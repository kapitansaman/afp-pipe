"""Manual first rollout only; remote create-only ledgers prevent billed replay."""
import base64,json,os,urllib.request,urllib.error
from .queue import DATA,OUT,atomic_json,load_json,utcnow
REPO='kapitansaman/afp-pipe';BRANCH='feat/agri-generator-v2-2905-merge593'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None

def policy(env=None,data=DATA):
 env=os.environ if env is None else env;p=load_json(data/'parallel-policy.json')
 if p.get('repository')!=REPO or p.get('key_limit')!=75 or p.get('max_article_workers')!=15 or p.get('image_concurrency')!=1 or p.get('production_enabled') is not False or p.get('max_published_posts')!=0:raise ValueError('Exact non-publication parallel rollout policy required')
 if env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_REPOSITORY')!=REPO or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ValueError('Verified manual destination Actions run required')
 return p

def reserve(phase,request_id,env=None,put_fn=None):
 env=os.environ if env is None else env
 if phase not in ('audit','research','trial'):raise ValueError('Non-publication phase required')
 expected={'audit':'parallel-75-key-audit-v1','research':'parallel-15-research-rollout-v1','trial':'parallel-family-trial-v2'}[phase]
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
