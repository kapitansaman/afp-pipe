import io,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from automation.agri_v2 import single_family_capability as r,family_keys as k,family_model_routing as m,staged_rollout as s
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.parallel_pool import SLOTS
from automation.agri_v2.parallel_control import reserve
from automation.agri_v2.client import CapabilityError

class SingleFamilyCapabilityTests(unittest.TestCase):
 def setup(self,root):
  d=root/'data';o=root/'out';atomic_json(d/'family-key-allocation.json',k.default_policy());atomic_json(d/'family-model-routing.json',m.expected(d));atomic_json(d/'config.json',{'repository':'kapitansaman/afp-pipe','credential_set_id':'fixture'})
  s.save(o,{'version':1,'limit':1,'cohort':[{'family_id':'family-07','topic_id':'agri-6fc1032cdf42'}],'accepted':[],'history':[],'schedule_enabled':False,'original_attempts_reset':False})
  atomic_json(o/'parallel/readiness/latest.json',{'families':[{'family_id':'family-07','topic_id':'agri-6fc1032cdf42','next_stage':'publish','attempts':3,'retry_exhausted':True}]});atomic_json(o/'provider-circuit.json',{'open':False})
  atomic_json(d/r.REQUEST,r.expected(d,o))
  env={slot:'synthetic-private-'+str(i) for i,slot in enumerate(SLOTS)}
  env.update(GITHUB_ACTIONS='true',GITHUB_REPOSITORY='kapitansaman/afp-pipe',GITHUB_REF_NAME='feat/agri-generator-v2-2905-merge593',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ID='123',GITHUB_TOKEN='synthetic-github',AFP_WP_APP_PASSWORD='synthetic-site-private')
  return d,o,env
 def response(self,*args,**kwargs):return {'http_status':200},{'model':r.TEXT_MODEL,'choices':[{'message':{'content':'OK'},'finish_reason':'stop'}]}
 def image(self,*args,**kwargs):
  b=io.BytesIO();Image.new('RGB',(1200,675),'green').save(b,'WEBP');return {'state':'healthy','http_status':200},b.getvalue()
 def run_probe(self,d,o,e,post=None,probe=None,res=None,guard=None):
  return r.run(e,d,o,post_fn=post or Mock(side_effect=self.response),probe_fn=probe or Mock(side_effect=self.image),reserve_fn=res or Mock(return_value=True),image_guard=guard or Mock())
 def test_real_admission_is_exact_and_bound(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));v=load_json(d/r.REQUEST);r.validate(v,d,o)
   for key,value in [('max_text_calls',4),('max_image_calls',2),('max_runs',2),('max_attempts_per_slot',2),('max_in_flight',2),('publication_authorized',True),('reset_attempts',True),('global_capacity_refresh',True),('family_id','family-08'),('image_slot','AGNES_API_KEY4'),('text_slots',['AGNES_API_KEY81']),('code_sha256','changed')]:
    with self.subTest(key=key),self.assertRaises(r.Blocked):r.validate(dict(v,**{key:value}),d,o)
 def test_success_uses_exact_owned_slots_once_sequentially(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));events=[]
   def post(*a,**kw):events.append(a[1]);return self.response()
   def probe(*a,**kw):events.append(a[1]);self.assertNotIn('AGNES_API_KEY81',kw['env']);self.assertNotIn('AFP_WP_APP_PASSWORD',kw['env']);self.assertEqual(kw['diagnostic_id'],r.ID);return self.image()
   before=r.manifest(d,o);v=self.run_probe(d,o,e,post,probe)
   self.assertEqual(events,[e[x] for x in r.TEXT+(r.IMAGE,)]);self.assertEqual((v['model_calls'],v['image_calls'],v['transport_reservations']),(3,1,4));self.assertEqual(v['status'],'single_family_capability_verified_not_promoted');self.assertTrue(v['originals_unchanged']);self.assertEqual(before,r.manifest(d,o))
   proof=load_json(o/'infrastructure-probes'/r.ID/'scoped-proof.json');self.assertFalse(proof['production_readiness_claimed']);self.assertFalse(proof['publication_visual_approval']);self.assertFalse((o/'parallel/runtime/image'/ (r.IMAGE+'.json')).exists())
 def test_text_payload_tiny_and_no_extra_calls(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));post=Mock(side_effect=self.response);self.run_probe(d,o,e,post=post)
   self.assertEqual(post.call_count,3)
   for c in post.call_args_list:self.assertEqual(c.args[0],'/chat/completions');self.assertEqual(c.args[2],{'model':r.TEXT_MODEL,'messages':[{'role':'user','content':'Reply with OK only.'}],'temperature':0,'max_tokens':256});self.assertEqual(c.kwargs,{'timeout':70})
 def test_all_dangerous_side_effects_stay_false_or_zero(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));v=self.run_probe(d,o,e)
   for x in ['site_calls','published_posts','article_edits','translation_edits','source_fetches','search_requests']:self.assertEqual(v[x],0)
   for x in ['attempts_reset','publication_authorized','schedule_enabled','promotion_authorized','global_capacity_refresh','production_readiness_claimed','publication_visual_approval']:self.assertIs(v[x],False)
 def test_failure_at_any_text_slot_stops_remaining_and_image(self):
  for fail_at in range(3):
   with tempfile.TemporaryDirectory() as td:
    d,o,e=self.setup(Path(td));post=Mock(side_effect=[self.response()]*fail_at+[({'http_status':401},None)]);probe=Mock();v=self.run_probe(d,o,e,post,probe);self.assertEqual(post.call_count,fail_at+1);probe.assert_not_called();self.assertEqual(v['image_calls'],0);self.assertEqual(v['status'],'single_family_capability_blocked')
 def test_unknown_text_preserved_and_never_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));post=Mock(side_effect=TimeoutError('PRIVATE BODY'));v=self.run_probe(d,o,e,post);self.assertEqual(v['model_calls'],1);self.assertNotIn('PRIVATE',json.dumps(v));self.assertEqual(v['cases'][0]['status'],'reconciliation_required');api=Mock();res=Mock();self.run_probe(d,o,e,api,api,res);api.assert_not_called();res.assert_not_called()
 def test_quota_backpressure_blocks_all_other_slots(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));post=Mock(return_value=({'http_status':429,'retry_after_seconds':7200},None));probe=Mock();v=self.run_probe(d,o,e,post,probe);post.assert_called_once();probe.assert_not_called();self.assertTrue(load_json(o/'provider-circuit.json')['open']);routing=load_json(o/'parallel/key-routing.json');self.assertGreater(routing['backpressure']['slots'][r.TEXT[0]]['cooldown_until_epoch'],time.time())
 def test_wrong_model_empty_truncated_or_non_ok_text_is_rejected(self):
  for obj in [{'model':'wrong','choices':[{'message':{'content':'OK'}}]}, {'choices':[{'message':{'content':''}}]}, {'choices':[{'message':{'content':'OK'},'finish_reason':'length'}]}, {'choices':[{'message':{'content':'not OK'}}]},None]:
   self.assertFalse(r.text_ok({'http_status':200},obj))
 def test_invalid_image_is_not_proof_and_not_retried(self):
  for safe,blob in [({'state':'healthy','http_status':200},b'invalid'),({'state':'model_mismatch','http_status':200},b'bad'),({'state':'quota_limited','http_status':429},None)]:
   with tempfile.TemporaryDirectory() as td:
    d,o,e=self.setup(Path(td));probe=Mock(return_value=(safe,blob));v=self.run_probe(d,o,e,probe=probe);probe.assert_called_once();self.assertEqual(v['image_calls'],1);self.assertEqual(v['status'],'single_family_capability_blocked');self.assertFalse((o/'infrastructure-probes'/r.ID/'scoped-proof.json').exists())
 def test_unknown_image_stays_spent_and_no_sensitive_error_saved(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));probe=Mock(side_effect=TimeoutError('SECRET PROVIDER BODY'));v=self.run_probe(d,o,e,probe=probe);self.assertEqual(v['image_calls'],1);self.assertEqual(v['cases'][-1]['status'],'reconciliation_required');self.assertNotIn('SECRET',json.dumps(v));probe.assert_called_once()
 def test_image_rejection_before_transport_not_reported_as_sent(self):
  from automation.agri_v2.image_transport import AdmissionBlocked
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));v=self.run_probe(d,o,e,probe=Mock(side_effect=AdmissionBlocked()));self.assertEqual(v['model_calls'],3);self.assertEqual(v['image_calls'],0);self.assertEqual(v['cases'][-1]['status'],'admission_blocked_not_sent')
 def test_remote_reservation_conflict_zero_transport(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));post=Mock();probe=Mock();self.run_probe(d,o,e,post,probe,Mock(return_value=False));post.assert_not_called();probe.assert_not_called()
 def test_unknown_old_report_zero_even_if_inputs_changed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));atomic_json(o/'infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});(d/r.REQUEST).unlink();api=Mock();v=self.run_probe(d,o,e,api,api,api,api);api.assert_not_called();self.assertEqual(v['model_calls'],0)
 def test_preflight_shared_image_hold_zero_paid_calls(self):
  from automation.agri_v2.image_transport import AdmissionBlocked
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));api=Mock()
   with self.assertRaises(AdmissionBlocked):self.run_probe(d,o,e,api,api,api,Mock(side_effect=AdmissionBlocked()))
   api.assert_not_called()
 def test_changed_input_denied_before_reserve(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));atomic_json(o/'new/agri-6fc1032cdf42/article.json',{'changed':True});api=Mock()
   with self.assertRaises(r.Blocked):self.run_probe(d,o,e,api,api,api)
   api.assert_not_called()
 def test_missing_or_duplicate_credentials_no_paid_calls(self):
  for changed in [{r.IMAGE:''},{r.IMAGE:'synthetic-private-0'}]:
   with tempfile.TemporaryDirectory() as td:
    d,o,e=self.setup(Path(td));e.update(changed);api=Mock()
    with self.assertRaises((ValueError,CapabilityError)):self.run_probe(d,o,e,api,api,api)
    api.assert_not_called()
 def test_manual_identity_and_exact_phase(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));self.assertTrue(reserve(r.PHASE,r.ID,e,put_fn=lambda row:True))
   for bad in [dict(e,GITHUB_EVENT_NAME='schedule'),dict(e,GITHUB_REF_NAME='main')]:
    with self.assertRaises(ValueError):reserve(r.PHASE,r.ID,bad,put_fn=lambda row:True)
    with self.assertRaises(ValueError):self.run_probe(d,o,bad)
   with self.assertRaises(ValueError):reserve(r.PHASE,'old-id',e,put_fn=lambda row:True)
 def test_durable_slot_hold_denies_all_before_first_paid_call(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));atomic_json(o/'parallel/key-routing.json',{'slot_request_counts':{},'backpressure':{'slots':{r.IMAGE:{'disabled':True,'cooldown_until_epoch':0}}}});atomic_json(d/r.REQUEST,r.expected(d,o));api=Mock()
   with self.assertRaises(r.Blocked):self.run_probe(d,o,e,api,api,api)
   api.assert_not_called()
 def test_global_health_and_all_history_are_protected(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));before=r.manifest(d,o)
   for path in [o/'parallel/health/latest.json',o/'infrastructure-probes/old-id/calls/unknown.json',o/'new/agri-6fc1032cdf42/lifecycle/publish/state.json']:
    atomic_json(path,{'status':'unchanged'});self.assertNotEqual(before,r.manifest(d,o));path.unlink()
 def test_shared_hold_and_malformed_deadline_no_transport(self):
  for row in [{'open':True,'request_kind':'image','retry_at_epoch':time.time()+3600},{'open':True,'retry_at_epoch':float('nan')},{'open':'false'}]:
   with tempfile.TemporaryDirectory() as td:
    d,o,e=self.setup(Path(td));atomic_json(o/'provider-circuit.json',row);api=Mock()
    with self.assertRaises(r.Blocked):self.run_probe(d,o,e,api,api,api)
    api.assert_not_called()
 def test_routing_counters_accumulate_without_reset(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));atomic_json(o/'parallel/key-routing.json',{'slot_request_counts':{r.TEXT[0]:17,'AGNES_API_KEY81':22},'backpressure':{}});atomic_json(d/r.REQUEST,r.expected(d,o));self.run_probe(d,o,e);counts=load_json(o/'parallel/key-routing.json')['slot_request_counts'];self.assertEqual(counts[r.TEXT[0]],18);self.assertEqual(counts['AGNES_API_KEY81'],22)
 def test_changed_inputs_between_calls_stop_before_next_request(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));post=Mock()
   def mutate(*args,**kwargs):atomic_json(o/'new/agri-6fc1032cdf42/article.json',{'unexpected':True});return self.response()
   post.side_effect=mutate;probe=Mock();v=self.run_probe(d,o,e,post,probe);post.assert_called_once();probe.assert_not_called();self.assertEqual(v['status'],'single_family_capability_originals_changed');self.assertFalse((o/'infrastructure-probes'/r.ID/'scoped-proof.json').exists())
 def test_provider_body_and_credential_values_never_persisted(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));post=Mock(return_value=({'http_status':403,'state':'PRIVATE PROVIDER BODY','body':'PRIVATE'},None));self.run_probe(d,o,e,post=post)
   saved=''.join(p.read_text() for p in o.rglob('*.json'));self.assertNotIn('PRIVATE',saved)
   for slot in SLOTS:self.assertNotIn(e[slot],saved)
 def test_portrait_image_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));b=io.BytesIO();Image.new('RGB',(800,1200)).save(b,'WEBP');v=self.run_probe(d,o,e,probe=Mock(return_value=({'state':'healthy','http_status':200},b.getvalue())));self.assertEqual(v['status'],'single_family_capability_blocked');self.assertEqual(v['image_calls'],1)
 def test_guard_rechecked_between_requests_without_new_paid_call(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e=self.setup(Path(td));post=Mock(side_effect=self.response);probe=Mock()
   with patch.object(r,'guards',side_effect=[None,None,r.Blocked('shared_provider_hold')]):v=self.run_probe(d,o,e,post,probe)
   post.assert_called_once();probe.assert_not_called();self.assertEqual(v['model_calls'],1)
