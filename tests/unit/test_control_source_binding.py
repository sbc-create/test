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
