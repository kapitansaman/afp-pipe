import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import checkpoint_reconcile as c,execution_recovery as r
from automation.agri_v2.queue import atomic_json,load_json

class ManualCheckpointReconcileTests(unittest.TestCase):
 def setup(self,td):
  root=Path(td);d=root/'data/agri-v2';o=root/'artifacts/agri-v2';ident='agri-000000000001';f=o/'new'/ident
  row={'version':1,'policy':r.VERSION,'repository':r.REPO,'branch':r.BRANCH,'status':'in_flight','run_id':'123','topics':[{'topic_id':ident,'family_id':'family-01'}],'original_attempts_reset':False,'automatic_uncertain_replay':False}
  atomic_json(d/'status/lifecycle-flight.json',row);atomic_json(o/'parallel/recovery/admissions/123.json',{'run_id':'123','intent':row,'reserved_row_sha256':r.fingerprint(row)})
  atomic_json(o/'parallel/lifecycle/runs/123/report.json',{'run_id':'123','status':'completed_with_failures','coordinator_failure':{'kind':'unexpected','category':'unspecified'},'results':[{'topic_id':ident,'checkpoint_merged':True,'status':'publication_ready'}],'publication_results':[{'topic_id':ident,'status':'stage_failed','failure':{'kind':'validation'}}],'published_posts':0})
  atomic_json(f/'lifecycle/publish/state.json',{'attempts':1,'history':[{'status':'failed'}],'status':'failed','last_run_id':'123','failure':{'kind':'validation'}});atomic_json(d/'briefs'/(ident+'.json'),{'slug':'test-slug'});wp=Mock();wp.call.return_value=([],{});e={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'124'}
  return d,o,f,e,wp,row
 def invoke(self,d,o,e,wp,check=lambda paths:None):
  with patch.object(c,'get_topic',return_value={'id':'agri-000000000001'}):return c.reconcile(e,d,o,wp,check)
 def test_known_failed_durable_checkpoint_closes_with_proof_not_success(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,f,e,wp,row=self.setup(td);before=(f/'lifecycle/publish/state.json').read_bytes();rp=o/'parallel/lifecycle/runs/123/report.json';report=rp.read_bytes();v=self.invoke(d,o,e,wp)
   self.assertEqual(v['status'],'known_failed_checkpoint_reconciled');self.assertFalse(v['stage_limit_changed']);self.assertEqual(before,(f/'lifecycle/publish/state.json').read_bytes());self.assertEqual(report,rp.read_bytes());self.assertEqual(wp.call.call_count,5)
   proof=load_json(o/'parallel/recovery/reconciliations/123.json');closed=load_json(d/'status/lifecycle-flight.json');self.assertEqual(closed['checkpoint_digest'],r.fingerprint(proof));self.assertFalse(proof['publication_success_claimed']);self.assertEqual(proof['post_mutations'],0)
   for call in wp.call.call_args_list:self.assertEqual(len(call.args),1);self.assertEqual(call.kwargs,{})
 def test_unknown_stage_never_clears_or_calls_remote(self):
  for status in ('reserved','reconciliation_required'):
   with self.subTest(status=status),tempfile.TemporaryDirectory()as td:
    d,o,f,e,wp,row=self.setup(td);atomic_json(f/'lifecycle/image-1/state.json',{'status':status});before=(d/'status/lifecycle-flight.json').read_bytes()
    with self.assertRaises(r.ReconciliationRequired):self.invoke(d,o,e,wp)
    self.assertEqual(before,(d/'status/lifecycle-flight.json').read_bytes());wp.preflight.assert_not_called()
 def test_existing_receipt_or_remote_post_requires_separate_reconciliation(self):
  for receipt in (True,False):
   with self.subTest(receipt=receipt),tempfile.TemporaryDirectory()as td:
    d,o,f,e,wp,row=self.setup(td)
    if receipt:atomic_json(f/'wordpress-receipt.json',{'status':'draft_created'})
    else:wp.call.return_value=([{'id':123}],{})
    with self.assertRaises(r.ReconciliationRequired):self.invoke(d,o,e,wp)
    self.assertEqual(load_json(d/'status/lifecycle-flight.json')['status'],'in_flight')
 def test_uncommitted_evidence_cannot_clear_fence(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,f,e,wp,row=self.setup(td)
   with self.assertRaises(r.ReconciliationRequired):self.invoke(d,o,e,wp,Mock(side_effect=r.ReconciliationRequired('uncommitted')))
   wp.preflight.assert_not_called()
 def test_incomplete_worker_or_unknown_publication_cannot_clear(self):
  for kind in ('worker','publication','already_published'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory()as td:
    d,o,f,e,wp,row=self.setup(td);p=o/'parallel/lifecycle/runs/123/report.json';v=load_json(p)
    if kind=='worker':v['results'][0]['checkpoint_merged']=False
    elif kind=='publication':v['publication_results'][0]['status']='stage_reconciliation_required'
    else:v['published_posts']=1
    atomic_json(p,v)
    with self.assertRaises(r.ReconciliationRequired):self.invoke(d,o,e,wp)
    wp.preflight.assert_not_called()
 def test_not_manual_or_changed_intent_does_not_clear(self):
  for kind in ('event','intent'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory()as td:
    d,o,f,e,wp,row=self.setup(td)
    if kind=='event':e['GITHUB_EVENT_NAME']='schedule'
    else:row['topics'][0]['family_id']='family-02';atomic_json(d/'status/lifecycle-flight.json',row)
    with self.assertRaises(r.ReconciliationRequired):self.invoke(d,o,e,wp)
    wp.preflight.assert_not_called()

 def test_unknown_search_outcome_stays_fenced(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,f,e,wp,row=self.setup(td);p=o/'parallel/lifecycle/runs/123/report.json';v=load_json(p);v['source_search']={'unknown_requests':1};atomic_json(p,v)
   with self.assertRaises(r.ReconciliationRequired):self.invoke(d,o,e,wp)
   wp.preflight.assert_not_called()
