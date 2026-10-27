import contextlib,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import language_fallback_continuation as c,provider_diagnostic as d,operation_request as op,language_review_queue as q
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.multilingual import LANGUAGES
class LanguageContinuationTests(unittest.TestCase):
 def test_exact_request_cannot_enable_publication_or_regenerate_images(self):
  req=dict(c.expected_request(),code_revision='a'*40);op.validate_request(req)
  for k,v in [('enable_schedule',True),('reset_attempts',True),('max_image_calls',1),('max_total_text_calls',17),('max_wordpress_mutations',1),('max_total_posts',1),('max_attempts_per_language_this_run',2),('max_provider_wait_seconds',3601)]:
   with self.assertRaises(ValueError):op.validate_request(dict(req,**{k:v}))
 def test_text_or_image_hold_blocks_text_diagnostic(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t);until=time.time()+3600;atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text_or_image','retry_at_epoch':until});self.assertEqual(d.active_cooldown(out),until)
 def test_image_only_hold_does_not_block_text_continuation(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t);atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'image','retry_at_epoch':time.time()+3600});self.assertEqual(d.active_cooldown(out),0)
 def test_wait_performs_no_calls_before_deadline(self):
  clock=[100.];waits=[]
  def cooldown(_):return 160. if clock[0]<160 else 0
  def sleep(n):clock[0]+=n;waits.append(n)
  with patch.object(d,'active_cooldown',side_effect=cooldown):self.assertTrue(c.wait_for_provider(Path('.'),sleep=sleep,clock=lambda:clock[0]))
  self.assertEqual(sum(waits),60);self.assertTrue(all(n<=30 for n in waits))
 def test_wait_refuses_deadline_beyond_bounded_window(self):
  sleep=Mock()
  with patch.object(d,'active_cooldown',return_value=4000):self.assertFalse(c.wait_for_provider(Path('.'),sleep=sleep,clock=lambda:100,max_wait=3600))
  sleep.assert_not_called()
 def test_wait_extension_does_not_restart_budget(self):
  clock=[100.]
  def cooldown(_):return 120 if clock[0]==100 else 5000
  def sleep(n):clock[0]+=n
  with patch.object(d,'active_cooldown',side_effect=cooldown):self.assertFalse(c.wait_for_provider(Path('.'),sleep=sleep,clock=lambda:clock[0],max_wait=3600))
  self.assertEqual(clock[0],120)
 def test_readonly_wordpress_refuses_all_mutations(self):
  wp=object.__new__(c.ReadOnlyWordPress)
  for method in ['POST','PUT','PATCH','DELETE']:
   with self.assertRaises(ValueError):wp.call('posts',method=method)
 def fixture(self,t):
  root=Path(t);data=root/'data';out=root/'out';source=out/'source';folder=out/'new'/c.TOPIC;article={'title':'fixture'};atomic_json(folder/'article.json',article);atomic_json(folder/'image-selection.json',{'roles':[1]});(folder/'image-1.webp').write_bytes(b'approved-unchanged');atomic_json(source/'article.json',article);atomic_json(out/'parallel/families/assignments.json',{'families':[{'id':'owner'}]});atomic_json(data/'status/owner-operation-admission.json',{'request_id':c.ID});atomic_json(out/'parallel/health/latest.json',{'checked_at':utcnow(),'eligible_text_slots':['AGNES_API_KEY']});atomic_json(out/'parallel/operations'/c.PRIOR/'prepare.json',{'image_test_passed':True,'translation_test_passed':False,'model_calls':1,'image_calls':1,'published_posts':0})
  for lang in LANGUAGES:atomic_json(q.path(folder,lang),{'language':lang,'status':'waiting','attempts':2 if lang=='tg-TJ' else 0,'model_calls_spent':7 if lang=='tg-TJ' else 0,'article_sha256':c.SOURCE_SHA,'next_attempt_at':utcnow(),'history':[]})
  return data,out,source,folder,article
 @contextlib.contextmanager
 def mocked(self,t):
  data,out,source,folder,article=self.fixture(t)
  with contextlib.ExitStack() as stack:
   for target,kwargs in [('automation.agri_v2.operation_request.authorize',{'return_value':True}),('automation.agri_v2.parallel_control.policy',{'return_value':{}}),('automation.agri_v2.language_fallback_continuation.source_inputs',{'return_value':({'id':c.TOPIC,'title':'fixture'},{},article,source,folder)}),('automation.agri_v2.image_quality.require_all',{'return_value':None}),('automation.agri_v2.image_layout.roles_for',{'return_value':(1,)}),('automation.agri_v2.multilingual.localized_body',{'return_value':'body'}),('automation.agri_v2.language_review_queue.index',{'return_value':{}})]:stack.enter_context(patch(target,**kwargs))
   yield data,out,source,folder,article
 def test_four_language_success_preserves_old_attempts_images_and_owners(self):
  with tempfile.TemporaryDirectory() as t,self.mocked(t) as (data,out,source,folder,article):
   approved=set()
   def attempt(p,client,data):
    r=load_json(p);r['attempts']+=1;r['model_calls_spent']+=2;r['status']='approved';atomic_json(p,r);atomic_json(q.target(p.parent.parent,r['language']),{'fixture':True});approved.add(r['language']);return {'status':'approved','language':r['language'],'model_calls':2}
   wp=Mock();wp.preflight.return_value={'can_publish':True};wp.call.return_value=({'schema':{'properties':{'afp_language':{},'afp_source_post_id':{}}}},{});factory=Mock()
   with patch.object(q,'approved',side_effect=lambda f,a,l:l in approved),patch.object(q,'run_item',side_effect=attempt):r=c.run({'GITHUB_RUN_ID':'123'},data,out,client_factory=factory,reserve_fn=lambda *_:{},wp_factory=lambda:wp,wait_fn=lambda *a,**k:True)
   self.assertEqual(r['status'],'image_fallback_verification_passed');self.assertTrue(r['translation_test_passed']);self.assertEqual(r['queues_after']['tg-TJ']['attempts'],3);self.assertEqual(r['queues_after']['tg-TJ']['model_calls_spent'],9);self.assertEqual(factory.call_count,4);self.assertEqual(r['image_calls'],0);self.assertEqual(r['published_posts'],0);self.assertFalse(r['schedule_activated']);self.assertTrue(r['protected_existing_files_unchanged']);self.assertTrue(r['prior_operations_unchanged']);self.assertTrue(r['assignments_unchanged']);self.assertEqual((folder/'image-1.webp').read_bytes(),b'approved-unchanged')
 def test_wait_limit_does_not_create_clients_or_reset_attempts(self):
  with tempfile.TemporaryDirectory() as t,self.mocked(t) as (data,out,source,folder,article):
   factory=Mock();wp=Mock();r=c.run({'GITHUB_RUN_ID':'123'},data,out,client_factory=factory,reserve_fn=lambda *_:{},wp_factory=wp,wait_fn=lambda *a,**k:False);self.assertEqual(r['status'],'language_continuation_wait_limit');factory.assert_not_called();wp.assert_not_called();self.assertEqual(load_json(q.path(folder,'tg-TJ'))['attempts'],2)
 def test_new_hold_after_wait_cannot_be_bypassed(self):
  with tempfile.TemporaryDirectory() as t,self.mocked(t) as (data,out,source,folder,article):
   factory=Mock()
   with patch.object(d,'active_cooldown',return_value=time.time()+3600):
    with self.assertRaises(ValueError):c.run({'GITHUB_RUN_ID':'123'},data,out,client_factory=factory,reserve_fn=lambda *_:{},wait_fn=lambda *a,**k:True)
   factory.assert_not_called()
 def test_replay_does_not_spend_another_budget(self):
  with tempfile.TemporaryDirectory() as t,self.mocked(t) as (data,out,source,folder,article):
   atomic_json(out/'parallel/operations'/c.ID/'prepare.json',{'status':'prior'});reserve=Mock();factory=Mock();r=c.run({'GITHUB_RUN_ID':'123'},data,out,client_factory=factory,reserve_fn=reserve);self.assertEqual(r['status'],'language_continuation_already_reserved');reserve.assert_not_called();factory.assert_not_called()
 def test_no_admission_no_work(self):
  with patch.object(op,'authorize',return_value=False):
   with self.assertRaises(ValueError):c.run({})

 def test_readonly_preflight_failure_prevents_every_model_call(self):
  with tempfile.TemporaryDirectory() as t,self.mocked(t) as (data,out,source,folder,article):
   wp=Mock();wp.preflight.return_value={'can_publish':False};wp.call.return_value=({'schema':{'properties':{}}},{});factory=Mock();r=c.run({'GITHUB_RUN_ID':'123'},data,out,client_factory=factory,reserve_fn=lambda *_:{},wp_factory=lambda:wp,wait_fn=lambda *a,**k:True);self.assertEqual(r['status'],'language_continuation_incomplete');factory.assert_not_called();self.assertEqual(r['model_calls'],0);self.assertTrue(r['protected_existing_files_unchanged'])
 def test_unapproved_languages_never_turn_into_success_by_attempt_count(self):
  with tempfile.TemporaryDirectory() as t,self.mocked(t) as (data,out,source,folder,article):
   wp=Mock();wp.preflight.return_value={'can_publish':True};wp.call.return_value=({'schema':{'properties':{'afp_language':{},'afp_source_post_id':{}}}},{});factory=Mock()
   with patch.object(q,'approved',return_value=False),patch.object(q,'run_item',return_value={'status':'needs_attention','model_calls':0}):r=c.run({'GITHUB_RUN_ID':'123'},data,out,client_factory=factory,reserve_fn=lambda *_:{},wp_factory=lambda:wp,wait_fn=lambda *a,**k:True)
   self.assertEqual(r['status'],'language_continuation_incomplete');self.assertFalse(r['translation_test_passed']);self.assertFalse(r['native_review_claimed']);self.assertEqual(r['published_posts'],0)
 def test_prior_consumed_budget_cannot_be_relabelled_for_extra_calls(self):
  with tempfile.TemporaryDirectory() as t,self.mocked(t) as (data,out,source,folder,article):
   p=out/'parallel/operations'/c.PRIOR/'prepare.json';r=load_json(p);r['model_calls']=2;atomic_json(p,r);reserve=Mock()
   with self.assertRaises(ValueError):c.run({'GITHUB_RUN_ID':'123'},data,out,reserve_fn=reserve)
   reserve.assert_not_called()
