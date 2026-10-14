"""Small synthetic regression suite; this is not an independent accuracy study."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uibe.analysis import parse_json,PROMPT_VERSION,EXPERIMENTAL_VERSION
from uibe.comparison import payload,normalize as normalize_comparison
from uibe.structured import load_generator,comparison_schema,filter_content
from uibe.extraction import extract_part


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',default='mlx-community/Qwen3-4B-Instruct-2507-4bit')
    parser.add_argument('--output',type=Path,default=ROOT/'local_data/model-evaluation.json')
    parser.add_argument('--section',choices=['all','extraction','comparison'],default='all')
    parser.add_argument('--experimental-source-fields',action='store_true')
    args=parser.parse_args()
    os.environ.setdefault('HF_HOME',str(ROOT/'local_data/model-cache'))
    generate=load_generator(args.model)
    cases_path=ROOT/'tests/evaluation_cases.json'
    cases=json.loads(cases_path.read_text())
    if args.section!='all':cases['extraction' if args.section=='comparison' else 'comparison']=[]
    results=[]
    def ask(chat,schema,validator):
        for attempt in range(2):
            text=generate(chat,schema,max_tokens=2200)
            try:return validator(parse_json(text))
            except (ValueError,KeyError,TypeError) as error:
                if attempt:raise
                chat += [{'role':'assistant','content':text},{'role':'user','content':str(error)+'。请重写完整 JSON。'}]
    for case in cases['extraction']:
        start=time.monotonic()
        try:
            gate=filter_content(generate,case['segments'])
            result=extract_part(generate,case['segments'],{},strict_fields=args.experimental_source_fields) if gate['relevant'] else {'relevant':False,'claims':[],'reason':gate['reason']}
            checks={}
            if 'expected_relevant' in case:checks['relevance']=result['relevant']==case['expected_relevant']
            if 'expected_kind' in case:checks['claim_kind']=any(c['kind']==case['expected_kind'] for c in result['claims'])
            if case['id']=='explicit_mechanism_only':
                checks['no_added_rate_mechanism']=not any('降息' in c['statement'] for c in result['claims'])
            if case['id']=='source_instruction_is_data':
                checks['no_injected_prediction']=not any(c['kind']=='博主预测' and '一定上涨' in c['statement'] for c in result['claims'])
            if case['id']=='prediction_conditions':
                predictions=[c for c in result['claims'] if c['kind']=='博主预测']
                checks['condition_and_horizon']=any('政策' in c['conditions'] and '三个月' in c['time_horizon'] for c in predictions)
            row={'id':case['id'],'checks':checks,'passed':all(checks.values()),'result':result}
        except Exception as error:row={'id':case['id'],'passed':False,'error':str(error)}
        row['elapsed_seconds']=round(time.monotonic()-start,3);results.append(row)
        print(row['id'],row['passed'],row['elapsed_seconds'],flush=True)
    def video(text):
        return {'title':'合成测试材料','analysis':{'events':[],
            'claims':[{'statement':text,'evidence':[{'segment_id':1,'quote':text}]}]}}
    for case in cases['comparison']:
        start=time.monotonic();left=video(case['left']);right=video(case['right'])
        try:
            result=ask(payload(left,right),comparison_schema(left,right),lambda raw:normalize_comparison(raw,left,right))
            passed=result['relation']==case['expected_relation'] if 'expected_relation' in case else result['relation']!=case['not_relation']
            row={'id':case['id'],'passed':passed,'result':result}
        except Exception as error:row={'id':case['id'],'passed':False,'error':str(error)}
        row['elapsed_seconds']=round(time.monotonic()-start,3);results.append(row)
        print(row['id'],row['passed'],row['elapsed_seconds'],flush=True)
    output={'model':args.model,'section':args.section,'independent_evaluation':False,'cases_sha256':hashlib.sha256(cases_path.read_bytes()).hexdigest(),
            'pipeline_version':EXPERIMENTAL_VERSION if args.experimental_source_fields else PROMPT_VERSION,
            'experimental_source_fields':args.experimental_source_fields,'inference':getattr(generate,'provenance',{}),
            'passed':sum(r['passed'] for r in results),'total':len(results),'results':results,
            'limitation':'Synthetic development checks only. Semantic correctness still requires source review.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    if output['passed']!=output['total']:sys.exit(1)


if __name__=='__main__':main()
