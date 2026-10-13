"""Isolated model process frees model memory when a video finishes."""
import argparse
import json
import os
from pathlib import Path
import time
import hashlib
from .analysis import chunks,parse_json,combine,SYSTEM,EXPERIMENTAL_VERSION
from .structured import load_generator,comparison_schema,filter_content
from .extraction import extract_part,EVENT_SYSTEM,CORRECTION_SYSTEM


def run(transcript, metadata, model, output, raw_dir,strict_fields=False):
    started=time.monotonic()
    generate=load_generator(model)
    raw_dir.mkdir(parents=True,exist_ok=True)
    parts=[]
    for index, segment_group in enumerate(chunks(transcript['segments'])):
        relevance=filter_content(generate,segment_group)
        (raw_dir/f'chunk-{index}-relevance.json').write_text(json.dumps(relevance,ensure_ascii=False),encoding='utf-8')
        if not relevance['relevant']:
            parts.append({'relevant':False,'title':metadata.get('title') or '无关内容记录',
                          'summary':relevance['reason'],'claims':[],'events':[],
                          'limitations':[],'asr_issues':[]})
            print(f'第 {index+1} 段与宏观金融无关，保留记录',flush=True)
            continue
        def save(name,text):
            (raw_dir/f'chunk-{index}-{name}').write_text(text,encoding='utf-8')
        part=extract_part(generate,segment_group,metadata,save,strict_fields=strict_fields)
        parts.append(part)
        print(f'已分析 {index+1} 段输入',flush=True)
    result=combine(parts,transcript,model,time.monotonic()-started)
    result['provenance'].update(getattr(generate,'provenance',{}))
    result['provenance']['experimental_source_fields']=strict_fields
    if strict_fields:result['provenance']['prompt_version']=EXPERIMENTAL_VERSION
    result['provenance']['prompts_sha256']=hashlib.sha256(('\n'.join([SYSTEM,EVENT_SYSTEM,CORRECTION_SYSTEM])).encode()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    staging=output.with_suffix('.tmp')
    staging.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(staging,output)
    return result


def compare(data,model,output):
    from .comparison import payload,normalize as validate_comparison,PROMPT_VERSION
    generate=load_generator(model)
    messages=payload(data['left'],data['right'])
    for attempt in range(2):
        text=generate(messages,comparison_schema(data['left'],data['right']),max_tokens=1000)
        try:
            result=validate_comparison(parse_json(text),data['left'],data['right']);break
        except (ValueError,KeyError,TypeError) as error:
            if attempt:raise
            messages += [{'role':'assistant','content':text},{'role':'user','content':str(error)+'。请重新输出完整有效 JSON。'}]
    result['model']=model
    result['prompt_version']=PROMPT_VERSION
    result['independently_evaluated']=False
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2));os.replace(temp,output)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--transcript',type=Path)
    p.add_argument('--compare',type=Path)
    p.add_argument('--metadata',type=Path)
    p.add_argument('--model',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--experimental-source-fields',action='store_true')
    a=p.parse_args()
    if a.compare:compare(json.loads(a.compare.read_text()),a.model,a.output)
    elif a.transcript:
        run(json.loads(a.transcript.read_text()),json.loads(a.metadata.read_text()) if a.metadata else {},
            a.model,a.output,a.output.parent/'model-output',strict_fields=a.experimental_source_fields)
    else:p.error('Provide --transcript or --compare')
