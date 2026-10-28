import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import staged_rollout as r,family_admission as admission,family_scheduler as scheduler
from automation.agri_v2.foundation_policy import POLICY
from automation.agri_v2.queue import atomic_json,load_json
from tests.agri_v2 import test_family_scheduler as fixtures

class FoundationStagedRolloutTests(unittest.TestCase):
 def setup(self,td):
  d,o,topics=fixtures.FamilySchedulerTests().setup(Path(td));atomic_json(d/'generator-foundation-policy.json',POLICY);topics=[dict(t,family_id='family-'+str(i+1).zfill(2)) for i,t in enumerate(topics[:20])];rows=[{'topic_id':t['id'],'family_id':t['family_id'],'stage':'text','due':True} for t in topics];return d,o,topics,rows
 def choose(self,topics,rows,d,o,run='100'):
  with patch.object(admission,'project',return_value=(topics,rows)):return r.choose(topics,d,o,run)
 def test_initial_limit_is_one_and_repeat_keeps_cohort_identity(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);selected,info=self.choose(t,rows,d,o);again,info2=self.choose(t,rows,d,o,'101');self.assertEqual(len(selected),1);self.assertEqual(again,selected);self.assertEqual(info['limit'],1);self.assertEqual(len(r.load(o)['cohort']),1)
 def test_prior_unrelated_pilot_is_not_a_new_stage_acceptance(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);atomic_json(o/'parallel/scoped-family-pilot/accepted.json',{'public_verified':True});selected,info=self.choose(t,rows,d,o);self.assertEqual(info['limit'],1);self.assertEqual(len(selected),1)
 def test_waiting_cohort_is_not_replaced_or_escalated(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);selected,_=self.choose(t,rows,d,o)
   with patch.object(admission,'project',return_value=(t[1:],rows)):again,info=r.choose(t,d,o,'101')
   self.assertEqual(again,[]);self.assertEqual(info['limit'],1);self.assertEqual(info['cohort'][0]['topic_id'],selected[0]['id'])
 def test_explicit_acceptance_moves_one_to_three_then_twenty_only(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);self.choose(t,rows,d,o);wp=Mock();env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'verify-1'}
   with patch.object(r,'verify_topic',side_effect=lambda m,*a:dict(m,public_verified=True)):result=r.verify(env,d,o,wp)
   self.assertEqual(result['current_limit'],3);selected,info=self.choose(t,rows,d,o,'102');self.assertEqual(len(selected),3);self.assertNotIn(t[0]['id'],{x['id'] for x in selected})
   with patch.object(r,'verify_topic',side_effect=lambda m,*a:dict(m,public_verified=True)):result=r.verify(env,d,o,wp)
   self.assertEqual(result['current_limit'],20);self.assertEqual([x['limit'] for x in r.load(o)['accepted']],[1,3]);self.assertFalse(result['schedule_enabled'])
 def test_incomplete_or_unknown_verification_never_changes_limit(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);self.choose(t,rows,d,o);before=(o/r.BASE/'state.json').read_bytes();wp=Mock()
   with patch.object(r,'verify_topic',side_effect=ValueError('untrusted raw secret')):result=r.verify({'GITHUB_EVENT_NAME':'workflow_dispatch'},d,o,wp)
   self.assertEqual(result['status'],'staged_acceptance_not_ready');self.assertEqual(result['failure']['category'],'unspecified');self.assertEqual(before,(o/r.BASE/'state.json').read_bytes());self.assertNotIn('secret',str(result));self.assertEqual(result['post_mutations'],0)
 def test_mutated_or_missing_acceptance_proof_cannot_enable_larger_stage(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);self.choose(t,rows,d,o)
   with patch.object(r,'verify_topic',return_value={'public_verified':True}):r.verify({'GITHUB_EVENT_NAME':'workflow_dispatch'},d,o,Mock())
   proof=next((o/r.BASE/'acceptances').glob('*.json'));proof.unlink()
   with self.assertRaises(ValueError):r.load(o)
 def test_limit_field_alone_cannot_skip_acceptance_chain(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);state=r.load(o);state['limit']=20;r.save(o,state)
   with self.assertRaises(ValueError):r.load(o)
 def test_missing_second_checkpoint_is_not_resumption_proof(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);atomic_json(o/'parallel/lifecycle/runs/1/report.json',{'run_id':'1','status':'completed','results':[{'topic_id':t[0]['id'],'checkpoint_merged':True,'status':'stage_completed'}]})
   with self.assertRaises(ValueError):r.checkpoints(t[0]['id'],o)
   atomic_json(o/'parallel/lifecycle/runs/2/report.json',{'run_id':'2','status':'completed_with_failures','results':[{'topic_id':t[0]['id'],'checkpoint_merged':True,'status':'stage_completed'}]});self.assertEqual(len(r.checkpoints(t[0]['id'],o)),2)
 def test_unknown_or_unmerged_checkpoint_does_not_count(self):
  for status in ('worker_timed_out','worker_failed','stage_reconciliation_required'):
   with tempfile.TemporaryDirectory() as td:
    d,o,t,rows=self.setup(td)
    for run in ('1','2'):atomic_json(o/'parallel/lifecycle/runs'/run/'report.json',{'run_id':run,'status':'completed','results':[{'topic_id':t[0]['id'],'checkpoint_merged':True,'status':status}]})
    with self.assertRaises(ValueError):r.checkpoints(t[0]['id'],o)
 def test_live_acceptance_requires_complete_family_before_wordpress_or_model_call(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);wp=Mock();member={'topic_id':t[0]['id'],'family_id':t[0]['family_id'],'title_sha256':r.digest(t[0]['title'])}
   with patch.object(r,'get_topic',return_value=t[0]),patch.object(scheduler,'family_complete',return_value=False),self.assertRaises(ValueError):r.verify_topic(member,wp,d,o)
   wp.call.assert_not_called();wp.verify.assert_not_called()
 def test_active_stage_keeps_ownership_through_language_handoff(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td)
   with patch.object(scheduler,'items',return_value=t):before=scheduler.allocate(d,o)
   self.choose(t,rows,d,o)
   with patch.object(scheduler,'items',return_value=t),patch('automation.agri_v2.language_review_queue.released',side_effect=lambda ident,*a:ident==t[0]['id']):after=scheduler.allocate(d,o)
   self.assertEqual(before['families'][0]['topic_id'],after['families'][0]['topic_id']);self.assertTrue(r.protects_handoff(t[0]['id'],d,o))
 def test_nonmanual_verification_is_rejected_without_access(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,rows=self.setup(td);wp=Mock()
   with self.assertRaises(ValueError):r.verify({'GITHUB_EVENT_NAME':'schedule'},d,o,wp)
   wp.preflight.assert_not_called()
 def test_published_bytes_require_original_receipt_hash_not_just_owned_marker(self):
  import hashlib
  raw='<!-- owned -->\n<p>approved source-bound bytes</p>';receipt={'publication_content_sha256':hashlib.sha256(raw.encode()).hexdigest()};r.verify_published_bytes({'content':{'raw':raw}},receipt)
  for post,proof in (({'content':{'raw':raw+'<p>unsupported change</p>'}},receipt),({'content':{'raw':raw}},{}),({'content':{'rendered':raw}},receipt)):
   with self.assertRaises(ValueError):r.verify_published_bytes(post,proof)
