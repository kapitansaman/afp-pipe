"""Offline queue simulation, NOT a live content/throughput/publication approval."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import family_scheduler as s
from automation.agri_v2.queue import DATA,items,atomic_json

class GeneratorQueueScaleTests(unittest.TestCase):
 def setup(self,root):
  d=root/'data';o=root/'out';atomic_json(d/'config.json',{'publication_holds':{},'multilingual':{'enabled':False}});atomic_json(d/'research-source-catalog.json',{'entries':[]})
  return d,o,items('new',DATA)
 def test_actual_2905_title_queue_rotates_without_duplicate_or_lost_ownership(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,topics=self.setup(Path(td));done=set();seen=[];waves=0
   self.assertEqual(len(topics),2905)
   with patch.object(s,'items',return_value=topics),patch.object(s,'published',side_effect=lambda ident,out:ident in done),patch.object(s,'family_complete',side_effect=lambda ident,data,out:ident in done):
    while True:
     state=s.allocate(d,o);owners=state['families']
     if not owners:break
     self.assertLessEqual(len(owners),20);self.assertEqual(len({x['topic_id'] for x in owners}),len(owners));self.assertEqual(len({x['family_id'] for x in owners}),len(owners))
     self.assertTrue(done.isdisjoint(x['topic_id'] for x in owners));self.assertFalse(any(x['publication_authorized_by_assignment'] for x in owners))
     before=[(x['family_id'],x['topic_id']) for x in owners];again=s.allocate(d,o)
     self.assertEqual(before,[(x['family_id'],x['topic_id']) for x in again['families']])
     batch=[x['topic_id'] for x in owners];seen.extend(batch);done.update(batch);waves+=1
     self.assertLessEqual(waves,146)
   self.assertEqual(waves,146);self.assertEqual(len(seen),2905);self.assertEqual(set(seen),{t['id'] for t in topics});self.assertEqual(len(state['history']),2905)
 def test_four_waiting_families_do_not_block_remaining_sixteen(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,topics=self.setup(Path(td));topics=topics[:100];done=set();first=None
   with patch.object(s,'items',return_value=topics),patch.object(s,'published',side_effect=lambda ident,out:ident in done),patch.object(s,'family_complete',side_effect=lambda ident,data,out:ident in done):
    first=s.allocate(d,o);waiting={x['topic_id'] for x in first['families'][:4]};bindings={x['family_id']:x['topic_id'] for x in first['families'][:4]}
    for _ in range(8):
     state=s.allocate(d,o)
     for row in state['families']:
      if row['family_id'] in bindings:self.assertEqual(row['topic_id'],bindings[row['family_id']])
      else:done.add(row['topic_id'])
    last=s.allocate(d,o)
   self.assertEqual(len(done),96);self.assertEqual({x['topic_id'] for x in last['families']},waiting);self.assertEqual(len(last['history']),96)
