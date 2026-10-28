import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import writer_retry_feedback as w,practical_drafting as d,family_lifecycle as f
from automation.agri_v2.queue import atomic_json
from automation.agri_v2.failure_diagnostics import failure_details
class RetryFeedbackTests(unittest.TestCase):
 def test_known_rejection_only_and_archived_raw_bytes_are_not_changed(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);raw=p/'lifecycle/text/rejected/1/practical-text-candidate.json';atomic_json(raw,{'body':'PRIVATE raw 正文'});before=raw.read_bytes();atomic_json(p/'lifecycle/text/state.json',{'history':[{'status':'failed','failure':{'category':'unexpected_mixed_language','message':'PRIVATE secret'}},{'status':'failed','failure':{'category':'PRIVATE arbitrary code'}}]})
   r=w.feedback(p);self.assertEqual(len(r['rejections']),1);self.assertIn('CJK',r['rejections'][0]['correction_contract']);self.assertFalse(r['scientific_approval']);self.assertFalse(r['attempt_reset_authorized']);self.assertNotIn('PRIVATE',json.dumps(r));self.assertEqual(before,raw.read_bytes());self.assertEqual(r['archived_candidates'][0]['raw_sha256'],hashlib.sha256(before).hexdigest())
 def test_unknown_or_validated_history_cannot_become_rejection_guidance(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);atomic_json(p/'lifecycle/text/state.json',{'history':[{'status':'validated','failure':{'category':'unexpected_mixed_language'}},{'status':'failed','failure':{'category':'provider_unavailable'}}]});self.assertEqual(w.feedback(p)['rejections'],[])
 def test_next_attempt_archives_numeric_and_identity_audit(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);atomic_json(f.row_path(p,'text'),{'attempts':1,'status':'failed','history':[]});paths=[p/'practical-text-numeric-audit.json',p/'practical-text-identity-binding.json']
   for item in paths:atomic_json(item,{'preserve':item.name})
   before={item:item.read_bytes() for item in paths};f.attempt(p,'text','next-run',lambda:{'new':True},f.stage_outputs(p,'text'))
   for item in paths:self.assertEqual(before[item],(p/'lifecycle/text/rejected/1'/item.name).read_bytes())
   self.assertEqual(f.state(p,'text')['attempts'],2)
 def test_admission_classification_is_safe_not_unexpected(self):
  from automation.agri_v2.parallel_pool import PoolDeferred
  from automation.agri_v2.image_transport import AdmissionBlocked
  from automation.blog_image_queue import ImageQueueBusy
  for error,code in ((PoolDeferred('PRIVATE'),'model_capacity_deferred'),(AdmissionBlocked('PRIVATE'),'image_admission_blocked'),(ImageQueueBusy(),'shared_image_queue_busy')):
   self.assertEqual(failure_details(error),{'kind':'admission_deferred','category':code})
 def test_image_quality_negative_remains_negative_and_gets_specific_diagnostic(self):
  from automation.agri_v2.image_quality import ImageQualityError
  self.assertEqual(failure_details(ImageQualityError('Image rejected by visual QA; preserve bytes, no upload or automatic regeneration')),{'kind':'image_quality','category':'image_critical_checks_failed'})
  self.assertEqual(failure_details(ImageQualityError('PRIVATE')),{'kind':'image_quality','category':'unspecified'})
 def test_generator_supplies_feedback_with_one_call_without_rewriting_prior_state(self):
  from tests.agri_v2.test_practical_drafting import fixture
  topic,brief,raw=fixture();client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);state=p/'lifecycle/text/state.json';atomic_json(state,{'attempts':2,'status':'reserved','history':[{'status':'failed','failure':{'category':'unexpected_mixed_language'}}]});before=state.read_bytes();d.generate(client,topic,brief,p);packet=json.loads(client.text.call_args.args[0]);self.assertEqual(packet['previous_rejection_feedback']['rejections'][0]['category'],'unexpected_mixed_language');self.assertFalse(packet['previous_rejection_feedback']['validator_bypass_authorized']);self.assertEqual(before,state.read_bytes());client.text.assert_called_once();self.assertEqual(client.text.call_args.kwargs['attempts'],1)
