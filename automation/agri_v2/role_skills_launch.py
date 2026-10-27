"""One separately budgeted, source-pinned launch validation; never enables a timer."""
import copy,hashlib,json,os,time
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,utcnow,get_topic
from .pipeline import digest
ID='ops-role-skills-controlled-launch-v1'
TOPIC='agri-b6f7d6bea16b'
SOURCE='ops-tajik-reference-feedback-final-round-v2'
SOURCE_SHA='e2e4b12048e1affeac212fdffc31c347f0c5cd6b7d629d717a213f947c484e73'
MAX_TEXT=19;MAX_IMAGE=3;MAX_CALLS=22;MAX_WP=15

def expected_request():
 return {'version':1,'request_id':ID,'operation':'role-skills-controlled-launch','authorized':True,'max_text_health_calls':0,'max_image_health_calls':1,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False,'max_total_text_calls':MAX_TEXT,'max_image_calls':MAX_IMAGE,'max_total_model_calls':MAX_CALLS,'max_wordpress_mutations':MAX_WP,'max_source_posts':1,'max_translations':4,'max_total_posts':5,'topic_id':TOPIC,'source_request':SOURCE,'source_article_sha256':SOURCE_SHA,'separate_launch_budget':True,'change_default_model':False}

def files_hash(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
def preserved_files(folder,before):return all((folder/name).is_file() and hashlib.sha256((folder/name).read_bytes()).hexdigest()==sha for name,sha in before.items())
def admission(env,data):
 from .operation_request import authorize
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Current role-skills launch admission required')
def source_inputs(data=DATA,out=OUT):
 from .pipeline import check_brief,validate_article,validate_for_publication
 from .scoped_research import validate_article_review_result
 topic=get_topic('new',TOPIC,data);brief=load_json(data/'briefs'/(TOPIC+'.json'));folder=out/'parallel/writer-verification'/SOURCE/TOPIC;article=load_json(folder/'article.json');proof=load_json(folder/'article-evidence-review.json')
 if digest(article)!=SOURCE_SHA or proof.get('article_sha256')!=SOURCE_SHA or proof.get('brief_sha256')!=digest(brief):raise ValueError('Pinned source/evidence changed')
 check_brief(topic,brief);validate_article(article,topic,brief);validate_for_publication(article);validate_article_review_result(article,proof.get('review'))
 from .role_skills import ROLES,pack
 if any(pack(r,data=data) is None for r in ROLES) or pack('translator','tg-TJ',data) is None:raise ValueError('Required role packs missing')
 dest=out/'new'/TOPIC
 if (dest/'article.json').exists() and load_json(dest/'article.json')!=article:raise ValueError('Never overwrite an existing different production article')
 return topic,brief,article,folder,dest

def prepare(env,data=DATA,out=OUT,reserve_fn=None,image_fn=None,readiness_fn=None):
 admission(env,data)
 from .parallel_control import reserve,policy
 policy(env,data);topic,brief,article,source,dest=source_inputs(data,out)
 root=out/'parallel/operations'/ID;rp=root/'prepare.json'
 if rp.exists():return {'status':'launch_already_reserved','model_calls':0,'published_posts':0}
 if (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'launch_already_reserved','model_calls':0,'published_posts':0}
 from .production_readiness import run as readiness
 check=readiness if readiness_fn is None else readiness_fn
 report={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'topic_id':TOPIC,'operation':'role-skills-controlled-launch','title':topic['title'],'source_request':SOURCE,'status':'launch_preflight_started','max_total_text_calls':MAX_TEXT,'max_image_calls':MAX_IMAGE,'max_total_model_calls':MAX_CALLS,'max_wordpress_mutations':MAX_WP,'model_calls':0,'image_calls':0,'wordpress_calls':0,'published_posts':0,'schedule_activated':False,'attempts_reset':False,'separate_launch_budget':True,'prior_experimental_calls_unchanged':7,'prior_experimental_repairs_unchanged':2,'source_sha256':SOURCE_SHA,'steps':[],'protected_existing_files':files_hash(dest),'protected_source_files':files_hash(source),'assignment_sha256':hashlib.sha256((out/'parallel/families/assignments.json').read_bytes()).hexdigest()}
 atomic_json(rp,report)
 before=check(data,out);report['readiness_before']=before
 required=['fresh_text_capacity','authenticated_publisher','translation_bridge','lifecycle_enabled']
 if not all(before['gates'][k]['passed'] for k in required):report.update(status='launch_prerequisites_blocked',completed_at=utcnow());atomic_json(rp,report);return report
 if not before['gates']['fresh_image_capacity']['passed']:
  from .operation_request import image_capability
  report['image_probe']=(image_capability if image_fn is None else image_fn)(env,data,out,request_id=ID);report['image_calls']=report['image_probe'].get('image_calls',0)
 after=check(data,out);report['readiness_after']=after
 report.update(status='role_skills_launch_prepared' if all(after['gates'][k]['passed'] for k in required+['fresh_image_capacity']) else 'launch_prerequisites_blocked',completed_at=utcnow());atomic_json(rp,report);return report

class BoundedPublisher:
 """Delegate to the original single publisher; reserve each mutation before sending."""
 @staticmethod
 def create(env,root):
  from .wordpress import WordPress
  class WP(WordPress):
   def call(self,path,method='GET',data=None,blob=None,headers=None):
    if method not in ('GET','OPTIONS','POST'):raise ValueError('Launch mutation method forbidden')
    if method=='POST':
     p=root/'wordpress-mutations.json';row=load_json(p) if p.exists() else {'reserved_mutations':0,'created_post_requests':0,'history':[]}
     if row['reserved_mutations']>=MAX_WP:raise ValueError('Launch WordPress mutation budget exhausted')
     if path=='posts':
      if row['created_post_requests']>=5:raise ValueError('One source plus four translations only')
      row['created_post_requests']+=1
     row['reserved_mutations']+=1;row['history'].append({'path':path,'method':method,'at':utcnow()});atomic_json(p,row)
    return super().call(path,method,data,blob,headers)
  return WP(env=env)

def pilot(env,data=DATA,out=OUT,client_factory=None,wp_factory=None):
 admission(env,data);root=out/'parallel/operations'/ID;rp=root/'prepare.json';report=load_json(rp)
 if report.get('run_id')!=env['GITHUB_RUN_ID'] or report.get('status')!='role_skills_launch_prepared':return {'status':'launch_pilot_not_admitted','published_posts':0,'model_calls':0}
 topic,brief,article,source,folder=source_inputs(data,out)
 if (root/'pilot-reserved.json').exists():return {'status':'launch_pilot_already_reserved','model_calls':0,'published_posts':0}
 atomic_json(root/'pilot-reserved.json',{'run_id':env['GITHUB_RUN_ID'],'at':utcnow(),'attempts_reset':False})
 from .parallel_pool import initialize,snapshot,routing_counts,record_routing
 from .parallel_client import ParallelModelClient
 from .alternate_reviewer_verification import AlternateDiagnosticClient
 from .role_skills import RoleClient,pack,ROLES
 from .failure_diagnostics import failure_details
 health=load_json(out/'parallel/health/latest.json');db=root/'pool.sqlite';probe_calls=report.get('image_calls',0)
 if db.exists():raise ValueError('Never replay an uncertain launch pool')
 initialize(db,list(dict.fromkeys(health.get('eligible_text_slots',[])+health.get('eligible_image_slots',[]))),text_limit=1,image_limit=1,max_calls=MAX_CALLS-probe_calls,per_worker=MAX_CALLS-probe_calls,prior_usage=routing_counts(out))
 worker_env=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=TOPIC,AFP_PARALLEL_FAMILY='separately-budgeted-role-skills-launch')
 for k in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):worker_env.pop(k,None)
 class Counted(ParallelModelClient):
  def request(self,kind,path,payload,timeout,attempts=None):
   ledger=root/'model-calls.json';row=load_json(ledger) if ledger.exists() else {'text':0,'image':0,'history':[]}
   if row[kind]>=(MAX_TEXT if kind=='text' else MAX_IMAGE-probe_calls):raise ValueError('Launch capability budget exhausted')
   row[kind]+=1;row['history'].append({'kind':kind,'model':payload.get('model'),'at':utcnow()});atomic_json(ledger,row)
   return super().request(kind,path,payload,timeout,attempts)
 class Tajik(Counted):
  text=AlternateDiagnosticClient.text
 report.update(status='launch_pilot_started',pilot_started_at=utcnow(),models={'default_text':'agnes-2.5-flash','tajik_text':'agnes-3.0-flash','image':'agnes-image-2.5-flash'},role_skill_sha256={r:pack(r,data=data)['sha256'] for r in sorted(ROLES)},tajik_skill_sha256=pack('translator','tg-TJ',data)['sha256']);atomic_json(rp,report);stage='source_review'
 try:
  stage='client_admission'
  client=(Counted if client_factory is None else client_factory)(health,env=worker_env,allow_calls=True,capabilities=('text','image'));client.image_rotation_enabled=False
  stage='source_review'
  from .scoped_research import review_article
  from .family_lifecycle import attempt,run_stage,publish_ready
  # Re-audit the pinned source with the new reviewer. No exhausted text attempt is reset.
  reviewed=root/'source-audit';reviewed.mkdir(parents=True,exist_ok=True)
  review_article(topic,article,brief,reviewed,RoleClient(client,'evidence-reviewer',data=data))
  for name,value in [('article.json',article),('article-evidence-review.json',load_json(reviewed/'article-evidence-review.json'))]:
   p=folder/name
   if p.exists() and load_json(p)!=value:raise ValueError('Existing production evidence must not be overwritten')
   atomic_json(p,value)
  atomic_json(folder/'role-skill-source-adoption.json',{'request_id':ID,'source_request':SOURCE,'article_sha256':SOURCE_SHA,'source_audit':str(reviewed.relative_to(out)),'preserved_text_attempts':load_json(folder/'lifecycle/text/state.json').get('attempts'),'at':utcnow()})
  report['steps'].append({'stage':'source_review','status':'passed'});atomic_json(rp,report)
  for kind in (1,2):
   for name in ('image-'+str(kind),'vision-'+str(kind)):
    stage=name;result=attempt(folder,name,env['GITHUB_RUN_ID'],lambda n=name:run_stage(topic,n,client,data,out),limit=3);report['steps'].append(result);atomic_json(rp,report)
    if result['status']!='stage_completed':raise ValueError('Launch image or vision stage not validated')
  from . import language_review_queue as q
  from .multilingual import LANGUAGES
  for lang in LANGUAGES:
   stage='language-'+lang;row=q.ensure(topic,article,folder,lang)
   if lang=='tg-TJ' and row['attempts']==0:
    prior=load_json(source/'review-queue/tg-TJ.json');row.update(attempts=prior['attempts'],model_calls_spent=prior['model_calls_spent'],pending_issues=prior.get('pending_issues',[]),next_attempt_at=utcnow(),status='waiting',primary_finished=True)
    row['history'].append({'event':'prior_experimental_history_imported_without_reset','previous_attempts':prior['attempts'],'previous_model_calls':prior['model_calls_spent'],'new_scope':ID,'at':utcnow()});atomic_json(q.path(folder,lang),row)
    atomic_json(folder/'review-queue/candidate-tg-TJ.json',{'article_sha256':SOURCE_SHA,'raw':load_json(source/'translations/tg-TJ.raw.json')})
   if snapshot(db)['cooldown_until_epoch']>time.time():
    row=load_json(q.path(folder,lang));row['primary_finished']=True;q.defer(row,q.path(folder,lang),'provider_cooldown_after_other_language',data);continue
   current=client
   if lang=='tg-TJ':
    current=(Tajik if client_factory is None else client_factory)(health,env=worker_env,allow_calls=True,capabilities=('text',));current.alternate_model='agnes-3.0-flash';current.declared_models=[]
   result=q.run_item(q.path(folder,lang),current,data);row=load_json(q.path(folder,lang));row['primary_finished']=True;atomic_json(q.path(folder,lang),row);report['steps'].append(result);atomic_json(rp,report)
  q.index(out);stage='publication';wp=BoundedPublisher.create(env,root) if wp_factory is None else wp_factory()
  result=attempt(folder,'publish',env['GITHUB_RUN_ID'],lambda:publish_ready(wp,topic,data,out),limit=3);report['publication_result']=result
  if result['status']!='stage_completed' or not load_json(folder/'wordpress-receipt.json').get('public_verified'):raise ValueError('Launch source not publicly verified')
  report.update(status='controlled_launch_published',published_posts=result.get('result',{}).get('published_posts',0),source_public_verified=True,full_family_complete=q.published(folder,'tg-TJ') and all(q.published(folder,l) for l in LANGUAGES))
 except Exception as exc:report.update(status='controlled_launch_blocked',failed_stage=stage,failure=failure_details(exc))
 finally:
  pool=snapshot(db);record_routing(out,pool);ledger=load_json(root/'model-calls.json') if (root/'model-calls.json').exists() else {'text':0,'image':0}
  report.update(pool=pool,model_calls=ledger['text'],image_calls=probe_calls+ledger['image'],reserved_total_model_calls=probe_calls+pool['model_requests_reserved'],wordpress_calls=load_json(root/'wordpress-mutations.json').get('reserved_mutations',0) if (root/'wordpress-mutations.json').exists() else 0,protected_existing_files_unchanged=preserved_files(folder,report['protected_existing_files']),experimental_source_unchanged=preserved_files(source,report['protected_source_files']),assignments_unchanged=hashlib.sha256((out/'parallel/families/assignments.json').read_bytes()).hexdigest()==report['assignment_sha256'],completed_at=utcnow(),schedule_activated=False)
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text_or_image','retry_at_epoch':pool['cooldown_until_epoch'],'at':utcnow(),'reason':'role_skills_launch_provider_backpressure'})
  if not all(report.get(k) for k in ('protected_existing_files_unchanged','experimental_source_unchanged','assignments_unchanged')):report['status']='launch_preservation_check_failed'
  atomic_json(rp,report)
 return report
