import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE = r'''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
checker=sys.argv[sys.argv.index('--tools')+1]==''
mode=os.environ.get('CASE','normal'); role='checker' if checker else 'generator'
p=Path(os.environ['TRACE']);p.open('a').write(json.dumps({'role':role,'args':sys.argv[1:]})+'\n')
print(json.dumps({'type':'system','subtype':'init','tools':[] if checker else ['Read']}),flush=True)
if mode==role+'-wait':
 print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'SECRET_PARTIAL'}]}}),flush=True)
 time.sleep(60)
if mode=='nonzero':
 print('SECRET_PROVIDER',file=sys.stderr);sys.exit(3)
if mode=='server-tool':
 print(json.dumps({'type':'assistant','message':{'content':[{'type':'server_tool_use','id':'s','name':'Bash','input':{}}]}}))
if mode=='missing-read-result':
 print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':'r','name':'Read','input':{'file_path':'/fixture'}}]}}))
if mode=='extra-tool':
 print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':'t','name':'Bash','input':{'command':'secret'}}]}}))
if not checker and mode.startswith('read'):
 print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':'r','name':'Read','input':{'file_path':'/fixture'}}]}}))
 print(json.dumps({'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'r','content':'Read fact: LIMIT=2'}]}}))
 if mode=='read-wait':time.sleep(60)
if mode=='missing-final':sys.exit(0)
if mode=='invalid-event':print('bad event');sys.exit(0)
answer={'reply':'已检查。`LIMIT` 为 2。','meaning_preserved':True}
if checker:
 if mode in ('bad-json','read-error'):result='not json SECRET_DRAFT'
 elif mode=='false':answer['meaning_preserved']=False;result=json.dumps(answer)
 elif mode=='bool-string':answer['meaning_preserved']='true';result=json.dumps(answer)
 elif mode=='empty':answer['reply']='';result=json.dumps(answer)
 elif mode=='protected-change':answer['reply']='LIMIT 为 3。';result=json.dumps(answer)
 else:result=json.dumps(answer)
else:result='SECRET_DRAFT。`LIMIT` 为 2。'
print(json.dumps({'type':'result','subtype':'success','is_error':mode=='is-error','result':result}),flush=True)
'''


class ReplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fake = self.root / 'claude'; fake.write_text(FAKE); fake.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root)+os.pathsep+os.environ['PATH'],
                        TRACE=str(self.root/'trace'), CASE='normal')

    def command(self, *args):
        return [sys.executable, str(ROOT/'zh_replies.py'), 'reply', *args]

    def run_cli(self, case='normal', *args):
        self.env['CASE'] = case
        return subprocess.run(self.command(*args), input='请说明LIMIT。', capture_output=True,
                              text=True, env=self.env, timeout=10)

    def test_default_has_no_independent_checker_and_checked_path_is_complete(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = [json.loads(l) for l in (self.root/'trace').read_text().splitlines()]
        self.assertEqual([c['role'] for c in calls], ['generator'])
        (self.root/'trace').unlink()
        r = self.run_cli('normal', '--check')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, '已检查。`LIMIT` 为 2。\n')
        self.assertNotIn('SECRET', r.stdout+r.stderr)
        calls = [json.loads(l) for l in (self.root/'trace').read_text().splitlines()]
        self.assertEqual([c['role'] for c in calls], ['generator','checker'])
        for c in calls:
            for flag in ('--safe-mode','--disable-slash-commands','--strict-mcp-config','--no-session-persistence'):
                self.assertIn(flag, c['args'])
        self.assertEqual(calls[0]['args'][calls[0]['args'].index('--append-system-prompt')+1],
                         calls[1]['args'][calls[1]['args'].index('--append-system-prompt')+1])

    def test_all_validation_errors_pause_delivery_without_raw_text(self):
        for case in ('nonzero','missing-final','invalid-event','is-error','bad-json','false',
                     'bool-string','empty','extra-tool','server-tool','missing-read-result','protected-change','read-error'):
            with self.subTest(case=case):
                r = self.run_cli(case,'--check')
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(r.stdout, '')
                self.assertIn('中文检查未完成，请重试。', r.stderr)
                self.assertNotIn('SECRET',r.stderr)

    def test_timeout_generation_checker_and_read_are_fail_closed(self):
        for case in ('generator-wait','checker-wait','read-wait'):
            with self.subTest(case=case):
                r = self.run_cli(case,'--check','--timeout','0.1')
                self.assertNotEqual(r.returncode,0)
                self.assertEqual(r.stdout,'')
                self.assertNotIn('SECRET',r.stderr)

    def test_cancel_generation_checker_and_read_are_fail_closed(self):
        for case, count in (('generator-wait',1),('checker-wait',2),('read-wait',1)):
            with self.subTest(case=case):
                trace=self.root/'trace'
                if trace.exists():trace.unlink()
                self.env['CASE']=case
                p=subprocess.Popen(self.command('--check'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,text=True,env=self.env)
                p.stdin.write('Prompt');p.stdin.close();p.stdin=None
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    if trace.exists() and len(trace.read_text().splitlines())>=count:break
                    time.sleep(.02)
                time.sleep(.08);p.send_signal(signal.SIGINT)
                out,err=p.communicate(timeout=5)
                self.assertEqual(p.returncode,130,err)
                self.assertEqual(out,'')
                self.assertNotIn('SECRET',err)

    def test_missing_cli_is_safe_and_does_not_print_prompt(self):
        self.env['PATH']=str(self.root/'absent')
        r=self.run_cli('normal','--check')
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(r.stdout,'')
        self.assertIn('中文检查未完成，请重试。',r.stderr)
        self.assertNotIn('请说明',r.stderr)

    def test_invalid_timeout_is_rejected_before_launch(self):
        for value in ('0','-1','nan','inf'):
            self.assertNotEqual(self.run_cli('normal','--timeout',value).returncode,0)
        self.assertFalse((self.root/'trace').exists())


class ProtectionTests(unittest.TestCase):
    def test_supported_spans_reject_alteration_deletion_duplicate_and_reorder(self):
        from reply import validate_candidate, ReplyFailure
        original='正常。\n```py\nx = 2\n```\n~~~txt\nraw\n~~~\n`LIMIT`\n> 固定原话\n[link](https://example.org/a)\n'
        validate_candidate(original,original,[])
        for changed in (original.replace('x = 2','x = 3'), original.replace('`LIMIT`','LIMIT'),
                        original+'> 固定原话\n',original.replace('https://example.org/a','https://example.org/b'),
                        original.replace('`LIMIT`\n> 固定原话','> 固定原话\n`LIMIT`')):
            with self.assertRaises(ReplyFailure):validate_candidate(original,changed,[])

    def test_crlf_fence_and_angle_destination_are_preserved_completely(self):
        from reply import validate_candidate, ReplyFailure
        original = '````py\r\nx = 2\r\n`````\r\n[link](<https://example.org/a b>)'
        validate_candidate(original, original, [])
        for changed in (original.replace('x = 2','x = 3'), original.replace('a b','a c')):
            with self.assertRaises(ReplyFailure):
                validate_candidate(original,changed,[])

    def test_explicit_terms_and_normal_word_senses_are_preserved(self):
        from reply import validate_candidate, ReplyFailure
        original='小模型认不认得？术语A术语A。'
        validate_candidate(original,original,['术语A'])
        with self.assertRaises(ReplyFailure):validate_candidate(original,'小模型认不认得？术语A。',['术语A'])

    def test_variable_delimiters_and_reference_links(self):
        from reply import validate_candidate, ReplyFailure
        original='``a`b``\n   ````py\nx\n   `````\n![image](local.png)\n[label]: https://example.org/ref\n'
        validate_candidate(original,original,[])
        for a,b in [('a`b','a`c'),('local.png','other.png'),('example.org/ref','example.org/other')]:
            with self.assertRaises(ReplyFailure):validate_candidate(original,original.replace(a,b),[])


if __name__ == '__main__':
    unittest.main()
