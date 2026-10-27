"""Three fresh queue topics; finite source-only trial, single original publisher."""
import hashlib,time
from .queue import DATA,OUT,load_json,atomic_json,utcnow,get_topic
from .role_skills_launch import files_hash,preserved_files
from .language_fallback_continuation import wait_for_provider
from .persian_source_pilot import SourceOnlyPublisher
ID='ops-three-fresh-persian-sources-bounded-v1'
TOPICS=('agri-c2b086b47679','agri-96d735d5bd11','agri-3c1cdef82c04')
MAX_TEXT=27;MAX_IMAGE=15;MAX_TOTAL=42;PER_FAMILY=14

REPAIR_ID='ops-three-fresh-persian-sources-repair-v2'
SAVED_ID='ops-three-fresh-persian-sources-saved-validation-v3'
OVERLAP_ID='ops-three-fresh-persian-sources-overlap-input-v4'
FAMILY_CONTEXT_ID='ops-three-fresh-persian-sources-family-context-v5'

def expected_request(request_id=ID):
 if request_id==FAMILY_CONTEXT_ID:
  r=expected_request(OVERLAP_ID);r.update(request_id=FAMILY_CONTEXT_ID,operation='continue-three-persian-sources-with-isolated-family-context',resume_from_request=OVERLAP_ID);return r
 if request_id==OVERLAP_ID:
  r=expected_request(SAVED_ID);r.update(request_id=OVERLAP_ID,operation='fetch-existing-content-and-continue-three-persian-sources',resume_from_request=SAVED_ID);return r
 if request_id==SAVED_ID:
  r=expected_request(REPAIR_ID);r.update(request_id=SAVED_ID,operation='validate-saved-three-persian-source-extractions-within-original-budget',resume_from_request=REPAIR_ID,prior_total_model_calls=6,max_total_text_calls=21,max_total_model_calls=36,max_model_calls_per_family=12);return r
 if request_id==REPAIR_ID:
  r=expected_request();r.update(request_id=REPAIR_ID,operation='repair-three-persian-source-trial-within-original-budget',resume_from_request=ID,prior_total_model_calls=3,original_total_model_budget=42,max_total_text_calls=24,max_total_model_calls=39,max_model_calls_per_family=13);return r
 if request_id!=ID:raise ValueError('Unknown three-source request')
 return {'version':1,'request_id':ID,'operation':'bounded-three-fresh-persian-source-trial','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':3,'enable_schedule':False,'reset_attempts':False,'topic_ids':list(TOPICS),'max_total_text_calls':MAX_TEXT,'max_image_calls':MAX_IMAGE,'max_total_model_calls':MAX_TOTAL,'max_model_calls_per_family':PER_FAMILY,'max_wordpress_mutations':21,'max_source_posts':3,'max_total_posts':3,'max_translations':0,'max_media_uploads':6,'max_provider_wait_seconds':3600,'change_default_model':False}

def admitted(env,data,request_id=ID):
 from .operation_request import authorize
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=request_id:raise ValueError('Exact three-source trial admission required')

def prepare(env,data=DATA,out=OUT,reserve_fn=None,wp_factory=None,request_id=ID):
 admitted(env,data,request_id)
 from .parallel_control import reserve,policy
 policy(env,data);root=out/'parallel/operations'/request_id;rp=root/'prepare.json'
 repair=request_id in (REPAIR_ID,SAVED_ID,OVERLAP_ID,FAMILY_CONTEXT_ID)
 if repair:
  from .three_source_repair import verify_prior
  prior=verify_prior(data,out,request_id)
 if rp.exists():return {'status':'three_source_trial_already_reserved','model_calls':0,'published_posts':0}
 manifest=load_json(data/'manifest.json')
 if manifest.get('counts')!={'new':2905,'merge':593,'hold':370}:raise ValueError('Immutable manifest counts changed')
 assignments=out/'parallel/families/assignments.json';owners=load_json(assignments)
 if any(t in {r['topic_id'] for r in owners['families']} for t in TOPICS):raise ValueError('Never steal active family ownership')
 topics=[get_topic('new',t,data) for t in TOPICS]
 for t in topics:
  if not repair and ((out/'new'/t['id']).exists() or (data/'briefs'/(t['id']+'.json')).exists()):raise ValueError('Fresh trial topics only; never reset exhausted files')
  from .scoped_research import entries_for
  if not entries_for(t,data):raise ValueError('No university discovery lead')
 if (reserve if reserve_fn is None else reserve_fn)('operation',request_id,env) is None:return {'status':'three_source_trial_already_reserved','model_calls':0,'published_posts':0}
 # Store old state bindings, not file contents; no credentials are captured.
 before={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'new').rglob('*') if p.is_file()}
 if repair:before=prior['prior_source_files']
 limits=expected_request(request_id)
 r={'request_id':request_id,'operation':limits['operation'],'run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'status':'three_source_trial_preflight','topic_ids':list(TOPICS),'titles':{t['id']:t['title'] for t in topics},'topic_id':TOPICS[0],'title':'آزمون محدود سه مقاله فارسی','source_only':True,'model_calls':0,'image_calls':0,'published_posts':0,'wordpress_calls':0,'production_activated':False,'schedule_activated':False,'attempts_reset':False,'max_total_model_calls':limits['max_total_model_calls'],'max_model_calls_per_family':limits['max_model_calls_per_family'],'max_total_posts':3,'source_readiness':'University discovery leads, not yet approved briefs or articles','prior_source_files':before,'assignment_sha256':hashlib.sha256(assignments.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),'results':[]};
 if repair:
  from .three_source_repair import original_files
  r.update(resume_from_request=limits['resume_from_request'],prior_model_calls=limits['prior_total_model_calls'],original_operation_files=original_files(out,request_id))
 atomic_json(rp,r)
 try:
  from .wordpress import WordPress
  wp=WordPress(env=env) if wp_factory is None else wp_factory();r['authenticated_preflight']=wp.preflight();inventory=wp.inventory()
  from .pipeline import fresh_inventory
  ip=root/'inventory.json';atomic_json(ip,inventory);fresh_inventory(ip)
  r['inventory_count']=len(inventory['records'])
  # The isolated worker cannot read authenticated WordPress. Fetch complete
  # overlap inputs here, as the standard lifecycle coordinator already does.
  from .scoped_research import prefetch_existing
  r['existing_content_fetch']=prefetch_existing([dict(t,family_id='three-source-trial-'+t['id']) for t in topics],inventory,wp,out,env['GITHUB_RUN_ID'])
  r['status']='three_source_trial_prepared'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  r.update(status='three_source_trial_blocked',failure=failure_details(exc))
 atomic_json(rp,r);return r

def pilot(env,data=DATA,out=OUT,client_factory=None,wp_factory=None,wait_fn=None,worker_fn=None,request_id=ID):
 admitted(env,data,request_id);root=out/'parallel/operations'/request_id;rp=root/'prepare.json';r=load_json(rp)
 limits=expected_request(request_id);max_total=limits['max_total_model_calls'];per_family=limits['max_model_calls_per_family'];max_text=limits['max_total_text_calls'];repair=request_id in (REPAIR_ID,SAVED_ID,OVERLAP_ID,FAMILY_CONTEXT_ID)
 if repair:
  from .three_source_repair import verify_prior
  verify_prior(data,out,request_id)
 if r.get('run_id')!=env['GITHUB_RUN_ID'] or r.get('status')!='three_source_trial_prepared':return {'status':'three_source_trial_not_admitted','published_posts':0}
 gate=root/'pilot-reserved.json'
 if gate.exists():return {'status':'three_source_trial_already_reserved','published_posts':0}
 atomic_json(gate,{'at':utcnow(),'max_total_posts':3,'max_total_model_calls':max_total,'max_model_calls_per_family':per_family})
 def waiting(until):
  if r.get('provider_retry_at_epoch')!=until:print('Respecting existing provider deadline:',int(until),flush=True)
  r.update(status='three_source_trial_provider_waiting',provider_retry_at_epoch=until);atomic_json(rp,r)
 if not (wait_for_provider if wait_fn is None else wait_fn)(out,on_wait=waiting):r.update(status='three_source_trial_wait_limit',completed_at=utcnow());atomic_json(rp,r);return r
 from .parallel_pool import initialize,snapshot,routing_counts,record_routing,PoolDeferred
 from .parallel_client import ParallelModelClient
 from .provider_diagnostic import active_cooldown
 from .failure_diagnostics import failure_details
 from . import family_lifecycle as f
 health=load_json(out/'parallel/health/latest.json');db=root/'pool.sqlite'
 initialize(db,list(dict.fromkeys(health.get('eligible_text_slots',[])+health.get('eligible_image_slots',[]))),text_limit=1,image_limit=1,max_calls=max_total,per_worker=per_family,prior_usage=routing_counts(out))
 class Counted(ParallelModelClient):
  def request(self,kind,path,payload,timeout,attempts=None):
   if active_cooldown(out):raise PoolDeferred('shared_provider_hold')
   if payload.get('model')!=('agnes-2.5-flash' if kind=='text' else 'agnes-image-2.5-flash'):raise ValueError('Trial model scope mismatch')
   p=root/'model-calls.json';row=load_json(p) if p.exists() else {'text':0,'image':0,'history':[]}
   if row[kind]>=(max_text if kind=='text' else MAX_IMAGE) or row['text']+row['image']>=max_total:raise PoolDeferred('trial_model_budget_exhausted')
   row[kind]+=1;row['history'].append({'kind':kind,'topic_id':self.env['AFP_PARALLEL_TOPIC'],'model':payload.get('model'),'at':utcnow()});atomic_json(p,row)
   return super().request(kind,path,payload,timeout,attempts=1)
 try:
  # Same normalized fresh inventory, not a stale queue snapshot.
  atomic_json(data/'parallel-inventory.json',load_json(root/'inventory.json'))
  for ident in TOPICS:
   topic=get_topic('new',ident,data);folder=out/'new'/ident;started=time.monotonic();item={'topic_id':ident,'title':topic['title'],'started_at':utcnow(),'published_posts':0};before=snapshot(db)['model_requests_reserved']
   try:
    if active_cooldown(out) or snapshot(db)['cooldown_until_epoch']>time.time():item.update(status='provider_deferred',model_calls=0)
    else:
     if request_id==REPAIR_ID:
      from .three_source_repair import prepare_topic
      prepare_topic(topic,data,out,env['GITHUB_RUN_ID'])
     worker=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=ident,AFP_PARALLEL_FAMILY='three-source-trial-'+ident)
     clean=dict(worker)
     for k in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):clean.pop(k,None)
     def factory(h,**kwargs):return (Counted if client_factory is None else client_factory)(h,env=clean,**kwargs)
     result=(f.worker if worker_fn is None else worker_fn)(topic,health,data,out,worker,client_factory=factory,source_only=True);item['worker_result']=result;item['status']=result['status']
     if result['status']=='publication_ready':
      brief=load_json(data/'briefs'/(ident+'.json'));pubroot=root/'publish'/ident;pubroot.mkdir(parents=True,exist_ok=True)
      wp=SourceOnlyPublisher(env,pubroot,topic,brief['slug'],mutation_limit=7,media_limit=2) if wp_factory is None else wp_factory(topic,pubroot,brief)
      pub=f.attempt(folder,'publish',env['GITHUB_RUN_ID'],lambda:f.publish_ready(wp,topic,data,out),limit=3);item['publication_result']=pub
      receipt=load_json(folder/'wordpress-receipt.json') if (folder/'wordpress-receipt.json').exists() else {}
      if pub['status']=='stage_completed' and receipt.get('public_verified') is True:item.update(status='source_public_verified',published_posts=pub.get('result',{}).get('published_posts',0),url=receipt['url'],post_id=receipt['post_id'])
      else:item['status']='publication_needs_review'
   except Exception as exc:item.update(status='needs_review',failure=failure_details(exc))
   item.update(duration_seconds=round(time.monotonic()-started,2),model_calls=snapshot(db)['model_requests_reserved']-before,completed_at=utcnow());r['results'].append(item);r['published_posts']+=item['published_posts'];atomic_json(rp,r)
  r['status']='three_source_trial_complete' if all(x['status']=='source_public_verified' for x in r['results']) else 'three_source_trial_partial'
 except Exception as exc:r.update(status='three_source_trial_blocked',failure=failure_details(exc))
 finally:
  pool=snapshot(db);record_routing(out,pool);ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'text':0,'image':0};r.update(pool=pool,model_calls=ledger['text'],image_calls=ledger['image'],reserved_total_model_calls=pool['model_requests_reserved'],wordpress_calls=sum(load_json(p).get('reserved_mutations',0) for p in (root/'publish').glob('*/wordpress-mutations.json')),prior_sources_unchanged=preserved_files(out,r['prior_source_files']),assignments_unchanged=hashlib.sha256((out/'parallel/families/assignments.json').read_bytes()).hexdigest()==r['assignment_sha256'],manifest_unchanged=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest()==r['manifest_sha256'],completed_at=utcnow())
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text_or_image','retry_at_epoch':pool['cooldown_until_epoch'],'at':utcnow(),'reason':'three_source_trial_shared_provider_hold'})
  if repair:
   r['original_operation_unchanged']=preserved_files(out,r['original_operation_files']);r['combined_total_model_calls']=limits.get('prior_total_model_calls',0)+ledger['text']+ledger['image']
  review=[x for x in r['results'] if x['status']!='source_public_verified'];atomic_json(out/'parallel/three-source-trial/review-queue.json',{'request_id':request_id,'items':review,'automatic_approval':False,'schedule_enabled':False,'updated_at':utcnow()})
  if not all(r[k] for k in ('prior_sources_unchanged','assignments_unchanged','manifest_unchanged')) or repair and not r['original_operation_unchanged']:r['status']='three_source_trial_preservation_failed'
  atomic_json(rp,r)
 return r
