"""One owner-approved 3-text/1-image family-07 check; no production promotion.
All transport is sequential and single-attempt. Unknown requests are never replayed.
"""
import hashlib,io,json,math,time
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .pipeline import digest
from .infrastructure_probe import identity,code_hash,protected
from .single_family_plan import prepare
from .family_model_routing import load as routing,binding as route_binding
from .family_keys import check_unique_values,restrict_env
from .parallel_capacity import CREDENTIAL_SET_ID
from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
ID='authorized-family07-capability-four-call-v1'
PHASE='single-family-capability'
REQUEST='single-family-capability-request.json'
FAMILY='family-07'
TEXT=('AGNES_API_KEY25','AGNES_API_KEY26','AGNES_API_KEY27')
IMAGE='AGNES_API_KEY28'
class Blocked(ValueError):pass


def manifest(data,out):
 return {k:v for k,v in protected(data,out,ID).items() if k!='data/'+REQUEST}


def expected(data=DATA,out=OUT):
 from .media_policy import reference_images
 from .credential_policy import binding
 p=prepare(data,out);roles=routing(data)
 if p['family_id']!=FAMILY or p['topic_id']!='agri-6fc1032cdf42' or roles['families'][FAMILY]!={'text_slots':list(TEXT),'image_slot':IMAGE}:
  raise Blocked('exact_existing_family07_cohort_required')
 return {'version':1,'request_id':ID,'authorization':'explicit_owner_approval_three_text_one_image_family07_only',
         'authorization_source':'https://app.notion.com/chat?t=40841579fa0a8078988900a99eb829d4',
         'family_id':FAMILY,'topic_id':p['topic_id'],'code_sha256':code_hash(),
         'proposal_sha256':digest(p),'protected_sha256':digest(manifest(data,out)),
         'credential_binding':binding(data),'credential_set_id':CREDENTIAL_SET_ID,
         'family_model_routing_sha256':route_binding(roles),'reference_images_sha256':digest(reference_images()),
         'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,
         'text_slots':list(TEXT),'image_slot':IMAGE,'max_runs':1,'max_text_calls':3,'max_image_calls':1,
         'max_attempts_per_slot':1,'max_in_flight':1,'max_output_text_tokens':256,'text_timeout_seconds':70,
         'max_source_fetches':0,'max_search_requests':0,'max_site_calls':0,
         'article_edits':0,'translation_edits':0,'publication_authorized':False,'schedule_enabled':False,
         'promotion_authorized':False,'reset_attempts':False,'global_capacity_refresh':False}


def validate(req,data=DATA,out=OUT):
 wanted=expected(data,out)
 if type(req)is not dict or set(req)!=set(wanted) or any(type(req[k])is not type(v) or req[k]!=v for k,v in wanted.items()):
  raise Blocked('single_family_capability_binding_changed')
 return wanted


def guards(out):
 from .family_capability_refresh import active_hold
 p=out/'provider-circuit.json'
 if p.exists():
  r=load_json(p)
  if type(r)is not dict or type(r.get('open'))is not bool or r.get('request_kind') not in (None,'text','image'):
   raise Blocked('provider_circuit_invalid')
  if r['open']:
   until=r.get('retry_at_epoch')
   if type(until)not in (int,float) or not math.isfinite(until) or until<0:raise Blocked('provider_deadline_invalid')
 if any(active_hold(out,k) for k in ('text','image')):raise Blocked('shared_provider_hold')


def text_ok(safe,obj):
 if type(safe)is not dict or safe.get('http_status')!=200 or type(obj)is not dict or obj.get('model',TEXT_MODEL)!=TEXT_MODEL:return False
 try:
  choice=obj['choices'][0];text=choice['message']['content']
  if isinstance(text,list):text=''.join(x.get('text','') for x in text if isinstance(x,dict) and isinstance(x.get('text'),str))
  return isinstance(text,str) and text.strip()=='OK' and choice.get('finish_reason') not in ('length','content_filter','tool_calls')
 except (KeyError,TypeError,IndexError):return False


def keep_failure(db,out,slot,safe,kind):
 from .parallel_pool import disable,defer_slot,defer
 status=safe.get('http_status');retry=safe.get('retry_after_seconds',0)
 retry=retry if type(retry)in (int,float) and math.isfinite(retry) and retry>=0 else 0
 if status in (401,403):disable(db,slot)
 elif status in (402,429):defer_slot(db,slot,max(3600,retry))
 if status is None or status in (402,429) or type(status)is int and status>=500:
  defer(db,max(3600,retry));atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':kind,'at':utcnow(),
   'retry_at_epoch':time.time()+max(3600,retry),'reason':'single_family_capability_uncertain_or_provider_limit','no_secrets':True})


def run(env,data=DATA,out=OUT,post_fn=None,probe_fn=None,reserve_fn=None,image_guard=None):
 identity(env);root=out/'infrastructure-probes'/ID;rp=root/'report.json'
 if rp.exists():return {'status':'single_family_capability_already_reserved_no_replay','model_calls':0,'image_calls':0,'site_calls':0}
 contract=validate(load_json(data/REQUEST),data,out);check_unique_values(env)
 if any(not env.get(s,'').strip() for s in TEXT+(IMAGE,)):raise Blocked('owned_credentials_missing')
 guards(out)
 from .parallel_pool import initialize,lease,snapshot,routing_counts,routing_backpressure,record_routing,PoolDeferred
 prior=routing_backpressure(out);now=time.time()
 if prior.get('shared_cooldown_until_epoch',0)>now:raise Blocked('durable_shared_cooldown')
 for slot in TEXT+(IMAGE,):
  hold=prior.get('slots',{}).get(slot,{})
  if hold.get('disabled') or hold.get('cooldown_until_epoch',0)>now:raise Blocked('owned_slot_unavailable_no_borrowing')
 owned,_=restrict_env(env,FAMILY,data)
 allowed=set(TEXT+(IMAGE,))|{'GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_EVENT_NAME','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_TOKEN','BLOG_IMAGE_QUEUE_TOKEN'}
 worker={k:v for k,v in owned.items() if k in allowed}
 worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(root/'pool.sqlite'),AFP_PARALLEL_TOPIC=ID,AFP_PARALLEL_FAMILY=FAMILY)
 from .image_transport import shared_guard,AdmissionBlocked
 from automation.blog_image_queue import ImageQueueBusy
 (image_guard or shared_guard)(IMAGE,worker) # Read-only shared admission before consuming text budget.
 if reserve_fn is None:
  from .parallel_control import reserve
  admitted=reserve(PHASE,ID,env)
 else:admitted=reserve_fn(env)
 if not admitted:return {'status':'single_family_capability_already_reserved_no_replay','model_calls':0,'image_calls':0,'site_calls':0}
 before=manifest(data,out)
 r={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'family_id':FAMILY,'topic_id':contract['topic_id'],
    'status':'single_family_capability_reserved','started_at':utcnow(),'contract_sha256':digest(contract),
    'max_text_calls':3,'max_image_calls':1,'model_calls':0,'image_calls':0,'search_requests':0,'source_fetches':0,
    'site_calls':0,'published_posts':0,'article_edits':0,'translation_edits':0,'attempts_reset':False,
    'publication_authorized':False,'schedule_enabled':False,'promotion_authorized':False,'global_capacity_refresh':False,
    'production_readiness_claimed':False,'publication_visual_approval':False,'cases':[]}
 atomic_json(rp,r);db=root/'pool.sqlite'
 initialize(db,list(TEXT)+[IMAGE],text_limit=1,image_limit=1,max_calls=4,per_worker=4,
            prior_usage=routing_counts(out),prior_backpressure=prior)
 from .parallel_audit import post_once
 from .image_key_audit import probe
 post_fn=post_fn or post_once;probe_fn=probe_fn or probe
 def checkpoint():atomic_json(rp,r)
 try:
  for kind,slot in [('text',s) for s in TEXT]+[('image',IMAGE)]:
   guards(out)
   if manifest(data,out)!=before:raise Blocked('protected_inputs_changed_before_request')
   receipt=root/'calls'/(slot+'.json')
   if receipt.exists() or len(r['cases'])>=4:raise Blocked('consumed_transport_no_replay')
   row={'kind':kind,'slot':slot,'status':'reserved','at':utcnow(),'max_attempts':1}
   with lease(db,kind,[slot],ID,wait=0):
    atomic_json(receipt,row);r['cases'].append(row)
    if kind=='text':
     payload={'model':TEXT_MODEL,'messages':[{'role':'user','content':'Reply with OK only.'}],'temperature':0,'max_tokens':256}
     row['request_sha256']=digest(payload);r['model_calls']+=1;checkpoint();atomic_json(receipt,row)
     try:safe,obj=post_fn('/chat/completions',worker[slot].strip(),payload,timeout=70)
     except Exception:safe,obj={'http_status':None},None
     passed=text_ok(safe,obj)
    else:
     r['image_calls']+=1;checkpoint()
     try:safe,blob=probe_fn(slot,worker[slot].strip(),env=worker,diagnostic_id=ID)
     except (AdmissionBlocked,ImageQueueBusy):
      r['image_calls']-=1;row['status']='admission_blocked_not_sent';atomic_json(receipt,row);raise Blocked('image_admission_changed_no_request')
     except Exception:safe,blob={'http_status':None},None
     passed=False
     if type(safe)is dict and safe.get('state')=='healthy' and safe.get('http_status')==200 and isinstance(blob,bytes):
      try:
       from PIL import Image
       with Image.open(io.BytesIO(blob)) as im:
        if im.width<768 or im.height<432 or im.width<=im.height or im.width*im.height>20_000_000:raise ValueError('Invalid image dimensions')
        width,height=im.size;im.verify()
       (root/'capability-image.webp').write_bytes(blob);row.update(image_sha256=hashlib.sha256(blob).hexdigest(),width=width,height=height);passed=True
      except Exception:passed=False
    status=safe.get('http_status') if type(safe)is dict else None
    if type(status)is not int or not 100<=status<=599:status=None
    safe=safe if type(safe)is dict else {}
    row.update(status='verified' if passed else 'reconciliation_required' if status is None else 'failed',http_status=status,completed_at=utcnow())
    atomic_json(receipt,row);checkpoint()
    if not passed:
     keep_failure(db,out,slot,dict(safe,http_status=status),kind);raise Blocked('probe_failed_stop_all_remaining_calls')
  r['status']='single_family_capability_verified_not_promoted'
  if manifest(data,out)!=before:raise Blocked('protected_inputs_changed_after_requests')
  atomic_json(root/'scoped-proof.json',{'request_id':ID,'family_id':FAMILY,'verified_at':utcnow(),
   'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,'credential_set_id':CREDENTIAL_SET_ID,
   'family_model_routing_sha256':contract['family_model_routing_sha256'],'text_slots':list(TEXT),'image_slot':IMAGE,
   'image_sha256':r['cases'][-1]['image_sha256'],'verification':'actual_successful_family_capability_probe',
   'scope':'isolated_family07_only_not_global_production_health','production_readiness_claimed':False,'publication_visual_approval':False})
 except Exception as exc:
  r['status']='single_family_capability_blocked'
  r['failure']={'kind':'guard' if type(exc)is Blocked else 'operational','category':str(exc) if type(exc)is Blocked else type(exc).__name__}
 finally:
  state=snapshot(db);record_routing(out,state);r['transport_reservations']=state['model_requests_reserved']
  r['originals_unchanged']=manifest(data,out)==before
  if not r['originals_unchanged']:r['status']='single_family_capability_originals_changed'
  r['completed_at']=utcnow();checkpoint()
 return r
