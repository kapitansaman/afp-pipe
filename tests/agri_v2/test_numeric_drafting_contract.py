import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import numeric_drafting_contract as n,practical_drafting as p
from automation.agri_v2.queue import load_json
from tests.agri_v2 import test_practical_drafting as fixtures

class NumericDraftingContractTests(unittest.TestCase):
 def test_scope_year_and_metric_equivalent_never_promote_to_numeric_authority(self):
  t,b,r=fixtures.fixture();b['source_scope_limitations']='Source year 2014; one inch is approximately 2.54 cm in USA, not Iran.';before=copy.deepcopy(b);c=n.contract(b)
  self.assertEqual(c['allowed_numeric_tokens_exactly'],[]);self.assertTrue(c['no_digits_authorized']);self.assertEqual(c['incidental_scope_numeric_tokens_not_authorized'],['2.54','2014']);self.assertEqual(b,before)
 def test_literals_and_conditions_match_existing_validator_without_metadata(self):
  t,b,r=fixtures.fixture();b['approved_facts'][0].update(claim='مشاهده ۲ اینچ در منطقه منبع',conditions='شرایط ۱۵ درجه');b['source_scope_limitations']='2014 metadata';self.assertEqual(n.allowed(b),{'2','15'});self.assertEqual(set(n.contract(b)['allowed_numeric_tokens_exactly']),{'2','15'})
 def test_fa_arabic_and_latin_variants_detected_in_body_excerpt_and_faq(self):
  t,b,r=fixtures.fixture();r['content_html']+='<p>≈۲٫۵۴ سانتی‌متر؛ سال ٢٠١٤</p>';r['excerpt']+=' 2.54';r['faq'][0]['answer']+=' ۲۰۱۴';before=copy.deepcopy(r);a=n.audit(r,b)
  self.assertFalse(a['lexical_numeric_contract_passed']);self.assertEqual({x['field'] for x in a['violations']},{'content_html','excerpt','faq.0.answer'});self.assertEqual(set(a['violations'][0]['unapproved_numeric_tokens']),{'2.54','2014'});self.assertEqual(r,before);self.assertFalse(a['candidate_rewritten']);self.assertFalse(a['scientific_approval'])
 def test_url_numbers_are_not_visible_quantities_or_authority(self):
  t,b,r=fixtures.fixture();r['content_html']='<p>متن <a href="https://example.edu/2014/254">منبع</a></p>';a=n.audit(r,b);self.assertTrue(a['lexical_numeric_contract_passed']);self.assertEqual(n.allowed(b),set())
 def test_declared_conversion_without_approved_fact_result_does_not_bypass_gate(self):
  t,b,r=fixtures.fixture();b['approved_facts'][0]['conversion']={'target_value':'2.54','target_unit':'cm','source_value':'1'};self.assertEqual(n.allowed(b),set());r['content_html']+='<p>2.54 cm</p>';self.assertFalse(n.audit(r,b)['lexical_numeric_contract_passed'])
 def test_actual_writer_receives_contract_and_persists_rejection_before_unchanged_gate(self):
  t,b,r=fixtures.fixture();b['source_scope_limitations']='2014 metadata 2.54 cm';r['content_html']+='<p>2.54 cm</p>';c=Mock();c.text.return_value=r
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaisesRegex(ValueError,'Unapproved numeric token'):p.generate(c,t,b,Path(td))
   request=json.loads(c.text.call_args.args[0]);self.assertEqual(request['numeric_authority_contract']['allowed_numeric_tokens_exactly'],[]);self.assertFalse(load_json(Path(td)/'practical-text-numeric-audit.json')['lexical_numeric_contract_passed']);self.assertEqual(load_json(Path(td)/'practical-text-candidate.json'),r);self.assertFalse((Path(td)/'practical-text-normalization.json').exists());c.text.assert_called_once();self.assertEqual(c.text.call_args.kwargs['attempts'],1)
 def test_qualitative_approved_words_retained_but_not_semantically_approved(self):
  t,b,r=fixtures.fixture();b['approved_facts'][0]['claim']='عمق یک اینچ در شرایط منبع مشاهده شد.';r['content_html']+='<p>عمق یک اینچ در شرایط منبع مشاهده شد.</p>';a=n.audit(r,b);self.assertTrue(a['lexical_numeric_contract_passed']);self.assertFalse(a['scientific_approval']);self.assertIn('do NOT invent quantities',n.contract(b)['requirements'])
 def test_ambiguous_article_still_rejected(self):
  t,b,r=fixtures.fixture()
  with self.assertRaisesRegex(ValueError,'Ambiguous'):n.audit(dict(r,article=r),b)
