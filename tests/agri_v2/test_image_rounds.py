import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import image_rounds as r
from automation.agri_v2.client import CapabilityError,ImageProviderError
from automation.agri_v2.healthcheck import IMAGE_MODEL,SLOTS
from automation.agri_v2.queue import load_json
class RoundTests(unittest.TestCase):
 def client(self,answer):
  c=Mock();c.image_rotation_binding='test30';c.image_candidates=[(n,'PRIVATE-'+str(i)) for i,n in enumerate(SLOTS)];c.keys={'image':c.image_candidates[:]};c.record_success=Mock()
  def call(*a,**kw):
   name=c.keys['image'][0][0];c._image_reserve_attempt(name);return answer(name)
  c.request=Mock(side_effect=call);return c
 def test_all_thirty_rejected_once_then_no_automatic_replay(self):
  def answer(n):raise ImageProviderError(401,None,'invalid_auth')
  with tempfile.TemporaryDirectory() as d,patch.object(r,'OUT',Path(d)):
   c=self.client(answer)
   with self.assertRaises(CapabilityError):r.generate(c,{'prompt':'test'},[])
   self.assertEqual(c.request.call_count,30)
   with self.assertRaises(CapabilityError):r.generate(c,{'prompt':'test'},[])
   self.assertEqual(c.request.call_count,30)
   text=next(Path(d).glob('image-key-rounds/*/report.json')).read_text();self.assertNotIn('PRIVATE',text);report=load_json(next(Path(d).glob('image-key-rounds/*/report.json')));self.assertEqual(len({x['slot'] for x in report['attempts']}),30)
 def test_success_on_second_key_stops_and_reuses_saved_image(self):
  def answer(n):
   if n==SLOTS[0]:raise ImageProviderError(403,None,'forbidden')
   return {'model':IMAGE_MODEL}
  with tempfile.TemporaryDirectory() as d,patch.object(r,'OUT',Path(d)),patch('automation.agri_v2.client.render_image',return_value=b'valid-image'):
   c=self.client(answer);self.assertEqual(r.generate(c,{'prompt':'test'},[]),b'valid-image');self.assertEqual(c.request.call_count,2);self.assertEqual(r.generate(c,{'prompt':'test'},[]),b'valid-image');self.assertEqual(c.request.call_count,2)
 def test_shared_503_defers_next_key_and_honors_retry_after(self):
  def answer(n):raise ImageProviderError(503,'image_queue_full','provider_unavailable',7200)
  with tempfile.TemporaryDirectory() as d,patch.object(r,'OUT',Path(d)),patch.object(r.time,'time',return_value=100):
   c=self.client(answer)
   with self.assertRaises(ImageProviderError):r.generate(c,{'prompt':'test'},[])
   with self.assertRaises(ValueError):r.generate(c,{'prompt':'test'},[])
   self.assertEqual(c.request.call_count,1);report=load_json(next(Path(d).glob('image-key-rounds/*/report.json')));self.assertEqual(report['retry_at_epoch'],7300)
 def test_malformed_image_moves_to_next_key(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'OUT',Path(d)),patch('automation.agri_v2.client.render_image',side_effect=[CapabilityError('invalid'),b'valid']):
   c=self.client(lambda n:{'model':IMAGE_MODEL});self.assertEqual(r.generate(c,{'prompt':'test'},[]),b'valid');self.assertEqual(c.request.call_count,2)

 def test_deferred_round_continues_with_next_key_after_deadline(self):
  names=[]
  def answer(n):
   names.append(n)
   if len(names)==1:raise ImageProviderError(503,'image_queue_full','provider_unavailable',5)
   return {'model':IMAGE_MODEL}
  with tempfile.TemporaryDirectory() as d,patch.object(r,'OUT',Path(d)),patch('automation.agri_v2.client.render_image',return_value=b'valid'):
   c=self.client(answer)
   with patch.object(r.time,'time',return_value=100):
    with self.assertRaises(ImageProviderError):r.generate(c,{'prompt':'test'},[])
   with patch.object(r.time,'time',return_value=2000):self.assertEqual(r.generate(c,{'prompt':'test'},[]),b'valid')
   self.assertEqual(names,SLOTS[:2])

 def test_owner_round_includes_all_thirty_configured_candidates(self):
  from automation.agri_v2.client import ModelClient
  from automation.agri_v2.healthcheck import TEXT_MODEL,API_BASE
  from automation.agri_v2.queue import utcnow
  report={'checked_at':utcnow(),'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,'eligible_text_slots':[SLOTS[0]],'eligible_image_slots':[SLOTS[0]]}
  env={name:'PRIVATE-'+str(i) for i,name in enumerate(SLOTS)}
  with patch('automation.agri_v2.queue.load_json',return_value={'credential_set_id':'test30','image_key_rotation':{'enabled':True}}):client=ModelClient(report,env,True)
  self.assertEqual(len(client.image_candidates),30);self.assertEqual(client.image_candidates[-1][0],SLOTS[-1])
