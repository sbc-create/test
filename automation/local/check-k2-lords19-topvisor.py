import importlib.util,pathlib,unittest
from unittest.mock import patch
p=pathlib.Path(__file__).with_name('k2-configure-lords19-topvisor.py');s=importlib.util.spec_from_file_location('compat',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Compat(unittest.TestCase):
 def test_group_names(self):
  c=m.Compatible(None)
  with patch.object(m.TopvisorClient,'call',return_value=None) as call:c.call('add/keywords_2/groups',{'project_id':35889576,'name':'Year'})
  self.assertEqual(call.call_args.args,('add/keywords_2/groups',{'project_id':35889576,'names':['Year']}))
 def test_keywords_csv(self):
  c=m.Compatible(None)
  with patch.object(m.TopvisorClient,'call',return_value=None) as call:c.call('add/keywords_2/keywords',{'project_id':35889576,'group_id':12,'keywords':['one','two']})
  method,payload=call.call_args.args;self.assertEqual(method,'add/keywords_2/keywords/import');self.assertEqual(payload['keywords'],'name\none\ntwo\n');self.assertEqual(payload['group_id'],12)
 def test_other_site(self):
  with self.assertRaises(AssertionError):m.Compatible(None).call('add/keywords_2/groups',{'project_id':2,'name':'bad'})
 def test_paid_blocked(self):
  from factory.errors import FactoryError
  with self.assertRaises(FactoryError):m.Compatible(None,dry_run=False).call('edit/positions_2/checker/go',{'project_id':35889576})
unittest.main()
