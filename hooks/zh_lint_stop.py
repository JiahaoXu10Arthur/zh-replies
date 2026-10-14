"""Claude Code Stop hook：lint 本轮给用户的最终回复。

stdin 收 Claude Code 的 hook JSON（含 transcript_path、stop_hook_active）。
取最后一条用户消息之后所有 assistant text，先交给 zh_lint（正则），再交给 zh_check（haiku 按机制判）。
这一轮是由 task-notification、hook feedback 这类程序消息触发的，就只运行正则、只提示，不调 haiku，也不要求模型改写。
不让模型改写。命中的句子以「原句 → 改法」成对列在 systemMessage 里给用户看，并写进 ~/.claude/zh-replies/stop-log.jsonl；
下一条用户消息发出时，zh_prompt_submit.py 把这份记录附给模型，模型在写下一条之前知道上一条错在哪。
只检查这一轮最后一条 assistant 消息，中途的过渡句不查。haiku 调用失败时只在 systemMessage 里说一句。
设环境变量 ZH_LINT_NO_MODEL=1 可以跳过 haiku。
"""
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import zh_check
import zh_lint
import zh_vocab


LOG = Path.home() / '.claude' / 'zh-replies' / 'stop-log.jsonl'
AUTOMATED = ('<task-notification>', '<system-reminder>', '<ci-monitor-event>', '<channel ', 'Stop hook feedback:', '[Request interrupted')


def final_reply(transcript_path):
    """Return (reply text of the current turn, whether a person typed the message that started it)."""
    parts = []
    human = True
    for line in Path(transcript_path).open(encoding='utf-8'):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = entry.get('message', {}).get('content')
        if entry.get('type') == 'user' and isinstance(content, str):
            parts = []
            human = not content.lstrip().startswith(AUTOMATED)
        elif entry.get('type') == 'assistant' and isinstance(content, list):
            texts = [p['text'] for p in content if isinstance(p, dict) and p.get('type') == 'text' and p.get('text')]
            if texts:
                parts = texts
    return '\n'.join(parts), human


def main():
    payload = json.load(sys.stdin)
    reply, human = final_reply(payload['transcript_path'])
    vocab = zh_vocab.load()
    hits = zh_lint.lint(reply)
    notes = []
    if human and reply.strip() and not os.environ.get('ZH_LINT_NO_MODEL'):
        try:
            seen = {h['match'] for h in hits}
            hits += [h for h in zh_check.check(reply, vocab=vocab) if h['match'] not in seen]
        except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            notes.append('zh-check 没跑成：' + str(error)[:120])
    problems = [h for h in hits if h['tier'] == '问题']
    hints = [h for h in hits if h['tier'] == '提示']
    out = {}
    if hints:
        notes.append('zh-lint 提示：' + '；'.join(f"{h['rule']}「{h['match']}」" for h in hints[:6]))
    if problems:
        notes.append('zh-lint：\n' + '\n'.join(f"  「{h['match']}」→ {h['hint']}" for h in problems[:8]))
    if hits:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': datetime.datetime.now().isoformat(timespec='seconds'), 'session_id': payload.get('session_id'), 'human': human,
                                'reply': reply, 'hits': [{'source': 'haiku' if h['rule'].startswith('机制') else 'regex', **h} for h in hits]}, ensure_ascii=False) + '\n')
    if notes:
        out['systemMessage'] = '\n'.join(notes)
    if out:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
