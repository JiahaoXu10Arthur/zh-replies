import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.claude = self.root / 'claude'
        self.codex = self.root / 'codex'
        self.claude.mkdir()
        self.codex.mkdir()
        self.c = self.claude / 'CLAUDE.md'
        self.x = self.codex / 'AGENTS.md'
        self.c.write_bytes(b'Original\r\nno final newline')
        self.x.write_bytes(b'Original codex\n')
        os.chmod(self.c, 0o640)

    def run_cli(self, action, *args):
        return subprocess.run([sys.executable, str(ROOT / 'zh_replies.py'), action,
                               '--claude-dir', str(self.claude), '--codex-dir', str(self.codex),
                               *args], capture_output=True, text=True)

    def install(self, *args):
        r = self.run_cli('install', *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_install_update_disable_restore_original_bytes_and_mode(self):
        self.install()
        installed = self.c.read_bytes()
        self.install()
        self.assertEqual(self.c.read_bytes(), installed)
        self.assertEqual(self.c.stat().st_mode & 0o777, 0o640)
        r = self.run_cli('disable')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.c.read_bytes(), b'Original\r\nno final newline')
        self.assertEqual(self.x.read_bytes(), b'Original codex\n')
        self.assertEqual(self.run_cli('disable').returncode, 0)

    def test_with_hooks_merges_into_settings_and_disable_removes_only_ours(self):
        settings = self.claude / 'settings.json'
        settings.write_text(json.dumps({'model': 'opus', 'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'echo theirs'}]}]}}))
        self.install('--with-hooks')
        self.install('--with-hooks')
        data = json.loads(settings.read_text())
        self.assertEqual(data['model'], 'opus')
        self.assertEqual([h['command'] for e in data['hooks']['Stop'] for h in e['hooks']], ['echo theirs', 'python3 ' + str(ROOT / 'hooks' / 'zh_lint_stop.py')])
        self.assertEqual(data['hooks']['MessageDisplay'][0]['hooks'][0]['timeout'], 30)
        self.assertIn('UserPromptSubmit', data['hooks'])
        self.assertTrue(json.loads(self.run_cli('status').stdout)['hooks_installed'])
        self.assertEqual(self.run_cli('disable').returncode, 0)
        data = json.loads(settings.read_text())
        self.assertEqual(data['hooks'], {'Stop': [{'hooks': [{'type': 'command', 'command': 'echo theirs'}]}]})
        self.assertFalse(json.loads(self.run_cli('status').stdout)['hooks_installed'])

    def test_install_without_flag_leaves_settings_alone(self):
        self.install()
        self.assertFalse((self.claude / 'settings.json').exists())

    def test_personal_source_reloads_and_explicit_removal_preserves_file(self):
        p = self.root / 'personal.md'
        p.write_text('Preference FIRST.')
        self.install('--personal', str(p))
        p.write_text('Preference SECOND.')
        self.install()
        self.assertIn('Preference SECOND.', self.c.read_text())
        self.assertNotIn('Preference FIRST.', self.c.read_text())
        self.install('--without-personal')
        self.assertNotIn('Preference SECOND.', self.c.read_text())
        self.assertEqual(p.read_text(), 'Preference SECOND.')

    def test_each_target_remembers_own_source(self):
        a, b = self.root / 'a.md', self.root / 'b.md'
        a.write_text('AAA preference'); b.write_text('BBB preference')
        self.install('--agent', 'claude', '--personal', str(a))
        self.install('--agent', 'codex', '--personal', str(b))
        a.write_text('AAA update'); b.write_text('BBB update')
        self.install()
        self.assertIn('AAA update', self.c.read_text())
        self.assertNotIn('BBB update', self.c.read_text())
        self.assertIn('BBB update', self.x.read_text())

    def test_missing_personal_source_preflights_both_targets(self):
        p = self.root / 'personal.md'; p.write_text('Local preference')
        self.install('--personal', str(p))
        before = self.c.read_bytes(), self.x.read_bytes()
        p.unlink()
        r = self.run_cli('install')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.c.read_bytes(), self.x.read_bytes()), before)

    def test_hand_edited_block_is_refused_without_touching_other_target(self):
        self.install()
        before = self.c.read_bytes()
        self.x.write_bytes(self.x.read_bytes().replace('中文对话回复'.encode(), b'edited'))
        edited = self.x.read_bytes()
        r = self.run_cli('install')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.c.read_bytes(), before)
        self.assertEqual(self.x.read_bytes(), edited)

    def test_symlink_and_nonempty_override_are_refused(self):
        original = self.root / 'original.md'; original.write_text('Keep me')
        self.x.unlink(); self.x.symlink_to(original)
        self.assertNotEqual(self.run_cli('install').returncode, 0)
        self.assertEqual(self.c.read_bytes(), b'Original\r\nno final newline')
        self.assertEqual(original.read_text(), 'Keep me')
        self.x.unlink(); self.x.write_text('Original codex')
        (self.codex / 'AGENTS.override.md').write_text('Overrides')
        self.assertNotEqual(self.run_cli('install').returncode, 0)
        (self.codex / 'AGENTS.override.md').write_text('')
        self.install()

    def test_size_boundary_and_rejection_preserve_all_targets(self):
        self.install()
        overhead = len(self.x.read_bytes()) - len(b'Original codex\n')
        self.run_cli('disable')
        self.x.write_bytes(b'x' * (32768 - overhead))
        self.install()
        self.assertEqual(self.x.stat().st_size, 32768)
        self.run_cli('disable')
        self.x.write_bytes(b'x' * (32769 - overhead))
        before = self.c.read_bytes(), self.x.read_bytes()
        self.assertNotEqual(self.run_cli('install').returncode, 0)
        self.assertEqual((self.c.read_bytes(), self.x.read_bytes()), before)

    def test_second_target_write_failure_is_recoverable(self):
        from unittest.mock import patch
        import zh_replies
        args = zh_replies.parser().parse_args(['install', '--claude-dir', str(self.claude),
                                              '--codex-dir', str(self.codex)])
        real_replace = os.replace
        def failing_replace(source, target):
            if Path(target) == self.x:
                raise OSError('injected second target failure')
            return real_replace(source, target)
        with patch('zh_replies.os.replace', side_effect=failing_replace):
            with self.assertRaises(zh_replies.Failure):
                zh_replies.manage(args)
        self.assertIn('中文对话回复', self.c.read_text())
        self.assertEqual(self.x.read_bytes(), b'Original codex\n')
        self.install()
        self.assertEqual(self.run_cli('status').returncode, 0)
        self.assertEqual(self.run_cli('disable').returncode, 0)
        self.assertEqual(self.c.read_bytes(), b'Original\r\nno final newline')

    def test_status_distinguishes_snapshot_from_session_loading(self):
        self.install()
        r = self.run_cli('status')
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertTrue(all(row['installed'] for row in d['targets']))
        self.assertTrue(all(row['active_session'] == 'unknown' for row in d['targets']))
        self.assertGreater(d['core_bytes'], 0)

    def test_malformed_begin_marker_preflights_all_targets(self):
        self.x.write_text('Original\n<!-- zh-replies:begin-->\npartial')
        before=self.c.read_bytes(),self.x.read_bytes()
        self.assertNotEqual(self.run_cli('install').returncode,0)
        self.assertEqual((self.c.read_bytes(),self.x.read_bytes()),before)

    def test_personal_cannot_inject_managed_markers(self):
        p = self.root / 'p.md'; p.write_text('<!-- zh-replies:end -->')
        self.assertNotEqual(self.run_cli('install', '--personal', str(p)).returncode, 0)
        self.assertEqual(self.c.read_bytes(), b'Original\r\nno final newline')


if __name__ == '__main__':
    unittest.main()
