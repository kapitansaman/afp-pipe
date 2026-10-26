"""Owner-requested one-shot Actions operation. No fabricated workflow_dispatch event."""
import argparse,json,os,subprocess,urllib.request
from .queue import DATA,OUT,ROOT,atomic_json,load_json,utcnow,age_hours
ID='ops-97-readiness-pilot-v1'
CONTINUATION_ID='ops-97-pilot-citation-v2'
GROUNDED_ID='ops-97-pilot-grounded-v3'
SUPPLEMENT_ID='ops-97-pilot-editorial-v4'
FULL_QUEUE_ID='ops-full-queue-routes-research-v1'
PATH='.github/afp-operations/request.json'
WORKFLOW='kapitansaman/afp-pipe/.github/workflows/afp-owner-operation.yml@refs/heads/main'

def context(env):
 return env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')=='kapitansaman/afp-pipe' and env.get('GITHUB_EVENT_NAME')=='push' and env.get('GITHUB_REF')=='refs/heads/main' and env.get('GITHUB_WORKFLOW_REF')==WORKFLOW and str(env.get('GITHUB_RUN_ID','')).isdigit() and len(env.get('GITHUB_SHA',''))==40

def validate_request(req):
 rid=req.get('request_id') if isinstance(req,dict) else None
 if rid not in (ID,CONTINUATION_ID,GROUNDED_ID,SUPPLEMENT_ID,FULL_QUEUE_ID):raise ValueError('Unknown bounded owner request')
 expected={'version':1,'request_id':rid,'operation':'readiness-audit-image-pilot','authorized':True,'max_text_health_calls':97 if rid==ID else 0,'max_image_health_calls':1 if rid==ID else 0,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False}
 if rid==FULL_QUEUE_ID:
  expected.update(operation='full-queue-research-only',max_pilot_families=20,max_worker_text_calls=80,max_worker_image_calls=0,max_wordpress_mutations=0)
 if not isinstance(req,dict) or set(req)!=set(expected)|{'code_revision'} or any(req.get(k)!=v or type(req.get(k)) is not type(v) for k,v in expected.items()):raise ValueError('Exact bounded owner request required')
 sha=req['code_revision']
 if not isinstance(sha,str) or len(sha)!=40 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('Pinned code revision required')
 return req

def authorize(env,data=DATA):
 if not context(env):return False
 p=data/'status/owner-operation-admission.json'
 if not p.exists():return False
 row=load_json(p)
 try:return row['request_id']==row['request']['request_id'] and row['run_id']==env['GITHUB_RUN_ID'] and row['request_commit']==env['GITHUB_SHA'] and 0<=age_hours(row['admitted_at'])<2 and validate_request(row['request']) is not None
 except (KeyError,TypeError,ValueError):return False

def load_owner_request(env,data=DATA,fetch_fn=None,revision_fn=None):
 if not context(env):raise ValueError('Exact destination push workflow context required')
 if fetch_fn is None:
  from .parallel_control import NoRedirect
  url='https://raw.githubusercontent.com/kapitansaman/afp-pipe/'+env['GITHUB_SHA']+'/'+PATH
  with urllib.request.build_opener(NoRedirect()).open(url,timeout=30) as response:
   raw=response.read(8193)
  if len(raw)>8192:raise ValueError('Request too large')
  req=json.loads(raw)
 else:req=fetch_fn()
 validate_request(req)
 revision=revision_fn() if revision_fn else subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if revision!=req['code_revision']:raise ValueError('Checked out code differs from explicit owner request')
 row={'request_id':req['request_id'],'run_id':env['GITHUB_RUN_ID'],'request_commit':env['GITHUB_SHA'],'admitted_at':utcnow(),'request':req};atomic_json(data/'status/owner-operation-admission.json',row);return row

def image_capability(env,data=DATA,out=OUT,probe_fn=None):
 from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
 from .parallel_capacity import CREDENTIAL_SET_ID
 from .healthcheck import SLOTS as legacy_slots
 from .recovery import circuit_open
 from .image_key_audit import probe
 from .image_transport import AdmissionBlocked
 from automation.blog_image_queue import ImageQueueBusy
 hp=out/'parallel/health/latest.json';h=load_json(hp)
 if h.get('repository')!='kapitansaman/afp-pipe' or h.get('credential_set_id')!=CREDENTIAL_SET_ID or h.get('audit_status')!='completed' or not 0<=age_hours(h['checked_at'])<24 or (h.get('text_model'),h.get('image_model'),h.get('api_base'))!=(TEXT_MODEL,IMAGE_MODEL,API_BASE):return {'status':'fresh_text_audit_required','image_calls':0}
 rp=out/'parallel/operations'/ID/'image-proof.json'
 if rp.exists():return {'status':'already_reserved','image_calls':0}
 if circuit_open('image'):return {'status':'shared_image_cooldown','image_calls':0}
 # One candidate chosen before any request; no key hop after an error.
 slots=[s for s in h['eligible_text_slots'] if s in legacy_slots and env.get(s,'').strip()]
 if not slots:return {'status':'no_eligible_image_probe_candidate','image_calls':0}
 slot=slots[0];row={'status':'reserved','slot':slot,'run_id':env['GITHUB_RUN_ID'],'image_calls':1,'publication_visual_approval':False,'started_at':utcnow()};atomic_json(rp,row)
 try:
  result,blob=(probe if probe_fn is None else probe_fn)(slot,env[slot])
 except (AdmissionBlocked,ImageQueueBusy):
  row.update(status='not_sent_admission_blocked',image_calls=0);atomic_json(rp,row);return row
 except Exception as exc:
  import time
  atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'image','at':utcnow(),'retry_at_epoch':time.time()+3600,'reason':'owner_operation_uncertain_image_probe','no_secrets':True})
  row.update(status='uncertain_probe_failure',error_type=type(exc).__name__);atomic_json(rp,row);return row
 safe={k:v for k,v in result.items() if k in {'state','http_status','provider_code','retry_after_seconds','reference_conditioned','publication_visual_approval'}};row['result']=safe
 if result.get('state')=='healthy' and blob:
  # The production probe already decoded/verified bytes. Keep diagnostic, not publishable media.
  target=rp.parent/(slot+'.webp');target.write_bytes(blob)
  proof={'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'kind':'image','slot':slot,'model':IMAGE_MODEL,'verified_at':utcnow(),'verification':'actual_successful_parallel_capability_probe','run_id':env['GITHUB_RUN_ID'],'publication_visual_approval':False}
  atomic_json(out/'parallel/runtime/image'/(slot+'.json'),proof)
  h['eligible_image_slots']=[slot];h['image_pool_audit']={'request_id':ID,'updated_at':utcnow(),'max_image_calls':1,'model':IMAGE_MODEL,'publication_visual_approval':False};atomic_json(hp,h);row['status']='image_capability_verified'
 else:
  row['status']='image_capability_failed_no_failover'
  status=result.get('http_status')
  if status in (402,429) or status is None or isinstance(status,int) and status>=500:
   import time
   retry=max(3600,result.get('retry_after_seconds') or 0);atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'image','at':utcnow(),'retry_at_epoch':time.time()+retry,'reason':'owner_operation_image_probe_shared_or_uncertain_failure','no_secrets':True})
 row['completed_at']=utcnow();atomic_json(rp,row);return row

def prepare(env=None,data=DATA,out=OUT):
 env=dict(os.environ if env is None else env);admission=load_owner_request(env,data)
 from .parallel_control import reserve,policy
 policy(env,data)
 from .production_readiness import run as readiness
 before=readiness(data,out)
 rid=admission['request_id']
 if rid==FULL_QUEUE_ID:
  from .route_audit import run as audit_routes
  routes=audit_routes(data,out)
  if routes['status']!='all_topics_routed':return {'status':'full_queue_route_gaps','model_calls':0,'published_posts':0}
 if reserve('operation',rid,env) is None:return {'status':'operation_already_reserved','model_calls':0,'published_posts':0}
 dest=out/'parallel/operations'/rid;rp=dest/'prepare.json';report={'request_id':rid,'run_id':env['GITHUB_RUN_ID'],'request_commit':env['GITHUB_SHA'],'code_revision':admission['request']['code_revision'],'started_at':utcnow(),'status':'started','readiness_before':before,'attempts_reset':False,'schedule_activated':False,'published_posts':0};atomic_json(rp,report)
 from .parallel_audit import run as audit
 report['audit']=audit(env,data,out) if admission['request']['max_text_health_calls'] else {'status':'not_requested_existing_proof_only','model_calls':0};atomic_json(rp,report)
 h=load_json(out/'parallel/health/latest.json') if (out/'parallel/health/latest.json').exists() else {}
 from .parallel_capacity import CREDENTIAL_SET_ID
 text_ready=h.get('credential_set_id')==CREDENTIAL_SET_ID and h.get('audit_status')=='completed' and 0<=age_hours(h['checked_at'])<24 and len(h.get('eligible_text_slots',[]))>=20
 if text_ready and admission['request']['max_image_health_calls']:report['image']=image_capability(env,data,out);atomic_json(rp,report)
 after=readiness(data,out);report['readiness_after']=after
 required=['fresh_text_capacity','fresh_image_capacity','authenticated_publisher','translation_bridge','lifecycle_enabled']
 if rid==FULL_QUEUE_ID:required=['configured_capacity','fresh_text_capacity','authenticated_publisher','lifecycle_enabled']
 report.update(status=('research_prerequisites_passed' if rid==FULL_QUEUE_ID else 'pilot_prerequisites_passed') if all(after['gates'][k]['passed'] for k in required) else 'pilot_prerequisites_blocked',completed_at=utcnow());atomic_json(rp,report);return report

def pilot(env=None,data=DATA,out=OUT):
 env=dict(os.environ if env is None else env)
 if not authorize(env,data):raise ValueError('Bound current owner operation admission required')
 rid=load_json(data/'status/owner-operation-admission.json')['request_id']
 rp=out/'parallel/operations'/rid/'prepare.json';report=load_json(rp)
 if report.get('run_id')!=env['GITHUB_RUN_ID'] or report.get('status') not in ('pilot_prerequisites_passed','research_prerequisites_passed'):return {'status':'pilot_not_admitted','published_posts':0}
 from .parallel_controller import run
 if rid==FULL_QUEUE_ID:
  env['AFP_FULL_QUEUE_RESEARCH_ONLY']='1'
  return run('advance',env,data,out)
 if rid==SUPPLEMENT_ID:env['AFP_EDITORIAL_SUPPLEMENT']=rid
 return run('white-bean-pilot',env,data,out)

def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','pilot'],required=True);args=p.parse_args()
 result=prepare() if args.phase=='prepare' else pilot()
 failures=[{k:row[k] for k in ('topic_id','family_id','stage','status','failure') if k in row} for row in result.get('results',[]) if row.get('failure')]
 print(json.dumps({'phase':args.phase,'status':result.get('status'),'run_id':os.environ.get('GITHUB_RUN_ID'),'published_posts':result.get('published_posts',0),'stage_failures':failures},ensure_ascii=False))
 return 0 if result.get('status') in ('pilot_prerequisites_passed','research_prerequisites_passed','completed') else 2
if __name__=='__main__':raise SystemExit(main())
