import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from automation.agri_v2 import family_keys as k, parallel_client as pc
from automation.agri_v2.client import ModelClient, CapabilityError, TextProviderError
from automation.agri_v2.parallel_pool import SLOTS, initialize, snapshot, lease, PoolDeferred, defer
from automation.agri_v2.parallel_capacity import CREDENTIAL_SET_ID
from automation.agri_v2.healthcheck import TEXT_MODEL, IMAGE_MODEL, API_BASE
from automation.agri_v2.queue import atomic_json, load_json, utcnow


class FamilyKeyTests(unittest.TestCase):
 def setup(self, root):
  d=root/'data';o=root/'out';d.mkdir();o.mkdir()
  atomic_json(d/'parallel-policy.json',{'credential_set_id':CREDENTIAL_SET_ID,'family_key_allocation_required':True})
  atomic_json(d/'family-key-allocation.json',k.default_policy())
  health={'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'checked_at':utcnow(),
          'audit_status':'completed','eligible_text_slots':SLOTS,'eligible_image_slots':SLOTS,
          'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE}
  env={s:'synthetic-unique-'+str(i) for i,s in enumerate(SLOTS)}
  env.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(root/'pool.db'),AFP_PARALLEL_FAMILY='family-01',AFP_PARALLEL_TOPIC='agri-000000000001')
  initialize(root/'pool.db',SLOTS,max_calls=100,per_worker=20)
  return d,o,health,env

 def client(self,d,h,e,capabilities=('text',)):
  with patch.object(pc,'DATA',d):return pc.ParallelModelClient(h,env=e,allow_calls=True,capabilities=capabilities)

 def test_exact_twenty_disjoint_four_slot_families_and_seventeen_central(self):
  p=k.default_policy();slots=[s for group in p['families'].values() for s in group]
  self.assertEqual(len(p['families']),20);self.assertEqual(len(slots),80);self.assertEqual(len(set(slots)),80)
  self.assertEqual(set(slots)|set(p['central_slots']),set(SLOTS));self.assertFalse(set(slots)&set(p['central_slots']))
  self.assertEqual(p['families']['family-01'],SLOTS[:4]);self.assertEqual(p['families']['family-20'],SLOTS[76:80]);self.assertEqual(p['central_slots'],SLOTS[80:])

 def test_missing_required_allocation_never_falls_back_to_shared_pool(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));(d/'family-key-allocation.json').unlink()
   with self.assertRaises(CapabilityError):self.client(d,h,e)
   self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],0)

 def test_invalid_partition_flags_or_family_ids_rejected(self):
  for mutate in (lambda p:p['families']['family-02'].__setitem__(0,SLOTS[0]),
                 lambda p:p['families']['family-01'].append(SLOTS[80]),
                 lambda p:p.__setitem__('automatic_reserve_promotion',True),
                 lambda p:p.__setitem__('enabled',False),
                 lambda p:p.__setitem__('cross_family_borrowing',0),
                 lambda p:p.__setitem__('credential_set_id','old'),
                 lambda p:p['families'].__setitem__('family-21',p['families'].pop('family-20'))):
   with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as td:
    d,o,h,e=self.setup(Path(td));p=k.default_policy();mutate(p);atomic_json(d/'family-key-allocation.json',p)
    with self.assertRaises(CapabilityError):k.load(d)

 def test_explicit_reviewed_partition_revision_remains_exact_and_hash_changes(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));before=k.binding(k.load(d));p=k.default_policy()
   p['families']['family-01'][0],p['central_slots'][0]=p['central_slots'][0],p['families']['family-01'][0];p['revision']=2
   atomic_json(d/'family-key-allocation.json',p)
   self.assertNotEqual(k.binding(k.load(d)),before);self.assertEqual(k.slots_for('family-01',d)[0][0],SLOTS[80])

 def test_unknown_or_missing_family_cannot_claim_any_group(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td))
   for family in ('family-00','family-21','family-1','unknown','',None):
    with self.subTest(family=family),self.assertRaises(CapabilityError):k.slots_for(family,d)

 def test_capabilities_intersect_owned_slots_independently_for_text_and_images(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));h.update(eligible_text_slots=[SLOTS[0],SLOTS[4]],eligible_image_slots=[SLOTS[2],SLOTS[80]])
   c=self.client(d,h,e,('text','image'));self.assertEqual([s for s,v in c.keys['text']],[SLOTS[0]]);self.assertEqual([s for s,v in c.keys['image']],[SLOTS[2]])
   self.assertEqual([s for s,v in c.image_candidates],[SLOTS[2]])

 def test_healthy_other_family_or_central_key_does_not_supply_missing_image(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));h['eligible_image_slots']=[SLOTS[4],SLOTS[80]]
   with self.assertRaises(k.FamilyCapabilityRequired) as caught:self.client(d,h,e,('text','image'))
   self.assertEqual(caught.exception.kind,'image');self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],0)

 def test_missing_own_secret_cannot_fall_back_to_other_healthy_secrets(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td))
   for slot in SLOTS[:4]:e.pop(slot)
   with self.assertRaises(k.FamilyCapabilityRequired):self.client(d,h,e)
   self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],0)

 def test_new_topic_and_new_client_preserve_family_slot_ownership(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));a=self.client(d,h,e);b=self.client(d,h,dict(e,AFP_PARALLEL_TOPIC='agri-000000000002'))
   self.assertEqual(a.family_key_slots,b.family_key_slots);self.assertEqual(a.family_key_binding,b.family_key_binding)

 def test_leases_are_deterministic_and_never_cross_family_boundary(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));a=self.client(d,h,e);b=self.client(d,h,dict(e,AFP_PARALLEL_FAMILY='family-02',AFP_PARALLEL_TOPIC='agri-000000000002'))
   chosen=[]
   def request(client,*args,**kwargs):chosen.append(client.keys['text'][0][0]);return {'ok':True}
   with patch.object(ModelClient,'request',autospec=True,side_effect=request):
    for i in range(4):a.request('text','/chat/completions',{},120)
    for i in range(4):b.request('text','/chat/completions',{},120)
   self.assertEqual(chosen,SLOTS[:8]);self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],8)

 def test_tampered_foreign_candidate_is_rejected_before_lease(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));c=self.client(d,h,e);c.keys['text'].append((SLOTS[4],e[SLOTS[4]]))
   with patch.object(ModelClient,'request') as remote:
    with self.assertRaises(CapabilityError):c.request('text','/chat/completions',{},120)
   remote.assert_not_called();self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],0)

 def test_account_quota_stops_one_request_without_blocking_independent_family(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));a=self.client(d,h,e);b=self.client(d,h,dict(e,AFP_PARALLEL_FAMILY='family-02'))
   chosen=[]
   def request(client,*args,**kwargs):
    chosen.append(client.keys['text'][0][0])
    if len(chosen)==1:raise TextProviderError(429,'rate_limited')
    return {'ok':True}
   with patch.object(ModelClient,'request',autospec=True,side_effect=request) as remote:
    with self.assertRaises(TextProviderError):a.request('text','/chat/completions',{},120)
    self.assertEqual(remote.call_count,1)
    self.assertEqual(b.request('text','/chat/completions',{},120),{'ok':True})
   self.assertEqual(chosen,[SLOTS[0],SLOTS[4]])
   row=snapshot(e['AFP_PARALLEL_POOL_DB']);self.assertEqual(row['model_requests_reserved'],2);self.assertEqual(row['cooldown_until_epoch'],0)

 def test_shared_service_error_still_stops_other_groups(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));a=self.client(d,h,e);b=self.client(d,h,dict(e,AFP_PARALLEL_FAMILY='family-02'))
   with patch.object(ModelClient,'request',side_effect=TextProviderError(503,'provider_unavailable')) as remote:
    with self.assertRaises(TextProviderError):a.request('text','/chat/completions',{},120)
    with self.assertRaises(PoolDeferred):b.request('text','/chat/completions',{},120)
    self.assertEqual(remote.call_count,1)
   self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],1)

 def test_all_own_keys_busy_does_not_borrow_idle_central_or_other_slots(self):
  import contextlib
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td))
   with contextlib.ExitStack() as stack:
    for i,slot in enumerate(SLOTS[:4]):stack.enter_context(lease(e['AFP_PARALLEL_POOL_DB'],'text',[slot],'owner'+str(i),wait=0))
    with self.assertRaises(PoolDeferred):
     with lease(e['AFP_PARALLEL_POOL_DB'],'text',list(k.slots_for('family-01',d)[0]),'blocked',wait=0):pass
   self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],4)

 def test_duplicate_secret_across_groups_rejected_without_disclosure(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));e[SLOTS[4]]=e[SLOTS[0]]
   with self.assertRaises(CapabilityError) as caught:self.client(d,h,e)
   self.assertNotIn(e[SLOTS[0]],str(caught.exception));self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['model_requests_reserved'],0)

 def test_worker_env_contains_only_owned_keys_and_no_values_in_metadata(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));clean,meta=k.restrict_env(e,'family-20',d)
   self.assertEqual([s for s in SLOTS if s in clean],SLOTS[76:80]);self.assertEqual(meta['family_key_slots'],SLOTS[76:80])
   for value in [e[s] for s in SLOTS]:self.assertNotIn(value,json.dumps(meta))
   self.assertEqual(len([s for s in SLOTS if s in e]),97)

 def test_worker_launch_strips_other_family_keys_and_records_context(self):
  from automation.agri_v2 import parallel_controller as controller
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o,h,e=self.setup(root);e['GITHUB_RUN_ID']='123'
   def launch(*args,**kwargs):
    passed=kwargs['env'];self.assertEqual([s for s in SLOTS if s in passed],SLOTS[:4])
    atomic_json(Path(passed['AFP_AGRI_OUT_DIR'])/'worker-result.json',{'status':'research_ready','topic_id':e['AFP_PARALLEL_TOPIC']});return Mock(returncode=0)
   with patch.object(controller.subprocess,'run',side_effect=launch):
    _,wd,wo,result=controller.launch_worker({'id':e['AFP_PARALLEL_TOPIC'],'title':'Title','family_id':'family-01'},root/'workspace',root/'pool.db',h,{},d,o,e)
   ctx=load_json(wo/'new'/e['AFP_PARALLEL_TOPIC']/'family-context/123.json');self.assertEqual(ctx['family_key_slots'],SLOTS[:4]);self.assertEqual(ctx['family_key_allocation_sha256'],k.binding(k.load(d)))

 def test_central_language_and_legacy_diagnostics_use_only_seventeen_central_slots(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td))
   for family in ('separate-language-review-queue','matrix-pilot-01','three-source-trial-agri-000000000001'):
    with self.subTest(family=family):
     c=self.client(d,h,dict(e,AFP_PARALLEL_FAMILY=family));self.assertEqual([s for s,v in c.keys['text']],SLOTS[80:])

 def test_capability_missing_worker_returns_safe_checkpointable_status_without_attempt(self):
  from automation.agri_v2 import parallel_worker as worker
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)
   with patch.object(worker,'OUT',out),patch.object(worker,'run',side_effect=k.FamilyCapabilityRequired('image')),patch('sys.argv',['worker','--topic','agri-000000000001']):
    self.assertEqual(worker.main(),0)
   row=load_json(out/'worker-result.json');self.assertEqual(row['status'],'capability_required');self.assertEqual(row['published_posts'],0);self.assertNotIn('attempts',row)

 def test_readiness_requires_fresh_proven_image_within_every_family_not_one_global_key(self):
  from tests.agri_v2.test_production_readiness import ProductionReadinessTests
  fixture=ProductionReadinessTests()
  with tempfile.TemporaryDirectory() as td:
   d,o,h=fixture.setup(Path(td));p=load_json(d/'parallel-policy.json');p['family_key_allocation_required']=True;atomic_json(d/'parallel-policy.json',p);atomic_json(d/'family-key-allocation.json',k.default_policy())
   atomic_json(o/'parallel/runtime/image'/(SLOTS[-1]+'.json'),{'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'slot':SLOTS[-1],'model':IMAGE_MODEL,'verified_at':utcnow(),'verification':'actual_successful_parallel_response'})
   result=fixture.inspect(d,o);self.assertTrue(result['gates']['family_owned_text_capacity']['passed']);self.assertTrue(result['gates']['fresh_image_capacity']['passed']);self.assertFalse(result['gates']['family_owned_image_capacity']['passed'])
   h['eligible_image_slots']=[SLOTS[4*i] for i in range(20)];atomic_json(o/'parallel/health/latest.json',h)
   for slot in h['eligible_image_slots']:atomic_json(o/'parallel/runtime/image'/(slot+'.json'),{'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'slot':slot,'model':IMAGE_MODEL,'verified_at':utcnow(),'verification':'actual_successful_parallel_response'})
   self.assertTrue(fixture.inspect(d,o)['gates']['family_owned_image_capacity']['passed'])

 def test_all_twenty_concurrent_families_keep_their_own_group(self):
  import concurrent.futures,threading
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));clients=[self.client(d,h,dict(e,AFP_PARALLEL_FAMILY=family,AFP_PARALLEL_TOPIC='agri-'+format(i+1,'012x'))) for i,family in enumerate(k.FAMILIES)]
   barrier=threading.Barrier(20)
   def request(client,*args,**kwargs):
    slot=client.keys['text'][0][0];barrier.wait(timeout=15)
    return {'family':client.env['AFP_PARALLEL_FAMILY'],'slot':slot}
   with patch.object(ModelClient,'request',autospec=True,side_effect=request),concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
    results=list(pool.map(lambda c:c.request('text','/chat/completions',{},120),clients))
   for result in results:self.assertIn(result['slot'],k.default_policy()['families'][result['family']])
   self.assertEqual(len({r['slot'] for r in results}),20);self.assertEqual(snapshot(e['AFP_PARALLEL_POOL_DB'])['peak_text_leases'],20)

 def test_duplicate_values_stop_coordinator_before_fence_or_workers(self):
  from tests.agri_v2.test_family_lifecycle import FamilyLifecycleTests
  from automation.agri_v2 import family_lifecycle as lifecycle,execution_recovery as recovery
  with tempfile.TemporaryDirectory() as td:
   d,o,topic,env,health=FamilyLifecycleTests().setup(td)
   atomic_json(d/'family-key-allocation.json',k.default_policy());env.update({SLOTS[0]:'synthetic-duplicate',SLOTS[4]:'synthetic-duplicate'})
   worker=Mock();wp=Mock()
   with patch.object(lifecycle,'allocate',return_value={}),patch.object(lifecycle,'assigned_topics',return_value=[topic]),patch.object(recovery,'begin') as fence:
    result=lifecycle.run(env,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   self.assertEqual(result['status'],'completed_with_failures');fence.assert_not_called();worker.assert_not_called();wp.preflight.assert_not_called()

 def test_runtime_proof_binds_allocation_without_secret_values(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h,e=self.setup(Path(td));c=self.client(d,h,e);c.last_text_slot=SLOTS[0]
   with patch.object(pc,'OUT',o):c.record_success('text',TEXT_MODEL)
   proof=load_json(o/'parallel-runtime/text'/(SLOTS[0]+'.json'));self.assertEqual(proof['assigned_key_slots'],SLOTS[:4]);self.assertEqual(proof['family_key_allocation_sha256'],k.binding(k.load(d)))
   for slot in SLOTS:self.assertNotIn(e[slot],json.dumps(proof))

 def test_readiness_missing_required_map_is_a_blocker_not_exception_or_fallback(self):
  from tests.agri_v2.test_production_readiness import ProductionReadinessTests
  fixture=ProductionReadinessTests()
  with tempfile.TemporaryDirectory() as td:
   d,o,h=fixture.setup(Path(td));p=load_json(d/'parallel-policy.json');p['family_key_allocation_required']=True;atomic_json(d/'parallel-policy.json',p)
   result=fixture.inspect(d,o);self.assertIn('family_key_allocation',result['blockers'])


if __name__=='__main__':unittest.main()
