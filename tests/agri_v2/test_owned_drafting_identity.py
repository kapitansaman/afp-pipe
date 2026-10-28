import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import practical_drafting as p
from automation.agri_v2.failure_diagnostics import failure_details
from automation.agri_v2.queue import load_json
from automation.agri_v2.pipeline import digest
from tests.agri_v2 import test_practical_drafting as fixtures

class OwnedDraftingIdentityTests(unittest.TestCase):
 def test_binding_uses_queue_identity_and_never_rewrites_raw_prose_or_topic(self):
  t,b,r=fixtures.fixture();r.update(title='سب.light',topic_id='another-topic',family_id='family-99',slug='wrong');raw=copy.deepcopy(r);topic=copy.deepcopy(t)
  bound,report=p.bind_generated_identity(r,t)
  self.assertEqual(r,raw);self.assertEqual(t,topic);self.assertEqual(bound['title'],t['title']);self.assertEqual(bound['content_html'],r['content_html']);self.assertEqual(bound['faq'],r['faq']);self.assertNotIn('topic_id',bound);self.assertNotIn('family_id',bound);self.assertNotIn('slug',bound);self.assertFalse(report['body_semantically_approved']);self.assertFalse(report['claims_added_by_identity_binding']);self.assertEqual(report['raw_sha256'],digest(raw))
 def test_wrapper_is_unambiguous_and_legacy_normalizer_remains_strict(self):
  t,b,r=fixtures.fixture();r['title']='wrong';bound,report=p.bind_generated_identity({'result':r},t);self.assertEqual(bound['result']['title'],t['title'])
  with self.assertRaisesRegex(ValueError,'canonical intent'):p.normalize(r,t,b)
  with self.assertRaisesRegex(ValueError,'Ambiguous'):p.bind_generated_identity(dict(r,article=r),t)
 def test_generation_preserves_raw_evidence_and_owns_only_identity(self):
  t,b,r=fixtures.fixture();r['title']='سب.light';c=Mock();c.text.return_value=r
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);a=p.generate(c,t,b,folder);self.assertEqual(a['title'],t['title']);self.assertEqual(load_json(folder/'practical-text-candidate.json'),r);self.assertEqual(load_json(folder/'practical-text-normalization.json')['raw_sha256'],digest(r));contract=load_json(folder/'practical-text-contract.json');self.assertEqual(contract['generated_fields'],['content_html','excerpt','faq']);self.assertEqual(contract['identity_contract_version'],2);self.assertTrue(contract['final_evidence_audit_required']);c.text.assert_called_once();self.assertEqual(c.text.call_args.kwargs['attempts'],1);self.assertIn('ONLY content_html, excerpt and faq',json.loads(c.text.call_args.args[0])['task'])
 def test_new_contract_does_not_approve_unsafe_or_unsupported_body(self):
  t,b,r=fixtures.fixture()
  for suffix in ['<script>alert(1)</script>','<p>عدد ساختگی 9999</p>','<p>متن 在经过</p>']:
   bad=copy.deepcopy(r);bad['title']='wrong';bad['content_html']+=suffix;c=Mock();c.text.return_value=bad
   with tempfile.TemporaryDirectory() as td:
    with self.assertRaises(ValueError):p.generate(c,t,b,Path(td))
    self.assertEqual(load_json(Path(td)/'practical-text-candidate.json'),bad);self.assertFalse((Path(td)/'practical-text-normalization.json').exists());c.text.assert_called_once()
 def test_titleless_model_output_supported_without_claiming_review(self):
  t,b,r=fixtures.fixture();r.pop('title');bound,report=p.bind_generated_identity(r,t);self.assertEqual(bound['title'],t['title']);self.assertEqual(report['model_identity_fields_ignored'],[]);self.assertFalse(report['body_semantically_approved'])
 def test_missing_queue_title_rejected_before_binding(self):
  t,b,r=fixtures.fixture()
  for title in (None,'','   '):
   with self.assertRaisesRegex(ValueError,'Canonical queue title required'):p.bind_generated_identity(r,dict(t,title=title))
 def test_exact_allowlisted_diagnostic_never_persists_exception_text(self):
  self.assertEqual(failure_details(ValueError('Generated title changed canonical intent')),{'kind':'validation','category':'canonical_title_mismatch'})
  self.assertEqual(failure_details(ValueError('Ambiguous or missing article object'))['category'],'article_object_ambiguous_or_missing')
  self.assertEqual(failure_details(ValueError('PRIVATE API credential')),{'kind':'validation','category':'unspecified'})
