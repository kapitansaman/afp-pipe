import copy,unittest
from automation.agri_v2 import translation_review as r,multilingual as m
from test_multilingual import article,response
class TranslationReviewTests(unittest.TestCase):
 def test_all_four_positive_judgments_required(self):
  good={'faithful':True,'languages':{lang:True for lang in m.LANGUAGES},'reason':'All actual target meanings and numbers were compared to the Persian source.'};r.validate(good)
  for lang in m.LANGUAGES:
   bad=copy.deepcopy(good);bad['languages'][lang]=False
   with self.assertRaises(ValueError):r.validate(bad)
 def test_review_binding_changes_if_any_translation_changes(self):
  a=article();rows={lang:m.render_translation(a,response(a,lang),lang) for lang in m.LANGUAGES};before=r.binding(a,rows);rows['en-US']['title']='Different text';self.assertNotEqual(before,r.binding(a,rows))
 def test_carrot_not_maize_in_tajik(self):
  a=article();a['commercial_matrix']={'crop':'هویج'};raw=response(a,'tg-TJ');parser,_=m.source_segments(a);raw['translations'][len(parser.texts)]['text']='Чаро тухмии сабзӣ намесабзад?';raw['translations'][0]['text']='ҷуворимакка'
  with self.assertRaisesRegex(ValueError,'crop identity'):m.render_translation(a,raw,'tg-TJ')
