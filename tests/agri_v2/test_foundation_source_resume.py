import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import web_source_repair as w,source_repair_resume as resume,family_lifecycle as f
from automation.agri_v2.foundation_policy import POLICY
from automation.agri_v2.queue import atomic_json,load_json
from tests.agri_v2 import test_web_source_repair as fixtures

class FoundationSourceResumeTests(unittest.TestCase):
 def setup(self,td):
  helper=fixtures.WebSourceRepairTests();d,o,t,e,h,ev,v=helper.setup(Path(td));atomic_json(d/'generator-foundation-policy.json',POLICY);helper.plan_stage(d,o,t,e,ev);return helper,d,o,t,e,ev
 def call(self,helper,d,o,t,e,ev,client,fetcher,now,api=None):
  with patch.object(resume.time,'time',return_value=now):return f.attempt(ev.parent,'research_refetch',str(now),lambda:w.refetch(t,client,d,o,e,fetcher=fetcher,search_fn=helper.result if api is None else api),limit=1)
 def test_temporary_retry_preserves_queries_docs_originals_and_budget(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);before=(ev/'sources.json').read_bytes();original=f.row_path(ev.parent,'research_extract').read_bytes();api=Mock(side_effect=h.result);c=Mock();c.text.side_effect=[h.verdict(t,False),h.verdict(t,False),h.verdict(t,True)]
   def partial(url):
    if url.endswith('/second'):raise TimeoutError()
    return h.document(url)
   fetch=Mock(side_effect=partial);r=self.call(h,d,o,t,e,ev,c,fetch,1000,api);self.assertEqual(r['status'],'stage_deferred');self.assertEqual(api.call_count,2);self.assertEqual(fetch.call_count,2)
   saved=load_json(ev/'real-search/progress.json');self.assertEqual(len(saved['documents']),1);self.assertEqual(saved['urls']['https://x.edu/second']['transport_attempts'],1);self.assertFalse(saved['scientific_acceptance'])
   waiting_fetch=Mock();r=self.call(h,d,o,t,e,ev,c,waiting_fetch,1100,api);self.assertEqual(r['status'],'stage_deferred');waiting_fetch.assert_not_called();self.assertEqual(c.text.call_count,2);self.assertEqual(api.call_count,2)
   retry_fetch=Mock(side_effect=h.document);r=self.call(h,d,o,t,e,ev,c,retry_fetch,1901,api);self.assertEqual(r['status'],'stage_completed');self.assertEqual(retry_fetch.call_count,1);self.assertEqual(retry_fetch.call_args.args[0],'https://x.edu/second');self.assertEqual(api.call_count,2);self.assertEqual(c.text.call_count,3);self.assertEqual(f.state(ev.parent,'research_refetch')['attempts'],1);self.assertEqual(original,f.row_path(ev.parent,'research_extract').read_bytes());self.assertEqual((ev/'model-source-originals/sources.json').read_bytes(),before)
 def test_three_transport_failures_park_without_scientific_absence_or_new_search(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);old=(ev/'sources.json').read_bytes();api=Mock(side_effect=h.result);fetch=Mock(side_effect=TimeoutError());c=Mock();c.text.return_value=h.verdict(t,False)
   for now in (1000,1901,3702):self.assertEqual(self.call(h,d,o,t,e,ev,c,fetch,now,api)['status'],'stage_deferred')
   self.assertEqual(fetch.call_count,6);self.assertEqual(api.call_count,2);self.assertEqual(c.text.call_count,2);self.assertEqual(load_json(ev/'real-search/retry.json')['status'],'requires_retrieval_review');self.assertEqual(f.state(ev.parent,'research_refetch')['attempts'],0)
   self.assertEqual(self.call(h,d,o,t,e,ev,c,fetch,100000,api)['status'],'stage_deferred');self.assertEqual(fetch.call_count,6);self.assertEqual(old,(ev/'sources.json').read_bytes());receipt=load_json(ev/'model-source-refetch.json');self.assertFalse(receipt['repair_exhausted']);self.assertFalse(receipt['scientific_acceptance'])
 def test_unique_url_budget_is_lifetime_not_reset_on_retry(self):
  import hashlib
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);api=Mock(side_effect=lambda q,*a:{'query':q,'results':[{'url':'https://x.edu/'+hashlib.sha256((q+str(i)).encode()).hexdigest(),'title':'fixture','description':'not evidence'} for i in range(6)]});fetch=Mock(side_effect=TimeoutError());c=Mock();c.text.return_value=h.verdict(t,False)
   self.call(h,d,o,t,e,ev,c,fetch,1000,api);self.call(h,d,o,t,e,ev,c,fetch,1901,api);p=load_json(ev/'real-search/progress.json');self.assertEqual(len(p['urls']),12);self.assertEqual(api.call_count,2);self.assertEqual(fetch.call_count,24);self.assertTrue(all(v['transport_attempts']==2 for v in p['urls'].values()))
 def test_corrupt_progress_blocks_before_search_fetch_or_model(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);api=Mock(side_effect=h.result);fetch=Mock(side_effect=TimeoutError());c=Mock();c.text.return_value=h.verdict(t,False);self.call(h,d,o,t,e,ev,c,fetch,1000,api);p=ev/'real-search/progress.json';r=load_json(p);r['urls']={};atomic_json(p,r);before=(api.call_count,fetch.call_count,c.text.call_count)
   r=self.call(h,d,o,t,e,ev,c,fetch,1901,api);self.assertEqual(r['status'],'stage_failed');self.assertEqual(before,(api.call_count,fetch.call_count,c.text.call_count))
 def test_actual_coverage_complete_does_not_wait_for_optional_failed_url(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);api=Mock(return_value={'query':'fixture query','results':[{'url':'https://x.edu/good','title':'good','description':'not evidence'},{'url':'https://x.edu/failed','title':'failed','description':'not evidence'}]});c=Mock();c.text.return_value=h.verdict(t,True)
   def fetch(url):
    if url.endswith('failed'):raise TimeoutError()
    return h.document(url)
   r=self.call(h,d,o,t,e,ev,c,fetch,1000,api);self.assertEqual(r['status'],'stage_completed');self.assertEqual(load_json(ev/'real-search/retry.json')['status'],'clear');self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def test_unknown_model_request_remains_fenced_even_with_fetch_progress(self):
  from automation.agri_v2.client import TextProviderError
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);c=Mock();c.text.side_effect=TextProviderError(None,'network_or_timeout');api=Mock(side_effect=h.result);r=self.call(h,d,o,t,e,ev,c,h.document,1000,api);self.assertEqual(r['status'],'stage_reconciliation_required');self.assertTrue((ev/'real-search/progress.json').exists());r=self.call(h,d,o,t,e,ev,c,h.document,10000,api);self.assertEqual(r['status'],'stage_reconciliation_required');self.assertEqual(api.call_count,1);c.text.assert_called_once()
 def test_model_admission_deferral_still_honors_source_wait_without_retry_file(self):
  from automation.agri_v2.parallel_pool import PoolDeferred
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);c=Mock();c.text.side_effect=PoolDeferred('Bounded model budget consumed');api=Mock(side_effect=h.result);fetch=Mock(side_effect=TimeoutError());self.assertEqual(self.call(h,d,o,t,e,ev,c,fetch,1000,api)['status'],'stage_deferred');self.assertFalse((ev/'real-search/retry.json').exists());before=(api.call_count,fetch.call_count,c.text.call_count);self.assertEqual(self.call(h,d,o,t,e,ev,c,fetch,1100,api)['status'],'stage_deferred');self.assertEqual(before,(api.call_count,fetch.call_count,c.text.call_count))
