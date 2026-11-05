"""Focused binding/guard tests: no service, registry, network or queue production writes."""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from factory.cell.remote_gateway import activation_source


class BindingTests(unittest.TestCase):
    def test_cached_declaration_survives_missing_source(self):
        cell=SimpleNamespace(repo={'path':'/canonical/dirty','remote':'https://github.com/sbc-create/site-fixture.git'},runtime={'code_delivery':{'source_path':'/missing/frozen/source'}})
        request=SimpleNamespace(commit='a'*40)
        source,binding=activation_source(cell,request,check_live=False)
        self.assertEqual(binding['path'],'/missing/frozen/source');self.assertEqual(cell.repo['path'],'/canonical/dirty')
        with self.assertRaises(ValueError):activation_source(cell,request,check_live=True)
    def test_clean_exact_source_and_origin_with_nonroot_git(self):
        owner=pwd.getpwnam('claude')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o711);source=root/'source';source.mkdir();os.chown(source,owner.pw_uid,owner.pw_gid)
            def git(*args):return subprocess.check_output(['sudo','-u','claude','--','git','-C',str(source),*args],text=True).strip()
            git('init','-q');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','fixture')
            git('remote','add','origin','https://github.com/sbc-create/site-fixture.git')
            cell=SimpleNamespace(repo={'path':'/canonical/dirty','remote':'https://github.com/sbc-create/site-fixture.git'},runtime={'code_delivery':{'source_path':str(source)}})
            request=SimpleNamespace(commit=git('rev-parse','HEAD'));self.assertEqual(activation_source(cell,request)[0],source)
            (source/'untracked').write_text('dirty')
            with self.assertRaises(ValueError):activation_source(cell,request)
            self.assertEqual(activation_source(cell,request,check_live=False)[0],source)
            (source/'untracked').unlink();git('remote','set-url','origin','https://github.com/sbc-create/wrong.git')
            with self.assertRaises(ValueError):activation_source(cell,request)
    def test_consumer_skips_only_remote_activations_and_preserves_busy(self):
        path=Path(__file__).resolve().parents[2]/'automation/host/k2-native-consumer.py'
        spec=importlib.util.spec_from_file_location('tiny_guard',path);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'requests').mkdir();calls=[]
            for name,site,operation in [('remote','lords-02','activate'),('ordinary','lords-02','deliver'),('busy','zona-01','deliver')]:
                (base/'requests'/(name+'.json')).write_text(json.dumps({'request_id':name,'site_id':site,'operation':operation}))
            def write(p,value):p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(value))
            queue=SimpleNamespace(разобрать=lambda value:SimpleNamespace(**value),RequestRejected=ValueError,записать_атомарно=write)
            def perform(request,**kwargs):calls.append(request.request_id);return {'status':'busy' if request.request_id=='busy' else 'ok'}
            executor=SimpleNamespace(выполнить=perform)
            registry=SimpleNamespace(resolve=lambda _:SimpleNamespace(runtime={'code_delivery':{'role':'local-ssh-bridge'}}))
            guard.consume(queue,executor,registry,base)
            self.assertEqual(set(calls),{'ordinary','busy'});self.assertTrue((base/'requests/remote.json').exists());self.assertTrue((base/'requests/busy.json').exists())
            self.assertFalse((base/'results/remote.json').exists());self.assertFalse((base/'results/busy.json').exists());self.assertTrue((base/'results/ordinary.json').exists())
