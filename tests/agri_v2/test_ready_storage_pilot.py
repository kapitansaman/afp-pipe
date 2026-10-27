import json,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import ready_storage_pilot as p,operation_request as op
from automation.agri_v2.queue import DATA,OUT,atomic_json,load_json,utcnow
from automation.agri_v2.parallel_pool import PoolDeferred

class ReadyStoragePilotTests(unittest.TestCase):
 def request(self):return dict(p.expected_request(),code_revision='a'*40)
 def env(self):return {'GITHUB_RUN_ID':'7654321','AFP_WP_BASE_URL':'test-only','AFP_WP_USERNAME':'test-only','AFP_WP_APP_PASSWORD':'test-only'}
 def fixture(self,root):
  data=root/'data';out=root/'out'
  for name in ('manifest.json','parallel-policy.json'):
   atomic_json(data/name,load_json(DATA/name))
  atomic_json(data/'status/owner-operation-admission.json',{'request_id':p.ID})
  atomic_json(data/'briefs'/(p.TOPIC+'.json'),load_json(DATA/'briefs'/(p.TOPIC+'.json')))
  shutil.copytree(OUT/'new'/p.TOPIC,out/'new'/p.TOPIC)
  atomic_json(out/'new/agri-621734b38aa9/protected.json',{'attempts':3})
  atomic_json(out/'parallel/families/assignments.json',{'unchanged':True})
  h=load_json(OUT/'parallel/health/latest.json');h['checked_at']=utcnow();atomic_json(out/'parallel/health/latest.json',h)
  return data,out
 def test_exact_request_rejects_expanded_or_publishing_scope(self):
  self.assertEqual(op.validate_request(self.request())['request_id'],p.ID)
  for k,v in [('max_total_text_calls',15),('max_image_calls',2),('max_pilot_families',20),('max_wordpress_mutations',1),('enable_schedule',True),('reset_attempts',True),('topic_id','agri-621734b38aa9')]:
   row=self.request();row[k]=v
   with self.assertRaises(ValueError):op.validate_request(row)
 def test_image_budget_is_one_and_never_replayed(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);p.charge(root,'image','test')
   with self.assertRaises(PoolDeferred):p.charge(root,'image','test')
   self.assertEqual(load_json(root/'model-calls.json')['image'],1)
 def test_text_budget_is_fourteen(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for _ in range(14):p.charge(root,'text','test')
   with self.assertRaises(PoolDeferred):p.charge(root,'text','test')
   p.charge(root,'image','test')
   self.assertEqual(len(load_json(root/'model-calls.json')['history']),15)
 def test_unknown_capability_rejected_without_receipt(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):p.charge(Path(t),'other','test')
   self.assertFalse((Path(t)/'model-calls.json').exists())
 def test_unadmitted_run_makes_no_calls(self):
  with patch.object(op,'authorize',return_value=False),patch.object(p,'source_inputs') as source:
   with self.assertRaises(ValueError):p.run(self.env())
   source.assert_not_called()
 def test_verified_run_preserves_originals_and_strips_publisher_secrets(self):
  with tempfile.TemporaryDirectory() as t:
   data,out=self.fixture(Path(t));topic,brief,article,folder=p.source_inputs();root=out/'parallel/operations'/p.ID;seen={}
   class Fake:
    def __init__(self,h,env,**kwargs):seen.update(env);self.env=env
    def image(self,*args,**kwargs):p.charge(root,'image','test');return b'test-image-only'
   def review(*args,**kwargs):p.charge(root,'text','test')
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy'),patch.object(p,'source_inputs',return_value=(topic,brief,article,out/'new'/p.TOPIC)),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=0),patch('automation.agri_v2.image_quality.ensure_review',side_effect=review),patch('automation.agri_v2.image_quality.valid_record',return_value={'review_policy':'test-only'}):
    result=p.run(self.env(),data,out,client_factory=Fake,reserve_fn=Mock(return_value={}))
    replay=p.run(self.env(),data,out,client_factory=Fake,reserve_fn=Mock(return_value={}))
   self.assertEqual(result['status'],'ready_nonpublishing_pilot_verified');self.assertEqual(replay['status'],'ready_pilot_already_reserved')
   self.assertEqual((result['model_calls'],result['image_calls'],result['published_posts'],result['wordpress_mutations']),(1,1,0,0))
   for k in ('protected_source_unchanged','white_bean_unchanged','assignments_unchanged','manifest_unchanged'):self.assertTrue(result[k])
   self.assertFalse(any(k.startswith('AFP_WP_') for k in seen))
 def test_provider_hold_does_not_call_factory(self):
  with tempfile.TemporaryDirectory() as t:
   data,out=self.fixture(Path(t));factory=Mock()
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy'),patch.object(p,'source_inputs',return_value=(dict(id=p.TOPIC,title='test'),{},{},out/'new'/p.TOPIC)),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=1):
    result=p.run(self.env(),data,out,client_factory=factory,reserve_fn=Mock(return_value={}))
   self.assertEqual(result['status'],'ready_pilot_provider_deferred');self.assertEqual(result['image_calls'],0);factory.assert_not_called()
 def test_real_source_pin_and_review_are_valid(self):
  topic,brief,article,folder=p.source_inputs();self.assertEqual(topic['id'],p.TOPIC)
  with patch('automation.agri_v2.pipeline.digest',return_value='changed'):
   with self.assertRaises(ValueError):p.source_inputs()
 def test_second_phase_only_reports_current_receipt(self):
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'status/owner-operation-admission.json',{'request_id':p.ID});rp=out/'parallel/operations'/p.ID/'prepare.json';atomic_json(rp,{'run_id':'7654321','status':'ready_nonpublishing_pilot_verified'})
   with patch.object(op,'authorize',return_value=True):
    self.assertEqual(p.result(self.env(),data,out)['image_calls'],0)
    with self.assertRaises(ValueError):p.result({'GITHUB_RUN_ID':'other'},data,out)
