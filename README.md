# zh-replies

让 Claude Code 和 Codex 的中文回复像人话。

Coding agent 写中文时，先有英文再逐字换成中文：「等 CI 绿了再 merge」「我自己核过」「变成纯派发器」。这个项目把这类毛病归成六种机制，用规则、regex、haiku 和三个 Claude Code hook 在生成前、显示前、结束后各管一道。

| Agent 原来写的 | 改成 |
|---|---|
| 等 CI 绿了再 merge。 | 等 CI 通过了再 merge。 |
| 关键两处我自己核过。 | 关键两处我自己核对过。 |
| 脚本退出码是 0 就算通过。 | 脚本 exit code 是 0 就算通过。 |
| 两份都折进去了。 | 两份都写进去了。 |
| 这份 sample 你接受吗？ | 你觉得这份 sample 可以吗？ |

## 快速开始

需要 Python 3.11+ 和已登录的 Claude Code，不装任何 package。

```sh
git clone https://github.com/JiahaoXu10Arthur/zh-replies.git && cd zh-replies
python3 zh_replies.py install --with-hooks   # 规则写进 CLAUDE.md / AGENTS.md，三个 hook 写进 settings.json
python3 zh_replies.py vocab                  # 收集你自己说过的话，以后不把它们当毛病
```

新开一个 Claude Code session 就生效。`python3 zh_replies.py status` 看装没装齐，`python3 zh_replies.py disable` 全部卸掉。改的每个文件旁边都留 backup。

## 六种机制

规则、judge、haiku 读的是同一份 [rules/mechanisms.md](rules/mechanisms.md)。每条是一种机制，例子只是帮助认出来，不是词表。

| # | 机制 | 例子 | 该写 |
|---|---|---|---|
| 1 | 英文动词直译 | 抛出 RecursionError、跑完、折回 spec、还挂着等你定 | 报错、运行完、写回、还没定 |
| 2 | 两字动词缩成一字 | 核过、没接的、不推、写完跑 | 核对过、没接受的、不推导 |
| 3 | 给新概念造中文名 | 派发器、两个面、票 00、退出码 | dispatcher、两个页面、ticket 00、exit code |
| 4 | 用颜色或比喻代替结果 | CI 绿了、守卫、没有牙 | 通过、guard、不拦人 |
| 5 | 英文语序和英文介词 | CI 结果目前不是 dev 的合并条件 | 现在 merge 进 dev 不看 CI 结果 |
| 6 | 催答复、下命令的口气 | 你认不认、认了我再……、写吧。 | 你觉得可以吗、你看有要改的地方吗 |

不算毛病：技术名词和动词保留英文（deploy、merge、ticket）；没有好中文说法的词直接用英文；用户自己用过的词；引号里转述别人的原话；code 和链接。

## 它在哪三个时机起作用

| 时机 | Hook | 做什么 |
|---|---|---|
| 你发消息时 | `UserPromptSubmit` | 把六种机制附在消息后面给模型看，规则紧贴着生成；上一条回复查到的毛病也一并附上 |
| 文字显示前 | `MessageDisplay` | regex 一对一替换瞬间完成；短批次再让 haiku 改写有毛病的句子，第一遍看到的就是改过的 |
| 回复结束后 | `Stop` | regex 加 haiku 查最后一条回复，列出「原句 → 改法」，写进记录，不让模型重发 |

Hook 只有 Claude Code 有。Codex 只拿到 `AGENTS.md` 里的规则。

## 怎么检查

**regex，`zh_lint.py`。** 一张词表，三档：问题（按规则算错，exit code 1）、提示（不如中文说法自然）、正常用法（中文技术圈本来就这么说的词，不算毛病）。每一条都是使用者亲手判过的句子。引号和 inline code 里不扫。

```sh
printf '%s\n' '等 CI 绿了再 merge。' | python3 zh_lint.py
```

**haiku 按机制判，`zh_check.py`。** 把回复和六种机制交给 haiku，返回句子、机制编号和改法。能抓词表里没有的词：拿两周里人工标出的 26 句试，一个例子不给、只给六条机制定义时抓到 19 句，带例子抓到 21 句，6 句干净样本零误报。走本机 Claude Code 登录，每次 1 到 8 秒，不到 0.001 美元。

**你自己说过的话不算毛病，`zh_vocab.py`。** 从本机 transcript 收集你亲手发过的短消息。haiku 报出来的词，你在至少两条消息里用过的就不算。只影响 haiku 的发现，不影响词表。

## 记录

| 文件 | 内容 |
|---|---|
| `~/.claude/zh-replies/display-log.jsonl` | 显示端每次改动：换前、换后、regex 还是 haiku、机制 |
| `~/.claude/zh-replies/stop-log.jsonl` | 每条回复查到的毛病：原句、改法、来源 |
| `~/.claude/zh-replies/user-vocab.json` | 你自己说过的话 |

屏幕上改的只是显示，transcript 里仍是原文，所以换前换后都留着，可以回头评估改得对不对。

## 命令

| 命令 | 作用 |
|---|---|
| `install` | 把 `rules/core.md` 写进 `~/.claude/CLAUDE.md` 和 `~/.codex/AGENTS.md`；`--with-hooks` 同时装三个 hook；`--agent claude\|codex` 只装一个；`--personal FILE` 附加你自己的偏好 |
| `status` | 装在哪、装没装齐、hook 在不在 |
| `disable` | 移除规则 block 和三个 hook，个人文件和别人的 hook 不动 |
| `vocab` | 收集你自己说过的话 |
| `reply --check` | 独立的问答入口：先生成，再开一个无 tool 的 Claude session 检查，通过才显示 |

<details>
<summary>install 的细节</summary>

install 把规则写成一个带标记的 block，文件里其他内容原样保留，改前先存 `.CLAUDE.md.zh-replies-backup-*`。再运行一次就是更新。手改过 block、标记破损或 target 是 symlink 都会拒绝，提示从 backup 恢复。`--claude-dir`、`--codex-dir` 指定别的 profile，默认尊重 `CLAUDE_CONFIG_DIR` 和 `CODEX_HOME`。Codex 的 `AGENTS.md` 超过 32768 bytes 会拒绝；Codex 的 global override 会遮蔽 `AGENTS.md`，status 会报。

个人偏好是一个 UTF-8 文本文件，只写表达偏好，例如「技术动词保留英文」。`install --personal FILE` 装上，改了文件再 `install` 就更新，`install --without-personal` 明确移除。

</details>

<details>
<summary>hook 的细节</summary>

三个 hook 由 `install --with-hooks` 写进 `~/.claude/settings.json`，每条长这样：

```json
{"type": "command", "command": "python3 /ABS/PATH/zh-replies/hooks/zh_lint_stop.py", "timeout": 45}
```

- `hooks/zh_prompt_submit.py`（UserPromptSubmit）：程序发的消息不附。
- `hooks/zh_display.py`（MessageDisplay）：只改完整的行，code block 和引号里不改；一批超过 300 个汉字只做 regex 替换；haiku 超时就显示原文。`ZH_DISPLAY_NO_MODEL=1` 只做替换。
- `hooks/zh_lint_stop.py`（Stop）：只查这一轮最后一条回复；由 task-notification 这类程序消息触发的轮次只运行 regex。`ZH_LINT_NO_MODEL=1` 跳过 haiku。

</details>

<details>
<summary>reply --check 的细节</summary>

```sh
printf '%s\n' '请简短解释当前项目的 README。' | python3 zh_replies.py reply --check
```

先捕获完整回复，再开一个独立的 Claude checker session 核对意思和固定原话；通过才显示。生成阶段只给 Read，checker 没有 tools。code、inline code、blockquote、链接逐字核对，其他要保护的原话用 `--protect '原话'`。检查没过或超时时 stdout 为空，退出码非零。默认每阶段 120 秒，`--timeout` 可调。

</details>

## 限制

- 规则在 context 里挡不住所有毛病，三个 hook 才是硬的；而 hook 只有 Claude Code 有。
- haiku 每批 5 到 8 秒，长回复显示会卡；超过 300 个汉字的批次只做 regex 替换。
- 显示端改的是屏幕上的字，模型自己看到的还是原文。它下一轮才知道上一条错在哪。
- thinking 里的中文不查。
- 词表是作者的口味，比如「守卫」换 guard。不同意就改 `zh_lint.py` 里的 `RULES` 和 `REPLACE`。
- 26 句的试验不能推广成准确率。

## 成本与隐私

规则 block 约 980 tokens，每个 session 都带。install、status、disable、vocab 不联网。hook 调的 haiku 走你自己的 Claude Code 登录。不记录对话，不上传 telemetry；三份记录和 backup 只在本机。不要把含个人内容的 CLAUDE.md 或 backup 加进 git。

## 开发

```sh
python3 -m unittest discover -s tests -v
```

## License

MIT
