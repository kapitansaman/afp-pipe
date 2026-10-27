import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import family_lifecycle as f,scoped_research as s
from automation.agri_v2.queue import atomic_json,load_json
from tests.agri_v2 import test_scoped_research as fixture_s
from tests.agri_v2 import test_family_lifecycle as fixture_f

class SavedResearchRoutingTests(unittest.TestCase):
 def setup(self,root):
  d,o,old,e,h=fixture_f.FamilyLifecycleTests().setup(str(root));t,v,docs=fixture_s.ScopedResearchTests().fixture();t['family_id']='family-01';p=load_json(d/'family-lifecycle-policy.json');p['scoped_evidence_research']=True;atomic_json(d/'family-lifecycle-policy.json',p)
  ev=o/'new'/t['id']/'lifecycle-evidence';atomic_json(ev/'sources.json',{'documents':docs,'source_text_layout_version':2});atomic_json(ev/'candidate-raw.json',v)
  return d,o,t,e,h,ev,v
 def test_good_raw_is_salvaged_locally_before_any_new_extraction(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));before={p:p.read_bytes() for p in ev.glob('*.json')};self.assertEqual(f.next_stage(t,d,o),('research_validate_saved',None));self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertFalse((ev/'candidate.json').exists())
 def test_known_insufficient_raw_routes_to_original_extract_not_repeated_local_failure(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));v['answers_intent']=False;atomic_json(ev/'candidate-raw.json',v);state=f.row_path(ev.parent,'research_validate_saved');atomic_json(state,{'status':'failed','attempts':2,'failure':{'category':'saved_evidence_declares_insufficient_scope'}});before=state.read_bytes();raw=(ev/'candidate-raw.json').read_bytes()
   for _ in range(3):self.assertEqual(f.next_stage(t,d,o),('research_extract','saved_evidence_declares_insufficient_scope'))
   self.assertEqual(state.read_bytes(),before);self.assertEqual((ev/'candidate-raw.json').read_bytes(),raw);self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def test_too_few_valid_facts_never_become_approved_to_move_forward(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));v['facts']=v['facts'][:2];atomic_json(ev/'candidate-raw.json',v)
   self.assertEqual(f.next_stage(t,d,o),('research_extract','scoped_four_to_twelve_facts_required'));self.assertFalse((ev/'candidate.json').exists())
 def test_foreign_or_unreadable_raw_remains_blocked_no_model_retry(self):
  for kind in ('foreign','corrupt','bad_sources'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td))
    if kind=='foreign':v['topic_id']='agri-ffffffffffff';atomic_json(ev/'candidate-raw.json',v)
    elif kind=='corrupt':(ev/'candidate-raw.json').write_text('{invalid')
    else:atomic_json(ev/'sources.json',{'source_text_layout_version':2})
    self.assertEqual(f.next_stage(t,d,o)[0],'blocked')
 def test_original_extract_counter_and_archive_are_preserved_at_remaining_limit(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));v['answers_intent']=False;atomic_json(ev/'candidate-raw.json',v);original=(ev/'candidate-raw.json').read_bytes()
   atomic_json(f.row_path(ev.parent,'research_extract'),{'status':'failed','attempts':2,'last_run_id':'99','history':[]});local=f.row_path(ev.parent,'research_validate_saved');atomic_json(local,{'status':'failed','attempts':2,'history':[]});local_before=local.read_bytes()
   client=Mock();client.text.return_value=copy.deepcopy(v);factory=Mock(return_value=client)
   with patch.object(s,'entries_for',return_value=[]):result=f.worker(t,h,d,o,e,factory)
   self.assertEqual(result['status'],'stage_failed');self.assertEqual(result['stage'],'research_extract');self.assertEqual(f.state(ev.parent,'research_extract')['attempts'],3);self.assertEqual(local.read_bytes(),local_before);client.text.assert_called_once();self.assertEqual((ev.parent/'lifecycle/research_extract/rejected/2/candidate-raw.json').read_bytes(),original)
   e['GITHUB_RUN_ID']='124';client.text.reset_mock()
   with patch.object(s,'entries_for',return_value=[]):again=f.worker(t,h,d,o,e,factory)
   self.assertEqual(again['status'],'stage_budget_exhausted');self.assertEqual(f.state(ev.parent,'research_extract')['attempts'],3);client.text.assert_not_called();self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def test_unknown_extract_reservation_is_not_replayed_or_archived(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));v['answers_intent']=False;atomic_json(ev/'candidate-raw.json',v);raw=(ev/'candidate-raw.json').read_bytes();atomic_json(f.row_path(ev.parent,'research_extract'),{'status':'reserved','attempts':1,'last_run_id':'99','history':[]});client=Mock()
   result=f.worker(t,h,d,o,e,Mock(return_value=client));self.assertEqual(result['status'],'stage_reconciliation_required');client.text.assert_not_called();self.assertEqual((ev/'candidate-raw.json').read_bytes(),raw)
 def test_source_fetch_and_local_finalization_do_not_require_api_credentials_or_probe(self):
  for stage in ('research_sources','research_validate_saved','existing_content_audit_finalize'):
   with self.subTest(stage=stage),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h,ev,v=self.setup(Path(td));h['eligible_text_slots']=[];factory=Mock()
    with patch.object(f,'next_stage',side_effect=[(stage,None),('blocked','test_stop')]),patch.object(f,'run_stage',return_value={'new_model_calls':0}) as execute,patch('automation.agri_v2.recovery.circuit_open',return_value=True):result=f.worker(t,h,d,o,e,factory)
    factory.assert_not_called();self.assertIsNone(execute.call_args.args[2]);self.assertEqual(result['status'],'blocked')
 def test_valid_candidate_still_requires_existing_content_and_independent_review(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h,ev,v=self.setup(Path(td));atomic_json(ev/'candidate.json',v);stage,reason=f.next_stage(t,d,o);self.assertNotIn(stage,('text','publish','research_validate_saved','research_extract'));self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())

if __name__=='__main__':unittest.main()
