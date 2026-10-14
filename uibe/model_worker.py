"""Isolated model process frees model memory when a video finishes."""
import argparse
import json
import os
from pathlib import Path
import time
import hashlib
from .analysis import contextual_chunks,parse_json,combine,SYSTEM,EXPERIMENTAL_VERSION
from .structured import load_generator,comparison_schema,filter_content
from .extraction import extract_part,EVENT_SYSTEM,CORRECTION_SYSTEM
from .summaries import select_summary


def run(transcript, metadata, model, output, raw_dir,strict_fields=False):
    started=time.monotonic()
    generate=load_generator(model)
    raw_dir.mkdir(parents=True,exist_ok=True)
    parts=[]
    for index, segment_group in enumerate(contextual_chunks(transcript['segments'])):
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
    result=select_summary(generate,result,metadata.get('title'),
        lambda text:(raw_dir/'summary-selection.json').write_text(text,encoding='utf-8'))
    result['provenance']['elapsed_seconds']=round(time.monotonic()-started,3)
    result['provenance'].update(getattr(generate,'provenance',{}))
    result['provenance']['experimental_source_fields']=strict_fields
    result['provenance']['input_context_segments']=12
    result['provenance']['input_context_budget_chars']=800
    if strict_fields:result['provenance']['prompt_version']=EXPERIMENTAL_VERSION
    result['provenance']['prompts_sha256']=hashlib.sha256(('\n'.join([SYSTEM,EVENT_SYSTEM,CORRECTION_SYSTEM])).encode()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    staging=output.with_suffix('.tmp')
    staging.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(staging,output)
    return result


def compare(data,model,output):
    from .comparison import payload,normalize as validate_comparison,source_bound_result,PROMPT_VERSION
    from .comparison_focus import select_sources
    from .analysis import check_numbers
    started=time.monotonic()
    # Keep every source claim and quote; reduce cache memory for the longer pair input.
    generate=load_generator(model,kv_bits=4)
    output.parent.mkdir(parents=True,exist_ok=True)
    focus,selected=select_sources(generate,data['left'],data['right'],
        lambda name,text:output.with_name(output.stem+'-'+name).write_text(text,encoding='utf-8'))
    if not all(selected.values()):
        result={'same_event':False,'same_question':focus['shared_question'],'comparable_horizons':False,
                'comparable_conditions':False,'event':focus['question'] or '未确定','relation':'无法比较',
                'reason':'未选出足够的双方依据。'+focus['reason'],'left_claim_ids':[],'right_claim_ids':[],
                'coexistence':'依据不足',
                'limitations':['共同问题与依据选择仍可能遗漏相关主张，可回到完整视频核对。']}
    else:
        messages=payload(data['left'],data['right'],selected,focus['question'])
        schema=comparison_schema(data['left'],data['right'],selected)
        sources='\n'.join(c['statement']+'\n'+'\n'.join(e['quote'] for e in c['evidence'])
            for side in ['left','right'] for i,c in enumerate(data[side]['analysis']['claims'],1) if i in selected[side])
        for attempt in range(2):
            text=generate(messages,schema,max_tokens=1000)
            output.with_suffix(f'.attempt-{attempt}.txt').write_text(text,encoding='utf-8')
            try:
                raw=schema.model_validate_json(text).model_dump()
                result=validate_comparison(raw,data['left'],data['right'])
                check_numbers(result['event']+'\n'+result['reason'],sources,'对照说明');break
            except (ValueError,KeyError,TypeError) as error:
                if attempt:raise
                messages += [{'role':'assistant','content':text},{'role':'user','content':str(error)+'。请重新输出完整有效 JSON。'}]
    result=source_bound_result(result,data['left'],data['right'],focus['question'])
    result['focus']={**focus,'selected_claim_ids':selected}
    result['model']=model
    result['prompt_version']=PROMPT_VERSION
    result['independently_evaluated']=False
    result['provenance']={**getattr(generate,'provenance',{}),
        'elapsed_seconds':round(time.monotonic()-started,3)}
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
