import copy,json,unittest
from automation.agri_v2 import grounded_drafting as g
class GroundedDraftingTests(unittest.TestCase):
 def setup(self):
  topic={'title':'عنوان دقیق'};brief={'review_mode':'automated_scoped_evidence_review_v1','sources':[{'url':'https://extension.example.edu/trial','excerpt':'UNAPPROVED 9999'}],'approved_facts':[{'fact_id':'f0','claim':'مشاهده محدود','conditions':'شرایط همان آزمایش','source_url':'https://extension.example.edu/trial'}]};value={'sections':[{'heading':'بخش مفید '+str(i),'paragraphs':[{'text':('واژه معتبر در محدوده مشاهده منبع '*12)+str(i)+' '+str(j),'fact_ids':['f0']} for j in range(2)]} for i in range(4)],'excerpt':'این خلاصه مربوط به همان مشاهده محدود منبع است.','faq':[{'question':'پرسش مرتبط با موضوع چیست؟','answer':'این پاسخ صرفاً همان مشاهده منبع و محدودیت آن را توضیح می‌دهد.','fact_ids':['f0']} for _ in range(3)]};return topic,brief,value
 def test_renderer_uses_exact_owned_source_links_and_canonical_title(self):
  t,b,v=self.setup();r=g.render(v,t,b);self.assertEqual(r['title'],t['title']);self.assertEqual(r['content_html'].count('<p>'),8);self.assertIn('<table>',r['content_html']);self.assertIn('href="https://extension.example.edu/trial"',r['content_html']);self.assertNotIn('9999',r['content_html']);self.assertEqual(len(r['faq']),3)
 def test_unknown_fact_cannot_acquire_a_citation(self):
  t,b,v=self.setup();v['sections'][0]['paragraphs'][0]['fact_ids']=['other-family-fact']
  with self.assertRaises(ValueError):g.render(v,t,b)
 def test_short_or_duplicate_paragraph_is_not_padded_or_approved(self):
  for duplicate in (False,True):
   t,b,v=self.setup();v['sections'][0]['paragraphs'][1]['text']=v['sections'][0]['paragraphs'][0]['text'] if duplicate else 'خیلی کوتاه'
   with self.assertRaises(ValueError):g.render(v,t,b)
 def test_raw_source_tables_are_not_given_to_writer(self):
  t,b,v=self.setup();p=g.prompt(t,b);self.assertNotIn('UNAPPROVED',p);self.assertNotIn('9999',p)
 def test_html_in_model_prose_is_not_a_link_bypass(self):
  t,b,v=self.setup();v['sections'][0]['paragraphs'][0]['text']='<a href="https://evil.example">bad</a>'
  with self.assertRaises(ValueError):g.render(v,t,b)
 def test_unrelated_cjk_rejected_without_banning_grounded_english_units(self):
  t,b,v=self.setup();v['sections'][0]['paragraphs'][0]['text']+=' 在经过'
  with self.assertRaisesRegex(ValueError,'CJK'):g.render(v,t,b)
  t,b,v=self.setup();v['sections'][0]['paragraphs'][0]['text']+=' 40°F carrot';g.render(v,t,b)
 def test_retry_feedback_preserves_raw_and_never_reuses_rejected_prose(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import Mock
  from automation.agri_v2.queue import atomic_json,load_json
  t,b,v=self.setup();old=copy.deepcopy(v);old['sections'][0]['paragraphs'][0]['text']='واژه '*49+'在经过'
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);p=folder/'lifecycle/text/rejected/1/grounded-text-candidate.json';atomic_json(p,old);original=p.read_bytes();c=Mock();c.text.return_value=v
   g.generate(c,t,b,folder);req=json.loads(c.text.call_args.args[0]);issues=req['prior_rejection_diagnostics'];self.assertTrue(any(x['issue']=='unrelated_CJK_script' for x in issues));self.assertEqual(p.read_bytes(),original);self.assertEqual(load_json(folder/'grounded-text-candidate.json'),v)
 def test_provider_schema_matches_renderer_and_approved_fact_ids(self):
  import re
  t,b,v=self.setup();schema=g.output_schema(b);self.assertEqual(set(schema['required']),{'sections','excerpt','faq'});self.assertFalse(schema['additionalProperties']);section=schema['properties']['sections'];self.assertEqual((section['minItems'],section['maxItems']),(4,4));paragraph=section['items']['properties']['paragraphs'];self.assertEqual((paragraph['minItems'],paragraph['maxItems']),(2,2));self.assertEqual(paragraph['items']['properties']['fact_ids']['items']['enum'],['f0']);pattern=paragraph['items']['properties']['text']['pattern'];self.assertIsNone(re.fullmatch(pattern,' '.join(['واژه']*49)));self.assertIsNotNone(re.fullmatch(pattern,' '.join(['واژه']*50)));self.assertIsNotNone(re.fullmatch(pattern,' '.join(['واژه']*160)));self.assertIsNone(re.fullmatch(pattern,' '.join(['واژه']*161)))
 def test_wrapped_shape_rejected_and_nested_errors_reported_not_accepted(self):
  t,b,v=self.setup();v.pop('excerpt');v['sections'][0]['paragraphs'][0]['text']=' '.join(['واژه']*47);wrapped={'content':'rejected duplicate prose','schema':v};issues=g.rejection_diagnostics(wrapped);self.assertTrue(any(r['issue']=='wrong_top_level_fields' for r in issues));self.assertTrue(any(r['issue']=='excerpt_missing' for r in issues));self.assertTrue(any(r.get('word_count')==47 for r in issues))
  with self.assertRaisesRegex(ValueError,'Structured grounded article required'):g.render(wrapped,t,b)
 def test_generate_requests_provider_schema_once_and_no_fallback_on_rejection(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import Mock
  from automation.agri_v2.queue import load_json
  t,b,v=self.setup();c=Mock();c.text.side_effect=ValueError('provider schema rejected')
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td)
   with self.assertRaisesRegex(ValueError,'provider schema rejected'):g.generate(c,t,b,folder)
   self.assertEqual(c.text.call_count,1);self.assertEqual(c.text.call_args.kwargs['response_schema'],g.output_schema(b));self.assertFalse(load_json(folder/'grounded-text-request-contract.json')['silent_fallback']);self.assertFalse((folder/'article.json').exists())
