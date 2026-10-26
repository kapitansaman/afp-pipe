"""One bounded fresh check of the new 30-key set. Never publishes articles.
All credentials are read only from job environment. Shared provider limits end
this audit rather than being bypassed by another key. Historical key evidence
is not reused after repository migration/rotation.
"""
import json,os,time
from pathlib import Path
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow
from .healthcheck import SLOTS,TEXT_MODEL,IMAGE_MODEL,API_BASE,post
from .credential_policy import binding
ID='afp-pipe-30-keys-v1'
MAX_KEYS=30

def text_result(safe,obj):
 row=dict(safe)
 if obj is not None:
  try:
   content=obj['choices'][0]['message']['content']
   if isinstance(content,list):content=''.join(x.get('text','') for x in content if isinstance(x,dict))
   row['state']='healthy' if isinstance(content,str) and content.strip() else 'invalid_text_response'
   if obj.get('model',TEXT_MODEL)!=TEXT_MODEL:row['state']='model_mismatch'
  except (KeyError,IndexError,TypeError,AttributeError):row['state']='invalid_text_response'
 return {k:v for k,v in row.items() if k in {'state','http_status','latency_ms'}}

def run(env=None,post_fn=None,image_probe=None,data=DATA,out=OUT,record_fn=None,max_image_calls=None):
 env=os.environ if env is None else env;post_fn=post if post_fn is None else post_fn
 image_budget=MAX_KEYS if max_image_calls is None else max_image_calls
 if type(image_budget) is not int or not 1<=image_budget<=MAX_KEYS:raise ValueError('Image budget outside explicit limit')
 config=load_json(data/'config.json')
 if config.get('repository')!='kapitansaman/afp-pipe' or config.get('credential_set_id')!=ID or config.get('max_key_slot')!=30:raise ValueError('Exact migrated 30-key configuration required')
 if config.get('publication_enabled') or config.get('automatic_generation'):raise ValueError('Fresh credential setup requires publication paused')
 dest=out/'key-connection'/ID;rp=dest/'report.json'
 if rp.exists():return {'status':'already_reserved','model_calls':0,'post_submissions':0}
 owners={};unique=[];aliases={};slots=[]
 for slot in SLOTS:
  key=env.get(slot,'').strip()
  if key:
   if key in owners:aliases[slot]=owners[key]
   else:owners[key]=slot;unique.append((slot,key))
  slots.append({'slot':slot,'configured':bool(key),'text':{'state':'not_probed' if key else 'missing'},'image':{'state':'not_probed' if key else 'missing'}})
 report={**binding(data),'request_id':ID,'status':'reserved','started_at':utcnow(),'run_id':env.get('GITHUB_RUN_ID'),'configured_slots':sum(x['configured'] for x in slots),'unique_credentials':len(unique),'duplicate_slots':aliases,'max_text_calls':30,'max_image_calls':image_budget,'text_calls':0,'image_calls':0,'cases':[],'post_submissions':0,'wordpress_calls':0,'article_calls':0}
 atomic_json(rp,report)
 from .progress import update
 update('بررسی تازه اتصال ۳۰ کلید؛ انتشار در مقصد هنوز متوقف است',0,status='health_refresh_required')
 if len(unique)!=30 or report['configured_slots']!=30:
  report.update(status='configuration_incomplete_or_duplicate',completed_at=utcnow());atomic_json(rp,report);return report
 health={**binding(data),'version':3,'checked_at':utcnow(),'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,'slot_limit':30,'configured_slots':30,'unique_credentials_tested':0,'slots':slots,'eligible_text_slots':[],'eligible_image_slots':[],'no_publication':True}
 byslot={r['slot']:r for r in slots}
 from .runtime_health import record
 record_fn=record if record_fn is None else record_fn
 from .recovery import circuit_open
 stop_text=False
 for slot,key in unique:
  if circuit_open('text'):stop_text=True;break
  report['text_calls']+=1;atomic_json(rp,report)
  safe,obj=post_fn('/chat/completions',key,{'model':TEXT_MODEL,'messages':[{'role':'user','content':'Reply with OK only.'}],'temperature':0,'max_tokens':256},timeout=70)
  row=text_result(safe,obj);byslot[slot]['text']=row;health['unique_credentials_tested']=report['text_calls']
  if row.get('state')=='healthy':health['eligible_text_slots'].append(slot);record_fn('text',slot,TEXT_MODEL)
  atomic_json(data/'health/latest.json',health)
  if row.get('http_status') not in (200,401,403):stop_text=True;break
 if not stop_text:
  if image_probe is None:
   from .image_key_audit import probe as image_probe
  from .image_key_audit import terminal
  for slot,key in unique:
   if report['image_calls']>=image_budget:report['status']='bounded_image_check_complete';break
   if circuit_open('image'):report['status']='waiting_image_cooldown';break
   report['image_calls']+=1;atomic_json(rp,report)
   try:row,blob=image_probe(slot,key)
   except Exception as exc:
    from .failure_diagnostics import failure_details
    from .image_transport import AdmissionBlocked
    from automation.blog_image_queue import ImageQueueBusy
    if isinstance(exc,(AdmissionBlocked,ImageQueueBusy)):
     report['image_calls']-=1;report['image_not_sent_admission_blocked']=True
    report['status']='image_admission_or_transport_blocked';report['failure']=failure_details(exc);break
   row={k:v for k,v in row.items() if k in {'state','http_status','provider_code','retry_after_seconds','reference_conditioned','publication_visual_approval'}}
   byslot[slot]['image']=dict(row);case=dict(row,slot=slot,checked_at=utcnow());report['cases'].append(case)
   if row.get('state')=='healthy' and blob:
    path=dest/(slot+'.webp');path.write_bytes(blob);health['eligible_image_slots'].append(slot);record_fn('image',slot,IMAGE_MODEL,blob)
   atomic_json(data/'health/latest.json',health);atomic_json(rp,report)
   if terminal(row):
    report['status']='stopped_provider_limit_or_uncertain_response'
    if row.get('http_status') in (402,429,503) or row.get('provider_code')=='image_queue_full':
     from .client import ImageProviderError
     from .pilot_resume import defer_provider
     defer_provider(ImageProviderError(row.get('http_status'),row.get('provider_code'),row.get('state'),row.get('retry_after_seconds')))
    break
  else:report['status']='capabilities_checked'
 else:report['status']='stopped_text_provider_limit_or_uncertain_response'
 report.update(completed_at=utcnow(),eligible_text_slots=health['eligible_text_slots'],eligible_image_slots=health['eligible_image_slots'],production_enabled=False)
 health['checked_at']=report['started_at'];health['run_id']=env.get('GITHUB_RUN_ID');atomic_json(data/'health/latest.json',health);atomic_json(rp,report)
 update('بررسی اتصال کلیدها پایان یافت؛ متن: '+str(len(health['eligible_text_slots']))+'، تصویر: '+str(len(health['eligible_image_slots']))+' کلید تأییدشده؛ اتصال وردپرس هنوز لازم است',0,status='health_refresh_required')
 return report

def main():
 result=run(max_image_calls=int(os.environ.get('AFP_IMAGE_PROBE_BUDGET','1')));print(json.dumps({k:v for k,v in result.items() if k not in {'cases','duplicate_slots'}},ensure_ascii=False))
 # A successful audit is not synonymous with ready-for-production.
 return 0 if result.get('eligible_text_slots') and result.get('eligible_image_slots') else 2
if __name__=='__main__':raise SystemExit(main())
