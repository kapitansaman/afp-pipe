import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import key_connection as k,healthcheck as h,image_transport,client,runtime_health,cycle
from automation.agri_v2.queue import atomic_json,load_json,utcnow
class KeyMigrationTests(unittest.TestCase):
 def config(self,data):
  cfg={'repository':'kapitansaman/afp-pipe','credential_set_id':k.ID,'max_key_slot':30,'publication_enabled':False,'automatic_generation':False}
  atomic_json(data/'config.json',cfg);return cfg
 def env(self):return {s:'PRIVATE_FIXTURE_TOKEN_'+str(i) for i,s in enumerate(h.SLOTS)}
 def text(self,*a,**kw):return {'state':'responded','http_status':200},{'model':h.TEXT_MODEL,'choices':[{'message':{'content':'OK'}}]}
 def test_all_thirty_secrets_are_mapped_in_every_generator_workflow(self):
  root=Path(__file__).resolve().parents[2]
  for p in (root/'.github/workflows').glob('afp-agri*.yml'):
   s=p.read_text()
   if 'AGNES_API_KEY:' not in s:continue
   self.assertNotIn('getsalet/nono',s)
   for i in range(1,31):self.assertIn('secrets.AGNES_API_KEY_'+str(i)+' }}',s,p.name)
 def test_all_thirty_unique_keys_can_be_verified_without_wordpress(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);calls=[]
   def image(slot,key):calls.append(slot);return {'state':'healthy','http_status':200},b'fixture image bytes'
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch('automation.agri_v2.wordpress.WordPress') as wp:
    result=k.run(self.env(),self.text,image,data,out,lambda *a:None);wp.assert_not_called()
   self.assertEqual(len(calls),30);self.assertEqual(result['text_calls'],30);self.assertEqual(result['image_calls'],30);self.assertEqual(len(result['eligible_image_slots']),30)
   self.assertFalse(result['production_enabled']);self.assertEqual(result['post_submissions'],0)
   text=json.dumps(result)+json.dumps(load_json(data/'health/latest.json'))
   self.assertNotIn('PRIVATE_FIXTURE_TOKEN',text)
   self.assertEqual(load_json(data/'health/latest.json')['repository'],'kapitansaman/afp-pipe')
 def test_explicit_single_image_budget_checks_all_text_but_only_one_image(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);image=Mock(return_value=({'state':'healthy','http_status':200},b'fixture image bytes'))
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):
    result=k.run(self.env(),self.text,image,data,out,lambda *a:None,max_image_calls=1)
   self.assertEqual(result['text_calls'],30);self.assertEqual(result['image_calls'],1);image.assert_called_once();self.assertEqual(result['max_image_calls'],1)
 def test_last_slot_is_included_and_next_is_rejected(self):
  self.assertEqual(len(h.SLOTS),30);self.assertEqual(h.SLOTS[-1],'AGNES_API_KEY30');self.assertNotIn('AGNES_API_KEY31',h.SLOTS)
 def test_invalid_budget_rejected_before_calls(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);paid=Mock()
   with self.assertRaises(ValueError):k.run(self.env(),paid,paid,data,out,max_image_calls=31)
   paid.assert_not_called()
 def test_duplicate_keys_do_not_consume_model_calls(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);env=self.env();env[h.SLOTS[-1]]=env[h.SLOTS[0]];paid=Mock()
   result=k.run(env,paid,paid,data,out,lambda *a:None);self.assertEqual(result['status'],'configuration_incomplete_or_duplicate');paid.assert_not_called()
 def test_missing_thirtieth_key_does_not_consume_model_calls(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);env=self.env();env.pop(h.SLOTS[-1]);paid=Mock()
   k.run(env,paid,paid,data,out,lambda *a:None);paid.assert_not_called()
 def test_shared_image_503_stops_before_trying_next_key(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);image=Mock(return_value=({'state':'provider_unavailable','http_status':503,'provider_code':'image_queue_full'},None))
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch('automation.agri_v2.pilot_resume.defer_provider') as wait:
    result=k.run(self.env(),self.text,image,data,out,lambda *a:None)
   image.assert_called_once();wait.assert_called_once();self.assertEqual(result['eligible_image_slots'],[]);self.assertEqual(result['text_calls'],30)
 def test_shared_text_limit_stops_before_next_key_and_before_images(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);text=Mock(return_value=({'state':'rate_limited','http_status':429},None));image=Mock()
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):result=k.run(self.env(),text,image,data,out,lambda *a:None)
   text.assert_called_once();image.assert_not_called();self.assertEqual(result['image_calls'],0);self.assertEqual(load_json(data/'health/latest.json')['unique_credentials_tested'],1)
 def test_admission_block_is_not_reported_as_a_paid_image_call(self):
  from automation.agri_v2.image_transport import AdmissionBlocked
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);image=Mock(side_effect=AdmissionBlocked('no lease'))
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):result=k.run(self.env(),self.text,image,data,out,lambda *a:None)
   self.assertEqual(result['image_calls'],0);self.assertTrue(result['image_not_sent_admission_blocked']);image.assert_called_once()
 def test_audit_reservation_cannot_be_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';self.config(data);paid=Mock()
   atomic_json(out/'key-connection'/k.ID/'report.json',{'status':'reserved'})
   result=k.run(self.env(),paid,paid,data,out,lambda *a:None);self.assertEqual(result['status'],'already_reserved');paid.assert_not_called()
 def test_legacy_capability_report_cannot_authorize_rotated_credentials(self):
  report={'checked_at':utcnow(),'text_model':h.TEXT_MODEL,'image_model':h.IMAGE_MODEL,'api_base':h.API_BASE,'eligible_text_slots':['AGNES_API_KEY'],'eligible_image_slots':['AGNES_API_KEY']}
  with self.assertRaisesRegex(client.CapabilityError,'another repository or credential set'):client.ModelClient(report,{'GITHUB_ACTIONS':'true','AGNES_API_KEY':'PRIVATE_FIXTURE'},True)
 def test_migrated_lease_never_uses_original_repository(self):
  from automation import blog_image_queue
  self.assertEqual(blog_image_queue.API,'https://api.github.com/repos/kapitansaman/afp-pipe')
 def test_paused_migration_cycle_has_zero_wordpress_or_model_calls(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d);self.config(data)
   with patch.object(cycle,'DATA',data),patch.object(cycle,'WordPress') as wp,patch.object(cycle,'draft') as draft:
    result=cycle.run(scheduled=True);self.assertEqual(result['status'],'publication_disabled');wp.assert_not_called();draft.assert_not_called()
 def test_old_repository_key_evidence_is_rejected(self):
  from automation.agri_v2.credential_policy import trusted
  self.assertFalse(trusted({'repository':'getsalet/nono','credential_set_id':'legacy'}))
