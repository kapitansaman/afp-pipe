import hashlib,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2.source_loading import load_documents
from automation.agri_v2.research import source_host
from automation.agri_v2.queue import load_json,utcnow,DATA
class SourceReportTests(unittest.TestCase):
 def test_http_failure_is_observable_without_raw_error_or_retry(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);u='https://extension.example.edu/beans';f=Mock(side_effect=urllib.error.HTTPError(u,301,'SECRET upstream text',{},None))
   self.assertEqual(load_documents([u],f,out,source_host,out/'report.json'),[]);f.assert_called_once_with(u)
   r=load_json(out/'report.json');self.assertEqual(r['sources'][0]['http_status'],301);self.assertNotIn('SECRET',str(r))
 def test_success_and_cache_record_without_second_fetch(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);u='https://extension.example.edu/beans';text='Verified document content '*30
   doc={'url':u,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':utcnow()};f=Mock(return_value=doc)
   load_documents([u],f,out,source_host,out/'report.json');self.assertEqual(load_json(out/'report.json')['sources'][0]['status'],'fetched')
   load_documents([u],f,out,source_host,out/'report.json');self.assertEqual(load_json(out/'report.json')['sources'][0]['status'],'cache_valid');self.assertEqual(f.call_count,1)
 def test_empty_discovery_is_explicit(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);load_documents([],Mock(),p,source_host,p/'report.json');self.assertEqual(load_json(p/'report.json'),{'requested':0,'loaded':0,'sources':[]})
 def test_catalog_new_intents_have_two_independent_institutions(self):
  c=load_json(DATA/'research-source-catalog.json');self.assertGreaterEqual(c['version'],4)
  for intent in ('maturity','grading','storage'):
   e=next(e for e in c['entries'] if intent in e['intents']);self.assertTrue(e['scope']);self.assertGreaterEqual(len({'.'.join(source_host(u).split('.')[-2:]) for u in e['urls']}),2)

 def test_extraction_prompt_explicitly_excludes_numeric_grade_labels(self):
  import inspect
  from automation.agri_v2 import research
  text=inspect.getsource(research.prepare_one)
  self.assertIn('including grade/class labels such as U.S. No.1',text)
  self.assertIn('catalog_scope_limitations',text)
