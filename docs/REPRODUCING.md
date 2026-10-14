# 从零复现、测试与调试

本说明和仓库文件足以让没有历史聊天的开发者接手。现有完整运行环境是 **Apple Silicon Mac、macOS 15+、原生 arm64 Python 3.11/3.12**；本轮依赖快照在 Python 3.11 实测。账号是否与原作者相同不影响源码；运行环境必须确实能够访问这台 Mac 的工作目录和本地算力。

原作者的视频、转录、数据库和登录状态不在仓库，也不需要上传。这里分别提供无私人素材的自动检查，以及历史真实输入的获取与核验方法。模型生成、平台返回和官方背景会随环境及时间变化，不能保证生成文字逐字一致；严格对照须记录输入哈希、代码、依赖、模型快照和推理参数。

队友可使用自己的 Codex 账号和 GitHub 账号。读取、安装和本地修改不需要原作者账号；推送到原仓库需要 GitHub 协作者权限，没有权限时可 Fork 到自己的 GitHub 再提交修改，不共享账号或凭据。

## 1. 获取完整程序与固定依赖

仓库默认 `main` 是入口说明，应用在 `codex/local-pipeline-validation`。从主链接进入的开发 AI 应先读根目录 `AGENTS.md`，再切换程序分支。ZIP 下载者须先选择该分支。

```bash
git clone --branch codex/local-pipeline-validation https://github.com/ywang587/UIBE-AI-Project.git
cd UIBE-AI-Project
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints-macos-py311.txt -r requirements-app.txt -r requirements-local-model.txt
python -m pip check
git rev-parse HEAD
```

`constraints-macos-py311.txt` 记录本轮独立环境的运行和测试依赖版本，包含可选浏览器测试包的约束，但不会自动安装它们。Python 3.12 可按 APP.md 安装，尚未用这份完整快照在 3.12 重测。不要复制 `.venv`、原作者的绝对路径、Cookie 或数据库。

## 2. 无需模型、登录或旧视频的工程与页面检查

```bash
python -m unittest discover -s tests -v
python -m pip install -c constraints-macos-py311.txt -r requirements-test.txt
python -m playwright install chromium
python scripts/smoke_browser.py
```

工程套件当前为 53 项。页面脚本自动生成无声测试画面、合成文字稿和临时数据库，以随机本机端口启动隔离服务，测试完成后关闭。它检查：无关视频隐藏且计数正确、关注页保留已导入更新、三条重点、完整主张展开、简体显示与原始稿下载、媒体跳转播放、390 像素宽度与脚本错误。不会使用或写入 `local_data/app/`，也不会执行抖音采集或模型推理。

报告、截图、日志在 `local_data/browser-smoke/`。重复执行须换新目录，例如 `--output local_data/browser-smoke-02`，不覆盖旧结果。这些是**合成界面回归**，不能写成真实视频或模型准确性验证。

## 3. 无需旧素材的真实转录与模型流程

```bash
python scripts/smoke_local.py
```

脚本通过 macOS 的 `say` 和 Tingting 中文声音生成本项目原创测试语音，然后使用真实 Faster-Whisper medium 和 Qwen 本地模型，在独立资料库中处理。检查非空转录、财经相关主张、原话引用、来源哈希及重复导入。默认模型不存在时首次自动下载，不需要付费 API。

输出在 `local_data/smoke-local/`，含 `speech.txt`、生成的 WAV、`report.json` 和 `app/videos/<id>/runs/<job>/` 内的分步日志。失败也保留报告；重复运行使用 `--output local_data/smoke-local-02`。如果系统没有 Tingting，运行 `say -v '?'` 查看声音，并在系统辅助功能的朗读设置中安装中文声音，或通过 `--voice` 指定已安装中文声音。

这个检查会真实加载模型，须与其他视频分析串行执行。通过只能证明短合成语音的完整流程可运行，不替代长视频、平台下载或真实内容准确性检查。

需要固定到历史权重快照时，在已激活环境里执行：

```bash
hf download mlx-community/Qwen3-4B-Instruct-2507-4bit --revision 50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b --cache-dir local_data/model-cache/hub
hf download Systran/faster-whisper-medium --revision 08e178d48790749d25932bbc082711ddcfdfbc4f --cache-dir local_data/model-cache/hub
```

这两条命令返回各自快照目录。将目录传给 `smoke_local.py --model <Qwen快照目录> --asr-model <Whisper快照目录>`，或者填入程序的分析/转录模型设置。使用已有完整缓存即可，无需为了复现而重复下载。复跑脚本生成的语音也可能随 macOS 声音版本不同，实际哈希保存在报告中。

## 4. 复跑已经做过的模型实验

以下案例、提示词与判定代码均在 GitHub，不需要原始视频：

```bash
python scripts/evaluate_local_model.py --output local_data/model-evaluation-current.json
python scripts/evaluate_local_model.py --section comparison --output local_data/comparison-current.json
python scripts/evaluate_source_review.py --output local_data/source-review-current.json
```

`tests/evaluation_cases.json` 包含 4 项领域筛选/提取和 3 项关系对照案例；`tests/source_review_cases.json` 包含 15 项来源审查正反例。程序会真实调用模型，退出码 1 表示至少一项未通过；必须读取 JSON 的各项结果，不能把它直接当成安装失败。来源审查曾出现大量误拒绝，因此没有接入正常分析流程，历史记录不要求当前实验全部通过。

两个脚本均可传 `--model <模型ID或本地快照目录>`。候选 Qwen3.5 的历史结果见相应报告，候选模型不是正常运行前置条件。不要为了测试而切换应用的默认模型。实验性的字段约束仅在 `evaluate_local_model.py --experimental-source-fields` 明确启用时运行，不能混同默认流程。

历史输出在 `docs/validation/`，代码也会继续变化。对比前检查报告中的 `pipeline_version`、模型版本、样本哈希和已知失败。不同版本的条目数、耗时和措辞不应该强行改到一致。

## 5. 历史真实视频、下载和监控测试

`tests/real_pipeline_cases.json` 列出 7 条曾进入应用的视频：公开链接、视频 ID、SHA256、时长和模型快照。`tests/historical_media_inventory.json` 列出早期 24 条下载/媒体核对样本的公开标识和文件指纹；不包含本机路径、视频或文字稿。两份清单不是自动授权批量下载的任务。

1. 按 [APP.md 的抖音安装与登录部分](APP.md#可选抖音链接和关注更新) 配好 MediaCrawler，用自己的账号在新电脑登录。
2. 从清单选一条短片，先用下载探测工具获取；将 `<视频ID>` 换成清单中的数字：

   ```bash
   ../MediaCrawler/.venv/bin/python scripts/probe_download.py ../MediaCrawler <视频ID> --output local_data/replay-download
   shasum -a 256 local_data/replay-download/dy/media/<视频ID>/video.mp4
   ```

3. 比较实际哈希与清单。相同才是同一文件；平台重新编码、替换或下架后不能假装完全复现。获取失败可改用自己有权使用的视频来验证同一种流程，但报告须标明更换输入。不要复制原作者的登录状态。
4. 启动独立资料库：`python -m uibe.server --port 7862 --data-dir local_data/replay-app`。打开 `http://127.0.0.1:7862`，上传刚下载的文件；观察下载/转录/分析状态，查看重点、展开原话、跳转播放、下载 JSON。无关生活片段应不出现在首页，仍在“关注与更新”保留。
5. 长短视频分别验证。需要两作者对照时导入清单中的 `7693573120950603018` 和 `7694611088712666394`，完成单条分析后在详情选择另一条并点击“对照”。若使用本地文件导入，作者身份可能未知，应记录此情况；也可在配置好的独立应用里直接从原链接导入。旧版本曾出现两次错误分歧，不能将历史“互补”当作任何新版必然正确的答案。
6. 关注一位自己选择的博主，检查更新并导入其中一条；核对发现列表在导入后仍保留。只开启定期检查、保持自动分析关闭，退出并重启独立服务，检查启动补查。分页失败不推进检查点的路径由工程测试模拟，不要人为破坏自己的登录状态制造失败。

早期全部 24 条文件如果已经自行获得，可执行原媒体审计：

```bash
python scripts/audit_media.py <存放这24条MP4的目录> tests/historical_media_inventory.json --output local_data/media-replay-audit.json
```

它按哈希识别，不依赖文件名；少一条或哈希不匹配都会报告缺失。其他来源的同主题视频不能作为这 24 条的完全复现。完整解码和关键帧抽查仍不代表语音识别或金融解释准确。

## 6. 调试与修改

先读 `AGENTS.md`、`docs/HANDOFF.md` 的代码导航和 `docs/PROJECT_STATE.md` 的已知问题。所有正常资料库均为 `--data-dir` 指定目录，默认 `local_data/app/`：

- `settings.json`：当前设备 Python、转录/分析模型、采集器和监控设置。
- `history.sqlite3`：`videos`、`jobs`、`creators`、`discoveries`、`comparisons`。优先经 API/界面读取，不手改生产库。
- `videos/<video_id>/runs/<job_id>/`：`download.log`、`transcribe.log`、`analysis.log`，完整文字稿、分析 JSON 与 `model-output/` 中的原始尝试。
- `creators/<creator_id>/`：发现列表与检查日志；`comparisons/<job_id>/`：双方输入、选择依据与对照结果。

代码入口：`uibe/server.py` 提供 API，`engine.py` 串行任务，`store.py` 保存队列；`structured.py` 加载 MLX，`extraction.py`/`analysis.py` 提取和校验，`summaries.py` 选重点，`comparison_focus.py`/`comparison.py` 对照，`web/` 显示。可用 FastAPI 的 `/docs` 查看当前接口；在独立测试实例上调试写操作。

修改后先跑工程测试；界面改动跑浏览器脚本；模型/转录改动再跑对应真实模型检查及必要媒体样例。记录代码提交、环境版本、输入哈希、执行命令、结果、失败与未测试范围。不要把历史旧报告改成新版本测试记录，也不要把“引文存在”写成“原意准确”。

## 7. 交付给队友的完成标准

队友无需聊天记录，能够仅从主链接找到程序分支、安装依赖、运行 53 项工程检查及页面脚本、在 Mac 上运行真实短流程、定位日志、按清单选择真实视频与重跑模型实验，再按代码导航调试修改，即满足源码与方法的交接。

不包含承诺恢复原作者的私人历史库、免去新设备扫码、保证平台视频永久可用，或保证所有模型输出与旧报告逐字一致。此类限制不是补写文档就能消除的，须在复跑记录里如实说明。
