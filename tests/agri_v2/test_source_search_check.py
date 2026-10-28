import tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import source_search as s,source_search_check as check
from automation.agri_v2.queue import atomic_json,utcnow,load_json
class SearchCheckTests(unittest.TestCase):
 def setup(self,root):
  data=root/'data';data.mkdir();atomic_json(data/'source-search-policy.json',s.POLICY);return data,root/'out',{'AFP_SOURCE_SEARCH_API_KEY':'PRIVATE'}
 def result(self):return {'cached':False,'results':[{'url':'https://extension.umn.edu/bean','title':'title','description':'untrusted snippet'}]}
 def doc(self,url):
  text='Actual fetched evidence text. '*40
  return {'url':url,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':utcnow()}
 def test_search_only_check_cannot_claim_scientific_or_publication_acceptance(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env=self.setup(Path(td));api=Mock(return_value=self.result());fetch=Mock(side_effect=self.doc);r=check.run(env,data,out,api,fetch)
   self.assertEqual(r['status'],'search_connection_verified');self.assertTrue(r['evidence_pipeline_verified']);self.assertEqual(r['model_calls'],0);self.assertEqual(r['published_posts'],0);self.assertFalse(r['scientific_acceptance']);api.assert_called_once();fetch.assert_called_once();self.assertFalse((out/'new').exists());self.assertNotIn('PRIVATE',(out/'parallel/source-search/connection-check.json').read_text())
 def test_missing_key_prevents_query(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env=self.setup(Path(td));api=Mock();r=check.run({},data,out,api,Mock());self.assertEqual(r['status'],'search_connection_blocked');api.assert_not_called()
 def test_provider_failure_is_sanitized_and_not_source_absence(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env=self.setup(Path(td));r=check.run(env,data,out,Mock(side_effect=s.SearchProviderError(401,'source_search_auth')),Mock());self.assertEqual(r['reason'],'source_search_auth');self.assertFalse(r['unknown_outcome']);self.assertNotIn('admitted_search_results',r)
 def test_failed_page_fetch_not_claimed_pipeline_success(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env=self.setup(Path(td));r=check.run(env,data,out,Mock(return_value=self.result()),Mock(side_effect=TimeoutError()));self.assertEqual(r['status'],'search_connection_verified');self.assertFalse(r['evidence_pipeline_verified']);self.assertEqual(r['fetched_documents'],0)
 def test_only_two_guarded_reads_and_cache_hit_is_labeled(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env=self.setup(Path(td));result=self.result();result['cached']=True;result['results']=[dict(url='https://x.edu/'+str(i),title='title',description='snippet') for i in range(6)];fetch=Mock(side_effect=self.doc);r=check.run(env,data,out,Mock(return_value=result),fetch);self.assertEqual(fetch.call_count,2);self.assertTrue(r['search_cache_hit'])
 def test_diagnostic_dispatch_is_wired_without_model_mode(self):
  root=Path(__file__).resolve().parents[2]
  self.assertIn('source-search-check',(root/'.github/workflows/afp-parallel-generator.yml').read_text());self.assertIn("'search_connection_blocked'",(root/'automation/agri_v2/parallel_controller.py').read_text())
