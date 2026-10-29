"""One post-cooldown health check, then ONLY never-attempted languages.
The failed Russian draft and unknown Arabic review are immutable and excluded.
"""
import hashlib,json,time
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours
from .pipeline import digest
from .infrastructure_probe import identity,code_hash,protected,preflight
from . import language_infrastructure_probe as prior
ID='post-hold-unattempted-language-validation-v1'
LANGUAGES=('tg-TJ','en-US')
LIMIT=9
HEALTH_PROMPT='Independent connectivity check only. Return exactly {"status":"ok"}. Do not write or review any article or translation.'
SCHEMA={'type':'object','properties':{'status':{'type':'string','enum':['ok']}},'required':['status'],'additionalProperties':False}
class ValidationBlocked(ValueError):pass

def old_binding(out=OUT):
 root=Path(out)/'infrastructure-probes'/prior.ID
 return digest({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()})

def expected(data=DATA,out=OUT):
 article,source=prior.inputs(data,out);root=Path(out)/'infrastructure-probes'/prior.ID;old=load_json(root/'report.json')
 if old.get('status')!='language_probe_blocked' or old.get('model_calls')!=4 or [r['language'] for r in old['languages']]!=['ru-RU','ar-IQ']:raise ValidationBlocked('prior_probe_not_exact_blocked_checkpoint')
 if len(list((root/'calls').glob('*/*.json')))!=4 or any((root/'calls'/lang).exists() or (root/'languages'/lang).exists() for lang in LANGUAGES):raise ValidationBlocked('language_already_attempted_no_replay')
 if not (root/'languages/ar-IQ/review-1.receipt.json').exists() or (root/'languages/ar-IQ/review-1.raw.json').exists():raise ValidationBlocked('unknown_arabic_evidence_changed')
 return {'version':1,'request_id':ID,'code_sha256':code_hash(),'source_article_sha256':digest(article),'prior_probe_sha256':old_binding(out),'languages':list(LANGUAGES),'excluded_languages':['ru-RU','ar-IQ'],'max_runs':1,'max_wait_seconds':1800,'max_model_calls':LIMIT,'max_health_calls':1,'max_language_calls':8,'max_calls_per_language':4,'max_total_language_calls_including_prior':16,'max_site_calls':0,'max_search_calls':0,'max_image_calls':0,'publication_authorized':False,'schedule_enabled':False,'reset_attempts':False}

def validate(req,data=DATA,out=OUT):
 wanted=expected(data,out)
 if not isinstance(req,dict) or set(req)!=set(wanted) or any(type(req[k])is not type(v) or req[k]!=v for k,v in wanted.items()):raise ValidationBlocked('post_hold_request_binding_changed')
 return prior.inputs(data,out)[0]

class CountedClient:
 def __new__(cls,health,worker,root,base_class=None):
  from .parallel_client import ParallelModelClient
  from .healthcheck import TEXT_MODEL
  class Bounded(ParallelModelClient if base_class is None else base_class):
   def request(self,kind,path,payload,timeout,attempts=None):
    phase=self.probe_language
    if phase not in ('health',)+LANGUAGES or kind!='text' or path!='/chat/completions' or payload.get('model')!=TEXT_MODEL:raise ValidationBlocked('post_hold_transport_not_allowed')
    if type(payload.get('max_tokens'))is not int or not 256<=payload['max_tokens']<=14000 or len(json.dumps(payload,ensure_ascii=False))>200000 or type(timeout)is not int or not 30<=timeout<=180:raise ValidationBlocked('post_hold_transport_budget')
    if phase=='health' and (payload['max_tokens']!=256 or timeout!=45 or payload.get('messages',[])[-1:]!=[{'role':'user','content':HEALTH_PROMPT}] or payload.get('response_format',{}).get('json_schema',{}).get('schema')!=SCHEMA):raise ValidationBlocked('health_probe_contract_changed')
    calls=list((root/'calls').glob('*/*.json'));owned=list((root/'calls'/phase).glob('*.json'));sha=digest(payload)
    if phase!='health' and not (root/'health-passed.json').exists():raise ValidationBlocked('health_not_confirmed')
    if len(calls)>=LIMIT or len(owned)>=(1 if phase=='health' else 4) or any(load_json(p).get('request_sha256')==sha for p in calls):raise ValidationBlocked('post_hold_consumed_no_replay')
    row={'phase':phase,'status':'reserved','request_sha256':sha,'max_attempts':1,'at':utcnow()};receipt=root/'calls'/phase/(str(len(owned))+'.json');atomic_json(receipt,row)
    value=super().request(kind,path,payload,timeout,attempts=1);atomic_json(receipt,dict(row,status='response_received',response_sha256=digest(value)));return value
  return Bounded(health,env=worker,allow_calls=True,capabilities=('text',))

def wait_for_release(out=OUT,sleep_fn=time.sleep):
 # A finite wait in this one manually dispatched run, never a recurring schedule.
 row=load_json(Path(out)/'provider-circuit.json');until=row.get('retry_at_epoch')
 if type(until) not in (int,float) or not __import__('math').isfinite(until):raise ValidationBlocked('hold_deadline_invalid')
 delay=max(0,until-time.time())
 if delay>1800:raise ValidationBlocked('hold_wait_exceeds_bound')
 if delay:sleep_fn(delay)

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None,wait_fn=None):
 identity(env);root=Path(out)/'infrastructure-probes'/ID;rp=root/'report.json'
 if rp.exists():return {'status':'post_hold_already_reserved_no_replay','model_calls':0,'site_calls':0}
 article=validate(load_json(data/'post-hold-validation-request.json'),data,out)
 from .family_capability_refresh import active_hold
 if active_hold(out,'text'):
  if wait_fn is not None:wait_fn(out)
  if active_hold(out,'text'):return {'status':'post_hold_provider_waiting','model_calls':0,'site_calls':0}
 health=load_json(out/'parallel/health/latest.json')
 if not 0<=age_hours(health['checked_at'])<24:raise ValidationBlocked('post_hold_health_expired')
 if client_factory is None:preflight(env,health)
 if reserve_fn is None:
  from .parallel_control import reserve
  admitted=reserve('post-hold-validation',ID,env)
 else:admitted=reserve_fn(env)
 if not admitted:return {'status':'post_hold_already_reserved_no_replay','model_calls':0,'site_calls':0}
 before=protected(data,out,ID);report={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'post_hold_reserved','started_at':utcnow(),'prior_language_calls':4,'max_model_calls':LIMIT,'languages':[],'excluded_languages':['ru-RU','ar-IQ'],'unknown_arabic_replayed':False,'site_calls':0,'post_mutations':0,'search_calls':0,'image_calls':0,'publication_authorized':False,'schedule_enabled':False,'attempts_reset':False,'production_readiness_claimed':False};atomic_json(rp,report)
 from .parallel_pool import SLOTS,initialize,snapshot,routing_counts,routing_backpressure,record_routing
 db=root/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=LIMIT,per_worker=LIMIT,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker={k:v for k,v in env.items() if k in SLOTS or k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID')};worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC='post-hold-unattempted-languages',AFP_PARALLEL_FAMILY='isolated-infrastructure-probe')
 try:
  client=(client_factory or CountedClient)(health,worker,root);client.probe_language='health'
  result=client.text(HEALTH_PROMPT,attempts=1,response_schema=SCHEMA,max_tokens=256,timeout=45)
  if type(result)is not dict or result!={'status':'ok'}:raise ValidationBlocked('health_probe_response_invalid')
  atomic_json(root/'health-passed.json',{'status':'passed','at':utcnow(),'response_sha256':digest(result),'not_translation_approval':True});report['health_status']='passed';atomic_json(rp,report)
  from .client import TextProviderError
  for lang in LANGUAGES:
   client.probe_language=lang
   try:report['languages'].append(prior.language(client,article,lang,root))
   except Exception as exc:
    report['languages'].append({'language':lang,'status':'blocked','failure':prior.diagnostic(exc)})
    if isinstance(exc,TextProviderError):break
   atomic_json(rp,report)
  report['status']='post_hold_unattempted_languages_passed' if len(report['languages'])==2 and all(r['status']=='fidelity_passed' for r in report['languages']) else 'post_hold_validation_blocked'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  report.update(status='post_hold_validation_blocked',failure={'kind':'post_hold_guard','category':str(exc)} if type(exc)is ValidationBlocked else failure_details(exc))
 finally:
  state=snapshot(db);record_routing(out,state)
  if state['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':state['cooldown_until_epoch'],'reason':'post_hold_validation_service_failure'})
  unchanged=protected(data,out,ID)==before
  if not unchanged:report['status']='post_hold_originals_changed'
  report.update(model_calls=state['model_requests_reserved'],originals_unchanged=unchanged,completed_at=utcnow());atomic_json(rp,report)
 return report
