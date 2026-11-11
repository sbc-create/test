import sys,json,datetime,urllib.request,concurrent.futures
from pathlib import Path
from html.parser import HTMLParser
sys.path.insert(0,'/home/claude/wt-portable-site-cell-01')
from factory.topvisor.client import TopvisorClient,ALLOWED,Method,Cost
from factory.topvisor.credentials import load
from factory.topvisor.plan import normalize_domain
O=Path(__file__).resolve().parents[2]/'var/topvisor-target-bindings'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');O.mkdir(parents=True,exist_ok=False)
MAP=json.loads((Path(__file__).resolve().parents[2]/'config/k2-topvisor-targets.json').read_text())['sites']
assert set(MAP)=={'lordserials1.cc','lordserials1.info','lordserials21.cc'}
class Canon(HTMLParser):
 def __init__(self):super().__init__();self.c=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='link' and a.get('rel')=='canonical':self.c.append(a.get('href'))
def verify(url):
 with urllib.request.urlopen(url,timeout=20) as r:
  c=Canon();c.feed(r.read().decode());assert r.status==200 and r.url==url and c.c==[url],(url,r.status,r.url,c.c)
 return {'url':url,'http':200,'canonical':url,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
a=TopvisorClient(load(),timeout=12,dry_run='--apply' not in sys.argv);projects=a.projects_with_regions();receipts=[]
ALLOWED['edit/keywords_2/keywords/target']=Method('edit/keywords_2/keywords/target',True,Cost.FREE,'Documented target-URL metadata edit; no rank check')
def site(domain):
 api=TopvisorClient(load(),timeout=12,dry_run='--apply' not in sys.argv)
 rows=[p for p in projects if normalize_domain(p.get('url',''))==domain];assert len(rows)==1;pid=rows[0]['id']
 targets=MAP[domain];before=api.call('get/keywords_2/keywords',{'project_id':pid,'fields':['id','name','target','group_id'],'limit':1000});assert {r['name'] for r in before}==set(targets)
 proof={path:verify('https://'+domain+path) for path in set(targets.values())}
 plan={'domain':domain,'project_id':pid,'before':before,'public_proofs':proof,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'apply':'--apply' in sys.argv,'method_source':'https://topvisor.com/ru/api/keywords-2/keywords/edit-target/','paid_requests':0}
 (O/(domain+'-targets-plan.json')).write_text(json.dumps(plan,ensure_ascii=False,indent=2))
 for path in set(targets.values()):
  ids=[r['id'] for r in before if targets[r['name']]==path and r.get('target')!='https://'+domain+path]
  for keyword_id in ids:api.call('edit/keywords_2/keywords/target',{'project_id':pid,'target':'https://'+domain+path,'target_type':'keywords','filters':[{'name':'id','operator':'EQUALS','values':[keyword_id]}]})
 after=api.call('get/keywords_2/keywords',{'project_id':pid,'fields':['id','name','target','group_id'],'limit':1000})
 if '--apply' in sys.argv:assert all(r['target']=='https://'+domain+targets[r['name']] for r in after)
 plan['after']=after;plan['result']='applied_verified' if '--apply' in sys.argv else 'dry_run';(O/(domain+'-targets-result.json')).write_text(json.dumps(plan,ensure_ascii=False,indent=2));print(domain,plan['result'],len(after),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(site,MAP))
