"""One sequential first-15 image capability audit, not a quota/capacity bypass."""
import datetime,email.utils,hashlib,json,os,time,urllib.request,urllib.error
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow
from .healthcheck import SLOTS,IMAGE_MODEL,API_BASE,MAX_RESPONSE,classify
from .media_policy import reference_images
from .client import render_image,ImageProviderError
from .image_transport import admission,shared_guard,AdmissionBlocked
from .recovery import circuit_open
from .pilot_resume import defer_provider
from .progress import update
from automation.agnes_key_pool import AgnesProviderError
from automation.blog_image_queue import ImageQueueBusy
ID='unique-image-capability-v1'
REQUEST={'request_id':ID,'model':'agnes-image-2.1-flash','max_image_calls':14,'max_calls_per_unique_key':1,'max_parallel':1,'publication_authorized':False}
def unique_slots(env):
 seen={};slots=[];aliases={}
 for name in SLOTS:
  key=env.get(name,'').strip()
  if not key:continue
  if key in seen:aliases[name]=seen[key]
  else:seen[key]=name;slots.append((name,key))
 return slots,aliases
def retry_seconds(value,now=None):
 if not value:return None
 if value.isdigit():return int(value)
 try:return max(0,int(email.utils.parsedate_to_datetime(value).timestamp()-(time.time() if now is None else now)))
 except (ValueError,TypeError,OverflowError):return None
def probe(slot,key,env=None):
 refs=reference_images()
 body={'model':IMAGE_MODEL,'prompt':'Capability test: photograph of one intact sealed white-blue AFP carton on bare soil, matching the reference identity. No humans, no additional text. Diagnostic '+slot+'.','size':'1K','ratio':'16:9','return_base64':True,'extra_body':{'response_format':'b64_json','image':refs}}
 with admission(slot,body,os.environ if env is None else env):
  req=urllib.request.Request(API_BASE+'/images/generations',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'AFP-bounded-unique-image-audit'})
  try:
   with urllib.request.urlopen(req,timeout=180) as response:
    raw=response.read(MAX_RESPONSE+1)
    if len(raw)>MAX_RESPONSE:return {'state':'response_too_large','http_status':200},None
    obj=json.loads(raw)
   if obj.get('model') and obj['model']!=IMAGE_MODEL:return {'state':'model_mismatch','http_status':200},None
   blob=render_image(obj,require_landscape=True,reject_reference_images=refs)
   return {'state':'healthy','http_status':200,'reference_conditioned':True,'publication_visual_approval':False},blob
  except urllib.error.HTTPError as exc:
   status=exc.code;raw=exc.read(20000);retry=retry_seconds(exc.headers.get('Retry-After'));exc.close();safe=AgnesProviderError(status,raw)
   return {'state':classify(status,raw),'http_status':status,'provider_code':safe.provider_code,'retry_after_seconds':retry},None
  except Exception as exc:return {'state':'transport_or_decode_failed','http_status':None,'error_type':type(exc).__name__},None

def terminal(row):
 status=row.get('http_status')
 # A different key must never be tried after quota/rate/capacity/uncertain errors.
 return status not in (200,401,403) or row.get('state') not in ('healthy','invalid_auth','forbidden')
def apply_result(health,slot,row):
 image={k:v for k,v in row.items() if k not in ('slot','path','sha256')}
 for entry in health['slots']:
  if entry['slot']==slot:entry['image']=image;break
 eligible=[s for s in health.get('eligible_image_slots',[]) if s!=slot]
 if row['state']=='healthy':eligible.append(slot)
 health['eligible_image_slots']=[s for s in SLOTS if s in eligible]
 # Keep checked_at and all text evidence unchanged. New image evidence has its
 # own date and cannot extend the old text capability lifetime.
 health['image_pool_audit']={'request_id':ID,'updated_at':utcnow(),'report':'artifacts/agri-v2/image-key-audit/'+ID+'/report.json','model':IMAGE_MODEL,'publication_visual_approval':False}

def run(env=None,probe_fn=None):
 env=os.environ if env is None else env;probe_fn=probe if probe_fn is None else probe_fn
 request_path=DATA/'image-key-audit-request.json'
 if not request_path.exists():return None
 req=load_json(request_path)
 if req!=REQUEST or IMAGE_MODEL!=req['model']:raise ValueError('Exact bounded first-15 image audit required')
 dest=OUT/'image-key-audit'/ID;rp=dest/'report.json';waiting=dest/'waiting.json'
 if rp.exists():return None # A reserved/interrupted/failed audit is never replayed.
 if circuit_open():
  atomic_json(waiting,{'status':'waiting_provider_deadline','image_calls':0,'post_submissions':0,'at':utcnow()})
  update('بررسی کلیدهای تصویر منتظر پایان توقف مشترک سرویس است',0,status='provider_cooldown')
  return {'status':'image_key_audit_waiting','model_calls':0,'published_posts':0}
 slots,aliases=unique_slots(env)
 health=load_json(DATA/'health/latest.json')
 if health.get('image_model')!=IMAGE_MODEL or health.get('api_base')!=API_BASE:raise ValueError('Image health model/base mismatch')
 # Previously unverified slots first; this is fresh capability discovery after
 # shared cooldown, never failover triggered by a rejection in this audit.
 prior=set(health.get('eligible_image_slots',[]));slots.sort(key=lambda item:item[0] in prior)
 report={'request_id':ID,'model':IMAGE_MODEL,'run_id':env.get('GITHUB_RUN_ID'),'started_at':utcnow(),'status':'reserved','image_calls':0,'max_image_calls':14,'unique_configured':len(slots),'duplicate_slots':aliases,'cases':[],'post_submissions':0,'text_calls':0,'no_automatic_retry':True}
 # Read-only admission before reserving budget. Per-slot denials skip requests;
 # shared holds prevent the entire run, including any alternative slot.
 if env.get('GITHUB_ACTIONS')=='true':
  from .image_transport import shared_evidence
  from .image_key_routing import choose
  try:choose([(s,'unique-placeholder-'+s) for s,k in slots],0,shared_evidence(),time.time())
  except AdmissionBlocked:
   atomic_json(waiting,{'status':'shared_admission_waiting','image_calls':0,'post_submissions':0,'at':utcnow()})
   return {'status':'image_key_audit_waiting','model_calls':0,'published_posts':0}
 atomic_json(rp,report)
 try:
  for slot,key in slots:
   if report['image_calls']>=14:break
   if circuit_open():report['status']='stopped_shared_cooldown';break
   if env.get('GITHUB_ACTIONS')=='true':
    evidence=shared_evidence()
    try:choose([(slot,'preflight')],0,[{k:v for k,v in d.items() if k!='keys'} for d in evidence],time.time())
    except AdmissionBlocked:report['status']='stopped_shared_admission';break
    try:choose([(slot,'preflight')],0,evidence,time.time())
    except AdmissionBlocked:
     report['cases'].append({'slot':slot,'state':'not_sent_slot_unavailable','checked_at':utcnow()});atomic_json(rp,report);continue
   row={'slot':slot,'state':'reserved','checked_at':utcnow()};report['cases'].append(row);report['image_calls']+=1;atomic_json(rp,report)
   update('بررسی دسترسی مدل تصویر برای '+slot,20,status='image_key_audit_running')
   try:result,blob=probe_fn(slot,key)
   except (AdmissionBlocked,ImageQueueBusy):
    report['image_calls']-=1;row['state']='not_sent_admission_blocked';report['status']='stopped_admission_changed';break
   row.update(result,checked_at=utcnow())
   if blob:
    path=dest/(slot+'.webp');path.write_bytes(blob);row.update(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(blob).hexdigest())
   apply_result(health,slot,row);atomic_json(DATA/'health/latest.json',health);atomic_json(rp,report)
   if terminal(row):
    report['status']='stopped_provider_limit_or_uncertain_failure'
    if row.get('http_status') in (402,429) or (row.get('http_status') or 0)>=500:
     exc=ImageProviderError(row['http_status'],row.get('provider_code'),row['state'],row.get('retry_after_seconds'));report['retry_at_epoch']=defer_provider(exc)
    break
  else:report['status']='completed_capability_audit'
  if report['status']=='reserved':report['status']='completed_budget_bound'
 except Exception as exc:report.update(status='stopped_internal_error',error_type=type(exc).__name__)
 finally:
  report.update(finished_at=utcnow(),healthy_tested_slots=[r['slot'] for r in report['cases'] if r['state']=='healthy'],eligible_image_slots=health.get('eligible_image_slots',[]));atomic_json(rp,report)
  update('بررسی محدود کلیدهای تصویر پایان یافت؛ گزارش دسترسی ثبت شد',40,status='image_key_audit_complete')
 return {'status':report['status'],'model_calls':report['image_calls'],'published_posts':0}
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
