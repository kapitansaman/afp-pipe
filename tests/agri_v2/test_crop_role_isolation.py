import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import role_skills as roles,media_policy as media,scoped_research as research
from automation.agri_v2.queue import atomic_json
class CropRoleIsolationTests(unittest.TestCase):
 def test_carrot_visual_skill_only_for_actual_carrot(self):
  for role in ('image-generator','image-reviewer'):
   bean=roles.pack(role,topic={'crop':'لوبیا چیتی'});carrot=roles.pack(role,topic={'crop':'هویج'})
   self.assertNotIn('Daucus carota',bean['instructions']);self.assertNotIn('carrot seedlings',bean['instructions']);self.assertIn('Daucus carota',carrot['instructions']);self.assertIn(role+'-carrot.md',carrot['resources']);self.assertNotEqual(bean['sha256'],carrot['sha256'])
 def test_bean_generation_does_not_inherit_carrot_example(self):
  c=Mock();topic={'id':'test','crop':'لوبیا چیتی','intent':'soil_sensor','title':'پایش رطوبت خاک مزرعه لوبیا چیتی'};media.generate_role(c,topic,1);p=c.image.call_args.args[0];self.assertIn('Phaseolus vulgaris',p);self.assertNotIn('Daucus carota',p);self.assertNotIn('young carrot seedlings',p);c.image.assert_called_once()
 def test_storage_uses_harvested_grain_not_growing_field(self):
  topic={'id':'test','crop':'لوبیا چیتی','intent':'storage','title':'نگهداری لوبیا چیتی پس از برداشت'}
  for k in (1,2):
   plan=media.scene_plan(topic,k);self.assertEqual(plan['scene_route'],'postharvest-dry-bean-storage-v1');self.assertIn('pinto beans',plan['evidence']);self.assertNotIn('plants and straw-colored pods still attached',plan['evidence']);self.assertFalse(plan['hardware_required']);p=media.image_prompt(topic,k);self.assertIn('do not imply irrigation tape preserves stored grain',p);self.assertNotIn('base on a separate bare-soil patch',p)
 def test_rejected_reviewer_feedback_is_not_an_approval_override(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);previous={'all_article_claims_supported':False,'reason':'Previous potentially mistaken source reading'};atomic_json(folder/'lifecycle/article_evidence_review/rejected/1/article-evidence-review.raw.json',previous)
   article={'writing_policy':'practical-direct-html-v1'};flags=research.article_review_flags(article);c=Mock();c.text.return_value={**dict.fromkeys(flags,True),'all_article_claims_supported':False,'reason':'Actual unsupported absolute threshold remains; a prior reviewer exception may have referred to a different source paragraph.'}
   with self.assertRaises(research.EvidenceBlocked):research.review_article({'id':'test','crop':'لوبیا قرمز','title':'چرا بذر سبز نمی‌شود؟'},article,{'approved_facts':[],'source_scope_limitations':'Source is not local.'},folder,c)
   c.text.assert_called_once();payload=json.loads(c.text.call_args.args[0]);self.assertEqual(payload['previous_review_diagnostic'],previous);self.assertIn('untrusted feedback',payload['review_feedback_contract']);self.assertFalse((folder/'article-evidence-review.json').exists())
