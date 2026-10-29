import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import post_hold_validation as p
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json
from automation.agri_v2.healthcheck import TEXT_MODEL

class PostHoldValidationTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123'}
 def test_exact_source_old_unknown_and_unattempted_languages_bound(self):
  req=p.expected();p.validate(req)
  for key,value in [('languages',['ar-IQ']),('max_model_calls',10),('max_site_calls',1),('reset_attempts',True),('publication_authorized',True),('code_sha256','changed'),('prior_probe_sha256','changed')]:
   with self.subTest(key=key),self.assertRaises(p.ValidationBlocked):p.validate(dict(req,**{key:value}))
 def test_prior_attempt_to_unattempted_language_blocks_admission(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'infrastructure-probes'/p.prior.ID;atomic_json(root/'report.json',{'status':'language_probe_blocked','model_calls':4,'languages':[{'language':'ru-RU'},{'language':'ar-IQ'}]})
   for n in range(4):atomic_json(root/'calls/ru-RU'/(str(n)+'.json'),{})
   (root/'languages/tg-TJ').mkdir(parents=True)
   with patch.object(p.prior,'inputs',return_value=({},{})),self.assertRaises(p.ValidationBlocked):p.expected(out=Path(d))
 def client(self,root,error=None):
  class Base:
   def __init__(self,*args,**kwargs):self.calls=0
   def request(self,*args,**kwargs):
    self.calls+=1;self.attempts=kwargs['attempts']
    if error:raise error
    return {'choices':[]}
  return p.CountedClient({}, {},root,base_class=Base)
 def payload(self,n=0):return {'model':TEXT_MODEL,'max_tokens':14000,'messages':[{'role':'user','content':'fixture-'+str(n)}]}
 def health(self):return {'model':TEXT_MODEL,'max_tokens':256,'messages':[{'role':'user','content':p.HEALTH_PROMPT}],'response_format':{'json_schema':{'schema':p.SCHEMA}}}
 def test_health_once_only_and_one_transport_attempt(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d));c.probe_language='health';c.request('text','/chat/completions',self.health(),45,attempts=5)
   with self.assertRaises(p.ValidationBlocked):c.request('text','/chat/completions',self.health(),45)
   self.assertEqual((c.calls,c.attempts),(1,1))
 def test_unknown_health_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d),TimeoutError());c.probe_language='health'
   with self.assertRaises(TimeoutError):c.request('text','/chat/completions',self.health(),45)
   with self.assertRaises(p.ValidationBlocked):c.request('text','/chat/completions',self.health(),45)
   self.assertEqual(c.calls,1)
 def test_ru_ar_image_site_and_unhealthy_language_blocked_before_transport(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d))
   for lang,kind,path in [('ru-RU','text','/chat/completions'),('ar-IQ','text','/chat/completions'),('tg-TJ','text','/chat/completions'),('tg-TJ','image','/images/generations'),('en-US','text','/posts')]:
    c.probe_language=lang
    with self.assertRaises(p.ValidationBlocked):c.request(kind,path,self.payload(),180)
   self.assertEqual(c.calls,0)
 def test_eight_language_calls_maximum_four_per_language(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);atomic_json(root/'health-passed.json',{'status':'passed'});c=self.client(root)
   for lang in p.LANGUAGES:
    c.probe_language=lang
    for n in range(4):c.request('text','/chat/completions',self.payload(n+(0 if lang=='tg-TJ' else 10)),180)
    with self.assertRaises(p.ValidationBlocked):c.request('text','/chat/completions',self.payload(99),180)
   self.assertEqual(c.calls,8)
 def test_hold_blocks_before_remote_reservation_or_client(self):
  factory=Mock();reserve=Mock()
  with patch.object(p,'circuit'),patch.object(p,'validate'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=True),patch.object(p,'load_json',return_value={}):
   result=p.run(self.env(),client_factory=factory,reserve_fn=reserve)
  self.assertEqual(result['status'],'post_hold_provider_waiting');factory.assert_not_called();reserve.assert_not_called()
 def test_preexisting_report_blocks_all_new_calls(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);atomic_json(root/'infrastructure-probes'/p.ID/'report.json',{'status':'post_hold_reserved'});factory=Mock();reserve=Mock();r=p.run(self.env(),out=root,client_factory=factory,reserve_fn=reserve)
   self.assertEqual(r['model_calls'],0);factory.assert_not_called();reserve.assert_not_called()
 def test_create_only_remote_reservation_and_exact_manual_identity(self):
  from automation.agri_v2.parallel_control import reserve
  put=Mock(return_value=True);r=reserve('post-hold-validation',p.ID,self.env(),put_fn=put);self.assertEqual(r['request_id'],p.ID)
  for env,ident in [(dict(self.env(),GITHUB_EVENT_NAME='schedule'),p.ID),(self.env(),'new-replay-id')]:
   with self.assertRaises(ValueError):reserve('post-hold-validation',ident,env,put_fn=put)

 def test_single_hold_wait_is_bounded_and_never_edits_circuit(self):
  with tempfile.TemporaryDirectory() as d,patch.object(p.time,'time',return_value=100):
   out=Path(d);row={'open':True,'request_kind':'text','retry_at_epoch':105};atomic_json(out/'provider-circuit.json',row);sleep=Mock();p.wait_for_release(out,sleep);sleep.assert_called_once_with(5);self.assertEqual(load_json(out/'provider-circuit.json'),row)
   for deadline in (1901,True,float('inf')):
    atomic_json(out/'provider-circuit.json',dict(row,retry_at_epoch=deadline));sleep=Mock()
    with self.assertRaises(p.ValidationBlocked):p.wait_for_release(out,sleep)
    sleep.assert_not_called()

 def test_malformed_circuit_is_not_treated_as_expired_permission(self):
  with tempfile.TemporaryDirectory() as d:
   for row in ({'open':'yes','retry_at_epoch':0},{'open':True,'request_kind':'text'},{'open':True,'request_kind':'text','retry_at_epoch':True},{'open':False,'request_kind':'unknown'}):
    atomic_json(Path(d)/'provider-circuit.json',row)
    with self.assertRaises(p.ValidationBlocked):p.circuit(Path(d))
