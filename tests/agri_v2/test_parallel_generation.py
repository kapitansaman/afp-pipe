import concurrent.futures,copy,hashlib,json,os,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2.parallel_pool import SLOTS,initialize,lease,defer,disable,snapshot,PoolDeferred
from automation.agri_v2 import parallel_audit as audit,parallel_controller as controller
from automation.agri_v2.parallel_control import policy,reserve
from automation.agri_v2.queue import atomic_json,load_json,utcnow

POLICY={'repository':'kapitansaman/afp-pipe','credential_set_id':'afp-pipe-parallel-75-keys-v1','key_limit':75,'max_article_workers':15,'image_concurrency':1,'production_enabled':False,'max_published_posts':0}
ENV={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':POLICY['repository'],'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123'}
def config(p):
 data=p/'data';out=p/'out';atomic_json(data/'parallel-policy.json',POLICY);atomic_json(data/'config.json',{'publication_enabled':False,'automatic_generation':False,'publication_holds':{}})
 return data,out
class PoolTests(unittest.TestCase):
 def test_fifteen_simultaneous_workers_have_distinct_dynamic_keys(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pool.db';initialize(db,SLOTS);barrier=threading.Barrier(15);chosen=[];lock=threading.Lock()
   def task(i):
    with lease(db,'text',SLOTS,str(i)) as slot:
     with lock:chosen.append(slot)
     barrier.wait(timeout=10)
   with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:list(ex.map(task,range(15)))
   self.assertEqual(len(set(chosen)),15);self.assertEqual(snapshot(db)['model_requests_reserved'],15)
 def test_rotation_reaches_all_75_without_fixed_five_key_partitions(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pool.db';initialize(db,SLOTS,per_worker=100);seen=[]
   for _ in range(75):
    with lease(db,'text',SLOTS,'same-worker') as slot:seen.append(slot)
   self.assertEqual(set(seen),set(SLOTS));self.assertEqual(len(seen),75)
 def test_no_double_lease_even_across_text_and_image(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pool.db';initialize(db,SLOTS)
   with lease(db,'text',[SLOTS[0]],'a'):
    with self.assertRaises(PoolDeferred):
     with lease(db,'image',[SLOTS[0]],'b',wait=0):pass
 def test_image_single_flight_preserved(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pool.db';initialize(db,SLOTS)
   with lease(db,'image',[SLOTS[0]],'a'):
    with self.assertRaises(PoolDeferred):
     with lease(db,'image',[SLOTS[1]],'b',wait=0):pass
 def test_shared_limit_blocks_all_other_slots_without_call(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pool.db';initialize(db,SLOTS);defer(db,7200)
   with self.assertRaises(PoolDeferred):
    with lease(db,'text',[SLOTS[74]]):pass
   self.assertEqual(snapshot(db)['model_requests_reserved'],0)
 def test_worker_and_global_budgets_never_reset(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pool.db';initialize(db,SLOTS,max_calls=2,per_worker=1)
   with lease(db,'text',SLOTS,'a'):pass
   initialize(db,SLOTS,max_calls=999,per_worker=999)
   with self.assertRaises(PoolDeferred):
    with lease(db,'text',SLOTS,'a'):pass
   with lease(db,'text',SLOTS,'b'):pass
   with self.assertRaises(PoolDeferred):
    with lease(db,'text',SLOTS,'c'):pass
 def test_disable_and_exception_release_do_not_leak_secret_values(self):
  with tempfile.TemporaryDirectory() as t:
   db=Path(t)/'pool.db';initialize(db,SLOTS);disable(db,SLOTS[0])
   try:
    with lease(db,'text',SLOTS,'a') as s:self.assertNotEqual(s,SLOTS[0]);raise ValueError('local failure')
   except ValueError:pass
   with lease(db,'text',[s],'b',wait=0):pass
   self.assertFalse(snapshot(db)['secret_values_stored'])

class AuditTests(unittest.TestCase):
 def env(self):return dict(ENV,**{s:'PRIVATE-KEY-'+str(i) for i,s in enumerate(SLOTS)})
 def post(self,*a,**k):return {'http_status':200,'state':'responded'},{'model':audit.TEXT_MODEL,'choices':[{'message':{'content':'OK'}}]}
 def test_all_75_actual_checks_without_image_approval_or_legacy_health_edit(self):
  with tempfile.TemporaryDirectory() as t:
   d,o=config(Path(t));atomic_json(d/'health/latest.json',{'legacy':'unchanged'});fn=Mock(side_effect=self.post)
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=audit.run(self.env(),d,o,fn,lambda *_:{'reserved':True})
   self.assertEqual(r['model_calls'],75);self.assertEqual(fn.call_count,75);self.assertEqual(len(r['eligible_text_slots']),75);self.assertEqual(r['eligible_image_slots'],[])
   self.assertEqual(load_json(d/'health/latest.json'),{'legacy':'unchanged'});self.assertNotIn('PRIVATE',json.dumps(r));self.assertEqual(r['published_posts'],0)
 def test_duplicates_or_missing_stop_before_paid_calls(self):
  for missing in (True,False):
   with tempfile.TemporaryDirectory() as t:
    d,o=config(Path(t));e=self.env()
    if missing:e.pop(SLOTS[-1])
    else:e[SLOTS[-1]]=e[SLOTS[0]]
    fn=Mock()
    with patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=audit.run(e,d,o,fn,lambda *_:{})
    self.assertEqual(r['model_calls'],0);fn.assert_not_called()
 def test_durable_reservation_blocks_replay(self):
  with tempfile.TemporaryDirectory() as t:
   d,o=config(Path(t));fn=Mock()
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=audit.run(self.env(),d,o,fn,lambda *_:None)
   self.assertEqual(r['status'],'already_reserved');fn.assert_not_called()
 def test_shared_error_stops_new_submissions_and_preserves_long_retry_after(self):
  with tempfile.TemporaryDirectory() as t:
   d,o=config(Path(t));fn=Mock(return_value=({'http_status':429,'state':'rate_limited','retry_after_seconds':7200},None))
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=audit.run(self.env(),d,o,fn,lambda *_:{})
   self.assertLessEqual(fn.call_count,2);self.assertEqual(r['status'],'stopped_shared_provider_limit');self.assertGreater(load_json(o/'provider-circuit.json')['retry_at_epoch'],time.time()+7100)
 def test_old_reservation_and_provider_cooldown_are_not_reset(self):
  with tempfile.TemporaryDirectory() as t:
   d,o=config(Path(t));fn=Mock()
   with patch('automation.agri_v2.recovery.circuit_open',return_value=True):r=audit.run(self.env(),d,o,fn,lambda *_:{})
   self.assertEqual(r['model_calls'],0);fn.assert_not_called()

class ControlTests(unittest.TestCase):
 def test_policy_rejects_production_and_schedule_and_wrong_repo(self):
  with tempfile.TemporaryDirectory() as t:
   d,o=config(Path(t));self.assertEqual(policy(ENV,d)['max_article_workers'],15)
   for e in [dict(ENV,GITHUB_EVENT_NAME='schedule'),dict(ENV,GITHUB_REPOSITORY='getsalet/nono')]:
    with self.assertRaises(ValueError):policy(e,d)
   p=dict(POLICY,production_enabled=True);atomic_json(d/'parallel-policy.json',p)
   with self.assertRaises(ValueError):policy(ENV,d)
 def test_remote_reservation_is_exact_and_never_reused(self):
  self.assertIsNone(reserve('research',controller.ID,ENV,lambda _:False))
  self.assertEqual(reserve('research',controller.ID,ENV,lambda _:True)['published_posts'],0)
  with self.assertRaises(ValueError):reserve('research','changed-id',ENV,lambda _:True)
 def test_fifteen_workers_use_isolated_outputs_and_single_merge_writer(self):
  with tempfile.TemporaryDirectory() as t:
   d,o=config(Path(t));inventory={'source_generated_at':utcnow(),'scope':'all published posts','records':[{'id':1,'title':'Existing other title','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   health={'audit_status':'completed','repository':POLICY['repository'],'credential_set_id':POLICY['credential_set_id'],'checked_at':utcnow(),'eligible_text_slots':SLOTS}
   atomic_json(o/'parallel/health/latest.json',health)
   topics=[{'id':'agri-'+format(i,'012x'),'title':'Title '+str(i)} for i in range(15)];barrier=threading.Barrier(15);threads=set();lock=threading.Lock()
   def worker(topic,workspace,db,h,inv,data,out,env):
    ident=topic['id'];wd=workspace/ident/'data';wo=workspace/ident/'out'
    with lock:threads.add(threading.get_ident())
    barrier.wait(timeout=15);atomic_json(wo/'research'/f'{ident}.json',{'topic_id':ident,'attempts':1,'status':'needs_review'})
    return ident,wd,wo,{'status':'research_needs_review','topic_id':ident,'published_posts':0}
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch.object(controller,'eligible_topics',return_value=(topics,{})):
    r=controller.run('research',ENV,d,o,lambda *_:{},lambda:inventory,worker)
   self.assertEqual(len(threads),15);self.assertEqual(len(r['results']),15);self.assertEqual(len(list((o/'research').glob('*.json'))),15);self.assertEqual(r['published_posts'],0)
   self.assertEqual(load_json(d/'config.json')['publication_enabled'],False)
 def test_merge_preserves_existing_brief_and_does_not_import_global_worker_config(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);d,o=config(p);wd=p/'wd';wo=p/'wo';ident='agri-000000000001'
   atomic_json(d/'briefs'/f'{ident}.json',{'old':True});atomic_json(wd/'briefs'/f'{ident}.json',{'new':True})
   with self.assertRaises(ValueError):controller.merge_worker(ident,wd,wo,d,o)
   self.assertEqual(load_json(d/'briefs'/f'{ident}.json'),{'old':True})
 def test_planner_preserves_holds_review_flags_and_exhausted_budgets(self):
  with tempfile.TemporaryDirectory() as t:
   d,o=config(Path(t));atomic_json(d/'research-source-catalog.json',{'version':4,'entries':[{'crops':['bean'],'intents':['storage']}]})
   topics=[{'id':'agri-'+format(i,'012x'),'title':'Title '+str(i),'crop':'bean','intent':'storage','priority':'P1'} for i in range(6)]
   cfg=load_json(d/'config.json');cfg['publication_holds']={topics[0]['id']:'held'};atomic_json(d/'config.json',cfg)
   atomic_json(o/'research'/f"{topics[1]['id']}.json",{'attempts':2,'status':'needs_review','reason':'insufficient_fetchable_institutional_sources','source_catalog_version':3})
   atomic_json(o/'research'/f"{topics[2]['id']}.json",{'attempts':1,'status':'needs_review','reason':'source_scout_scope_requires_review'})
   topics[3].update(overlap_review_required=True,related_existing_ids=[1]);topics[4]['crop']='unknown'
   with patch.object(controller,'items',return_value=topics):chosen,skipped=controller.eligible_topics({'records':[]},d,o)
   self.assertEqual([x['id'] for x in chosen],[topics[5]['id']]);self.assertEqual(load_json(o/'research'/f"{topics[1]['id']}.json")['attempts'],2)
 def test_workflow_maps_exactly_75_secrets_and_has_no_schedule_or_publish_input(self):
  root=Path(__file__).resolve().parents[2];s=(root/'.github/workflows/afp-parallel-generator.yml').read_text()
  self.assertEqual(s.count('secrets.AGNES_API_KEY_'),75);self.assertNotIn('schedule:',s);self.assertNotIn('secrets.AGNES_API_KEY_76',s);self.assertNotIn('options: [publish',s)
