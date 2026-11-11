import importlib.util,sys
from pathlib import Path
import pytest
from factory.topvisor import client as m
def read(payload):
 c=object.__new__(m.TopvisorClient);calls=[]
 c.call=lambda method,params:(calls.append((method,params)) or payload)
 return c.bank_info(),calls

def test_total_not_tariff_and_fields_explicit():
 d,calls=read({'balance_all':100,'balance_personal':90,'balance_bonus':10,'balance_tariff':0,'tariff':{'balance':0,'name':'XS'}})
 assert d['balance']==100 and d['tariff']['balance']==0 and d['name']=='XS'
 assert set(calls[0][1]['fields'])=={'balance_all','balance_personal','balance_bonus','balance_tariff','tariff'}
@pytest.mark.parametrize('value',[None,True,'bad',float('nan'),float('inf')])
def test_unknown_total_fails_closed(value):
 d,_=read({'balance_all':value,'balance':900,'sum':900,'tariff':{'balance':700}})
 assert d['balance'] is None

def test_missing_total_is_not_tariff():
 assert read({'tariff':{'balance':123}})[0]['balance'] is None

def test_list_numeric_string_and_real_zero():
 assert read([{'balance_all':'123.45','tariff':{'balance':0}}])[0]['balance']==123.45
 assert read({'balance_all':0,'tariff':{'balance':900}})[0]['balance']==0
@pytest.mark.parametrize('value',[[],None,'bad',{}])
def test_malformed_empty(value):assert read(value)[0]=={}
