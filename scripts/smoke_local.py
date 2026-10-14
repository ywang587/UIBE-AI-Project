"""Generate original test speech on macOS and run the real ASR/model pipeline."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uibe.engine import Engine

SPEECH='这是一段程序测试材料。我认为昨天金价上涨与美元走弱有关。如果这项政策落实，我预计人民币未来三个月可能升值。这只是条件预测，政策现在还没有公布。'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'local_data/smoke-local')
    p.add_argument('--model',default='mlx-community/Qwen3-4B-Instruct-2507-4bit')
    p.add_argument('--asr-model',default='medium')
    p.add_argument('--voice',default='Tingting')
    args=p.parse_args()
    if platform.system()!='Darwin' or platform.machine()!='arm64':
        p.error('完整模型测试需要原生 Apple Silicon Mac；工程测试无需运行本脚本')
    output=args.output.resolve()
    if output.exists():p.error('输出目录已存在，请指定新的 --output；不覆盖上次测试或复用正式资料库')
    output.mkdir(parents=True)
    report={'scope':'generated speech; real ASR and model, not historical video or accuracy benchmark',
            'system':platform.platform(),'python':platform.python_version(),'model':args.model,
            'asr_model':args.asr_model,'passed':False}
    started=time.monotonic();engine=None
    try:
        speech=output/'speech.wav'
        (output/'speech.txt').write_text(SPEECH,encoding='utf-8')
        subprocess.run(['/usr/bin/say','-v',args.voice,'-r','170','-o',str(speech),
                        '--file-format=WAVE','--data-format=LEI16@16000',SPEECH],check=True,timeout=120)
        engine=Engine(output/'app')
        engine.save_settings({'model':args.model,'asr_model':args.asr_model,
                              'monitor_enabled':False,'auto_process_discoveries':False})
        vid,_=engine.import_file(speech,title='自动生成的中文财经流程样例')
        engine.start()
        previous=None;deadline=time.monotonic()+2400
        while time.monotonic()<deadline:
            job=engine.store.all('jobs')[0]
            marker=(job['status'],job['stage'])
            if marker!=previous:print(*marker,flush=True);previous=marker
            if job['status']=='failed':raise RuntimeError(job['error'])
            if job['status']=='completed':break
            time.sleep(1)
        else:raise TimeoutError('测试超时，日志保留在输出目录')
        video=engine.store.video(vid)
        transcript=json.loads(Path(video['transcript_path']).read_text())
        analysis=json.loads(Path(video['analysis_path']).read_text())
        digest=hashlib.sha256(speech.read_bytes()).hexdigest()
        assert digest==transcript['source']['sha256']==analysis['source_sha256']
        assert transcript['segments'] and analysis['relevant'] and analysis['claims']
        source={s['id']:s['text'] for s in transcript['segments']}
        assert all(source[e['segment_id']]==e['quote'] for c in analysis['claims'] for e in c['evidence'])
        assert engine.import_file(speech)[1] is False
        report.update(passed=True,video_id=vid,segments=len(transcript['segments']),claims=len(analysis['claims']),
                      source_sha256=digest,model_provenance=analysis.get('provenance'),deduplication=True)
    except Exception as error:
        report['error']=f'{type(error).__name__}: {error}'
        raise
    finally:
        if engine:engine.close()
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print('报告：',output/'report.json',flush=True)


if __name__=='__main__':main()
