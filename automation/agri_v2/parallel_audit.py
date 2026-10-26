"""Up to 97 unique text checks, two in flight, no image/WordPress operation."""
import concurrent.futures,json,os,time,urllib.request,urllib.error
from .queue import DATA,OUT,atomic_json,load_json,utcnow
from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE,classify,MAX_RESPONSE
from .parallel_pool import SLOTS
from .parallel_control import policy,reserve
from .parallel_capacity import KEY_LIMIT,AUDIT_ID
ID=AUDIT_ID
def post_once(endpoint,key,payload,timeout=70):
 req=urllib.request.Request(API_BASE+endpoint,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'AFP-parallel-text-capability-audit'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:
   blob=r.read(MAX_RESPONSE+1)
   if len(blob)>MAX_RESPONSE:return {'state':'response_too_large','http_status':r.status},None
   try:obj=json.loads(blob)
   except ValueError:return {'state':'invalid_json','http_status':r.status},None
   return {'state':'responded','http_status':r.status},obj
 except urllib.error.HTTPError as e:
  from .provider_retry import retry_seconds
  code=e.code;body=e.read(20000);retry=retry_seconds(e.headers.get('Retry-After'));e.close()
  return {'state':classify(code,body),'http_status':code,'retry_after_seconds':retry},None
 except (urllib.error.URLError,TimeoutError,OSError):return {'state':'network_or_timeout','http_status':None},None


def run(env=None,data=DATA,out=OUT,post_fn=post_once,reserve_fn=reserve,workers=2):
 env=os.environ if env is None else env;p=policy(env,data)
 dest=out/'parallel/key-audits'/ID;rp=dest/'report.json'
 if rp.exists():return {'status':'already_reserved','model_calls':0,'published_posts':0}
 from .recovery import circuit_open
 if circuit_open('text'):return {'status':'shared_text_cooldown','model_calls':0,'published_posts':0}
 owners={};unique=[];aliases={};missing=[]
 for slot in SLOTS:
  key=env.get(slot,'').strip()
  if not key:missing.append(slot)
  elif key in owners:aliases[slot]=owners[key]
  else:owners[key]=slot;unique.append((slot,key))
 report={'request_id':ID,'repository':p['repository'],'credential_set_id':p['credential_set_id'],'run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'configured_slots':KEY_LIMIT-len(missing),'unique_credentials':len(unique),'duplicate_slots':aliases,'missing_slots':missing,'max_text_requests':KEY_LIMIT,'max_in_flight':min(2,max(1,workers)),'model_calls':0,'image_calls':0,'wordpress_calls':0,'published_posts':0,'cases':[],'status':'configuration_check'}
 if missing or aliases:report.update(status='missing_or_duplicate_credentials',completed_at=utcnow());atomic_json(rp,report);return report
 if reserve_fn('audit',ID,env) is None:return {'status':'already_reserved','model_calls':0,'published_posts':0}
 report['status']='in_progress';atomic_json(rp,report)
 pending={};cursor=iter(unique);stop=False
 def submit(pool):
  try:slot,key=next(cursor)
  except StopIteration:return False
  report['model_calls']+=1;report['cases'].append({'slot':slot,'state':'reserved','started_at':utcnow()});atomic_json(rp,report)
  payload={'model':TEXT_MODEL,'messages':[{'role':'user','content':'Reply with OK only.'}],'temperature':0,'max_tokens':256}
  pending[pool.submit(post_fn,'/chat/completions',key,payload,timeout=70)]=slot;return True
 with concurrent.futures.ThreadPoolExecutor(max_workers=report['max_in_flight']) as pool:
  for _ in range(report['max_in_flight']):submit(pool)
  while pending:
   done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    slot=pending.pop(future);row=next(r for r in report['cases'] if r['slot']==slot)
    try:safe,obj=future.result()
    except Exception:safe,obj={'state':'network_or_timeout','http_status':None},None
    content=None
    try:
     content=obj['choices'][0]['message']['content']
     if isinstance(content,list):content=''.join(x.get('text','') for x in content if isinstance(x,dict) and isinstance(x.get('text'),str))
    except (TypeError,KeyError,IndexError):pass
    valid=safe.get('http_status')==200 and isinstance(content,str) and bool(content.strip()) and isinstance(obj,dict) and obj.get('model',TEXT_MODEL)==TEXT_MODEL
    row.update(state='healthy' if valid else safe.get('state','invalid_text_response'),http_status=safe.get('http_status'),checked_at=utcnow())
    if not valid and safe.get('http_status')==200:row['state']='invalid_text_response'
    if safe.get('http_status') not in (200,401,403):
     stop=True
     retry=max(3600,safe.get('retry_after_seconds') or 0)
     atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':time.time()+retry,'reason':'parallel_audit_shared_provider_limit','no_secrets':True})
   # Finish all results in this completion set before scheduling more: no bypass of shared limits.
   atomic_json(rp,report)
   if not stop:
    while len(pending)<report['max_in_flight'] and submit(pool):pass
 healthy=[r['slot'] for r in report['cases'] if r['state']=='healthy']
 report.update(status='stopped_shared_provider_limit' if stop else 'completed',completed_at=utcnow(),eligible_text_slots=healthy,eligible_image_slots=[])
 atomic_json(rp,report)
 health={k:report[k] for k in ('repository','credential_set_id','run_id','eligible_text_slots','eligible_image_slots')}
 health.update(audit_status=report['status'],unique_credentials_tested=len(report['cases']),checked_at=report['started_at'],text_model=TEXT_MODEL,image_model=IMAGE_MODEL,api_base=API_BASE,slots=[{**r,'text':{'state':r['state']},'image':{'state':'not_probed'}} for r in report['cases']],capability_scope='text_only_no_image_approval',source_request_id=ID)
 atomic_json(out/'parallel/health/latest.json',health)
 return report
