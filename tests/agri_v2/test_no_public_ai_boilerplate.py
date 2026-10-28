import unittest
from automation.agri_v2.article_format import DISCLOSURE
from automation.agri_v2 import multilingual as m
from automation.agri_v2.editorial_presentation import verify_sources
class NoPublicAIBoilerplateTests(unittest.TestCase):
 def test_persian_and_legacy_renderers_have_no_public_disclosure(self):self.assertEqual(DISCLOSURE,'')
 def test_all_translations_omit_ai_boilerplate_and_keep_faq_sources_limits(self):
  banned=('Prepared with AI assistance','Материал подготовлен с помощью ИИ','أُعد هذا المقال بمساعدة الذكاء الاصطناعي','Ин мақола бо ёрии зеҳни сунъӣ')
  for lang in m.LANGUAGES:
   row={'language':lang,'title':'Title','content_html':'<p>Source-region limitations remain. <a href="https://example.edu/source">Source</a></p>','faq':[{'question':'Q','answer':'A'}]}
   body=m.localized_body(row,[{'url':'https://navar-abyari.ir/a.webp'}],{lang:[]})
   for text in banned:self.assertNotIn(text,body)
   self.assertNotIn('<p><em></em></p>',body);self.assertIn('Source-region limitations remain.',body);self.assertIn(m.FAQ_LABEL[lang],body);verify_sources(body,[{'url':'https://example.edu/source'}],lang)
