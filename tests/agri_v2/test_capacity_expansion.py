import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2.parallel_capacity import KEY_LIMIT,MAX_FAMILIES,CREDENTIAL_SET_ID,AUDIT_ID
from automation.agri_v2.parallel_pool import SLOTS,initialize,lease,snapshot,PoolDeferred,record_routing,routing_counts
from automation.agri_v2.parallel_control import reserve
from automation.agri_v2.queue import atomic_json,load_json,utcnow

class CapacityExpansionTests(unittest.TestCase):
 def test_exact_new_slots_and_families(self):
  from automation.agri_v2.family_scheduler import FAMILIES
  self.assertEqual(KEY_LIMIT,97);self.assertEqual(len(SLOTS),97);self.assertEqual(SLOTS[:2],['AGNES_API_KEY','AGNES_API_KEY2']);self.assertEqual(SLOTS[-1],'AGNES_API_KEY97');self.assertEqual(len(FAMILIES),20);self.assertEqual(FAMILIES[-1],'family-20')
 def test_five_new_owners_preserve_original_fifteen_and_failed_attempts(self):
  from automation.agri_v2 import family_scheduler as f
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';atomic_json(d/'config.json',{'publication_holds':{}});atomic_json(d/'research-source-catalog.json',{'entries':[]})
   topics=[{'id':'agri-'+format(i,'012x'),'title':'Topic '+str(i),'crop':'bean','intent':'yield'} for i in range(30)]
   old=[{'family_id':'family-'+str(i+1).zfill(2),'topic_id':t['id'],'assigned_at':'2026-10-26T04:00:00Z','assignment_status':'assigned'} for i,t in enumerate(topics[:15])];atomic_json(o/'parallel/families/assignments.json',{'families':old,'history':[]})
   attempt=o/'new'/topics[0]['id']/'lifecycle/research_review/state.json';atomic_json(attempt,{'attempts':3,'status':'failed'});before=attempt.read_bytes()
   with patch.object(f,'items',return_value=topics):new=f.allocate(d,o);again=f.allocate(d,o)
   self.assertEqual(new['assigned_count'],20);self.assertEqual(new['families'],again['families']);self.assertEqual(new['history'],[]);self.assertEqual(len({r['topic_id'] for r in new['families']}),20)
   for a,b in zip(old,new['families']):
    for k in ['family_id','topic_id','assigned_at','assignment_status']:self.assertEqual(a[k],b[k])
   self.assertEqual(attempt.read_bytes(),before);self.assertEqual([r['topic_id'] for r in new['families'][15:]],[t['id'] for t in topics[15:20]])
 def test_new_slots_enter_rotation_without_resetting_old_usage(self):
  with tempfile.TemporaryDirectory() as td:
   prior={s:7 for s in SLOTS[:75]};db=Path(td)/'pool.db';initialize(db,SLOTS,prior_usage=prior);chosen=[]
   for i in range(22):
    with lease(db,'text',SLOTS,str(i)) as slot:chosen.append(slot)
   self.assertEqual(chosen,SLOTS[75:]);rows={r['name']:r['used'] for r in snapshot(db)['slots']};self.assertTrue(all(rows[s]==7 for s in SLOTS[:75]));self.assertTrue(all(rows[s]==1 for s in SLOTS[75:]))
 def test_twenty_first_text_lease_deferred_and_higher_limit_rejected(self):
  import contextlib
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'pool.db';initialize(db,SLOTS)
   with contextlib.ExitStack() as stack:
    for i in range(20):stack.enter_context(lease(db,'text',SLOTS,str(i)))
    with self.assertRaises(PoolDeferred):
     with lease(db,'text',SLOTS,'extra',wait=0):pass
   self.assertEqual(snapshot(db)['peak_text_leases'],20)
   with self.assertRaises(ValueError):initialize(Path(td)/'bad.db',SLOTS,text_limit=21)
 def test_ineligible_old_slot_counts_survive_next_record(self):
  with tempfile.TemporaryDirectory() as td:
   o=Path(td);atomic_json(o/'parallel/key-routing.json',{'slot_request_counts':{SLOTS[0]:12,SLOTS[74]:9}})
   record_routing(o,{'slots':[{'name':SLOTS[0],'used':13},{'name':SLOTS[-1],'used':1}]});self.assertEqual(routing_counts(o),{SLOTS[0]:13,SLOTS[74]:9,SLOTS[-1]:1})
   with self.assertRaises(ValueError):record_routing(o,{'slots':[{'name':SLOTS[74],'used':8}]})
 def test_old_75_slot_audit_not_relabelled_or_replayed(self):
  env={'GITHUB_RUN_ID':'222'}
  self.assertEqual(reserve('audit',AUDIT_ID,env,lambda _:True)['request_id'],'parallel-97-key-audit-v1')
  with self.assertRaises(ValueError):reserve('audit','parallel-75-key-audit-v1',env,lambda _:True)
 def test_fresh_old_cohort_cannot_authorize_model_calls(self):
  from automation.agri_v2 import parallel_client as client
  from automation.agri_v2.client import CapabilityError
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);atomic_json(d/'parallel-policy.json',{'credential_set_id':CREDENTIAL_SET_ID});health={'repository':'kapitansaman/afp-pipe','credential_set_id':'afp-pipe-parallel-75-keys-v1','checked_at':utcnow()}
   with patch.object(client,'DATA',d),self.assertRaises(CapabilityError):client.ParallelModelClient(health,env={'AFP_PARALLEL_WORKER':'1','AFP_PARALLEL_POOL_DB':str(d/'pool.db')},allow_calls=True)
 def test_workflow_maps_each_slot_once_including_all_twenty_two_added(self):
  import re
  root=Path(__file__).resolve().parents[2];s=(root/'.github/workflows/afp-parallel-generator.yml').read_text();pairs=re.findall(r'^      (AGNES_API_KEY\d*): \$\{\{ secrets\.AGNES_API_KEY_(\d+) \}\}',s,re.M)
  self.assertEqual(len(pairs),97);self.assertEqual({int(n) for _,n in pairs},set(range(1,98)));self.assertEqual([name for name,_ in pairs],SLOTS);self.assertNotIn('schedule:',s)
