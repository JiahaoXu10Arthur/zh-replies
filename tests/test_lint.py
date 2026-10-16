import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import zh_lint


def rules(text, tier=None):
    return [h['rule'] for h in zh_lint.lint(text) if tier is None or h['tier'] == tier]


class LintTests(unittest.TestCase):
    def test_problem_tier_catches_sentences_the_user_flagged(self):
        self.assertEqual(rules('递归版本直接抛出 `RecursionError`', '问题'), ['英文动词直译'])
        self.assertEqual(rules('CI 是红是绿都不影响合并按钮', '问题'), ['颜色指代结果'])
        self.assertEqual(rules('等 CI 绿了，由你 merge。', '问题'), ['颜色指代结果'])
        self.assertEqual(rules('这份 sample 你接受吗？', '问题'), ['催答复的问法'])
        self.assertEqual(rules('范围、影响、root cause 你认不认？认了我再回到方案的 Q1。', '问题'), ['催答复的问法', '催答复的问法'])
        self.assertEqual(rules('你接受这份 sample 吗？如果接受，我会先把它写进 spec。'), [])
        self.assertEqual(rules('sample 在上面，你看有要改的地方吗？'), [])
        self.assertEqual(rules('反例写成「这份 sample 你接受吗」「认不认」，正例是「你觉得可以吗」。'), [])
        self.assertEqual(rules('我倾向 A，你必须选一个。', '问题'), ['强制口气'])
        self.assertEqual(rules('一个不多一个不少。\n写吧。先想清楚两件事。写完跑：', '问题'), ['强制口气', '强制口气'])
        self.assertEqual(rules('这个思路可以，你写吧，我在旁边看。'), [])
        self.assertEqual(rules('二面准备两个洞', '问题'), ['自造说法'])
        self.assertEqual(rules('你说的不写 Rust，都已经折进去了', '问题'), ['自造说法'])
        self.assertEqual(rules('不主动翻他一面的话', '问题'), ['自造说法'])
        self.assertEqual(rules('一面答虚的两道题', '问题'), ['自造说法'])
        self.assertEqual(rules('这是个真的口子，先记着。', '问题'), ['自造说法'])
        self.assertEqual(rules('两道都按二十秒版、停、等他追。', '问题'), ['自造说法'])
        self.assertEqual(rules('说二十秒就停，等他追问。'), [])
        self.assertEqual(rules('XXX INACTIVE、NBA Draft 这三支停车球队', '问题'), ['自造说法'])
        self.assertEqual(rules('球场旁边没有停车位。'), [])
        self.assertEqual(rules('2,963 条已经悬空的旧 MLB schedule', '问题'), ['自造说法'])
        self.assertEqual(rules('洞一：if not a: return b', '问题'), ['自造说法'])
        self.assertEqual(rules('要从大往小吐元素', '问题'), ['自造说法'])
        self.assertEqual(rules('把能做的说实，让他判断。', '问题'), ['自造说法'])
        self.assertEqual(rules('你简历对不上的是正经的', '问题'), ['自造说法'])
        self.assertEqual(rules('草稿，按微信口气：', '问题'), ['自造说法'])
        self.assertEqual(rules('说实话，这个说实在的不难。'), [])
        self.assertEqual(rules('还挂着等你定方向的：这种改名要不要配对。', '问题'), ['自造说法'])
        self.assertEqual(rules('墙上挂着一幅画。'), [])
        self.assertEqual(rules('238 的「为什么」还在：题目不让用除法。', '问题'), ['自造说法'])
        self.assertEqual(rules('服务还在跑，人还在公司。'), [])
        self.assertEqual(rules('公司背景核完了，关键两处我自己核过。核上的：', '问题'), ['自造说法', '自造说法', '自造说法'])
        self.assertEqual(rules('新雷，这条最重', '问题'), ['自造说法'])
        self.assertEqual(rules('我核对过了，最重要的是这条。'), [])
        self.assertEqual(rules('真出错由测试和 CI 兜住', '问题'), ['自造说法'])
        self.assertEqual(sorted(rules('sync-manager 变成纯派发器，要把派发做活。先 report-only 看几晚再翻。dashboard 两个面。', '问题')), ['自造名词', '自造名词', '自造说法', '自造说法'])
        self.assertEqual(rules('13 条站住，1 条没验。全部接受我就折回 spec。', '问题'), ['自造说法', '自造说法'])
        self.assertEqual(rules('这个理由站住脚。'), [])
        self.assertEqual(rules('它建议、我没接的：推出 single 变体。它自己也说不推，保留 20 次 run。', '问题'), ['自造说法'] * 3)
        self.assertEqual(rules('我没接受这个建议，推出了新版本。'), [])
        self.assertEqual(rules('票本身就是计划。票 00 已经做完，正准备做票 01。', '问题'), ['技术名词该用英文'] * 3)
        self.assertEqual(rules('我买了两张电影票。'), [])
        self.assertEqual(rules('烟雾测试完成。', '问题'), ['技术名词该用英文'])
        self.assertEqual(rules('不提交进 git。没有未提交的改动。退出码 0。', '问题'), ['技术名词该用英文'] * 3)
        self.assertEqual(rules('简历提交了，表格提交给 HR。'), [])
        self.assertEqual(rules('可以的话 OPEN 那条就关了。', '问题'), ['自造说法'])
        self.assertEqual(rules('灯关了，服务关掉了。'), [])
        self.assertEqual(rules('haiku 调用失败了只提示一句，不拦。', '问题'), ['自造说法'])
        self.assertEqual(rules('调研自身要打折的：两篇 harness 文章是二手。', '问题'), ['自造说法'])
        self.assertEqual(rules('这个结论的可信度要打折扣。'), [])
        self.assertEqual(rules('比调研深的：评测里的 judge 校准和标签循环。', '问题'), ['自造说法'])
        self.assertEqual(rules('这口井比那口深。'), [])
        self.assertEqual(sorted(rules('9/27 才写关门句。根子在命令本身。条目没有开启日期。', '问题')), ['自造名词', '自造说法', '自造说法'])
        self.assertEqual(rules('决定前先做一份样张给你看。', '问题'), ['自造名词'])
        self.assertEqual(rules('git 里 #113 已经合进。', '问题'), ['技术名词该用英文'])
        self.assertEqual(rules('spec-grill 要不要优化，用什么尺子量；过程里没改尺子。', '问题'), ['AI 比喻词'] * 2)
        self.assertEqual(rules('Repo 是干净的。reviewer 挂了换 stamp 再跑一次。', '提示'), ['词义对但用法不对'] * 2)
        self.assertEqual(rules('翻到下一页，这个面试有两个面试官。'), [])
        self.assertEqual(rules('和球员同一个口径', '提示'), ['词义对但用法不对'])
        self.assertEqual(rules('和球员同一个口径', '问题'), [])
        self.assertEqual(rules('回的时候不包装，招聘说这话是看准了。', '提示'), ['词义对但用法不对', '词义对但用法不对'])
        self.assertEqual(rules('回的时候不包装，招聘说这话是看准了。', '问题'), [])
        self.assertEqual(rules('两份都落库了，要点：', '提示'), ['词义对但用法不对'])
        self.assertEqual(rules('用兜底日期', '提示'), ['词义对但用法不对'])
        self.assertEqual(rules('工作区干净，这里有坑，上次踩坑了。', '提示'), ['词义对但用法不对'] * 3)
        self.assertEqual(rules('修了一个安全漏洞，洞察力不错'), [])
        self.assertEqual(rules('review-workflows 干净无在飞代码', '问题'), ['英文动词直译'])
        self.assertEqual(rules('用 A 还是 B，你定。先停在这里等你定，你定了我再改。', '问题'), ['英文动词直译'] * 3)
        self.assertEqual(rules('你定的规矩我照做，定金已经付了。'), [])
        self.assertEqual(rules('M2 要收窄成只查动词。', '问题'), ['英文动词直译'])
        self.assertEqual(rules('没有 `require.main` 守卫，直接跑 `main()`', '问题'), ['AI 比喻词'])
        self.assertEqual(rules('这一步是对外的 —— 他收到了通知 —— 这种动作我该先问你。', '问题'), ['一句两个破折号'])

    def test_hint_tier_only_hints(self):
        hits = zh_lint.lint('migration 都跑完了，上面第三条说的那个索引进行验证。')
        self.assertEqual({h['tier'] for h in hits}, {'提示'})
        self.assertEqual(rules('migration 都跑完了'), ['跑完跑通'])
        self.assertEqual(rules('先改 A；再改 B——然后 merge。', '提示'), ['分号破折号', '分号破折号'])
        self.assertEqual(rules('例子只是帮助认出来，不是词表。', '提示'), ['不是而是句式'])
        self.assertEqual(rules('这不是 bug，而是设计如此。', '提示'), ['不是而是句式'])
        self.assertEqual(rules('这个文件不是 README。'), [])

    def test_allowed_usage_is_silent(self):
        for text in ['改动落地了', '跑一遍测试', '第二个球员那条存不进去', '转述：他说「必须选一个」的原因是表单收不到 Enter', '地基档案', '例子：\n```sh\necho 等 CI 绿了再 merge\n```\n']:
            self.assertEqual(zh_lint.lint(text), [], text)

    def test_disabled_rule_is_skipped_by_lint_and_substitute(self):
        import os, tempfile
        home = tempfile.mkdtemp()
        cfg = Path(home) / '.claude' / 'zh-replies'
        cfg.mkdir(parents=True)
        (cfg / 'config.json').write_text('{"disabled_rules": ["跑完跑通", "颜色指代结果"]}', encoding='utf-8')
        saved, os.environ['HOME'] = os.environ.get('HOME'), home
        saved_cfg, zh_lint.CONFIG = zh_lint.CONFIG, cfg / 'config.json'
        try:
            self.assertEqual(rules('migration 跑完了，等 CI 绿了再 merge，烟雾测试完成。'), ['技术名词该用英文'])
            text, changes = zh_lint.substitute('migration 跑完了，等 CI 绿了再 merge，烟雾测试完成。')
            self.assertEqual(text, 'migration 跑完了，等 CI 绿了再 merge，smoke test 完成。')
        finally:
            zh_lint.CONFIG = saved_cfg
            os.environ['HOME'] = saved

    def test_hit_carries_line_sentence_and_hint(self):
        hit = zh_lint.lint('第一行。\n等 CI 绿了再 merge。')[0]
        self.assertEqual((hit['line'], hit['sentence']), (2, '等 CI 绿了再 merge。'))
        self.assertTrue(hit['hint'])

    def test_cli_exit_code_follows_problem_tier(self):
        root = Path(__file__).resolve().parents[1]
        run = lambda text: subprocess.run([sys.executable, str(root / 'zh_lint.py')], input=text, capture_output=True, text=True)
        self.assertEqual(run('migration 跑完了').returncode, 0)
        bad = run('等 CI 绿了再说')
        self.assertEqual(bad.returncode, 1)
        self.assertIn('颜色指代结果', bad.stdout)


if __name__ == '__main__':
    unittest.main()
