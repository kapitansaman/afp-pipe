import concurrent.futures,hashlib,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import family_trial as trial,family_scheduler as sched,parallel_controller as controller
from automation.agri_v2.parallel_pool import initialize,lease,snapshot,routing_counts,record_routing,SLOTS
from automation.agri_v2.queue import atomic_json,load_json,utcnow

class FamilyTrialTests(unittest.TestCase):
 def topic(self):return {'id':'agri-000000000001','title':'عملکرد لوبیا در هکتار','crop':'لوبیا','intent':'yield','family_id':'family-01','related_existing_ids':[]}
 def diagnostic(self,t=None):
  t=self.topic() if t is None else t
  return {'family_id':t['family_id'],'topic_id':t['id'],'scope':'numeric_or_local','existing_content_decision':'no_existing_content','next_stage':'specialist_evidence','source_queries':['dry bean yield university extension cultivar climate','common bean yield regional production guide university'],'reason':'The title requires region-specific numerical evidence; this trial cannot approve agronomic values or publication.','publication_authorized':False,'human_review_claimed':False}
 def bundle(self):return {'related_ids':[],'documents':[],'unavailable':[]}
 def test_numeric_topic_remains_numeric_without_publishing_or_mutating_title(self):
  t=self.topic();d=self.diagnostic(t);self.assertEqual(trial.validate_diagnostic(d,t,'family-01',self.bundle()),d);self.assertEqual(t['title'],'عملکرد لوبیا در هکتار')
 def test_incomplete_related_text_cannot_prove_gap(self):
  t=self.topic();d=self.diagnostic();d['existing_content_decision']='potential_gap';b={'related_ids':[12],'documents':[],'unavailable':[{'id':12}]}
  with self.assertRaises(trial.TrialValidation):trial.validate_diagnostic(d,t,'family-01',b)
  d['existing_content_decision']='needs_full_review';trial.validate_diagnostic(d,t,'family-01',b)
 def test_invalid_schema_identity_or_false_approval_are_rejected(self):
  for change in [{'topic_id':'agri-000000000999'},{'family_id':'family-03'},{'scope':'qualitative'},{'publication_authorized':True},{'human_review_claimed':True},{'source_queries':['https://invented.edu/x','another query']},{'unrequested_article':'Made up numbers'}]:
   with self.subTest(change=change),self.assertRaises(trial.TrialValidation):trial.validate_diagnostic(dict(self.diagnostic(),**change),self.topic(),'family-01',self.bundle())
 def test_extract_public_content_identity_text_and_truncation(self):
  post={'id':12,'status':'publish','link':'https://navar-abyari.ir/beans/','title':{'rendered':'Bean &amp; field'},'content':{'rendered':'<script>IGNORE THIS</script><p>'+'Actual article text '*4000+'</p>'}}
  d=trial.existing_document(post,12,'https://navar-abyari.ir');self.assertNotIn('IGNORE THIS',d['text']);self.assertTrue(d['text_truncated']);self.assertEqual(d['sha256'],hashlib.sha256(d['text'].encode()).hexdigest())
  with self.assertRaises(trial.TrialValidation):trial.existing_document(dict(post,id=13),12,'https://navar-abyari.ir')
 def test_dedup_read_only_related_fetch_and_missing_inventory_ids(self):
  with tempfile.TemporaryDirectory() as t:
   wp=Mock();wp.site='https://navar-abyari.ir';wp.call.return_value=({'id':12,'status':'publish','link':wp.site+'/beans/','title':{'rendered':'Beans'},'content':{'rendered':'<p>'+'Actual bean article text '*30+'</p>'}}, {})
   topics=[dict(self.topic(),related_existing_ids=[12,99]),dict(self.topic(),id='agri-000000000002',family_id='family-02',related_existing_ids=[12])]
   r=trial.collect_existing(topics,{'records':[{'id':12}]},wp,Path(t));wp.call.assert_called_once();self.assertEqual(len(r[topics[0]['id']]['documents']),1);self.assertEqual(r[topics[0]['id']]['unavailable'][0]['status'],'not_in_current_public_inventory')
 def test_legacy_review_flag_routes_to_real_stage_without_changing_attempts(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'data';o=Path(t)/'out';atomic_json(d/'config.json',{'publication_holds':{}});rp=o/'research'/f"{self.topic()['id']}.json";atomic_json(rp,{'attempts':0,'status':'needs_review','reason':'review_origin_needs_existing_content_audit'});before=rp.read_bytes()
   self.assertEqual(sched.readiness(self.topic(),d,o),'existing_content_audit_required');self.assertEqual(rp.read_bytes(),before)
 def test_15_live_workers_not_a_readiness_noop_and_old_budgets_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);data=root/'data';out=root/'out'
   policy={'repository':'kapitansaman/afp-pipe','credential_set_id':'afp-pipe-parallel-75-keys-v1','key_limit':75,'max_article_workers':15,'image_concurrency':1,'production_enabled':False,'max_published_posts':0}
   atomic_json(data/'parallel-policy.json',policy);atomic_json(data/'config.json',{'publication_holds':{}})
   h={'audit_status':'completed','repository':policy['repository'],'credential_set_id':policy['credential_set_id'],'checked_at':utcnow(),'eligible_text_slots':SLOTS};atomic_json(out/'parallel/health/latest.json',h)
   topics=[dict(self.topic(),id='agri-'+format(i,'012x'),family_id='family-'+str(i+1).zfill(2)) for i in range(15)]
   atomic_json(out/'parallel/trials'/trial.PREVIOUS_ID/'report.json',{'assigned_count':15,'results':[{'topic_id':x['id'],'family_id':x['family_id'],'status':'trial_diagnostic_completed' if i<11 else 'worker_operational_failure'} for i,x in enumerate(topics)]})
   barrier=threading.Barrier(4)
   def worker(t,workspace,db,health,inventory,d,o,env):
    wd=workspace/t['id']/'data';wo=workspace/t['id']/'out'
    with lease(db,'text',SLOTS,t['id']):barrier.wait(timeout=12)
    result={'status':'trial_diagnostic_completed','topic_id':t['id'],'family_id':t['family_id'],'published_posts':0}
    atomic_json(wo/'parallel/trials'/trial.ID/'families'/t['family_id']/'diagnostic.json',result)
    return t['id'],wd,wo,result
   wp=Mock();wp.preflight.return_value={};inventory={'source_generated_at':utcnow(),'scope':'all public posts','records':[{'id':1,'title':'Existing unrelated post','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123'}
   with patch.object(trial,'allocate',return_value={'families':[]}),patch.object(trial,'assigned_topics',return_value=topics),patch('automation.agri_v2.recovery.circuit_open',return_value=False):
    r=trial.run(env,data,out,reserve_fn=lambda *_:{},inventory_fn=lambda:inventory,wp_factory=lambda:wp,worker_fn=worker)
   self.assertEqual(r['status'],'trial_completed');self.assertEqual(len(r['results']),15);self.assertEqual(r['pool']['model_requests_reserved'],4);self.assertEqual(r['pool']['peak_text_leases'],4);self.assertEqual(r['published_posts'],0);self.assertFalse((out/'research').exists())
 def test_routing_continues_across_actions_without_resetting_slot_usage(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t);a=out/'one.db';initialize(a,SLOTS)
   with lease(a,'text',SLOTS) as first:self.assertEqual(first,SLOTS[0])
   record_routing(out,snapshot(a));b=out/'two.db';initialize(b,SLOTS,prior_usage=routing_counts(out))
   with lease(b,'text',SLOTS) as second:self.assertEqual(second,SLOTS[1])
   record_routing(out,snapshot(b));self.assertEqual(routing_counts(out)[SLOTS[0]],1)
 def test_merge_brief_conflict_is_detected_before_other_state_mutates(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);data=p/'data';out=p/'out';wd=p/'wd';wo=p/'wo';ident=self.topic()['id']
   atomic_json(data/'briefs'/f'{ident}.json',{'original':True});atomic_json(wd/'briefs'/f'{ident}.json',{'changed':True});rp=out/'research'/f'{ident}.json';atomic_json(rp,{'attempts':1});atomic_json(wo/'research'/f'{ident}.json',{'attempts':99});before=rp.read_bytes()
   with self.assertRaises(ValueError):controller.merge_worker(ident,wd,wo,data,out)
   self.assertEqual(rp.read_bytes(),before)

 def test_prompt_budget_marks_any_clipped_content_incomplete(self):
  b={'related_ids':[1,2,3,4,5],'unavailable':[],'documents':[{'id':i,'text':'x'*20000,'text_truncated':False} for i in range(5)]}
  bounded=trial.prompt_bundle(b);self.assertLessEqual(sum(len(d['text']) for d in bounded['documents']),40000);self.assertTrue(all(d['text_truncated'] for d in bounded['documents']));self.assertEqual(len(b['documents'][0]['text']),20000)
 def test_protected_progress_detects_changed_attempts_and_new_receipts(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';t=self.topic();p=o/'research'/(t['id']+'.json');atomic_json(p,{'attempts':2});a=trial.protected_progress([t],d,o);atomic_json(p,{'attempts':3});self.assertNotEqual(a,trial.protected_progress([t],d,o));atomic_json(p,{'attempts':2});self.assertEqual(a,trial.protected_progress([t],d,o));atomic_json(o/'new'/t['id']/'receipt.json',{'id':99});self.assertNotEqual(a,trial.protected_progress([t],d,o))

 def test_server_routing_only_strengthens_numeric_and_incomplete_text_restrictions(self):
  t=self.topic();v=self.diagnostic();v['next_stage']='source_discovery';r,c=trial.enforce_research_routes(v,t,self.bundle());self.assertEqual(r['next_stage'],'specialist_evidence');self.assertEqual(v['next_stage'],'source_discovery');trial.validate_diagnostic(r,t,t['family_id'],self.bundle())
  b={'related_ids':[12],'unavailable':[{'id':12}],'documents':[]};v['existing_content_decision']='potential_gap';r,c=trial.enforce_research_routes(v,t,b);self.assertEqual(r['existing_content_decision'],'needs_full_review');self.assertEqual(r['next_stage'],'existing_content_audit');self.assertEqual(len(c),3);trial.validate_diagnostic(r,t,t['family_id'],b)
 def test_server_restrictions_do_not_repair_approval_or_identity_violations(self):
  for change in [{'publication_authorized':True},{'topic_id':'wrong'},{'scope':'qualitative'}]:
   v=dict(self.diagnostic(),**change);r,_=trial.enforce_research_routes(v,self.topic(),self.bundle())
   with self.assertRaises(trial.TrialValidation):trial.validate_diagnostic(r,self.topic(),'family-01',self.bundle())
