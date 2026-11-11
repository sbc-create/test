import importlib.util,pathlib,unittest,sys
path=pathlib.Path(sys.argv.pop(1))
spec=importlib.util.spec_from_file_location('seo_under_test',path);seo=importlib.util.module_from_spec(spec);spec.loader.exec_module(seo)
BASE='<html><head><title>Каталог</title><meta name="description" content="Описание"><link rel="canonical" href="https://lordserials1.info/catalog/"></head><body><h1>Каталог</h1></body></html>'.encode()
class Pagination(unittest.TestCase):
 def enrich(self,path,**kw):return seo.обогатить(BASE,'text/html',хост='lordserials1.info',путь=path,**kw).decode()
 def test_every_list_type(self):
  for path in ['/catalog/','/movies/','/series/','/animation/','/anime/','/dorama/','/new/','/genre/drama/','/year/2024/','/country/rossiya/','/collection/recently_added/']:
   with self.subTest(path=path):
    out=self.enrich(path+'?page=2');self.assertIn('<title>Каталог — страница 2</title>',out);self.assertIn('<h1>Каталог — страница 2</h1>',out);self.assertIn('content="Описание — страница 2"',out);self.assertIn('href="https://lordserials1.info'+path+'?page=2"',out);self.assertEqual(out.count('rel="canonical"'),1)
 def test_semantic_filter_and_tracking(self):
  out=self.enrich('/catalog/?year=2024&page=2&utm_source=test');self.assertIn('href="https://lordserials1.info/catalog/?year=2024&amp;page=2"',out)
 def test_error_nonlist_first_untouched(self):
  for path,code in [('/catalog/?page=1',200),('/catalog/?page=abc',200),('/catalog/?page=2&page=3',200),('/title/example/?page=2',200),('/catalog/?page=2',404)]:
   self.assertNotIn(' — страница ',self.enrich(path,код=code))
 def test_unbounded_page(self):
  self.assertNotIn(" — страница ",self.enrich("/catalog/?page="+"9"*5000))
 def test_idempotent(self):
  a=seo.обогатить(BASE,'text/html',хост='lordserials1.info',путь='/genre/drama/?page=2')
  b=seo.обогатить(a,'text/html',хост='lordserials1.info',путь='/genre/drama/?page=2');self.assertEqual(a,b)
unittest.main()
