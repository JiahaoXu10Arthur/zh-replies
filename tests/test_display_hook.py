import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / 'hooks' / 'zh_display.py'


def run(delta, env=None):
    payload = {'turn_id': 't', 'message_id': 'm', 'index': 0, 'final': True, 'delta': delta}
    merged = dict(os.environ, ZH_DISPLAY_NO_MODEL='1', HOME=env.pop('HOME') if env and 'HOME' in env else os.environ['HOME'])
    merged.update(env or {})
    done = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=merged)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)['hookSpecificOutput']['displayContent'] if done.stdout.strip() else None


class DisplayHookTests(unittest.TestCase):
    def test_replaces_known_words_keeps_partial_line_and_logs(self):
        with tempfile.TemporaryDirectory() as home:
            shown = run('改完提交进 git 了，等 CI 绿了再 merge。\n最后这截没换行', env={'HOME': home})
            self.assertEqual(shown, '改完 commit 进 git 了，等 CI 通过了再 merge。\n最后这截没换行')
            entry = json.loads((Path(home) / '.claude' / 'zh-replies' / 'display-log.jsonl').read_text().splitlines()[-1])
        self.assertEqual(entry['before'], '改完提交进 git 了，等 CI 绿了再 merge。\n')
        self.assertEqual([c['to'] for c in entry['changes']], ['commit', 'CI 通过了'])

    def test_untouched_text_code_block_and_english_only_produce_no_output(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertIsNone(run('一切正常。\n', env={'HOME': home}))
            self.assertIsNone(run('```\n跑完\n', env={'HOME': home}))
            self.assertIsNone(run('all good\n', env={'HOME': home}))
            self.assertFalse((Path(home) / '.claude' / 'zh-replies').exists())

    def test_long_batch_skips_model_and_says_so(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as bindir:
            broken = Path(bindir) / 'claude'
            broken.write_text('#!/bin/sh\necho should-not-run >&2\nexit 3\n')
            broken.chmod(0o755)
            long = ('等 CI 绿了再 merge，这是一句很长的话。' * 30) + '\n'
            shown = run(long, env={'HOME': home, 'PATH': bindir + ':' + os.environ['PATH'], 'ZH_DISPLAY_NO_MODEL': ''})
            self.assertIn('CI 通过了', shown)
            entry = json.loads((Path(home) / '.claude' / 'zh-replies' / 'display-log.jsonl').read_text().splitlines()[-1])
        self.assertIn({'source': 'haiku', 'skipped': 'batch over 300 chars'}, entry['changes'])
        self.assertFalse(any(c.get('error') for c in entry['changes']))

    def test_model_rewrite_is_applied_and_logged_with_source(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as bindir:
            fake = Path(bindir) / 'claude'
            answer = json.dumps({'result': json.dumps({'text': '两份都写进去了。\n', 'changes': [{'from': '折进去', 'to': '写进去', 'mechanism': 1}]}, ensure_ascii=False)}, ensure_ascii=False)
            fake.write_text('#!/bin/sh\ncat >/dev/null\nprintf %s \'' + answer.replace("'", "'\\''") + '\'\n')
            fake.chmod(0o755)
            shown = run('两份都折进去了。\n', env={'HOME': home, 'PATH': bindir + ':' + os.environ['PATH'], 'ZH_DISPLAY_NO_MODEL': ''})
            self.assertEqual(shown, '两份都写进去了。\n')
            entry = json.loads((Path(home) / '.claude' / 'zh-replies' / 'display-log.jsonl').read_text().splitlines()[-1])
        self.assertEqual(entry['changes'], [{'source': 'haiku', 'from': '折进去', 'to': '写进去', 'mechanism': 1}])


if __name__ == '__main__':
    unittest.main()
