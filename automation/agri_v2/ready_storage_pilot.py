"""One source-pinned nonpublishing pinto-storage pilot; no WordPress client."""
import hashlib,time
from .queue import DATA,OUT,load_json,atomic_json,utcnow,get_topic,age_hours
ID='ops-ready-pinto-storage-nonpublishing-v1'
TOPIC='agri-96d735d5bd11'
SOURCE_SHA='22b8e32191cb20b74d0ea2401f7f8884987dca1892177ca2ac2e56b6d498f92d'
BRIEF_SHA='ce2bf44b3daa066f9cd9fd2ab7e7f88ef380427c725529b3e0df4b1445419134'
MAX_TEXT=14;MAX_IMAGE=1;MAX_TOTAL=15;ROLE=2

def expected_request():
 return {'version':1,'request_id':ID,'operation':'nonpublishing-one-ready-pinto-storage-pilot','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False,'topic_id':TOPIC,'source_article_sha256':SOURCE_SHA,'brief_sha256':BRIEF_SHA,'max_total_text_calls':MAX_TEXT,'max_image_calls':MAX_IMAGE,'max_total_model_calls':MAX_TOTAL,'max_wordpress_mutations':0,'max_source_posts':0,'max_total_posts':0,'max_translations':0,'change_default_model':False}

def source_inputs(data=DATA,out=OUT):
 from .pipeline import digest
 from .family_lifecycle import article_checked
 from .scoped_research import validate_article_review_result
 topic=get_topic('new',TOPIC,data);folder=out/'new'/TOPIC
 brief=load_json(data/'briefs'/(TOPIC+'.json'));article=article_checked(folder,topic,brief)
 if digest(article)!=SOURCE_SHA or digest(brief)!=BRIEF_SHA:raise ValueError('Pinned accepted source changed; no paid call')
 proof=load_json(folder/'article-evidence-review.json')
 if proof.get('article_sha256')!=SOURCE_SHA or proof.get('brief_sha256')!=BRIEF_SHA:raise ValueError('Pinned current article review required')
 validate_article_review_result(article,proof.get('review'))
 return topic,brief,article,folder

def charge(root,kind,model):
 from .parallel_pool import PoolDeferred
 if kind not in ('text','image'):raise ValueError('Unknown pilot capability')
 p=root/'model-calls.json';row=load_json(p) if p.exists() else {'text':0,'image':0,'history':[]}
 if row[kind]>=(MAX_TEXT if kind=='text' else MAX_IMAGE) or row['text']+row['image']>=MAX_TOTAL:raise PoolDeferred('ready_pilot_budget_exhausted')
 row[kind]+=1;row['history'].append({'kind':kind,'model':model,'at':utcnow()});atomic_json(p,row)
 return row

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None):
 from .operation_request import authorize
 from .parallel_control import policy,reserve
 from .provider_diagnostic import active_cooldown
 from .role_skills_launch import files_hash,preserved_files
 from .parallel_pool import initialize,snapshot,routing_counts,record_routing,PoolDeferred
 from .parallel_client import ParallelModelClient
 from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
 from .failure_diagnostics import failure_details
 from .media_policy import generate_role
 from .image_quality import ensure_review,valid_record
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Exact current nonpublishing pilot admission required')
 policy(env,data);topic,brief,article,folder=source_inputs(data,out)
 root=out/'parallel/operations'/ID;rp=root/'prepare.json'
 if rp.exists():return {'status':'ready_pilot_already_reserved','model_calls':0,'image_calls':0,'published_posts':0}
 health=load_json(out/'parallel/health/latest.json')
 if health.get('repository')!='kapitansaman/afp-pipe' or health.get('credential_set_id')!=load_json(data/'parallel-policy.json')['credential_set_id'] or health.get('audit_status')!='completed' or not 0<=age_hours(health['checked_at'])<24 or (health.get('text_model'),health.get('image_model'),health.get('api_base'))!=(TEXT_MODEL,IMAGE_MODEL,API_BASE) or not health.get('eligible_text_slots') or not health.get('eligible_image_slots'):raise ValueError('Fresh independent text and image capacity required')
 if (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'ready_pilot_already_reserved','model_calls':0,'image_calls':0,'published_posts':0}
 assignments=out/'parallel/families/assignments.json';manifest=data/'manifest.json';white=out/'new/agri-621734b38aa9'
 report={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'topic_id':TOPIC,'title':topic['title'],'started_at':utcnow(),'status':'ready_pilot_started','source_article_sha256':SOURCE_SHA,'brief_sha256':BRIEF_SHA,'reused_accepted_text':True,'new_text_generation':False,'selected_image_role':ROLE,'limits':expected_request(),'model_calls':0,'image_calls':0,'wordpress_mutations':0,'published_posts':0,'schedule_activated':False,'production_activated':False,'attempts_reset':False,'protected_source_files':files_hash(folder),'protected_white_bean_files':files_hash(white),'assignment_sha256':hashlib.sha256(assignments.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}
 atomic_json(rp,report)
 if active_cooldown(out):report.update(status='ready_pilot_provider_deferred',completed_at=utcnow());atomic_json(rp,report);return report
 db=root/'pool.sqlite';initialize(db,list(dict.fromkeys(health['eligible_text_slots']+health['eligible_image_slots'])),text_limit=1,image_limit=1,max_calls=MAX_TOTAL,per_worker=MAX_TOTAL,prior_usage=routing_counts(out))
 worker=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=TOPIC,AFP_PARALLEL_FAMILY='nonpublishing-ready-storage-pilot')
 for name in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):worker.pop(name,None)
 class Counted(ParallelModelClient):
  def request(self,kind,path,payload,timeout,attempts=None):
   if active_cooldown(out):raise PoolDeferred('shared_provider_hold')
   if payload.get('model')!=(TEXT_MODEL if kind=='text' else IMAGE_MODEL):raise ValueError('Pilot default model scope mismatch')
   charge(root,kind,payload.get('model'))
   return super().request(kind,path,payload,timeout,attempts=1)
 try:
  client=(Counted if client_factory is None else client_factory)(health,env=worker,allow_calls=True,capabilities=('text','image'))
  client.image_rotation_enabled=False
  target=root/('image-'+str(ROLE)+'.webp')
  # New experimental media only; no original article/stage/review is overwritten.
  target.write_bytes(generate_role(client,topic,ROLE,article))
  ensure_review(client,target,topic,ROLE,article)
  proof=valid_record(target,topic,ROLE,article)
  report.update(status='ready_nonpublishing_pilot_verified',image_test_passed=True,source_test_passed=True,image_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),image_review_policy=proof['review_policy'],image_path=str(target.relative_to(out)))
 except Exception as exc:
  report.update(status='ready_nonpublishing_pilot_needs_review',failure=failure_details(exc),image_test_passed=False)
 finally:
  pool=snapshot(db);record_routing(out,pool);ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'text':0,'image':0}
  report.update(model_calls=ledger['text'],image_calls=ledger['image'],reserved_total_model_calls=pool['model_requests_reserved'],protected_source_unchanged=preserved_files(folder,report['protected_source_files']),white_bean_unchanged=preserved_files(white,report['protected_white_bean_files']),assignments_unchanged=hashlib.sha256(assignments.read_bytes()).hexdigest()==report['assignment_sha256'],manifest_unchanged=hashlib.sha256(manifest.read_bytes()).hexdigest()==report['manifest_sha256'],completed_at=utcnow())
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text_or_image','retry_at_epoch':pool['cooldown_until_epoch'],'at':utcnow(),'reason':'bounded_ready_storage_pilot_provider_hold'})
  if not all(report[k] for k in ('protected_source_unchanged','white_bean_unchanged','assignments_unchanged','manifest_unchanged')):report['status']='ready_pilot_preservation_failed'
  atomic_json(rp,report)
 return report

def result(env,data=DATA,out=OUT):
 from .operation_request import authorize
 if not authorize(env,data):raise ValueError('Current admission required')
 row=load_json(data/'status/owner-operation-admission.json')
 if row['request_id']!=ID:raise ValueError('Exact ready pilot required')
 r=load_json(out/'parallel/operations'/ID/'prepare.json')
 if r.get('run_id')!=env['GITHUB_RUN_ID']:raise ValueError('Current run receipt required')
 return {'status':r['status'],'model_calls':0,'image_calls':0,'published_posts':0,'verification_phase_only':True}
