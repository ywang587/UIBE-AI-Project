"""Repair copied course launchers; keep local settings and backups out of Git."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def backup(path):
    target = path.with_name(path.name + '.before-portability')
    if path.exists() and not target.exists():
        shutil.copy2(path, target)


def repair(root):
    root = root.resolve()
    crawler = root / 'MediaCrawler'
    repo = Path(__file__).resolve().parents[1]
    config = crawler / 'config/base_config.py'
    text = config.read_text(encoding='utf-8')
    lines = text.splitlines()
    replacement = "SAVE_DATA_PATH = str(__import__('pathlib').Path(__import__('os').environ.get('UIBE_DOWNLOAD_DIR', __import__('pathlib').Path(__file__).resolve().parents[2] / 'outputs' / '下载结果')).expanduser().resolve())"
    matched = [i for i, line in enumerate(lines) if line.startswith('SAVE_DATA_PATH =')]
    if len(matched) != 1:
        raise ValueError('无法唯一定位 SAVE_DATA_PATH，未修改')
    backup(config)
    lines[matched[0]] = replacement
    config.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    loader = crawler / 'config/course_urls.py'
    backup(loader)
    shutil.copy2(repo / 'scripts/course_urls.py', loader)
    launch = root / 'outputs/启动抖音视频下载.command'
    backup(launch)
    launch.write_text('''#!/bin/zsh
set -eu
COURSE_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
[[ ! -f "$COURSE_ROOT/.uibe-local.env" ]] || source "$COURSE_ROOT/.uibe-local.env"
[[ -z "${UIBE_NODE_DIR:-}" ]] || export PATH="$UIBE_NODE_DIR:$PATH"
cd -- "${UIBE_CRAWLER_DIR:-$COURSE_ROOT/MediaCrawler}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$PWD/.browsers}"
export MPLCONFIGDIR="$PWD/.matplotlib"
export UIBE_VIDEO_LINKS_DIR="${UIBE_VIDEO_LINKS_DIR:-$COURSE_ROOT/测试视频}"
export UIBE_DOWNLOAD_DIR="${UIBE_DOWNLOAD_DIR:-$COURSE_ROOT/outputs/下载结果}"
export PYTHONUNBUFFERED=1
command -v node >/dev/null || { print '请安装 Node.js 并加入 PATH。'; exit 1; }
PYTHON_BIN="${UIBE_CRAWLER_PYTHON:-$PWD/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || { print 'Python 环境不可用；请按项目运行说明重新创建环境。'; exit 1; }
"$PYTHON_BIN" main.py --platform dy --lt qrcode --type detail --get_media true --get_comment false --save_data_path "$UIBE_DOWNLOAD_DIR" "$@"
''', encoding='utf-8')
    launch.chmod(0o755)
    notebook_launcher = root / 'outputs/打开视频转文字.command'
    backup(notebook_launcher)
    notebook_launcher.write_text('''#!/bin/zsh
set -eu
COURSE_ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd -- "$COURSE_ROOT"
[[ ! -f "$COURSE_ROOT/.uibe-local.env" ]] || source "$COURSE_ROOT/.uibe-local.env"
PYTHON_BIN="${UIBE_TRANSCRIBE_PYTHON:-$COURSE_ROOT/UIBE-AI-Project/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || { print '请配置 UIBE_TRANSCRIBE_PYTHON 或建立项目 .venv。'; exit 1; }
export JUPYTER_PATH="$COURSE_ROOT/work/jupyter${JUPYTER_PATH:+:$JUPYTER_PATH}"
"$PYTHON_BIN" -m jupyterlab '视频转文字.ipynb'
''', encoding='utf-8')
    notebook_launcher.chmod(0o755)
    for name in ['视频转文字.ipynb', 'outputs/视频转文字_单视频测试.ipynb']:
        path = root / name
        backup(path)
        doc = json.loads(path.read_text(encoding='utf-8'))
        sources = [
            "from pathlib import Path\nimport os, sys\ncourse_root = Path(os.environ.get('UIBE_COURSE_ROOT', Path.cwd())).resolve()\nif course_root.name == 'outputs':\n    course_root = course_root.parent\nsys.path.insert(0, str(course_root / 'UIBE-AI-Project' / 'scripts'))\nfrom transcribe import run\n# 可替换为任意视频路径；输出按内容哈希隔离，不覆盖旧稿。\nvideo_path = course_root / '测试视频/测试视频10_8/印度经济困境！外汇储备大幅缩水.mp4'\n",
            "result_dir = run(video_path, course_root / 'UIBE-AI-Project/local_data/transcripts')\n",
            "print((result_dir / 'transcript.txt').read_text(encoding='utf-8'))\nprint('JSON 与 SRT 已一并保存：', result_dir)\n"]
        code_cells = [c for c in doc['cells'] if c['cell_type']=='code']
        if len(code_cells) != len(sources):
            raise ValueError(f'Notebook 结构改变，停止修改：{name}')
        for c, source in zip(code_cells, sources):
            c.update(source=source.splitlines(keepends=True), outputs=[], execution_count=None)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print('已修复启动脚本、链接读取、输出路径和 Notebook；原文件已备份。')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('course_root', type=Path)
    repair(p.parse_args().course_root)
