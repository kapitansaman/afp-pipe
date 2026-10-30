import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_catalog_validation as r
from automation.agri_v2.queue import load_json,atomic_json
class CatalogValidationTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123'}
 def test_new_admission_bound_to_catalog_schema_and_all_old_outcomes(self):
  req=r.expected();r.validate(req);self.assertEqual(req['max_model_calls'],2);self.assertEqual(req['max_search_requests'],0);self.assertEqual(req['max_source_fetches'],0);self.assertEqual(req['review_wire_contract'],'regional-quote-catalog-v1')
  for k,v in [('request_id',r.base.ID),('max_model_calls',3),('max_model_calls_per_language',2),('languages',['ru-RU']),('previous_keyed_report_sha256','changed'),('response_schema_sha256',{}),('quote_catalog_sha256',{}),('protected_sha256','changed'),('reset_attempts',True),('promotion_authorized',True),('publication_authorized',True)]:
   with self.subTest(k=k),self.assertRaises(r.base.RecheckBlocked):r.validate(dict(req,**{k:v}))
 def test_prior_unknown_or_changed_result_cannot_be_reclassified(self):
  current=r.prior(r.OUT)
  for delta in [{'model_calls':1},{'originals_unchanged':False},{'status':'unknown'},{'results':[]},{'request_id':r.ID}]:
   with patch.object(r,'load_json',return_value=dict(current,**delta)),self.assertRaises(r.base.RecheckBlocked):r.prior(Path('/fixture'))
 def test_history_and_consumed_requests_remain_protected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/'config.json',{});before=r.manifest(data,out);atomic_json(data/r.REQUEST,{});atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{});self.assertEqual(before,r.manifest(data,out))
   for p in [out/'infrastructure-probes'/r.base.ID/'report.json',data/'regional-schema-recheck-request.json',out/'new/topic/review-queue/ar-IQ.json',out/'new/topic/regional-research/ar-IQ/continuation.json',out/'infrastructure-probes/unknown/languages/ar-IQ/review-1.receipt.json']:
    atomic_json(p,{'original':True});self.assertNotEqual(before,r.manifest(data,out));p.unlink()
 def test_only_exact_manual_remote_reservation(self):
  from automation.agri_v2.parallel_control import reserve
  self.assertIsNotNone(reserve('regional-catalog-validation',r.ID,self.env(),put_fn=lambda row:True))
  for ident,env in [(r.base.ID,self.env()),('retry-new-id',self.env()),(r.ID,dict(self.env(),GITHUB_EVENT_NAME='schedule')),(r.ID,dict(self.env(),GITHUB_REF_NAME='main'))]:
   with self.assertRaises(ValueError):reserve('regional-catalog-validation',ident,env,put_fn=lambda row:True)
 def test_unknown_or_completed_own_report_never_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});f=Mock();s=Mock();result=r.run(self.env(),out=out,client_factory=f,reserve_fn=s);self.assertEqual(result['model_calls'],0);f.assert_not_called();s.assert_not_called()
 def test_active_hold_stops_before_reservation_or_transport(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';atomic_json(data/r.REQUEST,{})
   with patch.object(r,'validate',return_value=(None,None,None,None)),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=True):
    f=Mock();s=Mock();result=r.run(self.env(),data=data,out=root/'out',client_factory=f,reserve_fn=s);self.assertEqual(result['model_calls'],0);f.assert_not_called();s.assert_not_called()
 def test_shared_executor_uses_separate_exact_admission_not_old_id(self):
  with patch.object(r.base,'execute',return_value={'status':'fixture'}) as ex:
   r.run(self.env());args=ex.call_args.args;self.assertEqual(args[5:7],(r.ID,r.REQUEST));self.assertEqual(args[-1],'regional-catalog-validation');self.assertIs(args[7],r.validate);self.assertIs(args[8],r.manifest);self.assertEqual(ex.call_args.kwargs,{'wire_contract':r.VERSION})

 def test_wire_phase_cannot_switch_historical_or_catalog_contract(self):
  for phase,wire in [('regional-catalog-validation','regional-keyed-facts-v1'),('regional-keyed-validation',r.VERSION),('regional-schema-recheck',r.VERSION)]:
   with self.subTest(phase=phase),self.assertRaises(r.base.RecheckBlocked):
    r.base.execute(self.env(),r.DATA,r.OUT,None,None,r.ID,r.REQUEST,r.validate,r.manifest,phase,wire_contract=wire)
 def test_two_negative_rechecks_keep_all_originals_and_never_promote(self):
  from automation.agri_v2.client import ModelClient
  from automation.agri_v2.parallel_pool import lease
  import json
  from automation.agri_v2.queue import utcnow
  from automation.agri_v2.post_hold_validation import ID as health_id
  article={'content_html':'<p>Current fixture observation only, not a recommendation for another location.</p>'};brief={'approved_facts':[{'fact_id':'f1'}]};docs={l:[{'id':'s0','url':'https://extension.example.edu/a','text':'Fixture document with complete technical context and retained conditions. This observation does not establish local applicability.'}] for l in r.base.LANGUAGES}
  verdict={'regional_review_schema_version':2,'applicable':False,'no_unsupported_local_prescription':True,'country_limits_retained':True,'fact_checks':[{'fact_id':'f1','supported':True,'document_id':'s0','quote':'Fixture document.','source_kind':'extension_guidance','country':'US','scope':'Fixture scope retained for this test only.','international_fallback':True,'local_evidence_gap':'Fixture gap','transfer_limits_retained':True}],'rejection_reasons':[{'flag':'applicable','fact_ids':['f1'],'claim_type':'source_observation','article_quote':'Current fixture observation','reason':'This fixture has insufficient evidence for applicability.'}]}
  class Base(ModelClient):
   def __init__(self,health,env,**k):self.env=env
   def request(self,kind,path,payload,timeout,attempts=None):
    with lease(self.env['AFP_PARALLEL_POOL_DB'],kind,['AGNES_API_KEY'],self.env['AFP_PARALLEL_TOPIC']):
     wire=dict(verdict,fact_checks={row['fact_id']:dict({k:v for k,v in row.items() if k not in ('fact_id','quote','document_id')},evidence_quote_id='d0p0') for row in verdict['fact_checks']},rejection_reasons=[dict({k:v for k,v in reason.items() if k!='article_quote'},article_quote_id='a0p0') for reason in verdict['rejection_reasons']]);return {'choices':[{'message':{'content':json.dumps(wire)}}]}
   def record_success(self,*a,**k):pass
  def factory(health,worker,root):return r.base.CountedClient(health,worker,root,base_class=Base)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';folder=out/'new/topic';atomic_json(data/r.REQUEST,{});atomic_json(out/'parallel/health/latest.json',{'checked_at':utcnow(),'eligible_text_slots':['AGNES_API_KEY']});atomic_json(out/'infrastructure-probes'/health_id/'health-passed.json',{'status':'passed','at':utcnow()});atomic_json(folder/'regional-research/ar-IQ/continuation.json',{'attempts':2,'status':'needs_attention'});before=r.manifest(data,out)
   with patch.object(r,'validate',return_value=(folder,article,brief,docs)),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False),patch('automation.agri_v2.source_search.search',side_effect=AssertionError('no search')),patch('automation.agri_v2.scoped_sources.fetch',side_effect=AssertionError('no fetch')):
    result=r.run(self.env(),data,out,client_factory=factory,reserve_fn=lambda e:True)
   self.assertEqual(result['model_calls'],2);self.assertEqual(result['request_receipts'],2);self.assertEqual([x['status'] for x in result['results']],['validated_negative']*2,result);self.assertTrue(result['originals_unchanged']);self.assertEqual(before,r.manifest(data,out));self.assertFalse(list((out/'infrastructure-probes'/r.ID).glob('languages/*/approved.json')));self.assertEqual(len(list((out/'infrastructure-probes'/r.ID).glob('languages/*/*.catalog.json'))),2)

 def test_stale_health_stops_before_reservation_and_never_refreshes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/r.REQUEST,{})
   from automation.agri_v2.post_hold_validation import ID as health_id
   atomic_json(out/'infrastructure-probes'/health_id/'health-passed.json',{'status':'passed','at':'2020-01-01T00:00:00Z'})
   atomic_json(out/'parallel/health/latest.json',{'checked_at':'2020-01-01T00:00:00Z'})
   with patch.object(r,'validate',return_value=(None,None,None,None)),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False):
    f=Mock();s=Mock()
    with self.assertRaises(r.base.RecheckBlocked):r.run(self.env(),data,out,client_factory=f,reserve_fn=s)
    f.assert_not_called();s.assert_not_called()
