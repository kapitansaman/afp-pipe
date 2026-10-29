import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_keyed_validation as r
from automation.agri_v2.queue import load_json,atomic_json
class KeyedValidationTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123'}
 def test_new_admission_bound_to_keyed_schema_and_all_old_outcomes(self):
  req=r.expected();r.validate(req);self.assertEqual(req['max_model_calls'],2);self.assertEqual(req['max_search_requests'],0);self.assertEqual(req['max_source_fetches'],0);self.assertEqual(req['review_wire_contract'],'regional-keyed-facts-v1')
  for k,v in [('request_id',r.base.ID),('max_model_calls',3),('max_model_calls_per_language',2),('languages',['ru-RU']),('previous_recheck_sha256','changed'),('response_schema_sha256',{}),('protected_sha256','changed'),('reset_attempts',True),('promotion_authorized',True),('publication_authorized',True)]:
   with self.subTest(k=k),self.assertRaises(r.base.RecheckBlocked):r.validate(dict(req,**{k:v}))
 def test_prior_unknown_or_changed_result_cannot_be_reclassified(self):
  current=r.prior(r.OUT)
  for delta in [{'model_calls':1},{'originals_unchanged':False},{'status':'unknown'},{'results':[]},{'request_id':r.ID}]:
   with patch.object(r,'load_json',return_value=dict(current,**delta)),self.assertRaises(r.base.RecheckBlocked):r.prior(Path('/fixture'))
 def test_history_and_consumed_requests_remain_protected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/'config.json',{});before=r.manifest(data,out);atomic_json(data/r.REQUEST,{});atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{});self.assertEqual(before,r.manifest(data,out))
   for p in [out/'infrastructure-probes'/r.base.ID/'report.json',data/'regional-schema-recheck-request.json',out/'new/topic/review-queue/ar-IQ.json',out/'new/topic/regional-research/ar-IQ/continuation.json',out/'infrastructure-probes/unknown/languages/ar-IQ/review-1.receipt.json']:
    atomic_json(p,{'original':True});self.assertNotEqual(before,r.manifest(data,out));p.unlink()
 def test_only_exact_manual_remote_reservation(self):
  from automation.agri_v2.parallel_control import reserve
  self.assertIsNotNone(reserve('regional-keyed-validation',r.ID,self.env(),put_fn=lambda row:True))
  for ident,env in [(r.base.ID,self.env()),('retry-new-id',self.env()),(r.ID,dict(self.env(),GITHUB_EVENT_NAME='schedule')),(r.ID,dict(self.env(),GITHUB_REF_NAME='main'))]:
   with self.assertRaises(ValueError):reserve('regional-keyed-validation',ident,env,put_fn=lambda row:True)
 def test_unknown_or_completed_own_report_never_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});f=Mock();s=Mock();result=r.run(self.env(),out=out,client_factory=f,reserve_fn=s);self.assertEqual(result['model_calls'],0);f.assert_not_called();s.assert_not_called()
 def test_active_hold_stops_before_reservation_or_transport(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';atomic_json(data/r.REQUEST,{})
   with patch.object(r,'validate',return_value=(None,None,None,None)),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=True):
    f=Mock();s=Mock();result=r.run(self.env(),data=data,out=root/'out',client_factory=f,reserve_fn=s);self.assertEqual(result['model_calls'],0);f.assert_not_called();s.assert_not_called()
 def test_shared_executor_uses_separate_exact_admission_not_old_id(self):
  with patch.object(r.base,'execute',return_value={'status':'fixture'}) as ex:
   r.run(self.env());args=ex.call_args.args;self.assertEqual(args[5:7],(r.ID,r.REQUEST));self.assertEqual(args[-1],'regional-keyed-validation');self.assertIs(args[7],r.validate);self.assertIs(args[8],r.manifest)
