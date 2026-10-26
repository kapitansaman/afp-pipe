"""Explicit 3-model x 2-key x 2-input diagnostic. No article or WordPress calls.
A fixed comparison, not production failover. One request per cell, no replay.
"""
import base64,datetime,hashlib,io,json,os,socket,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ID='afp-three-models-two-keys-reference-matrix-v1'
MODELS=('agnes-image-2.0-flash','agnes-image-2.1-flash','agnes-image-2.5-flash')
SLOTS=('AGNES_API_KEY2','AGNES_API_KEY3')
MODES=('plain','reference')
REQUEST={'request_id':ID,'models':list(MODELS),'slots':list(SLOTS),'modes':list(MODES),'max_image_calls':12,'max_calls_per_cell':1,'publication_authorized':False}
API_BASE='https://apihub.agnes-ai.com/v1'
MAX_RESPONSE=18*1024*1024
PROMPT='Photograph of one intact sealed white-blue product carton standing on bare soil, natural daylight, realistic photography, no people, no extra text. Use the attached reference identity when a reference image is supplied.'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def cells():
 return [{'case_id':f'{mode}-{slot}-{model}', 'model':model,'slot':slot,'mode':mode} for mode in MODES for slot in SLOTS for model in MODELS]
def payload(model,mode,refs):
 if model not in MODELS or mode not in MODES:raise ValueError('Out-of-scope comparison cell')
 body={'model':model,'prompt':PROMPT,'size':'1K','ratio':'16:9','return_base64':True,'extra_body':{'response_format':'b64_json'}}
 if mode=='reference':body['extra_body']['image']=refs
 return body
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):return None

def probe(cell,key):
 from .image_transport import admission
 from .media_policy import reference_images
 from .client import image_bytes
 from .healthcheck import classify
 from .provider_retry import retry_seconds
 from automation.agnes_key_pool import AgnesProviderError
 from PIL import Image,ImageChops
 refs=reference_images() if cell['mode']=='reference' else []
 body=payload(cell['model'],cell['mode'],refs)
 # The lease remains repository-wide and serialized for all diagnostic cells.
 with admission(cell['slot'],body,os.environ):
  request=urllib.request.Request(API_BASE+'/images/generations',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'AFP-explicit-model-matrix-v1'})
  started=time.monotonic()
  try:
   with urllib.request.build_opener(NoRedirect()).open(request,timeout=180) as response:
    raw=response.read(MAX_RESPONSE+1)
    if len(raw)>MAX_RESPONSE:return {'state':'response_too_large','http_status':200,'latency_ms':round((time.monotonic()-started)*1000)},None
    obj=json.loads(raw)
   row={'http_status':200,'latency_ms':round((time.monotonic()-started)*1000),'response_model':obj.get('model') if obj.get('model') in MODELS else None}
   if obj.get('model') and obj.get('model')!=cell['model']:return dict(row,state='model_mismatch'),None
   blob=image_bytes(obj)
   with Image.open(io.BytesIO(blob)) as im:
    w,h=im.size
    if w*h>20_000_000:return dict(row,state='dimensions_too_large',width=w,height=h),None
    image=im.convert('RGB');landscape=abs(w/h-16/9)/(16/9)<=.02
    for ref in refs:
     with Image.open(io.BytesIO(base64.b64decode(ref.split(',',1)[1],validate=True))) as original:
      if original.size==image.size and ImageChops.difference(original.convert('RGB'),image).getbbox() is None:return dict(row,state='reference_echo',width=w,height=h),None
    buf=io.BytesIO();image.save(buf,'WEBP',quality=85)
    return dict(row,state='healthy' if landscape else 'valid_image_wrong_aspect',width=w,height=h,native_landscape_16_9=landscape,valid_image=True,publication_visual_approval=False),buf.getvalue()
  except urllib.error.HTTPError as exc:
   code=exc.code;body=exc.read(12000);retry=retry_seconds(exc.headers.get('Retry-After'));exc.close();safe=AgnesProviderError(code,body)
   return {'state':classify(code,body),'http_status':code,'provider_code':safe.provider_code,'retry_after_seconds':retry,'latency_ms':round((time.monotonic()-started)*1000)},None
  except (TimeoutError,socket.timeout,urllib.error.URLError):return {'state':'transport_or_timeout','http_status':None,'latency_ms':round((time.monotonic()-started)*1000)},None
  except Exception as exc:return {'state':'invalid_or_undecodable_response','http_status':200,'error_type':type(exc).__name__,'latency_ms':round((time.monotonic()-started)*1000)},None

def run(env=None,data=None,out=None,probe_fn=None,sleep_fn=time.sleep,publish_fn=None,cooldown_fn=None):
 env=os.environ if env is None else env;data=Path(data or ROOT/'data/agri-v2');out=Path(out or ROOT/'artifacts/agri-v2')
 req=json.loads((data/'model-matrix-request.json').read_text())
 if req!=REQUEST:raise ValueError('Exact explicit 12-cell diagnostic authorization required')
 config=json.loads((data/'config.json').read_text())
 if config.get('repository')!='kapitansaman/afp-pipe' or config.get('publication_enabled') or config.get('automatic_generation'):raise ValueError('Destination production must remain paused')
 if probe_fn is None:
  if env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_REPOSITORY')!='kapitansaman/afp-pipe':raise ValueError('Live diagnostic requires destination Actions environment')
  probe_fn=probe
 if publish_fn is None:
  from .progress import publish_file
  publish_fn=lambda report:publish_file('data/agri-v2/status/model-matrix.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if cooldown_fn is None:
  from .recovery import circuit_open
  cooldown_fn=lambda:circuit_open('image')
 folder=out/'model-matrix'/ID;rp=folder/'report.json'
 report=json.loads(rp.read_text()) if rp.exists() else {'request_id':ID,'repository':'kapitansaman/afp-pipe','run_id':env.get('GITHUB_RUN_ID'),'started_at':now(),'status':'reserved','max_image_calls':12,'image_calls':0,'cases':[],'text_calls':0,'article_calls':0,'wordpress_calls':0,'post_submissions':0,'production_enabled':False,'publication_visual_approval':False}
 def save():
  report['updated_at']=now();report['completed_cells']=sum(c.get('state')!='reserved' for c in report['cases']);report['valid_images']=sum(c.get('valid_image') is True for c in report['cases']);report['healthy_cells']=sum(c.get('state')=='healthy' for c in report['cases']);atomic(rp,report)
  try:publish_fn(report)
  except Exception:pass
 keys=[env.get(s,'').strip() for s in SLOTS]
 if not all(keys) or len(set(keys))!=2:report['status']='missing_or_duplicate_credentials';save();return report
 if report.get('status')=='completed':return report
 if report.get('retry_at_epoch',0)>time.time() or cooldown_fn():report['status']='waiting_shared_provider_deadline';save();return report
 attempted={c['case_id'] for c in report['cases']}
 for cell in cells():
  if cell['case_id'] in attempted:continue
  if report['image_calls']>=12:break
  row=dict(cell,state='reserved',started_at=now());report['cases'].append(row);report['status']='in_progress';save()
  # Reserve before a possibly interrupted provider operation; a cell never replays.
  try:
   safe,blob=probe_fn(cell,keys[SLOTS.index(cell['slot'])])
  except Exception as exc:
   row.update(state='admission_or_local_error',error_type=type(exc).__name__,completed_at=now());report['status']='admission_or_local_error';save();return report
  report['image_calls']+=1
  allowed={'state','http_status','provider_code','retry_after_seconds','latency_ms','response_model','width','height','native_landscape_16_9','valid_image','publication_visual_approval','error_type'}
  row.update({k:v for k,v in safe.items() if k in allowed});row['completed_at']=now()
  if blob:
   target=folder/(cell['case_id']+'.webp');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob);row['image_path']=str(target.relative_to(out));row['image_sha256']=hashlib.sha256(blob).hexdigest()
  save()
  retry=row.get('retry_after_seconds')
  if row.get('http_status') in (402,429) or (isinstance(retry,(int,float)) and retry>0):
   # Quota/rate limits and explicit Retry-After pause ALL remaining cells, not just this key.
   report.update(status='waiting_shared_provider_deadline',retry_at_epoch=time.time()+max(1800,retry or 0));save();return report
  if row.get('http_status')==503 or row.get('state')=='transport_or_timeout':sleep_fn(60)
 report.update(status='completed' if len(report['cases'])==12 else 'budget_exhausted',completed_at=now());save();return report

def main():
 result=run();print(json.dumps({k:result.get(k) for k in ['request_id','status','image_calls','completed_cells','valid_images','healthy_cells','post_submissions','production_enabled']},ensure_ascii=False))
 return 0 if result['status']=='completed' else 2
if __name__=='__main__':raise SystemExit(main())
