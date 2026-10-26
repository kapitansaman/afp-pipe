import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import image_key_audit as a,cycle
from automation.agri_v2.queue import atomic_json,load_json
class AuditTests(unittest.TestCase):
 def health(self):return {'checked_at':'2026-10-24T08:28:09+00:00','image_model':a.IMAGE_MODEL,'api_base':a.API_BASE,'slots':[{'slot':s,'text':{'state':'healthy'},'image':{'state':'not_probed'}} for s in a.SLOTS],'eligible_image_slots':['AGNES_API_KEY']}
 def test_unique_first_fifteen_only(self):
  slots,aliases=a.unique_slots({'AGNES_API_KEY':'a','AGNES_API_KEY2':'b','AGNES_API_KEY8':'a','AGNES_API_KEY23':'c'})
  self.assertEqual(len(slots),2);self.assertEqual(aliases,{'AGNES_API_KEY8':'AGNES_API_KEY'})
 def test_long_retry_after_preserved(self):self.assertEqual(a.retry_seconds('3600'),3600)
 def test_retry_after_http_date(self):self.assertEqual(a.retry_seconds('Sun, 25 Oct 2026 03:00:00 GMT',1792893600),3600)
 def test_limit_and_uncertain_errors_stop(self):
  for status in (402,429,500,503,None):self.assertTrue(a.terminal({'http_status':status,'state':'failure'}))
  for status,state in ((401,'invalid_auth'),(403,'forbidden'),(200,'healthy')):self.assertFalse(a.terminal({'http_status':status,'state':state}))
 def test_image_evidence_does_not_refresh_text(self):
  h=self.health();before=copy.deepcopy(h);a.apply_result(h,'AGNES_API_KEY2',{'state':'healthy','checked_at':'new'})
  self.assertEqual(h['checked_at'],before['checked_at']);self.assertEqual([x['text'] for x in h['slots']],[x['text'] for x in before['slots']]);self.assertIn('AGNES_API_KEY2',h['eligible_image_slots'])
 def setup_paths(self,d):
  root=Path(d);data=root/'data';out=root/'out';atomic_json(data/'config.json',{'legacy_one_off_hooks_enabled':True});atomic_json(data/'image-key-audit-request.json',a.REQUEST);atomic_json(data/'health/latest.json',self.health());return root,data,out
 def test_cooldown_spends_no_calls_or_reservation(self):
  with tempfile.TemporaryDirectory() as d:
   root,data,out=self.setup_paths(d)
   with patch.object(a,'DATA',data),patch.object(a,'OUT',out),patch.object(a,'circuit_open',return_value=True),patch.object(a,'update'):
    self.assertEqual(a.run(env={},probe_fn=lambda *x:self.fail('paid request'))['model_calls'],0);self.assertFalse((out/'image-key-audit'/a.ID/'report.json').exists())
 def test_503_stops_before_second_key_no_automatic_replay(self):
  with tempfile.TemporaryDirectory() as d:
   root,data,out=self.setup_paths(d);calls=[]
   def probe(s,k):calls.append(s);return {'state':'provider_unavailable','http_status':503,'provider_code':'image_queue_full','retry_after_seconds':600},None
   with patch.object(a,'DATA',data),patch.object(a,'OUT',out),patch.object(a,'ROOT',root),patch.object(a,'circuit_open',return_value=False),patch.object(a,'defer_provider',return_value=999),patch.object(a,'update'):
    r=a.run(env={'AGNES_API_KEY':'secret-a','AGNES_API_KEY2':'secret-b','AGNES_API_KEY8':'secret-a'},probe_fn=probe);self.assertEqual(r['model_calls'],1);self.assertEqual(calls,['AGNES_API_KEY2']);self.assertIsNone(a.run(env={},probe_fn=probe));text=(out/'image-key-audit'/a.ID/'report.json').read_text();self.assertNotIn('secret-a',text);self.assertNotIn('secret-b',text)
 def test_success_updates_only_verified_slots(self):
  with tempfile.TemporaryDirectory() as d:
   root,data,out=self.setup_paths(d)
   with patch.object(a,'DATA',data),patch.object(a,'OUT',out),patch.object(a,'ROOT',root),patch.object(a,'circuit_open',return_value=False),patch.object(a,'update'):
    r=a.run(env={'AGNES_API_KEY2':'secret-b'},probe_fn=lambda *x:({'state':'healthy','http_status':200},b'validated-by-probe-fixture'));self.assertEqual(r['model_calls'],1);self.assertIn('AGNES_API_KEY2',load_json(data/'health/latest.json')['eligible_image_slots'])
 def test_scheduled_audit_never_calls_wordpress(self):
  with tempfile.TemporaryDirectory() as d:
   root,data,out=self.setup_paths(d)
   with patch.object(cycle,'DATA',data),patch.object(a,'run',return_value={'status':'waiting','model_calls':0}),patch.object(cycle,'WordPress') as wp:
    self.assertEqual(cycle.run(scheduled=True)['model_calls'],0);wp.assert_not_called()
