import json,socket,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import recovery
from tests.agri_v2 import run_offline as runner

class OfflineRunnerIsolationTests(unittest.TestCase):
 def test_live_hold_is_unchanged_and_explicit_test_holds_still_work(self):
  for kind in ('text','image'):
   with tempfile.TemporaryDirectory() as td:
    live=Path(td)/'live';live.mkdir();file=live/'provider-circuit.json';original=json.dumps({'open':True,'request_kind':kind,'retry_at_epoch':time.time()+3600,'reason':'synthetic live hold'}).encode();file.write_bytes(original)
    def isolated_case():
     self.assertNotEqual(recovery.OUT,live);self.assertFalse(recovery.circuit_open(kind));self.assertEqual(file.read_bytes(),original)
     with self.assertRaisesRegex(AssertionError,'External network prohibited'):socket.create_connection(('example.test',443))
     with socket.socket() as sock:
      with self.assertRaisesRegex(AssertionError,'External network prohibited'):sock.connect(('127.0.0.1',1))
     # A circuit-specific unit test may still use its own explicit fixture.
     with patch.object(recovery,'OUT',live):self.assertTrue(recovery.circuit_open(kind))
    suite=unittest.TestSuite([unittest.FunctionTestCase(isolated_case)])
    with patch.object(recovery,'OUT',live),patch.object(runner.unittest.defaultTestLoader,'discover',return_value=suite):
     self.assertTrue(recovery.circuit_open(kind));self.assertEqual(runner.main(),0);self.assertEqual(recovery.OUT,live);self.assertTrue(recovery.circuit_open(kind))
    self.assertEqual(file.read_bytes(),original)
 def test_parallel_preflight_and_ci_use_same_isolated_runner(self):
  root=Path(__file__).resolve().parents[2]
  for name in ('afp-parallel-generator.yml','afp-owned-drafting-offline.yml'):
   text=(root/'.github/workflows'/name).read_text();self.assertIn('python tests/agri_v2/run_offline.py',text);self.assertNotIn('python -m unittest discover -s tests/agri_v2 -v',text)
