import unittest,tempfile,json
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import image_quality as q
from automation.agri_v2.client import ModelClient,CapabilityError
from automation.agri_v2.queue import OUT
class SealedHardwareGateTests(unittest.TestCase):
 def test_open_port_false_overrides_perfect_score(self):
  value={'score':100,'checks':{k:True for k in q.CHECKS},'reasons':['fixture']};value['checks']['hardware_sealed_all_ports_connected']=False;self.assertFalse(q.verdict(value)['passed'])
 def test_old_fourteen_check_payload_no_longer_approves(self):
  value={'score':100,'checks':{k:True for k in q.CHECKS if k!='hardware_sealed_all_ports_connected'},'reasons':['fixture']}
  with self.assertRaises(q.ImageQualityError):q.verdict(value)
 def test_known_false_positive_never_reapproved_or_overwritten(self):
  image=OUT/'health-canary/one-hour-final-technical-canary-v1/role-3.webp';before=q.review_path(image).read_bytes();client=Mock()
  with self.assertRaises(q.ImageQualityError):q.ensure_review(client,image,{'id':'agri-af1a4b491d83','crop':'لوبیا قرمز'},3)
  client.review_image.assert_not_called();self.assertEqual(q.review_path(image).read_bytes(),before)
 def test_reviewer_prompt_explicitly_rejects_uncapped_mouth(self):
  client=object.__new__(ModelClient);client.request=Mock(return_value={'choices':[{'message':{'content':'{}'}}]})
  with self.assertRaises(CapabilityError):client.review_image(b'fixture',{'crop':'لوبیا قرمز','title':'نصب فیلتر آبیاری'},3)
  prompt=str(client.request.call_args);self.assertIn('hardware_sealed_all_ports_connected',prompt);self.assertIn('uncapped upward mouth',prompt)
