"""Maintain capability freshness from real successful use; at most one text probe per six hours.
Never claim a fresh image probe, extend old evidence, or audit the whole key pool.
"""
import hashlib,json,os
from pathlib import Path
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow,age_hours
from .healthcheck import SLOTS,TEXT_MODEL,IMAGE_MODEL,API_BASE,post
from .recovery import circuit_open
MAX_AGE=24

def record(kind,slot,model,blob=None):
 if kind not in ('text','image') or slot not in SLOTS or model!=({'text':TEXT_MODEL,'image':IMAGE_MODEL}[kind]):return
 from .credential_policy import binding
 row={**binding(),'kind':kind,'slot':slot,'model':model,'api_base':API_BASE,'verified_at':utcnow(),'verification':'actual_successful_production_response','run_id':os.environ.get('GITHUB_RUN_ID')}
 if blob is not None:row['decoded_image_sha256']=hashlib.sha256(blob).hexdigest()
 atomic_json(OUT/'runtime-health'/kind/(slot+'.json'),row)

def fresh(at):
 try:return 0<=age_hours(at)<MAX_AGE
 except (ValueError,TypeError,KeyError):return False

def evidence(out=OUT):
 result={'text':{},'image':{}}
 def take(kind,slot,row,path):
  from .credential_policy import trusted
  if not trusted(row):return
  if slot not in SLOTS or not fresh(row.get('verified_at')):return
  old=result[kind].get(slot)
  if not old or age_hours(row['verified_at'])<age_hours(old['verified_at']):result[kind][slot]={**row,'evidence_path':str(path)}
 audit=out/'image-key-audit/unique-image-capability-v1/report.json'
 if audit.exists():
  report=load_json(audit)
  from .credential_policy import trusted
  if report.get('model')==IMAGE_MODEL and trusted(report):
   for row in report.get('cases',[]):
    if row.get('state')!='healthy' or row.get('http_status')!=200 or not row.get('path'):continue
    path=(ROOT/row['path']).resolve()
    if not path.is_relative_to((ROOT/'artifacts/agri-v2/image-key-audit').resolve()) or path.suffix!='.webp':continue
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==row.get('sha256'):
     take('image',row.get('slot'),{'verified_at':row.get('checked_at'),'model':IMAGE_MODEL,'api_base':API_BASE,'verification':'actual_image_audit_with_matching_saved_bytes'},audit)
 for kind,model in [('text',TEXT_MODEL),('image',IMAGE_MODEL)]:
  for path in (out/'runtime-health'/kind).glob('*.json'):
   row=load_json(path)
   if row.get('kind')==kind and row.get('model')==model and row.get('api_base')==API_BASE and row.get('verification') in {'actual_successful_production_response','actual_bounded_text_probe'}:take(kind,row.get('slot'),row,path)
 return result

def ensure_fresh(data=DATA,out=OUT,env=None,post_fn=None):
 hp=data/'health/latest.json';old=load_json(hp) if hp.exists() else {}
 from .credential_policy import trusted,binding
 if fresh(old.get('checked_at')) and trusted(old,data):return {'status':'health_current','model_calls':0}
 config=load_json(data/'config.json').get('runtime_health',{})
 if config.get('enabled') is not True or config.get('max_text_probes_per_6h')!=1 or config.get('max_image_probes')!=0:return {'status':'health_refresh_not_authorized','model_calls':0}
 ev=evidence(out);env=os.environ if env is None else env;post_fn=post if post_fn is None else post_fn;calls=0
 if not ev['image']:return {'status':'image_capability_evidence_expired','model_calls':0}
 if not ev['text']:
  probe_path=out/'runtime-health/text-probe-reservation.json';previous=load_json(probe_path) if probe_path.exists() else {}
  if previous.get('at') and age_hours(previous['at'])<6:return {'status':'text_probe_cooldown','model_calls':0}
  if circuit_open('text'):return {'status':'provider_cooldown','model_calls':0}
  slot=next((s for s in old.get('eligible_text_slots',[]) if s in SLOTS and env.get(s,'').strip()),None)
  if not slot:return {'status':'no_verified_text_credential','model_calls':0}
  atomic_json(probe_path,{'at':utcnow(),'slot':slot,'max_calls':1,'image_calls':0,'status':'reserved'})
  safe,obj=post_fn('/chat/completions',env[slot].strip(),{'model':TEXT_MODEL,'messages':[{'role':'user','content':'Reply with OK only.'}],'temperature':0,'max_tokens':256},timeout=70);calls=1
  valid=False
  if isinstance(obj,dict) and obj.get('model',TEXT_MODEL)==TEXT_MODEL:
   try:
    content=obj['choices'][0]['message']['content']
    if isinstance(content,list):content=''.join(x.get('text','') for x in content if isinstance(x,dict) and isinstance(x.get('text'),str))
    valid=safe.get('http_status')==200 and isinstance(content,str) and bool(content.strip())
   except (KeyError,IndexError,TypeError):pass
  atomic_json(probe_path,{'at':utcnow(),'slot':slot,'max_calls':1,'image_calls':0,'status':'verified' if valid else 'failed','http_status':safe.get('http_status')})
  if not valid:return {'status':'bounded_text_probe_failed','model_calls':calls}
  row={**binding(data),'kind':'text','slot':slot,'model':TEXT_MODEL,'api_base':API_BASE,'verified_at':utcnow(),'verification':'actual_bounded_text_probe','run_id':os.environ.get('GITHUB_RUN_ID')}
  path=out/'runtime-health/text'/(slot+'.json');atomic_json(path,row);ev['text'][slot]={**row,'evidence_path':str(path)}
 # This is the oldest still-valid underlying observation, NOT the rebuild time.
 checked=max((r['verified_at'] for kind in ev.values() for r in kind.values()),key=age_hours)
 report={**binding(data),'version':2,'checked_at':checked,'rebuilt_at':utcnow(),'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,'slot_limit':len(SLOTS),'slots':[], 'eligible_text_slots':[s for s in SLOTS if s in ev['text']], 'eligible_image_slots':[s for s in SLOTS if s in ev['image']],'capability_evidence':ev,'scope':'Only actual unexpired per-capability observations; no blanket pool refresh','new_image_probes':0}
 for s in SLOTS:
  report['slots'].append({'slot':s,'configured':bool(env.get(s,'')),'text':{'state':'healthy' if s in ev['text'] else 'not_reverified'},'image':{'state':'healthy' if s in ev['image'] else 'not_reverified'}})
 if hp.exists():atomic_json(out/'runtime-health/snapshots'/('before-'+utcnow().replace(':','-')+'.json'),old)
 atomic_json(hp,report)
 return {'status':'health_refreshed_from_actual_evidence','model_calls':calls,'new_image_calls':0,'eligible_text_slots':report['eligible_text_slots'],'eligible_image_slots':report['eligible_image_slots']}
