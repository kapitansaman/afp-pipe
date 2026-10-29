import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import claim_policy_recheck as c,claim_policy as policy,regional_revision as revision,regional_sources as regions,parallel_control as control
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.pipeline import digest
import test_regional_revision_recheck as fixtures

class ClaimRecheckTests(unittest.TestCase):
 def setup(self,t):
  data,out,topic,env,old,oldreq,proposal,docs=fixtures.PreparedRevisionTests().setup(t)
  env['GITHUB_REF_NAME']=control.BRANCH
  prior={'status':'revision_needs_attention','model_calls':3,'total_revision_receipts':8}
  atomic_json(old/'continuations'/c.PRIOR/'report.json',prior)
  for name in ['prepared-qualitative-fact-review','article-evidence-review','persian-regional-review']:
   raw={'untrusted_prior':name};atomic_json(old/'calls'/(name+'.raw.json'),raw);atomic_json(old/'calls'/(name+'.receipt.json'),{'status':'received','raw_sha256':digest(raw)})
  req={'version':1,'request_id':c.ID,'topic_id':revision.TOPIC,'source_post_id':524204,'prepare_authorized':True,'publication_authorized':False,'max_model_calls':4,'max_search_requests':0,'max_runs':1,'reset_original_attempts':False,'policy_version':policy.VERSION,'code_binding':c.code_binding(),'prior_report_sha256':digest(prior),'proposal_sha256':digest(proposal),'documents_sha256':digest(docs),'local_process_sha256':digest(load_json(data/'regional-revision-local-process.json'))}
  atomic_json(data/'alfalfa-claim-policy-recheck-request.json',req)
  return data,out,topic,env,old,req,proposal,docs
 def annotation(self,candidate):
  return {'research_policy_version':policy.VERSION,'conflicts':[],'facts':[{'fact_index':i,'claim_type':'general_principle','study_context':{k:{'value':None,'quote':None} for k in policy.CONTEXT_FIELDS}} for i in range(len(candidate['facts']))]}
 def test_exact_request_and_eight_confirmed_old_calls(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t)
   with patch.object(c,'get_topic',return_value=topic):self.assertEqual(c.validate(req,data,out)[0],proposal)
 def test_no_publication_extra_budget_search_or_counter_reset(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t)
   for key,value in [('publication_authorized',True),('max_model_calls',5),('max_search_requests',1),('reset_original_attempts',True),('max_runs',2)]:
    with self.subTest(key=key),self.assertRaises(ValueError):c.validate(dict(req,**{key:value}),data,out)
 def test_code_and_inputs_are_hash_bound(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t)
   for key in ('code_binding','prior_report_sha256','proposal_sha256','documents_sha256','local_process_sha256'):
    bad=copy.deepcopy(req);bad[key]={} if key=='code_binding' else 'changed'
    with self.subTest(key=key),self.assertRaises(ValueError):c.validate(bad,data,out)
 def test_unknown_prior_outcome_blocks_before_new_calls(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);atomic_json(old/'calls/article-evidence-review.receipt.json',{'status':'reserved'})
   with self.assertRaisesRegex(ValueError,'uncertain_prior'):c.validate(req,data,out)
 def test_annotation_cannot_rewrite_claims_sources_or_original_candidate(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);original=copy.deepcopy(proposal['candidate']);raw=self.annotation(original);new=c.annotate(raw,original,topic,docs)
   self.assertEqual(original,proposal['candidate']);self.assertEqual(new['facts'][0]['claim'],original['facts'][0]['claim']);self.assertEqual(new['facts'][0]['evidence_id'],original['facts'][0]['evidence_id']);self.assertNotIn('approved_for_draft',new);self.assertEqual(new['review_schema_version'],2)
   raw['facts'][0]['claim']='fabrication'
   with self.assertRaises(ValueError):c.annotate(raw,original,topic,docs)
 def test_annotation_requires_every_exact_fact_once(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);raw=self.annotation(proposal['candidate']);raw['facts'][0]['fact_index']=1
   with self.assertRaises(ValueError):c.annotate(raw,proposal['candidate'],topic,docs)
 def test_annotation_invented_context_is_not_source_bound(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);raw=self.annotation(proposal['candidate']);raw['facts'][0]['study_context']['cultivar']={'value':'invented cultivar','quote':'invented cultivar trial'}
   with self.assertRaises(policy.PolicyBlocked):c.annotate(raw,proposal['candidate'],topic,docs)
 def test_wrong_event_or_branch_never_reserves(self):
  for env in ({},{'GITHUB_EVENT_NAME':'schedule','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_REF_NAME':control.BRANCH,'GITHUB_RUN_ID':'1'}):
   reserve=Mock()
   with self.assertRaises(ValueError):c.run(env,reserve_fn=reserve)
   reserve.assert_not_called()
 def test_remote_duplicate_blocks_even_without_local_report(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);factory=Mock();reserve=Mock(return_value=None)
   with patch.object(c,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None):result=c.run(env,data,out,client_factory=factory,reserve_fn=reserve)
   self.assertEqual(result['status'],'claim_recheck_already_reserved_no_replay');factory.assert_not_called();reserve.assert_called_once()
 def test_negative_preserves_originals_and_no_automatic_replay(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);before=c.protected_binding(data,out);factory=Mock(return_value=Mock());reserve=Mock(return_value={'reserved':True})
   env.update(AFP_WP_APP_PASSWORD='not-a-real-secret',AFP_WP_USERNAME='unused',AFP_SOURCE_SEARCH_API_KEY='unused',FTP_PASSWORD='unused')
   with patch.object(c,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch('automation.agri_v2.translation_review_repair.request',return_value=self.annotation(proposal['candidate'])),patch.object(revision,'review_candidate',side_effect=regions.RegionalBlocked('regional_applicability_not_approved')):
    result=c.run(env,data,out,client_factory=factory,reserve_fn=reserve);again=c.run(env,data,out,client_factory=factory,reserve_fn=reserve)
   self.assertEqual(result['status'],'revision_needs_attention');self.assertEqual(result['post_mutations'],0);self.assertEqual(result['search_requests'],0);self.assertTrue(result['originals_unchanged']);self.assertEqual(before,c.protected_binding(data,out));self.assertEqual(again['status'],'claim_recheck_already_reserved_no_replay');self.assertEqual(factory.call_count,1);self.assertEqual(reserve.call_count,1)
   worker=factory.call_args.kwargs['env'];self.assertFalse(any(k.startswith('AFP_WP_') for k in worker));self.assertNotIn('AFP_SOURCE_SEARCH_API_KEY',worker);self.assertNotIn('FTP_PASSWORD',worker)
 def test_interruption_is_fenced_locally_without_retry(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);reserve=Mock(return_value={'reserved':True})
   with patch.object(c,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch('automation.agri_v2.translation_review_repair.request',side_effect=KeyboardInterrupt()):
    with self.assertRaises(KeyboardInterrupt):c.run(env,data,out,client_factory=Mock(return_value=Mock()),reserve_fn=reserve)
   self.assertEqual(c.run(env,data,out,reserve_fn=reserve)['status'],'claim_recheck_already_reserved_no_replay');self.assertEqual(reserve.call_count,1)
 def test_only_exact_manual_request_can_obtain_durable_reservation(self):
  env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':control.BRANCH,'GITHUB_RUN_ID':'123'};put=Mock(return_value=True)
  row=control.reserve('claim-policy-recheck',c.ID,env,put_fn=put);self.assertEqual(row['request_id'],c.ID);self.assertEqual(row['published_posts'],0)
  for request,event in [(c.ID,'schedule'),('different-id','workflow_dispatch')]:
   with self.assertRaises(ValueError):control.reserve('claim-policy-recheck',request,dict(env,GITHUB_EVENT_NAME=event),put_fn=put)
 def test_ready_still_has_no_publication_and_requires_remaining_gates(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,old,req,proposal,docs=self.setup(t);brief={'approved_facts':[]};article={'content_html':'proposal'};reserve=Mock(return_value={'reserved':True})
   with patch.object(c,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch('automation.agri_v2.translation_review_repair.request',return_value=self.annotation(proposal['candidate'])),patch.object(revision,'review_candidate',return_value=brief),patch('automation.agri_v2.practical_drafting.normalize',return_value=(article,{})),patch('automation.agri_v2.scoped_research.review_article'),patch.object(revision,'review_region'):
    result=c.run(env,data,out,client_factory=Mock(return_value=Mock()),reserve_fn=reserve)
   self.assertEqual(result['status'],'claim_recheck_ready_for_publication_review');self.assertFalse(result['publication_authorized']);self.assertEqual(result['writer_calls'],0);self.assertIn('image_binding_and_visual_review',result['next_required_gates'])
