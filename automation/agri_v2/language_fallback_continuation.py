"""One bounded language-only continuation. Never regenerate images or publish."""
import hashlib,time
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours
from .role_skills_launch import TOPIC,SOURCE_SHA,source_inputs,files_hash,preserved_files
from .image_fallback_verification import ID as PRIOR
ID='ops-image-fallback-language-only-after-cooldown-v1'
MAX_CALLS=16
from .wordpress import WordPress
class ReadOnlyWordPress(WordPress):
 def call(self,path,method='GET',data=None,blob=None,headers=None):
  if method not in ('GET','OPTIONS'):raise ValueError('No WordPress mutation authorized')
  return super().call(path,method,data,blob,headers)

def expected_request():
 return {'version':1,'request_id':ID,'operation':'nonpublishing-language-only-after-provider-cooldown','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False,'topic_id':TOPIC,'source_article_sha256':SOURCE_SHA,'prior_request':PRIOR,'max_image_calls':0,'max_total_text_calls':MAX_CALLS,'max_total_model_calls':MAX_CALLS,'prior_text_calls':1,'max_combined_text_calls':17,'max_combined_model_calls':18,'max_wordpress_mutations':0,'max_source_posts':0,'max_total_posts':0,'max_translation_languages':4,'max_attempts_per_language_this_run':1,'max_provider_wait_seconds':3600,'change_default_model':False}

def wait_for_provider(out,on_wait=lambda until:None,sleep=time.sleep,clock=time.time,max_wait=3600):
 from .provider_diagnostic import active_cooldown
 started=clock()
 while True:
  until=active_cooldown(out)
  if not until:return True
  remaining=until-clock()
  if remaining>max_wait-(clock()-started):return False
  on_wait(until);sleep(min(max(remaining,1),30))

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None,wp_factory=None,wait_fn=None):
 from .operation_request import authorize
 from .parallel_control import policy,reserve
 from . import language_review_queue as q
 from .image_quality import require_all
 from .image_layout import roles_for
 from .multilingual import LANGUAGES,localized_body
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Exact language-only admission required')
 policy(env,data)
 topic,brief,article,source,folder=source_inputs(data,out);require_all(folder,topic,article)
 prior=load_json(out/'parallel/operations'/PRIOR/'prepare.json')
 if prior.get('image_test_passed') is not True or prior.get('translation_test_passed') is not False or (prior.get('model_calls'),prior.get('image_calls'),prior.get('published_posts'))!=(1,1,0):raise ValueError('Partial nonpublishing image test required')
 root=out/'parallel/operations'/ID;rp=root/'prepare.json'
 if rp.exists():return {'status':'language_continuation_already_reserved','model_calls':0,'published_posts':0}
 if (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'language_continuation_already_reserved','model_calls':0,'published_posts':0}
 protected={k:v for k,v in files_hash(folder).items() if not k.startswith(('review-queue/','translations/'))}
 source_before=files_hash(source);prior_before=files_hash(out/'parallel/operations'/PRIOR);owners=out/'parallel/families/assignments.json';owner_sha=hashlib.sha256(owners.read_bytes()).hexdigest()
 queues_before={lang:{k:load_json(q.path(folder,lang)).get(k) for k in ('attempts','model_calls_spent','article_sha256')} for lang in LANGUAGES}
 report={'request_id':ID,'operation':expected_request()['operation'],'run_id':env['GITHUB_RUN_ID'],'topic_id':TOPIC,'title':topic['title'],'started_at':utcnow(),'status':'language_continuation_started','image_test_passed':True,'translation_test_passed':False,'image_result':{'status':'images_ready','roles':list(roles_for(folder)),'fallback_used':len(roles_for(folder))==1},'model_calls':0,'image_calls':0,'wordpress_mutations':0,'published_posts':0,'production_activated':False,'schedule_activated':False,'attempts_reset':False,'native_review_claimed':False,'queues_before':queues_before,'max_total_text_calls':MAX_CALLS,'steps':[]};atomic_json(rp,report)
 def waiting(until):
  if report.get('provider_retry_at_epoch')!=until:print('Waiting for the existing shared provider deadline:',int(until),flush=True)
  report.update(status='language_continuation_provider_waiting',provider_retry_at_epoch=until);atomic_json(rp,report)
 if not (wait_for_provider if wait_fn is None else wait_fn)(out,on_wait=waiting):
  report.update(status='language_continuation_wait_limit',completed_at=utcnow());atomic_json(rp,report);return report
 from .provider_diagnostic import active_cooldown
 if active_cooldown(out):raise ValueError('Provider hold remains; no bypass')
 health=load_json(out/'parallel/health/latest.json')
 if not 0<=age_hours(health['checked_at'])<24:
  report.update(status='language_continuation_fresh_health_required',completed_at=utcnow());atomic_json(rp,report);return report
 from .parallel_pool import initialize,snapshot,routing_counts,record_routing
 from .parallel_client import ParallelModelClient
 from .alternate_reviewer_verification import AlternateDiagnosticClient
 from .parallel_pool import PoolDeferred
 db=root/'pool.sqlite';initialize(db,health.get('eligible_text_slots',[]),text_limit=1,image_limit=1,max_calls=MAX_CALLS,per_worker=MAX_CALLS,prior_usage=routing_counts(out))
 worker=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=TOPIC,AFP_PARALLEL_FAMILY='nonpublishing-language-fallback-continuation')
 for k in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):worker.pop(k,None)
 class Counted(ParallelModelClient):
  def request(self,kind,path,payload,timeout,attempts=None):
   if kind!='text' or payload.get('model') not in ('agnes-2.5-flash','agnes-3.0-flash'):raise ValueError('Text Flash-only continuation')
   if active_cooldown(out):raise PoolDeferred('shared_provider_hold')
   p=root/'model-calls.json';ledger=load_json(p) if p.exists() else {'text':0,'history':[]}
   if ledger['text']>=MAX_CALLS:raise ValueError('Continuation call cap reached')
   ledger['text']+=1;ledger['history'].append({'kind':'text','model':payload.get('model'),'at':utcnow()});atomic_json(p,ledger)
   return super().request(kind,path,payload,timeout,attempts=1)
 class Tajik(Counted):text=AlternateDiagnosticClient.text
 try:
  wp=ReadOnlyWordPress(env=env) if wp_factory is None else wp_factory();me=wp.preflight();schema,_=wp.call('posts',method='OPTIONS');report['authenticated_readonly_preflight']={'passed':me.get('can_publish') is True,'translation_bridge':{'afp_language','afp_source_post_id'}<=set(schema.get('schema',{}).get('properties',{})),'mutations':0}
  if not all(report['authenticated_readonly_preflight'].get(k) for k in ('passed','translation_bridge')):raise ValueError('Read-only preflight failed')
  for lang in LANGUAGES:
   p=q.path(folder,lang);row=load_json(p)
   if q.approved(folder,article,lang):continue
   until=max(active_cooldown(out),snapshot(db)['cooldown_until_epoch'])
   if until>time.time():q.defer_provider(row,p,until);continue
   if not q.due(row):report['steps'].append({'language':lang,'status':'not_due','model_calls':0});continue
   current=(Tajik if lang=='tg-TJ' else Counted) if client_factory is None else client_factory
   client=current(health,env=worker,allow_calls=True,capabilities=('text',))
   if lang=='tg-TJ':client.alternate_model='agnes-3.0-flash';client.declared_models=[]
   report['steps'].append(q.run_item(p,client,data));atomic_json(rp,report)
  q.index(out);require_all(folder,topic,article)
  report['language_results']={lang:{'approved':q.approved(folder,article,lang),'status':load_json(q.path(folder,lang))['status']} for lang in LANGUAGES}
  report['translation_test_passed']=all(r['approved'] for r in report['language_results'].values())
  roles=roles_for(folder);media=[{'index':k,'id':100+k,'url':'https://navar-abyari.ir/test-only-not-uploaded-'+str(k)+'.webp'} for k in roles]
  report['localized_render_preview']={lang:localized_body(load_json(q.target(folder,lang)),media,{lang:[]}).count('<figure') for lang in LANGUAGES if report['language_results'][lang]['approved']}
  if any(n!=max(0,len(roles)-1) for n in report['localized_render_preview'].values()):raise ValueError('Unexpected inline image count')
  report['status']='image_fallback_verification_passed' if report['translation_test_passed'] else 'language_continuation_incomplete'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  report.update(status='language_continuation_incomplete',failure=failure_details(exc))
 finally:
  pool=snapshot(db);record_routing(out,pool);ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'text':0};report.update(pool=pool,model_calls=ledger['text'],reserved_total_model_calls=pool['model_requests_reserved'],protected_existing_files_unchanged=preserved_files(folder,protected),experimental_source_unchanged=preserved_files(source,source_before),prior_operations_unchanged=preserved_files(out/'parallel/operations'/PRIOR,prior_before),assignments_unchanged=hashlib.sha256(owners.read_bytes()).hexdigest()==owner_sha,queues_after={lang:{k:load_json(q.path(folder,lang)).get(k) for k in ('attempts','model_calls_spent','status')} for lang in LANGUAGES},completed_at=utcnow())
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','retry_at_epoch':pool['cooldown_until_epoch'],'at':utcnow(),'reason':'language_only_continuation_provider_backpressure'})
  if not all(report[k] for k in ('protected_existing_files_unchanged','experimental_source_unchanged','prior_operations_unchanged','assignments_unchanged')):report['status']='language_continuation_preservation_failed'
  atomic_json(rp,report)
 return report
