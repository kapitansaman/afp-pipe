import concurrent.futures,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import family_lifecycle as f
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.parallel_pool import PoolDeferred,SLOTS,lease
from automation.agri_v2.parallel_control import reserve
from automation.agri_v2.healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE

class FamilyLifecycleTests(unittest.TestCase):
 def setup(self,td):
  root=Path(td);data=root/'data';out=root/'out';topic={'id':'agri-000000000001','title':'نگهداری لوبیا','crop':'لوبیا','intent':'storage','family_id':'family-01','origin':'NEW'}
  atomic_json(data/'family-lifecycle-policy.json',{'version':1,'enabled':True,'publication_enabled':True,'max_families':20,'max_attempts_per_stage':3,'max_model_requests_per_family':12,'max_published_families':20,'preserve_legacy_budgets':True})
  atomic_json(data/'config.json',{'publication_holds':{},'multilingual':{'enabled':False}})
  atomic_json(data/'parallel-policy.json',{'repository':'kapitansaman/afp-pipe','credential_set_id':'afp-pipe-parallel-97-keys-v1','key_limit':97,'max_article_workers':20,'image_concurrency':1,'production_enabled':False,'max_published_posts':0})
  env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'100','AFP_PARALLEL_WORKER':'1','AFP_PARALLEL_TOPIC':topic['id']}
  health={'audit_status':'completed','repository':'kapitansaman/afp-pipe','credential_set_id':'afp-pipe-parallel-97-keys-v1','checked_at':utcnow(),'eligible_text_slots':SLOTS,'eligible_image_slots':[],'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE}
  atomic_json(out/'parallel/health/latest.json',health)
  return data,out,topic,env,health
 def test_invalid_stage_retries_next_run_only_preserving_failed_candidate(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);p=folder/'candidate.json'
   def bad():atomic_json(p,{'bad':True});raise ValueError('invalid')
   self.assertEqual(f.attempt(folder,'text','100',bad,[p])['status'],'stage_failed')
   fn=Mock();self.assertEqual(f.attempt(folder,'text','100',fn,[p])['status'],'deferred_same_run');fn.assert_not_called()
   def good():self.assertFalse(p.exists());return {'passed':True}
   self.assertEqual(f.attempt(folder,'text','101',good,[p])['status'],'stage_completed');self.assertEqual(load_json(folder/'lifecycle/text/rejected/1/candidate.json'),{'bad':True});self.assertEqual(f.state(folder,'text')['attempts'],2)
 def test_three_failed_attempts_stop_without_reset_or_fourth_paid_call(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);fn=Mock(side_effect=ValueError('bad'))
   for run in ['1','2','3']:self.assertEqual(f.attempt(folder,'text',run,fn)['status'],'stage_failed')
   self.assertEqual(f.attempt(folder,'text','4',fn)['status'],'stage_budget_exhausted');self.assertEqual(fn.call_count,3);self.assertEqual(len(f.state(folder,'text')['history']),3)
 def test_admission_deferral_does_not_spend_invalid_output_budget(self):
  with tempfile.TemporaryDirectory() as td:
   fn=Mock(side_effect=PoolDeferred('busy'));folder=Path(td)
   self.assertEqual(f.attempt(folder,'image-1','1',fn)['status'],'stage_deferred');self.assertEqual(f.state(folder,'image-1')['attempts'],0)
 def test_hold_numeric_and_legacy_research_attempts_are_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td)
   self.assertEqual(f.next_stage(dict(t,intent='yield'),d,o),('blocked','specialist_evidence_required'))
   t['overlap_review_required']=True;t['related_existing_ids']=[12];self.assertEqual(f.next_stage(t,d,o)[1],'verified_existing_content_audit_required')
   rp=o/'research'/(t['id']+'.json');atomic_json(rp,{'attempts':2,'status':'needs_review'});before=rp.read_bytes();self.assertEqual(f.next_stage(t,d,o)[1],'legacy_research_budget_exhausted');self.assertEqual(before,rp.read_bytes())
   cfg=load_json(d/'config.json');cfg['publication_holds']={t['id']:'keep'};atomic_json(d/'config.json',cfg);self.assertEqual(f.next_stage(t,d,o)[1],'publication_hold')
 def test_successful_steps_not_regenerated_and_failure_stops_until_next_action(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);stages=iter([('text',None),('translation-en-US',None)]);client=Mock()
   def execute(topic,stage,*args):
    if stage.startswith('translation'):raise ValueError('bad translation')
    return {'okay':True}
   with patch.object(f,'next_stage',side_effect=lambda *_:next(stages)),patch.object(f,'run_stage',side_effect=execute) as run:
    r=f.worker(t,h,d,o,e,lambda *a,**k:client)
   self.assertEqual(r['status'],'stage_failed');self.assertEqual(run.call_count,2)
   e['GITHUB_RUN_ID']='101'
   with patch.object(f,'next_stage',side_effect=[('translation-en-US',None),('publish',None)]),patch.object(f,'run_stage',return_value={'okay':True}) as run:
    r=f.worker(t,h,d,o,e,lambda *a,**k:client)
   self.assertEqual(r['status'],'publication_ready');self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[1],'translation-en-US');self.assertEqual(f.state(o/'new'/t['id'],'text')['attempts'],1)
 def test_image_requires_actual_image_capability_not_75_text_passes(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);factory=Mock()
   with patch.object(f,'next_stage',return_value=('image-1',None)),patch('automation.agri_v2.recovery.circuit_open',return_value=False):r=f.worker(t,h,d,o,e,factory)
   self.assertEqual(r['status'],'capability_required');self.assertEqual(r['kind'],'image');factory.assert_not_called()
 def test_real_image_cooldown_still_precedes_capability_and_spends_no_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);factory=Mock()
   with patch.object(f,'next_stage',return_value=('image-1',None)),patch('automation.agri_v2.recovery.circuit_open',return_value=True):r=f.worker(t,h,d,o,e,factory)
   self.assertEqual(r['status'],'stage_deferred');self.assertEqual(r['reason'],'provider_cooldown');factory.assert_not_called();self.assertEqual(f.state(o/'new'/t['id'],'image-1')['attempts'],0)
 def test_rejected_legacy_image_is_archived_not_destroyed(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);image=folder/'image-1.webp';image.write_bytes(b'old rejected image');atomic_json(image.with_suffix('.quality.json'),{'status':'reviewed','verdict':{'passed':False}})
   def generate():image.write_bytes(b'new candidate');return {}
   f.attempt(folder,'image-1','1',generate,f.stage_outputs(folder,'image-1'))
   self.assertEqual((folder/'lifecycle/image-1/rejected/0/image-1.webp').read_bytes(),b'old rejected image');self.assertEqual(image.read_bytes(),b'new candidate')
 def test_run_bound_reservations_allow_new_action_not_same_request_identity(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td)
   self.assertIsNotNone(reserve('lifecycle','family-lifecycle-run-100',e,put_fn=lambda _:True))
   with self.assertRaises(ValueError):reserve('lifecycle','family-lifecycle-run-99',e,put_fn=lambda _:True)
   self.assertIsNone(reserve('lifecycle','family-lifecycle-run-100',e,put_fn=lambda _:False))
 def test_publisher_rechecks_all_gates_instead_of_trusting_worker_status(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);wp=Mock()
   with patch.object(f,'next_stage',return_value=('blocked','specialist_evidence_required')):r=f.publish_ready(wp,t,d,o)
   self.assertEqual(r['status'],'not_publication_ready');wp.publish.assert_not_called()
 def test_coordinator_20_workers_and_single_serial_publisher(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);topics=[dict(t,id='agri-'+format(i,'012x'),family_id='family-'+str(i+1).zfill(2)) for i in range(20)];barrier=threading.Barrier(20);wp=Mock();inventory={'source_generated_at':utcnow(),'scope':'all public posts','records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]};wp.inventory.return_value=inventory
   def worker(topic,workspace,db,*args):
    with lease(db,'text',SLOTS,topic['id']):barrier.wait(timeout=10)
    wd=workspace/topic['id']/'data';wo=workspace/topic['id']/'out';return topic['id'],wd,wo,{'topic_id':topic['id'],'status':'publication_ready'}
   thread_ids=[]
   def publish(wp,topic,*args):thread_ids.append(threading.get_ident());return {'published_posts':1,'public_verified':True}
   with patch.object(f,'allocate',return_value={}),patch.object(f,'assigned_topics',return_value=topics),patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch.object(f,'next_stage',return_value=('publish',None)),patch.object(f,'publish_ready',side_effect=publish):
    r=f.run(e,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   self.assertEqual(r['pool']['peak_text_leases'],20);self.assertEqual(r['published_posts'],20);self.assertEqual(len(set(thread_ids)),1);self.assertEqual(len(r['results']),20)
 def test_replayed_action_does_not_call_workers_or_wordpress(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);worker=Mock();wp=Mock();r=f.run(e,d,o,worker_fn=worker,wp_factory=wp,reserve_fn=lambda *_:None);self.assertEqual(r['status'],'lifecycle_already_reserved');wp.assert_not_called();worker.assert_not_called()
 def test_fully_validated_payload_is_the_only_published_content(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);folder=o/'new'/t['id'];brief={'slug':'beans-storage','publish_authorized':True};article={'title':t['title'],'content_html':'<p>Validated body</p>','excerpt':'Validated excerpt','faq':[]};atomic_json(d/'briefs'/(t['id']+'.json'),brief)
   folder.mkdir(parents=True);(folder/'image-1.webp').write_bytes(b'one');(folder/'image-2.webp').write_bytes(b'two');wp=Mock();wp.inventory.return_value={'source_generated_at':utcnow(),'scope':'all public posts','records':[{'id':2,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]};wp.publish.return_value={'post_id':20,'public_verified':True}
   with patch.object(f,'next_stage',return_value=('publish',None)),patch.object(f,'article_checked',return_value=article),patch('automation.agri_v2.image_quality.require_all'),patch.object(f,'family_complete',return_value=True):r=f.publish_ready(wp,t,d,o)
   self.assertEqual(r['status'],'family_complete');self.assertTrue(wp.publish.call_args.kwargs['authorized']);payload=load_json(folder/'wordpress-draft-payload.json');self.assertEqual(payload['content'],article['content_html']);self.assertEqual(payload['slug'],brief['slug'])
 def test_changed_saved_payload_blocks_before_wordpress_write(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);folder=o/'new'/t['id'];brief={'slug':'beans-storage','publish_authorized':True};article={'title':t['title'],'content_html':'<p>Valid</p>','excerpt':'Valid','faq':[]};atomic_json(d/'briefs'/(t['id']+'.json'),brief);atomic_json(folder/'wordpress-draft-payload.json',{'content':'tampered'})
   wp=Mock();wp.inventory.return_value={'source_generated_at':utcnow(),'scope':'all public posts','records':[{'id':2,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   with patch.object(f,'next_stage',return_value=('publish',None)),patch.object(f,'article_checked',return_value=article),patch('automation.agri_v2.image_quality.require_all'),self.assertRaises(f.StageBlocked):f.publish_ready(wp,t,d,o)
   wp.publish.assert_not_called()
 def test_real_checkpoint_flow_resumes_images_without_redrafting_text(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);folder=o/'new'/t['id'];brief={'publish_authorized':True};atomic_json(d/'briefs'/(t['id']+'.json'),brief);article={'title':t['title'],'content_html':'<p>Valid source-grounded article</p>','excerpt':'Valid source-grounded excerpt','faq':[]};client=Mock();client.text.return_value=article
   def valid(path,*_):
    if not path.with_suffix('.quality.json').exists():raise ValueError('no QA')
    if load_json(path.with_suffix('.quality.json'))['verdict']['passed'] is not True:raise ValueError('rejected')
    return {}
   def review(client,path,*_):atomic_json(path.with_suffix('.quality.json'),{'status':'reviewed','verdict':{'passed':True}})
   with patch.object(f,'check_brief'),patch.object(f,'validate_article'),patch.object(f,'validate_for_publication'),patch.object(f,'normalize_article',side_effect=lambda x,*_:x),patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch('automation.agri_v2.image_quality.valid_record',side_effect=valid),patch('automation.agri_v2.image_quality.ensure_review',side_effect=review),patch('automation.agri_v2.media_policy.generate_role',return_value=b'validated format image') as generate:
    r=f.worker(t,h,d,o,e,lambda *a,**k:client);self.assertEqual(r['status'],'capability_required');self.assertTrue((folder/'article.json').exists());self.assertEqual(client.text.call_count,1);generate.assert_not_called()
    h['eligible_image_slots']=[SLOTS[1]];e['GITHUB_RUN_ID']='101';r=f.worker(t,h,d,o,e,lambda *a,**k:client)
   self.assertEqual(r['status'],'publication_ready');self.assertEqual(generate.call_count,2);self.assertEqual(client.text.call_count,1);self.assertEqual(f.state(folder,'image-1')['attempts'],1);self.assertEqual(f.state(folder,'vision-2')['attempts'],1)
 def test_real_rejected_second_image_preserves_first_image_and_text(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);folder=o/'new'/t['id'];atomic_json(d/'briefs'/(t['id']+'.json'),{'publish_authorized':True});article={'title':t['title'],'content_html':'<p>Valid</p>','excerpt':'Valid','faq':[]};atomic_json(folder/'article.json',article)
   for n in (1,2):(folder/f'image-{n}.webp').write_bytes(('old-'+str(n)).encode());atomic_json(folder/f'image-{n}.quality.json',{'status':'reviewed','verdict':{'passed':n==1}})
   first=(folder/'image-1.webp').read_bytes();text=(folder/'article.json').read_bytes();h['eligible_image_slots']=[SLOTS[2]]
   def valid(path,*_):
    q=path.with_suffix('.quality.json')
    if not q.exists() or load_json(q)['verdict']['passed'] is not True:raise ValueError('not passed')
   def review(client,path,*_):atomic_json(path.with_suffix('.quality.json'),{'status':'reviewed','verdict':{'passed':True}})
   client=Mock()
   with patch.object(f,'check_brief'),patch.object(f,'validate_article'),patch.object(f,'validate_for_publication'),patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch('automation.agri_v2.image_quality.valid_record',side_effect=valid),patch('automation.agri_v2.image_quality.ensure_review',side_effect=review),patch('automation.agri_v2.media_policy.generate_role',return_value=b'new-second') as generate:r=f.worker(t,h,d,o,e,lambda *a,**k:client)
   self.assertEqual(r['status'],'publication_ready');self.assertEqual(generate.call_count,1);self.assertEqual(generate.call_args.args[2],2);self.assertEqual((folder/'image-1.webp').read_bytes(),first);self.assertEqual((folder/'article.json').read_bytes(),text);self.assertEqual((folder/'lifecycle/image-2/rejected/0/image-2.webp').read_bytes(),b'old-2');client.text.assert_not_called()
 def test_old_translation_receipts_and_raw_outputs_are_preserved_during_retry(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);path=folder/'translations/en-US.raw.json';receipt=folder/'translations/en-US.receipt.json';atomic_json(path,{'bad':True});atomic_json(receipt,{'status':'needs_review','max_calls':1});before=receipt.read_bytes()
   f.attempt(folder,'translation-en-US','100',lambda:{'validated':True},[path]);self.assertEqual(receipt.read_bytes(),before);self.assertTrue((folder/'lifecycle/translation-en-US/rejected/0/en-US.raw.json').exists())
 def test_verified_post_count_includes_translations_without_counting_old_receipts(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);atomic_json(folder/'wordpress-receipt.json',{'post_id':1,'public_verified':True});self.assertEqual(f.verified_posts(folder),{1})
   for lang,i in [('en-US',2),('ar-IQ',3),('tg-TJ',4),('ru-RU',5)]:atomic_json(folder/'translations'/(lang+'.wordpress.json'),{'post_id':i,'public_verified':True})
   self.assertEqual(f.verified_posts(folder),{1,2,3,4,5});atomic_json(folder/'translations/ru-RU.wordpress.json',{'post_id':5,'public_verified':False});self.assertEqual(f.verified_posts(folder),{1,2,3,4})
 def test_coordinator_setup_failure_is_saved_not_reported_as_success(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=self.setup(td);h['checked_at']='2020-01-01T00:00:00+00:00';atomic_json(o/'parallel/health/latest.json',h)
   with patch.object(f,'allocate',return_value={}),patch.object(f,'assigned_topics',return_value=[t]):r=f.run(e,d,o,reserve_fn=lambda *_:{})
   self.assertEqual(r['status'],'completed_with_failures');self.assertIn('coordinator_failure',r);self.assertEqual(load_json(o/'parallel/lifecycle/runs/100/report.json')['status'],'completed_with_failures')
