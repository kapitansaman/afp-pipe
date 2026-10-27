import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import operation_request as op
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
from automation.agri_v2.parallel_capacity import CREDENTIAL_SET_ID

class OwnerOperationTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'push','GITHUB_REF':'refs/heads/main','GITHUB_WORKFLOW_REF':op.WORKFLOW,'GITHUB_RUN_ID':'12345','GITHUB_SHA':'a'*40,'AGNES_API_KEY':'private-test-only'}
 def req(self):return {'version':1,'request_id':op.ID,'operation':'readiness-audit-image-pilot','authorized':True,'max_text_health_calls':97,'max_image_health_calls':1,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False,'code_revision':'b'*40}
 def health(self,o):
  atomic_json(o/'parallel/health/latest.json',{'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'audit_status':'completed','checked_at':utcnow(),'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,'eligible_text_slots':['AGNES_API_KEY'],'eligible_image_slots':[]})
 def test_only_exact_destination_push_context_is_accepted(self):
  for k,v in [('GITHUB_REPOSITORY','other/repo'),('GITHUB_REF','refs/heads/other'),('GITHUB_EVENT_NAME','pull_request'),('GITHUB_WORKFLOW_REF','untrusted'),('GITHUB_RUN_ID','x')]:
   e=self.env();e[k]=v;self.assertFalse(op.context(e))
 def test_request_cannot_enable_schedule_reset_or_expand_budget(self):
  for k,v in [('enable_schedule',True),('reset_attempts',True),('max_image_health_calls',2),('max_pilot_families',20),('max_text_health_calls',98)]:
   r=self.req();r[k]=v
   with self.assertRaises(ValueError):op.validate_request(r)
 def test_pinned_code_must_match_before_admission(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'differs'):op.load_owner_request(self.env(),Path(t),lambda:self.req(),lambda:'c'*40)
   self.assertFalse(op.authorize(self.env(),Path(t)))
 def test_admission_is_bound_to_current_run_and_exact_request_commit(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);e=self.env();op.load_owner_request(e,d,lambda:self.req(),lambda:'b'*40);self.assertTrue(op.authorize(e,d))
   for k,v in [('GITHUB_RUN_ID','12346'),('GITHUB_SHA','c'*40)]:
    bad=dict(e);bad[k]=v;self.assertFalse(op.authorize(bad,d))
 def test_first_success_records_actual_image_proof_without_changing_text_date(self):
  with tempfile.TemporaryDirectory() as t:
   o=Path(t);self.health(o);date=load_json(o/'parallel/health/latest.json')['checked_at'];probe=Mock(return_value=({'state':'healthy','http_status':200},b'verified-by-production-probe'))
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=op.image_capability(self.env(),out=o,probe_fn=probe)
   self.assertEqual(r['status'],'image_capability_verified');self.assertEqual(probe.call_count,1);h=load_json(o/'parallel/health/latest.json');self.assertEqual(h['checked_at'],date);self.assertEqual(h['eligible_image_slots'],['AGNES_API_KEY']);p=load_json(o/'parallel/runtime/image/AGNES_API_KEY.json');self.assertFalse(p['publication_visual_approval'])
 def test_one_image_request_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as t:
   o=Path(t);self.health(o);atomic_json(o/'parallel/operations'/op.ID/'image-proof.json',{'status':'reserved'});probe=Mock()
   self.assertEqual(op.image_capability(self.env(),out=o,probe_fn=probe)['status'],'already_reserved');probe.assert_not_called()
 def test_shared_limit_stops_without_trying_another_key(self):
  with tempfile.TemporaryDirectory() as t:
   o=Path(t);self.health(o);probe=Mock(return_value=({'state':'rate_limited','http_status':429,'retry_after_seconds':7200},None))
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=op.image_capability(self.env(),out=o,probe_fn=probe)
   self.assertEqual(r['image_calls'],1);self.assertEqual(probe.call_count,1);self.assertTrue(load_json(o/'provider-circuit.json')['open']);self.assertEqual(load_json(o/'parallel/health/latest.json')['eligible_image_slots'],[])
 def test_admission_denial_is_not_billed_success(self):
  from automation.agri_v2.image_transport import AdmissionBlocked
  with tempfile.TemporaryDirectory() as t:
   o=Path(t);self.health(o)
   with patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=op.image_capability(self.env(),out=o,probe_fn=Mock(side_effect=AdmissionBlocked('held')))
   self.assertEqual(r['image_calls'],0);self.assertEqual(r['status'],'not_sent_admission_blocked')
 def test_pilot_does_not_run_without_current_successful_prepare(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'data';o=Path(t)/'out';e=self.env();op.load_owner_request(e,d,lambda:self.req(),lambda:'b'*40);atomic_json(o/'parallel/operations'/op.ID/'prepare.json',{'run_id':'old','status':'pilot_prerequisites_passed'})
   with patch('automation.agri_v2.parallel_controller.run') as run:self.assertEqual(op.pilot(e,d,o)['status'],'pilot_not_admitted');run.assert_not_called()
 def test_workflow_is_one_shot_not_new_periodic_generator(self):
  p=Path(__file__).resolve().parents[2]/'.github/workflows/afp-owner-operation.yml';s=p.read_text();self.assertIn("paths: ['.github/afp-operations/request.json']",s);self.assertNotIn('cron:',s);self.assertIn('group: afp-agri-v2-live',s);self.assertIn('if: always()',s);self.assertEqual(s.count('secrets.AGNES_API_KEY_'),97);self.assertNotIn('GITHUB_EVENT_NAME:',s)

 def test_continuation_requires_zero_new_health_probes(self):
  r=self.req();r.update(request_id=op.CONTINUATION_ID,max_text_health_calls=0,max_image_health_calls=0);self.assertEqual(op.validate_request(r)['request_id'],op.CONTINUATION_ID)
  r['max_text_health_calls']=97
  with self.assertRaises(ValueError):op.validate_request(r)
 def test_unique_retry_keeps_the_same_finite_health_budget(self):
  r=self.req();r['request_id']=op.RETRY_ID
  self.assertEqual(op.validate_request(r)['request_id'],op.RETRY_ID)
  r['max_image_health_calls']=2
  with self.assertRaises(ValueError):op.validate_request(r)
 def test_unknown_operation_does_not_create_an_unbounded_replay_path(self):
  r=self.req();r['request_id']='ops-97-arbitrary-retry'
  with self.assertRaises(ValueError):op.validate_request(r)
 def test_grounded_continuation_performs_no_new_health_calls(self):
  from automation.agri_v2.parallel_pool import SLOTS
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'data';o=Path(t)/'out';self.health(o);h=load_json(o/'parallel/health/latest.json');h['eligible_text_slots']=SLOTS[:20];atomic_json(o/'parallel/health/latest.json',h)
   req=self.req();req.update(request_id=op.GROUNDED_ID,max_text_health_calls=0,max_image_health_calls=0);op.validate_request(req)
   readiness={'gates':{k:{'passed':True} for k in ['fresh_text_capacity','fresh_image_capacity','authenticated_publisher','translation_bridge','lifecycle_enabled']}}
   with patch.object(op,'load_owner_request',return_value={'request_id':op.GROUNDED_ID,'request':req}),patch('automation.agri_v2.parallel_control.policy'),patch('automation.agri_v2.parallel_control.reserve',return_value={}),patch('automation.agri_v2.production_readiness.run',return_value=readiness),patch('automation.agri_v2.parallel_audit.run') as audit,patch.object(op,'image_capability') as image:
    r=op.prepare(self.env(),d,o)
   self.assertEqual(r['status'],'pilot_prerequisites_passed');audit.assert_not_called();image.assert_not_called()
