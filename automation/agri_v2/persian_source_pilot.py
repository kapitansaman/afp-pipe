"""Exactly one existing approved Persian source, same publisher, zero model calls."""
import hashlib,re
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .role_skills_launch import TOPIC,SOURCE_SHA,source_inputs,files_hash,preserved_files
from .wordpress import WordPress,WPError
from .display_units import text as display_text
ID='ops-one-approved-persian-source-single-image-v1'
MAX_MUTATIONS=5

def expected_request():
 return {'version':1,'request_id':ID,'operation':'publish-one-existing-approved-persian-source','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False,'topic_id':TOPIC,'source_article_sha256':SOURCE_SHA,'max_image_calls':0,'max_total_text_calls':0,'max_total_model_calls':0,'max_wordpress_mutations':MAX_MUTATIONS,'max_source_posts':1,'max_total_posts':1,'max_translations':0,'max_media_uploads':1,'required_selected_roles':[1],'change_default_model':False}

class SourceOnlyPublisher(WordPress):
 """The existing WordPress.publish implementation; only locale fan-out is off."""
 def __init__(self,env,root,topic,slug,mutation_limit=5,media_limit=1):
  if (mutation_limit,media_limit) not in ((5,1),(7,2)):raise WPError('Unsupported bounded source media scope')
  super().__init__(env=env);self.root=root;self.topic=topic;self.slug=slug;self.mutation_limit=mutation_limit;self.media_limit=media_limit
 def call(self,path,method='GET',data=None,blob=None,headers=None):
  if method not in ('GET','OPTIONS','POST'):raise WPError('Source pilot method not authorized')
  if method=='POST':
   if path not in ('posts','media') and not re.fullmatch(r'(posts|media)/[1-9][0-9]*',path):raise WPError('Source pilot route not authorized')
   if data and any(k.startswith('afp_') for k in data):raise WPError('Translation mutation forbidden')
   if path=='posts' and (not data or data.get('title')!=display_text(self.topic['title'],'fa-IR') or data.get('slug')!=self.slug or data.get('status')!='draft'):raise WPError('Only exact Persian source draft allowed')
   p=self.root/'wordpress-mutations.json';r=load_json(p) if p.exists() else {'reserved_mutations':0,'created_post_requests':0,'media_upload_requests':0,'history':[]}
   if r['reserved_mutations']>=self.mutation_limit:raise WPError('Source pilot mutation budget exhausted')
   field='created_post_requests' if path=='posts' else 'media_upload_requests' if path=='media' else None
   if field:
    if r[field]>=(1 if field=='created_post_requests' else self.media_limit):raise WPError('Source/media creation limit reached')
    r[field]+=1
   r['reserved_mutations']+=1;r['history'].append({'method':method,'path':path,'at':utcnow()});atomic_json(p,r)
  return super().call(path,method,data,blob,headers)
 def publish_family(self,folder,topic,result):
  return dict(result,translation_publication_skipped=True,source_only=True)

def validate_source(data,out):
 from .family_lifecycle import next_stage,article_checked
 from .image_quality import require_all
 from .image_layout import roles_for
 topic,brief,article,source,folder=source_inputs(data,out);article_checked(folder,topic,brief);require_all(folder,topic,article)
 if roles_for(folder)!=(1,):raise ValueError('Exact retained approved image 1 required')
 stage,reason=next_stage(topic,data,out)
 if stage!='publish':raise ValueError('Existing source is not publication ready')
 # No language gate is bypassed: every unfinished language is already handed off.
 from .language_review_queue import path
 from .multilingual import LANGUAGES
 for lang in LANGUAGES:
  row=load_json(path(folder,lang))
  if row.get('article_sha256')!=SOURCE_SHA or not row.get('primary_finished'):raise ValueError('Unfinished language must remain durably handed off')
 return topic,brief,article,source,folder

def prepare(env,data=DATA,out=OUT,reserve_fn=None,wp_factory=None):
 from .operation_request import authorize
 from .parallel_control import policy,reserve
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Exact source-only pilot admission required')
 policy(env,data);topic,brief,article,source,folder=validate_source(data,out)
 root=out/'parallel/operations'/ID;rp=root/'prepare.json'
 if rp.exists():return {'status':'source_only_pilot_already_reserved','model_calls':0,'published_posts':0}
 if (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'source_only_pilot_already_reserved','model_calls':0,'published_posts':0}
 owners=out/'parallel/families/assignments.json';allowed={'wordpress-receipt.json','wordpress-draft-payload.json','lifecycle-publication-validation.json','lifecycle/publish/state.json'}
 report={'request_id':ID,'operation':expected_request()['operation'],'topic_id':TOPIC,'title':topic['title'],'run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'status':'source_only_pilot_preflight','model_calls':0,'image_calls':0,'published_posts':0,'wordpress_calls':0,'source_only':True,'image_test_passed':True,'max_total_posts':1,'max_translations':0,'selected_image_roles':[1],'schedule_activated':False,'production_activated':False,'attempts_reset':False,'protected_existing_files':{k:v for k,v in files_hash(folder).items() if k not in allowed},'protected_source_files':files_hash(source),'assignment_sha256':hashlib.sha256(owners.read_bytes()).hexdigest(),'provider_circuit_sha256':hashlib.sha256((out/'provider-circuit.json').read_bytes()).hexdigest()};atomic_json(rp,report)
 try:
  wp=SourceOnlyPublisher(env,root,topic,brief['slug']) if wp_factory is None else wp_factory();report['authenticated_preflight']=wp.preflight();report['status']='source_only_pilot_prepared'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  report.update(status='source_only_pilot_blocked',failure=failure_details(exc))
 atomic_json(rp,report);return report

def pilot(env,data=DATA,out=OUT,wp_factory=None):
 from .operation_request import authorize
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('Exact source-only pilot admission required')
 root=out/'parallel/operations'/ID;rp=root/'prepare.json';r=load_json(rp)
 if r.get('run_id')!=env['GITHUB_RUN_ID'] or r.get('status')!='source_only_pilot_prepared':return {'status':'source_only_pilot_not_admitted','published_posts':0}
 topic,brief,article,source,folder=validate_source(data,out)
 gate=root/'pilot-reserved.json'
 if gate.exists():return {'status':'source_only_pilot_already_reserved','published_posts':0}
 atomic_json(gate,{'at':utcnow(),'run_id':env['GITHUB_RUN_ID'],'max_total_posts':1,'max_model_calls':0})
 from .family_lifecycle import attempt,publish_ready
 from .failure_diagnostics import failure_details
 try:
  wp=SourceOnlyPublisher(env,root,topic,brief['slug']) if wp_factory is None else wp_factory()
  result=attempt(folder,'publish',env['GITHUB_RUN_ID'],lambda:publish_ready(wp,topic,data,out),limit=3);r['publication_result']=result
  receipt=load_json(folder/'wordpress-receipt.json') if (folder/'wordpress-receipt.json').exists() else {}
  if result['status']!='stage_completed' or receipt.get('public_verified') is not True:raise ValueError('Source publication not publicly verified')
  r.update(status='source_only_pilot_public_verified',published_posts=result.get('result',{}).get('published_posts',0),source_public_verified=True,post_id=receipt['post_id'],url=receipt['url'])
 except Exception as exc:r.update(status='source_only_pilot_blocked',failure=failure_details(exc))
 finally:
  r.update(wordpress_calls=load_json(root/'wordpress-mutations.json').get('reserved_mutations',0) if (root/'wordpress-mutations.json').exists() else 0,protected_existing_files_unchanged=preserved_files(folder,r['protected_existing_files']),experimental_source_unchanged=preserved_files(source,r['protected_source_files']),assignments_unchanged=hashlib.sha256((out/'parallel/families/assignments.json').read_bytes()).hexdigest()==r['assignment_sha256'],provider_circuit_unchanged=hashlib.sha256((out/'provider-circuit.json').read_bytes()).hexdigest()==r['provider_circuit_sha256'],completed_at=utcnow())
  if not all(r[k] for k in ('protected_existing_files_unchanged','experimental_source_unchanged','assignments_unchanged','provider_circuit_unchanged')):r['status']='source_only_pilot_preservation_failed'
  atomic_json(rp,r)
 return r
