"""Manual daily text renewal and independent, pinned single-flight image proofs.
Create-only daily reservations prevent blind retry after interrupted checkpoints.
No article, publication, stage-attempt reset or schedule activation occurs here.
"""
import concurrent.futures,datetime,json,os,tempfile,time
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours
from .parallel_control import policy,reserve
from .parallel_capacity import CREDENTIAL_SET_ID
from .parallel_pool import SLOTS,initialize,lease
from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
from .family_keys import check_unique_values,binding as allocation_binding,load as allocation
from .family_model_routing import load as routing,binding as route_binding
from .parallel_audit import post_once

def day():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')
def fresh(at):
 try:return 0<=age_hours(at)<24
 except (ValueError,TypeError,KeyError):return False

def image_proofs(out,roles):
 result=[];rb=route_binding(roles)
 for family,row in roles['families'].items():
  slot=row['image_slot'];p=out/'parallel/runtime/image'/(slot+'.json')
  if not p.exists():continue
  r=load_json(p)
  if r.get('repository')=='kapitansaman/afp-pipe' and r.get('credential_set_id')==CREDENTIAL_SET_ID and r.get('slot')==slot and r.get('family_id')==family and r.get('model')==IMAGE_MODEL and r.get('family_model_routing_sha256')==rb and r.get('verification') in ('actual_successful_parallel_response','actual_successful_parallel_capability_probe') and fresh(r.get('verified_at')):result.append(slot)
 return result

def embedded_proofs(out,roles):
 return {slot:load_json(out/'parallel/runtime/image'/(slot+'.json')) for slot in image_proofs(out,roles)}

def text_fresh(h,roles):
 return h.get('audit_status')=='completed' and h.get('repository')=='kapitansaman/afp-pipe' and h.get('credential_set_id')==CREDENTIAL_SET_ID and (h.get('text_model'),h.get('image_model'),h.get('api_base'))==(TEXT_MODEL,IMAGE_MODEL,API_BASE) and fresh(h.get('checked_at')) and h.get('family_model_routing_sha256')==route_binding(roles)

def active_hold(out,kind):
 p=out/'provider-circuit.json'
 if not p.exists():return False
 r=load_json(p)
 if not r.get('open') or r.get('request_kind') not in (None,kind):return False
 return r['retry_at_epoch']>time.time() if 'retry_at_epoch' in r else fresh(r.get('at')) and age_hours(r['at'])<1

def stop(out,kind):atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':kind,'at':utcnow(),'retry_at_epoch':time.time()+3600,'reason':'family_capability_uncertain_or_service_failure','no_secrets':True})

def context(env,data):
 policy(env,data)
 if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch':raise ValueError('Manual capability refresh only')
 check_unique_values(env);roles=routing(data)
 if roles is None:raise ValueError('Explicit model roles required')
 if any(not env.get(s,'').strip() for s in SLOTS):raise ValueError('All 97 configured slots required')
 return roles

def text(env,data=DATA,out=OUT,post_fn=post_once,reserve_fn=reserve):
 roles=context(env,data);hp=out/'parallel/health/latest.json';old=load_json(hp) if hp.exists() else {}
 if text_fresh(old,roles):return {'status':'fresh_text_capability_reused','model_calls':0,'image_calls':0,'published_posts':0}
 if active_hold(out,'text'):return {'status':'shared_text_cooldown','model_calls':0,'published_posts':0}
 rid='family-capability-'+day()+'-text';rp=out/'parallel/capability-refresh'/day()/'text.json'
 if rp.exists() or reserve_fn('capability',rid,env) is None:return {'status':'capability_already_reserved_no_replay','model_calls':0,'published_posts':0}
 a=allocation(data);targets=[s for row in roles['families'].values() for s in row['text_slots']]+a['central_slots']
 r={'request_id':rid,'run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'family_model_routing_sha256':route_binding(roles),'status':'reserved','model_calls':0,'image_calls':0,'published_posts':0,'cases':[],'max_text_requests':len(targets),'max_parallel':2,'original_attempts_reset':False}
 atomic_json(rp,r);pending={};cursor=iter(targets);halt=False
 def submit(pool):
  try:slot=next(cursor)
  except StopIteration:return False
  row={'slot':slot,'state':'reserved','started_at':utcnow()};r['cases'].append(row);r['model_calls']+=1;atomic_json(rp,r)
  payload={'model':TEXT_MODEL,'messages':[{'role':'user','content':'Reply with OK only.'}],'temperature':0,'max_tokens':256}
  pending[pool.submit(post_fn,'/chat/completions',env[slot],payload,timeout=70)]=row;return True
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  submit(pool);submit(pool)
  while pending:
   done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in done:
    row=pending.pop(f)
    try:safe,obj=f.result()
    except Exception:safe,obj={'http_status':None},None
    content=None
    try:
     content=obj['choices'][0]['message']['content']
     if isinstance(content,list):content=''.join(x.get('text','') for x in content if isinstance(x,dict))
    except (KeyError,TypeError,IndexError):pass
    status=safe.get('http_status');valid=status==200 and isinstance(content,str) and bool(content.strip()) and obj.get('model',TEXT_MODEL)==TEXT_MODEL
    row.update(state='healthy' if valid else 'invalid_text_response' if status==200 else 'account_rejected' if status in (401,402,403,429) else 'uncertain_or_service_failure',http_status=status,checked_at=utcnow())
    if status not in (200,401,402,403,429):halt=True;stop(out,'text')
   atomic_json(rp,r)
   if not halt:
    while len(pending)<2 and submit(pool):pass
 r.update(status='incomplete_provider_failure' if halt else 'completed',completed_at=utcnow());atomic_json(rp,r)
 h={'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'run_id':env['GITHUB_RUN_ID'],'audit_status':'incomplete' if halt else 'completed','checked_at':r['started_at'],'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,'family_model_routing_sha256':route_binding(roles),'source_request_id':rid,'unique_credentials_tested':len(r['cases']),'eligible_text_slots':[x['slot'] for x in r['cases'] if x['state']=='healthy'],'eligible_image_slots':image_proofs(out,roles),'image_capability_proofs':embedded_proofs(out,roles),'slots':[dict(x,text={'state':x['state']},image={'state':'independently_probed_only'}) for x in r['cases']]}
 atomic_json(hp,h);r['families_with_text']=sum(bool(set(x['text_slots'])&set(h['eligible_text_slots'])) for x in roles['families'].values())
 if not halt and r['families_with_text']<20:r['status']='family_text_capacity_incomplete'
 atomic_json(rp,r);return r

def images(env,data=DATA,out=OUT,probe_fn=None,reserve_fn=reserve):
 roles=context(env,data);hp=out/'parallel/health/latest.json';h=load_json(hp) if hp.exists() else {};rb=route_binding(roles);proven=image_proofs(out,roles)
 result={'status':'image_capability_batch_completed','run_id':env['GITHUB_RUN_ID'],'image_model':IMAGE_MODEL,'model_calls':0,'image_calls':0,'max_image_calls':4,'published_posts':0,'cases':[],'publication_visual_approval':False,'original_attempts_reset':False}
 if active_hold(out,'image'):return dict(result,status='shared_image_cooldown')
 from .image_key_audit import probe
 from .image_transport import AdmissionBlocked
 from automation.blog_image_queue import ImageQueueBusy
 calls=0
 with tempfile.TemporaryDirectory(prefix='afp-family-image-proof-') as td:
  db=td+'/pool.db';initialize(db,[r['image_slot'] for r in roles['families'].values()],max_calls=4,per_worker=1)
  for family,role in roles['families'].items():
   slot=role['image_slot'];receipt=out/'parallel/capability-refresh'/day()/'image'/(slot+'.json')
   if slot in proven or receipt.exists():continue
   if calls>=4:break
   rid='family-capability-'+day()+'-image-'+slot
   if reserve_fn('capability',rid,env) is None:
    row={'status':'reconciliation_required','slot':slot,'family_id':family,'image_calls':0};atomic_json(receipt,row);result['cases'].append(row);result['status']='capability_reconciliation_required';break
   row={'status':'reserved','slot':slot,'family_id':family,'model':IMAGE_MODEL,'image_calls':1,'started_at':utcnow()};atomic_json(receipt,row);calls+=1;result['image_calls']+=1
   e=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=db,AFP_PARALLEL_FAMILY=family,AFP_PARALLEL_TOPIC='capability-'+family)
   try:
    with lease(db,'image',[slot],family):safe,blob=(probe if probe_fn is None else probe_fn)(slot,env[slot],env=e)
   except (AdmissionBlocked,ImageQueueBusy):row.update(status='admission_blocked_not_sent',image_calls=0);result['image_calls']-=1;atomic_json(receipt,row);result['cases'].append(row);continue
   except Exception:safe,blob={'http_status':None,'state':'uncertain'},None
   status=safe.get('http_status');row.update(http_status=status,completed_at=utcnow(),status='verified' if safe.get('state')=='healthy' and blob else 'failed')
   if row['status']=='verified':
    from PIL import Image
    import io,hashlib
    try:
     image=Image.open(io.BytesIO(blob));image.verify()
     if image.width<768 or image.height<432 or image.width<=image.height:raise ValueError('Invalid capability image')
     media=receipt.with_suffix('.webp');media.write_bytes(blob)
     proof={'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'family_id':family,'slot':slot,'kind':'image','model':IMAGE_MODEL,'verified_at':utcnow(),'verification':'actual_successful_parallel_capability_probe','run_id':env['GITHUB_RUN_ID'],'family_model_routing_sha256':rb,'family_key_allocation_sha256':allocation_binding(allocation(data)),'image_sha256':hashlib.sha256(blob).hexdigest(),'publication_visual_approval':False}
     atomic_json(out/'parallel/runtime/image'/(slot+'.json'),proof)
    except Exception:row['status']='failed_invalid_image'
   if status is None or status>=500:row['status']='reconciliation_required'
   atomic_json(receipt,row);result['cases'].append(row)
   if status not in (200,401,402,403,429):stop(out,'image');result['status']='incomplete_provider_failure';break
 h['eligible_image_slots']=image_proofs(out,roles);h['image_capability_proofs']=embedded_proofs(out,roles);atomic_json(hp,h)
 result.update(proven_families=len(h['eligible_image_slots']),pending_families=20-len(h['eligible_image_slots']),completed_at=utcnow())
 atomic_json(out/'parallel/capability-refresh'/('images-run-'+env['GITHUB_RUN_ID']+'.json'),result);return result
