import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import practical_drafting as p,grounded_drafting as g
from automation.agri_v2.pipeline import numbers

def fixture():
 topic={'id':'agri-000000000001','title':'پرسش عملی مزرعه','crop':'هویج','intent':'germination'};url='https://extension.example.edu/carrots';brief={'review_mode':'automated_scoped_evidence_review_v1','sources':[{'url':url,'excerpt':'RAW UNAPPROVED 9999'}],'approved_facts':[{'fact_id':'f0','claim':'رطوبت سطح خاک در استقرار بذر اهمیت دارد.','conditions':'این شاهد محدود به شرایط منبع است و تضمین نتیجه نیست.','source_url':url}]}
 starts=['آغاز','شواهد','رطوبت','خاک','حدود','تصمیم','پایش','نتیجه']
 paragraphs=[start+' '+('در این بررسی وضعیت مزرعه و محدودیت شواهد موجود برای خواننده به روشنی توضیح داده می‌شود. '*5) for start in starts]
 raw={'title':topic['title'],'content_html':'<h2>پاسخ مستقیم</h2>'+''.join('<p>'+text+' <a href="'+url+'">منبع</a></p>' for text in paragraphs)+'<table><tr><td>نکته مستند</td><td>حدود کاربرد</td></tr></table>','excerpt':'این خلاصه از همان موضوع و حدود شواهد در مقاله توضیح می‌دهد.','faq':[{'question':'پرسش مرتبط درباره مزرعه چیست؟','answer':'این پاسخ درباره همان شواهد موجود و محدودیت کاربرد آن توضیح می‌دهد.'} for _ in range(3)]};return topic,brief,raw
class PracticalDraftingTests(unittest.TestCase):
 def test_one_heading_and_short_paragraph_are_not_blockers(self):
  t,b,r=fixture();r['content_html']=r['content_html'].replace('<h2>پاسخ مستقیم</h2>','<h2>پاسخ مستقیم</h2><p>این بند کوتاه است.</p>');article,report=p.normalize(r,t,b);self.assertEqual(article['title'],t['title']);self.assertTrue(report['warnings']);self.assertFalse(report['claims_added_by_normalizer'])
 def test_49_word_paragraph_is_accepted_without_padding(self):
  t,b,r=fixture();text=' '.join(['توضیح']*49);r['content_html']=r['content_html'].replace('<h2>پاسخ مستقیم</h2>','<h2>پاسخ مستقیم</h2><p>'+text+'</p>');article,_=p.normalize(r,t,b);self.assertIn('<p>'+text+'</p>',article['content_html'])
 def test_unambiguous_wrapper_html_alias_and_excerpt_are_repaired(self):
  t,b,r=fixture();r['html']=r.pop('content_html');r.pop('excerpt');original=copy.deepcopy(r);article,report=p.normalize({'result':r},t,b);self.assertEqual(r,original);self.assertTrue(article['excerpt']);self.assertTrue(any(x['kind']=='unwrap_inert_object' for x in report['format_repairs']));self.assertFalse(report['claims_added_by_normalizer'])
 def test_conflicting_alternatives_are_not_silently_chosen(self):
  t,b,r=fixture()
  for raw in [dict(r,article=r),dict(r,html='<p>Conflicting text</p>')]:
   with self.assertRaises(ValueError):p.normalize(raw,t,b)
 def test_unsafe_links_scripts_new_numbers_and_mixed_language_remain_blockers(self):
  t,b,r=fixture()
  for suffix in ['<script>alert(1)</script>','<a href="https://evil.example/">bad link</a>','<p>عدد ساختگی 9999</p>','<p>متن 在经过</p>']:
   raw=copy.deepcopy(r);raw['content_html']+=suffix
   with self.assertRaises(ValueError):p.normalize(raw,t,b)
 def test_repeated_substantive_paragraph_still_rejected(self):
  t,b,r=fixture();r['content_html']+=r['content_html'][r['content_html'].index('<p>'):r['content_html'].index('</p>')+4]
  with self.assertRaisesRegex(ValueError,'Duplicate substantive'):p.normalize(r,t,b)
 def test_title_and_research_numbers_cannot_be_rewritten(self):
  t,b,r=fixture();r['title']='عنوان دیگر'
  with self.assertRaisesRegex(ValueError,'canonical intent'):p.normalize(r,t,b)
 def test_active_writer_uses_direct_html_not_strict_schema_or_fact_id_outline(self):
  t,b,r=fixture();c=Mock();c.text.return_value=r
  with tempfile.TemporaryDirectory() as td:
   article=g.generate(c,t,b,Path(td));request=json.loads(c.text.call_args.args[0]);self.assertEqual(c.text.call_count,1);self.assertNotIn('response_schema',c.text.call_args.kwargs);self.assertEqual(c.text.call_args.kwargs['max_tokens'],14000);self.assertNotIn('9999',json.dumps(request));self.assertNotIn('constraints',request);self.assertIn('commercial_matrix',article)
 def test_below_editorial_target_warns_but_fragment_still_rejected(self):
  import re
  from automation.agri_v2.pipeline import validate_article
  t,b,r=fixture();n=[0]
  def short(match):
   n[0]+=1;start=['آغاز','شواهد','رطوبت','خاک','حدود','تصمیم','پایش','نتیجه'][n[0]-1];return '<p>'+start+' '+('توضیح مرتبط با شواهد محدود موجود و شرایط کاربرد آن برای خواننده روشن است. '*3)+'</p>'
  r['content_html']=re.sub(r'<p>.*?</p>',short,r['content_html']);r['content_html']+='<p><a href="'+b['sources'][0]['url']+'">منبع</a></p>'
  a,report=p.normalize(r,t,b);self.assertTrue(any(x['kind']=='overall_length_below_editorial_target_not_blocker' for x in report['warnings']));legacy=dict(a);legacy.pop('writing_policy')
  with self.assertRaisesRegex(ValueError,'550'):validate_article(legacy,t,b)
  tiny=dict(r,content_html='<p>متن ناقص <a href="'+b['sources'][0]['url']+'">منبع</a></p><table><tr><td>نکته</td></tr></table>')
  with self.assertRaises(ValueError):p.normalize(tiny,t,b)
 def test_unified_final_review_requires_core_truth_and_never_ignores_negative_commercial_judgment(self):
  from automation.agri_v2 import scoped_research as s
  t,b,r=fixture();a,_=p.normalize(r,t,b);value={k:True for k in ['all_article_claims_supported','no_additional_numbers_or_advice','units_geography_product_preserved','answers_canonical_intent','no_fabricated_human_review']};value['reason']='The actual source claims, units, scope, reader answer and commercial context were independently checked without fabricated claims.';s.validate_article_review_result(a,value)
  for key in ['all_article_claims_supported','answers_canonical_intent','product_claims_not_invented','irrigation_bridge_supported_or_omitted']:
   bad=dict(value);bad[key]=False
   with self.assertRaises(ValueError):s.validate_article_review_result(a,bad)
 def test_old_commercial_review_contract_is_not_retroactively_weakened(self):
  from automation.agri_v2 import scoped_research as s
  t,b,r=fixture();a,_=p.normalize(r,t,b);a.pop('writing_policy');value={k:True for k in ['all_article_claims_supported','no_additional_numbers_or_advice','units_geography_product_preserved','answers_canonical_intent','no_fabricated_human_review']};value['reason']='The actual source claims and scope were independently checked without fabricated claims or scientific review.'
  with self.assertRaises(ValueError):s.validate_article_review_result(a,value)
 def test_source_citation_tags_in_faq_become_plain_text_without_changing_numbers(self):
  t,b,r=fixture();url=b['sources'][0]['url'];r['faq'][0]['answer']+=' <a href="'+url+'">منبع</a>';a,report=p.normalize(r,t,b);self.assertNotIn('<',a['faq'][0]['answer']);self.assertTrue(any(x['kind']=='plain_faq_citation_tags' for x in report['format_repairs']));r['faq'][0]['answer']+=' <a href="https://evil.example/">bad</a>'
  with self.assertRaises(ValueError):p.normalize(r,t,b)
