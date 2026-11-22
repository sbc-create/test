import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from factory.lords.canonical_projection import спроецировать
from factory.lords.nova_publish import собрать_сайт, Снимок, РеестрСлагов, PublishError

ROOT = Path(__file__).resolve().parents[2]
TEXT = 'Проверенное описание произведения с достаточной длиной текста.'
FULL = 'Полное описание произведения, которое нельзя заменять кратким текстом.'
ID = '11111111-1111-1111-1111-111111111111'

class DescriptionFallbackTest(unittest.TestCase):
    def project(self, row=None, detail=None, enabled=True):
        return спроецировать({'external_id': ID, 'name': 'Тест', **(row or {})},
                            {'id': ID, **(detail or {})}, short_description_fallback=enabled)

    def test_disabled_by_default(self):
        self.assertIsNone(спроецировать({'external_id':ID}, {'id':ID,'short_description':TEXT}).description)

    def test_exact_identity_and_precedence(self):
        self.assertEqual(self.project(detail={'short_description':TEXT}).description, TEXT)
        self.assertIsNone(self.project(detail={'id':'other','short_description':TEXT}).description)
        self.assertEqual(self.project({'short_description':TEXT}, {'id':'other'}).description, TEXT)
        self.assertEqual(self.project({'description':FULL}, {'short_description':TEXT}).description, FULL)
        self.assertEqual(self.project({'description':TEXT}, {'description':FULL,'short_description':TEXT}).description, FULL)
        self.assertEqual(self.project({'short_description':FULL}, {'short_description':TEXT}).description_source, 'detail.short_description')

    def test_gate_unchanged(self):
        for text in ('', 'a'*39, 'Описание отсутствует'):
            self.assertIsNone(self.project(detail={'short_description':text}).description)
        self.assertEqual(self.project(detail={'short_description':'a'*40}).description, 'a'*40)

    def build(self, prior=None, enabled=True):
        ledger=РеестрСлагов(); ledger.засеять({ID:'test'})
        return собрать_сайт(снимок=Снимок({ID:{'external_id':ID,'name':'Тест'}},'', 'f'*64),
            реестр=ledger, детали_кэш=Path('/unused'), site_id='lords-05',
            прежние_подробности=prior, читатель=lambda *_:{'id':ID,'short_description':TEXT},
            short_description_fallback=enabled)

    def test_previous_full_preserved_and_site_default_off(self):
        prior={'test':{'id':ID,'description':FULL,'description_source':'accepted'}}
        result=self.build(prior)[1]['details']['test']
        self.assertEqual(result['description'],FULL)
        self.assertEqual(result['description_source'],'accepted')
        self.assertEqual(self.build()[1]['details']['test']['description'],TEXT)
        self.assertNotIn('description',self.build(enabled=False)[1]['details']['test'])

    def test_policy(self):
        spec=importlib.util.spec_from_file_location('description_policy_publisher',ROOT/'automation/host/nova-catalog-publish.py')
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'policy.json'
            self.assertEqual(module.load_description_policy(path)['sites'],{})
            valid={'schema_version':1,'sites':{'lords-05':{'short_description_fallback':True}}}
            path.write_text(json.dumps(valid));self.assertEqual(module.load_description_policy(path)['sites'],valid['sites'])
            for bad in ({}, {'schema_version':1,'sites':{'unknown':{'short_description_fallback':True}}},
                        {'schema_version':1,'sites':{'lords-05':{'short_description_fallback':'true'}}},
                        {'schema_version':1,'sites':{'lords-05':{'other':True}}}):
                path.write_text(json.dumps(bad))
                with self.assertRaises(PublishError):module.load_description_policy(path)

class DescriptionOnlyTest(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('scoped_publisher',ROOT/'automation/host/nova-catalog-publish.py')
        self.m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=self.m;spec.loader.exec_module(self.m)

    def test_registered_baseline_and_cas(self):
        import hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'cell';data.mkdir()
            runtime={'lords-05':{'managed_by':'cell','data_owner':'pipeline','data_dir':str(data)}}
            with patch.object(self.m,'размещения',return_value=runtime):
                targets=self.m.description_baseline_targets('lords-05',root/'central')
                self.assertEqual(targets.каталог,data/'lords-05-catalog.json')
                pins={'lords-05':{}}
                for name,path in (('catalog',targets.каталог),('details',targets.подробности)):
                    path.write_text('{}');pins['lords-05'][name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                self.m.check_description_baselines(pins,root/'central')
                targets.подробности.write_text('{"changed":true}')
                with self.assertRaises(PublishError):self.m.check_description_baselines(pins,root/'central')
            with patch.object(self.m,'размещения',return_value={}):
                with self.assertRaises(PublishError):self.m.description_baseline_targets('lords-05',root)

    def test_preserves_all_other_data(self):
        import copy
        catalog={'items':[{'slug':'test','title':'Тест'}],'revision':'old'}
        before={'details':{'test':{'id':ID,'seasons':[{'n':2,'nums':[3,4],'eps':2,'avail':0}],
            'crew':['known'],'unknown_field':'keep'}},'revision':'old'}
        expected=copy.deepcopy(before)
        generated={'details':{'test':{'id':ID,'description':TEXT,'description_source':'detail.short_description',
             'seasons':[{'n':2,'eps':2,'avail':2}],'crew':[]}},'revision':'new'}
        got_catalog,got,ids=self.m.description_only_projection(catalog,before,generated)
        expected['details']['test'].update(description=TEXT,description_source='detail.short_description')
        self.assertEqual(got,expected);self.assertEqual(got_catalog,catalog);self.assertEqual(ids,[ID])
        self.assertEqual(self.m.description_only_projection(catalog,got,generated)[2],[])

    def test_rejects_scope_and_identity(self):
        for sites,policy in ((None,{}),(['lords-05'],{}),(['lords-05','lords-06'],{'lords-05':{'short_description_fallback':True}})):
            with self.assertRaises(PublishError):
                self.m._выполнить(сайты=sites,description_only=True,description_policy={'sites':policy})
        for generated in ({'details':{}},{'details':{'test':{'id':'other'}}}):
            with self.assertRaises(PublishError):
                self.m.description_only_projection({}, {'details':{'test':{'id':ID}}},generated)

    def test_never_replaces_nonempty_or_uses_full_source(self):
        for text,source in ((FULL,'detail.short_description'),('', 'detail')):
            old={'details':{'test':{'id':ID,'description':text}}}
            result=self.m.description_only_projection({},old,{'details':{'test':{'id':ID,'description':TEXT,'description_source':source}}})
            self.assertEqual(result[1]['details']['test']['description'],text)
            self.assertEqual(result[2],[])

if __name__=='__main__':unittest.main()
