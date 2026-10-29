import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import knowledge_policy as k,editorial_structure as e,role_skills,pipeline,quality_index,regional_sources,scoped_research
from tests.agri_v2 import test_scoped_drafting_contract as drafting_fixtures
from tests.agri_v2.test_practical_drafting import fixture

class MixedKnowledgeTests(unittest.TestCase):
 def test_writer_can_explain_with_model_background_not_only_paraphrase(self):
  b=drafting_fixtures.ScopedDraftingContractTests().brief();before=copy.deepcopy(b);request=json.loads(pipeline.article_prompt({'title':'موضوع'},b));contract=request['knowledge_basis_policy']
  self.assertTrue(contract['model_background_allowed']);self.assertFalse(contract['field_trial_required_for_every_claim']);self.assertEqual(b,before)
  self.assertIn('General model background does not need a citation',request['approved_claim_contract']['requirements']);self.assertNotIn('Only approved_facts are claim authority',str(request));self.assertNotIn('without adding agronomic claims',str(request))
 def test_model_memory_not_relabelled_as_verified_source(self):
  c=k.contract();self.assertFalse(c['model_memory_is_verified_source']);self.assertFalse(c['invented_citations_allowed']);self.assertTrue(c['numeric_authority_unchanged']);self.assertFalse(c['publication_authorized'])
 def test_extraction_still_requires_actual_quotes(self):
  c=k.contract('researcher');self.assertEqual(c['mode'],'source_extraction_with_model_reasoning');self.assertFalse(c['model_background_allowed']);self.assertIn('never to manufacture an evidence ID or quotation',c['rules'])
 def test_translators_cannot_add_model_knowledge(self):
  for role in ('translator','translation-reviewer'):
   c=k.contract(role);self.assertEqual(c['mode'],'fidelity_only');self.assertFalse(c['model_background_allowed'])
 def test_sensitive_current_local_numeric_and_brand_claims_need_verification(self):
  for text in ('Local operational rates/dates','safety-critical inputs','brand performance guarantees','current verification','exact units/scope','not model memory alone'):
   self.assertIn(text,k.RULES)
 def test_all_text_roles_receive_same_version_without_an_extra_call(self):
  for role in ('researcher','persian-writer','evidence-reviewer','translator','translation-reviewer'):
   payload=json.loads(role_skills.enrich({'task':'fixture'},role));self.assertEqual(payload['knowledge_basis_policy']['version'],k.VERSION)
 def test_regional_and_quality_review_do_not_require_field_trials_for_every_sentence(self):
  c=regional_sources.review_contract('fa-IR')['knowledge_basis_policy'];self.assertEqual(c['mode'],'independent_mixed_knowledge_audit');self.assertFalse(c['field_trial_required_for_every_claim']);self.assertIn(k.RULES,quality_index.task());self.assertIn(e.RULES,quality_index.task())
 def test_new_numbers_and_unsafe_links_still_fail_real_normalizer(self):
  from automation.agri_v2 import practical_drafting
  t,b,raw=fixture()
  for suffix in ('<p>عدد ساختگی 9999</p>','<a href="https://unapproved.example/">منبع ساختگی</a>'):
   value=copy.deepcopy(raw);value['content_html']+=suffix
   with self.assertRaises(ValueError):practical_drafting.normalize(value,t,b)
 def test_final_review_gets_mixed_policy_even_without_role_wrapper(self):
  t,b,raw=fixture();b['source_scope_limitations']='Fixture limitations, not production evidence.';c=Mock();c.text.return_value={}
  with tempfile.TemporaryDirectory() as d,patch.object(scoped_research,'save_article_review',return_value={}):
   scoped_research.review_article(t,raw,b,Path(d),c)
   request=json.loads(c.text.call_args.args[0]);self.assertEqual(request['knowledge_basis_policy']['version'],k.VERSION);self.assertEqual(request['editorial_structure_contract']['version'],e.VERSION);self.assertEqual(c.text.call_count,1)
 def test_direct_writer_gets_structure_and_knowledge_without_changing_schema(self):
  from automation.agri_v2 import practical_drafting
  t,b,raw=fixture();c=Mock();c.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   practical_drafting.generate(c,t,b,Path(d))
   record=json.loads((Path(d)/'practical-text-contract.json').read_text());self.assertEqual(record['knowledge_basis_policy_version'],k.VERSION);self.assertEqual(record['editorial_structure_version'],e.VERSION);self.assertTrue(record['model_general_background_permitted'])
  request=json.loads(c.text.call_args.args[0]);self.assertEqual(request['knowledge_basis_policy']['version'],k.VERSION);self.assertEqual(request['editorial_structure_contract']['version'],e.VERSION);self.assertEqual(request['response_contract']['required_fields'],['content_html','excerpt','faq']);self.assertEqual(c.text.call_count,1)
 def test_example_is_structure_not_factual_authority_or_fixed_template(self):
  c=e.contract();self.assertFalse(c['example_is_factual_evidence']);self.assertFalse(c['fixed_section_count']);self.assertTrue(c['theme_owns_navigation']);self.assertTrue(c['renderer_owns_sources_and_faq']);self.assertIn('Do not pad',c['rules']);self.assertIn('not critical failures',c['rules'])
 def test_no_retroactive_rewrite_of_briefs_sources_or_gates(self):
  b=drafting_fixtures.ScopedDraftingContractTests().brief();before=copy.deepcopy(b);pipeline.article_prompt({'title':'موضوع'},b);self.assertEqual(b,before);self.assertEqual(json.loads(pipeline.article_prompt({'title':'موضوع'},b))['approved_claim_contract']['numeric_tokens_allowed_exactly'],['3633'])
