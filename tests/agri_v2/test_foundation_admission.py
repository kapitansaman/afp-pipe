import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import family_admission as a,family_lifecycle as f
from automation.agri_v2.foundation_policy import POLICY
from automation.agri_v2.queue import atomic_json,load_json
from tests.agri_v2 import test_family_lifecycle as fixtures

class FoundationAdmissionTests(unittest.TestCase):
 def setup(self,td):
  d,o,t,e,h=fixtures.FamilyLifecycleTests().setup(td);atomic_json(d/'generator-foundation-policy.json',POLICY);return d,o,t,e,h
 def test_blocked_complete_unknown_and_exhausted_are_not_launched(self):
  for kind in ('blocked','complete','unknown','budget'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h=self.setup(td);folder=o/'new'/t['id']
    if kind=='unknown':atomic_json(f.row_path(folder,'research_extract'),{'attempts':1,'status':'reconciliation_required','history':[{}]})
    if kind=='budget':atomic_json(f.row_path(folder,'text'),{'attempts':3,'status':'failed','history':[{}]})
    stage=kind if kind in ('blocked','complete') else 'text'
    with patch.object(f,'next_stage',return_value=(stage,None)):r=a.decision(t,d,o)
    self.assertFalse(r['due']);self.assertFalse(r['publication_authorized'])
 def test_due_projection_preserves_every_attempt_byte_and_family_ownership(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);p=f.row_path(o/'new'/t['id'],'text');atomic_json(p,{'attempts':2,'status':'failed','history':[{}]});before=p.read_bytes()
   with patch.object(f,'next_stage',return_value=('text',None)),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False):due,rows=a.project([t],d,o)
   self.assertEqual(due,[t]);self.assertEqual(before,p.read_bytes());self.assertEqual(rows[0]['family_id'],t['family_id'])
 def test_no_due_work_does_not_create_worker_or_wordpress_client(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);worker=Mock();wp=Mock()
   with patch.object(f,'allocate',return_value={}),patch.object(f,'assigned_topics',return_value=[t]),patch.object(f,'next_stage',return_value=('blocked','held')):
    r=f.run(e,d,o,worker_fn=worker,wp_factory=wp,reserve_fn=lambda *a:{})
   self.assertEqual(r['status'],'completed');self.assertTrue(r['no_due_work']);worker.assert_not_called();wp.assert_not_called();self.assertEqual(r['model_calls'],0)
 def test_provider_hold_blocks_due_before_worker_allocation(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td)
   with patch.object(f,'next_stage',return_value=('text',None)),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=True):r=a.decision(t,d,o)
   self.assertFalse(r['due']);self.assertEqual(r['reason'],'provider_cooldown')
 def test_verified_source_review_due_does_not_reset_publish_budget(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);folder=o/'new'/t['id'];atomic_json(folder/'wordpress-receipt.json',{'public_verified':True});atomic_json(folder/'review-queue/en-US.json',{'fixture':True});p=f.row_path(folder,'publish');atomic_json(p,{'attempts':3,'status':'failed','history':[]});before=p.read_bytes()
   with patch.object(f,'next_stage',return_value=('publish',None)),patch('automation.agri_v2.language_review_queue.due',return_value=True),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False):self.assertTrue(a.decision(t,d,o)['due'])
   self.assertEqual(before,p.read_bytes())
 def test_deferred_archive_merge_retires_exact_old_active_candidate(self):
  import shutil
  from automation.agri_v2.parallel_controller import merge_worker
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);wd=root/'wd';wo=root/'wo';d=root/'d';o=root/'o';ident='agri-000000000001';src=wo/'new'/ident;dest=o/'new'/ident;dest.mkdir(parents=True);(dest/'practical-text-candidate.json').write_text('old');shutil.copytree(dest,src)
   atomic_json(f.row_path(src,'text'),{'attempts':1,'status':'deferred','history':[{}]});atomic_json(f.row_path(dest,'text'),{'attempts':1,'status':'deferred','history':[{}]});f.archive(src,'text',[src/'practical-text-candidate.json']);merge_worker(ident,wd,wo,d,o)
   self.assertFalse((dest/'practical-text-candidate.json').exists());self.assertEqual((dest/'lifecycle/text/deferred/1/practical-text-candidate.json').read_text(),'old');merge_worker(ident,wd,wo,d,o)
 def test_review_queue_does_not_process_topics_outside_selected_cohort(self):
  from automation.agri_v2 import language_review_queue as q
  from automation.agri_v2.queue import DATA
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);atomic_json(d/'language-review-policy.json',load_json(DATA/'language-review-policy.json'));p=o/'new/other/review-queue/en-US.json';atomic_json(p,{'topic_id':'other','experimental_only':False})
   with patch.object(q,'entries',return_value=[p]),patch.object(q,'due',return_value=True),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=False),patch('automation.agri_v2.parallel_pool.initialize') as initialize:
    r=q.process_due(e,h,d,o,topic_ids={t['id']})
   self.assertEqual(r['status'],'no_due_items');initialize.assert_not_called();self.assertEqual(r['model_calls'],0)
 def test_enabled_coordinator_dispatches_only_one_of_twenty_due_owned_families(self):
  from automation.agri_v2.queue import utcnow
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);topics=[dict(t,id='agri-'+format(i+1,'012x'),family_id='family-'+str(i+1).zfill(2)) for i in range(20)];worker=Mock();wp=Mock();wp.inventory.return_value={'source_generated_at':utcnow(),'scope':'all public posts','records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   def work(topic,workspace,db,*args):return topic['id'],workspace/'data',workspace/'out',{'topic_id':topic['id'],'status':'publication_ready'}
   worker.side_effect=work
   with patch.object(f,'allocate',return_value={}),patch.object(f,'assigned_topics',return_value=topics),patch.object(f,'next_stage',return_value=('publish',None)),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False),patch('automation.agri_v2.parallel_controller.merge_worker'),patch.object(f,'publish_ready',return_value={'published_posts':1,'public_verified':True}) as publish:
    result=f.run(e,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *a:{})
   self.assertEqual(result['assigned_count'],1);self.assertEqual(result['staged_rollout']['limit'],1);self.assertEqual(worker.call_count,1);self.assertEqual(publish.call_count,1);self.assertEqual(result['max_total_model_calls'],12);self.assertEqual(result['results'][0]['family_id'],'family-01')
 def test_required_missing_policy_cannot_fall_back_to_twenty_family_legacy_path(self):
  from automation.agri_v2.foundation_policy import enabled
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);p=d/'family-lifecycle-policy.json';row=load_json(p);row['foundation_admission_required']=True;atomic_json(p,row);(d/'generator-foundation-policy.json').unlink()
   with self.assertRaises(ValueError):enabled(d)
