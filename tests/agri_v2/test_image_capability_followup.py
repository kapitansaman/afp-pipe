import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import image_capability_followup as f,family_capability_refresh as r
from automation.agri_v2.queue import atomic_json,load_json,utcnow,OUT
from automation.agri_v2.family_model_routing import binding
from automation.agri_v2.parallel_control import reserve
from tests.agri_v2 import test_family_capability_refresh as fixtures
class FollowupTests(unittest.TestCase):
 def setup(self,td):
  helper=fixtures.CapabilityRefreshTests();d,o,e,roles=helper.setup(Path(td));atomic_json(d/'image-capability-followup.json',f.REQUEST)
  original=OUT/f.ORIGINAL;target=o/f.ORIGINAL;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(original.read_bytes())
  # Populate 19 role-bound mock image successes, not provider calls.
  for family,role in roles['families'].items():
   if family==f.FAMILY:continue
   atomic_json(o/'parallel/runtime/image'/(role['image_slot']+'.json'),{'repository':'kapitansaman/afp-pipe','credential_set_id':r.CREDENTIAL_SET_ID,'family_id':family,'slot':role['image_slot'],'model':f.IMAGE_MODEL,'family_model_routing_sha256':binding(roles),'verification':'actual_successful_parallel_capability_probe','verified_at':utcnow()})
  atomic_json(o/'parallel/scoped-family-pilot/accepted.json',{'status':'scoped_family_pilot_verified','public_verified':True,'image_model':f.IMAGE_MODEL,'family_model_routing_sha256':binding(roles),'checked_at':utcnow()})
  atomic_json(o/'parallel/health/latest.json',{'checked_at':'unchanged-text-time','eligible_text_slots':['unchanged']})
  return d,o,e,roles,Mock(side_effect=helper.probe),Mock(return_value={})
 def test_success_new_request_original_and_text_unchanged_no_replay(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);before=(o/f.ORIGINAL).read_bytes();result=f.run(e,d,o,api,ledger)
   self.assertEqual(result['status'],'followup_verified_new_diagnostic');self.assertEqual(result['proven_families'],20);self.assertEqual(result['image_calls'],1);self.assertFalse(result['original_outcome_resolved']);self.assertEqual(before,(o/f.ORIGINAL).read_bytes());self.assertEqual(hashlib.sha256(before).hexdigest(),f.ORIGINAL_HASH)
   api.assert_called_once();self.assertEqual(api.call_args.args,(f.SLOT,e[f.SLOT]));self.assertEqual(api.call_args.kwargs['diagnostic_id'],f.ID);ledger.assert_called_once_with('capability-followup',f.ID,e)
   h=load_json(o/'parallel/health/latest.json');self.assertEqual(h['checked_at'],'unchanged-text-time');self.assertEqual(h['eligible_text_slots'],['unchanged'])
   self.assertEqual(f.run(dict(e,GITHUB_RUN_ID='456'),d,o,api,ledger)['status'],'followup_already_reserved_no_replay');api.assert_called_once()
 def test_missing_other_proof_blocks_before_reserve(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);(o/'parallel/runtime/image/AGNES_API_KEY4.json').unlink();self.assertEqual(f.run(e,d,o,api,ledger)['status'],'followup_waiting_other_19');api.assert_not_called();ledger.assert_not_called()
 def test_accepted_pilot_required(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);(o/'parallel/scoped-family-pilot/accepted.json').unlink();self.assertEqual(f.run(e,d,o,api,ledger)['status'],'followup_waiting_accepted_pilot');api.assert_not_called();ledger.assert_not_called()
 def test_active_image_hold_blocks_but_text_scope_does_not(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);r.stop(o,'image');self.assertEqual(f.run(e,d,o,api,ledger)['status'],'shared_image_cooldown');api.assert_not_called();ledger.assert_not_called();r.stop(o,'text');self.assertEqual(f.run(e,d,o,api,ledger)['status'],'followup_verified_new_diagnostic')
 def test_original_hash_and_contract_cannot_be_changed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);(o/f.ORIGINAL).write_text('{}')
   with self.assertRaises(ValueError):f.run(e,d,o,api,ledger)
   api.assert_not_called();ledger.assert_not_called()
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);atomic_json(d/'image-capability-followup.json',dict(f.REQUEST,slot='AGNES_API_KEY40'))
   with self.assertRaises(ValueError):f.run(e,d,o,api,ledger)
   api.assert_not_called()
 def test_remote_reservation_collision_no_send_no_retry(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);ledger.return_value=None;self.assertEqual(f.run(e,d,o,api,ledger)['status'],'followup_reconciliation_required');ledger.assert_called_once();api.assert_not_called();f.run(e,d,o,api,ledger);ledger.assert_called_once()
 def test_uncertain_outcome_sets_hold_and_never_retries_or_leaks(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,api,ledger=self.setup(td);api.side_effect=TimeoutError('PRIVATE key body');result=f.run(e,d,o,api,ledger);self.assertEqual(result['status'],'followup_reconciliation_required');self.assertTrue(r.active_hold(o,'image'));self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn(f.SLOT,r.image_proofs(o,roles));f.run(e,d,o,api,ledger);api.assert_called_once()
 def test_invalid_bytes_and_account_rejection_never_grant_capability(self):
  for safe,blob in [({'state':'healthy','http_status':200},b'not image'),({'state':'quota_limited','http_status':429},None)]:
   with tempfile.TemporaryDirectory() as td:
    d,o,e,roles,api,ledger=self.setup(td);api.side_effect=None;api.return_value=safe,blob;result=f.run(e,d,o,api,ledger);self.assertIn(result['status'],('followup_failed','followup_failed_invalid_image'));self.assertNotIn(f.SLOT,r.image_proofs(o,roles));f.run(e,d,o,api,ledger);api.assert_called_once()
 def test_manual_and_exact_remote_id_only(self):
  with self.assertRaises(ValueError):reserve('capability-followup',f.ID,{'GITHUB_EVENT_NAME':'schedule'},put_fn=lambda x:True)
  with self.assertRaises(ValueError):reserve('capability-followup','other',{'GITHUB_EVENT_NAME':'workflow_dispatch'},put_fn=lambda x:True)
  row=reserve('capability-followup',f.ID,{'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123'},put_fn=lambda x:True);self.assertEqual(row['request_id'],f.ID)
 def test_distinct_provider_prompt_safe_id_only(self):
  from automation.agri_v2 import image_key_audit as audit
  import contextlib
  response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.read.return_value=b'{"data":[]}'
  with patch.object(audit,'admission',return_value=contextlib.nullcontext()),patch.object(audit.urllib.request,'urlopen',return_value=response) as call,patch.object(audit,'render_image',return_value=b'decoded'):
   audit.probe(f.SLOT,'PRIVATE',env={},diagnostic_id=f.ID)
   payload=json.loads(call.call_args.args[0].data);self.assertIn('New independent diagnostic '+f.ID,payload['prompt']);self.assertNotIn('PRIVATE',json.dumps(payload));self.assertEqual(payload['model'],f.IMAGE_MODEL)
  with self.assertRaises(ValueError):audit.probe(f.SLOT,'PRIVATE',diagnostic_id='bad\ninput')
