"""Source-pinned live test, explicitly NO WordPress mutations or activation."""
import hashlib,time
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .role_skills_launch import TOPIC,SOURCE,SOURCE_SHA,source_inputs,files_hash,preserved_files
ID='ops-image-three-corrections-single-fallback-test-v1'
PRIOR='ops-role-skills-image-pair-final-v3'
IMAGE_SHA='e38af7b313f86773a5671757966576a81f83b77ec316063428d13de39271d376'
def expected_request():
 return {'version':1,'request_id':ID,'operation':'nonpublishing-three-image-corrections-single-fallback-test','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False,'topic_id':TOPIC,'source_article_sha256':SOURCE_SHA,'prior_request':PRIOR,'remaining_generation_attempts':1,'max_corrective_rounds':3,'max_total_generation_attempts_per_role':4,'max_image_calls':1,'max_visual_reviews':1,'max_total_text_calls':17,'max_total_model_calls':18,'max_wordpress_mutations':0,'max_source_posts':0,'max_total_posts':0,'change_default_model':False}

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None,wp_factory=None):
 from .operation_request import authorize
 from .parallel_control import policy,reserve
 from . import image_workflow as images
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Exact nonpublishing fallback test admission required')
 policy(env,data)
 if not images.enabled(data):raise ValueError('Image repair policy not enabled')
 topic,brief,article,source,folder=source_inputs(data,out)
 from .family_lifecycle import state
 if (state(folder,'image-2')['attempts'],state(folder,'vision-2')['attempts'])!=(3,3) or hashlib.sha256((folder/'image-2.webp').read_bytes()).hexdigest()!=IMAGE_SHA:raise ValueError('Exact existing three-attempt checkpoint required; never reset/replay')
 from .image_quality import valid_record
 valid_record(folder/'image-1.webp',topic,1,article)
 from .scoped_research import validate_article_review_result
 proof=load_json(folder/'article-evidence-review.json')
 from .pipeline import digest
 if proof.get('article_sha256')!=SOURCE_SHA or proof.get('brief_sha256')!=digest(brief):raise ValueError('Current accepted source proof required')
 validate_article_review_result(article,proof.get('review'))
 root=out/'parallel/operations'/ID;rp=root/'prepare.json'
 if rp.exists() or (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'fallback_test_already_reserved','model_calls':0,'published_posts':0}
 allowed={'image-2.webp','image-2.quality.json','lifecycle/image-2/state.json','lifecycle/vision-2/state.json'}
 prior={rid:files_hash(out/'parallel/operations'/rid) for rid in ['ops-role-skills-controlled-launch-v1','ops-role-skills-image-feedback-continuation-v2',PRIOR]}
 report={'request_id':ID,'operation':'nonpublishing-three-image-corrections-single-fallback-test','run_id':env['GITHUB_RUN_ID'],'topic_id':TOPIC,'title':topic['title'],'source_request':SOURCE,'started_at':utcnow(),'status':'fallback_test_started','max_total_text_calls':17,'max_image_calls':1,'max_total_model_calls':18,'model_calls':0,'image_calls':0,'wordpress_calls':0,'wordpress_mutations':0,'published_posts':0,'schedule_activated':False,'attempts_reset':False,'production_activated':False,'native_review_claimed':False,'protected_existing_files':{k:v for k,v in files_hash(folder).items() if k not in allowed},'protected_source_files':files_hash(source),'protected_prior_operations':prior,'assignment_sha256':hashlib.sha256((out/'parallel/families/assignments.json').read_bytes()).hexdigest(),'steps':[]}
 atomic_json(rp,report)
 from .provider_diagnostic import active_cooldown
 if active_cooldown(out):report.update(status='fallback_test_provider_waiting',completed_at=utcnow());atomic_json(rp,report);return report
 from .parallel_pool import initialize,snapshot,routing_counts,record_routing
 from .parallel_client import ParallelModelClient
 from .alternate_reviewer_verification import AlternateDiagnosticClient
 from .failure_diagnostics import failure_details
 health=load_json(out/'parallel/health/latest.json');db=root/'pool.sqlite';initialize(db,list(dict.fromkeys(health.get('eligible_text_slots',[])+health.get('eligible_image_slots',[]))),text_limit=1,image_limit=1,max_calls=18,per_worker=18,prior_usage=routing_counts(out))
 worker=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=TOPIC,AFP_PARALLEL_FAMILY='nonpublishing-image-fallback-test')
 for k in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):worker.pop(k,None)
 class Counted(ParallelModelClient):
  def request(self,kind,path,payload,timeout,attempts=None):
   p=root/'model-calls.json';r=load_json(p) if p.exists() else {'text':0,'image':0,'history':[]}
   if r[kind]>=(17 if kind=='text' else 1):raise ValueError('Fallback test capability budget exhausted')
   r[kind]+=1;r['history'].append({'kind':kind,'model':payload.get('model'),'at':utcnow()});atomic_json(p,r);return super().request(kind,path,payload,timeout,attempts)
 class Tajik(Counted):text=AlternateDiagnosticClient.text
 try:
  from .wordpress import WordPress
  class ReadOnlyWP(WordPress):
   def call(self,path,method='GET',data=None,blob=None,headers=None):
    if method not in ('GET','OPTIONS'):raise ValueError('No WordPress mutation authorized in this test')
    return super().call(path,method,data,blob,headers)
  wp=ReadOnlyWP(env=env) if wp_factory is None else wp_factory();me=wp.preflight();schema,_=wp.call('posts',method='OPTIONS');report['authenticated_readonly_preflight']={'passed':me.get('can_publish') is True,'translation_bridge':{'afp_language','afp_source_post_id'}<=set(schema.get('schema',{}).get('properties',{})),'mutations':0}
  client=(Counted if client_factory is None else client_factory)(health,env=worker,allow_calls=True,capabilities=('text','image'))
  result=images.advance(client,folder,topic,article,env['GITHUB_RUN_ID'],data);report['image_result']=result;report['steps'].extend(result['steps']);atomic_json(rp,report)
  from . import language_review_queue as q
  from .multilingual import LANGUAGES,localized_body
  for lang in LANGUAGES:
   row=q.ensure(topic,article,folder,lang)
   if lang=='tg-TJ' and row['attempts']==0:
    old=load_json(source/'review-queue/tg-TJ.json');row.update(attempts=old['attempts'],model_calls_spent=old['model_calls_spent'],pending_issues=old.get('pending_issues',[]),status='waiting',primary_finished=True,next_attempt_at=utcnow());row['history'].append({'event':'old_experimental_history_imported_without_reset','prior_attempts':old['attempts'],'prior_calls':old['model_calls_spent'],'scope':ID,'at':utcnow()});atomic_json(q.path(folder,lang),row);atomic_json(folder/'review-queue/candidate-tg-TJ.json',{'article_sha256':SOURCE_SHA,'raw':load_json(source/'translations/tg-TJ.raw.json')})
   if snapshot(db)['cooldown_until_epoch']>time.time():
    row['primary_finished']=True;q.defer(row,q.path(folder,lang),'provider_backpressure',data);continue
   current=client
   if lang=='tg-TJ':current=(Tajik if client_factory is None else client_factory)(health,env=worker,allow_calls=True,capabilities=('text',));current.alternate_model='agnes-3.0-flash';current.declared_models=[]
   item=q.run_item(q.path(folder,lang),current,data);row=load_json(q.path(folder,lang));row['primary_finished']=True;atomic_json(q.path(folder,lang),row);report['steps'].append(item);atomic_json(rp,report)
  q.index(out);report['language_results']={lang:{'approved':q.approved(folder,article,lang),'status':load_json(q.path(folder,lang))['status']} for lang in LANGUAGES}
  report['image_test_passed']=result['status']=='images_ready';report['translation_test_passed']=all(r['approved'] for r in report['language_results'].values())
  if report['image_test_passed']:
   from .image_quality import require_all
   from .image_layout import roles_for
   from .wordpress import illustrated_content
   require_all(folder,topic,article);roles=roles_for(folder);media=[{'index':k,'id':100+k,'url':'https://navar-abyari.ir/test-only-not-uploaded-'+str(k)+'.webp'} for k in roles];body=illustrated_content(article['content_html'],media,topic['crop']);report['source_render_preview']={'selected_roles':list(roles),'inline_figures':body.count('<figure'),'expected_inline_figures':max(0,len(roles)-1),'uploaded':False}
   report['localized_render_preview']={lang:localized_body(load_json(folder/'translations'/(lang+'.json')),media,{lang:[]}).count('<figure') for lang in LANGUAGES if report['language_results'][lang]['approved']}
  report['status']='image_fallback_verification_passed' if report['image_test_passed'] and report['translation_test_passed'] and all(report['authenticated_readonly_preflight'].get(k) for k in ('passed','translation_bridge')) else 'image_fallback_verification_incomplete'
 except Exception as exc:report.update(status='image_fallback_verification_incomplete',failure=failure_details(exc))
 finally:
  pool=snapshot(db);record_routing(out,pool);ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'text':0,'image':0};report.update(pool=pool,model_calls=ledger['text'],image_calls=ledger['image'],reserved_total_model_calls=pool['model_requests_reserved'],protected_existing_files_unchanged=preserved_files(folder,report['protected_existing_files']),experimental_source_unchanged=preserved_files(source,report['protected_source_files']),prior_operations_unchanged=all(preserved_files(out/'parallel/operations'/rid,h) for rid,h in prior.items()),assignments_unchanged=hashlib.sha256((out/'parallel/families/assignments.json').read_bytes()).hexdigest()==report['assignment_sha256'],completed_at=utcnow())
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text_or_image','retry_at_epoch':pool['cooldown_until_epoch'],'at':utcnow(),'reason':'nonpublishing_image_fallback_test_backpressure'})
  if not all(report[k] for k in ('protected_existing_files_unchanged','experimental_source_unchanged','prior_operations_unchanged','assignments_unchanged')):report['status']='fallback_test_preservation_failed'
  atomic_json(rp,report)
 return report
