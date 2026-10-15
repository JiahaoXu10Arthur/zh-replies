#!/usr/bin/env python3
"""Local instruction snapshots for Chinese conversation replies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BEGIN = '<!-- zh-replies:begin '
END = '<!-- zh-replies:end -->\n'
BLOCK = re.compile(r'\n\n<!-- zh-replies:begin (\{[^\n]*\}) -->\n(.*?)<!-- zh-replies:end -->\n', re.S)


class Failure(Exception):
    pass


def compose_rules(personal=None):
    body = (ROOT / 'rules/core.md').read_text(encoding='utf-8').rstrip() + '\n'
    if personal is not None:
        text = Path(personal).read_text(encoding='utf-8')
        if 'zh-replies:' in text:
            raise Failure('个人文件含有管理标记，请将标记移到规则之外。')
        body += '\n# 可选个人规则\n\n' + text.rstrip() + '\n'
    return body


def digest(source, body):
    return hashlib.sha256((json.dumps(source, ensure_ascii=False) + '\n' + body).encode()).hexdigest()


def read_target(path):
    if path.is_symlink():
        raise Failure(f'目标是 symlink，请先选择实际文件：{path}')
    raw = path.read_bytes() if path.exists() else b''
    text = raw.decode('utf-8')
    if '<!-- zh-replies:begin' not in text and '<!-- zh-replies:end' not in text:
        return raw, None, None
    match = BLOCK.search(text)
    if not match or text.count(BEGIN) != 1 or text.count('<!-- zh-replies:end') != 1:
        raise Failure(f'管理标记不完整，请先从本地 backup 核对并恢复：{path}')
    meta = json.loads(match.group(1))
    if (meta.get('version') != 1 or not isinstance(meta.get('source'), (str, type(None)))
            or meta.get('sha256') != digest(meta.get('source'), match.group(2))):
        raise Failure(f'规则 block 已被修改，请将偏好移到个人文件或从 backup 恢复：{path}')
    return raw, match, meta


def atomic_write(path, raw, previous):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    if path.exists():
        backup = path.parent / f'.{path.name}.zh-replies-backup-{time.time_ns()}'
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(previous)
    fd, name = tempfile.mkstemp(prefix='.zh-replies-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
            os.fchmod(out.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def selected_targets(args):
    rows = []
    if args.agent in ('claude', 'both'):
        rows.append(('claude', Path(args.claude_dir).expanduser().absolute() / 'CLAUDE.md'))
    if args.agent in ('codex', 'both'):
        rows.append(('codex', Path(args.codex_dir).expanduser().absolute() / 'AGENTS.md'))
    return rows


HOOKS = (('UserPromptSubmit', 'zh_prompt_submit.py', 5), ('MessageDisplay', 'zh_display.py', 30), ('Stop', 'zh_lint_stop.py', 45))


def hook_command(script):
    return 'python3 ' + str(ROOT / 'hooks' / script)


def hooks_installed(claude_dir):
    path = Path(claude_dir).expanduser().absolute() / 'settings.json'
    if not path.exists():
        return False
    hooks = json.loads(path.read_text(encoding='utf-8')).get('hooks', {})
    return all(any(h.get('command') == hook_command(script) for e in hooks.get(event, []) for h in e.get('hooks', []))
               for event, script, _ in HOOKS)


def write_hooks(claude_dir, enable):
    """Add or remove the three hook commands in <claude_dir>/settings.json; other settings untouched."""
    path = Path(claude_dir).expanduser().absolute() / 'settings.json'
    settings = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    hooks = settings.setdefault('hooks', {})
    for event, script, timeout in HOOKS:
        command = hook_command(script)
        entries = [e for e in hooks.get(event, []) if not any(h.get('command') == command for h in e.get('hooks', []))]
        if enable:
            entries.append({'hooks': [{'type': 'command', 'command': command, 'timeout': timeout}]})
        if entries:
            hooks[event] = entries
        else:
            hooks.pop(event, None)
    if not hooks:
        settings.pop('hooks', None)
    raw = (json.dumps(settings, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    atomic_write(path, raw, path.read_bytes() if path.exists() else None)


def manage(args):
    prepared, rows = [], []
    for agent, path in selected_targets(args):
        raw, match, meta = read_target(path)
        override = path.parent / 'AGENTS.override.md'
        shadowed = agent == 'codex' and override.exists() and bool(override.read_bytes().strip())
        if args.action == 'status':
            rows.append({'agent': agent, 'path': str(path), 'installed': match is not None,
                         'personal_source': meta['source'] if meta else None,
                         'shadowed': shadowed, 'active_session': 'unknown', 'target_bytes': len(raw)})
            continue
        text = raw.decode('utf-8')
        if args.action == 'disable':
            changed = text[:match.start()] + text[match.end():] if match else text
        else:
            if shadowed:
                raise Failure(f'Codex global override 会遮蔽目标，请先处理：{override}')
            source = (str(Path(args.personal).expanduser().resolve()) if args.personal else
                      None if args.without_personal else meta['source'] if meta else None)
            body = compose_rules(source)
            header = {'version': 1, 'source': source, 'sha256': digest(source, body)}
            new_block = '\n\n' + BEGIN + json.dumps(header, ensure_ascii=False) + ' -->\n' + body + END
            changed = text[:match.start()] + new_block + text[match.end():] if match else text + new_block
            if agent == 'codex' and len(changed.encode('utf-8')) > 32768:
                raise Failure(f'Codex 目标超过 32768 UTF-8 bytes，请精简 instruction：{path}')
        prepared.append((path, changed.encode('utf-8'), raw))
    if args.action == 'status':
        core = compose_rules()
        print(json.dumps({'core_bytes': len(core.encode()), 'core_chars': len(core), 'hooks_installed': hooks_installed(args.claude_dir),
                          'new_session_required': True, 'targets': rows}, ensure_ascii=False, indent=2))
        return
    completed = []
    try:
        for path, changed, raw in prepared:
            if changed != raw:
                atomic_write(path, changed, raw)
            completed.append(str(path))
    except OSError as exc:
        raise Failure('写入失败；已完成目标：' + ', '.join(completed)) from exc
    if args.agent in ('claude', 'both') and (args.action == 'disable' or args.with_hooks):
        write_hooks(args.claude_dir, args.action == 'install')
    print(('规则已停用' if args.action == 'disable' else '规则已更新') + '。请开始新的 session。')


def parser():
    p = argparse.ArgumentParser(description='zh-replies：跨 agent 的本地中文回复规则')
    sub = p.add_subparsers(dest='action', required=True)
    for action in ('install', 'status', 'disable'):
        s = sub.add_parser(action)
        s.add_argument('--agent', choices=('claude', 'codex', 'both'), default='both')
        s.add_argument('--claude-dir', default=os.environ.get('CLAUDE_CONFIG_DIR', '~/.claude'))
        s.add_argument('--codex-dir', default=os.environ.get('CODEX_HOME', '~/.codex'))
        if action == 'install':
            group = s.add_mutually_exclusive_group()
            group.add_argument('--personal', type=Path)
            group.add_argument('--without-personal', action='store_true')
            s.add_argument('--with-hooks', action='store_true', help='同时把三个 Claude Code hook 写进 settings.json')
    sub.add_parser('vocab', help='从本机 transcript 收集你自己发过的消息，检查时你用过的词不报')
    sub.add_parser('rules', help='列出检查规则的名字；要关掉哪条，写进 ~/.claude/zh-replies/config.json 的 disabled_rules')
    s = sub.add_parser('reply', help='独立 Claude Code 问答；--check 才调用检查器')
    s.add_argument('--check', action='store_true')
    s.add_argument('--personal', type=Path)
    s.add_argument('--timeout', type=float, default=120)
    s.add_argument('--protect', action='append', default=[])
    return p


def main():
    args = parser().parse_args()
    try:
        if args.action == 'vocab':
            import zh_vocab
            print('收了', zh_vocab.build(), '条你自己发的消息，写到', zh_vocab.VOCAB)
            return 0
        if args.action == 'rules':
            import zh_lint
            off = zh_lint.disabled_rules()
            for tier, name, _, _ in zh_lint.RULES:
                print(f"[{tier}] {name}" + ('  （已关）' if name in off else ''))
            for n in range(1, 8):
                print(f"[问题] 机制{n}" + ('  （已关）' if f'机制{n}' in off else ''))
            print('关掉规则：在', zh_lint.CONFIG, '写 {"disabled_rules": ["规则名"]}')
            return 0
        if args.action == 'reply':
            from reply import run_reply, ReplyFailure
            try:
                result = run_reply(sys.stdin.read(), args.check, args.personal, args.timeout, args.protect)
            except ReplyFailure as exc:
                raise Failure(str(exc)) from exc
            print(result)
        else:
            manage(args)
        return 0
    except KeyboardInterrupt:
        print('已取消，未交付回复。', file=sys.stderr)
        return 130
    except (Failure, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
