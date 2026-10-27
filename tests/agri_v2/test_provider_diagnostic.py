import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import provider_diagnostic as d,operation_request as op,parallel_audit as a
from automation.agri_v2.queue import atomic_json,load_json
class DiagnosticTests(unittest.TestCase):
 def req(self):return {'version':1,'request_id':d.ID,'operation':'97-text-health-and-two-schema-probes','authorized':True,'max_text_health_calls':97,'max_image_health_calls':0,'max_pilot_families':0,'enable_schedule':False,'reset_attempts':False,'max_schema_probe_calls':2,'max_total_text_calls':99,'max_wordpress_mutations':0,'code_revision':'b'*40}
 def setup(self,td):
  data=Path(td)/'data';out=Path(td)/'out';atomic_json(data/'status/owner-operation-admission.json',{'request_id':d.ID});env={'GITHUB_RUN_ID':'123',d.SLOTS[0]:'synthetic-not-a-real-key'};audit={'status':'completed','model_calls':97,'eligible_text_slots':[d.SLOTS[0]],'cases':[{'slot':s,'state':'healthy','http_status':200} for s in d.SLOTS]};return data,out,env,audit
 def response(self,value):return {'state':'responded','http_status':200},{'choices':[{'message':{'content':json.dumps(value)},'finish_reason':'stop'}]}
 def test_exact_zero_publication_limits_cannot_expand(self):
  op.validate_request(self.req())
  for k,v in [('max_text_health_calls',98),('max_schema_probe_calls',3),('max_total_text_calls',100),('max_image_health_calls',1),('max_wordpress_mutations',1),('max_pilot_families',1),('reset_attempts',True),('enable_schedule',True)]:
   req=self.req();req[k]=v
   with self.assertRaises(ValueError):op.validate_request(req)
 def test_summary_has_every_slot_and_never_calls_untested_unhealthy(self):
  rows,counts=d.slot_summary({'cases':[{'slot':d.SLOTS[0],'state':'healthy'}],'missing_slots':[d.SLOTS[1]],'duplicate_slots':{d.SLOTS[2]:d.SLOTS[0]}});self.assertEqual(len(rows),97);self.assertEqual(counts,{'healthy':1,'not_configured':1,'duplicate_not_independent':1,'not_tested':94})
 def test_complete_99_call_cap_same_key_no_secrets_or_article_operations(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env,audit=self.setup(td);post=Mock(side_effect=[self.response({'ok':True}),self.response({'sections':[{'text':'ok yes','fact_ids':['f0']}],'excerpt':'OK'})])
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy',return_value={}):r=d.run(env,data,out,post_fn=post,reserve_fn=lambda *_:{},audit_fn=lambda *_,**__:audit)
   self.assertEqual(r['status'],'diagnostic_completed');self.assertEqual(r['model_calls'],99);self.assertEqual(r['slot_state_counts'],{'healthy':97});self.assertEqual(post.call_count,2);self.assertEqual(post.call_args_list[0].args[1],post.call_args_list[1].args[1]);self.assertEqual(r['image_calls'],0);self.assertEqual(r['wordpress_calls'],0);self.assertFalse(r['article_attempts_modified']);self.assertNotIn(env[d.SLOTS[0]],json.dumps(r));self.assertFalse(r['full_article_or_image_capability_proved'])
 def test_baseline_timeout_stops_before_strict_and_opens_circuit(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env,audit=self.setup(td);post=Mock(return_value=({'state':'network_or_timeout','http_status':None},None))
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy',return_value={}):r=d.run(env,data,out,post_fn=post,reserve_fn=lambda *_:{},audit_fn=lambda *_,**__:audit)
   self.assertEqual(post.call_count,1);self.assertEqual(r['status'],'diagnostic_baseline_failed');self.assertGreater(d.active_cooldown(out),time.time());self.assertEqual(r['model_calls'],98)
 def test_shared_audit_failure_prevents_both_schema_probes(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env,audit=self.setup(td);audit.update(status='stopped_shared_provider_limit',model_calls=2,cases=[{'slot':s,'state':'network_or_timeout'} for s in d.SLOTS[:2]]);post=Mock()
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy',return_value={}):r=d.run(env,data,out,post_fn=post,reserve_fn=lambda *_:{},audit_fn=lambda *_,**__:audit)
   post.assert_not_called();self.assertEqual(r['slot_state_counts'],{'network_or_timeout':2,'not_tested':95});self.assertEqual(r['model_calls'],2)
 def test_strict_failure_has_no_fallback_or_key_hop(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env,audit=self.setup(td);post=Mock(side_effect=[self.response({'ok':True}),({'state':'request_rejected','http_status':400},None)])
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy',return_value={}):r=d.run(env,data,out,post_fn=post,reserve_fn=lambda *_:{},audit_fn=lambda *_,**__:audit)
   self.assertEqual(post.call_count,2);self.assertEqual(r['status'],'diagnostic_strict_failed');self.assertEqual(r['schema_probes'][1]['http_status'],400);self.assertFalse(r['full_article_or_image_capability_proved'])
 def test_active_cooldown_preserved_and_no_calls(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env,audit=self.setup(td);until=time.time()+3600;atomic_json(out/'parallel/lifecycle/latest.json',{'pool':{'cooldown_until_epoch':until}});probe=Mock();audit_fn=Mock()
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy',return_value={}):r=d.run(env,data,out,post_fn=probe,reserve_fn=lambda *_:{},audit_fn=audit_fn)
   probe.assert_not_called();audit_fn.assert_not_called();self.assertEqual(r['model_calls'],0);self.assertEqual(r['cooldown_until_epoch'],until)
 def test_no_admission_no_calls(self):
  with patch.object(op,'authorize',return_value=False):
   with self.assertRaises(ValueError):d.run({})
 def test_actual_audit_97_requests_and_new_immutable_report(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,env,audit=self.setup(td);env.update({s:'synthetic-unique-'+s for s in d.SLOTS});post=Mock(return_value=({'state':'responded','http_status':200,'elapsed_seconds':0.1},{'choices':[{'message':{'content':'OK'}}]}));p={'repository':'kapitansaman/afp-pipe','credential_set_id':'fixture'}
   with patch.object(op,'authorize',return_value=True),patch.object(a,'policy',return_value=p),patch('automation.agri_v2.recovery.circuit_open',return_value=False):
    r=a.run(env,data,out,post_fn=post,reserve_fn=lambda *_:{},audit_id=d.ID);again=a.run(env,data,out,post_fn=post,reserve_fn=lambda *_:{},audit_id=d.ID)
   self.assertEqual(r['model_calls'],97);self.assertEqual(len(r['cases']),97);self.assertEqual(post.call_count,97);self.assertEqual(again['model_calls'],0);self.assertEqual(r['status'],'completed');self.assertTrue((out/'parallel/key-audits'/d.ID/'report.json').exists())
