import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / 'hooks' / 'zh_lint_stop.py'
SUBMIT = HOOK.with_name('zh_prompt_submit.py')
HOME = tempfile.mkdtemp()


def transcript(lines):
    tmp = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False, encoding='utf-8')
    for entry in lines:
        tmp.write(json.dumps(entry, ensure_ascii=False) + '\n')
    tmp.close()
    return tmp.name


def user(text):
    return {'type': 'user', 'message': {'role': 'user', 'content': text}}


def tool_result():
    return {'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'ok'}]}}


def assistant(*parts):
    return {'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': p} for p in parts]}}


def run(path, active=False, env=None):
    payload = {'session_id': 's', 'transcript_path': path, 'hook_event_name': 'Stop', 'stop_hook_active': active}
    merged = dict(os.environ, ZH_LINT_NO_MODEL='1', HOME=HOME)
    merged.update(env or {})
    done = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=merged)
    return done.returncode, json.loads(done.stdout) if done.stdout.strip() else {}


def fake_claude(directory, result):
    """A stand-in `claude` on PATH that answers with a fixed JSON envelope."""
    script = Path(directory) / 'claude'
    script.write_text('#!/bin/sh\ncat >/dev/null\nprintf %s \'' + json.dumps({'result': json.dumps(result, ensure_ascii=False)}, ensure_ascii=False).replace("'", "'\\''") + '\'\n')
    script.chmod(0o755)
    return {'PATH': str(directory) + ':' + os.environ['PATH'], 'ZH_LINT_NO_MODEL': ''}


class StopHookTests(unittest.TestCase):
    def test_problem_in_final_reply_is_listed_as_pairs(self):
        path = transcript([user('之前的话'), assistant('等 CI 绿了再 merge。'), user('现在呢'), assistant('好，先看。'), tool_result(), assistant('等 CI 绿了由你 merge。')])
        code, out = run(path)
        self.assertEqual(code, 0)
        self.assertNotIn('decision', out)
        self.assertIn('「CI 绿了」→', out['systemMessage'])

    def test_only_current_turn_is_linted(self):
        path = transcript([user('一'), assistant('等 CI 绿了再 merge。'), user('二'), assistant('好，改好了。')])
        self.assertEqual(run(path), (0, {}))

    def test_model_hits_merge_with_regex_hits(self):
        path = transcript([user('问'), assistant('两份都折进去了。\n整体看有两个硬理由。')])
        with tempfile.TemporaryDirectory() as directory:
            env = fake_claude(directory, {'hits': [{'sentence': '两份都折进去了。', 'mechanism': 1, 'match': '折进去', 'fix': '写进去了'}, {'sentence': '整体看有两个硬理由。', 'mechanism': 3, 'match': '硬理由', 'fix': '站得住的理由'}]})
            code, out = run(path, env=env)
        self.assertEqual(code, 0)
        self.assertNotIn('decision', out)
        self.assertEqual(out['systemMessage'].count('「折进去」'), 1)
        self.assertIn('「硬理由」→ 站得住的理由', out['systemMessage'])

    def test_plugin_mode_also_injects_core_rules(self):
        payload = json.dumps({'session_id': 'p', 'prompt': '问'})
        plain = subprocess.run([sys.executable, str(SUBMIT)], input=payload, capture_output=True, text=True, env=dict(os.environ, HOME=HOME, CLAUDE_PLUGIN_ROOT=''))
        plugin = subprocess.run([sys.executable, str(SUBMIT)], input=payload, capture_output=True, text=True, env=dict(os.environ, HOME=HOME, CLAUDE_PLUGIN_ROOT='/x'))
        plain_ctx = json.loads(plain.stdout)['hookSpecificOutput']['additionalContext']
        plugin_ctx = json.loads(plugin.stdout)['hookSpecificOutput']['additionalContext']
        self.assertNotIn('先保留原意', plain_ctx)
        self.assertIn('先保留原意', plugin_ctx)
        self.assertIn('七种问题', plugin_ctx)

    def test_unsure_items_are_logged_but_not_shown(self):
        path = transcript([user('问'), assistant('这个方案站得住。')])
        with tempfile.TemporaryDirectory() as directory:
            env = fake_claude(directory, {'hits': [], 'unsure': [{'sentence': '这个方案站得住。', 'mechanism': 1, 'match': '站得住', 'fix': '成立'}]})
            code, out = run(path, env=env)
        self.assertEqual((code, out), (0, {}))
        entry = json.loads((Path(HOME) / '.claude' / 'zh-replies' / 'stop-log.jsonl').read_text().splitlines()[-1])
        self.assertEqual((entry['hits'], entry['unsure'][0]['match']), ([], '站得住'))

    def test_model_failure_is_reported_not_blocking(self):
        path = transcript([user('问'), assistant('一切正常。')])
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / 'claude'
            broken.write_text('#!/bin/sh\necho boom >&2\nexit 3\n')
            broken.chmod(0o755)
            code, out = run(path, env={'PATH': str(directory) + ':' + os.environ['PATH'], 'ZH_LINT_NO_MODEL': ''})
        self.assertEqual(code, 0)
        self.assertNotIn('decision', out)
        self.assertIn('zh-check 没跑成', out['systemMessage'])

    def test_automated_turn_runs_regex_only(self):
        path = transcript([user('人说的'), assistant('好。'), user('<task-notification>\n<task-id>x</task-id>\n</task-notification>'), assistant('等 CI 绿了再 merge。')])
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / 'claude'
            broken.write_text('#!/bin/sh\necho should-not-run >&2\nexit 3\n')
            broken.chmod(0o755)
            code, out = run(path, env={'PATH': str(directory) + ':' + os.environ['PATH'], 'ZH_LINT_NO_MODEL': ''})
        self.assertEqual(code, 0)
        self.assertNotIn('decision', out)
        self.assertIn('「CI 绿了」', out['systemMessage'])
        self.assertNotIn('zh-check 没跑成', out['systemMessage'])

    def test_only_last_assistant_message_is_checked(self):
        path = transcript([user('问'), assistant('改完提交进 git 了。'), tool_result(), assistant('好，一切正常。')])
        self.assertEqual(run(path), (0, {}))

    def test_findings_are_logged_and_fed_into_next_prompt(self):
        path = transcript([user('问'), assistant('等 CI 绿了再 merge。')])
        run(path)
        log = Path(HOME) / '.claude' / 'zh-replies' / 'stop-log.jsonl'
        entry = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual((entry['session_id'], entry['reply'], entry['hits'][0]['match'], entry['hits'][0]['source']), ('s', '等 CI 绿了再 merge。', 'CI 绿了', 'regex'))
        done = subprocess.run([sys.executable, str(SUBMIT)], input=json.dumps({'session_id': 's', 'prompt': '下一个问题'}), capture_output=True, text=True, env=dict(os.environ, HOME=HOME))
        context = json.loads(done.stdout)['hookSpecificOutput']['additionalContext']
        self.assertIn('上一条回复里查到的毛病', context)
        self.assertIn('「CI 绿了」→', context)
        done = subprocess.run([sys.executable, str(SUBMIT)], input=json.dumps({'session_id': 'other', 'prompt': '下一个问题'}), capture_output=True, text=True, env=dict(os.environ, HOME=HOME))
        self.assertNotIn('上一条回复', json.loads(done.stdout)['hookSpecificOutput']['additionalContext'])

    def test_hint_tier_only_messages_user(self):
        path = transcript([user('问'), assistant('migration 都跑完了。')])
        code, out = run(path)
        self.assertEqual(code, 0)
        self.assertNotIn('decision', out)
        self.assertIn('跑完', out['systemMessage'])


if __name__ == '__main__':
    unittest.main()
