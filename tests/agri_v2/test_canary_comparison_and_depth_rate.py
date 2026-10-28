import unittest
from automation.agri_v2.text_fields import plain_citations
from automation.agri_v2.translation_chunks import normalize_batch
from automation.agri_v2.multilingual import source_segments,render_translation
from automation.agri_v2.display_units import text,content,UnitReviewRequired

class CanaryComparisonAndDepthRateTests(unittest.TestCase):
 def test_decoded_operator_segment_is_plain_text(self):
  _,values=source_segments({'content_html':'<p>&gt; <a href="https://example.edu/source">۵۵</a> درصد</p>','title':'عنوان','excerpt':'خلاصه','faq':[]})
  self.assertEqual(plain_citations(values[0]),('> ',[]))
  self.assertEqual(normalize_batch({'translations':[{'id':0,'text':'> '}]},[{'id':0,'text':values[0]}]),[{'id':0,'text':'> '}])
 def test_comparison_preserved_with_numbers(self):
  self.assertEqual(normalize_batch({'translations':[{'id':0,'text':'soil < 55 percent'}]},[{'id':0,'text':'خاک < ۵۵ درصد'}])[0]['text'],'soil < 55 percent')
 def test_comparison_cannot_be_reversed_or_removed(self):
  for value in ['soil > 55 percent','soil 55 percent']:
   with self.assertRaisesRegex(ValueError,'comparison'):normalize_batch({'translations':[{'id':0,'text':value}]},[{'id':0,'text':'خاک < ۵۵ درصد'}])
 def test_markup_and_encoded_markup_still_rejected(self):
  for value in ['<script>alert(1)</script>','&lt;script&gt;alert(1)&lt;/script&gt;','<img src=x>','</p>']:
   with self.assertRaises(ValueError):plain_citations(value)
 def test_render_escapes_comparison_instead_of_creating_markup(self):
  a={'content_html':'<p>&gt; مرز</p>','title':'عنوان','excerpt':'خلاصه','faq':[{'question':'پرسش','answer':'پاسخ'}]*3}
  _,values=source_segments(a);raw={'translations':[{'id':i,'text':('> ' if '>'in v else '')+'valid English agricultural source text '*5}for i,v in enumerate(values)]}
  result=render_translation(a,raw,'en-US');self.assertIn('&gt;',result['content_html']);self.assertNotIn('<script',result['content_html'])
 def test_daily_inches_convert_as_rate_not_length(self):self.assertEqual(text('۰٫۳۰ اینچ/روز','fa-IR'),'7.62 mm/day')
 def test_daily_inches_in_english_keep_metric_parenthesis(self):self.assertEqual(text('0.30 inch/day','en-US'),'0.3 in/day (7.62 mm/day)')
 def test_metric_daily_rate_supported(self):self.assertEqual(text('10 mm/day','en-US'),'0.394 in/day (10 mm/day)')
 def test_daily_depth_range(self):self.assertEqual(text('0.10–0.30 inch/day','fa-IR'),'2.54–7.62 mm/day')
 def test_unsupported_rate_stays_blocked(self):
  for value in ['10 mm/hour','5 kg/day','5 °F/day']:
   with self.assertRaises(UnitReviewRequired):text(value,'fa-IR')
 def test_daily_rate_html_retains_url_and_uncertainty(self):
  s='<p>حدود <a href="https://example.edu/0.30inch/day">۰٫۳۰ اینچ/روز</a></p>'
  self.assertEqual(content(s,'fa-IR'),'<p>حدود <a href="https://example.edu/0.30inch/day">7.62 mm/day</a></p>')

 def test_diagnostic_does_not_store_source_or_exception_text(self):
  from automation.agri_v2.failure_diagnostics import failure_details
  self.assertEqual(failure_details(UnitReviewRequired('secret detail')),{'kind':'validation','category':'display_unit_review_required'})
  self.assertEqual(failure_details(ValueError('Unsafe markup in plain text field')),{'kind':'validation','category':'translation_plain_text_markup_invalid'})
