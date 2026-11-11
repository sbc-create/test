import importlib.util,tempfile,pathlib,json
s=importlib.util.spec_from_file_location('prov',str(pathlib.Path(__file__).with_name('k2-catalog-provenance.py')));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t);box=p/'box';box.mkdir();reports=p/'reports';reports.mkdir();snap=p/'snapshot';snap.write_text('{}')
 for k,h in [('catalog','items'),('details','details')]: (box/f'lords-19-{k}.json').write_text(json.dumps({'site':'lords-19','revision':'abc',h:[1,2]}))
 report={'finished_at':'2026-11-11','snapshot':{'path':str(snap),'items':2,'id_set_checksum':'abc123'},'sites':{'lords-19':{'expected_sha256':{k:m.digest(box/f'lords-19-{k}.json') for k in ['catalog','details']}}}}
 (reports/'r.json').write_text(json.dumps(report));o=m.create(box,snap,reports);assert o['files']['lords-19-catalog.json']['count']==2
 target=box/'lords-19-data-provenance.json';old=target.read_bytes();(box/'lords-19-catalog.json').write_text(json.dumps({'site':'lords-19','revision':'abc','items':[1,3]}))
 try:m.create(box,snap,reports)
 except AssertionError:pass
 else:raise AssertionError('digest mismatch accepted')
 assert old==target.read_bytes()
 print('PASS matching report; reject mismatched digest; preserve prior provenance')
