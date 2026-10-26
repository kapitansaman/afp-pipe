import json,tempfile,unittest,importlib.util
from pathlib import Path
from unittest.mock import Mock
try:
 from automation.agri_v2 import model_matrix as m
except ImportError:
 spec=importlib.util.spec_from_file_location('model_matrix',Path(__file__).resolve().parents[2]/'automation/agri_v2/model_matrix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ModelMatrixTests(unittest.TestCase):
 def setup(self,tmp):
  data=Path(tmp)/'data';out=Path(tmp)/'out';m.atomic(data/'model-matrix-request.json',m.REQUEST);m.atomic(data/'config.json',{'repository':'kapitansaman/afp-pipe','publication_enabled':False,'automatic_generation':False});return data,out
 def env(self):return {'AGNES_API_KEY2':'PRIVATE_KEY_A','AGNES_API_KEY3':'PRIVATE_KEY_B','GITHUB_RUN_ID':'123'}
 def run_matrix(self,data,out,probe,env=None):return m.run(self.env() if env is None else env,data,out,probe,sleep_fn=lambda _:None,publish_fn=lambda _:None,cooldown_fn=lambda:False)
 def test_exact_cartesian_product_no_duplicates(self):
  rows=m.cells();self.assertEqual(len(rows),12);self.assertEqual(len({r['case_id'] for r in rows}),12);self.assertEqual({r['model'] for r in rows},set(m.MODELS));self.assertEqual({r['slot'] for r in rows},set(m.SLOTS));self.assertEqual({r['mode'] for r in rows},set(m.MODES))
 def test_reference_changes_only_input_reference(self):
  a=m.payload(m.MODELS[0],'plain',['data:image/webp;base64,test']);b=m.payload(m.MODELS[0],'reference',['data:image/webp;base64,test']);self.assertNotIn('image',a['extra_body']);self.assertIn('image',b['extra_body']);self.assertEqual(a['prompt'],b['prompt']);self.assertEqual(a['ratio'],'16:9');self.assertEqual(a['size'],'1K')
 def test_full_matrix_is_bounded_redacted_and_not_replayed(self):
  with tempfile.TemporaryDirectory() as tmp:
   data,out=self.setup(tmp);probe=Mock(return_value=({'state':'healthy','http_status':200,'valid_image':True,'native_landscape_16_9':True},b'image fixture'));r=self.run_matrix(data,out,probe);self.assertEqual(probe.call_count,12);self.assertEqual(r['valid_images'],12);self.assertEqual(r['status'],'completed');self.assertEqual(r['post_submissions'],0);self.assertFalse(r['production_enabled']);self.assertNotIn('PRIVATE_KEY',json.dumps(r));self.run_matrix(data,out,probe);self.assertEqual(probe.call_count,12)
 def test_duplicate_keys_make_zero_requests(self):
  with tempfile.TemporaryDirectory() as tmp:
   data,out=self.setup(tmp);probe=Mock();env=self.env();env['AGNES_API_KEY3']=env['AGNES_API_KEY2'];r=self.run_matrix(data,out,probe,env);probe.assert_not_called();self.assertEqual(r['status'],'missing_or_duplicate_credentials')
 def test_shared_quota_stops_before_next_cell(self):
  with tempfile.TemporaryDirectory() as tmp:
   data,out=self.setup(tmp);probe=Mock(return_value=({'state':'quota_limited','http_status':429},None));r=self.run_matrix(data,out,probe);probe.assert_called_once();self.assertEqual(r['status'],'waiting_shared_provider_deadline');self.assertEqual(r['image_calls'],1)
 def test_explicit_retry_after_honored_across_models_and_keys(self):
  with tempfile.TemporaryDirectory() as tmp:
   data,out=self.setup(tmp);probe=Mock(return_value=({'state':'provider_unavailable','http_status':503,'retry_after_seconds':7200},None));r=self.run_matrix(data,out,probe);probe.assert_called_once();self.assertGreaterEqual(r['retry_at_epoch'],m.time.time()+7199)
 def test_diagnostic_queue_observations_do_not_repeat_same_cell(self):
  with tempfile.TemporaryDirectory() as tmp:
   data,out=self.setup(tmp);probe=Mock(return_value=({'state':'provider_unavailable','http_status':503,'provider_code':'image_queue_full'},None));r=self.run_matrix(data,out,probe);self.assertEqual(probe.call_count,12);self.assertEqual(r['valid_images'],0);self.assertEqual(len({c['case_id'] for c in r['cases']}),12)
 def test_production_cannot_be_enabled_by_diagnostic(self):
  with tempfile.TemporaryDirectory() as tmp:
   data,out=self.setup(tmp);m.atomic(data/'config.json',{'repository':'kapitansaman/afp-pipe','publication_enabled':True});probe=Mock()
   with self.assertRaises(ValueError):self.run_matrix(data,out,probe)
   probe.assert_not_called()
