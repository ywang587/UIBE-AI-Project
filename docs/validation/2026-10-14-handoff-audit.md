# 2026-10-14 GitHub 交接独立复核

## 范围与来源

用户要求同事仅通过 GitHub 即可获取程序并继续开发。本次未检索到名为“UIBE AI WYC MAC”的完整工作对话，也不能访问原作者 Mac；依据 GitHub 实际源码、PR #1、安装说明和历史验证报告进行复核。历史 Mac 测试是仓库记录，本报告中的 Linux 测试为本次实际执行，两者不能混同。

检查基线：`codex/local-pipeline-validation` 的 `a57a7b3118b302ec0e8dea1c49b49960f0dc0607`。检查时 `main` 为 `1c96165202dfbac9aeeb09e2c1c4a638f1fe6d38`，仅有旧交接资料；PR #1 为未合并草稿。程序源码确实已上传，但只克隆默认分支拿不到程序，这是最直接的交接缺口。

## 本次实际执行

从远端重新克隆程序分支，在独立 Linux x86_64 环境中新建 `.venv`，Python 3.12.14，不使用原 Mac 环境、模型、数据库或视频。

| 检查 | 结果 |
| --- | --- |
| `python -m pip install -r requirements-app.txt` | 成功；包括 Faster-Whisper、CTranslate2、PyAV、FastAPI 等 |
| `python -m pip check` | `No broken requirements found.` |
| `python -m unittest discover -s tests -v` | 53 项通过；0.270 秒；含模拟进程/数据，非真实模型评测 |
| 导入 `av`、`ctranslate2`、`faster_whisper` | 成功；没有加载或下载语音模型 |
| 启动真实 `python -m uibe.server --port <临时端口> --data-dir <空临时目录>` | 成功，`/api/state` 返回空视频库、空任务队列 |
| HTTP `/`、`/app.js`、`/style.css`、`/api/brief` | 均返回 200 且非空；结束后停止进程并移除临时数据 |
| `node --check web/app.js` | 成功；仅语法检查，非浏览器视觉验收 |
| 活跃源码、测试中搜索个人绝对目录 | 未发现 `/Users/`、`/workspace/`、`/home/`、`/opt/` 写死路径；仍需单独配置外部组件 |

测试输出包含 Starlette 对 TestClient 使用 httpx 的弃用提醒，目前未使任何测试失败；未来升级测试依赖时应复核兼容性。无需仅为消除警告更换当前运行依赖。

复现工程检查可运行：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m uibe.server --data-dir /tmp/uibe-handoff-check
```

最后一条启动后打开 `http://127.0.0.1:7860`；用新的空数据目录，不复用生产资料。Linux 上仅验证服务/界面与工程逻辑，不导入视频触发尚未适配的 MLX 分析。

## 没有验证的部分

- 没有在第二台 Apple Silicon Mac 下载模型、转录真实视频或完成本地分析。当前环境为 Linux，不能运行现有 MLX 分析后端。
- 没有使用用户账号重新登录抖音、下载实际视频或复测更新检查；不访问第三方查询网站。
- 没有迁移原 Mac 的历史资料，也不能检查未提交的本地改动是否存在。
- 没有证明 Windows/Linux/Intel Mac 支持完整程序，没有证明模型语义准确率或平台长期稳定性。

## 交接修复

- 新增 `docs/HANDOFF.md`：正确分支、平台限制、安装与分级验收、代码导航、数据边界、可复用 Codex 接手任务。
- 新增根目录 `AGENTS.md`：让新工作区的开发 AI 读取项目约束及测试方法，不依赖原聊天记录。
- 程序分支 README、项目状态增加本次入口；默认 `main` 的交接入口指向真正程序分支，避免把旧记录误当最新成果。
- 本次不修改运行逻辑，不合并草稿 PR，不宣称完成新的操作系统适配。

结论：代码与交接材料可以由 GitHub 获取并独立继续开发，基础依赖、53 项工程测试和服务启动在独立 Linux 环境通过。适用新 Mac 上的完整模型流程仍须作为该设备安装验收的一部分；换设备不等于自动同步私人历史数据。
