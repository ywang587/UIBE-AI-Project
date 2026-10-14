# UIBE AI Project

课程项目：从财经短视频中整理宏观事件、博主解释及共识与分歧，帮助理解金融市场正在讨论什么。

## 当前状态

**新同事 / 新设备先读 [交接指南](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/HANDOFF.md)**。2026-10-14 独立 Linux 环境已通过基础依赖安装、53 项工程测试与服务启动；完整模型分析仍仅支持下述 Apple Silicon 环境，详见 [复核记录](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/validation/2026-10-14-handoff-audit.md)。开发 AI 请同时阅读 [程序分支的 AGENTS.md](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/AGENTS.md)。

**下载应用请使用 [`codex/local-pipeline-validation` 分支](https://github.com/ywang587/UIBE-AI-Project/tree/codex/local-pipeline-validation)**（Code → Download ZIP）。`main` 尚是旧交接文档。新设备所需环境、安装步骤、模型下载及可选的抖音登录见 [完整安装说明](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/APP.md)。不需要上传或复制原来的本地测试视频。

2026-10-13：已接续可访问本地材料的环境，新增“观潮”本地应用。导入本地视频或抖音链接后，程序依次下载、转录、用本地模型提取主张，并将原文与可回放的时间位置一起展示，不需要付费 API。

应用提供历史记录、关注博主、启动补查、失败重试、同事件候选对照和已导入内容的事件简报。涉及美国债务规模时，还会单独显示带日期的官方背景，保留原始数值与来源；这不等于自动事实核查。自动分析与历史开发 AI 手工样例分别记录来源；结构与引文检查不等于分析准确率证明。

**启动应用：** 见 [观潮安装与使用](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/APP.md)。当前本地推理使用 Apple Silicon 上的 MLX；其他系统的推理后端尚未实现。已有工具见 [运行与换设备接续](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/RUNNING.md)。

本机现存六条真实视频记录，新增长视频及跨作者对照、失败修复和局限见 [首版交付验证](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/validation/2026-10-13-real-pair.md)。此前应用运行见 [应用验证](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/validation/2026-10-13-workbench.md)，前一阶段见 [本地接续验证](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/validation/2026-10-13-local-pipeline.md)。继续工作请先读 [项目状态与下一步](https://github.com/ywang587/UIBE-AI-Project/blob/codex/local-pipeline-validation/docs/PROJECT_STATE.md)。

## 已确认的产品目标

- 关注指定抖音博主，支持近期宏观财经内容，不限定黄金或某一种资产。
- 理想入口是博主主页或账号标识；首个 demo 允许手动导入视频或链接。
- 程序运行时检查更新；关闭时不要求运行；重新启动后补查遗漏。
- 提供单条视频解读、同事件跨博主对照，并逐步形成事件简报。
- 在程序内查看结果、历史和原视频；没有对照材料时先显示单条结果。
- 无关视频保留更新记录，不生成完整分析。
- 先解释已经发生的变化，保留原视频明确提出的预测与条件；预测准确性评估留待后续。

## 分析边界

分别呈现博主事实性主张、博主推断、外部背景和事实核查。
AI 不自行生成新的市场影响机制来填补博主解释，更不能把补充逻辑归到博主名下。
重要观点应能追溯到原文或时间位置；多位博主一致并不等于事实得到证实。
跨视频比较要核对事件、日期、期限和前提，允许相近、分歧、互补、无法比较。
平台 AI 摘要只能帮助定位，不能当作原始逐字稿。

## 协作和同步

由开发 AI 主动完成代码检查、合理实现选择、测试、问题修复和进度记录，不把常规验证交给用户。
只在账号授权、无法代办的本地操作或重大产品取舍上请求用户参与。
不访问或登录用户提到的第三方视频查询平台。

GitHub 保存项目代码、依赖说明、分析规则、测试结果与下一步；每个可复现阶段提交并推送。
运行环境、模型缓存、原始视频、数据库及登录状态不随普通 Git 提交自动同步。
换设备后先拉取仓库并阅读项目状态，再按环境说明恢复运行条件。
当前文档同步不表示开发已在后台持续运行。

## 外部组件

- [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)
- 用户材料记录的基线提交：`e9dd17a16338c3915f2335bc609383d316e055f2`
- 中文转录使用 Faster-Whisper；应用为本机浏览器界面，分析使用可替换的 Qwen3 4B 本地模型。

接入外部组件前检查其许可与本地修改，不直接复制整套依赖环境进本仓库。
