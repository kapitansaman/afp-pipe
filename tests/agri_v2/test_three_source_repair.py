import json,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import three_source_trial as t,three_source_repair as repair,operation_request as op,family_lifecycle as f
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json,get_topic
from automation.agri_v2.extraction_feedback import diagnose
from automation.agri_v2.source_discovery import entries_for,ranked_seed_urls
BASE=load_json(Path(__file__).parent/'fixtures/three-source-repair-baseline.json')
class ThreeSourceRepairTests(unittest.TestCase):
 def test_remaining_budget_not_a_new_42(self):
  r=t.expected_request(t.REPAIR_ID);op.validate_request(dict(r,code_revision='a'*40))
  self.assertEqual((r['max_total_text_calls'],r['max_image_calls'],r['max_total_model_calls'],r['max_model_calls_per_family']),(24,15,39,13))
  self.assertEqual(3+r['max_total_model_calls'],42)
  for key,val in [('max_total_model_calls',42),('max_model_calls_per_family',14),('prior_total_model_calls',0),('reset_attempts',True),('max_translations',1)]:
   with self.assertRaises(ValueError):op.validate_request(dict(r,code_revision='a'*40,**{key:val}))
 def test_actual_failed_fact_feedback_uses_literal_selected_quote(self):
  row=BASE['topics'][t.TOPICS[0]];topic=row['topic'];docs=row['files']['lifecycle-evidence/sources.json']['documents'];raw=row['files']['lifecycle-evidence/candidate-raw.json']
  r=diagnose(topic,raw,docs);self.assertFalse(r['scientific_approval']);self.assertEqual(r['candidate_error'],'number_absent_from_literal_source')
  self.assertIn('every_number_requires_unit_and_scope_binding',{x['code'] for x in r['errors']})
  first=r['errors'][0];self.assertEqual(first['literal_evidence']['id'],raw['facts'][0]['evidence_id']);self.assertNotIn('50',first['literal_evidence']['quote'])
 def test_storage_all_errors_reported_not_just_first(self):
  row=BASE['topics'][t.TOPICS[1]];r=diagnose(row['topic'],row['files']['lifecycle-evidence/candidate-raw.json'],row['files']['lifecycle-evidence/sources.json']['documents'])
  self.assertEqual({x['fact_index'] for x in r['errors']},{1,3,5})
 def test_sensor_method_lead_ranks_ahead_of_storage(self):
  topic=get_topic('new',t.TOPICS[2]);rows=entries_for(topic,DATA,'scoped-source-catalog.json');urls=ranked_seed_urls(rows)
  self.assertEqual(urls[0],'https://extension.umn.edu/irrigation/soil-moisture-sensors-irrigation-scheduling')
  self.assertIn('NOT a pinto-specific fixed rooting depth',rows[0]['scope'])
 def fixture(self,d):
  data=Path(d)/'data';out=Path(d)/'out';shutil.copytree(DATA,data)
  for ident,row in BASE['topics'].items():
   for path,value in row['files'].items():atomic_json(out/'new'/ident/path,value)
  atomic_json(out/'parallel/operations'/t.ID/'prepare.json',BASE['prepare']);atomic_json(out/'parallel/operations'/t.ID/'model-calls.json',BASE['model_calls']);atomic_json(out/'parallel/families/assignments.json',{})
  return data,out
 def test_next_attempt_preserves_history_raw_and_feedback(self):
  with tempfile.TemporaryDirectory() as d:
   data,out=self.fixture(d);topic=get_topic('new',t.TOPICS[0],data);folder=out/'new'/topic['id'];old=f.state(folder,'research_extract');raw=(folder/'lifecycle-evidence/candidate-raw.json').read_bytes()
   repair.prepare_topic(topic,data,out,'999')
   self.assertEqual(f.state(folder,'research_extract'),old);self.assertEqual((folder/'lifecycle/research_extract/rejected/1/candidate-raw.json').read_bytes(),raw)
   self.assertFalse((folder/'lifecycle-evidence/candidate-raw.json').exists());self.assertEqual(f.next_stage(topic,data,out)[0],'research_extract')
   result=f.attempt(folder,'research_extract','999',lambda:{'test_only':True});self.assertEqual(result['status'],'stage_completed');self.assertEqual(f.state(folder,'research_extract')['attempts'],2);self.assertEqual(f.state(folder,'research_extract')['history'][0],old['history'][0])
 def test_sensor_refresh_archives_sources_without_model_calls(self):
  with tempfile.TemporaryDirectory() as d:
   data,out=self.fixture(d);topic=get_topic('new',t.TOPICS[2],data);folder=out/'new'/topic['id'];old=(folder/'lifecycle-evidence/sources.json').read_bytes()
   with patch('automation.agri_v2.scoped_research.stage',return_value={'fixture':'sources only'}) as stage:repair.prepare_topic(topic,data,out,'999')
   self.assertEqual(stage.call_args.args[2],None);self.assertEqual(f.state(folder,'research_sources')['attempts'],2);self.assertEqual((folder/'lifecycle/research_sources/rejected/1/sources.json').read_bytes(),old)
 def test_previous_trial_is_verified_before_any_new_calls(self):
  with tempfile.TemporaryDirectory() as d:
   data,out=self.fixture(d);r=load_json(out/'parallel/operations'/t.ID/'prepare.json');r['assignment_sha256']=__import__('hashlib').sha256((out/'parallel/families/assignments.json').read_bytes()).hexdigest();atomic_json(out/'parallel/operations'/t.ID/'prepare.json',r)
   self.assertEqual(repair.verify_prior(data,out)['model_calls'],3)
   atomic_json(out/'new'/t.TOPICS[0]/'lifecycle/research_extract/state.json',{'attempts':0})
   with self.assertRaises(ValueError):repair.verify_prior(data,out)
