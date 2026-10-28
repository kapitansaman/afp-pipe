import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import research_review_contract as r,scoped_research as s
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from tests.agri_v2 import test_scoped_research as fixtures
class ResearchReviewContractTests(unittest.TestCase):
 def setup(self,td):
  h=fixtures.ScopedResearchTests();t,v,docs=h.fixture();v['research_route_version']=s.ROUTE_VERSION;facts=s.validate_candidate(t,v,docs);bundle,overlap=h.overlap(t);data=Path(td)/'data';out=Path(td)/'out';ev=out/'new'/t['id']/'lifecycle-evidence'
  atomic_json(ev/'sources.json',{'documents':docs});atomic_json(ev/'candidate.json',v);atomic_json(ev/'existing-content.json',bundle);atomic_json(ev/'overlap.json',overlap);atomic_json(data/'parallel-inventory.json',{'source_generated_at':utcnow(),'records':[]});return h,t,v,docs,facts,data,out,ev
 def test_exact_route_fields_in_both_explicit_schema_and_legacy_task(self):
  with tempfile.TemporaryDirectory() as td:
   h,t,v,docs,facts,data,out,ev=self.setup(td);client=Mock();client.text.return_value=dict(h.review(facts),research_route_version=s.ROUTE_VERSION,route_requirements_met=True);s.stage(t,'research_review',client,data,out);request=json.loads(client.text.call_args.args[0]);contract=request['response_contract'];self.assertIn('route_requirements_met',contract['required_root_fields']);self.assertIn('route_requirements_met:boolean',request['task']);self.assertEqual(contract['exact_fact_ids'],[f['fact_id'] for f in facts]);client.text.assert_called_once();self.assertEqual(client.text.call_args.kwargs['attempts'],1);self.assertEqual(client.text.call_args.kwargs['max_tokens'],10000);self.assertEqual(client.text.call_args.kwargs['timeout'],180)
 def test_omitted_route_fields_are_not_invented_and_raw_review_is_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   h,t,v,docs,facts,data,out,ev=self.setup(td);raw=h.review(facts);before=copy.deepcopy(raw);client=Mock();client.text.return_value=raw
   with self.assertRaises(s.EvidenceBlocked):s.stage(t,'research_review',client,data,out)
   self.assertEqual(load_json(ev/'review-raw.json'),before);self.assertEqual(raw,before);self.assertFalse((data/'briefs'/(t['id']+'.json')).exists())
 def test_honest_negative_route_is_still_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   h,t,v,docs,facts,data,out,ev=self.setup(td);client=Mock();client.text.return_value=dict(h.review(facts),research_route_version=s.ROUTE_VERSION,route_requirements_met=False)
   with self.assertRaises(s.EvidenceBlocked):s.stage(t,'research_review',client,data,out)
   self.assertFalse(load_json(ev/'review-raw.json')['route_requirements_met']);self.assertFalse((data/'briefs'/(t['id']+'.json')).exists())
 def test_detailed_contract_requires_negative_reasons_and_original_fact_ids(self):
  candidate={'review_schema_version':2,'research_route_version':s.ROUTE_VERSION};contract=r.contract(candidate,[{'fact_id':'f0'},{'fact_id':'f0-conversion-0'}]);self.assertIn('decision',contract['required_root_fields']);self.assertIn('rejection_reasons',contract['required_root_fields']);self.assertTrue(contract['missing_flag_is_not_approval']);self.assertEqual(contract['exact_fact_ids'],['f0','f0-conversion-0'])
 def test_safe_pool_categories_do_not_expose_arbitrary_exception_text(self):
  from automation.agri_v2.failure_diagnostics import failure_details
  from automation.agri_v2.parallel_pool import PoolDeferred
  self.assertEqual(failure_details(PoolDeferred('Eligible credentials busy; defer without provider call'))['category'],'pool_credentials_busy');self.assertEqual(failure_details(PoolDeferred('Temporary source fetch failure; no scientific absence inferred')),{'kind':'source_fetch_deferred','category':'source_fetch_temporarily_unavailable'});self.assertNotIn('PRIVATE',json.dumps(failure_details(PoolDeferred('PRIVATE'))))
