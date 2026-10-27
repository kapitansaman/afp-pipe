import base64,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import execution_recovery as r,family_lifecycle as f
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.client import TextProviderError,ImageProviderError
from automation.agri_v2.parallel_pool import PoolDeferred

class ExecutionRecoveryTests(unittest.TestCase):
 def setup(self,root):
  data=root/'data/agri-v2';out=root/'artifacts/agri-v2';atomic_json(data/'execution-recovery-policy.json',r.POLICY)
  env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':r.REPO,'GITHUB_RUN_ID':'123','GITHUB_TOKEN':'test-only-not-persisted'};topics=[{'id':'agri-000000000001','title':'test','family_id':'family-01'}]
  return data,out,env,topics
 def transport(self,prior=None):
  def call(method,payload=None):
   if method=='GET':return prior
   raw=base64.b64decode(payload['content']);return {'content':{'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}}
  return Mock(side_effect=call)
 def prior(self,status='in_flight',run='122'):
  row={'version':1,'policy':r.VERSION,'repository':r.REPO,'branch':r.BRANCH,'status':status,'run_id':run,'checkpoint_digest':'a'*64}
  return {'sha':'b'*40,'content':base64.b64encode(json.dumps(row).encode()).decode()}
 def test_remote_fence_is_confirmed_before_work_and_contains_no_secrets(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,t=self.setup(Path(td));call=self.transport();row=r.begin(e,t,d,o,call)
   self.assertEqual([c.args[0] for c in call.call_args_list],['GET','PUT']);self.assertEqual(row['status'],'in_flight');self.assertEqual(load_json(d/'status/lifecycle-flight.json'),row)
   evidence=(o/'parallel/recovery/admissions/123.json').read_text();self.assertNotIn(e['GITHUB_TOKEN'],evidence);self.assertFalse(row['automatic_uncertain_replay'])
 def test_prior_inflight_blocks_both_same_and_next_run_without_put(self):
  for run in ('123','122'):
   with self.subTest(run=run),tempfile.TemporaryDirectory() as td:
    d,o,e,t=self.setup(Path(td));call=self.transport(self.prior(run=run))
    with self.assertRaises(r.ReconciliationRequired):r.begin(e,t,d,o,call)
    self.assertEqual(call.call_count,1)
 def test_checkpointed_previous_run_uses_compare_and_swap(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,t=self.setup(Path(td));call=self.transport(self.prior('checkpointed'));r.begin(e,t,d,o,call);self.assertEqual(call.call_args.args[1]['sha'],'b'*40)
 def test_same_checkpointed_run_is_never_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,t=self.setup(Path(td));call=self.transport(self.prior('checkpointed','123'))
   with self.assertRaises(r.ReconciliationRequired):r.begin(e,t,d,o,call)
   self.assertEqual(call.call_count,1)
 def test_uncertain_or_unconfirmed_remote_write_never_admits_work(self):
  for response in ({},{'content':{'sha':'bad'}}):
   with self.subTest(response=response),tempfile.TemporaryDirectory() as td:
    d,o,e,t=self.setup(Path(td));call=Mock(side_effect=[None,response])
    with self.assertRaises(r.ReconciliationRequired):r.begin(e,t,d,o,call)
    self.assertFalse((d/'status/lifecycle-flight.json').exists())
 def test_foreign_fence_and_missing_token_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,t=self.setup(Path(td));e.pop('GITHUB_TOKEN')
   with self.assertRaises(r.ReconciliationRequired):r.begin(e,t,d,o,self.transport())
 def test_only_all_merged_results_can_close_fence(self):
  for status,merged,coordinator,expected in [('stage_failed',True,False,True),('worker_timed_out',True,False,False),('worker_failed',False,False,False),('blocked',True,True,False),('stage_reconciliation_required',True,False,True)]:
   with self.subTest(status=status,merged=merged,coordinator=coordinator),tempfile.TemporaryDirectory() as td:
    root=Path(td);d,o,e,t=self.setup(root);r.begin(e,t,d,o,self.transport());report={'run_id':'123','status':'completed_with_failures','results':[{'topic_id':t[0]['id'],'status':status,'checkpoint_merged':merged}]}
    if coordinator:report['coordinator_failure']={'kind':'unexpected'}
    atomic_json(o/'parallel/lifecycle/runs/123/report.json',report);row,sha=r.checkpoint_candidate(root,e);self.assertEqual(row is not None,expected);self.assertIsNotNone(sha)
 def test_changed_local_intent_cannot_clear_remote_fence(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o,e,t=self.setup(root);r.begin(e,t,d,o,self.transport());p=d/'status/lifecycle-flight.json';row=load_json(p);row['topics']=[];atomic_json(p,row)
   with self.assertRaises(r.ReconciliationRequired):r.checkpoint_candidate(root,e)
 def test_crash_after_stage_reservation_does_not_repeat_request_or_reset_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);crash=Mock(side_effect=KeyboardInterrupt())
   with self.assertRaises(KeyboardInterrupt):f.attempt(folder,'text','1',crash)
   before=f.row_path(folder,'text').read_bytes();fn=Mock();result=f.attempt(folder,'text','2',fn)
   self.assertEqual(result['status'],'stage_reconciliation_required');self.assertEqual(f.row_path(folder,'text').read_bytes(),before);fn.assert_not_called();self.assertEqual(f.state(folder,'text')['attempts'],1)
 def test_image_same_run_correction_cannot_replay_unknown_reserved_request(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);atomic_json(f.row_path(folder,'image-1'),{'attempts':1,'status':'reserved','last_run_id':'1'});fn=Mock();row=f.attempt(folder,'image-1','1',fn,allow_same_run=True)
   self.assertEqual(row['status'],'stage_reconciliation_required');fn.assert_not_called()
 def test_transport_uncertainty_is_sticky_but_known_http_rejection_stays_bounded(self):
  for error in (TextProviderError(None,'network_or_timeout'),ImageProviderError(None,None,'network_or_timeout'),TextProviderError(503,'provider_unavailable')):
   with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as td:
    folder=Path(td);fn=Mock(side_effect=error);row=f.attempt(folder,'text','1',fn);again=Mock();self.assertEqual(row['status'],'stage_reconciliation_required');self.assertEqual(f.attempt(folder,'text','2',again)['status'],'stage_reconciliation_required');again.assert_not_called();self.assertEqual(f.state(folder,'text')['attempts'],1)
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);row=f.attempt(folder,'text','1',Mock(side_effect=TextProviderError(429,'rate_limited')));self.assertEqual(row['status'],'stage_failed')
 def test_admission_deferral_still_does_not_spend_stage_attempts(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);self.assertEqual(f.attempt(folder,'text','1',Mock(side_effect=PoolDeferred('busy')))['status'],'stage_deferred');self.assertEqual(f.state(folder,'text')['attempts'],0)

 def test_uncertain_run_gate_stops_before_workers_or_publisher(self):
  from tests.agri_v2 import test_family_lifecycle as fixtures
  from automation.agri_v2.queue import utcnow
  with tempfile.TemporaryDirectory() as td:
   d,o,topic,env,health=fixtures.FamilyLifecycleTests().setup(td);worker=Mock();wp=Mock();wp.inventory.return_value={'source_generated_at':utcnow(),'records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   with patch.object(f,'allocate',return_value={}),patch.object(f,'assigned_topics',return_value=[topic]),patch.object(r,'begin',side_effect=r.ReconciliationRequired('test unresolved intent')):result=f.run(env,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   self.assertEqual(result['status'],'reconciliation_required');self.assertEqual(result['published_posts'],0);worker.assert_not_called();wp.publish.assert_not_called()

 def test_unknown_language_attempt_is_held_not_retried_after_backoff(self):
  from tests.agri_v2 import test_language_review_queue as fixtures
  from automation.agri_v2 import language_review_queue as q
  import datetime
  with tempfile.TemporaryDirectory() as td:
   data,out,folder,article,topic=fixtures.LanguageReviewQueueTests().setup(td);row=q.ensure(topic,article,folder,'ru-RU');row.update(status='reserved',attempts=1,history=[{'max_calls':4}]);atomic_json(q.path(folder,'ru-RU'),row);client=Mock();result=q.run_item(q.path(folder,'ru-RU'),client,data)
   saved=load_json(q.path(folder,'ru-RU'));self.assertEqual(result['status'],'reconciliation_required');self.assertEqual(saved['model_calls_spent'],4);self.assertFalse(q.due(saved,datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=100)));client.text.assert_not_called()
 def test_uncertain_language_provider_does_not_block_sibling_or_repeat_request(self):
  from tests.agri_v2 import test_language_review_queue as fixtures
  from automation.agri_v2 import language_review_queue as q
  with tempfile.TemporaryDirectory() as td:
   data,out,folder,article,topic=fixtures.LanguageReviewQueueTests().setup(td);q.ensure(topic,article,folder,'ru-RU');sibling=q.ensure(topic,article,folder,'en-US');client=Mock();client.text.side_effect=TextProviderError(None,'network_or_timeout')
   with patch.object(q,'source_checked'):result=q.run_item(q.path(folder,'ru-RU'),client,data)
   self.assertEqual(result['status'],'reconciliation_required');calls=client.text.call_count;q.run_item(q.path(folder,'ru-RU'),client,data);self.assertEqual(client.text.call_count,calls);self.assertTrue(q.due(sibling));self.assertEqual(load_json(q.path(folder,'ru-RU'))['attempts'],1)

 def test_unknown_wordpress_mutation_does_not_repeat_publish_stage(self):
  from automation.agri_v2.wordpress import WPError
  for error in (WPError('WordPress transport/JSON failure; reconcile by slug before retry'),WPError('WordPress HTTP 503')):
   with self.subTest(error=str(error)),tempfile.TemporaryDirectory() as td:
    folder=Path(td);first=Mock(side_effect=error);self.assertEqual(f.attempt(folder,'publish','1',first)['status'],'stage_reconciliation_required');again=Mock();self.assertEqual(f.attempt(folder,'publish','2',again)['status'],'stage_reconciliation_required');again.assert_not_called();self.assertEqual(f.state(folder,'publish')['attempts'],1)
 def test_unknown_locale_publication_holds_only_that_locale(self):
  from tests.agri_v2 import test_language_review_queue as fixtures
  from automation.agri_v2 import language_review_queue as q
  from automation.agri_v2.wordpress import WPError
  with tempfile.TemporaryDirectory() as td:
   data,out,folder,article,topic=fixtures.LanguageReviewQueueTests().setup(td)
   for lang in ('ru-RU','en-US'):
    row=q.ensure(topic,article,folder,lang);row['status']='approved';atomic_json(q.path(folder,lang),row)
   q.publication_failed(q.path(folder,'ru-RU'),WPError('WordPress transport/JSON failure; reconcile by slug before retry'));row=load_json(q.path(folder,'ru-RU'));self.assertEqual(row['status'],'publication_reconciliation_required');self.assertFalse(q.publication_due(row));self.assertEqual(row['publication_attempts'],1);self.assertEqual(row['model_calls_spent'],0);self.assertTrue(q.publication_due(load_json(q.path(folder,'en-US'))))
