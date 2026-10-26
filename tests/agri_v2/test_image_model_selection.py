import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import healthcheck as h
from automation.agri_v2.client import ModelClient,CapabilityError
from automation.agri_v2 import image_diagnostic
class ImageModelSelectionTests(unittest.TestCase):
 def test_config_is_authoritative(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config.json';p.write_text(json.dumps({'image_model':'agnes-image-2.1-flash'}))
   self.assertEqual(h.configured_image_model(p),'agnes-image-2.1-flash')
 def test_selected_model_is_25(self):
  self.assertEqual(h.IMAGE_MODEL,'agnes-image-2.5-flash')
 def test_25_config_is_supported(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config.json';p.write_text(json.dumps({'image_model':'agnes-image-2.5-flash'}))
   self.assertEqual(h.configured_image_model(p),'agnes-image-2.5-flash')
 def test_unsupported_config_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config.json';p.write_text(json.dumps({'image_model':'other-model'}))
   with self.assertRaises(ValueError):h.configured_image_model(p)
 def test_production_payload_matches_verified_reference_test(self):
  c=object.__new__(ModelClient)
  with patch.object(c,'request',return_value={'model':h.IMAGE_MODEL}) as req,patch('automation.agri_v2.client.render_image',return_value=b'ok'):
   self.assertEqual(c.image('test'),b'ok');body=req.call_args.args[2]
   self.assertEqual(body['model'],h.IMAGE_MODEL);self.assertNotIn('n',body);self.assertEqual(body['size'],'1K');self.assertEqual(body['ratio'],'16:9')
   self.assertTrue(body['extra_body']['image'][0].startswith('data:image/'))
 def test_wrong_response_model_rejected(self):
  c=object.__new__(ModelClient)
  with patch.object(c,'request',return_value={'model':'wrong-model'}),patch('automation.agri_v2.client.render_image') as render:
   with self.assertRaises(CapabilityError):c.image('test')
   render.assert_not_called()
 def test_historical_diagnostic_does_not_silently_change(self):
  self.assertEqual(image_diagnostic.IMAGE_MODEL,'agnes-image-2.5-flash')
