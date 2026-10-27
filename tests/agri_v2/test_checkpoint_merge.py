"""Generator foundation regressions: no model calls, no CMS access."""
import tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import parallel_controller as c,family_lifecycle as f
from automation.agri_v2.queue import atomic_json,load_json

class CheckpointMergeTests(unittest.TestCase):
 def setup(self,root):
  d=root/'data';o=root/'out';wd=root/'worker/data';wo=root/'worker/out';ident='agri-000000000001'
  return d,o,wd,wo,ident,o/'new'/ident,wo/'new'/ident
 def test_failed_regeneration_does_not_resurrect_archived_image_or_quality(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,wd,wo,ident,dest,src=self.setup(Path(td));dest.mkdir(parents=True)
   (dest/'image-1.webp').write_bytes(b'rejected-image');atomic_json(dest/'image-1.quality.json',{'verdict':{'passed':False}})
   shutil.copytree(dest,src)
   def fail():raise RuntimeError('simulated provider failure')
   f.attempt(src,'image-1','123',fail,f.stage_outputs(src,'image-1'))
   c.merge_worker(ident,wd,wo,d,o)
   self.assertFalse((dest/'image-1.webp').exists());self.assertFalse((dest/'image-1.quality.json').exists())
   self.assertEqual((dest/'lifecycle/image-1/rejected/0/image-1.webp').read_bytes(),b'rejected-image')
   self.assertEqual(f.state(dest,'image-1')['attempts'],1)
   c.merge_worker(ident,wd,wo,d,o)
   self.assertFalse((dest/'image-1.webp').exists())
 def test_archived_review_raw_is_not_reintroduced_after_failed_request(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,wd,wo,ident,dest,src=self.setup(Path(td));raw=dest/'lifecycle-evidence/review-raw.json';atomic_json(raw,{'rejected':True});shutil.copytree(dest,src)
   f.attempt(src,'research_review','123',lambda:(_ for _ in ()).throw(ValueError('invalid response')),f.stage_outputs(src,'research_review'))
   c.merge_worker(ident,wd,wo,d,o)
   self.assertFalse(raw.exists());self.assertEqual(load_json(dest/'lifecycle/research_review/rejected/0/review-raw.json'),{'rejected':True})
 def test_changed_coordinator_candidate_fails_before_any_merge_write(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,wd,wo,ident,dest,src=self.setup(Path(td));raw=dest/'lifecycle-evidence/review-raw.json';atomic_json(raw,{'old':True});shutil.copytree(dest,src)
   f.attempt(src,'research_review','123',lambda:(_ for _ in ()).throw(ValueError('invalid')),f.stage_outputs(src,'research_review'))
   atomic_json(raw,{'newer_coordinator':True});before=raw.read_bytes()
   with self.assertRaisesRegex(ValueError,'Archived output conflict'):c.merge_worker(ident,wd,wo,d,o)
   self.assertEqual(raw.read_bytes(),before);self.assertFalse((dest/'lifecycle/research_review/state.json').exists())
 def test_stage_budget_cannot_move_backwards_during_merge(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,wd,wo,ident,dest,src=self.setup(Path(td));atomic_json(f.row_path(dest,'text'),{'attempts':3});atomic_json(f.row_path(src,'text'),{'attempts':1})
   with self.assertRaisesRegex(ValueError,'Stage attempts decreased'):c.merge_worker(ident,wd,wo,d,o)
   self.assertEqual(f.state(dest,'text')['attempts'],3)
 def test_new_candidate_replaces_active_but_retains_old_archive(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,wd,wo,ident,dest,src=self.setup(Path(td));raw=dest/'model-candidate.json';atomic_json(raw,{'old':True});shutil.copytree(dest,src)
   f.attempt(src,'text','123',lambda:atomic_json(src/'model-candidate.json',{'new':True}),f.stage_outputs(src,'text'))
   c.merge_worker(ident,wd,wo,d,o)
   self.assertEqual(load_json(raw),{'new':True});self.assertEqual(load_json(dest/'lifecycle/text/rejected/0/model-candidate.json'),{'old':True})
 def test_partial_worker_does_not_delete_unarchived_or_other_family_files(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,wd,wo,ident,dest,src=self.setup(Path(td));atomic_json(dest/'article.json',{'accepted':True});atomic_json(o/'new/agri-000000000002/proof.json',{'keep':True});atomic_json(src/'lifecycle/text/state.json',{'attempts':1})
   c.merge_worker(ident,wd,wo,d,o)
   self.assertEqual(load_json(dest/'article.json'),{'accepted':True});self.assertEqual(load_json(o/'new/agri-000000000002/proof.json'),{'keep':True})

 def test_atomic_copy_failure_keeps_previous_checkpoint_intact(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);source=p/'source';target=p/'target';source.write_bytes(b'new');target.write_bytes(b'accepted')
   def fail(src,dest):Path(dest).write_bytes(b'partial');raise OSError('simulated disk failure')
   with patch.object(c.shutil,'copy2',side_effect=fail),self.assertRaises(OSError):c.atomic_copy(source,target)
   self.assertEqual(target.read_bytes(),b'accepted');self.assertFalse(list(p.glob('.checkpoint-*')))
 def test_twenty_isolated_family_archives_do_not_resurrect_or_cross_contaminate(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d=root/'data';out=root/'out'
   for i in range(20):
    ident='agri-'+format(i,'012x');wd=root/ident/'data';wo=root/ident/'out';dest=out/'new'/ident;src=wo/'new'/ident
    atomic_json(dest/'article.json',{'owner':ident,'accepted':True});atomic_json(dest/'model-candidate.json',{'rejected_owner':ident});shutil.copytree(dest,src)
    f.attempt(src,'text','123',lambda:(_ for _ in ()).throw(ValueError('simulated failure')),f.stage_outputs(src,'text'))
    c.merge_worker(ident,wd,wo,d,out)
   for i in range(20):
    ident='agri-'+format(i,'012x');dest=out/'new'/ident
    self.assertFalse((dest/'model-candidate.json').exists());self.assertEqual(load_json(dest/'article.json')['owner'],ident)
    self.assertEqual(load_json(dest/'lifecycle/text/rejected/0/model-candidate.json')['rejected_owner'],ident)

 def test_research_coordinator_rejects_other_worker_topic_before_merge(self):
  from tests.agri_v2.test_parallel_generation import config,ENV,POLICY
  from automation.agri_v2.queue import utcnow
  from automation.agri_v2.parallel_pool import SLOTS
  with tempfile.TemporaryDirectory() as td:
   d,o=config(Path(td));inventory={'source_generated_at':utcnow(),'records':[{'id':1,'title':'Existing','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   health={'audit_status':'completed','repository':POLICY['repository'],'credential_set_id':POLICY['credential_set_id'],'checked_at':utcnow(),'eligible_text_slots':SLOTS};atomic_json(o/'parallel/health/latest.json',health)
   topic={'id':'agri-000000000001','title':'Assigned','family_id':'family-01'}
   def wrong_worker(topic,workspace,*args):return 'agri-000000000002',workspace/'data',workspace/'out',{'topic_id':'agri-000000000002','status':'research_ready'}
   with patch('automation.agri_v2.family_scheduler.allocate',return_value={'families':[]}),patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch.object(c,'eligible_topics',return_value=([topic],{})),patch.object(c,'merge_worker') as merge:
    result=c.run('research',ENV,d,o,lambda *_:{},lambda:inventory,wrong_worker)
   merge.assert_not_called();self.assertEqual(result['results'][0]['status'],'worker_or_merge_failed');self.assertEqual(result['results'][0]['topic_id'],topic['id'])
