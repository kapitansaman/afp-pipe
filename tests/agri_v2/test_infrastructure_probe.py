import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import infrastructure_probe as p,quality_index as q,scoped_research as s
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json,utcnow
from automation.agri_v2.parallel_control import REPO,BRANCH
from tests.agri_v2.test_practical_drafting import fixture

class InfrastructureProbeTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REPOSITORY':REPO,'GITHUB_REF_NAME':BRANCH,'GITHUB_RUN_ID':'123'}
 def grade(self,good=True):
  return {'quality_policy':q.VERSION,'dimensions':dict(q.DIMENSIONS) if good else dict.fromkeys(q.DIMENSIONS,0),'critical_issues':[],'reason':'Fixture assessment of actual candidate usefulness and source fidelity, not production approval.'}
 def test_real_bound_request_and_unpublished_input(self):
  # Consumed production request remains historical; no live reauthorization.
  request=load_json(DATA/'infrastructure-probe-request.json')
  with self.assertRaises(p.ProbeBlocked):p.validate(request)
  topic,brief=p.select();test_request=dict(request,code_sha256=p.code_hash())
  t,b=p.validate(test_request);self.assertFalse((OUT/'new'/t['id']/'wordpress-receipt.json').exists());self.assertEqual(b['review_mode'],'automated_scoped_evidence_review_v1')
 def test_no_budget_expansion_or_changed_source(self):
  r=load_json(DATA/'infrastructure-probe-request.json')
  for key,value in [('max_model_calls',5),('max_repairs',2),('max_image_calls',1),('publication_authorized',True),('schedule_enabled',True),('reset_attempts',True),('brief_sha256','changed'),('code_sha256','changed')]:
   with self.subTest(key=key),self.assertRaises(p.ProbeBlocked):p.validate(dict(r,**{key:value}))
 def test_wrong_event_branch_repo_and_native_env_block(self):
  for key,value in [('GITHUB_ACTIONS','false'),('GITHUB_EVENT_NAME','push'),('GITHUB_REF_NAME','main'),('GITHUB_REPOSITORY','wrong/repo'),('GITHUB_RUN_ID','x')]:
   with self.subTest(key=key),self.assertRaises(p.ProbeBlocked):p.identity(dict(self.env(),**{key:value}))
 def test_missing_reservation_token_sends_no_network(self):
  with patch.object(p.urllib.request,'build_opener') as opener:
   with self.assertRaises(p.ProbeBlocked):p.reserve(self.env())
   opener.assert_not_called()
 def test_reservation_is_create_only_and_duplicate_is_not_replayed(self):
  import urllib.error
  error=urllib.error.HTTPError('https://api.github.com',422,'already exists',{},None);opener=Mock();opener.open.side_effect=error
  with patch.object(p.urllib.request,'build_opener',return_value=opener):self.assertFalse(p.reserve(dict(self.env(),GITHUB_TOKEN='private-fixture')))
  request=opener.open.call_args.args[0];body=json.loads(request.data);self.assertNotIn('sha',body);self.assertEqual(body['branch'],BRANCH);self.assertEqual(request.method,'PUT')
 def client(self,root,result=None,error=None):
  class Base:
   def __init__(self,*args,**kwargs):self.kwargs=kwargs;self.calls=0
   def request(self,*args,**kwargs):
    self.calls+=1;self.last_attempts=kwargs['attempts']
    if error:raise error
    return {'choices':[]} if result is None else result
  return p.CountedClient({},self.env(),root,base_class=Base)
 def payload(self):
  from automation.agri_v2.healthcheck import TEXT_MODEL
  return {'model':TEXT_MODEL,'max_tokens':7500,'messages':[{'role':'user','content':'fixture'}]}
 def test_transport_allows_one_attempt_and_no_same_stage_replay(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d));c.probe_stage='writer';c.request('text','/chat/completions',self.payload(),180,attempts=9);self.assertEqual(c.last_attempts,1)
   with self.assertRaises(p.ProbeBlocked):c.request('text','/chat/completions',self.payload(),180)
   self.assertEqual(c.calls,1)
 def test_unknown_outcome_reserved_and_never_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);c=self.client(root,error=TimeoutError());c.probe_stage='writer'
   with self.assertRaises(TimeoutError):c.request('text','/chat/completions',self.payload(),180)
   self.assertEqual(load_json(root/'calls/writer.json')['status'],'reserved')
   with self.assertRaises(p.ProbeBlocked):c.request('text','/chat/completions',self.payload(),180)
   self.assertEqual(c.calls,1)
 def test_no_image_other_endpoint_unbounded_output_or_large_prompt(self):
  cases=[('image','/images/generations',self.payload()),('text','/wrong',self.payload()),('text','/chat/completions',dict(self.payload(),max_tokens=14001)),('text','/chat/completions',dict(self.payload(),max_tokens=True)),('text','/chat/completions',dict(self.payload(),messages=['x'*200001]))]
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d));c.probe_stage='writer'
   for kind,path,body in cases:
    with self.assertRaises(p.ProbeBlocked):c.request(kind,path,body,180)
   self.assertEqual(c.calls,0)
 def test_at_most_four_distinct_stages(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d))
   for stage in p.STAGES:c.probe_stage=stage;c.request('text','/chat/completions',self.payload(),180)
   c.probe_stage='fifth'
   with self.assertRaises(p.ProbeBlocked):c.request('text','/chat/completions',self.payload(),180)
   self.assertEqual(c.calls,4)
 def setup_run(self,tmp):
  data=Path(tmp)/'data';out=Path(tmp)/'out';atomic_json(data/'infrastructure-probe-request.json',{});atomic_json(out/'parallel/health/latest.json',{'checked_at':utcnow(),'eligible_text_slots':['AGNES_API_KEY']});t,b,a=fixture();return data,out,t,b,a
 def test_existing_report_or_remote_duplicate_never_calls_model(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,t,b,a=self.setup_run(d);factory=Mock();reserve=Mock(return_value=False)
   with patch.object(p,'validate',return_value=(t,b)),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None):r=p.run(self.env(),data,out,client_factory=factory,reserve_fn=reserve)
   self.assertEqual(r['status'],'probe_already_reserved_no_replay');factory.assert_not_called()
   atomic_json(out/'infrastructure-probes'/p.ID/'report.json',{'status':'reserved'})
   r=p.run(self.env(),data,out,client_factory=factory,reserve_fn=reserve);self.assertEqual(reserve.call_count,1)
 def test_model_gets_only_model_keys_and_minimal_identity(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,t,b,a=self.setup_run(d);factory=Mock(return_value=Mock());env=dict(self.env(),AGNES_API_KEY='fixture',AFP_WP_APP_PASSWORD='private',GITHUB_TOKEN='private',FTP_PASSWORD='private',AFP_SOURCE_SEARCH_API_KEY='private')
   with patch.object(p,'validate',return_value=(t,b)),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(p,'stages',side_effect=TimeoutError()):r=p.run(env,data,out,client_factory=factory,reserve_fn=lambda e:True)
   worker=factory.call_args.args[1];self.assertFalse(set(worker)&{'AFP_WP_APP_PASSWORD','GITHUB_TOKEN','FTP_PASSWORD','AFP_SOURCE_SEARCH_API_KEY'});self.assertTrue(r['originals_unchanged']);self.assertEqual(r['site_calls'],0);self.assertEqual(r['status'],'probe_text_cycle_blocked')
 def test_successful_review_does_not_manufacture_a_repair(self):
  t,b,a=fixture();client=Mock();report={'steps':[],'repair_exercised':False}
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   with patch('automation.agri_v2.practical_drafting.generate',return_value=a),patch.object(s,'review_article'),patch.object(q,'bound',return_value={'accepted':True,'score':90}),patch.object(q,'repair') as repair:p.stages(client,t,b,folder,report)
   repair.assert_not_called();self.assertFalse(report['repair_exercised']);self.assertEqual(report['status'],'probe_text_cycle_passed');self.assertEqual([r['stage'] for r in report['steps']],['writer','review'])
 def test_negative_review_is_archived_then_one_repair_independent_recheck(self):
  t,b,a=fixture();client=Mock();report={'steps':[],'repair_exercised':False};seen=[]
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   def review(*args):
    seen.append(client.probe_stage)
    if len(seen)==1:
     atomic_json(folder/'article-evidence-review.raw.json',self.grade(False));raise s.EvidenceBlocked('article_quality_below_publication_threshold')
   with patch('automation.agri_v2.practical_drafting.generate',return_value=a),patch.object(s,'review_article',side_effect=review),patch.object(q,'bound',side_effect=[{'accepted':False,'score':50},{'accepted':True,'score':90}]),patch.object(q,'repair') as repair:p.stages(client,t,b,folder,report)
   repair.assert_called_once();self.assertEqual(seen,['review','recheck']);self.assertTrue((folder/'initial-review/article-evidence-review.raw.json').exists());self.assertTrue(report['repair_exercised']);self.assertEqual(report['status'],'probe_text_cycle_passed')
 def test_negative_recheck_stays_negative_no_second_repair(self):
  t,b,a=fixture();report={'steps':[],'repair_exercised':False}
  with tempfile.TemporaryDirectory() as d,patch('automation.agri_v2.practical_drafting.generate',return_value=a),patch.object(s,'review_article',side_effect=s.EvidenceBlocked('article_quality_below_publication_threshold')),patch.object(q,'bound',return_value={'accepted':False,'score':50}),patch.object(q,'repair') as repair:
   with self.assertRaises(s.EvidenceBlocked):p.stages(Mock(),t,b,Path(d),report)
   repair.assert_called_once();self.assertTrue(report['repair_exercised'])
 def test_production_files_are_protected_not_only_one_topic(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,t,b,a=self.setup_run(d);atomic_json(out/'new/other/article.json',a);before=p.protected(data,out);atomic_json(out/'new/other/article.json',dict(a,excerpt='changed'));self.assertNotEqual(p.protected(data,out),before)

 def test_real_probe_constructor_uses_central_keys_only(self):
  from automation.agri_v2.family_keys import slots_for
  from automation.agri_v2.parallel_pool import SLOTS
  health=load_json(OUT/'parallel/health/latest.json');health['checked_at']=utcnow()
  env={slot:'synthetic-distinct-'+slot for slot in SLOTS}
  env.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB='unused-offline-fixture',AFP_PARALLEL_FAMILY='isolated-infrastructure-probe',AFP_PARALLEL_TOPIC='offline-fixture')
  with tempfile.TemporaryDirectory() as d,patch('socket.socket',side_effect=AssertionError('network forbidden')):
   client=p.CountedClient(health,env,Path(d))
  central=set(slots_for('isolated-infrastructure-probe')[0])
  self.assertEqual(central,set(SLOTS[80:]));self.assertTrue(client.keys['text'])
  self.assertEqual({slot for slot,_ in client.keys['text']},central.intersection(health['eligible_text_slots']))
  self.assertFalse({slot for slot,_ in client.keys['text']}.intersection(SLOTS[:80]))

 def test_probe_never_borrows_production_keys_when_central_missing(self):
  from automation.agri_v2.parallel_pool import SLOTS
  from automation.agri_v2.family_keys import FamilyCapabilityRequired
  health=load_json(OUT/'parallel/health/latest.json');health['checked_at']=utcnow()
  env={slot:'synthetic-distinct-'+slot for slot in SLOTS[:80]}
  env.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB='unused-offline-fixture',AFP_PARALLEL_FAMILY='isolated-infrastructure-probe')
  with tempfile.TemporaryDirectory() as d,patch('socket.socket',side_effect=AssertionError('network forbidden')):
   with self.assertRaises(FamilyCapabilityRequired):p.CountedClient(health,env,Path(d))

 def test_admission_error_has_safe_explicit_diagnostic(self):
  from automation.agri_v2.client import CapabilityError
  from automation.agri_v2.failure_diagnostics import failure_details
  self.assertEqual(failure_details(CapabilityError('Known family or explicitly scoped central worker required')),{'kind':'capability_or_protocol','category':'worker_scope_not_admitted'})
  self.assertEqual(failure_details(CapabilityError('secret-like-untrusted-detail'))['category'],'unspecified')

 def test_consumed_remote_reservation_and_zero_calls_report_preserved(self):
  receipt=load_json(DATA/'status/parallel-reservations'/(p.ID+'.json'))
  report=load_json(OUT/'infrastructure-probes'/p.ID/'report.json')
  self.assertEqual(receipt['run_id'],report['run_id']);self.assertEqual(report['model_calls'],0)
  self.assertEqual(report['status'],'probe_text_cycle_blocked');self.assertTrue(report['originals_unchanged'])

 def test_continuation_is_distinct_code_bound_and_does_not_rebind_old_request(self):
  topic,brief=p.select();request=p.expected(topic,brief,p.CONTINUATION_ID)
  p.validate(request,request_id=p.CONTINUATION_ID)
  with self.assertRaises(p.ProbeBlocked):p.validate(request)
  with self.assertRaises(p.ProbeBlocked):p.expected(topic,brief,'arbitrary-new-budget')
  self.assertNotEqual(p.REQUESTS[p.ID],p.REQUESTS[p.CONTINUATION_ID])
  self.assertEqual(request['max_model_calls'],4);self.assertFalse(request['publication_authorized'])

 def test_continuation_protects_prior_negative_report(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,t,b,a=self.setup_run(d);prior=out/'infrastructure-probes'/p.ID/'report.json';atomic_json(prior,{'status':'probe_text_cycle_blocked'})
   before=p.protected(data,out,p.CONTINUATION_ID);atomic_json(prior,{'status':'tampered'})
   self.assertNotEqual(before,p.protected(data,out,p.CONTINUATION_ID))

 def test_real_preflight_is_network_free_and_checks_owned_central_slots(self):
  from automation.agri_v2.parallel_pool import SLOTS
  health=load_json(OUT/'parallel/health/latest.json');health['checked_at']=utcnow()
  env={slot:'synthetic-distinct-'+slot for slot in SLOTS};env.update(self.env())
  with patch('socket.socket',side_effect=AssertionError('network forbidden')):result=p.preflight(env,health)
  self.assertTrue(result['eligible_owned_text_slots']);self.assertTrue(set(result['eligible_owned_text_slots'])<=set(SLOTS[80:]));self.assertEqual(result['transport_calls'],0)

 def test_failed_preflight_does_not_consume_remote_reservation(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,t,b,a=self.setup_run(d);reserve=Mock()
   with patch.object(p,'validate',return_value=(t,b)),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(p,'preflight',side_effect=p.ProbeBlocked('fixture-preflight')):
    with self.assertRaises(p.ProbeBlocked):p.run(self.env(),data,out,reserve_fn=reserve)
   reserve.assert_not_called();self.assertFalse((out/'infrastructure-probes'/p.ID/'report.json').exists())

 def test_actual_writer_prompt_reaches_bounded_transport_without_network(self):
  from automation.agri_v2.parallel_pool import SLOTS,initialize,snapshot
  from automation.agri_v2.client import ModelClient
  from automation.agri_v2.role_skills import RoleClient
  from automation.agri_v2.practical_drafting import generate
  health=load_json(OUT/'parallel/health/latest.json');health['checked_at']=utcnow();topic,brief=p.select()
  class TransportStopped(Exception):pass
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);db=root/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=4,per_worker=4)
   env={slot:'synthetic-distinct-'+slot for slot in SLOTS};env.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_FAMILY='isolated-infrastructure-probe',AFP_PARALLEL_TOPIC=topic['id'])
   client=p.CountedClient(health,env,root);client.probe_stage='writer'
   with patch.object(ModelClient,'request',side_effect=TransportStopped()) as transport,patch('socket.socket',side_effect=AssertionError('network forbidden')):
    with self.assertRaises(TransportStopped):generate(RoleClient(client,'persian-writer'),topic,brief,root/'draft')
   transport.assert_called_once();self.assertEqual(snapshot(db)['model_requests_reserved'],1)
   self.assertEqual(load_json(root/'calls/writer.json')['status'],'reserved')
