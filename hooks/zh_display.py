"""Claude Code MessageDisplay hook：显示之前把 assistant 文字里的毛病换掉。

stdin 收 {turn_id, message_id, index, final, delta}。delta 是这一批刚写完的行。
先用 zh_lint.substitute 做一对一替换（瞬间），再交给 haiku 改写有毛病的句子（几秒）。一批超过 300 个汉字就只做替换，haiku 来不及。
只改完整的行；delta 末尾没换行的那一截不动。code block 里的行不动。
每次有改动就往 ~/.claude/zh-replies/display-log.jsonl 追加一条：换前、换后、谁换的、机制，供以后评估。
输出 hookSpecificOutput.displayContent；没有改动就不输出。环境变量 ZH_DISPLAY_NO_MODEL=1 只做替换。
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

LOG = Path.home() / '.claude' / 'zh-replies' / 'display-log.jsonl'
MAX_MODEL_CHARS = 300


def split_complete(delta):
    """(complete lines with their newline, trailing partial line)."""
    cut = delta.rfind('\n') + 1
    return delta[:cut], delta[cut:]


def main():
    payload = json.load(sys.stdin)
    delta = payload.get('delta') or ''
    complete, partial = split_complete(delta)
    if not complete.strip() or complete.count('```') % 2 or zh_lint.CJK.search(complete) is None:
        return 0
    vocab = zh_vocab.load()
    shown, changes = zh_lint.substitute(complete)
    entries = [{'source': 'regex', 'from': a, 'to': b} for a, b in changes]
    long_batch = len(zh_lint.CJK.findall(complete)) > MAX_MODEL_CHARS
    if long_batch:
        entries.append({'source': 'haiku', 'skipped': 'batch over %d chars' % MAX_MODEL_CHARS})
    if not long_batch and not os.environ.get('ZH_DISPLAY_NO_MODEL'):
        try:
            text, model_changes = zh_check.rewrite(shown, timeout=25, vocab=vocab)
            if model_changes:
                entries += [{'source': 'haiku', **c} for c in model_changes]
                shown = text
        except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            entries.append({'source': 'haiku', 'error': str(error)[:120]})
    if shown == complete and not entries:
        return 0
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'ts': datetime.datetime.now().isoformat(timespec='seconds'), 'turn_id': payload.get('turn_id'),
                            'message_id': payload.get('message_id'), 'index': payload.get('index'), 'before': complete, 'after': shown,
                            'changes': entries}, ensure_ascii=False) + '\n')
    if shown != complete:
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'MessageDisplay', 'displayContent': shown + partial}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
