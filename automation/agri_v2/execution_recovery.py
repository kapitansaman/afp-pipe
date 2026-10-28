"""Remote write-ahead run fence; only a durable checkpoint closes it.
No time-based unlock, automatic replay, secret persistence or budget reset.
"""
import base64,hashlib,json,os,urllib.request,urllib.error
from .queue import load_json,atomic_json,utcnow,safe_id
from .parallel_control import REPO,BRANCH,NoRedirect
VERSION='write-ahead-lifecycle-v1'
FLIGHT='data/agri-v2/status/lifecycle-flight.json'
POLICY={'version':1,'policy':VERSION,'enabled':True,'require_remote_intent_before_work':True,'close_only_with_committed_checkpoints':True,'automatic_uncertain_replay':False,'reset_attempts':False}
class ReconciliationRequired(RuntimeError):pass

def enabled(data):
 p=data/'execution-recovery-policy.json'
 if not p.exists():return False
 value=load_json(p)
 if value==dict(POLICY,enabled=False):return False
 if value!=POLICY:raise ValueError('Exact write-ahead execution policy required')
 return True

def uncertain_outcome(error):
 from .source_search import SearchProviderError
 if isinstance(error,SearchProviderError):return error.http_status is None or type(error.http_status)is int and error.http_status>=500
 from .client import TextProviderError,ImageProviderError
 if isinstance(error,(TextProviderError,ImageProviderError)):
  return error.http_status is None or type(error.http_status)is int and error.http_status>=500
 from .wordpress import WPError
 if isinstance(error,WPError):
  message=str(error)
  return message=='WordPress transport/JSON failure; reconcile by slug before retry' or message.startswith('WordPress HTTP 5') and len(message)==18 and message[-3:].isdigit()
 return False

def canonical(row):return json.dumps(row,sort_keys=True,separators=(',',':')).encode()
def fingerprint(row):return hashlib.sha256(canonical(row)).hexdigest()

def transport(env,method,payload=None):
 url='https://api.github.com/repos/'+REPO+'/contents/'+FLIGHT
 if method=='GET':url+='?ref='+BRANCH
 request=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),method=method,headers={'Authorization':'Bearer '+env['GITHUB_TOKEN'],'Content-Type':'application/json','Accept':'application/vnd.github+json'})
 try:
  with urllib.request.build_opener(NoRedirect()).open(request,timeout=45) as response:return json.loads(response.read(2*1024*1024))
 except urllib.error.HTTPError as exc:
  code=exc.code;exc.close()
  if method=='GET' and code==404:return None
  raise ReconciliationRequired('Remote lifecycle fence rejected; no work authorized') from None
 except Exception:raise ReconciliationRequired('Remote lifecycle fence uncertain; no work authorized') from None

def begin(env,topics,data,out,call_fn=None):
 if not enabled(data):return None
 if env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_REPOSITORY')!=REPO or not str(env.get('GITHUB_RUN_ID','')).isdigit() or not env.get('GITHUB_TOKEN'):raise ReconciliationRequired('Verified destination run and durable fence credentials required')
 if not 1<=len(topics)<=20 or len({t['id'] for t in topics})!=len(topics):raise ValueError('One to twenty unique owned topics required')
 for t in topics:safe_id(t['id'])
 call=(lambda method,payload=None:transport(env,method,payload)) if call_fn is None else call_fn
 prior=call('GET');sha=None
 if prior is not None:
  try:
   sha=prior['sha'];old=json.loads(base64.b64decode(prior['content']))
  except Exception:raise ReconciliationRequired('Invalid remote lifecycle fence') from None
  if old.get('version')!=1 or old.get('policy')!=VERSION or old.get('repository')!=REPO or old.get('branch')!=BRANCH:raise ReconciliationRequired('Foreign or invalid lifecycle fence')
  if old.get('status')!='checkpointed':raise ReconciliationRequired('Previous lifecycle has uncommitted outcomes; reconcile before new work')
  if old.get('run_id')==env['GITHUB_RUN_ID']:raise ReconciliationRequired('Current lifecycle already checkpointed; never replay the same run')
  if len(str(old.get('checkpoint_digest','')))!=64:raise ReconciliationRequired('Durable checkpoint proof required')
 row={'version':1,'policy':VERSION,'repository':REPO,'branch':BRANCH,'status':'in_flight','run_id':env['GITHUB_RUN_ID'],'topics':[{'topic_id':t['id'],'family_id':t.get('family_id')} for t in topics],'started_at':utcnow(),'automatic_uncertain_replay':False,'original_attempts_reset':False}
 raw=(json.dumps(row,ensure_ascii=False,indent=2)+'\n').encode();payload={'branch':BRANCH,'message':'Fence lifecycle '+row['run_id']+' before paid work [skip ci]','content':base64.b64encode(raw).decode()}
 if sha is not None:payload['sha']=sha
 response=call('PUT',payload)
 try:remote_sha=response['content']['sha']
 except Exception:raise ReconciliationRequired('Lifecycle fence write not confirmed; no work authorized') from None
 expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 if remote_sha!=expected:raise ReconciliationRequired('Lifecycle fence bytes not confirmed; no work authorized')
 atomic_json(data/'status/lifecycle-flight.json',row)
 atomic_json(out/'parallel/recovery/admissions'/(row['run_id']+'.json'),{'version':1,'run_id':row['run_id'],'remote_flight_sha':remote_sha,'reserved_row_sha256':fingerprint(row),'intent':row,'secret_values_stored':False})
 return row

def checkpoint_candidate(root,env):
 """Return a closing record only for all identity-checked, merged worker results."""
 data=root/'data/agri-v2';out=root/'artifacts/agri-v2';p=root/FLIGHT
 if not p.exists():return None,None
 row=load_json(p);run=str(env.get('GITHUB_RUN_ID',''))
 if row.get('status')!='in_flight' or row.get('run_id')!=run:return None,None
 ap=out/'parallel/recovery/admissions'/(run+'.json')
 if not ap.exists():return None,None
 admission=load_json(ap)
 if admission.get('run_id')!=run or admission.get('reserved_row_sha256')!=fingerprint(row):raise ReconciliationRequired('Local run intent changed; fence must stay closed to work')
 expected=admission['remote_flight_sha'];rp=out/'parallel/lifecycle/runs'/run/'report.json'
 if not rp.exists():return None,expected
 report=load_json(rp);results=report.get('results',[]);ids=[t['topic_id'] for t in row['topics']]
 if report.get('run_id')!=run or report.get('status') not in ('completed','completed_with_failures') or report.get('coordinator_failure') or len(results)!=len(ids):return None,expected
 unknown={'worker_timed_out','worker_missing_result','worker_operational_failure','worker_failed'}
 if {r.get('topic_id') for r in results}!=set(ids) or any(r.get('checkpoint_merged') is not True or r.get('status') in unknown for r in results):return None,expected
 closed=dict(row,status='checkpointed',checkpointed_at=utcnow(),all_selected_workers_merged=True,checkpoint_report_sha256=hashlib.sha256(rp.read_bytes()).hexdigest())
 return closed,expected
