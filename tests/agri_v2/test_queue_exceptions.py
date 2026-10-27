import tempfile,unittest,concurrent.futures
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import queue_exceptions as q,family_scheduler as scheduler,family_lifecycle as lifecycle
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from tests.agri_v2 import test_family_scheduler as scheduler_fixtures
from tests.agri_v2 import test_family_lifecycle as lifecycle_fixtures

class QueueExceptionTests(unittest.TestCase):
 def setup(self,root,n=45):
  d,o,topics=scheduler_fixtures.FamilySchedulerTests().setup(root,n);atomic_json(d/'queue-exception-policy.json',q.POLICY);atomic_json(d/'family-lifecycle-policy.json',{'version':1,'enabled':True,'publication_enabled':True,'max_families':20,'max_attempts_per_stage':3,'max_model_requests_per_family':14,'max_published_families':20,'preserve_legacy_budgets':True})
  with patch.object(scheduler,'items',return_value=topics):state=scheduler.allocate(d,o)
  return d,o,topics,state
 def fail(self,d,o,t,stage='research_review',attempts=3,status='failed'):
  atomic_json(o/'new'/t['id']/'lifecycle'/stage/'state.json',{'attempts':attempts,'status':status,'last_run_id':'123','failure':{'category':'independent_scoped_review_rejected'},'history':[{'kept':'original'}]})
  atomic_json(o/'new'/t['id']/'lifecycle-evidence/review-raw.json',{'accepted':False})
  return {'topic_id':t['id'],'status':'stage_failed','stage':stage}
 def test_exhausted_scientific_review_frees_only_its_slot_without_approval_or_reset(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,initial=self.setup(Path(td));result=self.fail(d,o,t[0]);q.note_terminal(dict(t[0],family_id='family-01',assigned_work_stage='old'),result,d,o)
   files={p:p.read_bytes() for p in (o/'new'/t[0]['id']).rglob('*') if p.is_file()}
   with patch.object(scheduler,'items',return_value=t):state=scheduler.allocate(d,o,allow_deferral=True)
   self.assertEqual(state['families'][0]['topic_id'],t[20]['id']);self.assertEqual(state['families'][1:],initial['families'][1:]);self.assertEqual(state['exception_backlog_count'],1)
   row=state['exception_backlog'][t[0]['id']];self.assertEqual(row['attempts_preserved'],3)
   for k in ('publication_authorized','automatic_retry_authorized','prior_attempts_reset'):self.assertIs(row[k],False)
   self.assertEqual(files,{p:p.read_bytes() for p in files});self.assertEqual(state['history'][-1]['completion'],'deferred_to_exception_backlog')
   self.assertEqual(lifecycle.next_stage(t[0],d,o),('blocked','exception_queue_requires_explicit_review'));wp=Mock();self.assertEqual(lifecycle.publish_ready(wp,t[0],d,o)['status'],'not_publication_ready');wp.publish.assert_not_called()
 def test_twenty_terminal_topics_cannot_pin_all_slots_forever(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td))
   for topic in t[:20]:q.note_terminal(topic,self.fail(d,o,topic),d,o)
   with patch.object(scheduler,'items',return_value=t):state=scheduler.allocate(d,o,allow_deferral=True)
   self.assertEqual([x['topic_id'] for x in state['families']],[x['id'] for x in t[20:40]]);self.assertEqual(state['exception_backlog_count'],20);self.assertEqual(len(state['history']),20)
 def test_diagnostic_allocation_never_moves_terminal_topic(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,initial=self.setup(Path(td));q.note_terminal(t[0],self.fail(d,o,t[0]),d,o)
   with patch.object(scheduler,'items',return_value=t):state=scheduler.allocate(d,o)
   self.assertEqual(state['families'],initial['families']);self.assertEqual(state['exception_backlog_count'],0)
 def test_remaining_attempt_or_validated_stage_never_qualifies(self):
  for attempts,status in [(2,'failed'),(3,'validated'),(3,'deferred'),(True,'failed')]:
   with self.subTest(attempts=attempts,status=status),tempfile.TemporaryDirectory() as td:
    d,o,t,_=self.setup(Path(td));r=self.fail(d,o,t[0],attempts=attempts,status=status);self.assertIsNone(q.note_terminal(t[0],r,d,o))
 def test_deferred_provider_worker_crash_and_language_failure_do_not_quarantine(self):
  for status,stage in [('stage_deferred','research_review'),('worker_timed_out','research_review'),('worker_operational_failure','research_review'),('images_deferred','image-1'),('stage_failed','language_primary-ru-RU'),('stage_failed','translation-ru-RU'),('stage_failed','publish')]:
   with self.subTest(status=status,stage=stage),tempfile.TemporaryDirectory() as td:
    d,o,t,_=self.setup(Path(td));r=self.fail(d,o,t[0],stage=stage);r['status']=status;self.assertIsNone(q.note_terminal(t[0],r,d,o))
 def test_explicit_holds_and_any_publication_evidence_keep_ownership(self):
  for kind in ('hold','source-receipt','uncertain-source','translation-receipt','payload','publish-attempt'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    d,o,t,_=self.setup(Path(td));r=self.fail(d,o,t[0]);folder=o/'new'/t[0]['id']
    if kind=='hold':atomic_json(d/'config.json',{'publication_holds':{t[0]['id']:'keep'}})
    elif kind in ('source-receipt','uncertain-source'):atomic_json(folder/'wordpress-receipt.json',{'public_verified':kind=='source-receipt'})
    elif kind=='translation-receipt':atomic_json(folder/'translations/ru-RU.wordpress.json',{'public_verified':False})
    elif kind=='payload':atomic_json(folder/'wordpress-draft-payload.json',{})
    else:atomic_json(folder/'lifecycle/publish/state.json',{'attempts':3,'status':'failed'})
    self.assertIsNone(q.note_terminal(t[0],r,d,o))
 def test_changed_evidence_brief_topic_or_policy_invalidates_pending_checkpoint(self):
  for kind in ('evidence','brief','topic','policy'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    d,o,t,_=self.setup(Path(td));q.note_terminal(t[0],self.fail(d,o,t[0]),d,o);topic=dict(t[0])
    if kind=='evidence':atomic_json(o/'new'/t[0]['id']/'lifecycle-evidence/candidate.json',{'new':True})
    elif kind=='brief':atomic_json(d/'briefs'/(t[0]['id']+'.json'),{'new':True})
    elif kind=='topic':topic['title']='changed title'
    else:atomic_json(d/'research-source-catalog.json',{'entries':[],'changed':True})
    self.assertIsNone(q.deferral(topic,d,o))
 def test_counters_alone_or_forged_terminal_outcome_do_not_move_topic(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,initial=self.setup(Path(td));r=self.fail(d,o,t[0]);self.assertIsNone(q.deferral(t[0],d,o));r['topic_id']='agri-ffffffffffff';self.assertIsNone(q.note_terminal(t[0],r,d,o))
   r['topic_id']=t[0]['id'];r['stage']='unknown';self.assertIsNone(q.note_terminal(t[0],r,d,o))
 def test_disabled_or_absent_policy_does_not_create_terminal_checkpoint(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));r=self.fail(d,o,t[0]);atomic_json(d/'queue-exception-policy.json',dict(q.POLICY,enabled=False));self.assertIsNone(q.note_terminal(t[0],r,d,o));(d/'queue-exception-policy.json').unlink();self.assertIsNone(q.note_terminal(t[0],r,d,o))
 def test_legacy_exhaustion_preserves_original_two_attempts(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));path=o/'research'/(t[0]['id']+'.json');atomic_json(path,{'attempts':2,'status':'needs_review'});before=path.read_bytes()
   r={'topic_id':t[0]['id'],'status':'blocked','reason':'legacy_research_budget_exhausted'};self.assertIsNotNone(q.note_terminal(t[0],r,d,o));row=q.deferral(t[0],d,o);self.assertEqual(row['attempts_preserved'],2);self.assertEqual(path.read_bytes(),before)
 def test_specific_overlap_batch_uses_real_three_attempt_limit(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));r=self.fail(d,o,t[0],stage='existing_content_audit-005');self.assertIsNotNone(q.note_terminal(t[0],r,d,o));self.assertEqual(q.deferral(t[0],d,o)['stage'],'existing_content_audit-005')
 def test_same_allocation_and_concurrent_calls_never_duplicate_history(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));q.note_terminal(t[0],self.fail(d,o,t[0]),d,o)
   with patch.object(scheduler,'items',return_value=t),concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:rows=list(ex.map(lambda _:scheduler.allocate(d,o,allow_deferral=True),range(3)))
   self.assertTrue(all(x['families']==rows[0]['families'] for x in rows));self.assertEqual(len(rows[-1]['history']),1);self.assertEqual(rows[-1]['exception_backlog_count'],1)
 def test_assignment_disk_failure_cannot_detach_topic_from_checkpoint(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));q.note_terminal(t[0],self.fail(d,o,t[0]),d,o);path=o/'parallel/families/assignments.json';before=path.read_bytes()
   with patch.object(scheduler,'items',return_value=t),patch.object(scheduler,'atomic_json',side_effect=OSError('disk full')),self.assertRaises(OSError):scheduler.allocate(d,o,allow_deferral=True)
   self.assertEqual(path.read_bytes(),before);self.assertIsNotNone(q.deferral(t[0],d,o))
 def test_queued_topic_does_not_return_when_catalog_changes(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));q.note_terminal(t[0],self.fail(d,o,t[0]),d,o)
   with patch.object(scheduler,'items',return_value=t):
    first=scheduler.allocate(d,o,allow_deferral=True);atomic_json(d/'research-source-catalog.json',{'entries':[],'new':True});second=scheduler.allocate(d,o,allow_deferral=True)
   self.assertEqual(first['exception_backlog'],second['exception_backlog']);self.assertEqual(first['families'],second['families']);self.assertTrue(q.queued(t[0]['id'],o))
 def test_corrupt_overlapping_or_authorizing_backlog_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,initial=self.setup(Path(td));q.note_terminal(t[0],self.fail(d,o,t[0]),d,o);row=q.deferral(t[0],d,o);initial['exception_backlog']={t[0]['id']:row};atomic_json(o/'parallel/families/assignments.json',initial)
   with patch.object(scheduler,'items',return_value=t),self.assertRaises(ValueError):scheduler.allocate(d,o,allow_deferral=True)
   row['publication_authorized']=True
   with self.assertRaises(ValueError):q.validate_backlog({t[0]['id']:row})
 def test_coordinator_records_exhausted_results_then_advances_slots_without_paid_calls(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,topic,env,health=lifecycle_fixtures.FamilyLifecycleTests().setup(td);atomic_json(d/'queue-exception-policy.json',q.POLICY);atomic_json(d/'research-source-catalog.json',{'entries':[]})
   topics=[dict(topic,id='agri-'+format(i,'012x'),title='Topic '+str(i)) for i in range(40)]
   topics=[{k:v for k,v in t.items() if k!='family_id'} for t in topics]
   wp=Mock();wp.inventory.return_value={'source_generated_at':utcnow(),'records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   def worker(t,workspace,*args):
    wd=workspace/t['id']/'data';wo=workspace/t['id']/'out';r=self.fail(d,wo,t);return t['id'],wd,wo,r
   with patch.object(scheduler,'items',return_value=topics):result=lifecycle.run(env,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   state=load_json(o/'parallel/families/assignments.json');self.assertEqual(state['exception_backlog_count'],20);self.assertEqual([r['topic_id'] for r in state['families']],[t['id'] for t in topics[20:]])
   self.assertEqual(result['pool']['model_requests_reserved'],0);self.assertEqual(result['published_posts'],0);wp.publish.assert_not_called();self.assertTrue(all(r.get('terminal_exception_checkpoint_saved') for r in result['results']))

 def test_image_exception_requires_both_roles_exhausted_and_no_valid_fallback(self):
  from automation.agri_v2 import image_workflow as image
  for attempts,approved,expected in [((4,3),(),False),((4,4),(1,),False),((4,4),(),True)]:
   with self.subTest(attempts=attempts,approved=approved),tempfile.TemporaryDirectory() as td:
    d,o,t,_=self.setup(Path(td));folder=o/'new'/t[0]['id'];atomic_json(folder/'article.json',{'retained':True})
    for k,n in enumerate(attempts,1):atomic_json(folder/'lifecycle'/('image-'+str(k))/'state.json',{'attempts':n,'status':'failed'})
    result={'topic_id':t[0]['id'],'status':'blocked','reason':'images_need_attention'}
    with patch.object(image,'enabled',return_value=True),patch.object(image,'approved_roles',return_value=approved):row=q.note_terminal(t[0],result,d,o)
    self.assertEqual(row is not None,expected)
 def test_one_shot_quality_repair_limit_is_not_increased_to_three(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));r=self.fail(d,o,t[0],stage='article_quality_repair',attempts=1);row=q.note_terminal(t[0],r,d,o);self.assertIsNotNone(row);self.assertEqual(row['proof']['attempt_limit'],1)
 def test_mixed_full_2905_queue_finishes_assignment_without_losing_exceptions(self):
  from automation.agri_v2.queue import DATA,items
  with tempfile.TemporaryDirectory() as td:
   d,o,_,_=self.setup(Path(td));(o/'parallel/families/assignments.json').unlink();topics=items('new',DATA);done=set();seen=set();exception_ids=set();waves=0
   self.assertEqual(len(topics),2905)
   with patch.object(scheduler,'items',return_value=topics),patch.object(scheduler,'published',new=lambda ident,out:ident in done),patch.object(scheduler,'family_complete',new=lambda ident,data,out:ident in done):
    while True:
     state=scheduler.allocate(d,o,allow_deferral=True)
     active=state['families']
     if not active:break
     self.assertLessEqual(len(active),20);self.assertTrue(seen.isdisjoint(row['topic_id'] for row in active));waves+=1;self.assertLessEqual(waves,146)
     by_id={t['id']:t for t in topics}
     for row in active:
      ident=row['topic_id'];seen.add(ident)
      if len(seen)%5==0:q.note_terminal(by_id[ident],self.fail(d,o,by_id[ident]),d,o);exception_ids.add(ident)
      else:done.add(ident)
   self.assertEqual(len(seen),2905);self.assertEqual(seen,done|exception_ids);self.assertFalse(done&exception_ids);self.assertEqual(set(state['exception_backlog']),exception_ids);self.assertEqual(len(exception_ids),581);self.assertEqual(len(state['history']),2905)

 def test_exhausted_quality_repair_waits_for_explicit_review_not_another_round(self):
  from automation.agri_v2 import quality_index as quality
  from automation.agri_v2.queue import DATA
  from automation.agri_v2.pipeline import digest
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));folder=o/'new'/t[0]['id'];brief={'retained_brief':True};article={'content_html':'Retained original article'}
   atomic_json(d/'quality-index-policy.json',load_json(DATA/'quality-index-policy.json'));atomic_json(d/'briefs'/(t[0]['id']+'.json'),brief);atomic_json(folder/'article.json',article)
   review={'quality_policy':quality.VERSION,'dimensions':{key:0 for key in quality.DIMENSIONS},'critical_issues':[],'reason':'Article needs substantial support and remains below the finite acceptance threshold.'}
   atomic_json(folder/'article-quality-index.json',{'article_sha256':digest(article),'brief_sha256':digest(brief),'review':review});atomic_json(folder/'lifecycle/article_quality_repair/state.json',{'attempts':1,'status':'validated'})
   result={'topic_id':t[0]['id'],'status':'blocked','reason':'article_quality_review_queue'};row=q.note_terminal(t[0],result,d,o)
   self.assertIsNotNone(row);self.assertEqual(row['proof']['kind'],'quality_budget_exhausted');self.assertEqual(q.deferral(t[0],d,o)['attempt_limit'],1)
 def test_legacy_generation_budget_is_not_reset_when_family_leaves_slot(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,_=self.setup(Path(td));folder=o/'new'/t[0]['id'];atomic_json(folder/'article.json',{'retained':True});path=folder/'cycle-attempts.json';atomic_json(path,{'attempts':2,'status':'failed'});before=path.read_bytes()
   result={'topic_id':t[0]['id'],'status':'blocked','reason':'legacy_generation_budget_exhausted'};row=q.note_terminal(t[0],result,d,o)
   self.assertIsNotNone(row);self.assertEqual(q.deferral(t[0],d,o)['stage'],'legacy_generation');self.assertEqual(path.read_bytes(),before)
