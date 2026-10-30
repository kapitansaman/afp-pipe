import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import single_family_plan as p,family_keys as k,family_model_routing as m,staged_rollout as s
from automation.agri_v2.queue import atomic_json

class SingleFamilyPlanTests(unittest.TestCase):
 def setup(self,root):
  d=root/'data';o=root/'out';atomic_json(d/'family-key-allocation.json',k.default_policy());atomic_json(d/'family-model-routing.json',m.expected(d))
  s.save(o,{'version':1,'limit':1,'cohort':[{'family_id':'family-07','topic_id':'agri-6fc1032cdf42'}],'accepted':[],'history':[],'schedule_enabled':False,'original_attempts_reset':False})
  atomic_json(o/'parallel/readiness/latest.json',{'families':[{'family_id':'family-07','topic_id':'agri-6fc1032cdf42','next_stage':'publish','attempts':3,'retry_exhausted':True}]})
  return d,o
 def test_budget_only_three_owned_text_one_image(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));r=p.prepare(d,o);b=r['proposed_capability_only_budget']
   self.assertEqual(b['text_slots'],['AGNES_API_KEY25','AGNES_API_KEY26','AGNES_API_KEY27']);self.assertEqual(b['image_slot'],'AGNES_API_KEY28');self.assertEqual((b['max_text_calls'],b['max_image_calls'],b['max_runs'],b['max_attempts_per_slot'],b['max_parallel_requests']),(3,1,1,1,1))
 def test_proposal_never_authorizes_transport_or_claims_success(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));r=p.prepare(d,o)
   for key in ('paid_execution_authorized','publication_authorized','schedule_enabled','promotion_authorized','reset_attempts','global_capacity_refresh','production_readiness_claimed','capability_success_is_visual_approval'):self.assertIs(r[key],False)
   self.assertEqual((r['model_calls'],r['image_calls'],r['site_calls'],r['published_posts']),(0,0,0,0));self.assertEqual(r['status'],'offline_proposal_not_authorized')
 def test_no_files_mutated_and_no_network(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o=self.setup(root)
   def hashes():return {str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in root.rglob('*') if f.is_file()}
   before=hashes()
   with patch('socket.socket.connect',side_effect=AssertionError('No network')):p.prepare(d,o)
   self.assertEqual(before,hashes())
 def test_exhausted_stage_preserved_not_reset_or_admitted(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));r=p.prepare(d,o);self.assertEqual(r['current_stage']['attempts'],3);self.assertTrue(r['current_stage']['retry_exhausted']);self.assertIn('existing_stage_budget_exhausted_no_automatic_continuation',r['blockers'])
 def test_isolated_positive_is_not_production_language_acceptance(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));self.assertIn('production_language_acceptance_not_proven_by_isolated_diagnostics',p.prepare(d,o)['blockers'])
 def test_multiple_cohort_cannot_silently_select(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));s.save(o,{'version':1,'limit':1,'cohort':[],'accepted':[],'history':[],'schedule_enabled':False,'original_attempts_reset':False})
   with self.assertRaises(ValueError):p.prepare(d,o)
 def test_mismatched_readiness_topic_fails(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));atomic_json(o/'parallel/readiness/latest.json',{'families':[{'family_id':'family-07','topic_id':'agri-000000000000'}]})
   with self.assertRaises(ValueError):p.prepare(d,o)
 def test_unknown_attempt_budget_fails(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));atomic_json(o/'parallel/readiness/latest.json',{'families':[{'family_id':'family-07','topic_id':'agri-6fc1032cdf42','attempts':True,'retry_exhausted':False}]})
   with self.assertRaises(ValueError):p.prepare(d,o)
 def test_no_article_prose_or_raw_response_is_copied(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));folder=o/'new/agri-6fc1032cdf42';atomic_json(folder/'article.json',{'content':'PRIVATE ARTICLE PROSE'});atomic_json(folder/'lifecycle/text/state.json',{'status':'validated','attempts':3,'raw':'PRIVATE RAW'})
   r=p.prepare(d,o);self.assertNotIn('PRIVATE',json.dumps(r));self.assertIn('article.json',r['input_sha256']);self.assertEqual(r['operational_states']['text']['attempts'],3)
 def test_changed_input_changes_binding(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));a=p.prepare(d,o);path=o/'parallel/readiness/latest.json';row=json.loads(path.read_text());row['checked_at']='new evidence';atomic_json(path,row);b=p.prepare(d,o);self.assertNotEqual(a['input_sha256']['readiness'],b['input_sha256']['readiness'])
 def test_missing_routing_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));(d/'family-model-routing.json').unlink()
   with self.assertRaises(ValueError):p.prepare(d,o)
 def test_unsafe_topic_fails(self):
  with tempfile.TemporaryDirectory() as td:
   d,o=self.setup(Path(td));state=s.load(o);state['cohort'][0]['topic_id']='../../other';s.save(o,state)
   with self.assertRaises(ValueError):p.prepare(d,o)
