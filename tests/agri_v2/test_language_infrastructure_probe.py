import json,tempfile,unittest,copy
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import language_infrastructure_probe as p
from automation.agri_v2.queue import DATA,OUT,load_json
from automation.agri_v2.healthcheck import TEXT_MODEL

class LanguageInfrastructureProbeTests(unittest.TestCase):
 def test_exact_accepted_source_and_request_binding(self):
  request=load_json(DATA/'language-infrastructure-probe-request.json');article,source=p.validate(request)
  self.assertEqual(source['article_sha256'],p.digest(article))
  for key,value in [('max_model_calls',17),('max_site_calls',1),('publication_authorized',True),('schedule_enabled',True),('reset_attempts',True),('source_article_sha256','changed'),('code_sha256','changed')]:
   with self.subTest(key=key),self.assertRaises(p.LanguageProbeBlocked):p.validate(dict(request,**{key:value}))
 def client(self,root,error=None):
  class Base:
   def __init__(self,*args,**kwargs):self.calls=0
   def request(self,*args,**kwargs):
    self.calls+=1;self.attempts=kwargs['attempts']
    if error:raise error
    return {'choices':[]}
  return p.CountedLanguageClient({}, {},root,base_class=Base)
 def payload(self,n=0):return {'model':TEXT_MODEL,'max_tokens':14000,'messages':[{'content':'fixture-'+str(n)}]}
 def test_one_transport_attempt_and_duplicate_unknown_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   client=self.client(Path(d),TimeoutError());client.probe_language='en-US'
   with self.assertRaises(TimeoutError):client.request('text','/chat/completions',self.payload(),180,attempts=9)
   with self.assertRaises(p.LanguageProbeBlocked):client.request('text','/chat/completions',self.payload(),180)
   self.assertEqual(client.calls,1);self.assertEqual(client.attempts,1)
 def test_no_more_than_four_calls_per_language_or_sixteen_total(self):
  from automation.agri_v2.multilingual import LANGUAGES
  with tempfile.TemporaryDirectory() as d:
   client=self.client(Path(d))
   for lang in LANGUAGES:
    client.probe_language=lang
    for i in range(4):client.request('text','/chat/completions',self.payload(i),180)
    with self.assertRaises(p.LanguageProbeBlocked):client.request('text','/chat/completions',self.payload(4),180)
   self.assertEqual(client.calls,16)
 def test_wrong_capability_endpoint_language_and_payload_rejected_before_transport(self):
  with tempfile.TemporaryDirectory() as d:
   client=self.client(Path(d));client.probe_language='en-US'
   for kind,path,payload in [('image','/images/generations',self.payload()),('text','/posts',self.payload()),('text','/chat/completions',dict(self.payload(),max_tokens=14001)),('text','/chat/completions',dict(self.payload(),messages=['x'*200001]))]:
    with self.assertRaises(p.LanguageProbeBlocked):client.request(kind,path,payload,180)
   client.probe_language='unapproved'
   with self.assertRaises(p.LanguageProbeBlocked):client.request('text','/chat/completions',self.payload(),180)
   self.assertEqual(client.calls,0)
 def test_duplicate_remote_reservation_is_create_only(self):
  import urllib.error
  from automation.agri_v2.parallel_control import REPO,BRANCH
  env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':REPO,'GITHUB_REF_NAME':BRANCH,'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123','GITHUB_TOKEN':'synthetic-private'}
  opener=Mock();opener.open.side_effect=urllib.error.HTTPError('https://api.github.com',422,'exists',{},None)
  with patch.object(p.urllib.request,'build_opener',return_value=opener):self.assertFalse(p.reserve(env))
  payload=json.loads(opener.open.call_args.args[0].data);self.assertNotIn('sha',payload);self.assertEqual(payload['branch'],BRANCH)
 def fixture(self):
  article={'title':'منبع فارسی','content_html':'<p>متن فارسی بدون عدد</p>','excerpt':'خلاصه','faq':[]};source=['متن فارسی بدون عدد','عبارت دوم فارسی']
  return article,source
 def language_case(self,responses):
  article,source=self.fixture();client=Mock();client.text.side_effect=responses
  context=[patch('automation.agri_v2.multilingual.source_segments',return_value=(None,source)),patch('automation.agri_v2.multilingual.render_translation',return_value={'language':'en-US','content_html':'translated prose'})]
  return article,client,context
 def test_positive_review_uses_two_calls_and_never_manufactures_edit(self):
  responses=[{'translations':[{'id':0,'text':'Source text'},{'id':1,'text':'Second text'}]},{'faithful':True,'reason':'Faithful to the actual source.','issues':[]}]
  article,client,context=self.language_case(responses)
  with tempfile.TemporaryDirectory() as d,context[0],context[1]:
   result=p.language(client,article,'en-US',Path(d));self.assertEqual(result['status'],'fidelity_passed');self.assertFalse(result['repair_exercised']);self.assertFalse((Path(d)/'languages/en-US/edit.receipt.json').exists())
  self.assertEqual(client.text.call_count,2)
 def test_one_source_bound_edit_then_independent_recheck(self):
  responses=[{'translations':[{'id':0,'text':'Source text'},{'id':1,'text':'Second text'}]},{'faithful':False,'reason':'Actual meaning defect.','issues':[{'id':0,'detail':'Actual source meaning was changed.'}]},{'patches':[{'id':0,'text':'Corrected source text'}]},{'faithful':True,'reason':'Corrected meaning preserved.','issues':[]}]
  article,client,context=self.language_case(responses)
  with tempfile.TemporaryDirectory() as d,context[0],context[1]:
   result=p.language(client,article,'en-US',Path(d));self.assertTrue(result['repair_exercised']);self.assertTrue((Path(d)/'languages/en-US/before-edit.json').exists())
  self.assertEqual(client.text.call_count,4)
 def test_negative_recheck_is_retained_no_second_edit_or_forced_pass(self):
  negative={'faithful':False,'reason':'Actual meaning defect.','issues':[{'id':0,'detail':'Actual source meaning was changed.'}]}
  responses=[{'translations':[{'id':0,'text':'Source text'},{'id':1,'text':'Second text'}]},negative,{'patches':[{'id':0,'text':'Corrected source text'}]},negative]
  article,client,context=self.language_case(responses)
  with tempfile.TemporaryDirectory() as d,context[0],context[1]:
   with self.assertRaises(p.LanguageProbeBlocked):p.language(client,article,'en-US',Path(d))
   self.assertFalse((Path(d)/'languages/en-US/approved.json').exists())
  self.assertEqual(client.text.call_count,4)
 def test_preexisting_report_never_replays_or_calls_provider(self):
  from automation.agri_v2.queue import atomic_json
  from automation.agri_v2.parallel_control import REPO,BRANCH
  env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':REPO,'GITHUB_REF_NAME':BRANCH,'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123'}
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);atomic_json(out/'infrastructure-probes'/p.ID/'report.json',{'status':'language_probe_blocked'});factory=Mock()
   result=p.run(env,out=out,client_factory=factory);factory.assert_not_called();self.assertEqual(result['status'],'language_probe_already_reserved_no_replay')
