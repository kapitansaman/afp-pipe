"""Text-first parallel client; image capability must be proved separately, never inferred."""
import os
from .client import ModelClient,CapabilityError,TextProviderError,ImageProviderError
from .parallel_pool import SLOTS,lease,defer,defer_slot,disable
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours
from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE

class ParallelModelClient(ModelClient):
 def __init__(self,report,env=None,allow_calls=False,capabilities=('text',)):
  self.env=os.environ if env is None else env
  self.data=DATA
  if not allow_calls or self.env.get('AFP_PARALLEL_WORKER')!='1' or not self.env.get('AFP_PARALLEL_POOL_DB'):raise CapabilityError('Controlled parallel worker required')
  if self.env.get('GITHUB_ACTIONS')=='true' and self.env.get('GITHUB_REPOSITORY')!='kapitansaman/afp-pipe':raise CapabilityError('Destination Actions identity required')
  policy=load_json(DATA/'parallel-policy.json')
  if report.get('repository')!='kapitansaman/afp-pipe' or report.get('credential_set_id')!=policy['credential_set_id'] or not 0<=age_hours(report['checked_at'])<24:raise CapabilityError('Fresh parallel capability evidence required')
  if (report.get('text_model'),report.get('image_model'),report.get('api_base'))!=(TEXT_MODEL,IMAGE_MODEL,API_BASE):raise CapabilityError('Parallel model/base mismatch')
  from .family_keys import slots_for,check_unique_values
  self.family_key_slots,self.family_key_binding=slots_for(self.env.get('AFP_PARALLEL_FAMILY'),DATA)
  if self.family_key_slots is not None:check_unique_values(self.env)
  self.report=report;self.used={'text':0,'image':0};self.keys={}
  for kind in ('text','image'):
   names=report.get('eligible_'+kind+'_slots',[])
   if any(n not in SLOTS for n in names):raise CapabilityError('Unknown parallel capability slot')
   if self.family_key_slots is not None:names=[n for n in names if n in self.family_key_slots]
   from .family_model_routing import slots as role_slots
   role=role_slots(self.env.get('AFP_PARALLEL_FAMILY'),kind,self.data)
   if role is not None:
    names=[n for n in names if n in role]
    if kind=='image':
     from .family_model_routing import load as load_roles,binding as role_binding
     rb=role_binding(load_roles(DATA));proofs=report.get('image_capability_proofs',{})
     names=[n for n in names if isinstance(proofs.get(n),dict) and proofs[n].get('slot')==n and proofs[n].get('family_id')==self.env.get('AFP_PARALLEL_FAMILY') and proofs[n].get('model')==IMAGE_MODEL and proofs[n].get('family_model_routing_sha256')==rb and 0<=age_hours(proofs[n]['verified_at'])<24]
   seen=set();pool=[]
   for n in names:
    key=self.env.get(n,'').strip()
    if key and key not in seen:pool.append((n,key));seen.add(key)
   self.keys[kind]=pool
   if kind in capabilities and not pool:
    if self.family_key_slots is not None:
     from .family_keys import FamilyCapabilityRequired
     raise FamilyCapabilityRequired(kind)
    raise CapabilityError('No verified '+kind+' capability')
  self.image_rotation_enabled=bool(self.keys['image']);self.image_rotation_binding=policy['credential_set_id']
  self.image_candidates=list(self.keys['image'])
 def request(self,kind,path,payload,timeout,attempts=None):
  db=self.env['AFP_PARALLEL_POOL_DB'];pool=self.keys[kind];values=dict(pool)
  if self.family_key_slots is not None and not set(values)<=set(self.family_key_slots):raise CapabilityError('Foreign family credential rejected before lease')
  from .family_model_routing import slots as role_slots
  role=role_slots(self.env.get('AFP_PARALLEL_FAMILY'),kind,self.data)
  if role is not None:
   if not set(values)<=set(role):raise CapabilityError('Wrong family capability role rejected before lease')
   if kind=='image' and (path!='/images/generations' or payload.get('model')!=IMAGE_MODEL):raise CapabilityError('Image role requires image model and endpoint')
   if kind=='text' and (path!='/chat/completions' or str(payload.get('model','')).startswith('agnes-image-')):raise CapabilityError('Text role cannot invoke image model')
  with lease(db,kind,list(values),self.env.get('AFP_PARALLEL_TOPIC','worker')) as slot:
   self.keys[kind]=[(slot,values[slot])]
   try:return super().request(kind,path,payload,timeout,attempts=1)
   except (TextProviderError,ImageProviderError) as e:
    if e.http_status in (401,403):disable(db,slot)
    elif e.http_status in (402,429):defer_slot(db,slot,max(3600,e.retry_after_seconds or 0))
    elif e.http_status is None or isinstance(e.http_status,int) and e.http_status>=500:defer(db,max(3600,e.retry_after_seconds or 0))
    raise
   finally:self.keys[kind]=pool
 def record_success(self,kind,model,blob=None):
  # Worker-local evidence, merged once by coordinator; never mutate serial health.
  slot=getattr(self,'last_'+kind+'_slot',None)
  if slot not in SLOTS:return
  row={'repository':'kapitansaman/afp-pipe','credential_set_id':self.image_rotation_binding,'kind':kind,'slot':slot,'model':model,'verified_at':utcnow(),'verification':'actual_successful_parallel_response','family_id':self.env.get('AFP_PARALLEL_FAMILY'),'topic_id':self.env.get('AFP_PARALLEL_TOPIC')}
  if self.family_key_binding is not None:row.update(family_key_allocation_sha256=self.family_key_binding,assigned_key_slots=list(self.family_key_slots))
  from .family_model_routing import load as load_roles,binding as role_binding
  roles=load_roles(self.data)
  if roles is not None:row['family_model_routing_sha256']=role_binding(roles)
  atomic_json(OUT/'parallel-runtime'/kind/(slot+'.json'),row)
