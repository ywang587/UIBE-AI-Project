# 新设备与 Codex 接手指南

更新：2026-10-14。项目名：观潮；仓库：https://github.com/ywang587/UIBE-AI-Project 。

**从零复现和调试请继续读 [REPRODUCING.md](REPRODUCING.md)**：固定依赖快照、自动页面检查、自动生成中文语音的真实模型流程、历史输入清单、模型实验与日志定位均有可执行步骤。只交给新 Codex 此仓库链接即可按根目录 `AGENTS.md` 找到这些入口，无需原聊天记录。

## 先知道这四件事

1. **程序已在 GitHub，但在 `codex/local-pipeline-validation` 分支，PR #1 尚为草稿。** 默认 `main` 是交接入口；下载时必须选择程序分支。
2. **完整分析目前需要 M 系列 Mac、macOS 15+、原生 arm64 Python 3.11/3.12。** Windows、Linux、Intel Mac 尚无分析后端；不能承诺任意电脑直接完整运行。
3. **新电脑可以从空资料库开始，不需要原作者的测试视频或聊天记录。** 模型首次下载；抖音功能另装 MediaCrawler 并在该设备自行登录。仅导入本地视频不需要抖音登录。
4. **同一个 Codex 账号不会把本地文件、模型、历史或登录状态搬过去。** 接手依据是此仓库；能否读取/修改本地文件和推送 GitHub，取决于当前工作区权限和 GitHub 授权。

## 下载、安装、运行

适用设备上打开终端，执行：

```bash
git clone --branch codex/local-pipeline-validation https://github.com/ywang587/UIBE-AI-Project.git
cd UIBE-AI-Project
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-app.txt -r requirements-local-model.txt
python -m pip check
python -m unittest discover -s tests -v
python -m uibe.server --open-browser
```

Python 3.12 用户将第一条 Python 命令改为 `python3.12`。浏览器地址为 `http://127.0.0.1:7860`。已有仓库先检查分支与未提交改动，不要覆盖或重新复制 `.venv`。

硬件、模型下载、双击启动、MediaCrawler 安装、新设备扫码登录和常见故障详见 [APP.md](APP.md)。若当前 Codex 在云端，不能据此操作你电脑上的目录；本地运行需要在已打开该项目目录的本地开发环境中完成。

安装完成的分级标准：

| 检查 | 完成标准 | 能证明什么 |
| --- | --- | --- |
| 基础工程 | `pip check` 与当前全部单元测试通过，服务首页可打开 | 依赖与工程回归；不能证明模型工作 |
| 本地视频 | 自备短视频导入后，转录和分析完成；可查看原文、时间位置并回放 | 当前设备上的完整本地流程 |
| 抖音下载（可选） | 当前设备独立登录后，一条可访问链接成功下载并分析 | 当前账号、链接和网络下的在线流程 |
| 关注更新（可选） | 检查一位博主、查看发现记录；启用定期检查后重启，日志显示补查 | 当前场景的监控；不代表无遗漏覆盖所有历史 |

先跑本地视频，再接抖音，便于定位故障。首次模型下载、CPU 转录和本地分析可能较慢；长视频在原 Mac 上曾花费几十分钟，不代表任务卡死。

## 项目已经做到哪里

- 可导入视频/链接，串行下载、转录、分析，去重、失败重试，保存历史并定位原视频。
- 单条分析保留博主主张及原文；同事件跨作者对照须核对问题、期限与条件；事件简报仅整理已导入资料。
- 提供关注博主、运行时检查及启动补查。默认不启用定期检查和新发现自动处理；需要在设置中开启。
- 美国债务规模可补充带日期的财政部背景；这不是通用新闻检索或自动事实核查。
- 真实长视频在原 Mac 已有完成记录，但语音识别、分类、条件提取和对照仍会出错；没有经过独立准确率评估。

细节以 [PROJECT_STATE.md](PROJECT_STATE.md) 和日期明确的验证记录为准。本次独立环境复核见 [2026-10-14-handoff-audit.md](validation/2026-10-14-handoff-audit.md)。该复核没有取得原 Mac 的全部聊天记录或私人运行数据。

## 接手修改时看哪里

| 文件/目录 | 用途 |
| --- | --- |
| `uibe/server.py`、`web/` | 本机服务、接口与界面 |
| `uibe/engine.py`、`uibe/store.py` | 队列、设备配置、任务与 SQLite 数据 |
| `uibe/analysis.py`、`uibe/structured.py` | 主张处理、证据校验与本地模型调用 |
| `uibe/comparison.py`、`uibe/background.py` | 条件对照与独立外部背景 |
| `scripts/` | 转录、采集适配及历史实验工具；并非全部是首次安装步骤 |
| `tests/` | 工程回归测试，包含模拟数据与模拟进程 |
| `docs/validation/` | 各版本验证范围、实际问题与局限 |

常见定位顺序：界面“处理记录 → 查看记录” → 当前设备设置/路径 → 对应处理步骤。不要为了换电脑重跑旧材料修复脚本。新设备默认路径会按当前项目推导；如果手动复制了旧配置，需重新填写 Python、MediaCrawler 和 Node 路径。

`local_data/`、虚拟环境、模型、原视频、历史数据库和 Cookie 不在 GitHub。当前没有一键历史迁移功能，复制数据库也不会自动改写旧绝对路径。先从空库运行；如需迁移历史，应单独设计备份、路径迁移与核验流程，不将这些数据推入公开仓库。

`constraints-macos-py311.txt` 提供本轮 Mac arm64 / Python 3.11 独立环境的完整包版本快照，用法见复现指南。它不是所有系统和 Python 版本的通用锁文件；未来重装若出现版本差异，记录实际版本及错误再修复，不把旧测试通过视为永久保证。

## 可直接发给新设备 Codex 的任务

> 请接手 https://github.com/ywang587/UIBE-AI-Project 。先检查工作区和设备，获取 `codex/local-pipeline-validation` 分支，阅读 `AGENTS.md`、`docs/HANDOFF.md`、`docs/PROJECT_STATE.md` 和 `docs/APP.md`。保留已有改动与运行数据，按当前设备安装并检查依赖、测试和启动；在适用的 Apple Silicon Mac 上用本机可用视频验证完整流程。不要假设能访问原作者电脑或聊天中的附件，不复制登录资料。记录已验证与受阻部分，修复可自行处理的问题，并将代码、检查结果和下一步推送 GitHub。

后续优先事项：适用新 Mac 的完整模型流程验收；分析/对照质量改进；长时间运行与平台异常恢复。若接手电脑是 Windows/Linux，应先单独安排可替换推理后端，不能仅改路径就宣称兼容。
