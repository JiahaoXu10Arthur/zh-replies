"""正则 lint：扫 agent 写给用户的中文，按三档报命中。只用标准库。

用法：
    python3 zh_lint.py FILE...        # 扫文件
    printf '%s' '文本' | python3 zh_lint.py   # 扫 stdin
    python3 zh_lint.py --json FILE    # JSON 输出
退出码：有「问题」档命中为 1，否则 0。

三档：问题（按规则算错，应改写）、提示（不如中文说法自然，只提示）、正常用法（中文技术圈本来就这么说，不报，见 ALLOW）。
关掉某条规则：在 ~/.claude/zh-replies/config.json 写 {"disabled_rules": ["规则名"]}，规则名见 `python3 zh_replies.py rules`；haiku 的机制也可以关，名字是「机制1」到「机制7」。
"""
import json
import re
import sys
from pathlib import Path


RULES = [
    ('问题', '颜色指代结果', r'(?:CI|test|测试|检查|流水线|pipeline|节点)[^\n。]{0,12}(?:全绿|变绿|变红|绿了|红了|是红是绿|红绿)|(?:全绿|变绿|变红|绿了|红了|是红是绿)(?=[^\n。]{0,12}(?:CI|test|测试|检查|merge|合并))', '说通过或失败'),
    ('问题', '英文动词直译', r'抛出(?=[^\n。]{0,12}(?:错误|异常|`|Error|Exception))|在飞|飞着|飞起来|(?:由你|等你|你来|你)定(?=[。！；，\n]|了我|$)|收窄|放宽(?=规则|范围|条件)', '报错 / 还在跑、未完成 / 你定是 your call 直译，写「请你决定」「你决定了我再做」 / 收窄是 narrow 直译，写「把范围改小」「只查动词」'),
    ('问题', 'AI 比喻词', r'守卫|魔法值|尺子|吃掉(?:了)?(?:异常|错误|报错|Enter)|会咬人|推着走|没有牙|地基(?!档)', '写字面意思：guard、sentinel value、swallow、不处理'),
    ('问题', '自造说法', r'[一二两三四五六七八九十几\d]+个洞|洞[一二三四五]|的洞(?!察)|吐(?:元素|出|数据|结果)|折进(?:去|来)?|翻[^\n，。]{0,4}的话|答虚|口子|等(?:他|她|对方|面试官)追(?!问)|停车(?:球队|队|用)|悬空|说实(?!话|在)|是正经的|按[^\n，。]{0,6}口气|还挂着|挂着(?=等|没|的)|(?:问题|疑问|「[^」\n]{1,8}」)还在(?=[：，。？\n])|核(?:上|完|过)(?!对)|(?:条|项|个|雷)最重(?!要)|最重的(?:一条|一项|问题|雷)|兜住|做活|再翻(?=[。，）])|条站住|站住(?=[，。；])|折回|我没接(?!受)|没接的|不推(?=[，。；])|不拦(?=[，。；])|要打折(?!扣)|打折的(?=[：，])|关门全靠|做掉的|根子在|失去判据|开启日期|就地追加|比[^\n，。]{1,6}深的(?=[：，])|推出[^\n，。]{0,12}变体|(?:OPEN|open|待定|那条|这条)[^\n，。]{0,4}(?:就关了|关了|关掉)', '写字面意思：没答好的题、已经加进去、提他说过的话'),
    ('问题', '自造名词', r'派发器|[两三四五几]个面(?=[。，：])|样张|关门句', '新概念用英文原名或大白话，不自己造中文名词；样张→sample，关门句→close'),
    ('问题', '技术名词该用英文', r'票(?= ?\d|本身)|按票|[一两三几\d]张票|这张票|烟雾测试|冒烟测试|提交(?= ?进 ?git|的改动|了代码|代码)|未提交|退出码|合并请求|拉取请求|分支保护|已经合进|合进(?: ?(?:dev|main|master))', '用英文原名：ticket'),
    ('问题', '强制口气', r'你必须(?:选|定|决定)|必须选一个|只能选一个|(?:^|[\n。！？])(?:写|改|做|上|来|去)吧[。！]|写完跑', '摆出方案，请用户给意见；下一步用完整的句子说，不用一个字加「吧」'),
    ('问题', '催答复的问法', r'[^\n，。？！「」“”`]{1,12}你(?:接受|认|认可|同意)吗|认不认|认了(?:我|再|就)', '「你觉得可以吗」「你看有要改的地方吗」'),
    ('问题', '一句两个破折号', r'(?:——|—— )[^\n。]{1,60}(?:——| ——)', '拆成两句'),
    ('提示', '跑完跑通', r'跑完|跑通', '「运行完」「通过」更自然'),
    ('提示', '分号破折号', r'；|——', '中文少用分号和破折号：分号拆成两句，破折号改成逗号、冒号或括号'),
    ('提示', '不是而是句式', r'只是[^\n，。]{1,12}，不是[^\n，。]{1,8}[。）\n]|不是[^\n，。]{1,12}，而是', '正面写它是什么，拆成一句'),
    ('提示', '词义对但用法不对', r'口径|不包装|看准了|落库|兜底|工作区干净|干净的工作区|干净无|Repo 是干净的|踩坑|填坑|有坑|是个坑|大坑|(?:reviewer|agent|job|服务|进程)[^\n，。]{0,3}挂(?:了|的)', '词是中文有的，这里的用法不对：口径是说话的口径；包装、看准了都不是这个场合的说法'),
    ('提示', '编号指代', r'第[一二三四五六七八九\d]+(?:条|点|项)(?=[^\n。]{0,3}(?:说|讲|提|是|里))|上面(?:第|那)[一二三四五六七八九\d]+(?:条|点|项)', '直接写出所指'),
    ('提示', '进行＋动词', r'进行(?:判断|验证|处理|修改|检查|比较|分析|测试|确认|评估)', '直接用动词'),
    ('提示', '被动直译', r'被(?:设计为|实现为|用于|视为|看作)', '改主动'),
    ('提示', '英文介词句式', r'基于(?:这|此|该|以上|上面)|在[^\n。，]{1,10}的情况下', '「照……」「……时」'),
    ('提示', '堆叠的', r'的[^\n。，、的]{1,8}的[^\n。，、的]{1,8}的[^\n。，、的]{1,8}的', '拆成短句'),
]
REPLACE = [
    (r'提交(?= ?进 ?git)', 'commit'), (r'未提交', '没 commit'), (r'退出码', 'exit code'), (r'烟雾测试|冒烟测试', 'smoke test'),
    (r'票(?= ?\d)', 'ticket'), (r'跑完', '运行完'), (r'跑通', '通过'), (r'全绿', '全部通过'), (r'(?P<ci>CI[^\n，。]{0,6}?)绿了', r'\g<ci>通过了'),
    (r'抛出(?=[^\n。]{0,12}(?:错误|异常|`|Error|Exception))', '报'), (r'守卫', 'guard'), (r'核过', '核对过'), (r'核完', '核对完'),
    (r'核上的', '核对上的'), (r'我没接的', '我没接受的'), (r'不推(?=[，。；])', '不 push'), (r'尺子', '标准'), (r'派发器', 'dispatcher'),
]
REPLACE_RX = re.compile('|'.join('(?P<r%d>%s)' % (i, p) for i, (p, _) in enumerate(REPLACE)))
CJK = re.compile(r'[\u4e00-\u9fff]')


def substitute(text):
    """Apply the one-to-one replacements in one pass; return (new text, [(from, to)]). Quoted and inline-code spans are left alone."""
    quoted = [m.span() for m in QUOTED.finditer(text)]
    off = disabled_rules()
    off_rx = [rx for _, name, rx, _ in COMPILED if name in off]
    changes = []
    def swap(m):
        if any(a < m.start() and m.end() <= b for a, b in quoted) or any(rx.search(m.group(0)) for rx in off_rx):
            return m.group(0)
        index = int(m.lastgroup[1:])
        out = m.expand(REPLACE[index][1]) if '\\' in REPLACE[index][1] else REPLACE[index][1]
        before = text[m.start() - 1] if m.start() else ''
        after = text[m.end()] if m.end() < len(text) else ''
        if out[:1].isascii() and out[:1].isalpha() and CJK.match(before):
            out = ' ' + out
        if out[-1:].isascii() and out[-1:].isalnum() and (CJK.match(after) or after.isdigit()):
            out = out + ' '
        changes.append((m.group(0), out.strip()))
        return out
    return REPLACE_RX.sub(swap, text), changes


ALLOW = ['落地', '跑（代码、脚本、测试）']
COMPILED = [(tier, name, re.compile(pattern), hint) for tier, name, pattern, hint in RULES]
CONFIG = Path.home() / '.claude' / 'zh-replies' / 'config.json'


def disabled_rules():
    """Rule names the user switched off in config.json; a missing file means none."""
    if not CONFIG.exists():
        return set()
    return set(json.loads(CONFIG.read_text(encoding='utf-8')).get('disabled_rules', []))


def context(text, start, end):
    left = max(text.rfind('\n', 0, start), text.rfind('。', 0, start)) + 1
    rights = [i for i in (text.find('\n', end), text.find('。', end)) if i != -1]
    right = min(rights) + 1 if rights else len(text)
    return text[left:right].strip()


QUOTED = re.compile(r'「[^」\n]*」|“[^”\n]*”|```[\s\S]*?```|`[^`\n]*`')


def lint(text):
    quoted = [m.span() for m in QUOTED.finditer(text)]
    off = disabled_rules()
    hits = []
    for tier, name, rx, hint in COMPILED:
        if name in off:
            continue
        for m in rx.finditer(text):
            if any(a < m.start() and m.end() <= b for a, b in quoted):
                continue
            hits.append({'tier': tier, 'rule': name, 'match': m.group(0), 'line': text.count('\n', 0, m.start()) + 1, 'sentence': context(text, m.start(), m.end()), 'hint': hint})
    hits.sort(key=lambda h: (h['line'], h['tier'] != '问题'))
    return hits


def main(argv):
    as_json = '--json' in argv
    paths = [a for a in argv if a != '--json']
    sources = [(p, Path(p).read_text(encoding='utf-8')) for p in paths] if paths else [('stdin', sys.stdin.read())]
    all_hits = []
    for name, text in sources:
        for h in lint(text):
            all_hits.append({'file': name, **h})
    if as_json:
        print(json.dumps(all_hits, ensure_ascii=False, indent=2))
    else:
        for h in all_hits:
            print(f"{h['file']}:{h['line']} [{h['tier']}] {h['rule']}「{h['match']}」→ {h['hint']}\n    {h['sentence']}")
        problems = sum(h['tier'] == '问题' for h in all_hits)
        print(f"问题 {problems}，提示 {len(all_hits) - problems}")
    return 1 if any(h['tier'] == '问题' for h in all_hits) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
