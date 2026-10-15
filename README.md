# zh-replies

让 Claude Code 写出自然的中文回复。

Coding agent 写中文的时候，经常先想好一句英文，再逐字翻成中文，于是出现「等 CI 绿了再 merge」、「我自己核过」、「烟雾测试完成」这样的句子。这个项目把这类问题分成七种，用规则、regex、haiku 和三个 Claude Code hook 来检查。检查分别发生在模型开始写之前、文字显示之前和回复结束之后。

| 原句 | 改后 |
|---|---|
| 「等 CI 绿了再 merge。」 | 「等 CI 通过了再 merge。」 |
| 「关键两处我自己核过。」 | 「关键两处我自己核对过。」 |
| 「脚本退出码是 0 就算通过。」 | 「脚本 exit code 是 0 就算通过。」 |
| 「两份都折进去了。」 | 「两份都写进去了。」 |
| 「这份 sample 你接受吗？」 | 「你觉得这份 sample 可以吗？」 |

## 效果

在人工标出有问题的 26 个句子中，haiku 查出了 21 个。另有 6 个没有问题的句子作为对照，haiku 没有误报其中任何一个。

## 为什么要用 hook

只在 CLAUDE.md 里写规则是不够的。这个项目最早只有规则，规则装上以后，模型照样写出了「不拦」「核过」「烟雾测试」这样的词。所以后来加了三个 hook，分别在模型开始写之前、文字显示之前和回复结束以后运行，下面「工作方式」一节有说明。

## 改写不会改变意思

haiku 查出有问题的句子以后，只替换其中有问题的几个字，不会重写整段文字。这样做是因为让模型重写整段的时候，原文里的数字、条件、否定经常会被改掉或者丢掉。每次替换前后的内容都会写进本机的记录文件，用于事后校对。

## 可以按自己的习惯调整

用户自己说过的词默认不会被改写。`vocab` 命令会从本机的 transcript 里收集用户发过的消息，这些消息里出现过的词，haiku 查到了也不替换。用户也可以在配置文件里关掉任何一条规则。

## Quick start

需要 Python 3.11 以上，并且已经登录 Claude Code。不需要安装任何 package。

```sh
git clone https://github.com/JiahaoXu10Arthur/zh-replies.git && cd zh-replies
python3 zh_replies.py install --with-hooks   # 规则写进 CLAUDE.md，三个 hook 写进 settings.json
python3 zh_replies.py vocab                  # 收集用户常说的词，检查时跳过这些词
```

也可以不 clone，在 Claude Code 里用 plugin 命令安装，只装三个 hook，不改 CLAUDE.md：

```
/plugin install zh-replies --marketplace JiahaoXu10Arthur/zh-replies
```

新开一个 Claude Code session 就生效。`python3 zh_replies.py status` 查看安装情况，`python3 zh_replies.py disable` 卸载全部内容。改过的每个文件旁边都留一份 backup。

## 工作方式

三个 hook 在不同的时机运行：

| 时机 | Hook | 做什么 |
|---|---|---|
| 用户发消息时 | `UserPromptSubmit` | 把七种问题的说明附在消息后面，模型写回复时能看到规则。上一条回复查到的问题也一起附上 |
| 文字显示之前 | `MessageDisplay` | 先做 regex 的一对一替换。一次显示的文字不超过 300 个汉字时，再由 haiku 改写有问题的句子。屏幕上显示的已经是改过的文字 |
| 回复结束之后 | `Stop` | 用 regex 和 haiku 检查最后一条回复，列出「原句 → 改法」，并写进记录。模型不需要重写 |

检查有三种：

**regex 查词表（`zh_lint.py`）。** 词表分三档：问题（按规则算错，exit code 为 1）、提示（有更自然的中文说法）、正常用法（中文技术圈本来就这么说，不算问题）。词表里的每一条都来自真实回复里标出的句子。引号和 inline code 里的内容不检查。

```sh
printf '%s\n' '等 CI 绿了再 merge。' | python3 zh_lint.py
```

**haiku 按七种问题检查（`zh_check.py`）。** 把回复和七种问题的说明一起交给 haiku，它返回有问题的句子、问题编号和改法。词表里没有的词它也能查出来。开头表格里的数字就是它在人工标出的 26 句上的结果；只给前六种问题的定义、不给例子时，查出 19 句。调用用的是本机的 Claude Code 账号，每次 1 到 8 秒，费用不到 0.001 美元。

**用户自己常用的词不算问题（`zh_vocab.py`）。** 从本机的 transcript 里收集用户发过的短消息。haiku 查出来的词，只要用户在至少两条消息里用过，就不算问题。词表里的词不受影响，照常报告。

## 七种问题

完整说明在 [rules/mechanisms.md](rules/mechanisms.md)，规则和 haiku 检查用的都是这份文件。每一条是一种问题，后面的例子帮助识别它。

| # | 问题 | 例子 | 应该写成 |
|---|---|---|---|
| 1 | 英文动词直译 | 「抛出 RecursionError」「跑完」「折回 spec」「不推」 | 报错、运行完、写回、不 push |
| 2 | 两字动词缩成一个字 | 「核过」「没接的」「写完跑」 | 核对过、没接受的、写完运行 |
| 3 | 英文专有名词直译、给新概念造中文名 | 「烟雾测试」「退出码」「票 00」 | smoke test、exit code、ticket 00 |
| 4 | 用颜色或比喻代替结果 | 「CI 绿了」「守卫」「没有牙」 | 通过、guard、不会拦截 |
| 5 | 英文语序、英文介词、不必要的转折 | 「CI 结果目前不是 dev 的合并条件」，「例子只是帮助认出来，不是词表」 | 现在 merge 进 dev 不看 CI 结果；例子帮助认出机制 |
| 6 | 催答复、下命令的口气 | 「你认不认」「认了我再……」「写吧。」 | 你觉得可以吗、你看有要改的地方吗 |
| 7 | 同一个东西换着用不同的名字 | 同一段里「链 A」「主线」「agent 工程」说的是同一条线 | 全篇只用「链 A」 |

以下情况不算问题：技术名词和动词保留英文，比如 deploy、merge、ticket；中文里没有现成说法的词，直接用英文；用户自己用过的词；引号里转述别人的原话；code 和链接。

## 记录

| 文件 | 内容 |
|---|---|
| `~/.claude/zh-replies/display-log.jsonl` | 显示时的每一次改动：改前的句子、改后的句子、由 regex 还是 haiku 改的、属于哪种问题 |
| `~/.claude/zh-replies/stop-log.jsonl` | 每条回复查到的问题：原句、改法、由 regex 还是 haiku 查到 |
| `~/.claude/zh-replies/user-vocab.json` | 用户自己常用的词 |

显示时的改动只影响屏幕上的文字，transcript 里保留原文。改前和改后的句子都有记录，之后可以评估改得对不对。

## 命令

| 命令 | 作用 |
|---|---|
| `install` | 把 `rules/core.md` 写进 `~/.claude/CLAUDE.md`；加 `--with-hooks` 同时安装三个 hook；`--personal FILE` 附加个人偏好文件 |
| `status` | 显示安装位置、安装是否完整、hook 是否已经装上 |
| `disable` | 移除规则 block 和三个 hook，不动个人偏好文件和其他 hook |
| `vocab` | 收集用户自己常用的词 |
| `rules` | 列出所有检查规则的名字。要关掉某一条，把名字写进 `~/.claude/zh-replies/config.json` 的 `disabled_rules` |
| `reply --check` | 单独的命令：先生成回复，再开一个没有 tool 的 Claude session 做检查，检查通过才显示 |

<details>
<summary>install 的细节</summary>

install 把规则写成一个带标记的 block，文件里的其他内容原样保留，写入之前先保存一份 `.CLAUDE.md.zh-replies-backup-*`。再运行一次 install 就是更新。如果 block 被手动改过、标记损坏，或者目标文件是 symlink，install 会拒绝写入，并提示从 backup 恢复。`--claude-dir` 可以指定其他 profile，默认读取 `CLAUDE_CONFIG_DIR`。`--agent codex` 会把同一份规则写进 `~/.codex/AGENTS.md`，但 Codex 没有 hook，只有规则会生效。

个人偏好是一个 UTF-8 文本文件，里面只写表达上的偏好，例如「技术动词保留英文」。用 `install --personal FILE` 安装；改了文件之后再运行一次 `install` 就会更新；`install --without-personal` 会移除它。

</details>

<details>
<summary>hook 的细节</summary>

三个 hook 由 `install --with-hooks` 写进 `~/.claude/settings.json`，每一条的格式如下：

```json
{"type": "command", "command": "python3 /ABS/PATH/zh-replies/hooks/zh_lint_stop.py", "timeout": 45}
```

- `hooks/zh_prompt_submit.py`（UserPromptSubmit）：程序自动发出的消息不附加规则。
- `hooks/zh_display.py`（MessageDisplay）：只改完整的行，code block 和引号里的内容不改；一次显示的文字超过 300 个汉字时只做 regex 替换；haiku 超时就显示原文。设置 `ZH_DISPLAY_NO_MODEL=1` 可以只做 regex 替换。
- `hooks/zh_lint_stop.py`（Stop）：只检查这一轮的最后一条回复；由 task-notification 这类程序消息触发的那一轮只运行 regex。设置 `ZH_LINT_NO_MODEL=1` 可以跳过 haiku。

</details>

<details>
<summary>reply --check 的细节</summary>

```sh
printf '%s\n' '请简短解释当前项目的 README。' | python3 zh_replies.py reply --check
```

先生成完整的回复，再开一个独立的 Claude session 做检查，核对意思有没有变、原话有没有被改动，通过了才显示。生成阶段只提供 Read 这一个 tool，检查阶段不提供任何 tool。code、inline code、blockquote 和链接会逐字核对；其他需要保护的原话用 `--protect '原话'` 指定。检查没通过或者超时时，stdout 为空，exit code 非零。每个阶段默认 120 秒，可以用 `--timeout` 修改。

</details>

## 限制

- CLAUDE.md 里的规则只能减少问题，不能完全避免。主要靠三个 hook 检查。
- haiku 每次调用需要 5 到 8 秒，长回复显示时会有等待；一次显示的文字超过 300 个汉字时只做 regex 替换。
- 显示时的改动只改屏幕上的文字，模型看到的还是原文，要到下一轮才知道上一条错在哪里。
- 不检查 thinking 里的中文。
- 词表可以自定，编辑 `zh_lint.py` 里的 `RULES` 和 `REPLACE`。

## 成本与隐私

规则 block 大约 980 tokens，每个 session 都会带上这部分内容。install、status、disable、vocab 这四个命令都不联网。hook 调用 haiku 时用的是本机的 Claude Code 账号。这个工具不记录对话，也不上传任何 telemetry。三份记录文件和 backup 都只保存在本机。

## 运行测试

```sh
python3 -m unittest discover -s tests -v
```

## License

MIT
