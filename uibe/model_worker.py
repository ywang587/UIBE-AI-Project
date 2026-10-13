"""Isolated model process frees model memory when a video finishes."""
import argparse
import json
import os
from pathlib import Path
import time
from .analysis import chunks,messages,normalize,parse_json,combine
from .structured import load_generator,extraction_schema,comparison_schema,filter_content


def run(transcript, metadata, model, output, raw_dir):
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
        chat=messages(segment_group,metadata)
        for attempt in range(2):
            text=generate(chat,extraction_schema(segment_group))
            (raw_dir/f'chunk-{index}-attempt-{attempt}.txt').write_text(text,encoding='utf-8')
            try:
                part=normalize(parse_json(text),segment_group)
                break
            except (ValueError,TypeError,KeyError) as error:
                if attempt:raise ValueError(f'模型输出未通过结构和证据检查：{error}') from error
                # Do not feed back long invalid citation lists: they anchor the next answer.
                chat=messages(segment_group,metadata)
                chat.append({'role':'user','content':f'上次输出失败：{error}。这次只提取最多4条原子主张，每条不超过30个中文字，每条最多4个证据编号。主张太宽就缩小表述，只记录直接依据，不能列出整段连续编号。期限、条件没明说就填未说明。请输出完整 JSON。'})
        parts.append(part)
        print(f'已分析 {index+1} 段输入',flush=True)
    result=combine(parts,transcript,model,time.monotonic()-started)
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
    a=p.parse_args()
    if a.compare:compare(json.loads(a.compare.read_text()),a.model,a.output)
    elif a.transcript:
        run(json.loads(a.transcript.read_text()),json.loads(a.metadata.read_text()) if a.metadata else {},
            a.model,a.output,a.output.parent/'model-output')
    else:p.error('Provide --transcript or --compare')
