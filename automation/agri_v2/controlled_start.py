"""One owner-authorized manual production cycle, with a durable no-replay gate.
The cron workflow is disabled again immediately after dispatch by the operator.
This gate additionally rejects any cron event and pauses config on completion.
"""
import base64,datetime,hashlib,json,os,urllib.request,urllib.error
from pathlib import Path
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow,age_hours
ID='afp-pipe-controlled-start-v1'
MATRIX='afp-three-models-two-keys-reference-matrix-v1'
REPO='kapitansaman/afp-pipe'
LEDGER='data/agri-v2/status/controlled-cycles/'+ID+'.json'

def authorized(req,data=None,out=None,root=None):
 data=DATA if data is None else Path(data);out=OUT if out is None else Path(out);root=ROOT if root is None else Path(root)
 from .image_quality import REVIEW_POLICY,SCORE_POLICY
 from .healthcheck import IMAGE_MODEL
 from .credential_policy import trusted
 cfg=load_json(data/'config.json');health=load_json(data/'health/latest.json')
 if (req.get('request_id')!=ID or req.get('authorized') is not True or req.get('mode')!='one_manual_source_ready_critical_checks' or req.get('max_posts_per_run')!=1 or req.get('max_cycles')!=1 or req.get('preserve_publication_holds') is not True or req.get('review_policy')!=REVIEW_POLICY or req.get('score_policy')!=SCORE_POLICY):raise ValueError('Exact owner-authorized controlled start required')
 if cfg.get('controlled_start',{}).get('active') is not True or cfg.get('repository')!=REPO or not cfg.get('automatic_generation') or not cfg.get('publication_enabled') or cfg.get('max_posts_per_run')!=1 or IMAGE_MODEL!='agnes-image-2.5-flash':raise ValueError('Controlled destination configuration mismatch')
 if not trusted(health,data) or health.get('image_model')!=IMAGE_MODEL or not 0<=age_hours(health['checked_at'])<24 or not health.get('eligible_text_slots'):raise ValueError('Fresh bound capability evidence required')
 path=out/'activation-readiness'/ID/'report.json'
 if hashlib.sha256(path.read_bytes()).hexdigest()!=req.get('readiness_report_sha256'):raise ValueError('Controlled readiness proof changed')
 proof=load_json(path)
 if proof.get('repository')!=REPO or proof.get('credential_set_id')!=cfg.get('credential_set_id') or not 0<=age_hours(proof['checked_at'])<24 or proof.get('source_paused') is not True or proof.get('matrix_run_conclusion')!='success' or proof.get('wordpress_connection',{}).get('can_publish') is not True:raise ValueError('Current source, connection and diagnostic readiness required')
 for topic,reason in proof.get('preserved_publication_holds',{}).items():
  if cfg.get('publication_holds',{}).get(topic)!=reason:raise ValueError('A preserved publication hold changed')
 matrix=out/'model-matrix'/MATRIX/'report.json'
 if hashlib.sha256(matrix.read_bytes()).hexdigest()!=proof.get('matrix_report_sha256'):raise ValueError('Matrix proof changed')
 report=load_json(matrix)
 if report.get('status')!='completed' or report.get('run_id')!=proof.get('matrix_run_id'):raise ValueError('Completed matrix proof required')
 for slot in ('AGNES_API_KEY2','AGNES_API_KEY3'):
  rows=[r for r in report['cases'] if r.get('model')==IMAGE_MODEL and r.get('slot')==slot and r.get('mode')=='reference']
  if len(rows)!=1 or rows[0].get('state')!='healthy' or rows[0].get('valid_image') is not True or rows[0].get('native_landscape_16_9') is not True or slot not in health.get('eligible_image_slots',[]):raise ValueError('Both reference-conditioned image slots must be verified')
  image=(out/rows[0]['image_path']).resolve()
  if not image.is_relative_to((out/'model-matrix'/MATRIX).resolve()) or hashlib.sha256(image.read_bytes()).hexdigest()!=rows[0].get('image_sha256'):raise ValueError('Diagnostic image bytes changed')
 return True

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):return None

def reserve(config,env=None,remote_put=None):
 env=os.environ if env is None else env
 policy=config.get('controlled_start',{})
 if policy.get('active') is not True:return None
 if policy.get('request_id')!=ID or policy.get('max_cycles')!=1:raise ValueError('Exact one-cycle policy required')
 if env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_REPOSITORY')!=REPO or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch':return {'allowed':False,'status':'controlled_manual_event_required'}
 if not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ValueError('Verified Actions run identity required')
 receipt={'request_id':ID,'status':'reserved','allowed':True,'max_cycles':1,'run_id':env.get('GITHUB_RUN_ID'),'started_at':utcnow(),'original_attempts_reset':False}
 if remote_put is None:
  token=env.get('GITHUB_TOKEN')
  if not token:raise ValueError('Durable controlled-run reservation unavailable')
  payload={'message':'Reserve exactly one controlled AFP cycle [skip ci]','branch':'feat/agri-generator-v2-2905-merge593','content':base64.b64encode((json.dumps(receipt,indent=2)+'\n').encode()).decode()}
  request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/contents/'+LEDGER,data=json.dumps(payload).encode(),method='PUT',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'AFP-controlled-start'})
  try:
   with urllib.request.build_opener(NoRedirect()).open(request,timeout=30) as r:created=r.status==201
  except urllib.error.HTTPError as exc:
   code=exc.code;exc.close()
   if code==422:return {'allowed':False,'status':'controlled_cycle_already_reserved'}
   raise ValueError('Controlled-run reservation rejected; no production calls') from None
  except Exception:raise ValueError('Controlled-run reservation uncertain; no production calls') from None
 else:created=remote_put(receipt)
 if not created:return {'allowed':False,'status':'controlled_cycle_already_reserved'}
 atomic_json(OUT/'controlled-start'/ID/'receipt.json',receipt)
 return receipt

def finish(receipt,result=None,error=None):
 if not receipt or receipt.get('allowed') is not True:return
 cfg=load_json(DATA/'config.json');cfg['automatic_generation']=False;cfg['publication_enabled']=False;cfg['cutover']['status']='controlled_cycle_finished_paused';cfg['controlled_start']['active']=False;atomic_json(DATA/'config.json',cfg)
 safe={k:result[k] for k in ['status','topic_id','post_id','url','public_verified','published_posts'] if isinstance(result,dict) and k in result}
 receipt.update(status='finished' if error is None else 'blocked_or_failed',finished_at=utcnow(),result=safe,publication_paused_after_cycle=True)
 if error is not None:receipt['error_type']=type(error).__name__
 atomic_json(OUT/'controlled-start'/ID/'receipt.json',receipt)
 from .progress import publish_file
 publish_file(LEDGER,json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
