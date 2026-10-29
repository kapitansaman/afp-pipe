import copy,tempfile,unittest
from unittest.mock import Mock,patch
from automation.agri_v2 import claim_policy_regional_final as c,regional_review_schema as strict,regional_revision as revision,parallel_control as control
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json
import test_claim_policy_continuation as fixtures

class RegionalFinalTests(unittest.TestCase):
 def request(self):return load_json(DATA/'alfalfa-claim-policy-regional-final-request.json')
 def test_real_saved_reviews_revalidate_without_any_network_or_model(self):
  article,brief,docs,topic=c.validate(self.request(),DATA,OUT)
  self.assertFalse(brief['publish_authorized']);self.assertEqual(len(brief['approved_facts']),4)
 def test_missing_or_changed_predecessor_binding_blocks(self):
  for key in ('article.json','brief.json','regional-review.raw.json','calls/persian-regional-review.receipt.json'):
   req=self.request();req['predecessor_files'][key]='changed'
   with self.subTest(key=key),self.assertRaises(ValueError):c.validate(req,DATA,OUT)
  req=self.request();req['predecessor_files'].pop('article.json')
  with self.assertRaises(ValueError):c.validate(req,DATA,OUT)
 def test_extra_budget_and_publication_are_forbidden(self):
  for key,value in [('max_model_calls',2),('publication_authorized',True),('max_search_requests',1),('reset_original_attempts',True),('max_runs',2)]:
   req=self.request();req[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):c.validate(req,DATA,OUT)
 def test_changed_code_or_original_request_blocks(self):
  for key in ('code_binding','original_request_sha256'):
   req=self.request();req[key]={} if key=='code_binding' else 'changed'
   with self.subTest(key=key),self.assertRaises(ValueError):c.validate(req,DATA,OUT)
 def test_strict_transport_requires_schema_and_no_retry(self):
  article,brief,docs,topic=c.validate(self.request(),DATA,OUT);base=Mock();c.BoundedReviewClient(base,brief['approved_facts']).text('prompt',attempts=9)
  kw=base.text.call_args.kwargs;self.assertEqual(kw['attempts'],1);self.assertEqual(kw['max_tokens'],20000);schema=kw['response_schema']
  self.assertIn('regional_review_schema_version',schema['required']);self.assertIn('rejection_reasons',schema['required']);self.assertFalse(schema['additionalProperties'])
  self.assertEqual(schema['properties']['applicable'],{'type':'boolean'})
  self.assertEqual(schema['properties']['fact_checks']['items']['properties']['supported'],{'type':'boolean'})
  quotes=schema['properties']['fact_checks']['items']['properties']['quote']['enum'];self.assertTrue(all(len(q.strip())>=80 for q in quotes))
 def test_short_quote_catalog_is_not_sent(self):
  with self.assertRaises(ValueError):strict.schema([{'fact_id':'f0','evidence_quote':'short'}])
 def test_exact_one_shot_remote_reservation_only(self):
  env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':control.BRANCH,'GITHUB_RUN_ID':'123'};put=Mock(return_value=True)
  self.assertEqual(control.reserve('claim-policy-regional-final',c.ID,env,put_fn=put)['request_id'],c.ID)
  with self.assertRaises(ValueError):control.reserve('claim-policy-regional-final',c.prior.ID,env,put_fn=put)
  with self.assertRaises(ValueError):control.reserve('claim-policy-regional-final',c.ID,dict(env,GITHUB_EVENT_NAME='schedule'),put_fn=put)
 def test_only_regional_stage_runs_and_originals_are_preserved(self):
  result_inputs=c.validate(self.request(),DATA,OUT)
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=fixtures.ContinuationTests().setup(t);atomic_json(data/'alfalfa-claim-policy-regional-final-request.json',self.request());before=c.protected_binding(data,out);factory=Mock(return_value=Mock());reserve=Mock(return_value={'reserved':True})
   with patch.object(c,'validate',return_value=result_inputs),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(revision,'review_region') as regional,patch.object(revision,'review_candidate') as scientific,patch('automation.agri_v2.scoped_research.review_article') as article:
    result=c.run(env,data,out,client_factory=factory,reserve_fn=reserve);again=c.run(env,data,out,client_factory=factory,reserve_fn=reserve)
   self.assertEqual(regional.call_count,1);scientific.assert_not_called();article.assert_not_called();self.assertEqual(result['status'],'claim_recheck_ready_for_publication_review');self.assertEqual(result['prior_model_calls_preserved'],12);self.assertFalse(result['publication_authorized']);self.assertEqual(before,c.protected_binding(data,out));self.assertEqual(again['status'],'claim_recheck_already_reserved_no_replay');self.assertEqual(factory.call_count,1)
 def test_negative_final_stays_blocked(self):
  inputs=c.validate(self.request(),DATA,OUT)
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,prior,req=fixtures.ContinuationTests().setup(t);atomic_json(data/'alfalfa-claim-policy-regional-final-request.json',self.request())
   with patch.object(c,'validate',return_value=inputs),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(revision,'review_region',side_effect=ValueError('negative')):
    result=c.run(env,data,out,client_factory=Mock(return_value=Mock()),reserve_fn=lambda *a:{'reserved':True})
   self.assertEqual(result['status'],'revision_needs_attention');self.assertEqual(result['post_mutations'],0);self.assertTrue(result['originals_unchanged'])
