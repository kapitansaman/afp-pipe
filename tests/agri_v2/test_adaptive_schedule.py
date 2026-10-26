import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import adaptive_schedule as a
from automation.agri_v2.queue import atomic_json,load_json

class AdaptiveScheduleTests(unittest.TestCase):
 def setup(self,root,interval=1200,calibrated=False):
  d=root/'data';o=root/'out';policy=json.loads((Path(__file__).resolve().parents[2]/'data/agri-v2/adaptive-schedule-policy.json').read_text());atomic_json(d/'adaptive-schedule-policy.json',policy);atomic_json(d/'config.json',{'multilingual':{'enabled':False}});atomic_json(d/'family-lifecycle-policy.json',{'max_model_requests_per_family':14});atomic_json(o/'parallel/scheduling/state.json',{'interval_seconds':interval,'calibrated':calibrated,'history':[]});return d,o
 def observer(self,d,o,clock,fresh=True):return a.Observer(['t'+str(i) for i in range(20)],'999',fresh,d,o,lambda:clock[0])
 def rows(self,n,status='publication_ready'):return [{'topic_id':'t'+str(i),'status':status} for i in range(n)]
 def test_complete_early_shortens_with_margin_only_after_verified_publication(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));clock=[0];obs=self.observer(d,o,clock);clock[0]=600;report={'status':'completed','results':self.rows(20),'operational_failures':0};r=obs.finish(report,['t'+str(i) for i in range(20)]);self.assertTrue(r['sample_eligible']);self.assertEqual(r['interval_seconds'],720);self.assertTrue(a.current(d,o)['calibrated'])
 def test_eighty_percent_built_and_four_active_increases_once(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));clock=[0];obs=self.observer(d,o,clock);clock[0]=1200;r=obs.observe(self.rows(16));self.assertTrue(r['tail_adjustment_observed']);self.assertEqual(r['proposed_interval_seconds'],1440);self.assertEqual(r['active_families'],4);clock[0]=1250;obs.observe(self.rows(16));self.assertEqual(len(obs.events),1)
 def test_eighty_percent_terminal_failures_are_not_a_slow_tail(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));clock=[0];obs=self.observer(d,o,clock);clock[0]=1200;r=obs.observe(self.rows(16)+[{'topic_id':'t'+str(i),'status':'stage_failed'} for i in range(16,20)]);self.assertFalse(r['tail_adjustment_observed'])
 def test_fast_blocked_run_never_shortens_or_calibrates(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));clock=[0];obs=self.observer(d,o,clock);clock[0]=2;r=obs.finish({'status':'completed_with_failures','results':self.rows(20,'blocked'),'operational_failures':20},[]);self.assertFalse(r['sample_eligible']);self.assertEqual(a.current(d,o)['interval_seconds'],1200);self.assertFalse(a.current(d,o)['calibrated'])
 def test_unpublished_or_resumed_or_duplicate_families_do_not_calibrate(self):
  for fresh,verified in [(False,20),(True,19)]:
   with self.subTest(fresh=fresh,verified=verified),tempfile.TemporaryDirectory() as td:
    d,o=self.setup(Path(td));clock=[0];obs=self.observer(d,o,clock,fresh);clock[0]=500;r=obs.finish({'status':'completed','results':self.rows(20),'operational_failures':0},['t'+str(i) for i in range(verified)]);self.assertFalse(r['sample_eligible'])
 def test_missing_measured_twenty_family_sample_blocks_automatic_launch(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));p=a.settings(d);p['enabled']=True;atomic_json(d/'adaptive-schedule-policy.json',p);env=self.env();self.assertEqual(a.gate(env,d,o)['reason'],'verified_20_family_timing_required')
 def env(self):return {'GITHUB_RUN_ID':'999','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'schedule','GITHUB_WORKFLOW_REF':'kapitansaman/afp-pipe/.github/workflows/afp-agri-v2-scheduled.yml@refs/heads/main'}
 def test_paused_heartbeat_makes_no_model_or_wordpress_call(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td))
   with patch('automation.agri_v2.family_lifecycle.run') as run:r=a.run(self.env(),d,o)
   self.assertEqual(r['model_calls'],0);self.assertFalse(r['should_run']);run.assert_not_called()
 def test_wrong_repository_or_workflow_cannot_claim_schedule_admission(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));env=dict(self.env(),GITHUB_WORKFLOW_REF='kapitansaman/afp-pipe/other.yml@refs/heads/main');self.assertEqual(a.gate(env,d,o)['reason'],'wrong_scheduler_context');self.assertFalse(a.admitted(env,d,o))
 def test_bounds_are_maintained_and_reference_is_not_claimed_as_measured(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));clock=[0];obs=self.observer(d,o,clock);self.assertEqual(obs.rounded(1),300);self.assertEqual(obs.rounded(100000),14400);self.assertFalse(a.settings(d)['initial_reference_is_measured'])
 def test_old_serial_scheduler_is_replaced_by_same_lock_gated_97_key_path(self):
  root=Path(__file__).resolve().parents[2];text=(root/'.github/workflows/afp-agri-v2-scheduled.yml').read_text();self.assertIn('automation.agri_v2.adaptive_schedule',text);self.assertNotIn('automation.agri_v2.cycle --scheduled',text);self.assertEqual(text.count('secrets.AGNES_API_KEY_'),97);self.assertIn('group: afp-agri-v2-live',text);self.assertIn('cancel-in-progress: false',text)

 def test_done_but_unprocessed_futures_are_not_an_active_tail(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));clock=[0];obs=self.observer(d,o,clock);clock[0]=1200;r=obs.observe(self.rows(16),active_topic_ids=[]);self.assertFalse(r['tail_adjustment_observed']);self.assertEqual(r['active_families'],0)
