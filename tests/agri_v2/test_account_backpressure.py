"""Independent account admission; one provider call, durable holds, no gate bypass."""
import concurrent.futures,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import parallel_pool as p,parallel_client as pc
from automation.agri_v2.client import ModelClient,TextProviderError,ImageProviderError
from automation.agri_v2.queue import load_json,atomic_json

class AccountBackpressureTests(unittest.TestCase):
 def client(self,db):
  c=pc.ParallelModelClient.__new__(pc.ParallelModelClient)
  c.env={'AFP_PARALLEL_POOL_DB':str(db),'AFP_PARALLEL_TOPIC':'topic-a'}
  c.family_key_slots=tuple(p.SLOTS[:4]);c.keys={k:[(s,'PRIVATE-'+s) for s in p.SLOTS[:4]] for k in ('text','image')}
  return c
 def test_account_limit_is_local_for_text_and_image_and_never_immediate_hops(self):
  for kind in ('text','image'):
   for code in (402,429):
    with self.subTest(kind=kind,code=code),tempfile.TemporaryDirectory() as td:
     db=Path(td)/'pool';p.initialize(db,p.SLOTS);c=self.client(db)
     error=TextProviderError(code,'rate_limited',7200) if kind=='text' else ImageProviderError(code,None,'rate_limited',7200)
     with patch.object(ModelClient,'request',side_effect=error) as provider,self.assertRaises(type(error)):
      c.request(kind,'/unused',{},120)
     self.assertEqual(provider.call_count,1);self.assertEqual(provider.call_args.kwargs['attempts'],1)
     state=p.snapshot(db);self.assertEqual(state['cooldown_until_epoch'],0);self.assertGreater(state['slots'][0]['cooldown_until_epoch'],time.time()+7100)
     with self.assertRaises(p.PoolDeferred):
      with p.lease(db,kind,[p.SLOTS[0]],wait=0):pass
     with p.lease(db,kind,[p.SLOTS[4]],worker='family-b',wait=0) as slot:self.assertEqual(slot,p.SLOTS[4])
     self.assertEqual(len(c.keys[kind]),4)
 def test_auth_failure_disables_only_its_account(self):
  for code in (401,403):
   with self.subTest(code=code),tempfile.TemporaryDirectory() as td:
    db=Path(td)/'db';p.initialize(db,p.SLOTS);c=self.client(db)
    with patch.object(ModelClient,'request',side_effect=TextProviderError(code,'auth')),self.assertRaises(TextProviderError):c.request('text','/unused',{},120)
    row=p.snapshot(db);self.assertEqual(row['slots'][0]['disabled'],1);self.assertEqual(row['slots'][1]['disabled'],0);self.assertEqual(row['cooldown_until_epoch'],0)
 def test_service_and_network_global_guard_not_relaxed(self):
  for code in (None,500,503):
   with self.subTest(code=code),tempfile.TemporaryDirectory() as td:
    db=Path(td)/'db';p.initialize(db,p.SLOTS);c=self.client(db)
    with patch.object(ModelClient,'request',side_effect=TextProviderError(code,'provider_unavailable')),self.assertRaises(TextProviderError):c.request('text','/unused',{},120)
    with self.assertRaises(p.PoolDeferred):
     with p.lease(db,'text',[p.SLOTS[80]],wait=0):pass
    self.assertGreater(p.snapshot(db)['cooldown_until_epoch'],time.time()+3500)
 def test_other_independent_families_progress_concurrently(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'db';p.initialize(db,p.SLOTS);p.defer_slot(db,p.SLOTS[0],3600);barrier=threading.Barrier(19)
   def worker(i):
    with p.lease(db,'text',p.SLOTS[i*4:i*4+4],str(i),wait=1) as slot:
     barrier.wait(timeout=15);return slot
   with concurrent.futures.ThreadPoolExecutor(max_workers=19) as ex:slots=list(ex.map(worker,range(1,20)))
   self.assertEqual(len(set(slots)),19);self.assertEqual(p.snapshot(db)['model_requests_reserved'],19)
 def test_durable_holds_and_counters_survive_fresh_runner(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'out';db=Path(td)/'db';p.initialize(db,p.SLOTS);p.defer_slot(db,p.SLOTS[0],7200);p.disable(db,p.SLOTS[1])
   with p.lease(db,'text',[p.SLOTS[2]],'a'):pass
   p.record_routing(out,p.snapshot(db));fresh=Path(td)/'new'
   p.initialize(fresh,p.SLOTS,prior_usage=p.routing_counts(out),prior_backpressure=p.routing_backpressure(out));s=p.snapshot(fresh)
   self.assertGreater(s['slots'][0]['cooldown_until_epoch'],time.time()+7100);self.assertEqual(s['slots'][1]['disabled'],1);self.assertEqual(s['slots'][2]['used'],1)
   self.assertNotIn('PRIVATE',json.dumps(load_json(out/'parallel/key-routing.json')))
 def test_ineligible_old_holds_survive_checkpoint_with_subset(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'out';db=Path(td)/'db';p.initialize(db,p.SLOTS);p.defer_slot(db,p.SLOTS[0],7200);p.disable(db,p.SLOTS[1]);p.record_routing(out,p.snapshot(db));before=p.routing_backpressure(out)
   fresh=Path(td)/'new';p.initialize(fresh,[p.SLOTS[2]]);p.record_routing(out,p.snapshot(fresh))
   self.assertEqual(p.routing_backpressure(out),before)
 def test_longer_retry_after_never_shortened_by_reinitialization(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'db';p.initialize(db,p.SLOTS);p.defer_slot(db,p.SLOTS[0],7200);before=p.snapshot(db)['slots'][0]['cooldown_until_epoch'];p.defer_slot(db,p.SLOTS[0],60);p.initialize(db,p.SLOTS)
   self.assertEqual(p.snapshot(db)['slots'][0]['cooldown_until_epoch'],before)
 def test_expired_slot_hold_releases_without_resetting_counts(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'db'
   with patch.object(p.time,'time',return_value=1000):p.initialize(db,p.SLOTS);p.defer_slot(db,p.SLOTS[0],60)
   with patch.object(p.time,'time',return_value=1061):
    with p.lease(db,'text',[p.SLOTS[0]],wait=0) as slot:self.assertEqual(slot,p.SLOTS[0])
   self.assertEqual(p.snapshot(db)['slots'][0]['used'],1)
 def test_old_count_only_ledger_is_backward_compatible(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'out';atomic_json(out/'parallel/key-routing.json',{'slot_request_counts':{p.SLOTS[0]:7}});db=Path(td)/'db'
   p.initialize(db,p.SLOTS,prior_usage=p.routing_counts(out),prior_backpressure=p.routing_backpressure(out));self.assertEqual(p.snapshot(db)['slots'][0]['used'],7)
 def test_corrupt_durable_holds_fail_closed_before_leasing(self):
  bad=[{'slots':[]},{'slots':{'foreign':{'disabled':False,'cooldown_until_epoch':0}}},{'shared_cooldown_until_epoch':float('inf')},{'shared_cooldown_until_epoch':True},{'slots':{p.SLOTS[0]:{'disabled':False,'cooldown_until_epoch':-1}}},{'slots':{p.SLOTS[0]:{'disabled':0,'cooldown_until_epoch':0}}},{'unexpected':1}]
  for hold in bad:
   with self.subTest(hold=hold),tempfile.TemporaryDirectory() as td,self.assertRaises(ValueError):p.initialize(Path(td)/'db',p.SLOTS,prior_backpressure=hold)
 def test_global_guard_also_survives_checkpoint(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'out';db=Path(td)/'db';p.initialize(db,p.SLOTS);p.defer(db,7200);p.record_routing(out,p.snapshot(db));fresh=Path(td)/'new';p.initialize(fresh,p.SLOTS,prior_backpressure=p.routing_backpressure(out))
   with self.assertRaises(p.PoolDeferred):
    with p.lease(fresh,'text',[p.SLOTS[80]],wait=0):pass
 def test_real_generator_entrypoints_restore_durable_holds(self):
  root=Path(__file__).resolve().parents[2]
  for name in ('family_lifecycle.py','language_review_queue.py','parallel_controller.py'):
   self.assertIn('prior_backpressure=routing_backpressure(out)',(root/'automation/agri_v2'/name).read_text())
 def test_foreign_key_rejected_before_any_provider_call_or_lease(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'db';p.initialize(db,p.SLOTS);c=self.client(db);c.keys['text']=[(p.SLOTS[80],'PRIVATE')]
   with patch.object(ModelClient,'request') as provider,self.assertRaises(pc.CapabilityError):c.request('text','/unused',{},120)
   provider.assert_not_called();self.assertEqual(p.snapshot(db)['model_requests_reserved'],0)
