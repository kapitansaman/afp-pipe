import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from tests.agri_v2 import test_web_source_repair as fixture
from automation.agri_v2 import web_source_repair as w,model_source_repair as r,family_lifecycle as f,research_backlog as backlog
from automation.agri_v2.queue import atomic_json,load_json
class FinalCoverageTests(unittest.TestCase):
 def setup(self,td):
  h=fixture.WebSourceRepairTests();d,o,t,e,health,ev,value=h.setup(Path(td));h.plan_stage(d,o,t,e,ev);return h,d,o,t,e,ev
 def run_stage(self,h,d,o,t,e,ev,client,fetcher=None):
  return f.attempt(ev.parent,'research_refetch','101',lambda:w.refetch(t,client,d,o,e,fetcher=h.document if fetcher is None else fetcher,search_fn=h.result),limit=1)
 def test_final_gap_preserves_original_ids_and_attempts_and_routes_backlog(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);before={p:p.read_bytes() for p in (ev/'sources.json',ev/'candidate-raw.json',f.row_path(ev.parent,'research_extract'))};c=Mock();c.text.return_value=h.verdict(t,False)
   result=self.run_stage(h,d,o,t,e,ev,c);self.assertEqual(result['status'],'stage_completed');self.assertEqual(c.text.call_count,2);self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertFalse((ev/'model-source-originals').exists());self.assertFalse((ev/'candidate.json').exists());self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
   self.assertEqual(f.next_stage(t,d,o),('blocked','bounded_search_coverage_incomplete'));proof=r.exhausted_coverage(t,ev.parent,d);self.assertFalse(proof['final_coverage_complete']);self.assertFalse(proof['scientific_acceptance']);self.assertTrue((ev/'real-search/unapproved-documents.json').exists())
   row=backlog.deferral(t,d,o);self.assertEqual(row['kind'],'bounded_source_coverage_exhausted');self.assertFalse(row['automatic_retry_authorized']);self.assertFalse(row['publication_authorized']);self.assertFalse(row['prior_attempts_reset']);self.assertIn('model-source-refetch.json',row['evidence_fingerprints'])
 def test_final_coverage_success_retains_complementary_original_documents(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);original=load_json(ev/'sources.json')['documents'];c=Mock();c.text.side_effect=[h.verdict(t,False),h.verdict(t,True)];self.run_stage(h,d,o,t,e,ev,c)
   after=load_json(ev/'sources.json')['documents'];self.assertTrue(all(d in after for d in original));self.assertTrue(load_json(ev/r.RECEIPT)['final_coverage_complete']);self.assertIsNone(r.exhausted_coverage(t,ev.parent,d));self.assertEqual(f.next_stage(t,d,o),('research_extract',None));self.assertFalse((d/'briefs'/(t['id']+'.json')).exists())
 def test_changed_original_cannot_reuse_coverage_gap_proof(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);c=Mock();c.text.return_value=h.verdict(t,False);self.run_stage(h,d,o,t,e,ev,c);atomic_json(ev/'candidate-raw.json',{'changed':True})
   with self.assertRaises(r.RepairBlocked):r.exhausted_coverage(t,ev.parent,d)
 def test_old_receipt_is_not_reinterpreted_as_new_final_coverage(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);c=Mock();c.text.return_value=h.verdict(t,False);self.run_stage(h,d,o,t,e,ev,c);receipt=load_json(ev/r.RECEIPT);receipt.pop('coverage_contract_version');atomic_json(ev/r.RECEIPT,receipt);self.assertIsNone(r.exhausted_coverage(t,ev.parent,d))
 def test_temporary_source_failure_does_not_become_permanent_absence(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);c=Mock();c.text.return_value=h.verdict(t,False);old=(ev/'sources.json').read_bytes();result=self.run_stage(h,d,o,t,e,ev,c,Mock(side_effect=TimeoutError()));self.assertEqual(result['status'],'stage_deferred');self.assertEqual(f.state(ev.parent,'research_refetch')['attempts'],0);self.assertIsNone(r.exhausted_coverage(t,ev.parent,d));self.assertEqual(old,(ev/'sources.json').read_bytes());self.assertFalse(load_json(ev/r.RECEIPT)['repair_exhausted'])
 def test_final_coverage_uncertainty_retains_reconciliation_and_old_bytes(self):
  from automation.agri_v2.client import TextProviderError
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);before=(ev/'sources.json').read_bytes();c=Mock();c.text.side_effect=[h.verdict(t,False),TextProviderError(None,"text_transport_uncertain")];result=self.run_stage(h,d,o,t,e,ev,c);self.assertEqual(result['status'],'stage_reconciliation_required');self.assertEqual(before,(ev/'sources.json').read_bytes());self.assertIsNone(r.exhausted_coverage(t,ev.parent,d))
 def test_coverage_prompt_keeps_exact_route_and_no_invented_thresholds(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);c=Mock();c.text.return_value=h.verdict(t,True);self.run_stage(h,d,o,t,e,ev,c);packet=json.loads(c.text.call_args.args[0]);self.assertEqual(packet['research_route']['canonical_title'],t['title']);self.assertIn('not invented local thresholds',packet['scope_contract']);self.assertIn('Never invent botanical',packet['scope_contract'])

 def test_unapproved_document_changes_invalidate_deferral_proof(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev=self.setup(td);c=Mock();c.text.return_value=h.verdict(t,False);self.run_stage(h,d,o,t,e,ev,c);atomic_json(ev/'real-search/unapproved-documents.json',{'changed':True})
   with self.assertRaises(r.RepairBlocked):r.exhausted_coverage(t,ev.parent,d)
