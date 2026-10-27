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
