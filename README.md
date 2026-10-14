# zh-replies

用同一份本地规则改善 Claude Code 和 Codex 给用户的中文回复：表达自然、征求意见像商量、指代和说明对象清楚。默认让原模型参考规则生成回复，不增加独立检查调用；规则仍占 context tokens。

第一版验收的是 macOS 上 Claude Code CLI 2.1.286 与 Codex CLI 0.159.0-alpha.12.1。中文对照使用 Claude Opus 5.5 与 Codex gpt-6.1-sol（low）；其他模型未测。没有将 CLI 结果推广成 Codex cloud 或其他 agent 已通过验收。规则可复制到其他 agent 的指令文件，实际加载和效果需要分别验证。

## 启用

需要 Python 3.11+，无需安装 Python package。在本目录运行：

```sh
python3 zh_replies.py install
python3 zh_replies.py status
```

install 将 `rules/core.md` 的完整 snapshot 写入 `~/.claude/CLAUDE.md` 与 `~/.codex/AGENTS.md`，然后开始新的 session。加 `--with-hooks` 会同时把三个 Claude Code hook（UserPromptSubmit、MessageDisplay、Stop，见下文）写进 `~/.claude/settings.json`，其他设置不动；`disable` 一并移除这三条；`status` 的 `hooks_installed` 报告是否装齐。hook 用 haiku，需要已登录的 Claude Code。已有文件的其他内容保持原样；修改前保存本地 backup。指定 `--agent claude` 或 `--agent codex` 可只启用一个。自定义 profile 可用 `--claude-dir PATH`、`--codex-dir PATH`；默认尊重 `CLAUDE_CONFIG_DIR` 与 `CODEX_HOME`。

status 报告安装位置、snapshot、个人来源和可检测的 Codex override。当前 session 是否载入并遵守规则仍是 unknown。原有 user/project instructions 可能冲突；Claude safe/minimal mode 不会按普通方式加载，Codex global override 会遮蔽 AGENTS.md。Codex 安装目标超过 32768 UTF-8 bytes 时拒绝；这是产品的保守上限。项目指令另有 agent 自身的加载预算。

## 个人规则、update 和停用

在本地创建一个 UTF-8 文字文件，例如 `~/.config/zh-replies/personal.md`，只写你自己的表达偏好：

```text
技术动词保留英文，例如 deploy、parse、validate、cache。
同一个概念始终用同一个名字。
```

```sh
python3 zh_replies.py install --personal ~/.config/zh-replies/personal.md
```

手动编辑个人文件后，再运行 `install`：每个 target 会重读自己记录的来源。update 通用规则也运行 `install`。`install --without-personal` 明确移除个人 snapshot；来源失踪时会报错，不会悄悄删掉偏好。

```sh
python3 zh_replies.py disable
```

disable 只移除自己的 block，个人源文件保留。再次启用 personal 需要重新传 `--personal PATH`。启用、update、停用都在新 session 生效；已经进入 context 的旧规则不会从旧 session 里消失。

请编辑个人源文件或 `rules/core.md`，再 install。手改已安装 block、标记破损或 symlink target 会拒绝修改。可以核对 target 旁的 `.CLAUDE.md.zh-replies-backup-*` / `.AGENTS.md.zh-replies-backup-*`，把手改偏好移到个人源文件，恢复原 block 后重跑。每个 target 原子写入；若第二个写入失败，错误会列出已完成 target，重跑可继续。请保留其他工具同时修改文件时的独立 backup。

## 可选检查：独立 Claude Code 入口

`reply --check` 是单独的问答入口。它不接管 Claude Code TUI 或 Codex 的显示，也不维护多轮 native session。需要已有 Claude Code 登录；只支持问答与 Read，不支持写文件、运行命令或其他 tools。

```sh
printf '%s\n' '请简短解释当前项目的 README。' | python3 zh_replies.py reply --check
```

在当前项目目录运行；也可使用本工具的绝对路径。先捕获 Claude 完整回复，再启用一个独立 Claude checker session。检查成功后才显示完整回复。`reply` 不带 `--check` 时只生成，默认没有 checker。`--personal PATH` 只用于本次 reply，不继承安装 snapshot；`--protect '固定术语或引文'` 可以重复使用。

两阶段使用相同 core/本次 personal。safe-mode 关闭用户 customizations，empty MCP、禁用 skills、生成阶段仅 Read，checker 无 tools；admin-managed policy 与 agent builtin 能力仍受平台约束。Read 请求与结果作为检查证据，产品不修改 tool arguments/results。checker 与 tool turns、平台重试可能产生多次 provider requests，因此“一次独立 checker session”不等于“一次 HTTP request”。

检查出错、timeout、缺完整结果、保真判断不通过或保护内容改变时，stdout 为空，提示“中文检查未完成，请重试。”并非零退出。Ctrl-C 会取消并丢弃部分回复。默认每阶段 120 秒，可用 `--timeout 60` 调整。重试原命令会重新生成；没有自动 retry 或正常用法原稿。登录、权限或规则问题需要先处理，重试不会自动修好账号。

程序逐字检查支持范围内的 closed backtick/tilde fences、inline code、blockquote 行、Markdown inline/reference link destinations；保留出现顺序和重复次数。普通引文及复杂/未闭合 Markdown 需要 `--protect` 显式保护。字面检查以生成完成的 draft 为基准；生成阶段能否遵守用户给出的原话仍依赖模型。字面检查与 checker 自报均不能证明语义等价，实际含义保持仍受模型能力限制。

## 正则 lint：zh_lint.py

`zh_lint.py` 不调用模型，只用词表和正则扫中文文本，按三档报命中：问题（按规则算错）、提示（不如中文说法自然）、正常用法（「落地」「跑一遍测试」这两个中文技术圈本来就这么说的词不报）。引号和 inline code 里的字不扫。

```sh
printf '%s\n' '等 CI 绿了再 merge。' | python3 zh_lint.py
```

有「问题」档命中时退出码为 1。`--json` 输出结构化结果。词表来自作者 2026-10-08 盲评标出的句子和 PREFERENCES 里的对照表；2026-09 以来三个项目 37 万字 transcript 的命中分布在本地研究记录里。它只能查词表里有的形状，查不到的翻译腔仍靠规则和人读。

### 按机制判：zh_check.py

`zh_check.py` 把回复和 `rules/mechanisms.md`（六种毛病的说明和例子）交给 haiku，返回命中的句子、机制编号和改法。走本机 Claude Code 的登录，不读用户的 CLAUDE.md，不开 tools，每次约 1 到 6 秒、不到 0.001 美元。它按机制判，能抓词表里没有的词：2026-10-13 拿两周里人工标出的 26 句试，只给六条机制定义、不给任何例子时抓到 19 句，带例子抓到 21 句，6 句干净样本带例子时零误报。词表（`zh_lint.py`）仍在它前面先跑，当已知词的快速通道和回归 test。

### 你自己说过的话不报：zh_vocab.py

```sh
python3 zh_replies.py vocab
```

从本机 `~/.claude/projects/` 的 transcript 里收集你亲手发过的短消息，写到 `~/.claude/zh-replies/user-vocab.json`。程序注入的消息、贴进来的内容、session 续接摘要都不收。haiku 报出来的词，只要你自己在至少两条消息里用过，就不算毛病，显示端的改写也会撤回。词表（`zh_lint.py`）不受它影响，那里每一条都是你明确判过的。隔一阵重新运行一次就更新。

### 显示之前换字：MessageDisplay hook

`hooks/zh_display.py` 在 assistant 文字显示之前运行：先按 `zh_lint.REPLACE` 做一对一替换（「提交进 git」→「commit 进 git」，瞬间），再让 haiku 改写有毛病的句子（每批行 5 到 8 秒，偶尔更久）。只改完整的行，code block 里的不改，引号里的不改。改的只是屏幕上显示的字，transcript 和模型自己看到的还是原文。每次改动追加一条到 `~/.claude/zh-replies/display-log.jsonl`：换前、换后、谁换的、机制。这份记录是评估 haiku 改得对不对的材料。`ZH_DISPLAY_NO_MODEL=1` 只做替换。

### 生成之前提醒：UserPromptSubmit hook

`hooks/zh_prompt_submit.py` 把 `rules/mechanisms.md` 附在用户每条消息后面给模型看，让六种机制紧贴着生成。程序发的消息不附。

### Stop hook

`hooks/zh_lint_stop.py` 是 Claude Code 的 Stop hook：每轮结束时取这一轮最后一条给用户的回复，先交给 `zh_lint.py`，再交给 `zh_check.py`，命中的以「原句 → 改法」列在 systemMessage 里，不再让模型重写。程序触发的轮次只运行 regex。haiku 调用失败只在 systemMessage 里说一句。设 `ZH_LINT_NO_MODEL=1` 跳过 haiku。问题档命中就把句子和改法回给模型改写一次（第二次停下不再拦）；提示档只显示给用户。装法是在 `~/.claude/settings.json` 的 `hooks.Stop` 里加一条 command：

三个 hook 由 `install --with-hooks` 写进 `~/.claude/settings.json`，`disable` 一并移除。手工装的话每条是这样：

```json
{"type": "command", "command": "python3 /ABS/PATH/zh-style-lint/hooks/zh_lint_stop.py", "timeout": 45}
```

新开的 session 才会加载。它只看 transcript 里 assistant 的 text，thinking 不扫。

## 成本与隐私

通用规则正文为 3494 UTF-8 bytes、1236 characters，另加 managed header 和可选个人内容。用 tiktoken 的 o200k_base 计算，正文约 918 tokens；当前无个人规则的完整 managed snapshot 估计为 983 tokens，包含 header；原有指令和平台 wrapper 另计。这些是 tokenizer estimate，不是 Claude 的精确 token 数。字符数和 bytes 不是模型 token 数；token 数随 tokenizer、metadata 和个人文件变化。安装、status、disable 不联网。默认规则随原 agent 请求到现有 provider，不增加独立 checker。`--check` 会把用户 prompt、draft 和 Read 证据再发给同一 Claude provider，并增加延迟及账号用量。

产品不记录对话、不上传 telemetry。agent/provider 自己的日志、账号用量和数据处理按其原有行为；`reply` 使用 no-session-persistence，不能保证 provider 不保留请求。个人规则、backup、研究和实际验收 raw 只留本地。不要把含个人内容的 instruction 文件或 backup 加入 git。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

测试覆盖安装生命周期、手改拒绝、文件保护、独立检查开关、完整结果检查、取消和 timeout。真实 provider 的中文对照和真实 CLI 的 local API fixture 分开记录；fixture 不代表中文效果。有限样本不能推断普遍准确率，也不能证明比已有 Humanizer-zh 或 Tech-Doc-Style-Chinese 更好。

交付验证：21 unit tests、23 项实际 CLI 接入/故障检查通过；最终 140 条产品输出在逐例核对中保留原意，包括四条规则冻结后独立选择的样本。仍有偏长和解释不充分的回复；正常样本多为打平。该结果限于本次模型、prompt 和单次运行。个人样本、失败历史、逐例对照与独立审计报告均只留本地。
