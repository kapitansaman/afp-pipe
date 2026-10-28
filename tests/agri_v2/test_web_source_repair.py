import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import web_source_repair as w,model_source_repair as r,source_search as search,family_lifecycle as f
from automation.agri_v2.queue import atomic_json,load_json
from tests.agri_v2 import test_model_source_repair as fixture

class WebSourceRepairTests(unittest.TestCase):
 def setup(self,root):
  d,o,t,e,h,ev,v=fixture.ModelSourceRepairTests().setup(root);atomic_json(d/'source-search-policy.json',search.POLICY);e.update(AFP_SOURCE_SEARCH_API_KEY='PRIVATE-SEARCH',AFP_PARALLEL_POOL_DB=str(root/'searchdb'))
  return d,o,t,e,h,ev,v
 def plan(self,t):return {'topic_id':t['id'],'gap':'Direct evidence on the measurement-based irrigation decision method is missing.','queries':['dry bean soil moisture irrigation university'],'requirements':[{'id':'species_product','need':'Actual dry bean crop and harvested product identity.'},{'id':'exact_reader_method','need':'A real measured soil moisture irrigation decision method.'}]}
 def verdict(self,t,covered):return {'topic_id':t['id'],'requirements':[{'id':i,'covered':covered,'document_ids':['s0'] if covered else [],'missing':'' if covered else 'No document yet supports the exact measured decision method.'} for i in ('species_product','exact_reader_method')],'next_queries':[] if covered else ['dry bean irrigation measured soil water depletion method']}
 def document(self,url):return fixture.ModelSourceRepairTests().document(url)
 def plan_stage(self,d,o,t,e,ev,value=None):
  c=Mock();c.text.return_value=self.plan(t) if value is None else value
  result=f.attempt(ev.parent,'research_discover',e['GITHUB_RUN_ID'],lambda:r.discover(t,c,d,o,env=e),limit=1);self.assertEqual(result['status'],'stage_completed');return c
 def result(self,q,env,request):return {'query_id':search.query_key(q),'query':q,'cached':False,'checked_at_epoch':1,'results':[{'url':'https://x.edu/'+('second' if 'depletion' in q else 'first'),'title':'Search title, not a source quote','description':'Untrusted search snippet'}]}
 def test_plan_requests_real_queries_not_model_invented_urls(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));c=self.plan_stage(d,o,t,e,ev);p=load_json(ev/r.PLAN);self.assertEqual(p['version'],2);self.assertNotIn('leads',p['plan']);self.assertFalse(p['queries_executed']);c.text.assert_called_once();self.assertEqual(f.next_stage(t,d,o),('research_refetch',None))
 def test_two_rounds_search_then_original_extraction_without_reset(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));old=f.row_path(ev.parent,'research_extract').read_bytes();self.plan_stage(d,o,t,e,ev);c=Mock();c.text.return_value=self.verdict(t,False);api=Mock(side_effect=self.result)
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=self.document,search_fn=api),limit=1)
   self.assertEqual(result['status'],'stage_completed');self.assertEqual(result['result']['search_rounds'],2);self.assertEqual(api.call_count,2);c.text.assert_called_once();self.assertEqual(old,f.row_path(ev.parent,'research_extract').read_bytes());self.assertEqual(f.next_stage(t,d,o),('research_extract',None));self.assertFalse((d/'briefs'/(t['id']+'.json')).exists());receipt=load_json(ev/r.RECEIPT);self.assertFalse(receipt['scientific_acceptance']);self.assertEqual(len(receipt['rounds']),2)
 def test_sufficient_coverage_stops_search_but_never_approves_a_fact(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);c=Mock();c.text.return_value=self.verdict(t,True);api=Mock(side_effect=self.result)
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=self.document,search_fn=api),limit=1);self.assertEqual(result['result']['search_rounds'],1);api.assert_called_once();self.assertFalse((ev/'candidate.json').exists());self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def test_search_snippet_cannot_satisfy_a_requirement_when_page_not_fetched(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);old=(ev/'sources.json').read_bytes();c=Mock();c.text.return_value=self.verdict(t,True);fetch=Mock(side_effect=TimeoutError())
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=fetch,search_fn=self.result),limit=1);self.assertEqual(result['status'],'stage_failed');self.assertEqual(old,(ev/'sources.json').read_bytes());self.assertFalse((ev/'model-source-originals').exists())
 def test_missing_pages_after_two_rounds_preserve_inputs_and_record_exhaustion(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);old=(ev/'sources.json').read_bytes();c=Mock();c.text.return_value=self.verdict(t,False);api=Mock(side_effect=self.result)
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=Mock(side_effect=TimeoutError()),search_fn=api),limit=1);self.assertEqual(result['status'],'stage_deferred');self.assertEqual(f.state(ev.parent,'research_refetch')['attempts'],0);self.assertFalse(load_json(ev/r.RECEIPT)['repair_exhausted']);self.assertEqual(old,(ev/'sources.json').read_bytes());self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def test_fetch_budget_twelve_across_both_rounds(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));p=self.plan(t);p['queries'].append('dry bean irrigation engineering field guide');self.plan_stage(d,o,t,e,ev,p);c=Mock();verdict=self.verdict(t,False);verdict['next_queries'].append('dry bean irrigation method field measurements');c.text.return_value=verdict;fetched=[]
   def api(q,env,request):return {'results':[{'url':'https://x.edu/'+hashlib.sha256((q+str(i)).encode()).hexdigest(),'title':'title','description':'snippet'} for i in range(6)]}
   def fetch(url):fetched.append(url);return self.document(url)
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=fetch,search_fn=api),limit=1);self.assertEqual(result['status'],'stage_completed');self.assertEqual(len(fetched),12);self.assertEqual(load_json(ev/r.RECEIPT)['fetches_reserved'],12)
 def test_model_coverage_cannot_reference_nonexistent_documents(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);c=Mock();value=self.verdict(t,True);value['requirements'][0]['document_ids']=['invented'];c.text.return_value=value
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=self.document,search_fn=self.result),limit=1);self.assertEqual(result['status'],'stage_failed');self.assertFalse((ev/'model-source-originals').exists())
 def test_unknown_source_search_outcome_keeps_stage_reconciliation(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);api=Mock(side_effect=search.SearchProviderError(None,'source_search_unavailable'))
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,Mock(),d,o,e,fetcher=self.document,search_fn=api),limit=1);self.assertEqual(result['status'],'stage_reconciliation_required');self.assertEqual(f.next_stage(t,d,o),('research_refetch',None));api.assert_called_once()
 def test_missing_key_holds_before_planner_call_or_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));e.pop('AFP_SOURCE_SEARCH_API_KEY');factory=Mock();result=f.worker(t,h,d,o,e,factory)
   self.assertEqual(result['status'],'capability_required');self.assertEqual(result['kind'],'source_search');factory.assert_not_called();self.assertEqual(f.state(ev.parent,'research_discover')['attempts'],0);self.assertEqual(f.state(ev.parent,'research_extract')['attempts'],1)
 def test_old_v1_pending_fetch_needs_no_new_search_key_or_model(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=fixture.ModelSourceRepairTests().setup(Path(td));fixture.ModelSourceRepairTests().planning(d,o,t,e,ev,fixture.ModelSourceRepairTests().plan(t));atomic_json(d/'source-search-policy.json',search.POLICY)
   self.assertFalse(r.web_mode('research_refetch',ev.parent,d));self.assertEqual(f.next_stage(t,d,o),('research_refetch',None))
 def test_changed_inputs_holds_before_real_search(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);atomic_json(ev/'candidate-raw.json',{'changed':True});api=Mock()
   with self.assertRaises(r.RepairBlocked):w.refetch(t,Mock(),d,o,e,fetcher=self.document,search_fn=api)
   api.assert_not_called()
 def test_direct_repair_cannot_overwrite_an_accepted_brief(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);atomic_json(d/'briefs'/(t['id']+'.json'),{'preserve':'accepted'});api=Mock()
   with self.assertRaises(r.RepairBlocked):w.refetch(t,Mock(),d,o,e,fetcher=self.document,search_fn=api)
   api.assert_not_called()
 def test_checkpoint_merge_handles_real_search_receipt_without_resurrecting_raw(self):
  import shutil
  from automation.agri_v2.parallel_controller import merge_worker
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o,t,e,h,ev,v=self.setup(root/'worker');dd=root/'coordinator/data';oo=root/'coordinator/out';shutil.copytree(d,dd);shutil.copytree(o,oo);self.plan_stage(d,o,t,e,ev);c=Mock();c.text.return_value=self.verdict(t,True)
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=self.document,search_fn=self.result),limit=1);self.assertEqual(result['status'],'stage_completed');merge_worker(t['id'],d,o,dd,oo);self.assertFalse((oo/'new'/t['id']/'lifecycle-evidence/candidate-raw.json').exists());self.assertEqual(f.next_stage(t,dd,oo),('research_extract',None));merge_worker(t['id'],d,o,dd,oo)
 def test_query_urls_and_search_pages_not_promoted_to_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);c=Mock();c.text.return_value=self.verdict(t,False)
   def api(*a):return {'results':[{'url':'https://x.edu/search?q=beans','title':'Search page','description':'This is not evidence'}]}
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=self.document,search_fn=api),limit=1);self.assertEqual(result['result']['new_sources'],0);self.assertFalse((ev/'model-source-originals').exists())
 def test_two_empty_search_rounds_record_exhaustion_without_fake_sources(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.plan_stage(d,o,t,e,ev);c=Mock();c.text.return_value=self.verdict(t,False);old=(ev/'sources.json').read_bytes();api=Mock(return_value={'results':[]})
   result=f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,c,d,o,e,fetcher=Mock(),search_fn=api),limit=1);self.assertEqual(result['status'],'stage_completed');self.assertEqual(result['result']['search_rounds'],2);self.assertTrue(result['result']['repair_exhausted']);self.assertEqual(old,(ev/'sources.json').read_bytes());self.assertFalse((ev/'model-source-originals').exists())
