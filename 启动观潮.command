#!/bin/zsh
set -eu
APP_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
cd -- "$APP_ROOT"
PYTHON_BIN="${UIBE_APP_PYTHON:-$APP_ROOT/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || { print '请先按 docs/APP.md 安装运行环境。'; exit 1; }
print '观潮将在 http://127.0.0.1:7860 启动。关闭此窗口后停止处理；下次启动会继续。'
"$PYTHON_BIN" -m uibe.server --port 7860 --open-browser
