import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import queue_exceptions as q,image_workflow as image
from automation.agri_v2.queue import atomic_json
from tests.agri_v2 import test_queue_exceptions as fixtures

class ImageTerminalCheckpointTests(unittest.TestCase):
 def setup(self,td,counts=(4,4)):
  d,o,topics,_=fixtures.QueueExceptionTests().setup(Path(td));t=topics[0];f=o/'new'/t['id'];atomic_json(f/'article.json',{'title':t['title']})
  for k,n in enumerate(counts,1):atomic_json(f/'lifecycle'/('image-'+str(k))/'state.json',{'attempts':n,'status':'failed','history':[{'preserved':True}]})
  return d,o,t,f
 def test_direct_outcome_seals_same_proof_without_changing_attempts(self):
  with tempfile.TemporaryDirectory() as td,patch.object(image,'enabled',return_value=True),patch.object(image,'approved_roles',return_value=()):
   d,o,t,f=self.setup(td);before={p:p.read_bytes() for p in f.rglob('*') if p.is_file()}
   direct={'topic_id':t['id'],'status':'images_need_attention','roles':[]};blocked={'topic_id':t['id'],'status':'blocked','reason':'images_need_attention'}
   self.assertEqual(q.terminal_proof(t,direct,d,o),q.terminal_proof(t,blocked,d,o));self.assertIsNotNone(q.note_terminal(t,direct,d,o));row=q.deferral(t,d,o)
   self.assertEqual(row['attempts_preserved']['1']['image'],4);self.assertFalse(row['automatic_retry_authorized']);self.assertFalse(row['publication_authorized'])
   for p,b in before.items():self.assertEqual(p.read_bytes(),b)
 def test_direct_outcome_with_remaining_budget_never_qualifies(self):
  for counts in ((0,0),(4,3),(3,4)):
   with self.subTest(counts=counts),tempfile.TemporaryDirectory() as td,patch.object(image,'enabled',return_value=True),patch.object(image,'approved_roles',return_value=()):
    d,o,t,_=self.setup(td,counts);self.assertIsNone(q.note_terminal(t,{'topic_id':t['id'],'status':'images_need_attention'},d,o))
 def test_approved_role_or_publication_or_deferred_result_never_qualifies(self):
  for kind in ('approved','publication','deferred'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td,patch.object(image,'enabled',return_value=True),patch.object(image,'approved_roles',return_value=(1,) if kind=='approved' else ()):
    d,o,t,f=self.setup(td)
    if kind=='publication':atomic_json(f/'wordpress-receipt.json',{'public_verified':False})
    self.assertIsNone(q.note_terminal(t,{'topic_id':t['id'],'status':'images_deferred' if kind=='deferred' else 'images_need_attention'},d,o))
