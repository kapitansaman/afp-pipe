"""Four currently assigned families; at most eight text calls, no image/publisher."""
import hashlib,time,shutil
from .queue import DATA,OUT,load_json,atomic_json,utcnow,get_topic,age_hours
ID='ops-four-assigned-research-eight-text-v1'
FAMILIES={'family-02':'agri-7736a471e8c1','family-11':'agri-3aec9f066bb5','family-16':'agri-7dd8dae22417','family-18':'agri-abd5d9f00442'}
MAX_TEXT=8;PER_FAMILY=2

def expected_request():
 return {'version':1,'request_id':ID,'operation':'research-only-four-assigned-families','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':4,'enable_schedule':False,'reset_attempts':False,'family_topics':FAMILIES,'max_total_text_calls':MAX_TEXT,'max_text_calls_per_family':PER_FAMILY,'max_image_calls':0,'max_wordpress_mutations':0,'max_source_posts':0,'max_total_posts':0,'max_translations':0,'change_default_model':False}

def charge(root,topic,kind,model):
 from .parallel_pool import PoolDeferred
 from .healthcheck import TEXT_MODEL
 if topic not in FAMILIES.values() or kind!='text' or model!=TEXT_MODEL:raise ValueError('Exact text-only assigned-family scope required')
 p=root/'model-calls.json';row=load_json(p) if p.exists() else {'text':0,'image':0,'per_topic':{},'history':[]}
 if row['text']>=MAX_TEXT or row['per_topic'].get(topic,0)>=PER_FAMILY:raise PoolDeferred('bounded_four_family_text_budget_exhausted')
 row['text']+=1;row['per_topic'][topic]=row['per_topic'].get(topic,0)+1;row['history'].append({'topic_id':topic,'kind':'text','model':model,'at':utcnow()});atomic_json(p,row);return row

def permitted(stage):
 return stage in ('research_validate_saved','research_review','existing_content_audit','existing_content_audit_finalize') or stage.startswith('existing_content_audit-')

def local_stage(stage):return stage in ('research_validate_saved','existing_content_audit_finalize')

def advance(topic,env,client,root,data=DATA,out=OUT):
 from . import family_lifecycle as f
 from .provider_diagnostic import active_cooldown
 folder=out/'new'/topic['id'];steps=[];limit=f.settings(data)['max_attempts_per_stage']
 for _ in range(16):
  stage,reason=f.next_stage(topic,data,out)
  if stage=='blocked':return {'status':'family_blocked','next_stage':stage,'reason':reason,'steps':steps}
  if not permitted(stage):return {'status':'research_ready' if stage not in ('complete',) else 'already_complete','next_stage':stage,'steps':steps}
  ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'text':0,'per_topic':{}}
  if not local_stage(stage) and (ledger['text']>=MAX_TEXT or ledger['per_topic'].get(topic['id'],0)>=PER_FAMILY):return {'status':'bounded_checkpoint_saved','next_stage':stage,'steps':steps}
  if not local_stage(stage) and active_cooldown(out):return {'status':'provider_deferred','next_stage':stage,'steps':steps}
  result=f.attempt(folder,stage,env['GITHUB_RUN_ID'],lambda:f.run_stage(topic,stage,client,data,out),outputs=f.stage_outputs(folder,stage),limit=limit)
  steps.append(result)
  if result['status']!='stage_completed':return {'status':result['status'],'next_stage':stage,'steps':steps}
 return {'status':'local_step_limit','next_stage':f.next_stage(topic,data,out)[0],'steps':steps}

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None,wp_factory=None,advance_fn=None):
 from .operation_request import authorize
 from .parallel_control import policy,reserve
 from .role_skills_launch import files_hash,preserved_files
 from .parallel_pool import initialize,snapshot,routing_counts,record_routing,PoolDeferred
 from .parallel_client import ParallelModelClient
 from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
 from .provider_diagnostic import active_cooldown
 from .failure_diagnostics import failure_details
 from .scoped_research import prefetch_existing,content_digest
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Exact current four-family research admission required')
 policy(env,data);owners=load_json(out/'parallel/families/assignments.json');current={x['family_id']:x['topic_id'] for x in owners['families']}
 if any(current.get(k)!=v for k,v in FAMILIES.items()):raise ValueError('Assigned topic changed; never steal or reassign a family')
 root=out/'parallel/operations'/ID;rp=root/'prepare.json'
 if rp.exists():return {'status':'four_family_research_already_reserved','model_calls':0,'image_calls':0,'published_posts':0}
 health=load_json(out/'parallel/health/latest.json')
 if health.get('repository')!='kapitansaman/afp-pipe' or health.get('credential_set_id')!=load_json(data/'parallel-policy.json')['credential_set_id'] or health.get('audit_status')!='completed' or not 0<=age_hours(health['checked_at'])<24 or (health.get('text_model'),health.get('image_model'),health.get('api_base'))!=(TEXT_MODEL,IMAGE_MODEL,API_BASE) or not health.get('eligible_text_slots'):raise ValueError('Fresh existing text capability required; no new health audit authorized')
 if (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'four_family_research_already_reserved','model_calls':0,'image_calls':0,'published_posts':0}
 selected=set(FAMILIES.values());protected={}
 for folder in (out/'new').iterdir():
  if folder.is_dir() and folder.name not in selected:protected[folder.name]=files_hash(folder)
 prior={}
 for ident in selected:
  folder=out/'new'/ident;prior[ident]=files_hash(folder);shutil.copytree(folder,root/'prior'/ident)
  bp=data/'briefs'/(ident+'.json')
  if bp.exists():raise ValueError('Do not overwrite an existing approved brief in research-only trial')
 assignment_path=out/'parallel/families/assignments.json';manifest=data/'manifest.json'
 r={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'four_family_research_started','started_at':utcnow(),'family_topics':FAMILIES,'limits':expected_request(),'results':[],'model_calls':0,'image_calls':0,'wordpress_mutations':0,'published_posts':0,'schedule_activated':False,'production_activated':False,'attempts_reset':False,'assignment_sha256':hashlib.sha256(assignment_path.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'protected_other_topics':protected,'prior_selected_files':prior};atomic_json(rp,r)
 if active_cooldown(out):r.update(status='four_family_research_provider_deferred',completed_at=utcnow());atomic_json(rp,r);return r
 db=root/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=MAX_TEXT,per_worker=PER_FAMILY,prior_usage=routing_counts(out))
 class Counted(ParallelModelClient):
  def request(self,kind,path,payload,timeout,attempts=None):
   if active_cooldown(out):raise PoolDeferred('shared_provider_hold')
   charge(root,self.env['AFP_PARALLEL_TOPIC'],kind,payload.get('model'))
   return super().request(kind,path,payload,timeout,attempts=1)
 try:
  from .wordpress import WordPress
  class ReadOnlyWP(WordPress):
   def call(self,path,method='GET',data=None,blob=None,headers=None):
    if method not in ('GET','OPTIONS'):raise ValueError('No WordPress mutation authorized')
    return super().call(path,method,data,blob,headers)
  wp=ReadOnlyWP(env=env) if wp_factory is None else wp_factory()
  wp.preflight();inventory=wp.inventory()
  from .pipeline import fresh_inventory
  atomic_json(root/'inventory.json',inventory);fresh_inventory(root/'inventory.json')
  # Keep the fresh full-content fetch isolated. A changed comparison corpus is
  # not permission to delete old audits or silently reuse their approvals.
  topics=[dict(get_topic('new',ident,data),family_id=fid) for fid,ident in FAMILIES.items()]
  r['existing_content_fetch']=prefetch_existing(topics,inventory,wp,root/'live-inputs',env['GITHUB_RUN_ID'],data=data)
  ip=data/'parallel-inventory.json'
  if ip.exists():shutil.copyfile(ip,root/'prior-parallel-inventory.json')
  atomic_json(ip,inventory)
  for topic in topics:
   ident=topic['id'];item={'family_id':topic['family_id'],'topic_id':ident,'title':topic['title'],'started_at':utcnow()}
   try:
    old=load_json(out/'new'/ident/'lifecycle-evidence/existing-content.json');fresh=load_json(root/'live-inputs/new'/ident/'lifecycle-evidence/existing-content.json')
    if content_digest(old)!=content_digest(fresh):item.update(status='existing_content_changed_requires_reaudit',model_calls=0)
    elif active_cooldown(out) or snapshot(db)['cooldown_until_epoch']>time.time():item.update(status='provider_deferred',model_calls=0)
    else:
     clean=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=ident,AFP_PARALLEL_FAMILY=topic['family_id'])
     for key in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):clean.pop(key,None)
     client=(Counted if client_factory is None else client_factory)(health,env=clean,allow_calls=True,capabilities=('text',));client.image_rotation_enabled=False
     item.update((advance if advance_fn is None else advance_fn)(topic,clean,client,root,data,out))
   except Exception as exc:item.update(status='family_needs_review',failure=failure_details(exc))
   ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'per_topic':{}}
   item.update(model_calls=ledger['per_topic'].get(ident,0),completed_at=utcnow());r['results'].append(item);atomic_json(rp,r)
  r['status']='four_family_research_complete' if all(x['status'] in ('research_ready','bounded_checkpoint_saved','already_complete') for x in r['results']) else 'four_family_research_partial'
 except Exception as exc:r.update(status='four_family_research_blocked',failure=failure_details(exc))
 finally:
  pool=snapshot(db);record_routing(out,pool);ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'text':0,'image':0}
  r.update(model_calls=ledger['text'],image_calls=ledger['image'],reserved_total_model_calls=pool['model_requests_reserved'],other_topics_unchanged=all(preserved_files(out/'new'/ident,h) for ident,h in protected.items()),prior_selected_snapshots_unchanged=all(preserved_files(root/'prior'/ident,h) for ident,h in prior.items()),assignments_unchanged=hashlib.sha256(assignment_path.read_bytes()).hexdigest()==r['assignment_sha256'],manifest_unchanged=hashlib.sha256(manifest.read_bytes()).hexdigest()==r['manifest_sha256'],completed_at=utcnow())
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','retry_at_epoch':pool['cooldown_until_epoch'],'at':utcnow(),'reason':'bounded_four_family_research_provider_hold'})
  if not all(r[k] for k in ('other_topics_unchanged','prior_selected_snapshots_unchanged','assignments_unchanged','manifest_unchanged')):r['status']='four_family_research_preservation_failed'
  atomic_json(rp,r)
 return r

def result(env,data=DATA,out=OUT):
 from .operation_request import authorize
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Exact current research admission required')
 r=load_json(out/'parallel/operations'/ID/'prepare.json')
 if r.get('run_id')!=env['GITHUB_RUN_ID']:raise ValueError('Current run receipt required')
 return {'status':r['status'],'model_calls':0,'image_calls':0,'published_posts':0,'verification_phase_only':True}
