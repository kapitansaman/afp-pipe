import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_sources as r,family_lifecycle as f,language_review_queue as q
from automation.agri_v2.failure_diagnostics import failure_details
from automation.agri_v2.queue import atomic_json,load_json
import test_regional_sources as source_tests
import test_family_lifecycle as lifecycle_tests
class RegionalReviewContractTests(unittest.TestCase):
 def test_audience_is_not_all_country_experimental_coverage(self):
  for lang,country in [('en-US','US'),('ar-IQ','EG')]:
   c=r.review_contract(lang);self.assertIn(country,c['audience_countries']);self.assertIn('NOT a requirement',c['audience_semantics']);self.assertIn('EVERY',c['audience_semantics']);self.assertIn('disclaimer',c['transfer_check']);self.assertIn('decision table',c['transfer_check'])
 def test_both_local_and_fallback_receive_contract_and_complete_article(self):
  factory=source_tests.RegionalSourcesTests()
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=factory.data(root);a={'content_html':'<table>Untrusted prescription</table>','excerpt':'Untrusted excerpt','faq':[{'answer':'Untrusted answer'}]};doc=factory.doc('https://example.edu/x');client=Mock();client.text.side_effect=[{'applicable':False},factory.verdict(doc)]
   with patch.object(r,'collect',return_value=[doc]):r.local_research(factory.topic(),a,factory.brief(),'en-US',client,data,root,root/'family',root/'attempt',4)
   self.assertEqual(client.text.call_count,2)
   for call in client.text.call_args_list:
    payload=json.loads(call.args[0]);self.assertEqual(payload['article'],a);self.assertEqual(payload['review_contract'],r.review_contract('en-US'));self.assertEqual(payload['documents'][0]['id'],'s0');self.assertEqual(payload['approved_facts'],factory.brief()['approved_facts'])
 def test_one_us_source_can_support_bounded_english_observation_but_not_false_verdict(self):
  factory=source_tests.RegionalSourcesTests();d=factory.doc('https://example.edu/x');v=factory.verdict(d)
  self.assertEqual(r.validate_local_review(v,{},factory.brief(),[d],'en-US'),[d['url']])
  v['applicable']=False
  with self.assertRaises(r.RegionalBlocked):r.validate_local_review(v,{},factory.brief(),[d],'en-US')
 def test_arabic_foreign_fallback_still_requires_gap_and_limits(self):
  factory=source_tests.RegionalSourcesTests();d=factory.doc('https://example.edu/x');v=factory.verdict(d)
  for key,value in [('international_fallback',False),('local_evidence_gap',''),('transfer_limits_retained',False)]:
   bad=copy.deepcopy(v);bad['fact_checks'][0][key]=value
   with self.assertRaises(r.RegionalBlocked):r.validate_local_review(bad,{},factory.brief(),[d],'ar-IQ')
 def test_diagnostics_are_exact_codes_never_arbitrary_exception_text(self):
  self.assertEqual(failure_details(r.RegionalBlocked('regional_applicability_not_approved'))['category'],'regional_applicability_not_approved')
  self.assertEqual(failure_details(r.RegionalBlocked('secret or provider response'))['category'],'unspecified')
 def setup_source(self,t,status='validated',verified=True):
  data,out,topic,env,health=lifecycle_tests.FamilyLifecycleTests().setup(t);cfg=load_json(data/'config.json');cfg['multilingual']={'enabled':True,'independent_publication':True};atomic_json(data/'config.json',cfg);folder=out/'new'/topic['id'];atomic_json(folder/'wordpress-receipt.json',{'topic_id':topic['id'],'public_verified':verified,'post_id':125});atomic_json(f.row_path(folder,'publish'),{'attempts':3,'status':status,'history':[{'attempts':3}]});return data,out,topic,folder
 def test_verified_source_does_not_spend_or_reset_original_budget(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder=self.setup_source(t);p=f.row_path(folder,'publish');before=p.read_bytes();wp=Mock()
   with patch.object(f,'publish_ready') as publish:result=f.publish_source_or_queue(wp,topic,'new',data,out)
   self.assertEqual(result['status'],'source_checkpoint_retained');self.assertFalse(result['live_verification_performed']);self.assertEqual(result['published_posts'],0);self.assertEqual(before,p.read_bytes());publish.assert_not_called();wp.call.assert_not_called()
 def test_unverified_or_wrong_source_cannot_obtain_a_new_publish_budget(self):
  for wrong in [False,True]:
   with tempfile.TemporaryDirectory() as t:
    data,out,topic,folder=self.setup_source(t,verified=wrong)
    if wrong:atomic_json(folder/'wordpress-receipt.json',{'topic_id':'another-topic','public_verified':True,'post_id':125})
    with patch.object(f,'publish_ready') as publish:result=f.publish_source_or_queue(Mock(),topic,'new',data,out)
    self.assertEqual(result['status'],'stage_budget_exhausted');publish.assert_not_called();self.assertEqual(f.state(folder,'publish')['attempts'],3)
 def test_uncertain_original_is_not_bypassed_even_with_verified_receipt(self):
  for status in ['reserved','reconciliation_required']:
   with tempfile.TemporaryDirectory() as t:
    data,out,topic,folder=self.setup_source(t,status)
    with patch.object(f,'publish_ready') as publish:result=f.publish_source_or_queue(Mock(),topic,'new',data,out)
    self.assertEqual(result['status'],'stage_reconciliation_required');publish.assert_not_called()
 def test_unpublished_source_retains_original_three_attempt_ceiling(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder=self.setup_source(t);(folder/'wordpress-receipt.json').unlink()
   with patch.object(f,'publish_ready') as publish:result=f.publish_source_or_queue(Mock(),topic,'new',data,out)
   self.assertEqual(result['status'],'stage_budget_exhausted');publish.assert_not_called()

 def test_coordinator_does_not_publish_approved_language_with_missing_regional_proof(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder=self.setup_source(t);env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'100'};wp=Mock()
   from automation.agri_v2.queue import utcnow
   wp.inventory.return_value={'source_generated_at':utcnow(),'scope':'all public posts','records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   atomic_json(q.path(folder,'en-US'),{'topic_id':topic['id'],'language':'en-US','status':'approved'})
   def worker(topic,workspace,*args):return topic['id'],workspace/'data',workspace/'out',{'topic_id':topic['id'],'status':'publication_ready'}
   before=f.row_path(folder,'publish').read_bytes()
   with patch.object(f,'allocate',return_value={}),patch.object(f,'assigned_topics',return_value=[topic]),patch.object(f,'next_stage',return_value=('publish',None)),patch.object(f,'publish_ready') as publish,patch.object(q,'process_due',return_value={'status':'not_due','model_calls':0}),patch.object(q,'regional_ready',return_value=False):
    result=f.run(env,data,out,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   publish.assert_not_called();self.assertEqual(result['published_posts'],0);self.assertEqual(result['publication_results'][0]['status'],'source_checkpoint_retained');self.assertEqual(before,f.row_path(folder,'publish').read_bytes())
