import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_schema_recheck as r
from automation.agri_v2.regional_sources import response_schema
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.healthcheck import TEXT_MODEL

class SchemaRecheckTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123'}
 def test_exact_current_inputs_and_two_call_contract(self):
  req=r.expected();self.assertEqual(req['max_model_calls'],2);self.assertEqual(req['max_search_requests'],0);self.assertEqual(req['max_source_fetches'],0)
  r.validate(req)
  for k,v in [('languages',['ru-RU']),('max_model_calls',3),('reset_attempts',True),('publication_authorized',True),('promotion_authorized',True),('protected_sha256','changed'),('code_sha256','changed')]:
   with self.subTest(k=k),self.assertRaises(r.RecheckBlocked):r.validate(dict(req,**{k:v}))
 def test_admission_file_does_not_hash_itself(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/'config.json',{'x':1});before=r.manifest(data,out);atomic_json(data/'regional-schema-recheck-request.json',{'arbitrary':True});self.assertEqual(before,r.manifest(data,out))
 def test_all_history_queues_documents_and_unknowns_are_immutable(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/'config.json',{});before=r.manifest(data,out);atomic_json(out/'infrastructure-probes'/r.ID/'languages/ar-IQ/approved.json',{});self.assertEqual(before,r.manifest(data,out))
   for path in ['new/topic/article.json','new/topic/review-queue/ar-IQ.json','new/topic/regional-research/ar-IQ/continuation.json','infrastructure-probes/old/languages/ar-IQ/review-1.receipt.json']:
    atomic_json(out/path,{'reserved':True});self.assertNotEqual(before,r.manifest(data,out));(out/path).unlink()
 def test_only_exact_manual_reservation(self):
  from automation.agri_v2.parallel_control import reserve
  self.assertIsNotNone(reserve('regional-schema-recheck',r.ID,self.env(),put_fn=lambda x:True))
  for env,ident in [(dict(self.env(),GITHUB_EVENT_NAME='schedule'),r.ID),(self.env(),'new-id'),(dict(self.env(),GITHUB_REF_NAME='main'),r.ID)]:
   with self.assertRaises(ValueError):reserve('regional-schema-recheck',ident,env,put_fn=lambda x:True)
 def client(self,root,error=None):
  class Base:
   def __init__(self,*a,**k):self.calls=0
   def request(self,*a,**k):
    self.calls+=1;self.attempts=k['attempts']
    if error:raise error
    return {'choices':[]}
  c=r.CountedClient({}, {},root,base_class=Base);c.recheck_language='ar-IQ';c.expected_response_format={'type':'json_schema','json_schema':{'strict':True}};return c
 def payload(self):return {'model':TEXT_MODEL,'max_tokens':14000,'messages':[],'response_format':{'type':'json_schema','json_schema':{'strict':True}}}
 def test_unknown_is_reserved_once_never_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d),TimeoutError())
   with self.assertRaises(TimeoutError):c.request('text','/chat/completions',self.payload(),180,attempts=9)
   with self.assertRaises(r.RecheckBlocked):c.request('text','/chat/completions',self.payload(),180)
   self.assertEqual((c.calls,c.attempts),(1,1));self.assertEqual(load_json(Path(d)/'calls/ar-IQ.json')['status'],'reserved')
 def test_one_call_per_language_and_two_total(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d))
   for l in r.LANGUAGES:
    c.recheck_language=l;c.request('text','/chat/completions',self.payload(),180)
    with self.assertRaises(r.RecheckBlocked):c.request('text','/chat/completions',self.payload(),180)
   self.assertEqual(c.calls,2)
 def test_wrong_languages_transport_and_schema_rejected_without_call(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d))
   for l,k,p in [('ru-RU','text','/chat/completions'),('tg-TJ','text','/chat/completions'),('ar-IQ','image','/images/generations'),('en-US','text','/posts')]:
    c.recheck_language=l
    with self.assertRaises(r.RecheckBlocked):c.request(k,p,self.payload(),180)
   c.recheck_language='ar-IQ';payload=self.payload();payload['response_format']={'type':'json_object'}
   with self.assertRaises(r.RecheckBlocked):c.request('text','/chat/completions',payload,180)
   self.assertEqual(c.calls,0)
 def test_preexisting_unknown_report_stops_all_work(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});f=Mock();s=Mock();result=r.run(self.env(),out=out,client_factory=f,reserve_fn=s);self.assertEqual(result['model_calls'],0);f.assert_not_called();s.assert_not_called()
 def test_hold_stops_before_reservation(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'validate',return_value=(None,None,None,None)),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=True):
   atomic_json(Path(d)/'data/regional-schema-recheck-request.json',{});f=Mock();s=Mock();res=r.run(self.env(),data=Path(d)/'data',out=Path(d),client_factory=f,reserve_fn=s);self.assertEqual(res['model_calls'],0);f.assert_not_called();s.assert_not_called()
 def test_native_shape_cannot_replace_server_guard(self):
  schema=response_schema('regional-evidence-review-fallback',{'_role_skill':'evidence-reviewer','approved_facts':[{'fact_id':'f1'}],'documents':[{'id':'s0','text':'fixture'}]})
  value={'regional_review_schema_version':2,'applicable':True,'no_unsupported_local_prescription':True,'country_limits_retained':True,'rejection_reasons':[],'fact_checks':[{'fact_id':'f1','supported':False,'document_id':None,'quote':'','source_kind':'news','country':None,'scope':'','international_fallback':False,'local_evidence_gap':'','transfer_limits_retained':False}]}
  r.validate_wire(value,schema)
  for change in [dict(value,regional_review_schema_version=True),dict(value,extra=1),{k:v for k,v in value.items() if k!='rejection_reasons'},dict(value,fact_checks=[])]:
   with self.assertRaises(r.RecheckBlocked):r.validate_wire(change,schema)
  from automation.agri_v2.claim_policy import validate_regional_objections,PolicyBlocked
  with self.assertRaises(PolicyBlocked):validate_regional_objections(value,{},[{'fact_id':'f1'}])
 def test_source_hash_tamper_blocks_before_any_request(self):
  from automation.agri_v2 import regional_sources
  with patch.object(regional_sources,'documents_for',return_value=[]):
   with self.assertRaises(r.RecheckBlocked):r.selected()
 def test_two_negative_rechecks_keep_all_originals_and_never_promote(self):
  from automation.agri_v2.client import ModelClient
  from automation.agri_v2.parallel_pool import lease
  import json
  from automation.agri_v2.queue import utcnow
  from automation.agri_v2.post_hold_validation import ID as health_id
  article={'content_html':'<p>Current fixture observation only.</p>'};brief={'approved_facts':[{'fact_id':'f1'}]};docs={l:[{'url':'https://extension.example.edu/a','text':'Fixture document.'}] for l in r.LANGUAGES}
  verdict={'regional_review_schema_version':2,'applicable':False,'no_unsupported_local_prescription':True,'country_limits_retained':True,'fact_checks':[{'fact_id':'f1','supported':True,'document_id':'s0','quote':'Fixture document.','source_kind':'extension_guidance','country':'US','scope':'Fixture scope','international_fallback':True,'local_evidence_gap':'Fixture gap','transfer_limits_retained':True}],'rejection_reasons':[{'flag':'applicable','fact_ids':['f1'],'claim_type':'source_observation','article_quote':'Current fixture observation','reason':'This fixture has insufficient evidence for applicability.'}]}
  class Base(ModelClient):
   def __init__(self,health,env,**k):self.env=env
   def request(self,kind,path,payload,timeout,attempts=None):
    with lease(self.env['AFP_PARALLEL_POOL_DB'],kind,['AGNES_API_KEY'],self.env['AFP_PARALLEL_TOPIC']):return {'choices':[{'message':{'content':json.dumps(verdict)}}]}
   def record_success(self,*a,**k):pass
  def factory(health,worker,root):return r.CountedClient(health,worker,root,base_class=Base)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';folder=out/'new/topic';atomic_json(data/'regional-schema-recheck-request.json',{});atomic_json(out/'parallel/health/latest.json',{'checked_at':utcnow(),'eligible_text_slots':['AGNES_API_KEY']});atomic_json(out/'infrastructure-probes'/health_id/'health-passed.json',{'status':'passed','at':utcnow()});atomic_json(folder/'regional-research/ar-IQ/continuation.json',{'attempts':2,'status':'needs_attention'});before=r.manifest(data,out)
   with patch.object(r,'validate',return_value=(folder,article,brief,docs)),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False),patch('automation.agri_v2.source_search.search',side_effect=AssertionError('no search')),patch('automation.agri_v2.scoped_sources.fetch',side_effect=AssertionError('no fetch')):
    result=r.run(self.env(),data,out,client_factory=factory,reserve_fn=lambda e:True)
   self.assertEqual(result['model_calls'],2);self.assertEqual(result['request_receipts'],2);self.assertEqual([x['status'] for x in result['results']],['validated_negative']*2);self.assertTrue(result['originals_unchanged']);self.assertEqual(before,r.manifest(data,out));self.assertFalse(list((out/'infrastructure-probes'/r.ID).glob('languages/*/approved.json')))
