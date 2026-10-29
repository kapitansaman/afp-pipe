import tempfile,unittest,json
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_only_recovery as r
from automation.agri_v2 import source_search as s
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.parallel_pool import initialize,connect,PoolDeferred
from automation.agri_v2.healthcheck import TEXT_MODEL

class RegionalOnlyRecoveryTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123'}
 def test_request_bound_to_approved_fidelity_cohort_and_existing_counters(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'out';data=Path(d)/'data';folder=out/'new/topic';atomic_json(folder/'article.json',{'fixture':True});atomic_json(data/'briefs/topic.json',{});rows={lang:{'attempts':3,'model_calls_spent':4} for lang in r.LANGUAGES}
   for lang in r.LANGUAGES:atomic_json(folder/'translations'/(lang+'.fidelity.json'),{'faithful':True})
   from automation.agri_v2.post_hold_validation import ID
   atomic_json(out/'infrastructure-probes'/ID/'health-passed.json',{'status':'passed','at':utcnow()})
   with patch.object(r,'selected',return_value=('topic',folder,rows)):
    req=r.expected(data,out);r.validate(req,data,out)
    for key,value in [('languages',['ru-RU']),('max_model_calls',9),('max_search_requests',9),('reset_attempts',True),('publication_authorized',True),('article_sha256','changed'),('code_sha256','changed'),('queue_sha256',{})]:
     with self.subTest(key=key),self.assertRaises(r.RecoveryBlocked):r.validate(dict(req,**{key:value}),data,out)
 def test_multifamily_rollout_is_not_admitted(self):
  with patch('automation.agri_v2.staged_rollout.load',return_value={'limit':3,'cohort':[]}):
   with self.assertRaises(r.RecoveryBlocked):r.selected()
 def test_only_exact_manual_remote_reservation_is_allowed(self):
  from automation.agri_v2.parallel_control import reserve
  put=Mock(return_value=True);self.assertIsNotNone(reserve('regional-only-recovery',r.ID,self.env(),put_fn=put))
  with self.assertRaises(ValueError):reserve('regional-only-recovery',r.ID,dict(self.env(),GITHUB_EVENT_NAME='schedule'),put_fn=put)
  with self.assertRaises(ValueError):reserve('regional-only-recovery','retry-new-id',self.env(),put_fn=put)
 def test_unknown_preexisting_report_is_never_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{'status':'regional_recovery_reserved'});factory=Mock();reserve=Mock();result=r.run(self.env(),out=out,client_factory=factory,reserve_fn=reserve)
   self.assertEqual(result['model_calls'],0);factory.assert_not_called();reserve.assert_not_called()
 def client(self,root,error=None):
  class Base:
   def __init__(self,*a,**k):self.calls=0
   def request(self,*a,**k):
    self.calls+=1;self.attempts=k['attempts']
    if error:raise error
    return {'choices':[]}
  return r.CountedClient({}, {},root,base_class=Base)
 def payload(self,n=0):return {'model':TEXT_MODEL,'max_tokens':14000,'messages':[{'content':'fixture-'+str(n)}]}
 def test_one_attempt_unknown_not_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d),TimeoutError());c.recovery_language='ar-IQ'
   with self.assertRaises(TimeoutError):c.request('text','/chat/completions',self.payload(),180,attempts=8)
   with self.assertRaises(r.RecoveryBlocked):c.request('text','/chat/completions',self.payload(),180)
   self.assertEqual((c.calls,c.attempts),(1,1))
 def test_forbidden_languages_and_site_image_endpoints_stop_before_transport(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d))
   for lang,kind,path in [('tg-TJ','text','/chat/completions'),('ru-RU','text','/chat/completions'),('ar-IQ','image','/images/generations'),('en-US','text','/posts')]:
    c.recovery_language=lang
    with self.assertRaises(r.RecoveryBlocked):c.request(kind,path,self.payload(),180)
   self.assertEqual(c.calls,0)
 def test_eight_calls_total_no_more_than_four_per_approved_language(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.client(Path(d))
   for lang in r.LANGUAGES:
    c.recovery_language=lang
    for n in range(4):c.request('text','/chat/completions',self.payload(n),180)
    with self.assertRaises(r.RecoveryBlocked):c.request('text','/chat/completions',self.payload(8),180)
   self.assertEqual(c.calls,8)
 def test_immutable_protects_article_unknown_probes_and_all_other_language_queues(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/'config.json',{'enabled':False});atomic_json(out/'new/topic/article.json',{'unchanged':True});atomic_json(out/'new/topic/review-queue/ru-RU.json',{'unchanged':True});atomic_json(out/'infrastructure-probes/old/languages/ar-IQ/review-1.receipt.json',{'status':'reserved'})
   before=r.immutable(data,out,'topic');atomic_json(out/'new/topic/regional-research/ar-IQ/approved.json',{});atomic_json(out/'new/topic/review-queue/ar-IQ.json',{});self.assertEqual(before,r.immutable(data,out,'topic'))
   atomic_json(out/'new/topic/article.json',{'unchanged':False});self.assertNotEqual(before,r.immutable(data,out,'topic'))
 def test_provider_hold_stops_before_reservation_or_client(self):
  reserve=Mock();factory=Mock()
  with tempfile.TemporaryDirectory() as d,patch.object(r,'validate',return_value=('topic',Path('/no-write'),{})),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=True):result=r.run(self.env(),out=Path(d),client_factory=factory,reserve_fn=reserve)
  self.assertEqual(result['model_calls'],0);reserve.assert_not_called();factory.assert_not_called()

class SourceSearchSubBudgetTests(unittest.TestCase):
 def test_smaller_ceiling_preserves_actual_usage_and_cannot_be_increased_by_reinitialize(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);db=root/'pool';out=root/'out';initialize(db,['AGNES_API_KEY']);s.initialize(db,out,max_requests=1)
   with s.reservation(db,'query1','request1'):pass
   s.initialize(db,out,max_requests=80)
   with self.assertRaises(PoolDeferred):
    with s.reservation(db,'query2','request2'):pass
   report=s.persist(db,out);self.assertEqual(report['requests_reserved'],1);self.assertEqual(report['request_limit'],1);self.assertEqual(report['monthly_budget']['reserved'],1)
 def test_invalid_subbudgets_rejected_before_database_changes(self):
  with tempfile.TemporaryDirectory() as d:
   for value in (0,81,True,1.5):
    with self.assertRaises(ValueError):s.initialize(Path(d)/'pool',Path(d)/'out',max_requests=value)
