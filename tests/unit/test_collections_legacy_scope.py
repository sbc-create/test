import ast,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
source=(ROOT/'seo_operator/regular.py').read_text();tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='editorial_legacy_sites');ns={'json':json,'Path':pathlib.Path,'EDITORIAL_SITES':('animedia-01','zona-01','zona-03')};exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),fn],type_ignores=[])),'regular.py','exec'),ns)
class Test(unittest.TestCase):
 def test_only_admitted_skip_legacy(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'policy.json';p.write_text(json.dumps({'schema':'collections-refresh-bindings-v1','sites':[{'site_id':'zona-03','enabled':True}]}));self.assertEqual(ns['editorial_legacy_sites'](p),('animedia-01','zona-01'))
 def test_missing_or_malformed_preserves_scope(self):
  self.assertEqual(ns['editorial_legacy_sites'](None),ns['EDITORIAL_SITES'])
