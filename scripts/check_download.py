"""Verify one downloaded MP4 against MediaCrawler metadata and decode both tracks."""
import argparse
import json
from pathlib import Path
from transcribe import sha256


def read_jsonl(path):
    # splitlines() also splits U+2028 inside valid JSON strings; iterate LF records.
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def verify(root, video_id):
    import av
    root=Path(root)
    video=root/'dy/media'/video_id/'video.mp4'
    rows=[r for path in sorted(root.glob('douyin/jsonl/*.jsonl')) for r in read_jsonl(path)]
    matches=[r for r in rows if r.get('aweme_id')==video_id]
    if not matches:
        raise ValueError('找不到对应视频元数据')
    metadata=matches[-1]
    result={'video_id':video_id,'size_bytes':video.stat().st_size,'sha256':sha256(video),
            'metadata_records_for_id':len(matches),
            'metadata':{k:metadata.get(k) for k in ['aweme_id','nickname','create_time','aweme_url']}}
    with av.open(str(video)) as c:
        result['duration_seconds']=c.duration/av.time_base
        result['audio_frames']=sum(1 for _ in c.decode(audio=0))
    with av.open(str(video)) as c:
        result['video_frames']=sum(1 for _ in c.decode(video=0))
    if not result['audio_frames'] or not result['video_frames']:
        raise ValueError('视频或音轨没有可解码的帧')
    result['status']='pass'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('video_id')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=verify(a.root,a.video_id)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False,indent=2))
