import importlib.util,tempfile,pathlib,json,unittest
s=importlib.util.spec_from_file_location('prov',pathlib.Path(__file__).with_name('k2-catalog-provenance.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Provenance(unittest.TestCase):
 def test_exact_sites_report_hashes(self):
  for site in ['lords-18','lords-19','lords-20']:
   with self.subTest(site=site),tempfile.TemporaryDirectory() as t:
    p=pathlib.Path(t);box=p/'box';box.mkdir();reports=p/'reports';reports.mkdir();snap=p/'snapshot';snap.write_text('{}')
    for k,h in [('catalog','items'),('details','details')]: (box/f'{site}-{k}.json').write_text(json.dumps({'site':site,'revision':'abc',h:[1,2]}))
    report={'finished_at':'2026-11-11','snapshot':{'path':str(snap),'items':2,'id_set_checksum':'abc123'},'sites':{site:{'expected_sha256':{k:m.digest(box/f'{site}-{k}.json') for k in ['catalog','details']}}}}
    (reports/'r.json').write_text(json.dumps(report));o=m.create(box,snap,reports,site);self.assertEqual(o['files'][f'{site}-catalog.json']['count'],2)
    target=box/f'{site}-data-provenance.json';old=target.read_bytes();(box/f'{site}-catalog.json').write_text(json.dumps({'site':site,'revision':'abc','items':[1,3]}))
    with self.assertRaises(AssertionError):m.create(box,snap,reports,site)
    self.assertEqual(old,target.read_bytes())
 def test_other_site_refused(self):
  with self.assertRaises(AssertionError):m.create(None,None,None,'lords-21')
unittest.main()
