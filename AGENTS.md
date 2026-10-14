# 接手观潮

本仓库是项目交接依据，不依赖原作者的聊天记录或个人电脑目录。

## 开始工作

1. 先检查 `git status`、当前分支和远端更新，保留已有未提交改动。
2. 阅读 `docs/HANDOFF.md`、`docs/REPRODUCING.md`、`docs/PROJECT_STATE.md`、`docs/APP.md`。程序目前在 `codex/local-pipeline-validation`，PR #1；不要把旧 `main` 文档当作最新实现。
3. 确认当前设备和 Python。完整本地分析目前限 Apple Silicon / macOS 15+ / 原生 arm64 Python 3.11 或 3.12；Linux 的测试通过不代表 MLX 推理可用。
4. 先检查已有虚拟环境、模型缓存、队列和结果，再决定安装或重跑，避免重复处理长视频。

## 开发约束

- 产品目标和分析边界见项目状态：区分博主主张与外部背景，不替博主编造市场机制；原文引用检查不等于语义准确。
- 不访问或登录用户提到的第三方视频查询平台。抖音登录由设备使用者完成；不复制登录状态。
- 不提交原始视频、转录/分析私人资料、数据库、模型、Cookie、密钥、`.venv` 或设备专属配置。路径应由项目位置推导或配置，不能写死某个人的目录。
- 基础回归命令：`.venv/bin/python -m pip check` 和 `.venv/bin/python -m unittest discover -s tests -v`。修改界面脚本时可用 `node --check web/app.js` 检查语法，Node 不是本地视频运行的必需依赖。
- 可独立复跑的页面测试是 `scripts/smoke_browser.py`（合成记录、不运行模型）；Mac 的真实短流程测试是 `scripts/smoke_local.py`（自动生成语音、真实转录和推理）。先检查没有其他模型任务，再串行运行。二者均使用隔离资料库，报告留在忽略目录。
- 已确认的两位关注博主在 `config/followed_creators.json`。用户明确允许公开这两位的名称和公开主页；新设备按复现指南添加，不复制旧数据库、检查点或登录状态。
- 历史视频标识在 `tests/real_pipeline_cases.json` 和 `tests/historical_media_inventory.json`，只保存公开链接和指纹。不要自动批量下载或上传原始视频；不同哈希的输入不能写成原历史样本的完全复现。
- 将代码、实际验证范围、失败原因和下一步一起提交并推送；用明确的分支/提交标识交接。不要把模拟测试、旧机器验证或历史报告写成本机实测。
