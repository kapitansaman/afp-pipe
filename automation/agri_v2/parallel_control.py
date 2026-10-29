"""Manual first rollout only; remote create-only ledgers prevent billed replay."""
import base64,json,os,urllib.request,urllib.error
from .queue import DATA,OUT,atomic_json,load_json,utcnow
from .parallel_capacity import KEY_LIMIT,MAX_FAMILIES,CREDENTIAL_SET_ID,AUDIT_ID
REPO='kapitansaman/afp-pipe';BRANCH='feat/agri-generator-v2-2905-merge593'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None

def policy(env=None,data=DATA):
 env=os.environ if env is None else env;p=load_json(data/'parallel-policy.json')
 if p.get('repository')!=REPO or p.get('key_limit')!=KEY_LIMIT or p.get('max_article_workers')!=MAX_FAMILIES or p.get('credential_set_id')!=CREDENTIAL_SET_ID or p.get('image_concurrency')!=1 or p.get('production_enabled') is not False or p.get('max_published_posts')!=0:raise ValueError('Exact non-publication parallel rollout policy required')
 event_ok=env.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
 if env.get('GITHUB_EVENT_NAME')=='push':
  from .operation_request import authorize
  event_ok=authorize(env,data)
 if env.get('GITHUB_EVENT_NAME')=='schedule':
  from .adaptive_schedule import admitted
  event_ok=admitted(env,data,OUT)
 if env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_REPOSITORY')!=REPO or not event_ok or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ValueError('Verified manual, bounded owner operation or explicitly admitted adaptive Actions run required')
 return p

def reserve(phase,request_id,env=None,put_fn=None):
 env=os.environ if env is None else env
 if phase not in ('audit','research','trial','lifecycle','operation','capability','capability-followup','claim-policy-recheck','claim-policy-continuation','claim-policy-regional-final','post-hold-validation','regional-only-recovery','regional-schema-recheck','regional-keyed-validation'):raise ValueError('Non-publication phase required')
 if phase=='regional-keyed-validation':
  from .regional_keyed_validation import ID
  if request_id!=ID or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REF_NAME')!=BRANCH:raise ValueError('Exact manual keyed regional validation required')
  expected=ID
 elif phase=='regional-schema-recheck':
  from .regional_schema_recheck import ID
  if request_id!=ID or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REF_NAME')!=BRANCH:raise ValueError('Exact manual regional schema recheck required')
  expected=ID
 elif phase=='regional-only-recovery':
  from .regional_only_recovery import ID
  if request_id!=ID or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REF_NAME')!=BRANCH:raise ValueError('Exact manual regional-only continuation required')
  expected=ID
 elif phase=='post-hold-validation':
  from .post_hold_validation import ID
  if request_id!=ID or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REF_NAME')!=BRANCH:raise ValueError('Exact manual post-hold validation required')
  expected=ID
 elif phase=='claim-policy-regional-final':
  from .claim_policy_regional_final import ID
  if request_id!=ID or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REF_NAME')!=BRANCH:raise ValueError('Exact manual regional final required')
  expected=ID
 elif phase=='claim-policy-continuation':
  from .claim_policy_continuation import ID
  if request_id!=ID or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REF_NAME')!=BRANCH:raise ValueError('Exact manual claim-policy continuation required')
  expected=ID
 elif phase=='claim-policy-recheck':
  from .claim_policy_recheck import ID
  if request_id!=ID or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REF_NAME')!=BRANCH:raise ValueError('Exact manual claim-policy recheck required')
  expected=ID
 elif phase=='capability-followup':
  if request_id!='family09-image-followup-v1' or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch':raise ValueError('Exact manual one-shot diagnostic required')
  expected=request_id
 elif phase=='capability':
  import datetime
  from .parallel_pool import SLOTS
  prefix='family-capability-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')+'-'
  if request_id not in [prefix+'text']+[prefix+'image-'+s for s in SLOTS]:raise ValueError('Current-day exact capability reservation required')
  expected=request_id
 elif phase=='lifecycle':
  if request_id!='family-lifecycle-run-'+str(env.get('GITHUB_RUN_ID','')) or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ValueError('Current run-bound lifecycle reservation required')
  expected=request_id
 elif phase=='operation':
  from .operation_request import authorize
  if not authorize(env):raise ValueError('Bound owner operation required')
  expected=load_json(DATA/'status/owner-operation-admission.json')['request_id']
 else:expected={'audit':AUDIT_ID,'research':'parallel-15-research-rollout-v1','trial':'parallel-family-trial-v2'}[phase]
 if request_id!=expected:raise ValueError('Exact bounded first-rollout request required')
 row={'request_id':request_id,'phase':phase,'status':'reserved','run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'published_posts':0,'original_attempts_reset':False}
 if put_fn is not None:return row if put_fn(row) else None
 token=env.get('GITHUB_TOKEN')
 if not token:raise ValueError('Durable reservation unavailable')
 payload={'message':'Reserve bounded parallel '+phase+' rollout [skip ci]','branch':BRANCH,'content':base64.b64encode((json.dumps(row,indent=2)+'\n').encode()).decode()}
 req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/contents/data/agri-v2/status/parallel-reservations/'+request_id+'.json',data=json.dumps(payload).encode(),method='PUT',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/vnd.github+json'})
 try:
  with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as r:return row if r.status==201 else None
 except urllib.error.HTTPError as e:
  code=e.code;e.close()
  if code==422:return None
  raise ValueError('Remote reservation rejected; no model call') from None
 except Exception:raise ValueError('Remote reservation uncertain; no model call') from None
