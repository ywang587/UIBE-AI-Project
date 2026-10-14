# 观潮课程程序

观潮把本地视频或抖音分享链接放入处理队列，依次获取视频、转录、提取主张，再将分析与原文证据一起显示。窗口内可查看历史、关注博主的新发现及失败记录。分析采用本地模型，不需要 API 密钥。

首次接手、复跑已有测试或继续修改程序，另见 [完整复现与调试步骤](REPRODUCING.md)。其中提供 Mac / Python 3.11 的依赖快照、可生成的测试素材、历史公开输入清单和各级验证命令。

## 换一台电脑：先下载正确版本

当前可运行应用位于 [`codex/local-pipeline-validation` 分支](https://github.com/ywang587/UIBE-AI-Project/tree/codex/local-pipeline-validation)，尚未合入 `main`。直接下载默认分支会得到旧交接资料。

打开上述分支后选择 **Code → Download ZIP**，解压并进入项目目录；也可以运行：

```bash
git clone --branch codex/local-pipeline-validation https://github.com/ywang587/UIBE-AI-Project.git
cd UIBE-AI-Project
```

GitHub 保存应用代码、界面、测试与依赖清单，不保存原始测试视频、转录稿、分析结果、模型、历史数据库和登录状态。新电脑可以从空资料库开始，导入自己的视频；运行应用不需要原课程的测试视频、Notebook、`outputs/` 或 Conda 环境。

## 必需环境

| 项目 | 要求 |
| --- | --- |
| 电脑 | Apple Silicon Mac（M 系列），原生 arm64 Python；当前没有完成 Windows、Linux 或 Intel Mac 的分析后端适配 |
| 系统 | 本次依赖组合中的 MLX Metal 安装包要求 macOS 15 或以上 |
| Python | 3.11 或 3.12，可使用 [Python 官方安装包](https://www.python.org/downloads/macos/)；下面以 `python3.11` 为例，3.12 用户对应替换 |
| 内存 | 本机 8GB 已跑通，但长视频可能明显变慢；建议 16GB 或更多，此建议不是另一设备上的性能测试结论 |
| 空间与网络 | 安装和首次下载模型需联网；建议预留至少 10GB，再额外预留视频空间 |
| API 密钥 | 不需要 |

仅分析本地视频时，不需要 MediaCrawler、Node.js、Jupyter、Conda，也不必单独安装 FFmpeg 命令。Faster-Whisper 通过已列入依赖的 PyAV 解码音频，参见[上游说明](https://github.com/SYSTRAN/faster-whisper#requirements)。

## 安装并启动

在解压或克隆后的项目根目录运行：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-app.txt -r requirements-local-model.txt
python -m pip check
python -m uibe.server --open-browser
```

浏览器将打开 `http://127.0.0.1:7860`。以后可以双击仓库中的 `启动观潮.command`，或再次运行最后一行。ZIP 解压后启动文件若没有执行权限，可以在项目目录运行 `chmod +x 启动观潮.command`。程序只监听本机地址；不要直接把无登录保护的个人程序暴露到公网。

首次运行先通过“导入视频”上传一个自己已有的短视频。资料目录会自动创建，不需要复制本机已有资料。关闭终端会停止服务；下次启动会恢复未完成任务。若显示端口被占用，先查看是否已经启动过观潮，直接使用已有窗口即可。

默认分析模型为 `mlx-community/Qwen3-4B-Instruct-2507-4bit`，由 Qwen3 4B 指令模型转换，模型文件约 2.26GB。[模型卡](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit)与[原始模型](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)。运行方法依据 [MLX LM 文档](https://github.com/ml-explore/mlx-lm)。首次使用需要联网下载，之后使用缓存。模型是当前可替换的实现选择，不是已确定的最优分析方法。

模型卡标注 Apache-2.0 许可。当前调用发生在本机，没有按次或按字数计费的模型 API；仍会占用电脑内存、磁盘和电力。默认的语音模型 `medium` 另外需要约 1.4GB，自动下载到 Hugging Face 缓存；分析模型自动缓存到项目的 `local_data/model-cache/`。第一次等待可能包含模型下载，后续使用缓存。模型服务商提供的付费托管接口与本程序的本地运行方式不同。

## 可选：抖音链接和关注更新

只导入本地视频可以跳过本节。在线下载和关注更新还需要独立的 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)、[Node.js](https://nodejs.org/en/download/) 和 Playwright Chromium。安装 Node.js 的 macOS arm64 LTS 版本，重新打开终端并确认 `node --version` 有输出。

在观潮项目根目录执行以下命令，建立并列目录。MediaCrawler 使用自己的环境，避免它的 Web 依赖与观潮冲突：

```bash
cd ..
git clone https://github.com/NanmiCoder/MediaCrawler.git
cd MediaCrawler
git checkout e9dd17a16338c3915f2335bc609383d316e055f2
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" .venv/bin/python -m playwright install chromium
```

在 MediaCrawler 的 `config/base_config.py` 中设置 `ENABLE_CDP_MODE = False`、`SAVE_LOGIN_STATE = True`、`SAVE_DATA_OPTION = "jsonl"`。观潮的关注检查使用标准 Playwright 会话，下载与首次登录也须使用同一模式和目录。无需复制原课程的 TXT 读取器或 Notebook，也不要运行只适用于已有课程材料的 `repair_course.py`。

首次登录在 **MediaCrawler 目录** 运行下面命令，把 `你自己的视频ID` 换成一条可访问视频链接中的数字 ID，再在打开的浏览器里完成扫码及平台提示。此步骤只读取一条视频的资料，不批量下载：

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" .venv/bin/python main.py \
  --platform dy --lt qrcode --type detail --specified_id 你自己的视频ID \
  --headless false --get_media false --get_comment false --save_data_option jsonl
```

登录完成后打开观潮“运行设置 → 设备环境”：

| 设置 | 填写内容 |
| --- | --- |
| 分析 Python、转录 Python | 新设备项目目录中的 `.venv/bin/python`；全新安装默认已指向当前环境 |
| MediaCrawler 目录 | 新设备的 `MediaCrawler` 绝对路径；按上述并列布局安装时默认可用 |
| MediaCrawler Python | 上述目录内 `.venv/bin/python` 的绝对路径 |
| Node.js 所在目录 | `command -v node` 返回路径的父目录；例如返回 `/opt/homebrew/bin/node` 时填写 `/opt/homebrew/bin` |

项目已确定关注 **Darling凯文Kevin** 和 **小Lin说**，名称及公开主页见 [`config/followed_creators.json`](../config/followed_creators.json)，具体添加步骤见[复现指南](REPRODUCING.md#已确定的两位关注博主)。清单不会自动导入。

保存后添加一个博主并检查更新。先保留“自动下载、转录和分析新发现的视频”为关闭，手动选一条验证。登录失效时重新执行登录步骤；观潮不会自动代为扫码或处理验证码。下载受平台可见性、账号状态和网络影响；安装完成不保证任意视频都能下载。外部组件仍遵循其自身许可。

## 常见安装与运行问题

- **没有合适的 MLX 安装包**：检查系统是否 macOS 15+，并用 `python3.11 -c "import platform; print(platform.machine())"` 确认结果是 `arm64`；不要用 Rosetta 下的 x86_64 环境安装。
- **缺少 Python 包**：在项目目录激活 `.venv` 后重新运行安装命令和 `python -m pip check`，不要复制旧设备的 `.venv`。
- **一直显示转录或分析**：在“处理记录 → 查看记录”检查日志。`medium` 使用 CPU 转录；随后 Qwen 分段分析并可能修正引文，长视频可能需要几十分钟。内存不足时磁盘交换会进一步拖慢；某一段耗时不能直接推算剩余总时长。
- **模型下载失败**：确认新电脑能访问 Hugging Face，再重试任务；不需要填写 API 密钥。
- **登录失效或找不到浏览器/Node**：按上一节检查 MediaCrawler 自己的 Python、`.browsers` 路径和 Node 目录，勿复制旧电脑的登录目录。
- **新电脑没有以前的历史**：这是正常的，运行资料不在 GitHub。本地测试视频无需上传，也不是安装的前置材料。数据库中的旧绝对路径不能靠复制文件自动重写，本版尚无一键历史迁移工具。

2026-10-13 在同一台 Mac 上新建了不继承 Conda 包的独立 Python 3.11 环境，按依赖清单安装，依赖检查、53 项测试和转录组件导入通过；尚未在第二台实体电脑重跑完整媒体流程。

## 使用顺序

1. 点击“导入视频”，上传已有文件，或粘贴完整链接、短链接及分享文字。重复内容会复用已有记录。
2. 在“处理记录”观察下载、转录、分析的状态；失败时可查看记录并重试。
3. 在“视频与解读”先看最多三条已选重点，需要时展开完整分析及原话，点击时间定位原视频。宏观无关视频不出现在首页，也不计入首页内容数量。
4. 在“关注与更新”填写抖音主页或 sec_uid。添加后立即检查，发现记录在导入后仍保留并显示处理状态；无关内容也可从这里查看。其他没有关联发现记录的无关导入内容单列保留。
5. 在“运行设置”选择是否定期检查和自动处理新发现。启用定期检查后，重新启动时会检查已关注博主；中断的处理任务会回到队列。

界面中的显示抖音号不一定是采集 API 所需标识，优先粘贴博主主页。MediaCrawler 路径、Python 和 Node 所在目录均由当前设备配置；扫码登录在已有课程下载入口完成，程序不会自动代为登录或处理验证码。

## 分析规则

全文按片段分组处理，不截去超长视频的结尾。每组附带此前最多 12 个片段作为上下文，并限制前文输入长度，减少主语与后半句话被切开的影响；原文与编号不变。先筛选是否涉及宏观金融，再按五种类别提取主张，最后单独整理事件。模型选择连续原文的起止编号；程序保留该范围内每一段未经改写的原话。每项引用最长 90 秒，长引文可展开并按时间回听。

程序检查阿拉伯数字是否在当前引文中出现，并要求日期、期限、条件逐字对应当前引用。全文处理完后，模型只从已有主张中选择最多三条编号作为摘要，优先呈现核心解释、条件和风险；摘要逐字使用所选主张，不再自由补写机制。选择失败时保留全部主张并提示查看原文，不生成替代结论。这些规则能拦住一部分错误，却不能证明因果、主体、中文数词或单位被忠实保留。某条主张未通过原话检查时，只重试这一条；其余主张保留。仍不合格的草稿单列为待复核，不参与摘要、事件简报和对照。事件整理失败也保留已有主张。

事实性主张、解释、评价、预测和推广保存在可展开的完整分析中，默认页面只显示重点。没有有效重点选择的旧记录保留原摘要，不把任意前三条冒充重点。日期、期限和条件未说明时保留缺失，不使用视频发布日期替代事件时间。

中文语音识别和模型输出可能混用简繁体，阅读界面通过 OpenCC `t2s` 统一显示简体，包括引文和文字稿。转换只生成显示副本，不改文件、引用编号、时间戳、路径或来源哈希；下载的 JSON 保留原始识别结果。简繁转换不会纠正人名、公司名、数字或识别错误，疑似错误仍须回听。

同一句话、相同期限和条件、同一组引文若被模型放入多个类别，合并为一条“分类待复核”，列出原候选类别。原文仍可查看，该项不进入自动摘要；对照输入保留分类不确定的说明。这个检查只发现完全重复内容的标签冲突，不能判断其他类别是否正确，也不会合并条件或引文不同的说法。

程序从历史分析中选择少量相关候选进行对照；也可在视频详情中选择另一条已分析视频，点击“对照这两条视频”。程序先定位共同问题，再分别从每位作者的全部已有主张中选择最多四条依据，保留原编号和完整引用。模型判断事件、期限、条件以及两种说法能否同时成立，再区分相近、分歧、互补或无法比较。相同资产、不同解释角度和不同语气不能直接算作分歧。期限或条件未确认对应时，不支持直接判为预测分歧。页面使用关系标签、核对提示与原文呈现结果；模型自由生成的解释保留为原始草稿，不作为新的市场机制展示。候选筛选可能遗漏相关视频；自动对照结果尚需独立评估。两位博主观点一致不代表事实被证实。当前没有通用外部新闻检索或自动事实核查，界面不宣称已核实。涉及美国债务规模时，会在分析后读取美国财政部公开数据，并单独显示记录日期、原始数值和来源。该背景可能晚于视频事件，不传入博主观点提取或对照，也不证明因果解释。

## 检查点和失败处理

程序保存视频 ID、文件哈希、处理状态和博主检查点。切换转录模型时会检查缓存对应的模型和视频哈希，避免复用其他模型的转录。下载、转录与本地分析依次执行，模型在子进程退出后释放内存。单个视频失败不会丢失其他已完成记录。

模型分析的等待上限随输入分段数增加，每段分配最多 10 分钟、整次至少 30 分钟；实际速度受电脑内存与其他程序占用影响。对照使用四位推理缓存减少长输入的内存占用；各阶段参数随结果记录。此设置是失败处理上限，不是预计完成时间。

作品发现限制页数，并保留覆盖不完整的提示。网络、登录、分页字段或游标异常时不推进成功检查点。到达整页早于回查边界时，记录为一次有明确范围的检查；这依赖平台列表顺序，删除、隐藏、置顶及平台行为仍可能带来遗漏。

## 验证范围

开发测试覆盖队列恢复、去重、失败检查点、片段引用及同事件判断规则。`tests/evaluation_cases.json` 是用于发现方法问题的合成案例，不是独立样本上的准确率证明。实际本地模型结果、处理耗时和浏览器检查见当次验证记录。

## 可复现检查

```bash
python -m unittest discover -s tests -v
python scripts/evaluate_local_model.py
```

第二项会真实加载本地模型并运行合成语义案例，需要安装本地模型依赖，结果保存在 `local_data/model-evaluation.json`。它检查无关内容、条件预测、原文中的提示词攻击，以及事件日期、期限和方向差异；不能据此报告真实视频准确率。

本机数据位于 `local_data/app/`，可用 `python -m uibe.server --data-dir /path/to/data` 指定其他位置。视频每次处理保留独立运行记录，历史对照保存当时的主张和原文快照。转录错误仍须回听核对；重新导入丢失的原视频可修复播放路径。

结构化本地生成参考 [Outlines 的 MLX LM 接入文档](https://github.com/dottxt-ai/outlines/blob/main/docs/features/models/mlxlm.md)。对照先判断比较维度，再生成关系；期限或条件不可比时，校验器拒绝“分歧”。

## 引用审查实验

`python scripts/evaluate_source_review.py` 检验自动引用审查，不改变应用数据。15 个合成正反例包含因果倒置、遗漏条件、主体变更，以及正常的改写、评价、预测和推广。当前审查方法在默认 Qwen3 模型上仅通过 9 项，在候选 Qwen3.5 模型上通过 8 项；它误拒绝了多条正常主张，因此**没有接入应用作为通过门槛，也没有启用基于审查结论的自动修订**。新模型没有替换默认模型。完整结果见 [本轮证据质量检查](validation/2026-10-13-grounding.md)。

## 官方背景与作者标识

美国债务背景使用财政部免费公开接口，无需 API 密钥。数据获取失败不影响已完成的主张；旧分析不会仅因升级代码就被覆盖。下载器返回遮蔽昵称时，应用保留已关注作者的信息，并保存稳定作者哈希来排除同一作者的自动对照。见 [本轮验证记录](validation/2026-10-13-background-and-identity.md)。

实验性的期限和资产字段约束只在命令行添加 `--experimental-source-fields` 时启用，默认应用尚未启用。它仍需真实视频回归，不能将工程测试通过当作提取质量已提高。
