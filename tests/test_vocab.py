import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import zh_vocab


def entry(kind, content):
    return json.dumps({'type': kind, 'message': {'role': kind, 'content': content}}, ensure_ascii=False)


class VocabTests(unittest.TestCase):
    def test_build_keeps_only_short_human_chinese_messages_and_counts_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            projects = Path(root) / 'projects'
            (projects / '-Users-x-Desktop-app').mkdir(parents=True)
            (projects / '-Users-x-Desktop-zh-style-lint').mkdir()
            lines = [
                entry('user', '这个兜底计划可以'), entry('user', '兜底就行'), entry('user', '兜底就行'),
                entry('user', '<task-notification>兜底</task-notification>'), entry('user', 'Stop hook feedback:\n兜底'),
                entry('user', '# Skill 内容 兜底'), entry('user', 'all english'), entry('user', '看这个 <pasted_content id="1">派发器派发器</pasted_content> 怎么样'),
                entry('user', 'Another Claude session sent a message: 守卫 守卫'), entry('user', '守卫' * 150),
                entry('assistant', [{'type': 'text', 'text': '守卫 守卫'}]),
            ]
            (projects / '-Users-x-Desktop-app' / 'a.jsonl').write_text('\n'.join(lines) + '\n')
            (projects / '-Users-x-Desktop-zh-style-lint' / 'b.jsonl').write_text(entry('user', '两个洞不对') + '\n' + entry('user', '两个洞还是不对') + '\n')
            out = Path(root) / 'vocab.json'
            self.assertEqual(zh_vocab.build(projects, out), 3)
            messages = zh_vocab.load(out)
        self.assertEqual(messages, ['这个兜底计划可以', '兜底就行', '看这个  怎么样'])
        self.assertTrue(zh_vocab.used('兜底', messages))
        self.assertFalse(zh_vocab.used('派发器', messages))
        self.assertFalse(zh_vocab.used('守卫', messages))
        self.assertFalse(zh_vocab.used('两个洞', messages))
        self.assertFalse(zh_vocab.used('这个兜底计划可以', messages))
        self.assertEqual(zh_vocab.load(Path(root) / 'missing.json'), [])

    def test_model_hits_in_user_vocabulary_are_dropped_and_rewrites_undone(self):
        import zh_check
        with tempfile.TemporaryDirectory() as bindir:
            fake = Path(bindir) / 'claude'
            answer = json.dumps({'result': json.dumps({'hits': [{'sentence': 'a', 'mechanism': 1, 'match': '兜底', 'fix': 'x'}, {'sentence': 'b', 'mechanism': 3, 'match': '派发器', 'fix': 'dispatcher'}],
                                                       'text': '整段被模型改乱了\\n多了一行', 'changes': [{'from': '兜底', 'to': '默认值', 'mechanism': 1}, {'from': '派发器', 'to': 'dispatcher', 'mechanism': 3}]}, ensure_ascii=False)}, ensure_ascii=False)
            fake.write_text('#!/bin/sh\ncat >/dev/null\nprintf %s \'' + answer.replace("'", "'\\''") + '\'\n')
            fake.chmod(0o755)
            old = os.environ['PATH']
            os.environ['PATH'] = bindir + ':' + old
            try:
                vocab = ['用兜底值', '兜底就行']
                self.assertEqual([h['match'] for h in zh_check.check('x', vocab=vocab)], ['派发器'])
                text, changes = zh_check.rewrite('用兜底，派发器跑。', vocab=vocab)
            finally:
                os.environ['PATH'] = old
        self.assertEqual(text, '用兜底，dispatcher 跑。')
        self.assertEqual([c['from'] for c in changes], ['派发器'])


if __name__ == '__main__':
    unittest.main()
