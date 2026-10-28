import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from automation.agri_v2 import family_capability_refresh as r,family_model_routing as m,family_keys as k,parallel_client as pc
from automation.agri_v2.parallel_pool import SLOTS,initialize,snapshot
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.parallel_capacity import CREDENTIAL_SET_ID
from automation.agri_v2.healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
from automation.agri_v2.client import CapabilityError
class CapabilityRefreshTests(unittest.TestCase):
 def setup(self,root):
  d=root/'data';o=root/'out';atomic_json(d/'parallel-policy.json',{'repository':'kapitansaman/afp-pipe','key_limit':97,'max_article_workers':20,'credential_set_id':CREDENTIAL_SET_ID,'image_concurrency':1,'production_enabled':False,'max_published_posts':0,'family_key_allocation_required':True,'family_model_routing_required':True});atomic_json(d/'family-key-allocation.json',k.default_policy());roles=m.expected(d);atomic_json(d/'family-model-routing.json',roles)
  env={s:'synthetic-'+str(i) for i,s in enumerate(SLOTS)};env.update(GITHUB_ACTIONS='true',GITHUB_REPOSITORY='kapitansaman/afp-pipe',GITHUB_RUN_ID='123',GITHUB_EVENT_NAME='workflow_dispatch');return d,o,env,roles
 def post(self,*args,**kwargs):return {'http_status':200},{'model':TEXT_MODEL,'choices':[{'message':{'content':'OK'}}]}
 def probe(self,*args,**kwargs):
  buf=io.BytesIO();Image.new('RGB',(1200,675),'green').save(buf,'WEBP');return {'state':'healthy','http_status':200},buf.getvalue()
 def test_roles_preserve_97_partition_and_pin_fourth_image(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));self.assertEqual(m.slots('family-01','text',d),SLOTS[:3]);self.assertEqual(m.slots('family-01','image',d),[SLOTS[3]]);self.assertEqual(m.slots('family-20','image',d),[SLOTS[79]]);self.assertEqual(k.load(d),k.default_policy())
 def test_tampered_roles_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));roles['families']['family-01']['image_slot']=SLOTS[4];atomic_json(d/'family-model-routing.json',roles)
   with self.assertRaises(CapabilityError):m.load(d)
 def test_text_refresh_uses_text_model_only_and_no_pinned_image_keys(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));post=Mock(side_effect=self.post);rr=r.text(e,d,o,post,Mock(return_value={}));h=load_json(o/'parallel/health/latest.json');self.assertEqual(rr['model_calls'],77);self.assertEqual(rr['image_calls'],0);self.assertEqual(rr['families_with_text'],20);self.assertEqual(h['eligible_image_slots'],[])
   for c in post.call_args_list:self.assertEqual(c.args[0],'/chat/completions');self.assertEqual(c.args[2]['model'],TEXT_MODEL);self.assertNotIn(c.args[1],[e[x['image_slot']] for x in roles['families'].values()])
 def test_fresh_role_bound_text_health_reused_without_new_requests(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));r.text(e,d,o,self.post,Mock(return_value={}));api=Mock();reserve=Mock();rr=r.text(e,d,o,api,reserve);self.assertEqual(rr['model_calls'],0);api.assert_not_called();reserve.assert_not_called()
 def test_reserved_remote_refresh_never_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));api=Mock();rr=r.text(e,d,o,api,Mock(return_value=None));api.assert_not_called();self.assertEqual(rr['status'],'capability_already_reserved_no_replay')
 def test_image_probe_independent_of_text_success_and_pinned_to_own_family(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));probe=Mock(side_effect=self.probe);rr=r.images(e,d,o,probe,Mock(return_value={}));self.assertEqual(rr['image_calls'],4);self.assertEqual(rr['proven_families'],4);self.assertEqual(rr['model_calls'],0)
   self.assertEqual([c.args[0] for c in probe.call_args_list],[SLOTS[i] for i in (3,7,11,15)])
   for c in probe.call_args_list:self.assertEqual(c.args[1],e[c.args[0]]);self.assertEqual(c.kwargs['env']['AFP_PARALLEL_WORKER'],'1')
   self.assertEqual(load_json(o/'parallel/health/latest.json').get('eligible_text_slots',[]),[])
 def test_next_image_batch_skips_already_proven_without_key_rotation(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));r.images(e,d,o,self.probe,Mock(return_value={}));probe=Mock(side_effect=self.probe);rr=r.images(dict(e,GITHUB_RUN_ID='124'),d,o,probe,Mock(return_value={}));self.assertEqual(rr['proven_families'],8);self.assertEqual(probe.call_args_list[0].args[0],SLOTS[19])
 def test_timeout_stops_image_batch_and_does_not_borrow_key(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));probe=Mock(side_effect=TimeoutError());rr=r.images(e,d,o,probe,Mock(return_value={}));probe.assert_called_once();self.assertEqual(rr['proven_families'],0);self.assertEqual(rr['status'],'incomplete_provider_failure');self.assertTrue((o/'provider-circuit.json').exists())
 def test_quota_is_account_specific_not_text_or_shared_image_capability(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));rr=r.images(e,d,o,Mock(return_value=({'state':'quota_limited','http_status':429},None)),Mock(return_value={}));self.assertEqual(rr['image_calls'],4);self.assertEqual(rr['proven_families'],0);self.assertFalse((o/'provider-circuit.json').exists());self.assertEqual([x['slot'] for x in rr['cases']],[SLOTS[i] for i in (3,7,11,15)])
 def test_remote_image_uncertainty_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));probe=Mock();rr=r.images(e,d,o,probe,Mock(return_value=None));probe.assert_not_called();self.assertEqual(rr['status'],'capability_reconciliation_required')
 def test_nonmanual_and_duplicate_credentials_fail_before_call(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));api=Mock()
   with self.assertRaises(ValueError):r.text(dict(e,GITHUB_EVENT_NAME='schedule'),d,o,api,Mock())
   e[SLOTS[1]]=e[SLOTS[0]]
   with self.assertRaises(CapabilityError):r.images(e,d,o,api,Mock())
   api.assert_not_called()
 def test_production_client_uses_separate_roles_and_actual_image_proof(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o,e,roles=self.setup(root);r.text(e,d,o,self.post,Mock(return_value={}));r.images(e,d,o,self.probe,Mock(return_value={}));h=load_json(o/'parallel/health/latest.json');db=root/'db';initialize(db,SLOTS);e.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_FAMILY='family-01',AFP_PARALLEL_TOPIC='agri-000000000001')
   with patch.object(pc,'DATA',d):
    c=pc.ParallelModelClient(h,env=e,allow_calls=True,capabilities=('text','image'));self.assertEqual([x[0] for x in c.keys['text']],SLOTS[:3]);self.assertEqual([x[0] for x in c.keys['image']],[SLOTS[3]])
    with self.assertRaises(CapabilityError):c.request('image','/chat/completions',{'model':TEXT_MODEL},120)
    self.assertEqual(snapshot(db)['model_requests_reserved'],0)
 def test_text_success_never_grants_pinned_image_without_proof(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o,e,roles=self.setup(root);r.text(e,d,o,self.post,Mock(return_value={}));h=load_json(o/'parallel/health/latest.json');h['eligible_image_slots']=[SLOTS[3]];db=root/'db';initialize(db,SLOTS);e.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_FAMILY='family-01',AFP_PARALLEL_TOPIC='agri-000000000001')
   with patch.object(pc,'DATA',d),self.assertRaises(CapabilityError):pc.ParallelModelClient(h,env=e,allow_calls=True,capabilities=('image',))
 def test_actual_image_probe_uses_image_model_and_image_endpoint(self):
  from automation.agri_v2 import image_key_audit as audit
  import contextlib
  reply=Mock();reply.read.return_value=b'{"model":"agnes-image-2.5-flash","data":[]}'
  response=Mock();response.__enter__=Mock(return_value=reply);response.__exit__=Mock(return_value=False)
  with patch.object(audit,'admission',return_value=contextlib.nullcontext()),patch.object(audit.urllib.request,'urlopen',return_value=response) as call,patch.object(audit,'render_image',return_value=b'validated-image'):
   safe,blob=audit.probe('AGNES_API_KEY4','PRIVATE',env={'GITHUB_ACTIONS':'false'})
  request=call.call_args.args[0];self.assertTrue(request.full_url.endswith('/images/generations'));payload=json.loads(request.data);self.assertEqual(payload['model'],IMAGE_MODEL);self.assertNotEqual(payload['model'],TEXT_MODEL);self.assertEqual(safe['state'],'healthy');self.assertNotIn('PRIVATE',request.data.decode())
 def test_daily_reservation_cannot_use_arbitrary_id_or_repeat_epoch(self):
  from automation.agri_v2.parallel_control import reserve
  with self.assertRaises(ValueError):reserve('capability','anything',{'GITHUB_RUN_ID':'1'},put_fn=lambda row:True)
  rid='family-capability-'+r.day()+'-image-AGNES_API_KEY4';calls=[];row=reserve('capability',rid,{'GITHUB_RUN_ID':'1'},put_fn=lambda row:calls.append(row) or True);self.assertEqual(row['request_id'],rid);self.assertFalse(row['original_attempts_reset'])
 def test_explicit_full_image_refresh_still_tests_only_twenty_pinned_keys(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));probe=Mock(side_effect=self.probe);rr=r.images(e,d,o,probe,Mock(return_value={}),limit=20);self.assertEqual(rr['image_calls'],20);self.assertEqual(rr['proven_families'],20);self.assertEqual(rr['pending_families'],0);self.assertEqual([x.args[0] for x in probe.call_args_list],[SLOTS[4*i+3] for i in range(20)])
 def test_full_image_pass_has_wallclock_bound_and_no_arbitrary_limit(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));api=Mock()
   with patch.object(r.time,'monotonic',side_effect=[0,2401]):rr=r.images(e,d,o,api,Mock(return_value={}),limit=20)
   self.assertEqual(rr['image_calls'],0);api.assert_not_called()
   with self.assertRaises(ValueError):r.images(e,d,o,api,Mock(),limit=97)

 def test_transport_diagnostics_persist_class_without_secrets_or_replay(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles=self.setup(Path(td));probe=Mock(side_effect=TimeoutError('PRIVATE credential body'));rr=r.images(e,d,o,probe,Mock(return_value={}))
   self.assertEqual(rr['cases'][0]['error_type'],'TimeoutError');self.assertEqual(rr['cases'][0]['provider_state'],'uncertain');self.assertNotIn('PRIVATE',json.dumps(rr));probe.assert_called_once()
   second=Mock();held=r.images(dict(e,GITHUB_RUN_ID='124'),d,o,second,Mock(return_value={}));self.assertEqual(held['status'],'shared_image_cooldown');second.assert_not_called()
 def test_probe_decode_class_retained_but_arbitrary_text_never_persisted(self):
  self.assertEqual(r.image_diagnostic({'state':'transport_or_decode_failed','error_type':'JSONDecodeError','body':'PRIVATE'}),{'provider_state':'transport_or_decode_failed','error_type':'JSONDecodeError'})
  self.assertEqual(r.image_diagnostic({'state':'PRIVATE','error_type':'PRIVATE'}),{'provider_state':'unclassified','error_type':'OtherError'})
