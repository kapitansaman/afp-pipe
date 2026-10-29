import copy,tempfile,unittest
from unittest.mock import Mock,patch
from automation.agri_v2 import claim_policy_continuation as c,claim_policy_recheck as old,regional_revision as r,parallel_control as control
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.pipeline import digest
import test_claim_policy_recheck as fixtures

class ContinuationTests(unittest.TestCase):
 def setup(self,t):
  data,out,topic,env,root,oldreq,proposal,docs=fixtures.ClaimRecheckTests().setup(t)
  prior=out/'claim-policy-rechecks'/old.ID
  report={'request_id':old.ID,'status':'revision_needs_attention','model_calls':1,'originals_unchanged':True,'post_mutations':0,'failure':{'kind':'model_output','category':'text_incomplete_response'}}
  receipt={'status':'reserved','prompt_sha256':'unchanged'}
  atomic_json(prior/'report.json',report);atomic_json(prior/'calls/context-annotation.receipt.json',receipt)
  seed=fixtures.ClaimRecheckTests().annotation(proposal['candidate']);atomic_json(data/'alfalfa-claim-policy-context-seed.json',seed)
  req=dict(oldreq,request_id=c.ID,max_model_calls=3,code_binding=c.code_binding(),predecessor_request_sha256=digest(oldreq),predecessor_report_sha256=digest(report),predecessor_receipt_sha256=digest(receipt),context_seed_sha256=digest(seed))
  atomic_json(data/'alfalfa-claim-policy-continuation-request.json',req)
  return data,out,topic,env,prior,req
 def test_inputs_and_pending_seed_validate_without_scientific_approval(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=self.setup(t)
   with patch.object(old,'get_topic',return_value=topic):candidate=c.validate(req,data,out)[3]
   self.assertNotIn('approved_for_draft',candidate);self.assertEqual(candidate['research_policy_version'],'claim-context-research-v1')
 def test_changed_predecessor_or_code_or_seed_blocks(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=self.setup(t)
   for key in ('code_binding','predecessor_request_sha256','predecessor_report_sha256','predecessor_receipt_sha256','context_seed_sha256'):
    bad=copy.deepcopy(req);bad[key]={} if key=='code_binding' else 'changed'
    with self.subTest(key=key),patch.object(old,'get_topic',return_value=topic),self.assertRaises(ValueError):c.validate(bad,data,out)
 def test_no_extra_budget_publication_search_reset(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=self.setup(t)
   for key,value in [('max_model_calls',4),('publication_authorized',True),('max_search_requests',1),('reset_original_attempts',True),('max_runs',2)]:
    with self.subTest(key=key),self.assertRaises(ValueError):c.validate(dict(req,**{key:value}),data,out)
 def test_late_predecessor_output_requires_reconciliation(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=self.setup(t);atomic_json(prior/'calls/context-annotation.raw.json',{})
   with patch.object(old,'get_topic',return_value=topic),self.assertRaisesRegex(ValueError,'predecessor_changed'):c.validate(req,data,out)
 def test_review_has_one_attempt_and_explicit_output_bound(self):
  base=Mock();c.BoundedReviewClient(base).text('prompt',attempts=9,max_tokens=14000,timeout=60)
  self.assertEqual(base.text.call_count,1);self.assertEqual(base.text.call_args.kwargs,{'attempts':1,'max_tokens':20000,'timeout':180})
 def test_failure_never_replays_or_changes_predecessor_and_strips_secrets(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=self.setup(t);before=c.protected_binding(data,out);reserve=Mock(return_value={'reserved':True});factory=Mock(return_value=Mock())
   env.update(AFP_WP_APP_PASSWORD='unused',FTP_PASSWORD='unused',AFP_SOURCE_SEARCH_API_KEY='unused')
   with patch.object(old,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(r,'review_candidate',side_effect=ValueError('stop')):
    result=c.run(env,data,out,client_factory=factory,reserve_fn=reserve);again=c.run(env,data,out,client_factory=factory,reserve_fn=reserve)
   self.assertEqual(before,c.protected_binding(data,out));self.assertTrue(result['originals_unchanged']);self.assertEqual(result['prior_model_calls_preserved'],9);self.assertEqual(result['post_mutations'],0);self.assertEqual(result['writer_calls'],0);self.assertEqual(result['search_requests'],0);self.assertEqual(again['status'],'claim_recheck_already_reserved_no_replay');self.assertEqual(factory.call_count,1);self.assertEqual(reserve.call_count,1)
   worker=factory.call_args.kwargs['env'];self.assertFalse(any(k.startswith('AFP_WP_') for k in worker));self.assertNotIn('FTP_PASSWORD',worker);self.assertNotIn('AFP_SOURCE_SEARCH_API_KEY',worker)
 def test_remote_duplicate_blocks_without_local_checkpoint(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=self.setup(t);factory=Mock()
   with patch.object(old,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None):result=c.run(env,data,out,client_factory=factory,reserve_fn=lambda *a:None)
   self.assertEqual(result['model_calls'],0);factory.assert_not_called()
 def test_reservation_is_exact_and_manual(self):
  env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':control.BRANCH,'GITHUB_RUN_ID':'123'};put=Mock(return_value=True)
  self.assertEqual(control.reserve('claim-policy-continuation',c.ID,env,put_fn=put)['request_id'],c.ID)
  with self.assertRaises(ValueError):control.reserve('claim-policy-continuation',old.ID,env,put_fn=put)
  with self.assertRaises(ValueError):control.reserve('claim-policy-continuation',c.ID,dict(env,GITHUB_EVENT_NAME='schedule'),put_fn=put)
 def test_wrong_event_blocks_before_any_model(self):
  reserve=Mock()
  with self.assertRaises(ValueError):c.run({},reserve_fn=reserve)
  reserve.assert_not_called()
 def test_positive_is_not_publication_authorization(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=self.setup(t)
   with patch.object(old,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(r,'review_candidate',return_value={'approved_facts':[]}),patch('automation.agri_v2.practical_drafting.normalize',return_value=({'content_html':'test'},{})),patch('automation.agri_v2.scoped_research.review_article'),patch.object(r,'review_region'):
    result=c.run(env,data,out,client_factory=Mock(return_value=Mock()),reserve_fn=lambda *a:{'reserved':True})
   self.assertEqual(result['status'],'claim_recheck_ready_for_publication_review');self.assertFalse(result['publication_authorized']);self.assertIn('fresh_authenticated_original_identity_and_bytes',result['next_required_gates'])
