import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import image_key_routing as r
class RoutingTests(unittest.TestCase):
 def setUp(self):self.pool=[('AGNES_API_KEY','a'),('AGNES_API_KEY2','b'),('AGNES_API_KEY8','a')]
 def test_round_robin_unique(self):
  one,c=r.choose(self.pool,0,[],100);two,c=r.choose(self.pool,c,[],100);three,c=r.choose(self.pool,c,[],100)
  self.assertEqual([one[0],two[0],three[0]],['AGNES_API_KEY','AGNES_API_KEY2','AGNES_API_KEY'])
 def test_skip_per_key_cooldown(self):
  self.assertEqual(r.choose(self.pool,0,[{'keys':{'AGNES_API_KEY':{'retry_at_epoch':110}}}],100)[0][0],'AGNES_API_KEY2')
 def test_skip_scope_denied(self):
  self.assertEqual(r.choose(self.pool,0,[{'keys':{'AGNES_API_KEY':{'status':'image_scope_denied'}}}],100)[0][0],'AGNES_API_KEY2')
 def test_shared_queue_prevents_all_selection(self):
  with self.assertRaises(r.AdmissionBlocked):r.choose(self.pool,0,[{'shared_retry_at_epoch':110}],100)
 def test_billing_not_bypassed(self):
  with self.assertRaises(r.AdmissionBlocked):r.choose(self.pool,0,[{'shared_block':'billing_required'}],100)
 def test_all_keys_blocked(self):
  with self.assertRaises(r.AdmissionBlocked):r.choose(self.pool,0,[{'keys':{n:{'status':'quota_limited'} for n,k in self.pool}}],100)
 def test_unknown_slot_rejected(self):
  with self.assertRaises(r.AdmissionBlocked):r.choose([('AGNES_API_KEY31','z')],0,[],100)
 def test_invalid_deadline_fails_closed(self):
  with self.assertRaises(r.AdmissionBlocked):r.choose(self.pool,0,[{'retry_at_epoch':'unknown'}],100)
 def test_persists_only_slot_not_secret(self):
  from automation.agri_v2 import recovery,image_transport
  with tempfile.TemporaryDirectory() as d,patch.object(r,'OUT',Path(d)),patch.object(recovery,'circuit_open',return_value=False),patch.object(image_transport,'shared_evidence',return_value=[]):
   r.route([('AGNES_API_KEY','private-secret-value')],0,{'GITHUB_ACTIONS':'true'})
   text=(Path(d)/'image-key-routing.json').read_text();self.assertNotIn('private-secret-value',text);self.assertIn('AGNES_API_KEY',text)
 def test_pool_change_still_continues_after_last_verified_slot(self):
  from automation.agri_v2 import recovery,image_transport
  from automation.agri_v2.queue import atomic_json
  with tempfile.TemporaryDirectory() as tmp,patch.object(r,'OUT',Path(tmp)),patch.object(recovery,'circuit_open',return_value=False),patch.object(image_transport,'shared_evidence',return_value=[]):
   atomic_json(Path(tmp)/'image-key-routing.json',{'cursor':2,'last_selected_slot':'AGNES_API_KEY2'})
   picked=r.route([('AGNES_API_KEY2','b'),('AGNES_API_KEY3','c')],0,{'GITHUB_ACTIONS':'true'})
   self.assertEqual(picked[0],'AGNES_API_KEY3')

 def test_text_only_outage_does_not_block_image_routing(self):
  from automation.agri_v2 import recovery,image_transport
  with tempfile.TemporaryDirectory() as d,patch.object(r,'OUT',Path(d)),patch.object(recovery,'circuit_open',side_effect=lambda kind=None:kind!='image') as circuit,patch.object(image_transport,'shared_evidence',return_value=[]):
   self.assertEqual(r.route(self.pool,0,{'GITHUB_ACTIONS':'true'})[0],'AGNES_API_KEY')
   circuit.assert_called_once_with('image')
