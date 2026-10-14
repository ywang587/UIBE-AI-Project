"""Hash-match moved videos to inventory, decode every audio frame and sample video."""
import argparse
import json
from pathlib import Path
import platform
import av
from transcribe import sha256


def audit(root, inventory):
    known = {r['SHA256']: r for r in json.loads(inventory.read_text(encoding='utf-8'))}
    rows = []
    for path in sorted(root.rglob('*.mp4')):
        digest = sha256(path)
        row = {'file': path.relative_to(root).as_posix(), 'sha256': digest,
               'size_bytes': path.stat().st_size, 'video_id': known.get(digest, {}).get('视频ID')}
        try:
            with av.open(str(path)) as container:
                if not container.streams.audio or not container.streams.video:
                    raise ValueError('Missing audio or video stream')
                row['duration_seconds'] = container.duration / av.time_base
                frames = 0
                audio_end = 0
                for frame in container.decode(audio=0):
                    frames += 1
                    if frame.time is not None:
                        audio_end = max(audio_end, frame.time + frame.samples / frame.sample_rate)
                if not frames:
                    raise ValueError('Empty audio')
                row['audio_frames_decoded'] = frames
                row['audio_end_seconds'] = round(audio_end, 3)
            row['video_samples_seconds'] = []
            for pos in [0, row['duration_seconds']/2, max(0, row['duration_seconds']-2)]:
                with av.open(str(path)) as container:
                    container.seek(int(pos * av.time_base))
                    frame = next(container.decode(video=0))
                    row['video_samples_seconds'].append(frame.time)
            row['status'] = 'pass'
        except Exception as e:
            row['status'] = 'failed'
            row['error'] = f'{type(e).__name__}: {e}'
        rows.append(row)
        print(f"{len(rows)} {row['video_id']} {row['status']}", flush=True)
    seen = [r['video_id'] for r in rows if r['video_id']]
    return {'environment': {'python': platform.python_version(), 'av': av.__version__,
                            'system': platform.system(), 'machine': platform.machine()},
            'scope': 'SHA256 match; full audio decode; video keyframes at start/middle/end (not full video decode)',
            'files': rows, 'missing_ids': sorted(set(x['视频ID'] for x in known.values())-set(seen)),
            'duplicate_ids': sorted({x for x in seen if seen.count(x)>1})}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('inventory', type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    report = audit(a.root, a.inventory)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if not report['files'] or report['missing_ids'] or report['duplicate_ids'] or any(r['status']!='pass' or not r['video_id'] for r in report['files']):
        raise SystemExit(1)
