#!/usr/bin/env python3
"""Attach verified direct-publisher provenance to explicit lords-18/lords-19/lords-20 delivery only."""
import argparse,datetime,hashlib,json,pathlib

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def create(box,snapshot,reports,site='lords-19'):
 assert site in {'lords-18','lords-19','lords-20'},'provenance site outside approved scope'
 files={};revisions=[]
 for kind,holder in [('catalog','items'),('details','details')]:
  p=box/f'{site}-{kind}.json';d=json.loads(p.read_text());assert d.get('site')==site
  rev=d.get('catalog_revision') or d.get('revision');assert rev
  revisions.append(rev);files[kind]={'result_sha256':digest(p),'count':len(d[holder]),'catalog_revision':rev}
 assert len(set(revisions))==1 and files['catalog']['count']==files['details']['count']
 matches=[]
 for p in reports.glob('*.json'):
  d=json.loads(p.read_text());row=d.get('sites',{}).get(site,{})
  if row.get('expected_sha256')=={k:v['result_sha256'] for k,v in files.items()}:matches.append((d.get('finished_at',''),p,d,row))
 assert matches,'No publisher report matches delivered digests'
 _,report,d,row=max(matches,key=lambda x:x[0]);snap=d['snapshot'];assert pathlib.Path(snap['path']).resolve()==snapshot.resolve()
 assert snap['items']==files['catalog']['count'] and snap['id_set_checksum'].startswith(revisions[0])
 out={'site':site,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tool':'automation/local/k2-catalog-provenance.py','method':'direct-native-publisher','publish_finished_at':d['finished_at'],'publisher_report':str(report),'publisher_report_sha256':digest(report),'snapshot':snap,'snapshot_sha256_observed_at_pack':digest(snapshot),'files':{f'{site}-{k}.json':v for k,v in files.items()}}
 target=box/f'{site}-data-provenance.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');tmp.replace(target)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--site',choices=['lords-18','lords-19','lords-20'],default='lords-19');p.add_argument('--box',required=True,type=pathlib.Path);p.add_argument('--snapshot',required=True,type=pathlib.Path);p.add_argument('--reports',required=True,type=pathlib.Path);a=p.parse_args();o=create(a.box,a.snapshot,a.reports,a.site);print(a.site+' provenance: publisher report digests/revision/count verified')
