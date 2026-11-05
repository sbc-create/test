"""Isolated protocol/filesystem tests. Native functions are not monkeypatched."""
from dataclasses import asdict
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest

from factory.cell import executor,queue,registry,privileged
from factory.cell.remote_apply import VERSION,fingerprint,transact,unpack_capsule,validate_binding,exclusive
from factory.cell.rollback_state import capture,restore


_REQUEST=asdict(queue.собрать('lords-02','a'*40,'sha256:'+'b'*64,ci_run='123',repo='https://github.com/sbc-create/site-lordserial33-biz.git'))

def request():
    return queue.разобрать(dict(_REQUEST))


def profile():
    return {'package_sha256':'c'*64,'cell':{'site_id':'lords-02','domain':'lordserial33.biz',
        'repo':{'remote':'https://github.com/sbc-create/site-lordserial33-biz.git','path':'/unused'},
        'runtime':{'code_delivery':{'role':'local-ssh-bridge'},'account':'nobody','unit':'fixture.service','port':9111,'data_dir':'/unused'}},
        'target':{'host':'127.0.0.1','catalog':'/unused/lords-02-catalog.json'}}


def binding():
    return {'schema':VERSION,'nonce':'d'*64,'request':asdict(request()),'request_sha256':'e'*64,
        'profile_sha256':fingerprint(profile()),'package_sha256':'c'*64,'capsule_sha256':'f'*64,'expected_old_commit':'1'*40}


class Backend:
    def __init__(self):self.current=False;self.applied=0;self.checked=0;self.recovered=0;self.fail=False
    def is_current(self,r):return self.current
    def preflight(self,r,old,p):
        if self.current:raise AssertionError('Old-current checked before successful replay')
        self.checked+=1
    def activate(self,r):
        self.applied+=1
        if self.fail:raise RuntimeError('simulated post-promote failure')
        self.current=True
        return {'status':'activated','stage':'live_verified','build_id':'fixture','digest':r.digest,'steps':{'native':True}}
    def verify_replay(self,r,out):
        if not self.current:raise ValueError('active runtime drift')
    def reconcile(self,r):return {'status':'activated','stage':'live_verified','build_id':'fixture','steps':{'reconciled':True}}
    def recover(self,r):self.recovered+=1;self.current=False;return {'restored_previous':True}


class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_success_and_lost_ack_replay_never_reinstall(self):
        b=Backend();first=transact(binding(),profile(),b,state_root=self.root)
        # ACK is intentionally dropped; old-current is now different.
        second=transact(binding(),profile(),b,state_root=self.root)
        self.assertEqual(first,second);self.assertEqual(b.applied,1);self.assertEqual(b.checked,1)
    def test_replay_verifies_actual_runtime(self):
        b=Backend();transact(binding(),profile(),b,state_root=self.root);b.current=False
        with self.assertRaises(ValueError):transact(binding(),profile(),b,state_root=self.root)
        self.assertEqual(b.applied,1)
    def test_matching_in_progress_current_reconciles_without_install(self):
        b=Backend();b.current=True
        (self.root/('d'*64+'.json')).write_text(json.dumps({'binding':binding(),'outcome':None}))
        result=transact(binding(),profile(),b,state_root=self.root)
        self.assertTrue(result['steps']['reconciled']);self.assertEqual(b.applied,0)
    def test_missing_receipt_active_release_refuses_reinstall(self):
        b=Backend();b.current=True
        with self.assertRaises(ValueError):transact(binding(),profile(),b,state_root=self.root)
        self.assertEqual(b.applied,0)
    def test_post_promote_failure_returns_full_failure_and_recovery(self):
        b=Backend();b.fail=True
        out=transact(binding(),profile(),b,state_root=self.root)
        self.assertEqual(out['status'],'failed');self.assertEqual(b.recovered,1)
        self.assertEqual(transact(binding(),profile(),b,state_root=self.root),out)
        self.assertEqual(b.applied,1)
    def test_wrong_site_rejected_before_preflight(self):
        b=Backend();value=binding();value['request']['site_id']='zona-02'
        with self.assertRaises(Exception):transact(value,profile(),b,state_root=self.root)
        self.assertEqual(b.checked,0);self.assertEqual(b.applied,0)
    def test_wrong_package_profile_and_digest_binding(self):
        for key in ['profile_sha256','package_sha256']:
            b=Backend();value=binding();value[key]='0'*64
            with self.assertRaises(ValueError):transact(value,profile(),b,state_root=self.root)
            self.assertEqual(b.applied,0)
        b=Backend();transact(binding(),profile(),b,state_root=self.root)
        value=binding();value['request']['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):transact(value,profile(),b,state_root=self.root)
        self.assertEqual(b.applied,1)
    def test_closed_method_and_payload_schema(self):
        value=binding();value['command']='arbitrary'
        with self.assertRaises(ValueError):validate_binding(value,profile())
    def test_source_capsule_digest_and_traversal_guards(self):
        path=self.root/'bad.tar'
        with tarfile.open(path,'w') as tar:
            x=tarfile.TarInfo('../escape');x.size=1;tar.addfile(x,io.BytesIO(b'x'))
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):unpack_capsule(path,self.root/'payload',digest)
        with self.assertRaises(ValueError):unpack_capsule(path,self.root/'other','0'*64)
        self.assertFalse((self.root.parent/'escape').exists())
    def test_candidate_lock_rejects_concurrent_transaction(self):
        with exclusive(self.root/'.candidate.lock'):
            with self.assertRaises(BlockingIOError):transact(binding(),profile(),Backend(),state_root=self.root)


class NativeRollback(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        r=self.root/'site';releases=r/'releases';old=releases/'old';new=releases/'new';old.mkdir(parents=True);new.mkdir()
        (r/'current').symlink_to(old);(r/'candidate').symlink_to(new)
        self.p=SimpleNamespace(site_id='lords-02',unit='main.service',previous_unit=None,root=r,releases=releases,current=r/'current',candidate=r/'candidate')
        self.units=self.root/'units';self.units.mkdir();self.route=self.root/'upstreams';self.route.mkdir()
        for name in ['main.service','update.service','update.timer']:(self.units/name).write_text('old '+name)
        (self.route/'lords-02.upstream').write_text('server 127.0.0.1:9111;\n')
        self.data=r/'data';self.data.mkdir();(self.data/'editorial-overrides.json').write_text('protected user value')
        self.calls=[]
        def systemctl(*args,**kw):
            self.calls.append(args);return SimpleNamespace(returncode=0 if args[0] in ['is-active','is-enabled'] else 0)
        self.systemctl=systemctl;self.updater=SimpleNamespace(service='update.service',timer='update.timer');self.state=self.root/'state'
    def test_post_promote_restores_current_main_updater_route_no_previous_unit(self):
        capture(self.p,self.units,self.route,self.updater,self.systemctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        self.p.current.unlink();self.p.current.symlink_to(self.p.candidate.resolve())
        for f in self.units.iterdir():f.write_text('new')
        (self.route/'lords-02.upstream').write_text('server 127.0.0.1:9999;')
        out=restore(self.p,self.units,self.route,self.systemctl,wait_ready=lambda build:{'ok':True,'build_id':build},state_root=self.state)
        self.assertEqual(self.p.current.resolve().name,'old')
        self.assertEqual((self.units/'main.service').read_text(),'old main.service')
        self.assertEqual((self.units/'update.timer').read_text(),'old update.timer')
        self.assertEqual((self.route/'lords-02.upstream').read_text(),'server 127.0.0.1:9111;\n')
        self.assertEqual((self.data/'editorial-overrides.json').read_text(),'protected user value')
        self.assertIn(('restart','main.service'),self.calls);self.assertIn('update.service',out['restored_units'])
    def test_dropins_and_previous_mask_restored(self):
        self.p.previous_unit='previous.service'
        previous=self.units/'previous.service';previous.symlink_to('/dev/null')
        old=self.units/'update.service.d';old.mkdir();(old/'override.conf').write_text('old override')
        capture(self.p,self.units,self.route,self.updater,self.systemctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        previous.unlink();previous.write_text('new unmasked unit')
        (old/'override.conf').write_text('new override');(old/'new.conf').write_text('new')
        added=self.units/'previous.service.d';added.mkdir();(added/'cell-port-owner.conf').write_text('RefuseManualStart=yes')
        restore(self.p,self.units,self.route,self.systemctl,wait_ready=lambda build:{'ok':True,'build_id':build},state_root=self.state)
        self.assertTrue(previous.is_symlink());self.assertEqual(os.readlink(previous),'/dev/null')
        self.assertEqual((old/'override.conf').read_text(),'old override');self.assertFalse((old/'new.conf').exists())
        self.assertFalse(added.exists())
    def test_exact_enable_links_restored(self):
        directory=self.units/'timers.target.wants';directory.mkdir()
        (directory/'update.timer').symlink_to('../update.timer')
        capture(self.p,self.units,self.route,self.updater,self.systemctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        (directory/'update.timer').unlink()
        new=self.units/'multi-user.target.wants';new.mkdir();(new/'update.timer').symlink_to('../update.timer')
        restore(self.p,self.units,self.route,self.systemctl,wait_ready=lambda build:{'ok':True,'build_id':build},state_root=self.state)
        self.assertEqual(os.readlink(directory/'update.timer'),'../update.timer')
        self.assertFalse((new/'update.timer').is_symlink())
    def test_unrelated_candidate_cannot_use_old_checkpoint(self):
        capture(self.p,self.units,self.route,self.updater,self.systemctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        other=self.p.releases/'other';other.mkdir();self.p.candidate.unlink();self.p.candidate.symlink_to(other)
        self.assertIsNone(restore(self.p,self.units,self.route,self.systemctl,wait_ready=lambda build:{'ok':True,'build_id':build},state_root=self.state))
        self.assertEqual(self.p.current.resolve().name,'old')


def lock_owner(path,ready,release):
    lock=executor.взять_замок('lords-02',база=Path(path),операция='activate');ready.set();release.wait(10);lock.снять()


class NativeControl(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        cell=profile()['cell'];self.projection=self.root/'registry.json';self.projection.write_text(json.dumps({'cells':[cell]}));self.projection.chmod(0o400)
        self.req=request();self.file=self.root/'requests'/(self.req.request_id+'.json');self.file.parent.mkdir();self.file.write_text(json.dumps(asdict(self.req)))
        self.bin=self.root/'bin';self.bin.mkdir();gh=self.bin/'gh'
        gh.write_text('#!/usr/bin/python3\nimport os,json\nprint(json.dumps({"headSha":"'+self.req.commit+'","headBranch":"claude/extract-fixture","conclusion":os.environ.get("K2_TEST_CI","failure"),"status":"completed","databaseId":123}))\n');gh.chmod(0o755)
        self.old_path=os.environ['PATH'];os.environ['PATH']=str(self.bin)+os.pathsep+self.old_path
        self.addCleanup(os.environ.__setitem__,'PATH',self.old_path)
        os.environ['GH_TOKEN']='isolated-fixture';self.addCleanup(os.environ.pop,'GH_TOKEN',None)
    def test_ci_rejected_before_any_rpc_handler(self):
        called=[]
        with registry.scoped_projection(self.projection,'lords-02'):
            out=executor.выполнить(self.req,база=self.root,dry_run=False,activate_handler=lambda *a,**kw:called.append(True))
        self.assertEqual(out['status'],'rejected');self.assertEqual(called,[])
    def test_normal_consumer_keeps_remote_request_untouched(self):
        before=self.file.read_bytes()
        with registry.scoped_projection(self.projection,'lords-02'):
            out=executor.обслужить_очередь(база=self.root,dry_run=False)
        self.assertEqual(out[0]['status'],'waiting-bridge');self.assertEqual(self.file.read_bytes(),before)
        self.assertFalse((self.root/'results').exists())
    def test_uncertain_rpc_keeps_request_reconcilable(self):
        os.environ['K2_TEST_CI']='success';self.addCleanup(os.environ.pop,'K2_TEST_CI',None)
        def handler(*a,**kw):raise executor.BridgeUncertain('lost ACK')
        with registry.scoped_projection(self.projection,'lords-02'):
            out=executor.выполнить(self.req,база=self.root,dry_run=False,activate_handler=handler)
        self.assertEqual(out['status'],'reconcile');self.assertTrue(self.file.exists())
    def test_updater_failed_native_outcome_is_not_success(self):
        os.environ['K2_TEST_CI']='success';self.addCleanup(os.environ.pop,'K2_TEST_CI',None)
        def handler(*a,**kw):return {'status':'activated','stage':'updater_failed','steps':{'native':True}}
        with registry.scoped_projection(self.projection,'lords-02'):
            out=executor.выполнить(self.req,база=self.root,dry_run=False,activate_handler=handler)
        self.assertEqual(out['status'],'failed');self.assertEqual(out['outcome']['stage'],'updater_failed')
    def test_real_native_pid_lock_is_exclusive_across_processes(self):
        context=multiprocessing.get_context('fork');ready=context.Event();release=context.Event()
        child=context.Process(target=lock_owner,args=(str(self.root),ready,release));child.start()
        try:
            self.assertTrue(ready.wait(5))
            with self.assertRaises(executor.SiteBusy):executor.взять_замок('lords-02',база=self.root,операция='activate')
        finally:release.set();child.join(5)
        self.assertEqual(child.exitcode,0)
        lock=executor.взять_замок('lords-02',база=self.root,операция='activate');lock.снять()
    def test_writable_or_wrong_site_projection_rejected(self):
        self.projection.chmod(0o600)
        with self.assertRaises(registry.RegistryError):
            with registry.scoped_projection(self.projection,'lords-02'):pass
        self.projection.chmod(0o400)
        with self.assertRaises(registry.RegistryError):
            with registry.scoped_projection(self.projection,'zona-02'):pass


if __name__=='__main__':unittest.main()

class PackageIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'factory').mkdir();self.file=self.root/'factory/a.py';self.file.write_text('value=1\n');self.file.chmod(0o444)
        from factory.cell.remote_package import identity
        files={'factory/a.py':hashlib.sha256(self.file.read_bytes()).hexdigest()}
        self.meta={'schema':VERSION,'files':files,'package_sha256':identity(files)}
    def test_exact_readonly_package(self):
        from factory.cell.remote_package import verify
        self.assertEqual(verify(self.root,self.meta),self.meta['package_sha256'])
    def test_changed_or_extra_module_rejected(self):
        from factory.cell.remote_package import verify
        self.file.chmod(0o644)
        with self.assertRaises(PermissionError):verify(self.root,self.meta)
        self.file.write_text('value=2\n');self.file.chmod(0o444)
        with self.assertRaises(ValueError):verify(self.root,self.meta)
        self.file.chmod(0o644);self.file.write_text('value=1\n');self.file.chmod(0o444)
        (self.root/'factory/extra.py').write_text('')
        with self.assertRaises(ValueError):verify(self.root,self.meta)
    def test_symlink_and_identity_change_rejected(self):
        from factory.cell.remote_package import verify
        self.file.unlink();self.file.symlink_to('/etc/hosts')
        with self.assertRaises(PermissionError):verify(self.root,self.meta)
        self.meta['package_sha256']='0'*64
        with self.assertRaises(ValueError):verify(self.root,self.meta)

class ExactSourceProof(unittest.TestCase):
    def setUp(self):
        from dataclasses import replace
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        base=self.root/'base';base.mkdir()
        def run(*args):return subprocess.check_output(['git',*args],stderr=subprocess.DEVNULL,text=True).strip()
        run('init','-q',str(base));(base/'build.py').write_text('print("accepted")\n')
        (base/'.gitignore').write_text('ignored.py\n')
        run('-C',str(base),'add','.');run('-C',str(base),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture')
        self.source=self.root/'source';run('clone','-q','--depth=1','file://'+str(base),str(self.source))
        branch=run('-C',str(self.source),'symbolic-ref','--short','HEAD');run('-C',str(self.source),'config','--remove-section','branch.'+branch)
        self.remote='https://github.com/sbc-create/fixture.git';run('-C',str(self.source),'remote','set-url','origin',self.remote)
        self.request=replace(request(),commit=run('-C',str(self.source),'rev-parse','HEAD'));self.git=lambda *args:run('-C',str(self.source),*args)
    def validate(self):
        from factory.cell.remote_capsule import validate_source
        return validate_source(self.source,self.request,self.remote)
    def test_clean_shallow_source_proves(self):self.validate()
    def test_assume_unchanged_cannot_hide_modified_builder(self):
        self.git('update-index','--assume-unchanged','build.py');(self.source/'build.py').write_text('print("tampered")\n')
        self.assertEqual(self.git('status','--porcelain'),'')
        with self.assertRaises(ValueError):self.validate()
    def test_ignored_and_info_excluded_files_rejected(self):
        (self.source/'ignored.py').write_text('malicious=True\n')
        self.assertEqual(self.git('status','--porcelain'),'')
        with self.assertRaises(ValueError):self.validate()
        (self.source/'ignored.py').unlink();(self.source/'.git/info/exclude').write_text('hidden.py\n')
        (self.source/'hidden.py').write_text('malicious=True\n')
        with self.assertRaises(ValueError):self.validate()
    def test_executable_mode_change_rejected(self):
        (self.source/'build.py').chmod(0o755)
        with self.assertRaises(ValueError):self.validate()
    def test_git_indirection_rejected(self):
        for name in ['commondir','info/grafts','refs/replace','objects/info/alternates']:
            path=self.source/'.git'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('')
            with self.assertRaises(ValueError):self.validate()
            path.unlink()


class GatewayIdentity(unittest.TestCase):
    def test_native_journal_changes_do_not_change_release_binding(self):
        from dataclasses import replace
        from factory.cell.remote_gateway import immutable_request
        original=request();retry=replace(original,stages=[{'stage':'validated','at':'fixture'}])
        self.assertEqual(immutable_request(original),immutable_request(retry))
        self.assertNotEqual(immutable_request(original),immutable_request(replace(retry,digest='sha256:'+'0'*64)))

class RollbackReadiness(NativeRollback):
    def test_delayed_old_build_keeps_candidate_route(self):
        from factory.cell.rollback_state import wait_for_build
        capture(self.p,self.units,self.route,self.updater,self.systemctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        route=self.route/'lords-02.upstream';route.write_text('server 127.0.0.1:10111;')
        self.p.current.unlink();self.p.current.symlink_to(self.p.candidate.resolve())
        replies=iter([{'ok':False},{'ok':True,'build_id':'WRONG'},{'ok':True,'build_id':'old-fixture'}]);calls=[]
        def probe():
            self.assertEqual(route.read_text(),'server 127.0.0.1:10111;')
            self.assertTrue(self.p.candidate.exists());calls.append(True);return next(replies)
        def ready(build):return wait_for_build(probe,build,timeout=10,interval=0,sleep=lambda _:None)
        restore(self.p,self.units,self.route,self.systemctl,wait_ready=ready,state_root=self.state)
        self.assertEqual(len(calls),3);self.assertEqual(route.read_text(),'server 127.0.0.1:9111;\n')
    def test_wrong_old_build_retains_route_and_pending_checkpoint(self):
        capture(self.p,self.units,self.route,self.updater,self.systemctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        route=self.route/'lords-02.upstream';route.write_text('candidate still serving')
        with self.assertRaises(ValueError):restore(self.p,self.units,self.route,self.systemctl,wait_ready=lambda _: {'ok':True,'build_id':'wrong'},state_root=self.state)
        self.assertEqual(route.read_text(),'candidate still serving')
        self.assertEqual(json.loads((self.state/'lords-02.json').read_text())['phase'],'waiting_old_http')
    def test_previous_restart_enforces_mask_and_refuse_manual_start(self):
        self.p.previous_unit='previous.service'
        previous=self.units/'previous.service';previous.write_text('old previous unit')
        restarted=[]
        def ctl(*args,**kw):
            if args[0]=='restart':
                name=args[-1];unit=self.units/name;drop=self.units/(name+'.d')
                if unit.is_symlink() and os.readlink(unit)=='/dev/null':raise RuntimeError('unit masked')
                if drop.is_dir() and any('RefuseManualStart=yes' in p.read_text() for p in drop.glob('*.conf')):
                    raise RuntimeError('manual start refused')
                restarted.append(name)
            return SimpleNamespace(returncode=0)
        capture(self.p,self.units,self.route,self.updater,ctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        previous.unlink();previous.symlink_to('/dev/null')
        drop=self.units/'previous.service.d';drop.mkdir();(drop/'cell-port-owner.conf').write_text('RefuseManualStart=yes')
        restore(self.p,self.units,self.route,ctl,wait_ready=lambda build:{'ok':True,'build_id':build},state_root=self.state)
        self.assertIn('previous.service',restarted);self.assertFalse(drop.exists())
    def test_absent_unit_stop_before_remove_nonzero_tolerated(self):
        self.p.previous_unit='previous.service';calls=[]
        def ctl(*args,**kw):
            calls.append(args)
            if args[0] in ['is-active','is-enabled'] and args[-1]=='previous.service':return SimpleNamespace(returncode=4)
            if args[0]=='stop' and args[-1]=='previous.service':
                self.assertFalse(kw.get('проверять',True));return SimpleNamespace(returncode=5)
            if args[0]=='restart' and args[-1]=='previous.service':raise AssertionError('Absent inactive unit must not restart')
            return SimpleNamespace(returncode=0)
        capture(self.p,self.units,self.route,self.updater,ctl,old_build_id='old-fixture',new_build_id='new-fixture',state_root=self.state)
        new=self.units/'previous.service';new.write_text('newly created unit')
        drop=self.units/'previous.service.d';drop.mkdir();(drop/'cell-port-owner.conf').write_text('RefuseManualStart=yes')
        restore(self.p,self.units,self.route,ctl,wait_ready=lambda build:{'ok':True,'build_id':build},state_root=self.state)
        self.assertFalse(new.exists());self.assertFalse(drop.exists());self.assertIn(('stop','previous.service'),calls)


class CapsuleHeaderBudget(unittest.TestCase):
    def check_bad(self,data):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'bad.tar';path.write_bytes(data)
            with self.assertRaises(ValueError):unpack_capsule(path,root/'out',hashlib.sha256(data).hexdigest())
            self.assertFalse(any((root/'out').rglob('*')))
    def test_incremental_member_limit_before_extraction(self):
        headers=[]
        for n in range(20001):headers.append(tarfile.TarInfo('source/dir'+str(n)).tobuf(format=tarfile.USTAR_FORMAT))
        self.check_bad(b''.join(headers)+b'\0'*1024)
    def test_pax_longname_sparse_metadata_rejected_at_header(self):
        for kind in [b'x',b'g',b'L',b'K',b'S']:
            info=tarfile.TarInfo('source/metadata');info.type=kind;info.size=32*1024*1024
            self.check_bad(info.tobuf(format=tarfile.USTAR_FORMAT)+b'\0'*1024)

class GatewayRoundTrip(NativeControl):
    def configure_gateway(self):
        from factory.cell.remote_gateway import immutable_request
        p=profile();cell=json.loads(json.dumps(p['cell']))
        cell['runtime']['code_delivery']={'role':'local-ssh-bridge','expected_current':'1'*40,'profile':p}
        self.projection.chmod(0o600);self.projection.write_text(json.dumps({'cells':[cell]}));self.projection.chmod(0o400)
        for name in ['state','packages']:(self.root/name).mkdir(exist_ok=True)
        data=b'fixture frozen source capsule';cached=self.root/'packages'/(self.req.request_id+'.source.tar.gz');cached.write_bytes(data);cached.chmod(0o400)
        raw=self.file.read_bytes()
        saved={'stable':{'request':immutable_request(self.req),'profile_sha256':fingerprint(p),'package_sha256':p['package_sha256'],'expected_old_commit':'1'*40},'nonce':'d'*64,'request_sha256':hashlib.sha256(raw).hexdigest(),'original_request_utf8':raw.decode(),'capsule_sha256':hashlib.sha256(data).hexdigest()}
        (self.root/'state'/(self.req.request_id+'.remote.json')).write_text(json.dumps(saved))
        return p
    def process(self,request_id=None):
        env=dict(os.environ,SITE_CELL_QUEUE=str(self.root),SITE_CELLS_REGISTRY=str(self.projection),K2_TEST_CI='success',PYTHONDONTWRITEBYTECODE='1')
        child=subprocess.Popen(['/usr/bin/python3','-m','factory.cell.remote_gateway','--request',request_id or self.req.request_id],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        def finish():
            if child.poll() is None:child.kill();child.wait()
            for pipe in [child.stdin,child.stdout,child.stderr]:
                if pipe and not pipe.closed:pipe.close()
        self.addCleanup(finish)
        return child
    def test_full_control_journal_lost_ack_retry_installs_once(self):
        from factory.cell.remote_gateway import read_packet,packet
        p=self.configure_gateway();backend=Backend();receipts=self.root/'target-receipts'
        first=self.process();header=read_packet(first.stdout)
        self.assertEqual(header['method'],'активировать');first.stdout.read(header['bytes'])
        outcome=transact(header['binding'],p,backend,state_root=receipts)
        # Target receipt is durable, but the ACK never reaches CONTROL.
        first.stdin.close();result=read_packet(first.stdout);self.assertEqual(first.wait(timeout=5),0,first.stderr.read())
        self.assertEqual(result['result']['status'],'reconcile');self.assertTrue(self.file.exists())
        self.assertTrue(json.loads(self.file.read_text())['stages']);self.assertFalse((self.root/'results'/self.file.name).exists())
        second=self.process();replay=read_packet(second.stdout);second.stdout.read(replay['bytes'])
        self.assertEqual(header['binding'],replay['binding'])
        repeated=transact(replay['binding'],p,backend,state_root=receipts)
        packet(second.stdin,{'nonce':replay['binding']['nonce'],'binding_sha256':fingerprint(replay['binding']),'outcome':repeated})
        final=read_packet(second.stdout);self.assertEqual(second.wait(timeout=5),0,second.stderr.read())
        self.assertEqual(final['result']['status'],'ok');self.assertEqual(final['result']['outcome'],outcome)
        self.assertEqual(backend.applied,1);self.assertFalse(self.file.exists())
        self.assertEqual(json.loads((self.root/'results'/self.file.name).read_text())['outcome'],outcome)
    def test_cross_site_gateway_claim_contention_retains_both_requests(self):
        from dataclasses import replace
        from factory.cell.remote_gateway import read_packet
        self.configure_gateway();cells=json.loads(self.projection.read_text())['cells'];second=json.loads(json.dumps(cells[0]));second['site_id']='lords-03';second['domain']='fixture.example';second['runtime']['port']=9112
        second['runtime']['code_delivery']['profile']['cell']['site_id']='lords-03';cells.append(second)
        self.projection.chmod(0o600);self.projection.write_text(json.dumps({'cells':cells}));self.projection.chmod(0o400)
        req2=replace(self.req,site_id='lords-03',request_id='lords-03-'+self.req.commit[:12]);file2=self.root/'requests'/(req2.request_id+'.json');file2.write_text(json.dumps(asdict(req2)))
        guard=self.root/'locks'/'local-ssh-bridge.guard'
        with exclusive(guard):
            children=[self.process(),self.process(req2.request_id)]
            for child in children:
                response=read_packet(child.stdout);self.assertEqual(response['result']['status'],'busy')
                self.assertEqual(child.wait(timeout=5),0,child.stderr.read())
        self.assertTrue(self.file.exists());self.assertTrue(file2.exists());self.assertFalse((self.root/'results').exists())


class CredentialRole(unittest.TestCase):
    def test_relay_uses_pinned_transient_native_credential_role_without_pty(self):
        import importlib.util
        path=Path(__file__).resolve().parents[2]/'automation/local/cell-remote-bridge.py'
        spec=importlib.util.spec_from_file_location('isolated_relay',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        command=module.gateway_command('a'*64,'fixture-request')
        self.assertEqual(command[0],'systemd-run');self.assertIn('--pipe',command);self.assertNotIn('--pty',command)
        self.assertIn('LoadCredential=gh-token:/etc/site-factory/gh-token',command)
        self.assertIn('ProtectHome=read-only',command);self.assertIn('/'+'a'*64+'/',command[-3])
        with self.assertRaises(ValueError):module.gateway_command('current','fixture-request')

class KillDuringReceipt(unittest.TestCase):
    def test_sigkill_after_activation_reconciles_without_second_install(self):
        import signal
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);current=root/'current.json';ready=multiprocessing.Event();release=multiprocessing.Event()
            class PersistentBackend(Backend):
                def is_current(self,r):return current.exists()
                def activate(self,r):
                    self.applied+=1
                    current.write_text(json.dumps({'commit':r.commit,'installs':1}))
                    ready.set();release.wait(30)
                    return {'status':'activated','stage':'live_verified','build_id':'fixture','steps':{}}
                def reconcile(self,r):
                    if json.loads(current.read_text())['commit']!=r.commit:raise ValueError('wrong current')
                    return {'status':'activated','stage':'live_verified','build_id':'fixture','steps':{'reconciled_after_sigkill':True}}
            def worker():transact(binding(),profile(),PersistentBackend(),state_root=root/'receipts')
            child=multiprocessing.get_context('fork').Process(target=worker);child.start()
            try:
                self.assertTrue(ready.wait(5));os.kill(child.pid,signal.SIGKILL);child.join(5)
                receipt=json.loads((root/'receipts'/('d'*64+'.json')).read_text());self.assertIsNone(receipt['outcome'])
                backend=PersistentBackend();out=transact(binding(),profile(),backend,state_root=root/'receipts')
                self.assertTrue(out['steps']['reconciled_after_sigkill']);self.assertEqual(backend.applied,0)
                self.assertEqual(json.loads(current.read_text())['installs'],1)
            finally:
                if child.is_alive():child.kill();child.join(5)


class CandidateStopProof(unittest.TestCase):
    def test_inactive_dead_zero_pids_required(self):
        from factory.cell.remote_apply import NativeBackend
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'registry.json';path.write_text(json.dumps({'cells':[profile()['cell']]}));path.chmod(0o400)
            values={'ActiveState':'inactive','SubState':'dead','MainPID':'0','ControlPID':'0','ControlGroup':''}
            def ctl(*args,**kw):return SimpleNamespace(returncode=0,stdout='\n'.join(k+'='+v for k,v in values.items()))
            backend=NativeBackend('lords-02','/unused',profile(),systemctl=ctl)
            with registry.scoped_projection(path,'lords-02'):
                self.assertTrue(backend.candidate_stopped())
                for key,value in [('ActiveState','activating'),('SubState','auto-restart'),('MainPID','123'),('ControlPID','124')]:
                    old=values[key];values[key]=value;self.assertFalse(backend.candidate_stopped());values[key]=old

class RelayBoundaries(unittest.TestCase):
    def setUp(self):
        import importlib.util
        self.path=Path(__file__).resolve().parents[2]/'automation/local/cell-remote-bridge.py'
        spec=importlib.util.spec_from_file_location('bounded_relay',self.path);self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.args=SimpleNamespace(expected_site='lords-02',expected_host='107.189.23.212',expected_commit='a'*40,expected_digest='sha256:'+'b'*64,package_id='c'*64)
    def header(self):
        p=profile();p['target']['host']=self.args.expected_host
        value=binding();value['profile_sha256']=fingerprint(p);value['capsule_sha256']=hashlib.sha256(b'x').hexdigest()
        return {'method':'активировать','binding':value,'profile':p,'bytes':1}
    def test_closed_site_host_commit_digest_package_binding(self):
        self.assertEqual(self.module.validate_header(self.header(),self.args),self.args.expected_host)
        for bad in ['145.63.129.86','192.0.2.1','107.189.23.234']:
            value=self.header();value['profile']['target']['host']=bad
            with self.assertRaises(ValueError):self.module.validate_header(value,self.args)
        for key,value in [('site_id','zona-02'),('commit','0'*40),('digest','sha256:'+'0'*64)]:
            h=self.header();h['binding']['request'][key]=value
            with self.assertRaises(ValueError):self.module.validate_header(h,self.args)
        self.assertIn('ConnectTimeout=10',self.module.SSH);self.assertIn('IdentityAgent=none',self.module.SSH)
    def result(self,status,stage='live_verified',outcome_status='activated'):
        return {'method':'result','result':{'site_id':'lords-02','commit':'a'*40,'status':status,'outcome':{'status':outcome_status,'stage':stage,'digest':self.args.expected_digest}}}
    def test_only_verified_activated_success_is_exit_zero(self):
        self.assertEqual(self.module.result_code(self.result('ok'),self.args),0)
        for value in [self.result('rejected'),self.result('failed'),self.result('ok','updater_failed'),self.result('ok',outcome_status='rolled-back')]:
            self.assertEqual(self.module.result_code(value,self.args),1)
        for status in ['busy','reconcile','waiting-bridge']:self.assertEqual(self.module.result_code(self.result(status),self.args),75)
    def cli(self,message):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);key=root/'fixture-key';key.write_text('not a real key')
            calls=root/'calls.jsonl';terminated=root/'terminated';ssh=root/'ssh'
            ssh.write_text('#!/usr/bin/python3\nimport json,sys,time,signal\nfrom pathlib import Path\n'
                +'p=Path('+repr(str(calls))+');p.open("a").write(json.dumps(sys.argv[1:])+"\\n")\n'
                +'signal.signal(signal.SIGTERM,lambda *a:(Path('+repr(str(terminated))+').write_text("terminated"),sys.exit(99)))\n'
                +'print('+repr(json.dumps(message))+',flush=True)\ntime.sleep(.15)\n');ssh.chmod(0o755)
            env=dict(os.environ,PATH=str(root)+':/usr/bin:/bin')
            out=subprocess.run(['/usr/bin/python3',str(self.path),'--request','fixture-request','--admin-key',str(key),'--package-id',self.args.package_id,
                '--expected-site',self.args.expected_site,'--expected-host',self.args.expected_host,'--expected-commit',self.args.expected_commit,'--expected-digest',self.args.expected_digest],capture_output=True,text=True,env=env,timeout=5)
            return out,[json.loads(line) for line in calls.read_text().splitlines()],terminated.exists()
    def test_mispointed_control_never_opens_k2_ssh(self):
        message=self.header();message['profile']['target']['host']='145.63.129.86'
        out,calls,_=self.cli(message);self.assertNotEqual(out.returncode,0);self.assertEqual(len(calls),1)
        self.assertIn('claude-control-01',calls[0]);self.assertFalse(any(x.startswith('root@') for x in calls[0]))
    def test_early_results_exit_nonzero_and_wait_for_control(self):
        for status,stage,expected in [('rejected','failed',1),('busy','validated',75),('reconcile','validated',75),('ok','updater_failed',1),('ok','live_verified',1)]:
            out,calls,terminated=self.cli(self.result(status,stage));self.assertEqual(out.returncode,expected,out.stderr)
            self.assertEqual(len(calls),1);self.assertFalse(terminated)


class GatewayRoleRefusal(GatewayRoundTrip):
    def test_nonremote_request_refused_before_native_execution(self):
        from factory.cell.remote_gateway import read_packet
        self.configure_gateway();value=json.loads(self.projection.read_text());value['cells'][0]['runtime'].pop('code_delivery')
        self.projection.chmod(0o600);self.projection.write_text(json.dumps(value));self.projection.chmod(0o400)
        before=self.file.read_bytes();child=self.process();result=read_packet(child.stdout)
        self.assertEqual(child.wait(timeout=5),0,child.stderr.read());self.assertEqual(result['result']['status'],'rejected')
        self.assertEqual(self.file.read_bytes(),before);self.assertFalse((self.root/'results').exists())

class AuthoritativeCandidateRole(unittest.TestCase):
    def test_candidate_only_unit_role_with_live_data(self):
        main=privileged.ЮНИТ_ШАБЛОН.format(domain='fixture.invalid',site_id='lords-02',account='nobody',link='/srv/fixture/current',data='/srv/fixture/data',port=9111)
        candidate=privileged.candidate_unit_text(main)
        self.assertNotIn('SITE_CELL_ROLE',main);self.assertIn('Environment=SITE_CELL_ROLE=candidate\n',candidate)
        self.assertIn('--data-dir /srv/fixture/data',candidate);self.assertIn('ReadWritePaths=/srv/fixture/data',candidate)
    def test_declared_pinned_guard_required_without_executing_source(self):
        from factory.cell.remote_apply import ROLE_CAPABILITY,require_candidate_role_support
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'config').mkdir();(root/'src').mkdir()
            module=root/'src/episode_sync.py'
            content=b'raise RuntimeError("must never execute as root")\nimport os\ndef \xd0\xb7\xd0\xb0\xd0\xbf\xd1\x83\xd1\x81\xd1\x82\xd0\xb8\xd1\x82\xd1\x8c(runtime):\n    if os.environ.get("SITE_CELL_ROLE") == "candidate":\n        return False\n    return True\n'
            module.write_bytes(content)
            pins=root/'pins.lock.json';pins.write_text(json.dumps({'files':{'episode_sync.py':{'sha256':hashlib.sha256(content).hexdigest()}}}))
            with self.assertRaises(FileNotFoundError):require_candidate_role_support(root)
            cap=root/'config/episode-sync-role.json';cap.write_text(json.dumps(ROLE_CAPABILITY))
            self.assertEqual(require_candidate_role_support(root)['data'],'live')
            module.write_bytes(content.replace(b'return False',b'return True'))
            with self.assertRaises(ValueError):require_candidate_role_support(root)
            pins.write_text(json.dumps({'files':{'episode_sync.py':{'sha256':hashlib.sha256(module.read_bytes()).hexdigest()}}}))
            with self.assertRaises(ValueError):require_candidate_role_support(root)
