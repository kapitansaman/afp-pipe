import copy,json,shutil,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import family07_multilingual as r,retained_regional_positive as retained
from automation.agri_v2.queue import atomic_json,load_json,DATA,OUT,utcnow
from automation.agri_v2.pipeline import digest
from automation.agri_v2.parallel_pool import initialize,snapshot,SLOTS
from automation.agri_v2.parallel_control import reserve
from automation.agri_v2.client import ModelClient,TextProviderError

class Family07Tests(unittest.TestCase):
 def setup(self,root):
  d=root/'data';o=root/'out';shutil.copytree(DATA,d)
  for rel in ['new/'+r.TOPIC,'parallel/staged-rollout','parallel/health','parallel/key-routing.json','provider-circuit.json']+['infrastructure-probes/'+x for x in (retained.ar.ID,retained.en.ID,r.capability.ID)]:
   src=OUT/rel;dst=o/rel
   if src.is_dir():shutil.copytree(src,dst)
   elif src.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
  # Restore only the fixture copy, never production counters or history.
  queues=load_json(Path(__file__).parent/'fixtures/family07-continuation/queues.json')
  folder=o/'new'/r.TOPIC
  for lang,row in queues.items():
   atomic_json(r.q.path(folder,lang),row)
   (folder/'regional-research'/lang/'approved.json').unlink(missing_ok=True)
  for lang in r.LANGS:
   for suffix in ('.json','.raw.json','.fidelity.json'):(folder/'translations'/(lang+suffix)).unlink(missing_ok=True)
   (folder/'review-queue'/('candidate-'+lang+'.json')).unlink(missing_ok=True)
   shutil.rmtree(folder/'review-queue/attempts'/lang/'3',ignore_errors=True)
  proof=o/'infrastructure-probes'/r.capability.ID/'scoped-proof.json';value=load_json(proof);value['verified_at']=utcnow();atomic_json(proof,value)
  env={s:'synthetic-private-'+str(i) for i,s in enumerate(SLOTS)}
  env.update(GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REPOSITORY='kapitansaman/afp-pipe',GITHUB_REF_NAME='feat/agri-generator-v2-2905-merge593',GITHUB_RUN_ID='123',GITHUB_TOKEN='fake-token')
  atomic_json(d/r.REQUEST,r.expected(d,o));return d,o,env
 def test_actual_retained_contracts_read_only(self):
  before=r.manifest(DATA,OUT);v=retained.revalidate();self.assertEqual(set(v),set(r.RETAINED));self.assertEqual(before,r.manifest(DATA,OUT))
  for row in v.values():self.assertFalse(row['freshness_renewed']);self.assertEqual(len(row['documents']),3)
 def test_exact_admission_limits_and_bound_roles(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));v=load_json(d/r.REQUEST);r.validate(v,d,o)
   self.check_admission_mutations(v,d,o)
 def check_admission_mutations(self,v,d,o):
  for key,value in [('max_text_calls',11),('max_source_fetches',4),('max_search_requests',1),('max_site_calls',1),('max_image_calls',1),('max_runs',2),('max_attempts_per_request',2),('max_in_flight',2),('max_automatic_attempts',4),('max_model_calls_per_item',13),('publication_authorized',True),('schedule_enabled',True),('reset_attempts',True),('global_capacity_refresh',True),('conditional_internal_evidence_adoption_authorized',False),('role_slots',{'translator':'AGNES_API_KEY81'}),('code_sha256','tampered')]:
   with self.subTest(key=key),self.assertRaises(r.Blocked):r.validate(dict(v,**{key:value}),d,o)
 def test_mutable_paths_narrow(self):
  for rel in ['translations/ru-RU.raw.json','translations/tg-TJ.fidelity.json','review-queue/attempts/ru-RU/3/draft.raw.json','regional-research/ar-IQ/approved.json']:self.assertTrue(r.mutable('out/new/'+r.TOPIC+'/'+rel))
  for rel in ['article.json','translations/ar-IQ.json','translations/en-US.raw.json','review-queue/attempts/ru-RU/2/x','regional-research/tg-TJ/local/documents.json','lifecycle/publish/state.json']:self.assertFalse(r.mutable('out/new/'+r.TOPIC+'/'+rel))
  self.assertFalse(r.mutable('out/parallel/health/latest.json'))
 def test_manual_reservation_only_exact_id(self):
  e={'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123','GITHUB_TOKEN':'fake'}
  self.assertTrue(reserve(r.PHASE,r.ID,e,put_fn=lambda row:True))
  for change in [{'GITHUB_EVENT_NAME':'schedule'},{'GITHUB_REF_NAME':'main'}]:
   with self.assertRaises(ValueError):reserve(r.PHASE,r.ID,dict(e,**change),put_fn=Mock())
  with self.assertRaises(ValueError):reserve(r.PHASE,'old',e,put_fn=Mock())
 def test_old_unknown_report_no_input_read_or_calls(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);o=root/'out';atomic_json(o/'infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});fn=Mock()
   with patch.object(r,'identity'):v=r.run({},root/'absent',o,client_factory=fn,reserve_fn=fn,fetcher=fn)
   self.assertEqual(v['model_calls'],0);fn.assert_not_called()
 def test_protected_and_queue_binding_drift_before_reservation(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));atomic_json(o/'parallel/health/latest.json',{'changed':True});fn=Mock()
   with self.assertRaises(r.Blocked):r.run(e,d,o,reserve_fn=fn,fetcher=fn)
   fn.assert_not_called()
 def test_retained_raw_tampering_fails_without_network(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));p=o/'infrastructure-probes'/retained.ar.ID/'languages/ar-IQ/regional-evidence-review-fallback.raw.json';atomic_json(p,{'tampered':True})
   with self.assertRaises(ValueError):retained.revalidate(d,o)
 def test_scoped_proof_expiry_is_not_health_refresh(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));p=o/'infrastructure-probes'/r.capability.ID/'scoped-proof.json';v=load_json(p);v['verified_at']='2020-01-01T00:00:00Z';atomic_json(p,v)
   with self.assertRaises(r.Blocked):r.capability_proof(d,o)
 def test_durable_owned_slot_hold_preflight_zero_transport(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));atomic_json(o/'parallel/key-routing.json',{'slot_request_counts':{},'backpressure':{'slots':{r.capability.TEXT[2]:{'disabled':True,'cooldown_until_epoch':0}}}});atomic_json(d/r.REQUEST,r.expected(d,o));fn=Mock()
   with self.assertRaises(r.Blocked):r.run(e,d,o,reserve_fn=fn,fetcher=fn)
   fn.assert_not_called()
 def test_remote_reservation_conflict_zero_transport(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));fn=Mock();v=r.run(e,d,o,reserve_fn=lambda env:False,client_factory=fn,fetcher=fn);self.assertEqual(v['model_calls'],0);fn.assert_not_called()
 def test_real_retained_internal_adoption_keeps_original_dates_and_counters(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));folder=o/'new'/r.TOPIC;a=load_json(folder/'article.json');b=load_json(d/'briefs'/(r.TOPIC+'.json'))
   for lang,v in retained.revalidate(d,o).items():
    row=load_json(r.q.path(folder,lang));r.save_approval(folder,lang,a,b,v['documents'],v['review'],{'reviewed_at':v['original_reviewed_at'],'freshness_renewed':False},d)
    self.assertTrue(r.q.regional_ready(row,folder,d));self.assertTrue(r.q.approved(folder,a,lang));self.assertEqual(load_json(r.q.path(folder,lang)),row)
    self.assertEqual(load_json(folder/'regional-research'/lang/'approved.json')['reviewed_at'],v['original_reviewed_at'])
 def client(self,root):
  d=root/'data';o=root/'out';pool=root/'pool.sqlite';initialize(pool,list(r.capability.TEXT),max_calls=10,per_worker=10,text_limit=1);worker={s:'fake-'+s for s in r.capability.TEXT};worker['AFP_PARALLEL_POOL_DB']=str(pool)
  class Fake:
   def request(self,*a,**kw):return {'model':r.capability.TEXT_MODEL if hasattr(r.capability,'TEXT_MODEL') else 'agnes-2.5-flash','choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]}
  return r.CountedClient(worker,root/'owned',d,o,base_class=Fake),pool,d,o
 def payload(self,task='Translate all indexed Persian segments faithfully'):
  from automation.agri_v2.healthcheck import TEXT_MODEL
  return {'model':TEXT_MODEL,'messages':[{'role':'user','content':json.dumps({'task':task})}],'max_tokens':14000,'response_format':{'type':'json_schema'}}
 def call(self,c,p):return c.request('text','/chat/completions',p,180,attempts=1)
 def test_transport_fixed_translator_reviewer_roles_and_sequence(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r.capability,'guards'),patch.object(r,'capability_proof'):
   root=Path(td);c,pool,d,o=self.client(root);c.phase='semantic';c.language='ru-RU'
   for task in ['Translate all indexed Persian segments','Independent fidelity review','Correct ONLY listed target IDs','Independent fidelity review after correction']:self.call(c,self.payload(task))
   receipts=[load_json(p) for p in sorted((root/'owned/calls/ru-RU').glob('*.json'))];self.assertEqual([v['slot'] for v in receipts],[r.capability.TEXT[0],r.capability.TEXT[1],r.capability.TEXT[0],r.capability.TEXT[1]]);self.assertEqual(snapshot(pool)['model_requests_reserved'],4)
   with self.assertRaises(r.Blocked):self.call(c,self.payload('Independent fidelity review extra'))
 def test_transport_protected_binding_checked_before_first_request(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r.capability,'guards'),patch.object(r,'capability_proof'):
   c,pool,d,o=self.client(Path(td));c.phase='semantic';c.language='ru-RU';atomic_json(o/'parallel/health/latest.json',{'changed':True})
   with self.assertRaises(r.Blocked):self.call(c,self.payload())
   self.assertEqual(snapshot(pool)['model_requests_reserved'],0)
 def test_transport_no_search_image_extra_review_or_role_borrow(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r.capability,'guards'),patch.object(r,'capability_proof'):
   c,pool,d,o=self.client(Path(td));c.phase='semantic';c.language='ru-RU'
   for p in [self.payload('web search'),self.payload('Independent fidelity review'),dict(self.payload(),model='wrong'),dict(self.payload(),max_tokens=14001)]:
    with self.assertRaises(r.Blocked):self.call(c,p)
   with self.assertRaises(r.Blocked):c.request('image','/images/generations',self.payload(),180,attempts=1)
   self.assertEqual(snapshot(pool)['model_requests_reserved'],0)
 def test_regional_exact_materialized_contract_and_single_call(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r.capability,'guards'),patch.object(r,'capability_proof'):
   root=Path(td);c,pool,d,o=self.client(root);c.language='tg-TJ';p=self.payload('regional');c.expected_response_format=p['response_format'];c.expected_prompt_sha256=digest(p['messages'][-1]['content']);self.call(c,p)
   self.assertEqual(load_json(root/'owned/calls/tg-TJ/0.json')['slot'],r.capability.TEXT[2])
   with self.assertRaises(r.Blocked):self.call(c,p)
   self.assertEqual(snapshot(pool)['model_requests_reserved'],1)
 def test_unknown_transport_retained_no_replay_and_backpressure(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r.capability,'guards'),patch.object(r,'capability_proof'):
   root=Path(td);c,pool,d,o=self.client(root);c.phase='semantic';c.language='ru-RU'
   base=type(c).__mro__[1]
   with patch.object(base,'request',side_effect=TimeoutError('secret')):
    with self.assertRaises(TimeoutError):self.call(c,self.payload())
   self.assertEqual(load_json(root/'owned/calls/ru-RU/0.json')['status'],'reserved')
   with self.assertRaises(r.Blocked):self.call(c,self.payload())
   self.assertEqual(snapshot(pool)['model_requests_reserved'],1);self.assertTrue(load_json(o/'provider-circuit.json')['open'])
 def test_fresh_source_change_stops_before_any_model_or_adoption(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));values=retained.revalidate(d,o);docs=copy.deepcopy(values['ar-IQ']['documents']);docs[0]['sha256']='changed';factory=Mock()
   with patch('automation.agri_v2.source_loading.valid_document',return_value=True),patch.object(r.regional,'documents_for',side_effect=lambda ds,*a,**kw:ds):v=r.run(e,d,o,reserve_fn=lambda env:True,fetcher=Mock(side_effect=docs),client_factory=factory)
   self.assertEqual(v['source_fetches'],3);self.assertEqual(v['model_calls'],0);self.assertEqual(v['failure']['category'],'source_text_changed_retained_review_not_rebound');factory.assert_not_called();self.assertTrue(v['originals_unchanged'])
 def test_missing_source_fails_closed_no_more_fetch_or_model(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));fn=Mock(side_effect=TimeoutError('private'));factory=Mock();v=r.run(e,d,o,reserve_fn=lambda env:True,fetcher=fn,client_factory=factory);fn.assert_called_once();factory.assert_not_called();self.assertEqual(v['model_calls'],0);self.assertEqual(v['source_fetches'],1);self.assertNotIn('private',json.dumps(v))
 def test_full_conditional_adoption_separate_workspaces_and_queue_status_last(self):
  # Stub generation, not validators in production: verify orchestration and narrow copying.
  from automation.agri_v2.parallel_pool import lease
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));saved=retained.revalidate(d,o);docs=saved['ar-IQ']['documents'];seen=[]
   class FakeClient:
    def __init__(self,worker,root,*args):self.worker=worker;self.root=root
   def request(client,root,name,prompt,limit):
    lang=client.language
    with lease(client.worker['AFP_PARALLEL_POOL_DB'],'text',[r.capability.TEXT[2]],r.ID,wait=0):atomic_json(client.root/'calls'/lang/'0.json',{'stage':'regional','status':'received'})
    return saved['ar-IQ']['review']
   def approve(folder,lang,a,b,ds,v,provenance,data):
    atomic_json(folder/'regional-research'/lang/'approved.json',{'fixture':True,'reviewed_at':provenance['reviewed_at']})
   def semantic(path,client,data):
    lang=client.language;folder=path.parent.parent;seen.append(folder);row=load_json(path);self.assertEqual(row['attempts'],2);self.assertEqual(row['model_calls_spent'],3)
    with lease(client.worker['AFP_PARALLEL_POOL_DB'],'text',[r.capability.TEXT[0]],r.ID,wait=0):pass
    with lease(client.worker['AFP_PARALLEL_POOL_DB'],'text',[r.capability.TEXT[1]],r.ID,wait=0):pass
    atomic_json(folder/'review-queue/attempts'/lang/'3/draft.receipt.json',{'status':'received'})
    atomic_json(folder/'review-queue'/('candidate-'+lang+'.json'),{'fixture':True})
    for suffix in ('.json','.raw.json','.fidelity.json'):atomic_json(folder/'translations'/(lang+suffix),{'fixture':lang})
    row.update(status='approved',attempts=3,model_calls_spent=5);atomic_json(path,row);return {'language':lang,'status':'approved','model_calls':2}
   with patch('automation.agri_v2.source_loading.valid_document',return_value=True),patch.object(r.regional,'documents_for',side_effect=lambda ds,*a,**kw:ds),patch('automation.agri_v2.translation_review_repair.request',side_effect=request),patch('automation.agri_v2.regional_schema_recheck.validate_wire'),patch.object(r.regional,'validate_local_review'),patch.object(r,'save_approval',side_effect=approve),patch.object(r.q,'run_item',side_effect=semantic),patch.object(r.q,'approved',return_value=True),patch.object(r.q,'regional_ready',return_value=True):
    v=r.run(e,d,o,reserve_fn=lambda env:True,fetcher=Mock(side_effect=docs),client_factory=FakeClient)
   self.assertEqual(v['status'],'family07_multilingual_verified_not_published');self.assertEqual((v['model_calls'],v['source_fetches']),(6,3));self.assertTrue(v['originals_unchanged']);self.assertEqual(len(set(seen)),2)
   for lang in r.LANGS:self.assertEqual(v['queue_counters'][lang],{'status':'approved','attempts':3,'model_calls_spent':5});self.assertTrue((o/'new'/r.TOPIC/'translations'/(lang+'.json')).exists())
   for lang in r.RETAINED:self.assertEqual(v['queue_counters'][lang]['attempts'],3);self.assertEqual(v['queue_counters'][lang]['model_calls_spent'],5)
   for key in ('site_calls','image_calls','search_requests','published_posts'):self.assertEqual(v[key],0)
   for key in ('publication_authorized','schedule_enabled','stage_promotion_authorized','attempts_reset','global_capacity_refresh'):self.assertFalse(v[key])
 def test_regional_unknown_keeps_spend_and_reconciliation_without_semantic_retry(self):
  from automation.agri_v2.parallel_pool import lease
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));docs=retained.revalidate(d,o)['ar-IQ']['documents']
   class FakeClient:
    def __init__(self,worker,root,*args):self.worker=worker;self.root=root
   def unknown(client,*args):
    with lease(client.worker['AFP_PARALLEL_POOL_DB'],'text',[r.capability.TEXT[2]],r.ID,wait=0):atomic_json(client.root/'calls'/client.language/'0.json',{'stage':'regional','status':'reserved'})
    raise TimeoutError('private provider body')
   with patch('automation.agri_v2.source_loading.valid_document',return_value=True),patch('automation.agri_v2.translation_review_repair.request',side_effect=unknown),patch.object(r.q,'run_item') as semantic:
    v=r.run(e,d,o,reserve_fn=lambda env:True,fetcher=Mock(side_effect=docs),client_factory=FakeClient)
   semantic.assert_not_called();self.assertEqual(v['status'],'family07_multilingual_blocked');self.assertEqual(v['model_calls'],1);self.assertEqual(v['active_language'],'ru-RU');self.assertEqual(v['queue_counters']['ru-RU'],{'status':'reconciliation_required','attempts':2,'model_calls_spent':3});self.assertEqual(v['queue_counters']['tg-TJ']['model_calls_spent'],2);self.assertNotIn('private',json.dumps(v))
