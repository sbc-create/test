#!/usr/bin/env python3
"""Root-owned, exact lords-20 editorial receiver. No shell, paths or code in requests."""
import datetime,fcntl,hashlib,json,os,pathlib,pwd,stat,tempfile
SITE='lords-20';MAX=2*1024*1024
FIELDS={'name','original_name','poster_url','year','kind','description','seo_title','seo_description'}
INBOX=pathlib.Path('/home/k2deploy/stage/editorial-lords20')
DATA=pathlib.Path('/srv/lordserials21-cc/data')
STATE=pathlib.Path('/var/lib/k2-lords20-editorial')
class Refused(Exception):pass
def need(v,msg):
 if not v:raise Refused(msg)
def canonical(d):return (json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def strict(b):
 def unique(pairs):
  d={}
  for k,v in pairs:
   need(k not in d,'duplicate JSON key');d[k]=v
  return d
 return json.loads(b,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(Refused('nonfinite JSON')))
def directory(p):
 p=pathlib.Path(p);need(p.is_absolute(),'absolute fixed directory required')
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in p.parts[1:]:
   new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=new
  return fd
 except BaseException:os.close(fd);raise
def read_at(fd,name,absent=False):
 try:f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
 except FileNotFoundError:
  if absent:return None
  raise
 try:
  st=os.fstat(f);need(stat.S_ISREG(st.st_mode) and st.st_nlink==1,'regular single-link file required');need(st.st_size<=MAX,'file too large')
  data=b''
  while True:
   chunk=os.read(f,min(65536,MAX+1-len(data)))
   if not chunk:break
   data+=chunk;need(len(data)<=MAX,'file too large')
  return data
 finally:os.close(f)
def write_at(fd,name,body,uid,gid,mode=0o640):
 tmp='.editorial-'+os.urandom(12).hex();f=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode,dir_fd=fd)
 try:
  os.fchown(f,uid,gid)
  with os.fdopen(f,'wb',closefd=False) as out:out.write(body);out.flush();os.fsync(f)
  os.close(f);f=None;os.rename(tmp,name,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)
 finally:
  if f is not None:os.close(f)
  try:os.unlink(tmp,dir_fd=fd)
  except FileNotFoundError:pass
def validate(obj):
 need(isinstance(obj,dict) and set(obj)=={'site_id','expected_before_sha256','changed_title_id','content'},'envelope keys')
 need(obj['site_id']==SITE,'site identity')
 before=obj['expected_before_sha256'];need(before is None or isinstance(before,str) and len(before)==64 and all(c in '0123456789abcdef' for c in before),'invalid baseline digest')
 need(obj['changed_title_id'] is None or isinstance(obj['changed_title_id'],str) and 0<len(obj['changed_title_id'])<=200,'changed title identity')
 doc=obj['content'];need(isinstance(doc,dict) and set(doc)=={'schema_version','site_id','overrides'},'native document keys')
 need(type(doc['schema_version']) is int and doc['schema_version']==1 and doc['site_id']==SITE,'native document identity')
 need(isinstance(doc['overrides'],dict) and len(doc['overrides'])<=10000,'overrides shape')
 for key,row in doc['overrides'].items():
  need(isinstance(key,str) and 0<len(key)<=200 and all(ord(c)>=32 for c in key),'invalid title id')
  need(isinstance(row,dict) and set(row)=={'fields','actor','reason'},'row keys')
  need(all(isinstance(row[k],str) and 0<len(row[k])<=4096 for k in ['actor','reason']),'authorship required')
  fields=row['fields'];need(isinstance(fields,dict) and fields and set(fields)<=FIELDS,'forbidden fields')
  for k,v in fields.items():need(type(v) in (str,int) and (not isinstance(v,str) or len(v)<=100000),'field value type/size')
 return doc
def apply(inbox=INBOX,data=DATA,state=STATE,owner=None):
 fds=[directory(p) for p in (inbox,data,state)];i,d,s=fds
 try:
  lock=os.open('lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=s)
  try:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   raw=read_at(i,'pending.json',True)
   if raw is None:return {'status':'idle'}
   envelope=strict(raw);doc=validate(envelope);body=canonical(doc);request_sha=sha(canonical(envelope));current=read_at(d,'editorial-overrides.json',True);oldsha=sha(current) if current is not None else None;newsha=sha(body)
   # Root-owned receipts cannot be supplied through the writable incoming directory.
   if oldsha==newsha:status='already_applied'
   else:
    need(oldsha==envelope['expected_before_sha256'],'stale current digest')
    prior=strict(current)['overrides'] if current is not None else {}
    changed=envelope['changed_title_id'];new=doc['overrides']
    need(changed is not None,'changed title required')
    need({k:v for k,v in prior.items() if k!=changed}=={k:v for k,v in new.items() if k!=changed},'unrelated title changed')
    oldfields=prior.get(changed,{}).get('fields',{});newfields=new.get(changed,{}).get('fields',{})
    editorial={'description','seo_title','seo_description'}
    need({k:v for k,v in oldfields.items() if k not in editorial}=={k:v for k,v in newfields.items() if k not in editorial},'unrelated title fields changed')
    if current is not None:write_at(s,'previous.json',current,0 if owner is None else owner[0],0 if owner is None else owner[1],0o600)
    uid,gid=owner or (pwd.getpwnam('lordserials21-cc').pw_uid,pwd.getpwnam('lordserials21-cc').pw_gid)
    write_at(d,'editorial-overrides.json',body,uid,gid);status='applied'
   need(sha(read_at(d,'editorial-overrides.json'))==newsha,'post-write hash mismatch')
   result={'site_id':SITE,'status':status,'request_sha256':request_sha,'before_sha256':oldsha,'after_sha256':newsha,'entries':len(doc['overrides']),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
   receipt_name='receipt-'+request_sha+'.json'
   earlier=read_at(s,receipt_name,True)
   if earlier is not None:
    saved=strict(earlier)
    need(saved.get('request_sha256')==request_sha and saved.get('after_sha256')==newsha,'stored receipt mismatch')
    result=saved
   else:write_at(s,receipt_name,canonical(result),0 if owner is None else owner[0],0 if owner is None else owner[1],0o644)
   write_at(s,'latest.json',canonical(result),0 if owner is None else owner[0],0 if owner is None else owner[1],0o644)
   return result
  except BlockingIOError:return {'status':'busy'}
  except (Refused,OSError,ValueError) as e:
   failure={'site_id':SITE,'status':'refused','request_sha256':sha(raw) if 'raw' in locals() and raw is not None else None,'error':str(e),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
   write_at(s,'latest.json',canonical(failure),0 if owner is None else owner[0],0 if owner is None else owner[1],0o644)
   raise
  finally:os.close(lock)
 finally:
  for fd in fds:os.close(fd)
def inspect():
 root=pathlib.Path('/srv/lordserials21-cc');release=(root/'current').resolve()
 need(release.parent==root/'releases' and release.is_dir(),'release outside fixed root')
 cfg=json.loads((release/'config/site.json').read_text());need(cfg['site_id']==SITE and cfg['domain']=='lordserials21.cc','release identity')
 need('editorial-overrides.json' in cfg['data_contract']['user_writable'],'reader contract missing')
 reader=release/'src/editorial_overlay.py';need(reader.is_file() and not reader.is_symlink(),'runtime reader absent')
 frontend=release/'src'/pathlib.Path(cfg['entrypoint']).name
 if not frontend.is_file():frontend=release/cfg['entrypoint']
 need(frontend.is_file() and 'editorial_overlay' in frontend.read_text(),'runtime consumer not wired')
 d=directory(DATA)
 try:body=read_at(d,'editorial-overrides.json',True)
 finally:os.close(d)
 d=directory(DATA);h=hashlib.sha256()
 try:
  fd=os.open('lords-20-details.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=d)
  with os.fdopen(fd,'rb') as f:
   st=os.fstat(f.fileno());need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size<180*1024*1024,'invalid fact snapshot')
   for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 finally:os.close(d)
 import urllib.request
 with urllib.request.urlopen('http://127.0.0.1:9138/healthz',timeout=10) as response:health=json.loads(response.read())
 need(health.get('runtime_digest_match') is True,'running code digest mismatch')
 need(pathlib.Path(health.get('runtime_path','')).resolve()==frontend.resolve(),'running code differs from current release')
 need(str(health.get('runtime_commit','')).startswith(release.name),'running commit mismatch')
 return {'runtime_commit':health['runtime_commit'],'runtime_digest_match':True,'site_id':SITE,'domain':'lordserials21.cc','release':release.name,'reader_sha256':sha(reader.read_bytes()),'contract_verified':True,'details_sha256':h.hexdigest(),'overlay_sha256':sha(body) if body else None,'overlay':strict(body) if body else None}

def publish_state():
 # Only public editorial facts leave the private application data directory.
 info=inspect();d=directory(DATA);s=directory(STATE)
 try:
  old=read_at(s,'inspection.json',True)
  previous=strict(old) if old else {}
  if previous.get('details_sha256')!=info['details_sha256'] or not (STATE/'lords-20-details.json').is_file():
   f=os.open('lords-20-details.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=d)
   with os.fdopen(f,'rb') as stream:
    st=os.fstat(stream.fileno());need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size<180*1024*1024,'invalid public facts')
    body=stream.read(180*1024*1024)
   need(sha(body)==info['details_sha256'],'facts changed during export')
   write_at(s,'lords-20-details.json',body,0,0,0o644)
  info['inspected_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  write_at(s,'inspection.json',canonical(info),0,0,0o644)
 finally:os.close(d);os.close(s)
 return info

if __name__=='__main__':
 try:
  import sys
  need(sys.argv[1:] in ([],['--inspect']),'unsupported arguments')
  if sys.argv[1:]:
   fd=directory(STATE)
   try:result=strict(read_at(fd,'inspection.json'))
   finally:os.close(fd)
  else:
   need(os.geteuid()==0,'root receiver required')
   try:result=apply()
   finally:publish_state()
  print(json.dumps(result))
 except (Refused,OSError,ValueError) as e:print(json.dumps({'status':'refused','error':str(e)}));raise SystemExit(1)
