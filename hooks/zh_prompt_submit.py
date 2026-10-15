"""Claude Code UserPromptSubmit hook：把七种机制附在用户消息后面给模型看，让规则紧贴着生成。

程序发的消息（task-notification 等）不附。输出 hookSpecificOutput.additionalContext。
作为 plugin 运行时（有 CLAUDE_PLUGIN_ROOT 环境变量）没有 CLAUDE.md 里的规则 block，所以把 rules/core.md 也一起附上。
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTOMATED = ('<task-notification>', '<system-reminder>', '<ci-monitor-event>', '<channel ', 'Stop hook feedback:', '[Request interrupted')


LOG = Path.home() / '.claude' / 'zh-replies' / 'stop-log.jsonl'


def last_findings(session_id):
    """Problem-tier hits the Stop hook recorded for this session's latest reply, or []."""
    if not session_id or not LOG.exists():
        return []
    for line in reversed(LOG.read_text(encoding='utf-8').splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get('session_id') == session_id:
            return [h for h in entry['hits'] if h['tier'] == '问题']
    return []


def main():
    payload = json.load(sys.stdin)
    prompt = (payload.get('prompt') or '').lstrip()
    if not prompt or prompt.startswith(AUTOMATED):
        return 0
    mechanisms = (ROOT / 'rules' / 'mechanisms.md').read_text(encoding='utf-8')
    context = '回复用中文时，写完逐句对照下面七种毛病，有就当场改掉再发。\n' + mechanisms
    if os.environ.get('CLAUDE_PLUGIN_ROOT'):
        context = (ROOT / 'rules' / 'core.md').read_text(encoding='utf-8') + '\n' + context
    last = last_findings(payload.get('session_id'))
    if last:
        context += '\n你上一条回复里查到的毛病，这次不要再犯：\n' + '\n'.join(f"- 「{h['match']}」→ {h['hint']}" for h in last[:8])
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': context}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
