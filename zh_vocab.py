"""用户自己说过的话：从 Claude Code transcript 里取用户亲自发的消息；haiku 报出来的词，用户自己在至少两条消息里用过的不算毛病。
词表（zh_lint.py）不受它影响：词表里的每一条都是用户明确判过的。

构建：python3 zh_vocab.py build   → 写 ~/.claude/zh-replies/user-vocab.json
只收用户亲手打的短消息（200 字以内）：程序注入的（task-notification、hook feedback、skill 内容、命令输出、session 续接摘要）不收；贴进来的 <pasted_content> 块去掉；zh-style-lint 项目不收，因为那里在讨论毛病本身。
一个词要在至少两条不同消息里出现过才算用户自己的话。
"""
import datetime
import glob
import json
import re
import sys
from pathlib import Path

VOCAB = Path.home() / '.claude' / 'zh-replies' / 'user-vocab.json'
PROJECTS = Path.home() / '.claude' / 'projects'
SKIP_PREFIX = ('<', '#', '```', 'Stop hook feedback:', '[Request interrupted', 'Caveat:', 'Another Claude session', 'This session is being continued')
MAX_LEN = 200
EXCLUDE_PROJECT = 'zh-style-lint'
PASTED = re.compile(r'<pasted_content[^>]*>.*?</pasted_content[^>]*>', re.S)
CJK = re.compile(r'[一-鿿]')


def human_messages(projects=PROJECTS):
    seen = set()
    for path in sorted(glob.glob(str(projects / '*' / '*.jsonl'))):
        if EXCLUDE_PROJECT in Path(path).parent.name:
            continue
        for line in open(path, encoding='utf-8'):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            content = entry.get('message', {}).get('content')
            if entry.get('type') != 'user' or not isinstance(content, str):
                continue
            text = PASTED.sub('', content).strip()
            if not text or len(text) > MAX_LEN or text.startswith(SKIP_PREFIX) or 'Claude Code v' in text or not CJK.search(text) or text in seen:
                continue
            seen.add(text)
            yield text


def build(projects=PROJECTS, out=VOCAB):
    messages = list(human_messages(projects))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'built': datetime.datetime.now().isoformat(timespec='seconds'), 'messages': messages}, ensure_ascii=False), encoding='utf-8')
    return len(messages)


def load(path=VOCAB):
    """The user's messages, or [] when never built."""
    return json.loads(path.read_text(encoding='utf-8'))['messages'] if path.exists() else []


def used(phrase, messages, at_least=2):
    """True when the user has typed this phrase in at least two different messages of their own."""
    return len(phrase) >= 2 and sum(phrase in m for m in messages) >= at_least


if __name__ == '__main__':
    if sys.argv[1:] == ['build']:
        print('收了', build(), '条你自己发的消息，写到', VOCAB)
    else:
        print(__doc__)
