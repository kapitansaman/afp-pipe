import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import production_readiness as r
from automation.agri_v2.queue import atomic_json,utcnow
from automation.agri_v2.parallel_capacity import CREDENTIAL_SET_ID
from automation.agri_v2.parallel_pool import SLOTS
from automation.agri_v2.healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE

class ProductionReadinessTests(unittest.TestCase):
 def setup(self,root):
  d=root/'data';o=root/'out';atomic_json(d/'parallel-policy.json',{'key_limit':97,'max_article_workers':20});atomic_json(d/'family-lifecycle-policy.json',{'enabled':True,'publication_enabled':True,'research_only_for_scoped_rollout':False,'max_attempts_per_stage':3});atomic_json(d/'config.json',{'multilingual':{'enabled':True}});atomic_json(o/'parallel/families/assignments.json',{'families':[]});health={'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'checked_at':utcnow(),'audit_status':'completed','eligible_text_slots':SLOTS,'eligible_image_slots':[SLOTS[-1]],'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE};atomic_json(o/'parallel/health/latest.json',health);return d,o,health
 def inspect(self,d,o,wp=None):
  topics=[{'id':'agri-'+format(i,'012x'),'family_id':'family-'+str(i+1).zfill(2)} for i in range(20)]
  with patch('automation.agri_v2.family_scheduler.assigned_topics',return_value=topics),patch('automation.agri_v2.family_lifecycle.next_stage',return_value=('text',None)),patch('automation.agri_v2.family_lifecycle.state',return_value={'attempts':0}):return r.inspect(d,o,wp)
 def test_text_pass_does_not_count_as_actual_image_proof(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h=self.setup(Path(td));v=self.inspect(d,o);self.assertTrue(v['gates']['fresh_text_capacity']['passed']);self.assertFalse(v['gates']['fresh_image_capacity']['passed']);self.assertFalse(v['technical_ready']);self.assertEqual(v['model_calls'],0)
 def test_old_cohort_even_if_fresh_is_not_capacity_proof(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h=self.setup(Path(td));h['credential_set_id']='afp-pipe-parallel-75-keys-v1';atomic_json(o/'parallel/health/latest.json',h);self.assertFalse(self.inspect(d,o)['gates']['fresh_text_capacity']['passed'])
 def test_authenticated_options_can_verify_bridge_without_any_post_mutation(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h=self.setup(Path(td));wp=Mock();wp.preflight.return_value={'can_publish':True,'roles':['author']};wp.call.return_value=({'schema':{'properties':{'afp_language':{},'afp_source_post_id':{}}}},{});v=self.inspect(d,o,wp);self.assertTrue(v['gates']['authenticated_publisher']['passed']);self.assertTrue(v['gates']['translation_bridge']['passed']);wp.call.assert_called_once_with('posts',method='OPTIONS');self.assertEqual(v['post_mutations'],0)
 def test_bound_actual_image_response_is_separate_from_eligible_slot_declaration(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,h=self.setup(Path(td));atomic_json(o/'parallel/runtime/image'/(SLOTS[-1]+'.json'),{'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'slot':SLOTS[-1],'model':IMAGE_MODEL,'verified_at':utcnow(),'verification':'actual_successful_parallel_response'});self.assertTrue(self.inspect(d,o)['gates']['fresh_image_capacity']['passed'])
