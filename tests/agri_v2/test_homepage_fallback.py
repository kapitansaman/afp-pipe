import unittest
from unittest.mock import Mock
from automation.agri_v2 import homepage_fallback as h,internal_links as links,multilingual as m
class HomepageFallbackTests(unittest.TestCase):
 def decision(self,lang='fa-IR'):return h.resolve(True,[],lang,'https://navar-abyari.ir/current/',lambda *args:True)
 def test_related_article_suppresses_fallback_without_home_request(self):
  verify=Mock();r=h.resolve(True,[{'url':'https://navar-abyari.ir/related/'}],'fa-IR','https://navar-abyari.ir/current/',verify);self.assertIsNone(r['link']);verify.assert_not_called()
 def test_no_actual_irrigation_context_never_adds_forced_link(self):
  self.assertFalse(h.irrigation_context({'commercial_matrix':{'business_goal':'irrigation','irrigation_relationship':'distant'}},{'approved_facts':[{'claim':'رطوبت انبار و نگهداری بذر'}]}));self.assertTrue(h.irrigation_context({}, {'approved_facts':[{'claim':'تنش آبی و رطوبت خاک'}]}));self.assertIsNone(h.resolve(False,[],'fa-IR','https://navar-abyari.ir/current/',Mock())['link'])
 def test_context_is_not_truthy_arbitrary_string(self):
  self.assertIsNone(h.resolve('true',[],'fa-IR','https://navar-abyari.ir/current/',Mock())['link'])
 def test_each_language_uses_only_its_verified_home_and_local_anchor(self):
  for lang,(url,anchor,_) in h.HOMES.items():
   verify=Mock(return_value=True);r=h.resolve(True,[],lang,'https://navar-abyari.ir/current/',verify);verify.assert_called_once_with(url,lang);self.assertEqual(r['link']['anchor'],anchor);self.assertEqual(r['link']['url'],url)
 def test_verification_failure_does_not_fall_back_to_persian_or_block_article(self):
  verify=Mock(side_effect=ValueError('Wrong language or unavailable'));r=h.resolve(True,[],'en-US','https://navar-abyari.ir/current/',verify);self.assertIsNone(r['link']);self.assertIn('verification_failed',r['status']);verify.assert_called_once_with('https://navar-abyari.ir/en/','en-US')
 def test_unknown_language_and_self_link_never_fall_back_to_root(self):
  self.assertIsNone(h.resolve(True,[],'de-DE','https://navar-abyari.ir/current/',Mock())['link']);self.assertIsNone(h.resolve(True,[],'fa-IR','https://navar-abyari.ir/',Mock())['link'])
 def test_single_link_idempotent_neutral_sentence_before_faq(self):
  row=self.decision()['link'];body='<p>متن علمی</p><h2>سؤالات متداول</h2><p>پاسخ</p>';once=h.add(body,row,'fa-IR');self.assertEqual(h.add(once,row,'fa-IR'),once);self.assertEqual(once.count('href="https://navar-abyari.ir/"'),1);self.assertLess(once.index('afp-home-fallback'),once.index('<h2>سؤالات'));self.assertIn('متن علمی',once)
 def test_existing_home_link_is_not_duplicated_or_reworded(self):
  body='<p><a href="https://navar-abyari.ir/">نوار آبیاری</a></p>';self.assertEqual(h.add(body,self.decision()['link'],'fa-IR'),body)
 def test_cross_language_or_forged_url_rejected(self):
  with self.assertRaises(ValueError):h.add('<p>Text</p>',self.decision()['link'],'en-US')
 def test_augment_handles_neutral_home_even_with_commercial_cta_disabled(self):
  t={'crop':'چغندر لبویی','commercial_matrix':{'version':'search-to-drip-content-matrix-v1','cta_mode':'none'},'editorial_related':[],'editorial_home':self.decision()['link']};body='<p>متن <a href="https://example.edu/source">منبع</a></p>';result=links.augment(body,t,'https://navar-abyari.ir/current/');self.assertEqual(links.external_links(result),links.external_links(body));links.verify_links(result,links.selected_links(t,'https://navar-abyari.ir/current/'));self.assertIn('نوار تیپ',result)
 def test_translated_home_stays_before_final_scientific_sources(self):
  from automation.agri_v2.editorial_presentation import START,verify_sources
  row={'language':'en-US','title':'Test','content_html':'<p>Fact <a href="https://example.edu/source">Source</a></p>','faq':[{'question':'Q','answer':'A'}]}
  body=m.localized_body(row,[{'url':'https://navar-abyari.ir/media.webp'}],{'en-US':[self.decision('en-US')['link']]},lambda u:(u,'<html lang="en-US">',200));self.assertEqual(body.count('href="https://navar-abyari.ir/en/"'),1);self.assertLess(body.index('afp-home-fallback'),body.index(START));verify_sources(body,[{'url':'https://example.edu/source'}],'en-US')

 def test_nonaffirmative_probe_never_approves_home(self):
  self.assertIsNone(h.resolve(True,[],'fa-IR','https://navar-abyari.ir/current/',lambda *args:False)['link'])
 def test_existing_second_allowed_persian_keyword_verifies_without_duplicate(self):
  row=self.decision()['link'];body='<p><a href="https://navar-abyari.ir/">نوار آبیاری</a></p>';self.assertTrue(links.contains_link(body,row));self.assertEqual(h.add(body,row,'fa-IR'),body)
