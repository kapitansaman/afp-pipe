import tempfile,unittest,datetime,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import runtime_health as h
from automation.agri_v2.queue import atomic_json,load_json,utcnow
class RuntimeHealthTests(unittest.TestCase):
 def fixture(self,data):
  atomic_json(data/'config.json',{'runtime_health':{'enabled':True,'max_text_probes_per_6h':1,'max_image_probes':0}})
  atomic_json(data/'health/latest.json',{'checked_at':'2000-01-01T00:00:00+00:00','eligible_text_slots':['AGNES_API_KEY'],'text_model':h.TEXT_MODEL,'image_model':h.IMAGE_MODEL,'api_base':h.API_BASE})
 def images(self):
  before=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=2)).isoformat()
  return {'text':{},'image':{'AGNES_API_KEY2':{'verified_at':before,'model':h.IMAGE_MODEL,'evidence_path':'fixture image proof'}}}
 def test_one_real_text_probe_plus_real_image_evidence_not_fake_new_image_probe(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)/'data';out=Path(tmp)/'out';self.fixture(data);ev=self.images();probe=Mock(return_value=({'http_status':200},{'model':h.TEXT_MODEL,'choices':[{'message':{'content':'OK'}}]}))
   with patch.object(h,'evidence',return_value=ev),patch.object(h,'circuit_open',return_value=False):
    result=h.ensure_fresh(data,out,{'AGNES_API_KEY':'fixture'},probe);self.assertEqual(result['model_calls'],1);self.assertEqual(result['new_image_calls'],0)
    report=load_json(data/'health/latest.json');self.assertEqual(report['checked_at'],ev['image']['AGNES_API_KEY2']['verified_at']);self.assertNotEqual(report['checked_at'],report['rebuilt_at'])
    self.assertEqual(report['eligible_image_slots'],['AGNES_API_KEY2']);self.assertEqual(report['eligible_text_slots'],['AGNES_API_KEY']);self.assertEqual(probe.call_count,1)
    self.assertEqual(h.ensure_fresh(data,out,{},probe)['status'],'health_current');self.assertEqual(probe.call_count,1)
 def test_no_image_proof_no_hidden_paid_probe(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)/'data';self.fixture(data);probe=Mock()
   with patch.object(h,'evidence',return_value={'text':{},'image':{}}):self.assertEqual(h.ensure_fresh(data,Path(tmp)/'out',{},probe)['status'],'image_capability_evidence_expired')
   probe.assert_not_called()
 def test_failed_probe_never_rotates_or_retries_for_six_hours(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)/'data';out=Path(tmp)/'out';self.fixture(data);probe=Mock(return_value=({'http_status':429},None))
   with patch.object(h,'evidence',side_effect=lambda out:self.images()),patch.object(h,'circuit_open',return_value=False):
    self.assertEqual(h.ensure_fresh(data,out,{'AGNES_API_KEY':'fixture'},probe)['status'],'bounded_text_probe_failed')
    self.assertEqual(h.ensure_fresh(data,out,{'AGNES_API_KEY':'fixture'},probe)['status'],'text_probe_cooldown');self.assertEqual(probe.call_count,1)
    self.assertEqual(load_json(data/'health/latest.json')['checked_at'],'2000-01-01T00:00:00+00:00')
 def test_model_mismatch_does_not_refresh_report(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)/'data';self.fixture(data)
   with patch.object(h,'evidence',return_value=self.images()),patch.object(h,'circuit_open',return_value=False):
    r=h.ensure_fresh(data,Path(tmp)/'out',{'AGNES_API_KEY':'fixture'},lambda *a,**kw:({'http_status':200},{'model':'wrong','choices':[{'message':{'content':'OK'}}]}));self.assertEqual(r['status'],'bounded_text_probe_failed')
 def test_evidence_must_be_unexpired_and_not_future(self):
  self.assertFalse(h.fresh('2000-01-01T00:00:00+00:00'));self.assertFalse(h.fresh('2999-01-01T00:00:00+00:00'));self.assertTrue(h.fresh(utcnow()))
 def test_runtime_proof_validated_by_kind_model_and_slot(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);atomic_json(out/'runtime-health/image/AGNES_API_KEY2.json',{**__import__('automation.agri_v2.credential_policy',fromlist=['binding']).binding(),'kind':'image','slot':'AGNES_API_KEY2','model':h.IMAGE_MODEL,'api_base':h.API_BASE,'verified_at':utcnow(),'verification':'actual_successful_production_response'})
   atomic_json(out/'runtime-health/text/AGNES_API_KEY23.json',{'kind':'text','slot':'AGNES_API_KEY23','model':h.TEXT_MODEL,'api_base':h.API_BASE,'verified_at':utcnow(),'verification':'actual_successful_production_response'})
   ev=h.evidence(out);self.assertIn('AGNES_API_KEY2',ev['image']);self.assertFalse(ev['text'])
 def test_image_only_cooldown_does_not_prevent_text_health_probe(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)/'data';out=Path(tmp)/'out';self.fixture(data)
   probe=Mock(return_value=({'http_status':200},{'model':h.TEXT_MODEL,'choices':[{'message':{'content':'OK'}}]}))
   with patch.object(h,'evidence',return_value=self.images()),patch.object(h,'circuit_open',side_effect=lambda kind=None:kind!='text') as circuit:
    self.assertEqual(h.ensure_fresh(data,out,{'AGNES_API_KEY':'fixture'},probe)['model_calls'],1);circuit.assert_called_once_with('text')
