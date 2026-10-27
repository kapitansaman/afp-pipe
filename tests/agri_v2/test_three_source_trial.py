import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import three_source_trial as t,operation_request as op,family_lifecycle as f
from automation.agri_v2.persian_source_pilot import SourceOnlyPublisher
from automation.agri_v2.wordpress import WPError,WordPress
class ThreeSourceTrialTests(unittest.TestCase):
 def test_exact_three_source_scope_is_finite(self):
  r=dict(t.expected_request(),code_revision='a'*40);op.validate_request(r)
  for k,v in [('max_total_posts',4),('max_total_model_calls',43),('max_translations',1),('enable_schedule',True),('reset_attempts',True),('max_model_calls_per_family',15),('topic_ids',list(reversed(t.TOPICS)))]:
   with self.assertRaises(ValueError):op.validate_request(dict(r,**{k:v}))
 def test_scope_cannot_be_enabled_without_current_admission(self):
  with patch.object(op,'authorize',return_value=False):
   with self.assertRaises(ValueError):t.prepare({})
 def test_source_only_worker_is_not_a_general_translation_bypass(self):
  with patch.object(op,'authorize',return_value=False):
   with self.assertRaises(f.StageBlocked):f.worker({'id':t.TOPICS[0]},{},env={'GITHUB_RUN_ID':'123'},source_only=True)
 def test_per_source_two_media_budget_is_still_one_post(self):
  with tempfile.TemporaryDirectory() as d,patch.object(WordPress,'call',return_value=({},{})) as call:
   wp=SourceOnlyPublisher({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'},Path(d),{'title':'fixture'},'fixture',mutation_limit=7,media_limit=2)
   wp.call('posts','POST',{'title':'fixture','slug':'fixture','status':'draft'});wp.call('media','POST',blob=b'a');wp.call('media','POST',blob=b'b')
   with self.assertRaises(WPError):wp.call('posts','POST',{'title':'fixture','slug':'fixture','status':'draft'})
   with self.assertRaises(WPError):wp.call('media','POST',blob=b'c')
   self.assertEqual(call.call_count,3)
 def test_arbitrary_budget_expansion_is_not_supported(self):
  with self.assertRaises(WPError):SourceOnlyPublisher({},Path('.'),{},'',mutation_limit=100,media_limit=20)
 def test_scoped_trial_can_draft_after_actual_approved_brief(self):
  from test_family_lifecycle import FamilyLifecycleTests
  from automation.agri_v2.queue import atomic_json
  with tempfile.TemporaryDirectory() as d:
   data,out,topic,env,health=FamilyLifecycleTests().setup(d);topic=dict(topic,id=t.TOPICS[0]);env=dict(env,AFP_PARALLEL_TOPIC=topic['id']);atomic_json(data/'status/owner-operation-admission.json',{'request_id':t.ID});atomic_json(data/'briefs'/(topic['id']+'.json'),{'review_mode':'automated_scoped_evidence_review_v1'});factory=Mock()
   with patch.object(op,'authorize',return_value=True),patch.object(f,'next_stage',side_effect=[('text',None),('publish',None)]),patch.object(f,'run_stage',return_value={'validated':True}):r=f.worker(topic,health,data,out,env,client_factory=factory,source_only=True)
   self.assertEqual(r['status'],'publication_ready');factory.assert_called_once()
