"""One explicitly manual NEW diagnostic, never replay/reconcile an unknown call.
The old receipt stays immutable. No automatic retry, alternative key or publication.
"""
import hashlib,io,tempfile
from PIL import Image
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from . import family_capability_refresh as refresh
from .family_model_routing import binding as route_binding
from .family_keys import binding as allocation_binding,load as allocation
from .parallel_capacity import CREDENTIAL_SET_ID
from .parallel_control import reserve
from .parallel_pool import initialize,lease
from .healthcheck import IMAGE_MODEL
ID='family09-image-followup-v1'
SLOT='AGNES_API_KEY36'
FAMILY='family-09'
ORIGINAL='parallel/capability-refresh/20261028/image/AGNES_API_KEY36.json'
ORIGINAL_HASH='eb3ade86108f16b84192ea20d3c70858a4f62519d06064e12b16a7916ee4d170'
REQUEST={'request_id':ID,'family_id':FAMILY,'slot':SLOT,'model':'agnes-image-2.5-flash','original_receipt':ORIGINAL,'original_receipt_sha256':ORIGINAL_HASH,'max_new_image_requests':1,'automatic_retry':False,'original_outcome_resolved':False,'publication_authorized':False}

def run(env,data=DATA,out=OUT,probe_fn=None,reserve_fn=reserve):
 roles=refresh.context(env,data)
 if load_json(data/'image-capability-followup.json')!=REQUEST or IMAGE_MODEL!=REQUEST['model'] or roles['families'][FAMILY]['image_slot']!=SLOT:raise ValueError('Exact one-shot diagnostic contract required')
 original=out/ORIGINAL
 if not original.exists() or hashlib.sha256(original.read_bytes()).hexdigest()!=ORIGINAL_HASH:raise ValueError('Original unknown receipt changed or missing')
 old=load_json(original)
 if (old.get('status'),old.get('family_id'),old.get('slot'),old.get('model'))!=('reconciliation_required',FAMILY,SLOT,IMAGE_MODEL):raise ValueError('Original unknown identity mismatch')
 dest=out/'parallel/capability-followup'/ID;rp=dest/'report.json'
 base=dict(REQUEST,run_id=env['GITHUB_RUN_ID'],image_calls=0,model_calls=0,published_posts=0,original_attempts_reset=False)
 if rp.exists():return dict(base,status='followup_already_reserved_no_replay')
 proven=refresh.image_proofs(out,roles)
 if SLOT in proven:return dict(base,status='followup_not_needed')
 others={v['image_slot'] for f,v in roles['families'].items() if f!=FAMILY}
 if not others.issubset(proven):return dict(base,status='followup_waiting_other_19')
 accepted=out/'parallel/scoped-family-pilot/accepted.json';a=load_json(accepted) if accepted.exists() else {}
 if not(a.get('status')=='scoped_family_pilot_verified' and a.get('public_verified') is True and a.get('family_model_routing_sha256')==route_binding(roles) and a.get('image_model')==IMAGE_MODEL and refresh.fresh(a.get('checked_at'))):return dict(base,status='followup_waiting_accepted_pilot')
 if refresh.active_hold(out,'image'):return dict(base,status='shared_image_cooldown')
 if reserve_fn('capability-followup',ID,env) is None:
  result=dict(base,status='followup_reconciliation_required');atomic_json(rp,result);return result
 result=dict(base,status='reserved',started_at=utcnow(),image_calls=1);atomic_json(rp,result)
 from .image_key_audit import probe
 from .image_transport import AdmissionBlocked
 from automation.blog_image_queue import ImageQueueBusy
 with tempfile.TemporaryDirectory(prefix='afp-one-shot-image-') as td:
  db=td+'/pool.db';initialize(db,[SLOT],max_calls=1,per_worker=1)
  e=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=db,AFP_PARALLEL_FAMILY=FAMILY,AFP_PARALLEL_TOPIC=ID)
  try:
   with lease(db,'image',[SLOT],FAMILY):safe,blob=(probe if probe_fn is None else probe_fn)(SLOT,env[SLOT],env=e,diagnostic_id=ID)
  except (AdmissionBlocked,ImageQueueBusy):
   result.update(status='followup_admission_blocked_not_sent',image_calls=0,completed_at=utcnow());atomic_json(rp,result);return result
  except Exception as exc:safe,blob={'http_status':None,'state':'uncertain','error_type':type(exc).__name__},None
 result.update(refresh.image_diagnostic(safe),http_status=safe.get('http_status'),completed_at=utcnow(),status='followup_failed')
 if safe.get('http_status')==200 and safe.get('state')=='healthy' and blob:
  try:
   image=Image.open(io.BytesIO(blob));image.verify()
   if image.width<768 or image.height<432 or image.width<=image.height:raise ValueError('Invalid capability image')
   dest.mkdir(parents=True,exist_ok=True);(dest/'diagnostic.webp').write_bytes(blob)
   proof={'repository':'kapitansaman/afp-pipe','credential_set_id':CREDENTIAL_SET_ID,'family_id':FAMILY,'slot':SLOT,'kind':'image','model':IMAGE_MODEL,'verified_at':utcnow(),'verification':'actual_successful_parallel_capability_probe','run_id':env['GITHUB_RUN_ID'],'family_model_routing_sha256':route_binding(roles),'family_key_allocation_sha256':allocation_binding(allocation(data)),'image_sha256':hashlib.sha256(blob).hexdigest(),'publication_visual_approval':False,'followup_request_id':ID,'original_receipt_sha256':ORIGINAL_HASH,'original_outcome_resolved':False}
   atomic_json(out/'parallel/runtime/image'/(SLOT+'.json'),proof);result['status']='followup_verified_new_diagnostic'
  except Exception:result['status']='followup_failed_invalid_image'
 if safe.get('http_status') not in (200,401,402,403,429):
  refresh.stop(out,'image');result['status']='followup_reconciliation_required'
 # A fresh capability does not reconcile the old request or renew text health.
 hp=out/'parallel/health/latest.json';h=load_json(hp) if hp.exists() else {}
 h.update(eligible_image_slots=refresh.image_proofs(out,roles),image_capability_proofs=refresh.embedded_proofs(out,roles));atomic_json(hp,h)
 result['proven_families']=len(h['eligible_image_slots']);atomic_json(rp,result);return result
