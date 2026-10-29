import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_revision_recheck as c,regional_revision as r,regional_sources as regions
from automation.agri_v2.queue import load_json,atomic_json,utcnow
from automation.agri_v2.pipeline import digest
import test_regional_revision_context as fixture
class PreparedRevisionTests(unittest.TestCase):
 def setup(self,t):
  data,out,topic,env,root,oldreq,docs=fixture.RevisionContextTests().setup(t)
  prior={'status':'revision_needs_attention','total_revision_receipts':5};atomic_json(root/'continuations/alfalfa-revision-context-repair-v1/report.json',prior)
  for name in ['international-context-repair-extract','international-context-repair-fact-review']:
   raw={'untrusted_prior':name};atomic_json(root/'calls'/(name+'.raw.json'),raw);atomic_json(root/'calls'/(name+'.receipt.json'),{'status':'received','raw_sha256':digest(raw)})
  atomic_json(root/'search-plan.json',{'local_queries':['local first','local second']});atomic_json(root/'phases/local/new'/r.TOPIC/'lifecycle-evidence/sources.json',{'documents':[]});process={'local_queries':['local first','local second'],'local_document_urls':[],'local_gap':None,'scientific_acceptance':False};atomic_json(data/'regional-revision-local-process.json',process)
  candidate={'topic_id':r.TOPIC,'answers_intent':True,'local_prescription':False,'product_definition':'یونجه علوفه‌ای در مزرعه','outline':['سطح خاک','پایش رطوبت','حدود کاربرد'],'facts':[{'kind':'qualitative','claim':'پایش رطوبت خاک با بررسی وضعیت واقعی خاک انجام می‌شود.','conditions':'منبع دانشگاهی خارجی؛ حدود روش پایش حفظ شده و موعد یا مقدار آب محلی ارائه نمی‌شود.','evidence_id':'d0-e0','numeric_bindings':[]} for _ in range(4)]}
  proposal={'request_id':c.ID,'scientific_approval':False,'publication_authorized':False,'candidate':candidate,'article':{},'documents_sha256':digest(docs)};atomic_json(data/'alfalfa-scientific-proposal.json',proposal)
  req={'version':1,'request_id':c.ID,'revision_request_id':r.ID,'prepare_authorized':True,'publication_authorized':False,'max_remaining_model_calls':3,'max_search_requests':0,'max_rechecks':1,'reset_original_attempts':False,'proposal_sha256':digest(proposal),'context_report_sha256':digest(prior),'local_process_sha256':digest(process),'documents_sha256':digest(docs)};atomic_json(data/'alfalfa-scientific-recheck-request.json',req)
  return data,out,topic,env,root,req,proposal,docs
 def validate(self,req,data,out,topic):
  with patch.object(c,'get_topic',return_value=topic):return c.validate(req,data,out)
 def test_no_prior_scientific_approval_or_extra_budget_can_enter(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,proposal,docs=self.setup(t);self.assertEqual(len(self.validate(req,data,out,topic)[-1]),4)
   for key,v in [('publication_authorized',True),('max_remaining_model_calls',4),('max_search_requests',1),('reset_original_attempts',True)]:
    with self.assertRaises(ValueError):self.validate(dict(req,**{key:v}),data,out,topic)
 def test_unknown_prior_call_cannot_be_rechecked(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,proposal,docs=self.setup(t);atomic_json(root/'calls/international-context-repair-fact-review.receipt.json',{'status':'reserved'})
   with self.assertRaisesRegex(ValueError,'unknown_or_changed'):self.validate(req,data,out,topic)
 def test_spelled_out_measurement_cannot_masquerade_as_qualitative(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,proposal,docs=self.setup(t);proposal['candidate']['facts'][0]['claim']='آبیاری باید تا یک هفته پیش از برداشت یونجه قطع شده باشد.';atomic_json(data/'alfalfa-scientific-proposal.json',proposal);req['proposal_sha256']=digest(proposal)
   with self.assertRaisesRegex(ValueError,'disguised_measurement'):self.validate(req,data,out,topic)
 def test_failure_keeps_originals_no_search_and_no_replay(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,proposal,docs=self.setup(t);before=r.inputs(data,out);factory=Mock(return_value=Mock())
   with patch.object(c,'get_topic',return_value=topic),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(r,'review_candidate',side_effect=regions.RegionalBlocked('regional_applicability_not_approved')):
    result=c.run(env,data,out,client_factory=factory);again=c.run(env,data,out,client_factory=factory)
   self.assertEqual(result['status'],'revision_needs_attention');self.assertEqual(result['total_revision_receipts'],5);self.assertEqual(result['search_requests'],0);self.assertEqual(result['post_mutations'],0);self.assertEqual(before,r.inputs(data,out));self.assertEqual(again['status'],'prepared_recheck_already_reserved_no_replay');self.assertEqual(factory.call_count,1)
 def test_review_candidate_uses_full_used_documents_and_saves_actual_review(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,proposal,docs=self.setup(t);atomic_json(data/'briefs'/(r.TOPIC+'.json'),{'slug':'original-owned-slug'})
   from automation.agri_v2.scoped_research import validate_candidate
   facts=validate_candidate(topic,proposal['candidate'],docs);docs[0]['fetched_at']=utcnow()
   flags=['all_claims_supported','crop_species_and_product_match','answers_exact_intent','units_and_denominators_correct','geography_and_transfer_limits_retained','no_iranian_prescription_inferred','no_unsafe_input_rates','source_policy_satisfied','regional_sources_prioritized','international_transfer_limits_retained']
   value={k:True for k in flags};value.update(independent_sources=False,source_policy_version='university-single-source-v1',human_review_claimed=False,limitations='Only directly supported university guidance from the actual foreign setting; not an Iranian timing or water-rate prescription.',regional_research_version=regions.VERSION,regional_source_gap='Local official sources were searched first but did not support the exact pre-harvest decision method.',fact_checks=[{'fact_id':f['fact_id'],'supported':True,'scope_and_units_correct':True} for f in facts])
   client=Mock();client.text.return_value=value;ev=root/'new-review'
   brief=r.review_candidate(topic,proposal['candidate'],facts,docs,'prepared-qualitative',client,root/'new-calls',data,ev)
   self.assertFalse(brief['publish_authorized']);self.assertFalse(brief['overlap_review_done']);self.assertEqual(load_json(ev/'fact-review.json'),value);self.assertTrue(brief['revision_only'])
