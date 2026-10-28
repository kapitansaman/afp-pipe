import unittest
from automation.agri_v2 import media_policy as m
class CropVisualIdentityTests(unittest.TestCase):
 def topic(self,crop,title='انتخاب رقم مناسب برای کشت',intent='variety'):return {'id':'agri-123456789abc','crop':crop,'title':title,'intent':intent}
 def test_nonharvest_red_kidney_color_is_seed_coat_not_pepper_fruit(self):
  t=self.topic('لوبیا قرمز');spec=m.crop_spec(t);self.assertIn('Phaseolus vulgaris',spec);self.assertIn('green bean pods',spec);self.assertIn('SEED COATS INSIDE',spec);self.assertIn('never red fleshy fruit',spec);self.assertIn(spec,m.image_prompt(t,1))
 def test_cowpea_never_becomes_common_bean(self):
  for crop in ('لوبیا چشم\u200cبلبلی','لوبیا چشم بلبلی'):
   t=self.topic(crop,'برداشت محصول خشک لوبیا چشم بلبلی');spec=m.crop_spec(t);self.assertIn('Vigna unguiculata',spec);self.assertIn('NOT common bean',spec);self.assertFalse(m.common_bean(t));self.assertFalse(m.use_red_bean_close(t));self.assertNotIn('Phaseolus vulgaris) at harvest',m.scene_plan(t,1)['botany'])
 def test_other_crop_title_mentioning_bean_does_not_change_botany(self):
  t=self.topic('جو','کاشت جو پس از برداشت لوبیا قرمز');self.assertFalse(m.common_bean(t));self.assertFalse(m.use_red_bean_close(t));self.assertNotIn('common bean (Phaseolus',m.crop_spec(t))
 def test_existing_true_common_bean_harvest_identity_remains_strict(self):
  t=self.topic('لوبیا قرمز','برداشت لوبیا قرمز پس از رسیدگی');self.assertTrue(m.common_bean(t));self.assertTrue(m.use_red_bean_close(t));self.assertIn('straw-brown papery pods',m.crop_spec(t));self.assertIn('NEVER bright red pod walls',m.crop_spec(t))
