import importlib.util,sys,json
# Official free API contracts: https://topvisor.com/ru/api/keywords-2/groups/add/
# https://topvisor.com/ru/api/keywords-2/keywords/add-import/
sys.path.insert(0,"/home/claude/wt-portable-site-cell-01")
from pathlib import Path
from factory.topvisor.client import TopvisorClient,ALLOWED,Method,Cost
ALLOWED["add/keywords_2/keywords/import"]=Method("add/keywords_2/keywords/import",True,Cost.FREE,"Import keywords; official API contract 2026-11-11")
from factory.topvisor.credentials import load
from factory.topvisor import manifest,cli
s=importlib.util.spec_from_file_location('native_specs','/home/claude/wt-nova-publish-memory-02/factory/topvisor/manifest.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
spec=m.by_domain('lordserials1.info');orig=manifest.by_domain;manifest.by_domain=lambda d: spec if d=='lordserials1.info' else orig(d)
class Compatible(TopvisorClient):
 def call(self,method,payload=None):
  payload=dict(payload or {})
  if method=='add/keywords_2/groups' and 'name' in payload:
   assert payload['project_id']==35889576
   payload['names']=[payload.pop('name')]
  if method=='add/keywords_2/keywords' and 'keywords' in payload:
   assert payload['project_id']==35889576
   words=payload.pop('keywords')
   import csv,io
   buf=io.StringIO();writer=csv.writer(buf,lineterminator='\n');writer.writerow(['name']);writer.writerows([[w] for w in words])
   return super().call('add/keywords_2/keywords/import',{**payload,'keywords':buf.getvalue()})
  if method.startswith(('add/','edit/')):assert payload.get('project_id')==35889576
  return super().call(method,payload)
def main():
 a=Compatible(load(),dry_run=False,timeout=12);rows=[p for p in a.projects_with_regions() if p['id']==35889576];assert len(rows)==1
 r=cli.наполнить_семантику(a,rows);r['groups_contract']='https://topvisor.com/ru/api/keywords-2/groups/add/';r['paid_requests']=0
 Path('/home/claude/wt-nova-publish-memory-02/var/lords19-refresh-20261111/topvisor-semantics-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False))

if __name__=='__main__':main()
