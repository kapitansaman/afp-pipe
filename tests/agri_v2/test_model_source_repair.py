import copy,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import model_source_repair as r,family_lifecycle as f
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from tests.agri_v2 import test_saved_research_routing as fixtures

class ModelSourceRepairTests(unittest.TestCase):
 def setup(self,root):
  d,o,t,e,h,ev,v=fixtures.SavedResearchRoutingTests().setup(root)
  t.update(crop='لوبیا چیتی',intent='irrig_interval',title='آبیاری لوبیا چیتی بر پایه رطوبت خاک')
  v['answers_intent']=False;v['insufficiency_reason']='No source supplies a soil measurement decision method for the exact crop.';atomic_json(ev/'candidate-raw.json',v)
  atomic_json(d/'model-source-repair-policy.json',r.POLICY)
  atomic_json(f.row_path(ev.parent,'research_extract'),{'attempts':1,'status':'failed','last_run_id':'99','failure':{'category':'saved_evidence_declares_insufficient_scope'},'history':[{'preserved':True}]})
  return d,o,t,e,h,ev,v
 def plan(self,t,leads=True):
  return {'topic_id':t['id'],'gap':'A source-grounded soil moisture decision method is missing.','queries':['dry bean soil moisture irrigation extension'],'leads':[{'url':'https://x.edu/dry-bean-irrigation','kind':'document','why_relevant':'University production guide lead for the exact field crop.','expected_evidence':'A documented soil moisture measurement and scheduling method.'}] if leads else [],'no_source_found':not leads}
 def document(self,url,text=None,links=None):
  text=text or 'Actually fetched new university source describing a field soil moisture measurement method. '*12
  return {'url':url,'requested_url':url,'redirect_chain':[url],'text':text,'links':links or [],'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':utcnow(),'source_link_discovery_version':1,'source_text_layout_version':2}
 def planning(self,d,o,t,e,ev,value):
  client=Mock();client.text.return_value=value
  result=f.attempt(ev.parent,'research_discover',e['GITHUB_RUN_ID'],lambda:r.discover(t,client,d,o),limit=1)
  return result,client
 def test_gap_routes_to_model_before_blind_original_retry(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));old=f.row_path(ev.parent,'research_extract').read_bytes()
   self.assertEqual(f.next_stage(t,d,o),('research_discover',None));self.assertEqual(old,f.row_path(ev.parent,'research_extract').read_bytes())
 def test_model_plan_is_one_call_and_not_verified_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));result,c=self.planning(d,o,t,e,ev,self.plan(t));self.assertEqual(result['status'],'stage_completed');c.text.assert_called_once()
   self.assertEqual(c.text.call_args.kwargs['attempts'],1);p=load_json(ev/r.PLAN);self.assertFalse(p['search_engine_used']);self.assertFalse(p['queries_executed']);self.assertFalse(p['publication_authorized']);self.assertFalse((ev/'candidate.json').exists());self.assertEqual(f.next_stage(t,d,o),('research_refetch',None))
 def test_verified_new_source_requires_original_extraction_and_preserves_history(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));raw=(ev/'candidate-raw.json').read_bytes();sources=(ev/'sources.json').read_bytes();counter=f.row_path(ev.parent,'research_extract').read_bytes();self.planning(d,o,t,e,ev,self.plan(t))
   result=f.attempt(ev.parent,'research_refetch','101',lambda:r.refetch(t,d,o,lambda u:self.document(u)),limit=1)
   self.assertEqual(result['status'],'stage_completed');self.assertEqual(counter,f.row_path(ev.parent,'research_extract').read_bytes());self.assertEqual((ev/'model-source-originals/candidate-raw.json').read_bytes(),raw);self.assertEqual((ev/'model-source-originals/sources.json').read_bytes(),sources)
   self.assertFalse((ev/'candidate-raw.json').exists());self.assertFalse((ev/'candidate.json').exists());self.assertEqual(f.next_stage(t,d,o),('research_extract',None));self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def test_no_leads_or_unfetchable_urls_never_replaces_source_pack(self):
  for leads in (False,True):
   with self.subTest(leads=leads),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td));before={p:p.read_bytes() for p in (ev/'sources.json',ev/'candidate-raw.json')};self.planning(d,o,t,e,ev,self.plan(t,leads));fetch=Mock(side_effect=TimeoutError())
    result=f.attempt(ev.parent,'research_refetch','101',lambda:r.refetch(t,d,o,fetch),limit=1)
    self.assertEqual(result['status'],'stage_completed');self.assertEqual(result['result']['new_sources'],0);self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertEqual(f.next_stage(t,d,o)[0],'research_extract')
    if not leads:fetch.assert_not_called()
 def test_unadmitted_private_and_credential_urls_never_become_plan(self):
  for url in ('http://x.edu/doc','https://127.0.0.1/a','https://x.edu@evil.org/a','https://user:pass@x.edu/a','https://evil.org/a','https://x.edu/a#ignored'):
   with self.subTest(url=url),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td));p=self.plan(t);p['leads'][0]['url']=url;result,c=self.planning(d,o,t,e,ev,p)
    self.assertEqual(result['status'],'stage_failed');self.assertFalse((ev/r.PLAN).exists());self.assertFalse((ev/'candidate.json').exists())
 def test_foreign_or_invalid_model_plan_not_trusted(self):
  for kind in ('foreign','too_many','bad_reason','no_leads_claim_false'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td));p=self.plan(t)
    if kind=='foreign':p['topic_id']='agri-ffffffffffff'
    elif kind=='too_many':p['leads']*=5
    elif kind=='bad_reason':p['leads'][0]['why_relevant']='x'
    else:p['leads']=[]
    result,c=self.planning(d,o,t,e,ev,p);self.assertEqual(result['status'],'stage_failed');self.assertFalse((ev/r.PLAN).exists())
 def test_unknown_planner_or_refetch_keeps_reconciliation_even_without_raw(self):
  for stage in ('research_discover','research_refetch'):
   with self.subTest(stage=stage),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td));atomic_json(f.row_path(ev.parent,stage),{'status':'reserved','attempts':1,'last_run_id':'98'});(ev/'candidate-raw.json').unlink()
    client=Mock();result=f.worker(t,h,d,o,e,Mock(return_value=client));self.assertEqual(result['status'],'stage_reconciliation_required');client.text.assert_not_called()
 def test_partial_source_mutation_never_resumes_extraction(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));(ev/'model-source-originals').mkdir();atomic_json(f.row_path(ev.parent,'research_refetch'),{'status':'failed','attempts':1});(ev/'candidate-raw.json').unlink()
   self.assertEqual(f.next_stage(t,d,o),('blocked','source_repair_reconciliation_required'))
 def test_reserved_or_exhausted_original_request_is_not_bypassed(self):
  for status,attempts in (('reserved',1),('reconciliation_required',1),('failed',3)):
   with self.subTest(status=status,attempts=attempts),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td));row=load_json(f.row_path(ev.parent,'research_extract'));row.update(status=status,attempts=attempts);atomic_json(f.row_path(ev.parent,'research_extract'),row)
    self.assertIsNone(r.next_stage(t,ev.parent,d));self.assertNotIn(f.next_stage(t,d,o)[0],('research_discover','research_refetch'))
 def test_holds_accepted_work_and_scientific_verdict_never_repaired_around(self):
  for name in ('hold','brief','candidate','review','overlap-batch','article','receipt'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td))
    if name=='hold':atomic_json(d/'config.json',{'publication_holds':{t['id']:'keep'}})
    elif name=='brief':atomic_json(d/'briefs'/(t['id']+'.json'),{})
    elif name=='candidate':atomic_json(ev/'candidate.json',{})
    elif name=='review':atomic_json(ev/'review-raw.json',{'passed':False})
    elif name=='overlap-batch':atomic_json(ev/'overlap-batches/000.raw.json',{})
    else:atomic_json(ev.parent/('article.json' if name=='article' else 'wordpress-receipt.json'),{})
    self.assertIsNone(r.next_stage(t,ev.parent,d))
 def test_changed_source_pack_invalidates_planned_refetch(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.planning(d,o,t,e,ev,self.plan(t));atomic_json(ev/'sources.json',{'documents':[self.document('https://changed.edu/a')]})
   with self.assertRaises(r.RepairBlocked):r.refetch(t,d,o,Mock())
 def test_search_and_index_pages_are_not_used_as_agronomic_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));p=self.plan(t);p['leads'][0].update(url='https://x.edu/search?q=beans',kind='hub');self.planning(d,o,t,e,ev,p)
   result=f.attempt(ev.parent,'research_refetch','101',lambda:r.refetch(t,d,o,lambda u:self.document(u)),limit=1)
   self.assertEqual(result['result']['new_sources'],0);self.assertFalse((ev/'model-source-originals').exists())
 def test_planner_budget_one_and_no_repeat_when_refetch_failed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.planning(d,o,t,e,ev,self.plan(t));fn=Mock();self.assertEqual(f.attempt(ev.parent,'research_discover','102',fn,limit=1)['status'],'stage_budget_exhausted');fn.assert_not_called()
   atomic_json(f.row_path(ev.parent,'research_refetch'),{'status':'failed','attempts':1});self.assertIsNone(r.next_stage(t,ev.parent,d))
 def test_refetch_is_api_free_but_planning_requires_own_healthy_model_capability(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));h['eligible_text_slots']=[];factory=Mock()
   with patch.object(f,'next_stage',side_effect=[('research_refetch',None),('blocked','stop')]),patch.object(f,'run_stage',return_value={'new_sources':0}) as execute,patch('automation.agri_v2.recovery.circuit_open',return_value=True):result=f.worker(t,h,d,o,e,factory)
   factory.assert_not_called();self.assertIsNone(execute.call_args.args[2])
   with patch.object(f,'next_stage',return_value=('research_discover',None)),patch('automation.agri_v2.recovery.circuit_open',return_value=False):result=f.worker(t,h,d,o,e,factory)
   self.assertEqual(result['status'],'capability_required');factory.assert_not_called()
 def test_policy_absent_disabled_or_malformed_does_not_silently_enable(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));p=d/'model-source-repair-policy.json';p.unlink();self.assertFalse(r.enabled(d));atomic_json(p,dict(r.POLICY,enabled=False));self.assertFalse(r.enabled(d));atomic_json(p,dict(r.POLICY,max_leads=100))
   with self.assertRaises(r.RepairBlocked):r.enabled(d)
 def initial_gap(self,d,t,ev):
  from automation.agri_v2.source_policy import VERSION
  for p in (ev/'sources.json',ev/'candidate-raw.json',f.row_path(ev.parent,'research_extract')):p.unlink(missing_ok=True)
  atomic_json(f.row_path(ev.parent,'research_sources'),{'attempts':1,'status':'failed','failure':{'category':'university_or_two_fetchable_independent_publications_required'}})
  atomic_json(ev/'source-discovery-report.json',{'topic_id':t['id'],'source_policy_version':VERSION,'bounded_discovery_completed':True,'temporary_source_failure':False,'requested':0,'source_sufficiency':{'satisfied':False},'blocking_kind':'discovery_catalog_empty'})
 def test_empty_catalog_reaches_model_before_research_backlog(self):
  from automation.agri_v2.research_backlog import deferral
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.initial_gap(d,t,ev)
   self.assertEqual(f.next_stage(t,d,o),('research_discover',None));self.assertIsNone(deferral(t,d,o))
   self.planning(d,o,t,e,ev,self.plan(t));self.assertIsNone(deferral(t,d,o))
   result=f.attempt(ev.parent,'research_refetch','101',lambda:r.refetch(t,d,o,lambda u:self.document(u)),limit=1)
   self.assertEqual(result['status'],'stage_completed');self.assertIsNone(deferral(t,d,o));self.assertEqual(f.next_stage(t,d,o),('research_extract',None));self.assertEqual(f.state(ev.parent,'research_sources')['attempts'],1)
 def test_failed_bounded_discovery_releases_initial_gap_to_existing_backlog(self):
  from automation.agri_v2.research_backlog import deferral
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.initial_gap(d,t,ev);self.planning(d,o,t,e,ev,self.plan(t,False));f.attempt(ev.parent,'research_refetch','101',lambda:r.refetch(t,d,o,Mock()),limit=1)
   self.assertEqual(deferral(t,d,o)['kind'],'additional_source_discovery_required');self.assertEqual(f.state(ev.parent,'research_sources')['attempts'],1)
 def test_transient_source_failure_never_promoted_to_scientific_gap(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));self.initial_gap(d,t,ev);p=ev/'source-discovery-report.json';row=load_json(p);row['temporary_source_failure']=True;atomic_json(p,row)
   self.assertEqual(f.next_stage(t,d,o),('research_sources',None))
 def test_observed_link_navigation_fetches_document_but_excludes_search_hub(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));p=self.plan(t);p['leads'][0].update(url='https://x.edu/search?q=beans',kind='hub');self.planning(d,o,t,e,ev,p)
   target='https://y.edu/dry-bean-irrigation'
   def fetch(url):return self.document(url,links=[{'url':target,'label':'dry bean irrigation soil moisture guide'}] if 'search?' in url else [])
   result=f.attempt(ev.parent,'research_refetch','101',lambda:r.refetch(t,d,o,fetch),limit=1)
   self.assertEqual(result['status'],'stage_completed');self.assertEqual([x['url'] for x in load_json(ev/'sources.json')['documents']],[target]);self.assertFalse((ev/'candidate.json').exists())
 def test_real_worker_plans_refetches_then_spends_only_remaining_original_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));client=Mock();client.text.side_effect=[self.plan(t),copy.deepcopy(v)];factory=Mock(return_value=client)
   with patch('automation.agri_v2.scoped_sources.fetch',side_effect=lambda u:self.document(u)),patch('automation.agri_v2.scoped_research.entries_for',return_value=[]):result=f.worker(t,h,d,o,e,factory)
   self.assertEqual(result['status'],'stage_failed');self.assertEqual(result['stage'],'research_extract');self.assertEqual(client.text.call_count,2);self.assertEqual(f.state(ev.parent,'research_discover')['attempts'],1);self.assertEqual(f.state(ev.parent,'research_refetch')['attempts'],1);self.assertEqual(f.state(ev.parent,'research_extract')['attempts'],2);self.assertFalse((ev/'candidate.json').exists());self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def prepared_merge(self,root):
  import shutil
  d,o,t,e,h,ev,v=self.setup(root/'worker');dest=root/'coordinator';dest.mkdir();destdata=dest/'data';destout=dest/'out';shutil.copytree(d,destdata);shutil.copytree(o,destout)
  self.planning(d,o,t,e,ev,self.plan(t));result=f.attempt(ev.parent,'research_refetch','101',lambda:r.refetch(t,d,o,lambda u:self.document(u)),limit=1);self.assertEqual(result['status'],'stage_completed')
  return d,o,t,ev,destdata,destout
 def test_merge_retires_old_raw_ids_and_is_idempotent(self):
  from automation.agri_v2.parallel_controller import merge_worker
  with tempfile.TemporaryDirectory() as td:
   d,o,t,ev,dd,oo=self.prepared_merge(Path(td));merge_worker(t['id'],d,o,dd,oo);target=oo/'new'/t['id']/'lifecycle-evidence'
   self.assertFalse((target/'candidate-raw.json').exists());self.assertTrue((target/'model-source-originals/candidate-raw.json').exists());self.assertEqual(f.next_stage(t,dd,oo),('research_extract',None));merge_worker(t['id'],d,o,dd,oo);self.assertFalse((target/'candidate-raw.json').exists())
 def test_merge_detects_changed_coordinator_before_copying_any_state(self):
  from automation.agri_v2.parallel_controller import merge_worker
  with tempfile.TemporaryDirectory() as td:
   d,o,t,ev,dd,oo=self.prepared_merge(Path(td));target=oo/'new'/t['id']/'lifecycle-evidence';before=(target/'sources.json').read_bytes();atomic_json(target/'candidate-raw.json',{'concurrent':'changed'})
   with self.assertRaises(r.RepairBlocked):merge_worker(t['id'],d,o,dd,oo)
   self.assertEqual(before,(target/'sources.json').read_bytes())
 def test_merge_detects_pack_changed_after_validated_refetch(self):
  from automation.agri_v2.parallel_controller import merge_worker
  with tempfile.TemporaryDirectory() as td:
   d,o,t,ev,dd,oo=self.prepared_merge(Path(td));target=oo/'new'/t['id']/'lifecycle-evidence';before=(target/'sources.json').read_bytes();atomic_json(ev/'sources.json',{'changed':True})
   with self.assertRaises(r.RepairBlocked):merge_worker(t['id'],d,o,dd,oo)
   self.assertEqual(before,(target/'sources.json').read_bytes())
