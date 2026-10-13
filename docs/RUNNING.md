# 运行与换设备接续

本阶段提供可以单独运行的链接读取、媒体检查、中文转录和证据报告工具。分析报告接收已有分析 JSON，不会自动调用分析模型。原始视频、文字稿、登录状态和机器配置只留在本地。

## 安装转录环境

使用 Python 3.11 或 3.12，在仓库根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Windows 使用 `.venv\Scripts\activate` 激活。以上固定版本已在 macOS arm64 实测；Windows、Linux 和 CUDA 尚未验证。跨设备需重新创建虚拟环境，不能把复制后的 `.venv` 当作可移植程序。

## 中文转录

```bash
python scripts/transcribe.py /path/to/video.mp4 --output local_data/transcripts
```

默认使用 medium、CPU、int8、中文、beam size 5 与 VAD。首次运行需要下载模型；已有模型时可加 `--local-only`。`--model` 可接收本地模型目录，`--device`、`--compute-type` 和 `--beam-size` 可按设备设置。更改搜索宽度可能改变识别结果，不应把不同参数的速度直接比较。

每次成功生成一个结果目录，包含：

- `transcript.json`：原视频哈希、参数、运行环境、耗时、每段起止时间及原始识别文字。
- `transcript.txt`：带时间戳的文字稿。
- `transcript.srt`：字幕文件。

结果目录由视频内容哈希和参数标识确定。重跑相同输入与参数时复用完整结果；失败不会留下看似完成的空稿。旧文字稿和原视频不覆盖。原始识别不等于正确原话，尤其应检查数字、否定词、专有名词和财经术语。

## 证据报告

分析 JSON 至少包含 `source_sha256`、`title`、`method`、`claims`、`limitations`。每条主张包含 `kind`、`statement`、`evidence`、`limitation`；每条证据包含 `segment_id` 和原文 `quote`。支持的类别为博主事实性主张、博主解释、博主评价、博主预测、推广。

```bash
python scripts/evidence_report.py /path/to/transcript.json /path/to/analysis.json /path/to/video.mp4 --output local_data/report.html
```

报告检查视频哈希、转录来源和逐条引文，然后生成本地 HTML，可在浏览器中点击时间定位原视频。HTML 使用当前设备的本地视频地址，换设备后需要重新生成。引文存在只能证明引用位置有效，不能证明推理或分类正确。

当前没有自动分析模型、外部核查接口或跨视频比较器。`method` 应明确写出分析由谁以何种方式产生；开发 AI 整理的样例不能写成程序自动分析的结果。

## MediaCrawler 与课程材料

MediaCrawler 独立安装，基线提交为 `e9dd17a16338c3915f2335bc609383d316e055f2`。按其项目说明安装 Python 依赖、Node.js 和 Playwright 浏览器。保留其原许可，不将其虚拟环境、浏览器或登录状态提交到本仓库。

课程材料沿用以下布局：

```text
课程材料/
  MediaCrawler/
  UIBE-AI-Project/
  测试视频/
  outputs/
  视频转文字.ipynb
```

对这套已有材料执行一次修复：

```bash
python scripts/repair_course.py /path/to/课程材料
```

修复脚本备份旧文件后更新课程 TXT 读取器、下载输出路径、两个启动入口和两个中文 Notebook。它不安装依赖，也不修复虚拟环境本身；换设备须重新创建环境。原老师备份不改动。

课程根目录可放置仅本机使用的 `.uibe-local.env`，配置 `UIBE_TRANSCRIBE_PYTHON` 和可选 `UIBE_NODE_DIR`。该文件是用户自己的 shell 配置，不要使用他人提供的文件。其他可选变量包括 `UIBE_CRAWLER_DIR`、`UIBE_CRAWLER_PYTHON`、`UIBE_VIDEO_LINKS_DIR`、`UIBE_DOWNLOAD_DIR`。路径均由当前设备设置；Notebook 默认查找当前课程目录，也可设置 `UIBE_COURSE_ROOT`。

启动 Notebook 还需在选定 Python 环境安装 JupyterLab 与 ipykernel；内核必须使用已装 Faster-Whisper 的 Python。

TXT 支持完整链接、分享长链接、带 `modal_id` 的页面链接、短链接及整段分享文字。短链接通过网络跳转解析；网络失败会显式报错，不静默丢失输入。相同 ID 去重；这不等于任意目录下的视频都能自动复用，已移动到课程目录的原始视频仍需通过清单建立对应关系。

仅测试一条视频且不触发登录的方式：

```bash
/path/to/MediaCrawler/.venv/bin/python scripts/probe_download.py /path/to/MediaCrawler 7695692306247499738 --output local_data/download-probe
```

该探测使用已有会话；若需要重新登录则停止，交由用户在正常浏览器中处理。不要把程序退出码单独当作下载成功，必须确认 MP4、元数据和解码结果。macOS 沙箱可能阻止 Chromium 启动，这与平台下载失败不同。

## 已有视频的完整性检查

```bash
python scripts/audit_media.py /path/to/测试视频 /path/to/视频整理清单.json --output local_data/media-audit.json
```

工具以 SHA256 重新对应移动或重命名的视频，不相信旧清单中的绝对路径；完整解码音轨并抽查三个位置的视频关键帧，报告缺失、重复及失败。它不是逐帧视频检测，也不测量转录准确率。

## GitHub 与数据

接续分支：`codex/local-pipeline-validation`。先阅读 `docs/PROJECT_STATE.md` 和最新验证报告，再运行具体步骤。GitHub 保存程序和工程记录；`local_data/` 中的视频、字幕、分析 JSON 和报告需另行传递。GitHub 同步不会让另一台机器自动拥有登录状态或原始数据。
