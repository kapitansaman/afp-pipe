import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from tests.agri_v2 import test_practical_drafting as fixtures
from automation.agri_v2 import practical_drafting as d,writer_retry_feedback as w
from automation.agri_v2.failure_diagnostics import failure_details
from automation.agri_v2.queue import atomic_json
class WriterFAQContractTests(unittest.TestCase):
 def test_response_contract_is_explicit_and_single_existing_attempt(self):
  t,b,raw=fixtures.fixture();client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as td:
   d.generate(client,t,b,Path(td));request=json.loads(client.text.call_args.args[0]);contract=request['response_contract'];self.assertEqual(contract['required_fields'],['content_html','excerpt','faq']);self.assertEqual(contract['faq']['exact_items'],3);self.assertFalse(contract['immutable_identity_fields_generated']);client.text.assert_called_once();self.assertEqual(client.text.call_args.kwargs['attempts'],1);self.assertEqual(client.text.call_args.kwargs['max_tokens'],14000)
 def test_missing_faq_never_synthesized_or_written_as_approved_article(self):
  t,b,raw=fixtures.fixture();raw.pop('faq');before=copy.deepcopy(raw);client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   with self.assertRaisesRegex(ValueError,'Exactly three reviewed FAQs'):d.generate(client,t,b,p)
   self.assertEqual(raw,before);self.assertFalse((p/'article.json').exists());self.assertFalse((p/'practical-text-normalization.json').exists())
 def test_structural_failures_have_safe_specific_diagnostics(self):
  t,b,raw=fixtures.fixture()
  for value,category in (([], 'article_faq_count_invalid'),(['x']*3,'article_faq_entry_schema_invalid'),([{'question':'Q','answer':None}]*3,'article_faq_fields_incomplete')):
   candidate=copy.deepcopy(raw);candidate['faq']=value
   try:d.normalize(candidate,t,b)
   except Exception as exc:self.assertEqual(failure_details(exc)['category'],category)
   else:self.fail('Invalid FAQ was accepted')
 def test_new_diagnostic_can_guide_authorized_next_attempt_without_changing_state(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);state=p/'lifecycle/text/state.json';atomic_json(state,{'attempts':2,'history':[{'status':'failed','failure':{'category':'article_faq_count_invalid'}}]});before=state.read_bytes();r=w.feedback(p);self.assertEqual(len(r['rejections']),1);self.assertFalse(r['scientific_approval']);self.assertFalse(r['attempt_reset_authorized']);self.assertEqual(before,state.read_bytes())
