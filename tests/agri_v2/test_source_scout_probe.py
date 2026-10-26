import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import source_scout_probe as probe
from automation.agri_v2.queue import atomic_json,load_json,utcnow

class ProbeTests(unittest.TestCase):
 def setup(self,p):
  data=p/'data';out=p/'out'
  cfg={'repository':probe.REPO,'credential_set_id':'test-cohort','publication_enabled':False,'automatic_generation':False}
  atomic_json(data/'config.json',cfg);atomic_json(data/'source-scout-probe-request.json',probe.REQUEST)
  atomic_json(data/'health/latest.json',dict(cfg,checked_at=utcnow(),text_model=probe.TEXT_MODEL,eligible_text_slots=['AGNES_API_KEY2']))
  atomic_json(data/'research-source-catalog.json',{'version':4,'entries':[{'crops':['pumpkin'],'intents':['storage'],'urls':['https://extension.a.edu/storage','https://extension.b.edu/storage']}]})
  env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':probe.REPO,'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123','AGNES_API_KEY2':'PRIVATE-TEST-KEY'}
  topic={'id':probe.REQUEST['topic_id'],'title':'Pumpkin fruit storage','crop':'pumpkin','intent':'storage'}
  value={'document_ids':['s0','s1'],'crop_and_intent_match':True,'scope_limitations':'Whole pumpkin fruit only, not extracted seeds or regional numerical guidance.','reason':'Both fetched universities discuss mature pumpkin fruit storage and damage prevention.'}
  post=Mock(return_value=({'state':'responded','http_status':200},{'model':probe.TEXT_MODEL,'choices':[{'message':{'content':json.dumps(value)}}]}))
  def fetch(u):
   text='Pumpkin fruit storage source evidence. '*35
   return dict(url=u,text=text,fetched_at=utcnow(),sha256=hashlib.sha256(text.encode()).hexdigest())
  return data,out,env,topic,post,fetch
 def test_once_no_publication_and_no_config_or_queue_write(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,e,topic,post,fetch=self.setup(Path(t));before=(d/'config.json').read_bytes();reserve=Mock(return_value=True)
   with patch.object(probe,'items',return_value=[topic]),patch('automation.agri_v2.recovery.circuit_open',return_value=False):
    r=probe.run(e,d,o,post,reserve,fetch);again=probe.run(e,d,o,post,reserve,fetch)
   self.assertEqual(r['status'],'sources_selected');self.assertEqual(r['model_calls'],1);self.assertEqual(r['wordpress_calls'],0)
   self.assertEqual(again['status'],'already_reserved');post.assert_called_once();reserve.assert_called_once();self.assertEqual((d/'config.json').read_bytes(),before)
   self.assertNotIn('PRIVATE',json.dumps(r));self.assertFalse((d/'briefs').exists());self.assertFalse((o/'research').exists())
 def test_remote_reservation_blocks_paid_replay(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,e,topic,post,fetch=self.setup(Path(t))
   with patch.object(probe,'items',return_value=[topic]),patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=probe.run(e,d,o,post,lambda *_:False,fetch)
   self.assertEqual(r['status'],'already_reserved');post.assert_not_called()
 def test_no_scheduled_run_no_unpause_no_wrong_repository(self):
  for change in [{'GITHUB_EVENT_NAME':'schedule'},{'GITHUB_REPOSITORY':'getsalet/nono'}]:
   with tempfile.TemporaryDirectory() as t:
    d,o,e,topic,post,fetch=self.setup(Path(t));e.update(change)
    with self.assertRaises(ValueError):probe.run(e,d,o,post,Mock(),fetch)
    post.assert_not_called()
  with tempfile.TemporaryDirectory() as t:
   d,o,e,topic,post,fetch=self.setup(Path(t));cfg=load_json(d/'config.json');cfg['publication_enabled']=True;atomic_json(d/'config.json',cfg)
   with self.assertRaises(ValueError):probe.run(e,d,o,post,Mock(),fetch)
   post.assert_not_called()
 def test_provider_failure_never_retries_or_publishes(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,e,topic,post,fetch=self.setup(Path(t));post.return_value=({'state':'provider_busy','http_status':503},None)
   with patch.object(probe,'items',return_value=[topic]),patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=probe.run(e,d,o,post,lambda *_:True,fetch)
   post.assert_called_once();self.assertEqual(r['status'],'probe_failed');self.assertEqual(r['published_posts'],0)
 def test_request_is_exact_and_existing_cooldown_blocks_probe(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,e,topic,post,fetch=self.setup(Path(t))
   with patch('automation.agri_v2.recovery.circuit_open',return_value=True):r=probe.run(e,d,o,post,Mock(),fetch)
   self.assertEqual(r['model_calls'],0);post.assert_not_called()
   atomic_json(d/'source-scout-probe-request.json',dict(probe.REQUEST,max_text_calls=2))
   with self.assertRaises(ValueError):probe.run(e,d,o,post,Mock(),fetch)
