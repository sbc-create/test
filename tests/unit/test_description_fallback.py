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

if __name__=='__main__':unittest.main()
