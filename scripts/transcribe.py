"""Portable Chinese ASR; writes completed, source-identified timestamped bundles."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
import time


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def timestamp(seconds):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def validate_segments(segments, duration):
    previous = 0.0
    if not segments:
        raise ValueError('未识别到文字，不保存空白结果')
    for s in segments:
        if not s['text'].strip() or not (0 <= s['start'] <= s['end'] <= duration + 1):
            raise ValueError('文字或时间戳无效')
        if s['start'] < previous:
            raise ValueError('时间戳顺序错误')
        previous = s['start']


def run(video, output, model='medium', device='cpu', compute_type='int8', local_only=False, beam_size=5):
    video = Path(video).expanduser().resolve(strict=True)
    output = Path(output).expanduser().resolve()
    digest = sha256(video)
    settings = {'model': model, 'device': device, 'compute_type': compute_type,
                'language': 'zh', 'beam_size': beam_size, 'vad_filter': True,
                'condition_on_previous_text': True, 'task': 'transcribe'}
    config_digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:10]
    target = output / f'{digest[:16]}-{config_digest}'
    if target.exists():
        saved = json.loads((target / 'transcript.json').read_text(encoding='utf-8'))
        if saved['source']['sha256'] != digest or saved['settings'] != settings:
            raise ValueError('结果标识冲突，请使用新的输出目录')
        validate_segments(saved['segments'], saved['duration_seconds'])
        if not all((target / n).is_file() for n in ['transcript.txt', 'transcript.srt']):
            raise ValueError('已有结果不完整，请移走该结果后重跑')
        print(f'已有完整结果，跳过：{target}', flush=True)
        return target
    from faster_whisper import WhisperModel
    started = time.monotonic()
    print('加载语音模型……', flush=True)
    recognizer = WhisperModel(model, device=device, compute_type=compute_type,
                              local_files_only=local_only, cpu_threads=4)
    stream, info = recognizer.transcribe(str(video), language='zh', task='transcribe',
                                        beam_size=beam_size, vad_filter=True, condition_on_previous_text=True)
    segments = []
    for s in stream:
        if s.text.strip():
            row = {'id': len(segments) + 1, 'start': round(s.start, 3),
                   'end': round(s.end, 3), 'text': s.text.strip()}
            segments.append(row)
            print(f"[{row['start']:.1f}–{row['end']:.1f}] {row['text']}", flush=True)
    validate_segments(segments, info.duration)
    result = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
              'source': {'filename': video.name, 'sha256': digest, 'size_bytes': video.stat().st_size},
              'settings': settings, 'duration_seconds': info.duration,
              'elapsed_seconds': round(time.monotonic()-started, 3),
              'environment': {'python': platform.python_version(), 'system': platform.system(),
                              'machine': platform.machine(),
                              'packages': {p: version(p) for p in ['faster-whisper', 'ctranslate2', 'av']}},
              'quality_status': 'ASR output; not independently verified', 'segments': segments}
    output.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.incomplete-', dir=output))
    try:
        (staging / 'transcript.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        (staging / 'transcript.txt').write_text(''.join(f"[{s['start']:.3f}–{s['end']:.3f}] {s['text']}\n" for s in segments), encoding='utf-8')
        (staging / 'transcript.srt').write_text(''.join(f"{s['id']}\n{timestamp(s['start'])} --> {timestamp(s['end'])}\n{s['text']}\n\n" for s in segments), encoding='utf-8')
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f'完成：{target}', flush=True)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--output', type=Path, default=Path('local_data/transcripts'))
    parser.add_argument('--model', default='medium')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--compute-type', default='int8')
    parser.add_argument('--local-only', action='store_true')
    parser.add_argument('--beam-size', type=int, choices=range(1,11), default=5)
    a = parser.parse_args()
    run(a.video, a.output, a.model, a.device, a.compute_type, a.local_only, a.beam_size)
