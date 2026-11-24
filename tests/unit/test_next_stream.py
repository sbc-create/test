import json,pathlib,types,unittest
from html.parser import HTMLParser
ROOT=pathlib.Path(__file__).resolve().parents[2]
P=ROOT/'automation/local/editorial-sets-validate.py'
m=types.ModuleType('checker');m.__file__=str(P);exec(compile(P.read_text(),str(P),'exec'),m.__dict__)
class Cards(HTMLParser):
 def __init__(self):super().__init__();self.stack=[];self.groups={}
 def handle_starttag(self,t,a):
  d=dict(a);key=d.get('data-home-block');active=key or (self.stack[-1] if self.stack else None)
  if key:self.groups[key]=[]
  if t=='a' and active and any(c in d.get('class','').split() for c in ('portal-top-cell','portal-preview-link')):self.groups[active].append(d['href'])
  if t not in ('meta','link','img','br','hr','input','source','wbr','area','base','embed','param','track','col'):self.stack.append(active)
 def handle_startendtag(self,t,a):
  before=len(self.stack);self.handle_starttag(t,a)
  if len(self.stack)>before:self.stack.pop()
 def handle_endtag(self,t):
  if self.stack:self.stack.pop()
class Test(unittest.TestCase):
 def test_actual_stream_matches_independent_browser_order(self):
  raw=(ROOT/'tests/fixtures/collections/org-live-home.html').read_text();p=Cards();p.feed(m._normalize_next_stream(raw))
  browser=json.loads((ROOT/'tests/fixtures/collections/org-browser-fixture.json').read_text())
  for b in browser['blocks']:
   if b.get('key') in ('new-episodes','ongoing','new-on-site'):
    self.assertEqual(len(p.groups[b['key']]),12)
    if b['key']=='new-episodes':self.assertEqual(p.groups[b['key']],[x['href'] for x in b['links']])
  expected=json.loads((ROOT/'tests/fixtures/collections/org-actual-proof.json').read_text())['sites'][0]['composition']['expectations']
  intake=next(x for x in expected if x['region']['value']=='new-on-site')
  self.assertEqual(p.groups['new-on-site'],intake['ordered_hrefs'])
 def sample(self):return '<section><template id="P:1"></template></section><div hidden id="S:1"><a href="/anime/a">A</a></div><script>$RS("S:1","P:1")</script>'
 def test_move(self):self.assertIn('<section><a href="/anime/a">A</a></section>',m._normalize_next_stream(self.sample()))
 def test_json_string_not_executed(self):
  with self.assertRaises(ValueError):m._normalize_next_stream(self.sample().replace('$RS("S:1","P:1")','{"value":"$RS(\\"S:1\\",\\"P:1\\")"}'))
 def test_unknown_script_context(self):
  with self.assertRaises(ValueError):m._normalize_next_stream(self.sample().replace('$RS(', 'foo();$RS('))
 def test_non_javascript_context(self):
  with self.assertRaises(ValueError):m._normalize_next_stream(self.sample().replace('<script>','<script type="application/json">'))
 def test_duplicate_ids(self):
  with self.assertRaises(ValueError):m._normalize_next_stream(self.sample()+'<i id="S:1"></i>')
 def test_duplicate_move(self):
  with self.assertRaises(ValueError):m._normalize_next_stream(self.sample().replace('</script>',';$RS("S:1","P:1")</script>'))
 def test_cycle(self):
  with self.assertRaises(ValueError):m._normalize_next_stream('<div hidden id="S:1"><template id="P:1"></template></div><script>$RS("S:1","P:1")</script>')
 def test_future_node(self):
  with self.assertRaises(ValueError):m._normalize_next_stream('<script>$RS("S:1","P:1")</script><div hidden id="S:1"></div><template id="P:1"></template>')
 def test_incomplete_boundary(self):
  with self.assertRaises(ValueError):m._normalize_next_stream('<!--$?--><template id="B:0"></template><div hidden id="S:0"></div><script>$RC("B:0","S:0")</script>')
 def test_fallback_removed(self):
  s='<!--$?--><template id="B:0"></template><b>fallback</b><!--/$--><div hidden id="S:0"><i>actual</i></div><script>$RC("B:0","S:0")</script>'
  out=m._normalize_next_stream(s);self.assertNotIn('fallback',out);self.assertIn('<i>actual</i>',out)
