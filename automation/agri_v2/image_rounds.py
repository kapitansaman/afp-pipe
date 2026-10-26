"""Owner-authorized one round per image: at most 30 unique slots, no replay.
Shared provider deadlines defer the round; they are never bypassed by a key.
"""
import hashlib,json,time
from .queue import OUT,atomic_json,load_json,utcnow

def generate(client,body,references):
 from .client import CapabilityError,ImageProviderError,render_image
 from .healthcheck import IMAGE_MODEL
 from .image_transport import AdmissionBlocked
 from automation.blog_image_queue import ImageQueueBusy
 identity={'body':body,'credential_set_id':client.image_rotation_binding}
 ident=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
 folder=OUT/'image-key-rounds'/ident;rp=folder/'report.json';target=folder/'verified.webp'
 state=load_json(rp) if rp.exists() else {'request_id':ident,'model':IMAGE_MODEL,'credential_set_id':client.image_rotation_binding,'max_attempts':30,'attempts':[],'created_at':utcnow(),'status':'ready'}
 if state['status']=='verified':
  if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=state.get('image_sha256'):raise CapabilityError('Saved image round evidence missing or changed')
  return target.read_bytes()
 if state.get('retry_at_epoch',0)>time.time():raise AdmissionBlocked('Image round waiting for shared provider deadline')
 tried={r['slot'] for r in state['attempts']};pool=[];seen=set()
 for name,key in client.image_candidates:
  if key and key not in seen:pool.append((name,key));seen.add(key)
 routing=OUT/'image-key-routing.json'
 prior=load_json(routing).get('last_selected_slot') if routing.exists() else None
 names=[n for n,k in pool]
 if prior in names:
  offset=names.index(prior)+1;pool=pool[offset:]+pool[:offset]
 remaining=[(n,k) for n,k in pool if n not in tried]
 if len(state['attempts'])>=30 or not remaining:raise CapabilityError('Single image key round exhausted; no automatic reset')
 original=client.keys['image']
 try:
  for _ in range(min(30-len(state['attempts']),len(remaining))):
   client.keys['image']=[remaining[0]]
   row=None
   def reserve(name):
    nonlocal row
    if name in tried or len(state['attempts'])>=30:raise CapabilityError('Image key attempt already reserved')
    row={'slot':name,'started_at':utcnow(),'status':'reserved'};state['attempts'].append(row);tried.add(name);state['status']='in_progress';atomic_json(rp,state)
   client._image_reserve_attempt=reserve
   try:
    obj=client.request('image','/images/generations',body,180)
    if obj.get('model') and obj['model']!=IMAGE_MODEL:raise CapabilityError('Image model mismatch')
    blob=render_image(obj,require_landscape=True,reject_reference_images=references)
    target.write_bytes(blob);row.update(status='verified',completed_at=utcnow());state.update(status='verified',image_sha256=hashlib.sha256(blob).hexdigest(),completed_at=utcnow());atomic_json(rp,state);client.record_success('image',IMAGE_MODEL,blob);return blob
   except (AdmissionBlocked,ImageQueueBusy):
    state['status']='admission_deferred';atomic_json(rp,state);raise
   except ImageProviderError as exc:
    if row is not None:row.update(status='provider_rejected',http_status=exc.http_status,provider_code=exc.provider_code,category=exc.category)
    if exc.http_status in (402,429,503) or exc.http_status is None or exc.provider_code=='image_queue_full' or exc.retry_after_seconds:
     state.update(status='shared_provider_deferred',retry_at_epoch=time.time()+max(1800,exc.retry_after_seconds or 0));atomic_json(rp,state);raise
    if exc.http_status not in (401,403):
     state['status']='request_or_provider_error';atomic_json(rp,state);raise
   except CapabilityError:
    if row is None:raise # Existing caller/admission budget is not a paid failed response.
    row.update(status='invalid_image_response',completed_at=utcnow())
   state['status']='next_unique_key';atomic_json(rp,state);remaining=[(n,k) for n,k in remaining if n not in tried]
  state.update(status='exhausted',completed_at=utcnow());atomic_json(rp,state)
  raise CapabilityError('All available unique image keys tried once; no automatic reset')
 finally:
  client.keys['image']=original
  if hasattr(client,'_image_reserve_attempt'):del client._image_reserve_attempt
