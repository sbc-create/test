import ast,json,pathlib,tempfile,types,datetime,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
class Targets(unittest.TestCase):
 def test_each_keyword_exact_and_idempotent(self):
  source=(ROOT/'automation/local/k2-bind-topvisor-targets.py').read_text();tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='site');mapping=json.loads((ROOT/'config/k2-topvisor-targets.json').read_text())['sites'];projects=[{'id':i,'url':d} for i,d in enumerate(mapping,1)];rows={p['id']:[{'id':100*p['id']+i,'name':name,'target':'','group_id':1} for i,name in enumerate(mapping[p['url']])] for p in projects};writes=[]
  class API:
   def __init__(self,*a,**kw):pass
   def call(self,method,payload):
    if method.startswith('get/'):return [dict(x) for x in rows[payload['project_id']]]
    ids=payload['filters'][0]['values'];assert len(ids)==1;assert payload['target_type']=='keywords';writes.append((payload['project_id'],ids[0]))
    for r in rows[payload['project_id']]:
     if r['id']==ids[0]:r['target']=payload['target']
  with tempfile.TemporaryDirectory() as t:
   ns={'MAP':mapping,'projects':projects,'normalize_domain':lambda x:x,'TopvisorClient':API,'load':lambda:None,'O':pathlib.Path(t),'json':json,'sys':types.SimpleNamespace(argv=['test','--apply']),'datetime':datetime,'verify':lambda u:{'url':u,'http':200,'canonical':u}}
   exec(compile(ast.Module(body=[node],type_ignores=[]),'native-target-site','exec'),ns)
   for domain in mapping:ns['site'](domain)
   self.assertEqual(len(writes),14);self.assertEqual(len(set(writes)),14)
   for domain in mapping:ns['site'](domain)
   self.assertEqual(len(writes),14)
unittest.main()
