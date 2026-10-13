"""Run positive and negative controls against the actual local source reviewer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from uibe.structured import load_generator
from uibe.grounding_review import review_claim,supported,VERSION


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',default='mlx-community/Qwen3-4B-Instruct-2507-4bit')
    parser.add_argument('--output',type=Path,default=ROOT/'local_data/source-review-evaluation.json')
    args=parser.parse_args();os.environ.setdefault('HF_HOME',str(ROOT/'local_data/model-cache'))
    source=ROOT/'tests/source_review_cases.json';cases=json.loads(source.read_text())['cases']
    generate=load_generator(args.model);results=[]
    for case in cases:
        started=time.monotonic()
        claim={'statement':case['statement'],'kind':'博主事实性主张',
               'conditions':case.get('conditions','未说明'),'time_horizon':case.get('time_horizon','未说明'),
               'evidence':[{'segment_id':1,'quote':case['source']}]}
        try:
            review=review_claim(generate,claim)
            checks={'support':supported(review)==case['expected_support']}
            if 'expected_kind' in case:checks['kind']=review['recommended_kind']==case['expected_kind']
            result={'id':case['id'],'checks':checks,'passed':all(checks.values()),'result':review}
        except Exception as error:result={'id':case['id'],'passed':False,'error':str(error)}
        result['elapsed_seconds']=round(time.monotonic()-started,3);results.append(result)
        print(result['id'],result['passed'],result['elapsed_seconds'],flush=True)
    report={'model':args.model,'review_version':VERSION,'independent_evaluation':False,
            'cases_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'passed':sum(x['passed'] for x in results),'total':len(results),'results':results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if report['passed']!=report['total']:sys.exit(1)


if __name__=='__main__':main()
