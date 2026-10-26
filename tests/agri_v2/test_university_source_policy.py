import copy,unittest
from unittest.mock import Mock
from automation.agri_v2 import source_policy as p,research,source_scout,scoped_research as s,scoped_review_v2 as rv
from automation.agri_v2.pipeline import check_brief
from tests.agri_v2 import test_scoped_research as fixtures
from tests.agri_v2.test_source_scout import doc,decision,U

class UniversitySourcePolicyTests(unittest.TestCase):
 def fixture(self):
  helper=fixtures.ScopedResearchTests();t,v,d=helper.fixture();d=d[:1]
  for f in v['facts']:f['evidence_id']='d0-e0'
  facts=s.validate_candidate(t,v,d);r=helper.review(facts)
  r.update(source_policy_version=p.VERSION,source_policy_satisfied=True,independent_sources=False)
  return t,v,d,facts,r
 def test_single_university_allowed_but_single_government_not_allowed(self):
  self.assertTrue(p.assess([{'url':U}],research.source_host)['single_university_exception'])
  self.assertFalse(p.assess([{'url':'https://usda.gov/source'}],research.source_host)['satisfied'])
  self.assertTrue(p.assess([{'url':'https://usda.gov/a'},{'url':'https://noaa.gov/b'}],research.source_host)['satisfied'])
 def test_fake_university_and_unsafe_urls_cannot_use_exception(self):
  for url in ['https://good.edu.evil.org/a','https://university.example/a','http://one.edu/a','https://user@one.edu/a']:
   with self.subTest(url=url),self.assertRaises(ValueError):p.assess([{'url':url}],research.source_host)
 def test_single_selected_university_is_not_publication_authorization(self):
  c=Mock();c.text.return_value=decision(['s0']);docs,result=source_scout.select({'id':'x'},[],[doc(U)],c,research.source_host)
  self.assertEqual(len(docs),1);self.assertFalse(p.assess(docs,research.source_host)['publication_authorized'])
 def test_single_government_source_stops_before_model_call(self):
  c=Mock()
  with self.assertRaises(source_scout.ScoutBlocked):source_scout.select({'id':'x'},[],[doc('https://usda.gov/a')],c,research.source_host)
  c.text.assert_not_called()
 def test_university_scope_mismatch_still_rejected(self):
  c=Mock();c.text.return_value=decision(['s0'],match=False)
  with self.assertRaisesRegex(source_scout.ScoutBlocked,'scope'):source_scout.select({'id':'x'},[],[doc(U)],c,research.source_host)
 def test_single_scoped_source_with_honest_review_passes_final_brief_gate(self):
  t,v,d,facts,r=self.fixture();_,o=fixtures.ScopedResearchTests().overlap(t)
  b=s.build_brief(t,v,d,r,o,{'source_generated_at':d[0]['fetched_at'],'records':[]})
  check_brief(t,b);self.assertTrue(b['source_policy']['single_university_exception']);self.assertIn(p.DISCLOSURE,b['source_scope_limitations']);self.assertFalse(b['scoped_review']['independent_sources'])
 def test_single_source_may_not_claim_independent_corroboration(self):
  t,v,d,facts,r=self.fixture();r['independent_sources']=True
  with self.assertRaisesRegex(s.EvidenceBlocked,'corroboration'):s.validate_review(r,facts)
 def test_historical_review_not_relabelled_or_approved_under_new_policy(self):
  t,v,d,facts,r=self.fixture();r.pop('source_policy_version');r.pop('source_policy_satisfied');r['independent_sources']=True
  with self.assertRaises(s.EvidenceBlocked):s.validate_review(r,facts)
 def test_new_policy_does_not_waive_any_substantive_flag(self):
  t,v,d,facts,r=self.fixture()
  for flag in [k for k in rv.FLAGS if k!='independent_sources']+['source_policy_satisfied']:
   changed=copy.deepcopy(r);changed[flag]=False
   with self.subTest(flag=flag),self.assertRaises(s.EvidenceBlocked):s.validate_review(changed,facts)
 def test_detailed_review_handles_single_source_honestly_without_false_rejection(self):
  t,v,d,facts,r=self.fixture();r.update(decision='pass',rejection_reasons=[])
  for row,f in zip(r['fact_checks'],facts):row.update(reason='The actual source quote retains the exact crop, units and geographic limits.',evidence_quote=f['evidence_quote'][:90])
  rv.validate(r,facts);s.validate_review(r,facts)
  r['all_claims_supported']=False
  with self.assertRaises(s.EvidenceBlocked):rv.validate(r,facts)
 def test_numeric_invention_and_university_domain_swap_still_blocked(self):
  t,v,d,facts,r=self.fixture();v['facts'][0]['claim']='در این منبع عملکرد 9999 کیلوگرم گزارش شده است.'
  with self.assertRaises(s.EvidenceBlocked):s.validate_candidate(t,v,d)
  t,v,d,facts,r=self.fixture();d[0]['url']='https://usda.gov/beans'
  with self.assertRaisesRegex(s.EvidenceBlocked,'independent'):s.validate_candidate(t,v,d)
 def test_unknown_policy_fails_closed(self):
  t,v,d,facts,r=self.fixture();r['source_policy_version']='invented-policy'
  with self.assertRaises(s.EvidenceBlocked):s.validate_review(r,facts)
 def test_prompt_never_requires_fabricating_independence(self):
  self.assertIn('independent_sources:false',rv.task(source_policy=True));self.assertIn('source_policy_satisfied',rv.task(source_policy=True))

 def test_qualitative_single_university_round_trip_and_disclosure(self):
  from tests.agri_v2.test_research import fixtures,TOPIC
  docs,candidate,review,inventory=fixtures();docs=docs[:1]
  for f in candidate['facts']:f['source_url']=docs[0]['url']
  brief=research.build_brief(TOPIC,docs,candidate,review,inventory)
  check_brief(TOPIC,brief);self.assertIn(p.DISCLOSURE,brief['source_scope_limitations'])
 def test_unused_university_source_cannot_unlock_government_only_claims(self):
  from tests.agri_v2.test_research import fixtures,TOPIC
  docs,candidate,review,inventory=fixtures();docs=docs[:1]
  for f in candidate['facts']:f['source_url']=docs[0]['url']
  brief=research.build_brief(TOPIC,docs,candidate,review,inventory)
  brief['sources'].append(dict(brief['sources'][0]))
  brief['sources'][0]['url']='https://usda.gov/beans'
  for f in brief['approved_facts']:f['source_url']='https://usda.gov/beans'
  with self.assertRaises(ValueError):check_brief(TOPIC,brief)
