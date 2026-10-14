# zh-replies

让 Claude Code 和 Codex 的中文回复像人写的。

Coding agent 写中文的时候，常常先有一句英文，再逐字换成中文：「等 CI 绿了再 merge」「我自己核过」「烟雾测试完成」。这个项目把这类问题归成六种，用规则、regex、haiku 和三个 Claude Code hook，在模型写之前、文字显示之前、回复结束之后各查一次。

| Agent 原来写的 | 改成 |
|---|---|
| 等 CI 绿了再 merge。 | 等 CI 通过了再 merge。 |
| 关键两处我自己核过。 | 关键两处我自己核对过。 |
| 脚本退出码是 0 就算通过。 | 脚本 exit code 是 0 就算通过。 |
| 两份都折进去了。 | 两份都写进去了。 |
| 这份 sample 你接受吗？ | 你觉得这份 sample 可以吗？ |

## 快速开始

需要 Python 3.11 以上和已经登录的 Claude Code，不用装任何 package。

```sh
git clone https://github.com/JiahaoXu10Arthur/zh-replies.git && cd zh-replies
python3 zh_replies.py install --with-hooks   # 规则写进 CLAUDE.md 和 AGENTS.md，三个 hook 写进 settings.json
python3 zh_replies.py vocab                  # 收集你常说的词，检查时跳过这些词
```

新开一个 Claude Code session 就生效。`python3 zh_replies.py status` 查看安装情况，`python3 zh_replies.py disable` 卸载全部内容。改过的每个文件旁边都留一份 backup。

## 六种问题

规则、judge、haiku 读的是同一份 [rules/mechanisms.md](rules/mechanisms.md)。每条是一种问题，例子帮你认出来。

| # | 问题 | 例子 | 该写 |
|---|---|---|---|
| 1 | 英文动词直译 | 抛出 RecursionError、跑完、折回 spec、还挂着等你定 | 报错、运行完、写回、还没定 |
| 2 | 两字动词缩成一个字 | 核过、没接的、不推、写完跑 | 核对过、没接受的、不推导 |
| 3 | 给新概念造中文名 | 烟雾测试、两个面、票 00、退出码 | smoke test、两个页面、ticket 00、exit code |
| 4 | 用颜色或比喻代替结果 | CI 绿了、守卫、没有牙 | 通过、guard、不拦人 |
| 5 | 英文语序和英文介词 | CI 结果目前不是 dev 的合并条件 | 现在 merge 进 dev 不看 CI 结果 |
| 6 | 催答复、下命令的口气 | 你认不认、认了我再……、写吧。 | 你觉得可以吗、你看有要改的地方吗 |

这些不算问题：技术名词和动词保留英文（deploy、merge、ticket）；中文里没有现成说法的词直接用英文；用户自己用过的词；引号里转述别人的原话；code 和链接。

## 三个 hook 各在什么时候运行

| 时候 | Hook | 做什么 |
|---|---|---|
| 你发消息的时候 | `UserPromptSubmit` | 把六种问题附在你的消息后面，模型写的时候规则就在眼前；上一条回复查到的问题也一起附上 |
| 文字显示之前 | `MessageDisplay` | regex 的一对一替换马上做完；一批不长的话，再让 haiku 把有问题的句子改一遍，你第一眼看到的就是改过的 |
| 回复结束之后 | `Stop` | regex 和 haiku 查最后一条回复，把「原句 → 改法」列给你看，写进记录。模型不用重写一遍 |

Hook 只有 Claude Code 有。Codex 只拿到 `AGENTS.md` 里的规则。

## 三种检查

**regex 查词表（`zh_lint.py`）。** 一张词表，分三档：问题（按规则算错，exit code 1）、提示（有更自然的中文说法）、正常用法（中文技术圈本来就这么说，不算问题）。每一条都来自作者亲手标过的句子。引号和 inline code 里的字不查。

```sh
printf '%s\n' '等 CI 绿了再 merge。' | python3 zh_lint.py
```

**haiku 按六种问题检查（`zh_check.py`）。** 把回复和六种问题的说明交给 haiku，它返回句子、问题的编号和改法。词表里没有的词它也查得出来。拿两周里人工标出的 26 句试过：只给六种问题的定义，查出 19 句；加上例子，查出 21 句；6 句没问题的句子一句都没误报。调用走你本机的 Claude Code 登录，每次 1 到 8 秒，不到 0.001 美元。

**你自己说过的话不算问题（`zh_vocab.py`）。** 从本机 transcript 收集你亲手发过的短消息。haiku 查出来的词，只要你在至少两条消息里用过，就不算问题。词表里的词照样报。

## 记录

| 文件 | 内容 |
|---|---|
| `~/.claude/zh-replies/display-log.jsonl` | 屏幕上每一次改动：改前、改后、regex 还是 haiku 改的、哪种问题 |
| `~/.claude/zh-replies/stop-log.jsonl` | 每条回复查到的问题：原句、改法、regex 还是 haiku 查到的 |
| `~/.claude/zh-replies/user-vocab.json` | 你自己说过的话 |

屏幕上改的只是显示，transcript 里还是原文。改前改后都留着，回头可以评估改得对不对。

## 命令

| 命令 | 作用 |
|---|---|
| `install` | 把 `rules/core.md` 写进 `~/.claude/CLAUDE.md` 和 `~/.codex/AGENTS.md`；加 `--with-hooks` 同时装三个 hook；`--agent claude\|codex` 只装一个；`--personal FILE` 附上你自己的偏好 |
| `status` | 显示安装位置、安装是否完整、hook 是否已经装上 |
| `disable` | 移除规则 block 和三个 hook，个人文件和别人的 hook 不动 |
| `vocab` | 收集你自己说过的话 |
| `reply --check` | 独立的问答入口：先生成，再开一个没有 tool 的 Claude session 检查，检查通过才显示 |

<details>
<summary>install 的细节</summary>

install 把规则写成一个带标记的 block，文件里其他内容原样保留，改之前先存一份 `.CLAUDE.md.zh-replies-backup-*`。再运行一次就是更新。block 被手改过、标记破损、目标文件是 symlink，这三种情况都会拒绝，并提示从 backup 恢复。`--claude-dir`、`--codex-dir` 指定别的 profile，默认按 `CLAUDE_CONFIG_DIR` 和 `CODEX_HOME` 来。Codex 的 `AGENTS.md` 超过 32768 bytes 会拒绝；Codex 的 global override 会盖住 `AGENTS.md`，status 会提醒。

个人偏好是一个 UTF-8 文本文件，只写表达偏好，例如「技术动词保留英文」。`install --personal FILE` 装上，改了文件再运行一次 `install` 就更新，`install --without-personal` 明确移除。

</details>

<details>
<summary>hook 的细节</summary>

三个 hook 由 `install --with-hooks` 写进 `~/.claude/settings.json`，每条长这样：

```json
{"type": "command", "command": "python3 /ABS/PATH/zh-replies/hooks/zh_lint_stop.py", "timeout": 45}
```

- `hooks/zh_prompt_submit.py`（UserPromptSubmit）：程序自动发的消息不附。
- `hooks/zh_display.py`（MessageDisplay）：只改完整的行，code block 和引号里不改；一批超过 300 个汉字只做 regex 替换；haiku 超时就显示原文。设 `ZH_DISPLAY_NO_MODEL=1` 只做 regex 替换。
- `hooks/zh_lint_stop.py`（Stop）：只查这一轮最后一条回复；由 task-notification 这类程序消息触发的轮次只运行 regex。设 `ZH_LINT_NO_MODEL=1` 跳过 haiku。

</details>

<details>
<summary>reply --check 的细节</summary>

```sh
printf '%s\n' '请简短解释当前项目的 README。' | python3 zh_replies.py reply --check
```

先拿到完整回复，再开一个独立的 Claude checker session，核对意思和固定原话，通过才显示。生成的时候只给 Read 这一个 tool，checker 一个 tool 都没有。code、inline code、blockquote、链接逐字核对，其他要保护的原话用 `--protect '原话'`。检查没通过或者超时，stdout 为空，exit code 非零。默认每个阶段 120 秒，`--timeout` 可以改。

</details>

## 限制

- 规则放在 context 里挡不住所有问题，靠三个 hook 才管用；而 hook 只有 Claude Code 有。
- haiku 每批 5 到 8 秒，长回复显示的时候会等；超过 300 个汉字的批次只做 regex 替换。
- 屏幕上改的是显示的字，模型自己看到的还是原文。它要到下一轮才知道上一条错在哪。
- thinking 里的中文不查。
- 词表照作者的习惯定，比如「守卫」换成 guard。你要是不同意，改 `zh_lint.py` 里的 `RULES` 和 `REPLACE`。
- 26 句的试验太少，不能当准确率看。

## 成本与隐私

规则 block 大约 980 tokens，每个 session 都会带上这部分内容。install、status、disable、vocab 这四个命令都不联网。hook 调用 haiku 时用的是你自己的 Claude Code 账号。这个工具不记录对话，也不上传任何 telemetry。三份记录文件和 backup 都只保存在本机。CLAUDE.md 和 backup 里有个人内容，请不要把它们加进 git。

## 开发

```sh
python3 -m unittest discover -s tests -v
```

## License

MIT
