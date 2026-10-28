"""Admission does not consume a paid attempt or overwrite its evidence."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import family_lifecycle as f
from automation.agri_v2.parallel_pool import PoolDeferred
from automation.agri_v2.queue import atomic_json,load_json

class DeferredCheckpointArchiveTests(unittest.TestCase):
 def test_repeated_nonconsuming_deferrals_keep_unique_receipts_then_resume(self):
  for stage in ('vision-1','text'):
   with self.subTest(stage=stage),tempfile.TemporaryDirectory() as td:
    folder=Path(td);p=folder/'candidate.json';p.write_text('initial')
    for i in range(3):
     def defer(i=i):
      p.write_text('deferred-'+str(i));raise PoolDeferred('Bounded model budget consumed')
     r=f.attempt(folder,stage,str(i),defer,[p]);self.assertEqual(r['status'],'stage_deferred');self.assertEqual(f.state(folder,stage)['attempts'],0)
    self.assertEqual(f.attempt(folder,stage,'resume',lambda: {'done':True},[p])['status'],'stage_completed')
    self.assertEqual(f.state(folder,stage)['attempts'],1)
    self.assertEqual((folder/'lifecycle'/stage/'rejected/0/candidate.json').read_text(),'initial')
    for i in range(3):self.assertEqual((folder/'lifecycle'/stage/'deferred'/str(i+1)/'candidate.json').read_text(),'deferred-'+str(i))
    self.assertEqual(len(f.state(folder,stage)['history']),4)
 def test_paid_rejection_paths_and_attempts_are_not_reclassified(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);p=folder/'candidate.json'
   def reject():p.write_text('paid-rejection');raise ValueError('invalid')
   f.attempt(folder,'text','paid',reject,[p])
   def defer():p.write_text('admission-receipt');raise PoolDeferred('busy')
   f.attempt(folder,'text','wait',defer,[p]);f.attempt(folder,'text','resume',lambda:None,[p])
   self.assertEqual((folder/'lifecycle/text/rejected/1/candidate.json').read_text(),'paid-rejection')
   self.assertEqual((folder/'lifecycle/text/deferred/2/candidate.json').read_text(),'admission-receipt')
   self.assertEqual(f.state(folder,'text')['attempts'],2)
 def test_collision_still_fails_closed_without_overwriting_or_call(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);p=folder/'candidate.json';p.write_text('live')
   atomic_json(f.row_path(folder,'text'),{'attempts':1,'status':'deferred','history':[{}]})
   archive=folder/'lifecycle/text/deferred/1/candidate.json';archive.parent.mkdir(parents=True);archive.write_text('prior')
   fn=Mock()
   with self.assertRaises(f.StageBlocked):f.attempt(folder,'text','new',fn,[p])
   fn.assert_not_called();self.assertEqual(p.read_text(),'live');self.assertEqual(archive.read_text(),'prior');self.assertEqual(f.state(folder,'text')['attempts'],1)
 def test_unknown_outcome_remains_fenced_without_archiving_or_replay(self):
  for status in ('reserved','reconciliation_required'):
   with tempfile.TemporaryDirectory() as td:
    folder=Path(td);p=folder/'candidate.json';p.write_text('unknown')
    atomic_json(f.row_path(folder,'text'),{'attempts':1,'status':status,'history':[{}],'last_run_id':'old'})
    before=f.row_path(folder,'text').read_bytes();fn=Mock();r=f.attempt(folder,'text','new',fn,[p])
    self.assertEqual(r['status'],'stage_reconciliation_required');fn.assert_not_called();self.assertEqual(before,f.row_path(folder,'text').read_bytes());self.assertEqual(p.read_text(),'unknown')
 def test_deferred_history_does_not_grant_fourth_text_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);atomic_json(f.row_path(folder,'text'),{'attempts':3,'status':'deferred','history':[{}]});fn=Mock()
   self.assertEqual(f.attempt(folder,'text','new',fn)['status'],'stage_budget_exhausted');fn.assert_not_called()
