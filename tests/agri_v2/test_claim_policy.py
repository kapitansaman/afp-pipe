import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import claim_policy as p, scoped_research as s,regional_sources as r
from automation.agri_v2 import pipeline,role_skills,research_review_contract
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.research import source_host,ResearchBlocked
from automation.agri_v2.failure_diagnostics import failure_details
from tests.agri_v2 import test_scoped_research as fixtures

class ClaimPolicyTests(unittest.TestCase):
 def fixture(self):
  t,v,d=fixtures.ScopedResearchTests().fixture();v.update(research_policy_version=p.VERSION,conflicts=[],review_schema_version=2,evidence_revision=p.VERSION)
  for f in v['facts']:
   f['claim_type']='source_observation' if f['kind']=='source_observation' else 'general_principle'
   f['study_context']={k:{'value':None,'quote':None} for k in p.CONTEXT_FIELDS}
  v['facts'][0]['study_context']['geography']={'value':'North Dakota','quote':'stated North Dakota trial'}
  return t,v,d
 def review(self,facts):
  value=fixtures.ScopedResearchTests().review(facts);value.update(research_policy_version=p.VERSION,conflicts_reviewed=True,context_checks=[])
  for f in facts:
   if f.get('kind')=='deterministic_conversion':continue
   value['context_checks'].append({'fact_id':f['fact_id'],'claim_type':f['claim_type'],'context_supported':True,'publisher_expertise_supported':True,'reason':'The actual passage supports this bounded claim and the reported conditions.'})
  value.update(decision='pass',rejection_reasons=[])
  for row,f in zip(value['fact_checks'],facts):
   row.update(reason='The actual source supports this exact scoped fact and all reported units.',evidence_quote=f['evidence_quote'][:90])
  return value
 def test_reported_context_is_bound_unknown_stays_null_and_conversion_still_exact(self):
  t,v,d=self.fixture();before=copy.deepcopy(v);facts=s.validate_candidate(t,v,d)
  self.assertEqual(v,before);self.assertEqual(facts[0]['study_context']['geography']['value'],'North Dakota');self.assertIsNone(facts[0]['study_context']['cultivar']['value']);self.assertEqual(facts[-1]['conversion']['target_value'],'2241.702')
 def test_new_brief_round_trip_revalidates_context_and_does_not_upgrade_legacy(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);_,overlap=fixtures.ScopedResearchTests().overlap(t)
  b=s.build_brief(t,v,d,self.review(facts),overlap,{'source_generated_at':d[0]['fetched_at'],'records':[]})
  self.assertEqual(b['research_policy_version'],p.VERSION);s.verify_brief(b);pipeline.check_brief(t,b)
  b['approved_facts'][0]['study_context']['geography']['value']='Iran'
  with self.assertRaises(p.PolicyBlocked):s.verify_brief(b)
 def test_numeric_observation_cannot_be_reclassified_as_a_general_principle(self):
  t,v,d=self.fixture();v['facts'][0]['claim_type']='general_principle'
  with self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
 def test_context_schema_is_complete_not_arbitrary_prose(self):
  for field in p.CONTEXT_FIELDS:
   t,v,d=self.fixture();v['facts'][0]['study_context'].pop(field)
   with self.subTest(field=field),self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
 def test_unreported_conditions_cannot_be_fabricated_or_bound_to_another_passage(self):
  for item in [{'value':'Iran','quote':'stated North Dakota trial'},{'value':'Iran','quote':'Iran trial not in source'},{'value':None,'quote':'North Dakota'},{'value':'North Dakota','quote':None}]:
   t,v,d=self.fixture();v['facts'][0]['study_context']['geography']=item
   with self.subTest(item=item),self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
 def test_unknown_version_and_unscoped_local_prescription_are_blocked(self):
  t,v,d=self.fixture();v['research_policy_version']='unknown'
  with self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
  t,v,d=self.fixture();v['facts'][0]['claim_type']='local_recommendation'
  with self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
 def test_no_conflicts_field_is_not_silently_defaulted(self):
  t,v,d=self.fixture();v.pop('conflicts')
  with self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
 def test_unresolved_conflict_does_not_require_inventing_a_cause(self):
  t,v,d=self.fixture();v['conflicts']=[{'fact_indices':[0,1],'status':'unresolved','reason':'The available passages do not establish why these observations differ.','cause_quote':None}]
  self.assertTrue(s.validate_candidate(t,v,d))
 def test_conflict_causal_explanation_requires_literal_evidence(self):
  t,v,d=self.fixture();row={'fact_indices':[0,1],'status':'explained','reason':'The text explicitly reports the relevant source-bound explanation.','cause_quote':'An invented causal explanation which does not occur in either source.'};v['conflicts']=[row]
  with self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
  row['cause_quote']='Weather, market class and harvested dry seed basis must be retained.'
  self.assertTrue(s.validate_candidate(t,v,d)) # Semantic truth still needs independent review.
 def test_conflict_indices_cannot_be_dropped_duplicated_or_silently_remapped(self):
  for ids in [[0,0],[0,99],['0',1],[True,1]]:
   t,v,d=self.fixture();v['conflicts']=[{'fact_indices':ids,'status':'unresolved','reason':'Actual differences require further source-bound examination.','cause_quote':None}]
   with self.subTest(ids=ids),self.assertRaises(p.PolicyBlocked):s.normalize_saved_candidate(t,v,d)
 def test_legacy_candidate_is_not_relabelled(self):
  t,v,d=fixtures.ScopedResearchTests().fixture();before=copy.deepcopy(v);facts=s.validate_candidate(t,v,d)
  self.assertEqual(v,before);self.assertNotIn('research_policy_version',facts[0]);s.validate_review(fixtures.ScopedResearchTests().review(facts),facts)
 def test_policy_marker_cannot_be_stripped_from_candidate(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);v.pop('research_policy_version');v['facts']=facts[:-1]
  with self.assertRaises(p.PolicyBlocked):s.validate_candidate(t,v,d)
 def test_each_new_claim_needs_independent_context_and_expertise_review(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);value=self.review(facts);s.validate_review(value,facts)
  for key in ('context_supported','publisher_expertise_supported'):
   bad=copy.deepcopy(value);bad['context_checks'][0][key]=False
   with self.subTest(key=key),self.assertRaises(p.PolicyBlocked):s.validate_review(bad,facts)
 def test_missing_conflict_review_or_false_positive_does_not_pass(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d)
  for field,bad_value in [('conflicts_reviewed',False),('research_policy_version','unknown'),('context_checks',[])]:
   value=self.review(facts);value[field]=bad_value
   with self.subTest(field=field),self.assertRaises(p.PolicyBlocked):s.validate_review(value,facts)
 def test_context_review_cannot_override_an_honest_negative(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);value=self.review(facts);value['all_claims_supported']=False
  with self.assertRaises(s.EvidenceBlocked):s.validate_review(value,facts)
 def test_new_review_response_contract_includes_context_and_specific_objections(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);contract=research_review_contract.contract(v,facts)
  self.assertIn('context_checks',contract['required_root_fields']);self.assertIn('rejection_reasons',contract['required_root_fields']);self.assertEqual(len(contract['claim_research_contract']['context_checks']),4)
 def test_writer_receives_context_but_not_new_claim_authority(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);brief={'review_mode':s.MODE,'approved_facts':facts,'sources':[{'url':d[0]['url']}],'research_policy_version':p.VERSION,'conflicts':[]}
  b=pipeline.drafting_brief(brief);self.assertEqual(b['approved_facts'][0]['study_context'],facts[0]['study_context']);self.assertEqual(b['conflicts'],[])
  contract=p.extraction_contract();self.assertIn('not additional approved prose',contract['rules'])
 def test_official_admission_includes_local_and_additional_international_namespaces(self):
  for u in ('https://province.gov.ir/agriculture','https://city.gov.uk/water','https://ministry.gov.tr/research','https://agri.gouv.fr/report','https://agri.go.jp/report'):
   self.assertTrue(source_host(u));self.assertTrue(r.credible(u))
  for u in ('https://gov.tr.evil.org/report','https://fakegov.tr/report','https://random.tr/report','https://farmer.com/report'):
   with self.assertRaises(ResearchBlocked):source_host(u)
 def test_safe_diagnostics_do_not_log_untrusted_exception_text(self):
  self.assertEqual(failure_details(p.PolicyBlocked('claim_context_not_source_bound'))['category'],'claim_context_not_source_bound');self.assertEqual(failure_details(p.PolicyBlocked('SECRET'))['category'],'unspecified')
 def test_new_extraction_contract_is_actually_sent_and_missing_version_stays_blocked(self):
  t,v,d=self.fixture()
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';ev=out/'new'/t['id']/'lifecycle-evidence';atomic_json(ev/'sources.json',{'documents':d});client=Mock();raw=copy.deepcopy(v);raw.pop('research_policy_version');client.text.return_value=raw
   with self.assertRaises(p.PolicyBlocked):s.stage(t,'research_extract',client,data,out)
   request=json.loads(client.text.call_args.args[0]);self.assertEqual(request['claim_research_contract']['version'],p.VERSION);self.assertEqual(load_json(ev/'candidate-raw.json'),raw);self.assertFalse((ev/'candidate.json').exists())
 def test_source_context_contract_runs_on_a_new_extraction_without_live_calls(self):
  t,v,d=self.fixture()
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';ev=out/'new'/t['id']/'lifecycle-evidence';atomic_json(ev/'sources.json',{'documents':d});client=Mock();client.text.return_value=v
   result=s.stage(t,'research_extract',client,data,out);self.assertEqual(result['grounded_facts'],5);self.assertEqual(load_json(ev/'candidate.json')['review_schema_version'],2);self.assertEqual(client.text.call_count,1)

class RegionalObjectionTests(unittest.TestCase):
 def fixture(self):
  a={'content_html':'<p>Observe the source-specific soil conditions.</p>','excerpt':'No universal rate is established.','faq':[{'question':'How?','answer':'Use only supported conditions.'}]};facts=[{'fact_id':'f0'}]
  v={'regional_review_schema_version':2,'applicable':True,'no_unsupported_local_prescription':True,'country_limits_retained':True,'fact_checks':[{'fact_id':'f0','supported':True}],'rejection_reasons':[]}
  return a,facts,v
 def test_three_claim_classes_are_explicit_in_regional_contract(self):
  c=r.review_contract('fa-IR')['claim_review_contract'];self.assertIn('general_principle',c['rejection_reasons']);self.assertIn('source_observation',c['rejection_reasons']);self.assertIn('local_recommendation',c['rejection_reasons'])
 def test_bound_negative_remains_negative_not_automatic_approval(self):
  a,f,v=self.fixture();v['applicable']=False;v['rejection_reasons']=[{'flag':'applicable','fact_ids':['f0'],'claim_type':'local_recommendation','article_quote':a['excerpt'],'reason':'The source does not substantiate the actual local operational instruction.'}];p.validate_regional_objections(v,a,f)
  from tests.agri_v2.test_regional_sources import RegionalSourcesTests
  helper=RegionalSourcesTests()
  with self.assertRaises(r.RegionalBlocked):r.validate_local_review(v,a,helper.brief(),[helper.doc()],'fa-IR')
 def test_negative_needs_real_current_article_quote_not_brief_or_prior_draft(self):
  a,f,v=self.fixture();v['applicable']=False
  with self.assertRaises(p.PolicyBlocked):p.validate_regional_objections(v,a,f)
  v['rejection_reasons']=[{'flag':'applicable','fact_ids':['f0'],'claim_type':'source_observation','article_quote':'A source quote absent from this current article','reason':'A real negative needs an actual sentence from the current article.'}]
  with self.assertRaises(p.PolicyBlocked):p.validate_regional_objections(v,a,f)
 def test_every_negative_flag_and_fact_needs_an_objection(self):
  a,f,v=self.fixture();v['no_unsupported_local_prescription']=False;v['fact_checks'][0]['supported']=False;v['rejection_reasons']=[{'flag':'no_unsupported_local_prescription','fact_ids':['f0'],'claim_type':'local_recommendation','article_quote':a['excerpt'],'reason':'The current article wording makes an unsupported local recommendation.'}]
  with self.assertRaises(p.PolicyBlocked):p.validate_regional_objections(v,a,f)
 def test_positive_verdict_cannot_carry_unresolved_objections(self):
  a,f,v=self.fixture();v['rejection_reasons']=[{'flag':'applicable'}]
  with self.assertRaises(p.PolicyBlocked):p.validate_regional_objections(v,a,f)
 def test_contract_reaches_every_role_not_just_researcher(self):
  with tempfile.TemporaryDirectory() as td:
   data=Path(td);(data/'role-skills').mkdir()
   for role in ('researcher','persian-writer','evidence-reviewer','translator','translation-reviewer'):
    (data/'role-skills'/(role+'.md')).write_text('Use the exact schema and source-bound evidence.')
    atomic_json(data/'regional-research-policy.json',r.POLICY)
    before=r.profile('fa-IR')
    payload=json.loads(role_skills.enrich({'task':'test'},role,data=data));self.assertEqual(payload['claim_research_policy']['version'],p.VERSION)
    self.assertIn('NOT a blanket rejection',payload['regional_policy_priority']);self.assertEqual(before,r.profile('fa-IR'))
