"""按机制判的中文检查：把回复和 rules/mechanisms.md 交给 haiku，返回命中的句子。

走本机 Claude Code 的登录，不读用户的 CLAUDE.md，不开 tools，不留 session。
用法：printf '%s' '文本' | python3 zh_check.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import zh_lint
import zh_vocab
MECHANISMS = ROOT / 'rules' / 'mechanisms.md'
PROMPT = '''你是中文回复的审读。下面先给七种毛病的说明，再给一段 agent 写给用户的中文回复。
逐句读回复，找出属于这七种毛病的句子。按机制判断，说明里的例子只是帮助认出来，没列出的写法同样要报。
引号里转述别人的原话、code、链接、技术英文名词不报；引号里 agent 自己起的名字或自己的说法要报。拿不准的不放进 hits，另外列在 unsure 里，格式一样。

只输出 JSON，不加别的字：{"hits": [{"sentence": "原句", "mechanism": 1到7的数字, "match": "有问题的那几个字", "fix": "该怎么写"}], "unsure": [同样格式]}
没有问题就输出 {"hits": [], "unsure": []}

=== 七种毛病 ===
%s
=== 回复 ===
%s'''


def _call(prompt, timeout):
    env = dict(os.environ, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', DISABLE_AUTOUPDATER='1')
    done = subprocess.run(
        ['claude', '-p', '--model', 'haiku', '--output-format', 'json', '--tools', '', '--no-session-persistence',
         '--setting-sources', '', '--disable-slash-commands', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}'],
        input=prompt, capture_output=True, text=True, env=env, timeout=timeout)
    if done.returncode:
        raise RuntimeError(done.stderr.strip()[:200] or 'claude exit %d' % done.returncode)
    result = json.loads(done.stdout)['result']
    start, end = result.find('{'), result.rfind('}')
    return json.loads(result[start:end + 1])


def _hit(h):
    return {'tier': '问题', 'rule': '机制%s' % h['mechanism'], 'match': h['match'], 'sentence': h['sentence'], 'hint': h['fix']}


def check_all(text, timeout=50, vocab=()):
    """Return (hits, unsure): what haiku is sure about, and what it was unsure about. Unsure items are for later evaluation only."""
    result = _call(PROMPT % (MECHANISMS.read_text(encoding='utf-8'), text), timeout)
    off = zh_lint.disabled_rules()
    hits = [_hit(h) for h in result['hits'] if not (vocab and zh_vocab.used(h['match'], vocab)) and '机制%s' % h['mechanism'] not in off]
    return hits, [_hit(h) for h in result.get('unsure', [])]


def check(text, timeout=50, vocab=()):
    return check_all(text, timeout, vocab)[0]


REWRITE_PROMPT = '''你是中文回复的审读。下面先给七种毛病的说明，再给一段 agent 写给用户的中文回复。
只改有这七种毛病的句子，改成中文日常说法；其余一个字不动。保留所有 code、链接、引号里的原话、英文技术名词、Markdown 符号、空行和换行。不加任何解释。
拿不准的不改。改的地方不能改变意思。

只输出 JSON，不加别的字：{"text": "改后的整段原样文本", "changes": [{"from": "改前的那几个字", "to": "改后的那几个字", "mechanism": 1到7的数字}]}
没有要改的就输出 {"text": 原文, "changes": []}

=== 七种毛病 ===
%s
=== 回复 ===
%s'''


def rewrite(text, timeout=20, vocab=()):
    """Ask haiku which phrases to change, then apply its from→to pairs to the original text one by one.
    Its full rewritten text is not used, so line count and Markdown structure cannot drift.
    Returns (new text, applied changes). A change whose 'from' the user has typed themselves is skipped."""
    prompt = REWRITE_PROMPT % (MECHANISMS.read_text(encoding='utf-8'), text)
    result = _call(prompt, timeout)
    if not isinstance(result.get('text'), str) or not isinstance(result.get('changes'), list):
        raise ValueError('rewrite schema')
    new, changes = text, []
    off = zh_lint.disabled_rules()
    for change in result['changes']:
        src, dst = change.get('from', ''), change.get('to', '')
        if not src or not dst or src not in new or (vocab and zh_vocab.used(src, vocab)) or '机制%s' % change.get('mechanism') in off:
            continue
        at = new.index(src)
        before, after = new[at - 1:at], new[at + len(src):at + len(src) + 1]
        if dst[:1].isascii() and dst[:1].isalnum() and zh_vocab.CJK.match(before):
            dst = ' ' + dst
        if dst[-1:].isascii() and dst[-1:].isalnum() and zh_vocab.CJK.match(after):
            dst = dst + ' '
        new = new[:at] + dst + new[at + len(src):]
        changes.append(change)
    return new, changes


if __name__ == '__main__':
    for h in check(sys.stdin.read()):
        print(f"[{h['rule']}]「{h['match']}」→ {h['hint']}\n    {h['sentence']}")
