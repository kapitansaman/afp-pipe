import base64,hashlib,unittest
from unittest.mock import Mock
from automation.agri_v2 import media_policy as m,image_quality as q
from automation.agri_v2.client import ModelClient,CapabilityError
class TopicRoutedSceneTests(unittest.TestCase):
 def test_original_reference_bytes_no_layout_canvas(self):
  original=base64.b64decode((m.ASSETS/'afp-tape.webp.b64').read_text())
  for crop in ['لوبیا قرمز','لوبیا چیتی','گندم']:
   topic={'title':'برداشت '+crop,'crop':crop}
   for n in (1,2,3):
    actual=base64.b64decode(m.reference_images(n,topic)[0].split(',',1)[1])
    self.assertEqual(hashlib.sha256(actual).digest(),hashlib.sha256(original).digest())
 def test_harvest_does_not_require_filter(self):
  for crop in ['لوبیا قرمز','لوبیا چیتی','گندم']:
   topic={'title':'برداشت '+crop,'crop':crop};plan=m.scene_plan(topic,3)
   self.assertFalse(plan['hardware_required']);self.assertEqual(plan['reference_mode'],'original_product_identity_only')
   self.assertNotIn('closed black Y-filter',m.image_prompt(topic,3));self.assertIn('No filter, valve',m.image_prompt(topic,3))
 def test_filter_only_when_explicitly_requested(self):
  topic={'title':'نگهداری فیلتر آبیاری'}
  self.assertTrue(m.scene_plan(topic,3)['hardware_required']);self.assertIn('closed black Y-filter',m.image_prompt(topic,3))
  self.assertNotEqual(hashlib.sha256(m.reference_images(3,topic)[0].encode()).digest(),hashlib.sha256(m.reference_images()[0].encode()).digest())
 def test_reviewer_uses_topic_contract_not_role_alone(self):
  c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'message':{'content':'{}'}}]})
  with self.assertRaises(CapabilityError):c.review_image(b'fixture',{'title':'برداشت لوبیا چیتی','crop':'لوبیا چیتی'},3)
  prompt=c.request.call_args.args[2]['messages'][1]['content'][0]['text']
  self.assertIn('"hardware_required": false',prompt);self.assertIn('only when hardware_required=true',prompt)
 def test_new_policy_keeps_strict_critical_threshold(self):
  v={'score':91,'checks':{k:True for k in q.CHECKS},'reasons':['fixture']}
  self.assertTrue(q.verdict(v)['passed']);v['checks']['crop_stage_match']=False;self.assertFalse(q.verdict(v)['passed'])
