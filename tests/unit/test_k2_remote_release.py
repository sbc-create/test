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
        capture(self.p,self.units,self.route,self.updater,self.systemctl,state_root=self.state)
        self.p.current.unlink();self.p.current.symlink_to(self.p.candidate.resolve())
        for f in self.units.iterdir():f.write_text('new')
        (self.route/'lords-02.upstream').write_text('server 127.0.0.1:9999;')
        out=restore(self.p,self.units,self.route,self.systemctl,state_root=self.state)
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
        capture(self.p,self.units,self.route,self.updater,self.systemctl,state_root=self.state)
        previous.unlink();previous.write_text('new unmasked unit')
        (old/'override.conf').write_text('new override');(old/'new.conf').write_text('new')
        added=self.units/'previous.service.d';added.mkdir();(added/'cell-port-owner.conf').write_text('RefuseManualStart=yes')
        restore(self.p,self.units,self.route,self.systemctl,state_root=self.state)
        self.assertTrue(previous.is_symlink());self.assertEqual(os.readlink(previous),'/dev/null')
        self.assertEqual((old/'override.conf').read_text(),'old override');self.assertFalse((old/'new.conf').exists())
        self.assertFalse(added.exists())
    def test_unrelated_candidate_cannot_use_old_checkpoint(self):
        capture(self.p,self.units,self.route,self.updater,self.systemctl,state_root=self.state)
        other=self.p.releases/'other';other.mkdir();self.p.candidate.unlink();self.p.candidate.symlink_to(other)
        self.assertIsNone(restore(self.p,self.units,self.route,self.systemctl,state_root=self.state))
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
