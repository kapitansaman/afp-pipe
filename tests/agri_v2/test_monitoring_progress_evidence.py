import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import family_lifecycle as f,web_source_repair as w
from automation.agri_v2.failure_diagnostics import failure_details,SOURCE_REPAIR_CODES
from automation.agri_v2.model_source_repair import RepairBlocked
from automation.agri_v2.queue import load_json,atomic_json
from tests.agri_v2 import test_family_lifecycle as fixtures,test_source_coverage_cache as coverage_fixtures

class MonitoringProgressEvidenceTests(unittest.TestCase):
 def test_image_deferral_reports_prior_successful_steps_not_only_image_steps(self):
  with tempfile.TemporaryDirectory() as td:
   data,out,t,env,health=fixtures.FamilyLifecycleTests().setup(td);health['eligible_image_slots']=['AGNES_API_KEY4'];stages=iter([('text',None),('images',None)])
   atomic_json(out/'new'/t['id']/'article.json',{'content_html':'fixture only'})
   with patch.object(f,'next_stage',side_effect=lambda *_:next(stages)),patch.object(f,'run_stage',return_value={'written':True}),patch('automation.agri_v2.image_workflow.advance',return_value={'status':'images_deferred','steps':[{'stage':'image-1','status':'stage_deferred'}],'roles':[]}):
    result=f.worker(t,health,data,out,env,lambda *a,**kw:Mock())
   self.assertEqual([s['stage'] for s in result['steps']],['text','image-1']);self.assertEqual(result['status'],'images_deferred');self.assertEqual(result['published_posts'],0)
 def test_source_codes_are_allowlisted_only_for_exact_validator_type(self):
  for code in SOURCE_REPAIR_CODES:
   self.assertEqual(failure_details(RepairBlocked(code)),{'kind':'validation','category':code})
   self.assertEqual(failure_details(ValueError(code))['category'],'unspecified')
  self.assertEqual(failure_details(RepairBlocked('secret provider response'))['category'],'unspecified')
 def test_invalid_coverage_response_retained_but_never_cached_or_approved(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev,docs=coverage_fixtures.SourceCoverageCacheTests().setup(td);client=Mock();client.text.return_value={'topic_id':t['id'],'invalid':'fixture response'};work=ev/'real-search'
   with self.assertRaises(RepairBlocked):w.cached_coverage(t,h.plan(t),docs,client,1,work)
   paths=list((work/'coverage-responses').glob('*/*.json'));self.assertEqual(len(paths),1);row=load_json(paths[0]);self.assertEqual(row['response'],client.text.return_value);self.assertFalse(row['scientific_acceptance']);self.assertFalse(row['publication_authorized']);self.assertEqual(row['response_sha256'],w.coverage_fingerprint(row['response']));self.assertFalse(list((work/'coverage-cache').glob('*.json')))
 def test_transport_unknown_never_creates_fake_coverage_response_or_cache(self):
  from automation.agri_v2.client import TextProviderError
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev,docs=coverage_fixtures.SourceCoverageCacheTests().setup(td);client=Mock();client.text.side_effect=TextProviderError(None,'text_transport_uncertain');work=ev/'real-search'
   with self.assertRaises(TextProviderError):w.cached_coverage(t,h.plan(t),docs,client,1,work)
   self.assertFalse(list((work/'coverage-responses').glob('*/*.json')));self.assertFalse(list((work/'coverage-cache').glob('*.json')))
 def test_distinct_invalid_responses_preserved_separately_without_new_authority(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev,docs=coverage_fixtures.SourceCoverageCacheTests().setup(td);client=Mock();work=ev/'real-search'
   for value in ({'invalid':'one'},{'invalid':'two'}):
    client.text.return_value=value
    with self.assertRaises(RepairBlocked):w.cached_coverage(t,h.plan(t),docs,client,1,work)
   self.assertEqual(len(list((work/'coverage-responses').glob('*/*.json'))),2);self.assertFalse(list((work/'coverage-cache').glob('*.json')))
