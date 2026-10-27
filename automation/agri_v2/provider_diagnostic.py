"""One admitted 97-slot text audit plus at most two tiny, same-key schema probes."""
import json,time
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .parallel_pool import SLOTS
from .healthcheck import API_BASE,TEXT_MODEL
ID='ops-97-text-schema-diagnostic-v2'

def active_cooldown(out=OUT):
 until=0
 p=out/'provider-circuit.json'
 if p.exists():
  row=load_json(p)
  if row.get('open') is True and row.get('request_kind') not in ('image',):until=max(until,row.get('retry_at_epoch',0))
 p=out/'parallel/lifecycle/latest.json'
 if p.exists():until=max(until,load_json(p).get('pool',{}).get('cooldown_until_epoch',0))
 return until if until>time.time() else 0

def slot_summary(audit):
 checked={r['slot']:r for r in audit.get('cases',[])};missing=set(audit.get('missing_slots',[]));aliases=audit.get('duplicate_slots',{});rows=[]
 for slot in SLOTS:
  if slot in checked:row={k:v for k,v in checked[slot].items() if k in ('slot','state','http_status','elapsed_seconds','checked_at')}
  elif slot in missing:row={'slot':slot,'state':'not_configured'}
  elif slot in aliases:row={'slot':slot,'state':'duplicate_not_independent','duplicate_of_slot':aliases[slot]}
  else:row={'slot':slot,'state':'not_tested'}
  rows.append(row)
 counts={}
 for row in rows:counts[row['state']]=counts.get(row['state'],0)+1
 return rows,counts

def schema():
 return {'type':'object','additionalProperties':False,'required':['sections','excerpt'],'properties':{'sections':{'type':'array','minItems':1,'maxItems':1,'items':{'type':'object','additionalProperties':False,'required':['text','fact_ids'],'properties':{'text':{'type':'string','pattern':r'^\S+\s+\S+$'},'fact_ids':{'type':'array','minItems':1,'items':{'type':'string','enum':['f0']}}}}},'excerpt':{'type':'string','minLength':2,'maxLength':20}}}

def valid_response(obj,strict):
 try:
  if obj.get('model',TEXT_MODEL)!=TEXT_MODEL or obj['choices'][0].get('finish_reason') in ('length','content_filter'):return False
  content=obj['choices'][0]['message']['content']
  if isinstance(content,list):content=''.join(v.get('text','') for v in content if isinstance(v,dict))
  row=json.loads(content)
  if not strict:return isinstance(row,dict) and set(row)=={'ok'} and row['ok'] is True
  import re
  return isinstance(row,dict) and set(row)=={'sections','excerpt'} and isinstance(row['excerpt'],str) and 2<=len(row['excerpt'])<=20 and isinstance(row['sections'],list) and len(row['sections'])==1 and isinstance(row['sections'][0],dict) and set(row['sections'][0])=={'text','fact_ids'} and isinstance(row['sections'][0]['text'],str) and re.fullmatch(r'\S+\s+\S+',row['sections'][0]['text']) is not None and row['sections'][0]['fact_ids']==['f0']
 except (AttributeError,ValueError,KeyError,TypeError,IndexError):return False

def run(env,data=DATA,out=OUT,post_fn=None,reserve_fn=None,audit_fn=None):
 from .operation_request import authorize
 if not authorize(env,data):raise ValueError('current_diagnostic_owner_admission_required')
 admission=load_json(data/'status/owner-operation-admission.json')
 if admission['request_id']!=ID:raise ValueError('exact_diagnostic_request_required')
 from .parallel_control import reserve,policy
 policy(env,data)
 rp=out/'parallel/operations'/ID/'prepare.json'
 if rp.exists():return {'status':'diagnostic_already_reserved','model_calls':0,'published_posts':0}
 if (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'diagnostic_already_reserved','model_calls':0,'published_posts':0}
 report={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'status':'diagnostic_started','model_calls':0,'max_total_text_calls':99,'max_schema_probe_calls':2,'schema_probes':[],'image_calls':0,'wordpress_calls':0,'published_posts':0,'schedule_activated':False,'attempts_reset':False,'article_attempts_modified':False,'secrets_stored':False};atomic_json(rp,report)
 until=active_cooldown(out)
 if until:report.update(status='diagnostic_shared_cooldown',cooldown_until_epoch=until,completed_at=utcnow());atomic_json(rp,report);return report
 from .parallel_audit import run as audit,post_once
 post_fn=post_once if post_fn is None else post_fn
 def timed_post(*args,**kwargs):
  started=time.monotonic()
  try:safe,obj=post_fn(*args,**kwargs)
  except Exception:safe,obj={'state':'network_or_timeout','http_status':None},None
  return dict(safe,elapsed_seconds=round(time.monotonic()-started,3)),obj
 audit_result=(audit if audit_fn is None else audit_fn)(env,data,out,post_fn=timed_post,reserve_fn=lambda *_:{'operation_already_durably_reserved':True},audit_id=ID)
 report['audit']=audit_result;report['model_calls']=audit_result.get('model_calls',0);report['slots'],report['slot_state_counts']=slot_summary(audit_result);atomic_json(rp,report)
 if audit_result.get('status') not in ('completed','completed_with_configuration_gaps') or not audit_result.get('eligible_text_slots'):
  report.update(status='diagnostic_audit_not_complete',completed_at=utcnow());atomic_json(rp,report);return report
 slot=audit_result['eligible_text_slots'][0];key=env.get(slot,'').strip()
 if not key:raise ValueError('same_configured_probe_slot_required')
 # One selected key, no retry, no credential rotation, no article or image calls.
 for strict in (False,True):
  if active_cooldown(out):report['status']='diagnostic_stopped_shared_cooldown';break
  mode='strict_json_schema' if strict else 'baseline_json_object'
  payload={'model':TEXT_MODEL,'messages':[{'role':'user','content':'Return exactly {"sections":[{"text":"ok yes","fact_ids":["f0"]}],"excerpt":"OK"} as JSON only.' if strict else 'Return exactly {"ok":true} as JSON only.'}],'temperature':0,'max_tokens':256,'response_format':{'type':'json_schema','json_schema':{'name':'tiny_grounded_structure','strict':True,'schema':schema()}} if strict else {'type':'json_object'}}
  row={'mode':mode,'slot':slot,'state':'reserved','started_at':utcnow()};report['schema_probes'].append(row);report['model_calls']+=1;atomic_json(rp,report)
  safe,obj=timed_post('/chat/completions',key,payload,timeout=70)
  ok=safe.get('http_status')==200 and valid_response(obj,strict)
  row.update(state='verified' if ok else ('response_contract_failed' if safe.get('http_status')==200 else safe.get('state','unknown_failure')),http_status=safe.get('http_status'),elapsed_seconds=safe['elapsed_seconds'],completed_at=utcnow(),response_contract_valid=ok);atomic_json(rp,report)
  status=safe.get('http_status')
  if not ok:
   if status in (402,429) or status is None or isinstance(status,int) and status>=500:
    until=time.time()+max(3600,safe.get('retry_after_seconds') or 0);atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':until,'reason':'tiny_schema_diagnostic_shared_failure','no_secrets':True});report['cooldown_until_epoch']=until
   report['status']='diagnostic_baseline_failed' if not strict else 'diagnostic_strict_failed';break
 else:report['status']='diagnostic_completed'
 report['tiny_schema_capability_only']=True;report['full_article_or_image_capability_proved']=False;report['completed_at']=utcnow();atomic_json(rp,report);return report
