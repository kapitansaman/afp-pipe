import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import review_contract as c,quality_index as q,scoped_research as s
from automation.agri_v2.queue import load_json,atomic_json
from automation.agri_v2.pipeline import digest

class CurrentArticleReviewTests(unittest.TestCase):
 def article(self):return {'content_html':'<p>عمق کاشت جو در منبع shallow توصیف شده است.</p>','excerpt':'این متن درباره حدود اعتبار منبع است.','faq':[{'question':'آیا خاک سنگین مجاز است؟','answer':'خیر؛ در همه شرایط کشت جو ممنوع است.'}]}
 def verdict(self,quote):return {'quality_policy':q.VERSION,'dimensions':dict(q.DIMENSIONS),'critical_issues':[{'code':'unsupported_material_quantity','article_quote':quote,'reason':'این ادعا باید با شاهد لفظی منبع و حدود کاربرد آن بررسی شود.'}],'reason':'این یک رأی آزمایشی است و هیچ تأیید علمی یا انسانی محسوب نمی‌شود.'}
 def test_brief_only_quote_never_becomes_an_article_critical_quote(self):
  a=self.article();v=self.verdict('عمق کاشت ایده‌آل جو حدود یک اینچ توصیه می‌شود');before=copy.deepcopy(v);r=c.contract(a,v)
  self.assertEqual(r['prior_mechanical_diagnostics'],[{'issue_index':0,'code':'critical_quote_not_in_current_article'}]);self.assertFalse(r['automatic_approval']);self.assertFalse(r['negative_verdicts_rewritten']);self.assertEqual(v,before)
  with self.assertRaisesRegex(ValueError,'quote not in current article'):q.evaluate(a,v)
 def test_real_negative_quote_vetoes_perfect_scores(self):
  a=self.article();v=self.verdict(a['faq'][0]['answer']);r=q.evaluate(a,v);self.assertEqual(r['score'],100);self.assertFalse(r['accepted']);self.assertEqual(c.contract(a,v)['prior_mechanical_diagnostics'],[])
 def test_examples_are_actual_substrings_and_cover_faq_not_brief(self):
  a=self.article();r=c.contract(a)
  self.assertTrue(r['actual_current_article_quote_examples'])
  for quote in r['actual_current_article_quote_examples']:self.assertIn(quote,q.article_text(a))
  self.assertIn(a['faq'][0]['answer'],r['actual_current_article_quote_examples']);self.assertEqual(r['article_sha256'],digest(a));self.assertNotIn('یک اینچ',json.dumps(r,ensure_ascii=False))
 def test_unbound_saved_verdict_is_not_silently_repaired_or_saved_as_approval(self):
  a=self.article();v=self.verdict('عمق کاشت ایده‌آل جو حدود یک اینچ توصیه می‌شود')
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td)
   with self.assertRaisesRegex(s.EvidenceBlocked,'article_quality_issue_quote_not_in_article'):s.save_article_review(a,{'topic_id':'fixture'},folder,v)
   self.assertFalse((folder/'article-evidence-review.json').exists());self.assertFalse((folder/'article-quality-index.json').exists())
 def test_new_review_receives_actual_quote_contract_and_preserves_negative(self):
  a=self.article();prior=self.verdict('عمق کاشت ایده‌آل جو حدود یک اینچ توصیه می‌شود');value=self.verdict(a['faq'][0]['answer']);client=Mock();client.text.return_value=value;b={'topic_id':'fixture','approved_facts':[],'source_scope_limitations':'محدود به اقلیم منبع'}
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);atomic_json(folder/'article-evidence-review.raw.json',prior)
   with patch.object(s,'article_review_flags',return_value=[]),patch('automation.agri_v2.content_matrix.contract',return_value={}),patch.object(q,'policy',return_value={'enabled':True}):
    with self.assertRaisesRegex(s.EvidenceBlocked,'below_publication_threshold'):s.review_article({'id':'fixture'},a,b,folder,client)
   request=json.loads(client.text.call_args.args[0]);self.assertEqual(request['review_response_contract']['prior_mechanical_diagnostics'][0]['code'],'critical_quote_not_in_current_article');self.assertFalse(load_json(folder/'article-quality-index.json')['accepted']);self.assertEqual(load_json(folder/'article-evidence-review.raw.json'),value);self.assertFalse((folder/'article-evidence-review.json').exists());client.text.assert_called_once();self.assertEqual(client.text.call_args.kwargs['attempts'],1)
 def test_unknown_critical_codes_and_boolean_scores_still_fail_closed(self):
  a=self.article();v=self.verdict(a['faq'][0]['answer']);v['critical_issues'][0]['code']='cosmetic_preference'
  with self.assertRaises(ValueError):q.evaluate(a,v)
  v=self.verdict(a['faq'][0]['answer']);v['dimensions']['readability']=True
  with self.assertRaises(ValueError):q.evaluate(a,v)
 def test_score_without_critical_issue_still_requires_original_thresholds(self):
  a=self.article();v=self.verdict(a['faq'][0]['answer']);v['critical_issues']=[];v['dimensions']['source_fidelity']=0;self.assertFalse(q.evaluate(a,v)['accepted'])
 def test_long_catalog_stays_bounded_and_never_changes_article(self):
  a=self.article();a['content_html']='<p>'+('عبارت بلند واقعی '*25000)+'</p>';before=copy.deepcopy(a);r=c.contract(a);self.assertLessEqual(len(r['actual_current_article_quote_examples']),128);self.assertTrue(all(len(x)<=1200 for x in r['actual_current_article_quote_examples']));self.assertEqual(a,before)
