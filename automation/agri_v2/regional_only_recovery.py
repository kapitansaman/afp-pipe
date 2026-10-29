"""Finite regional research only for the accepted one-family cohort's
already linguistically approved Arabic/English outputs. Never publishes.
"""
import json,time
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours
from .pipeline import digest
from .infrastructure_probe import identity,code_hash,protected,preflight
ID='single-family-regional-only-continuation-v1'
LANGUAGES=('ar-IQ','en-US')
class RecoveryBlocked(ValueError):pass

def selected(data=DATA,out=OUT):
 from .staged_rollout import load
 from . import language_review_queue as q
 from .regional_continuation import eligible,due
 state=load(out)
 if state['limit']!=1 or len(state['cohort'])!=1:raise RecoveryBlocked('single_accepted_cohort_required')
 ident=state['cohort'][0]['topic_id'];folder=Path(out)/'new'/ident;rows={}
 for lang in LANGUAGES:
  row=load_json(q.path(folder,lang))
  if not eligible(row,folder) or not due(folder,lang) or q.published(folder,lang):raise RecoveryBlocked('unchanged_approved_regional_continuation_required')
  q.source_checked(row,load_json(folder/'article.json'),folder,data);rows[lang]=row
 return ident,folder,rows

def expected(data=DATA,out=OUT):
 from . import language_review_queue as q
 ident,folder,rows=selected(data,out)
 from .post_hold_validation import ID as health_id
 health=load_json(Path(out)/'infrastructure-probes'/health_id/'health-passed.json')
 if health.get('status')!='passed' or not 0<=age_hours(health['at'])<24:raise RecoveryBlocked('fresh_independent_health_required')
 return {'version':1,'request_id':ID,'code_sha256':code_hash(),'topic_id':ident,'languages':list(LANGUAGES),'article_sha256':digest(load_json(folder/'article.json')),'brief_sha256':digest(load_json(data/'briefs'/(ident+'.json'))),'queue_sha256':{lang:digest(rows[lang]) for lang in LANGUAGES},'fidelity_sha256':{lang:digest(load_json(q.proof_path(folder,lang))) for lang in LANGUAGES},'health_sha256':digest(health),'max_runs':1,'max_model_calls':8,'max_model_calls_per_item':4,'max_search_requests':8,'max_source_urls':24,'max_wordpress_calls':0,'max_image_calls':0,'publication_authorized':False,'schedule_enabled':False,'reset_attempts':False}

def validate(req,data=DATA,out=OUT):
 wanted=expected(data,out)
 if not isinstance(req,dict) or set(req)!=set(wanted) or any(type(req[k])is not type(v) or req[k]!=v for k,v in wanted.items()):raise RecoveryBlocked('regional_recovery_binding_changed')
 return selected(data,out)

def immutable(data,out,ident):
 values=protected(data,out,ID)
 prefixes=['out/source-cache/']
 prefixes += ['out/new/'+ident+'/regional-research/'+lang+'/' for lang in LANGUAGES]
 paths={'out/parallel/source-search/state.json'}|{'out/new/'+ident+'/review-queue/'+lang+'.json' for lang in LANGUAGES}
 return {k:v for k,v in values.items() if k not in paths and not any(k.startswith(prefix) for prefix in prefixes)}

class CountedClient:
 def __new__(cls,health,worker,root,base_class=None):
  from .parallel_client import ParallelModelClient
  from .healthcheck import TEXT_MODEL
  class Bounded(ParallelModelClient if base_class is None else base_class):
   def request(self,kind,path,payload,timeout,attempts=None):
    lang=self.recovery_language
    if lang not in LANGUAGES or kind!='text' or path!='/chat/completions' or payload.get('model')!=TEXT_MODEL:raise RecoveryBlocked('regional_recovery_transport_forbidden')
    if type(payload.get('max_tokens'))is not int or not 256<=payload['max_tokens']<=14000 or len(json.dumps(payload,ensure_ascii=False))>200000 or type(timeout)is not int or not 30<=timeout<=180:raise RecoveryBlocked('regional_recovery_transport_budget')
    rows=list((root/'calls').glob('*/*.json'));owned=list((root/'calls'/lang).glob('*.json'));sha=digest(payload)
    if len(rows)>=8 or len(owned)>=4 or any(load_json(p).get('request_sha256')==sha for p in owned):raise RecoveryBlocked('regional_recovery_consumed_no_replay')
    row={'language':lang,'status':'reserved','request_sha256':sha,'max_attempts':1,'at':utcnow()};receipt=root/'calls'/lang/(str(len(owned))+'.json');atomic_json(receipt,row)
    value=super().request(kind,path,payload,timeout,attempts=1);atomic_json(receipt,dict(row,status='response_received',response_sha256=digest(value)));return value
  return Bounded(health,env=worker,allow_calls=True,capabilities=('text',))

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None):
 identity(env);root=Path(out)/'infrastructure-probes'/ID;rp=root/'report.json'
 if rp.exists():return {'status':'regional_recovery_already_reserved','model_calls':0,'published_posts':0}
 ident,folder,rows=validate(load_json(data/'regional-only-recovery-request.json'),data,out)
 from .post_hold_validation import circuit
 from .family_capability_refresh import active_hold
 circuit(out)
 if active_hold(out,'text'):return {'status':'regional_recovery_provider_waiting','model_calls':0,'published_posts':0}
 health=load_json(out/'parallel/health/latest.json')
 if not 0<=age_hours(health['checked_at'])<24:raise RecoveryBlocked('regional_recovery_health_expired')
 from .source_search import require,initialize as initialize_search,persist as persist_search
 if not env.get('AFP_SOURCE_SEARCH_API_KEY','').strip():raise RecoveryBlocked('regional_search_connection_required')
 if client_factory is None:preflight(env,health)
 if reserve_fn is None:
  from .parallel_control import reserve
  admitted=reserve('regional-only-recovery',ID,env)
 else:admitted=reserve_fn(env)
 if not admitted:return {'status':'regional_recovery_already_reserved','model_calls':0,'published_posts':0}
 before=immutable(data,out,ident);report={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'topic_id':ident,'status':'regional_recovery_reserved','started_at':utcnow(),'results':[],'max_model_calls':8,'max_search_requests':8,'wordpress_calls':0,'published_posts':0,'image_calls':0,'publication_authorized':False,'schedule_enabled':False,'attempts_reset':False,'article_edits':0,'translation_edits':0};atomic_json(rp,report)
 from .parallel_pool import SLOTS,initialize,snapshot,routing_counts,routing_backpressure,record_routing
 db=root/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=8,per_worker=4,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out));initialize_search(db,out,max_requests=8)
 worker={k:v for k,v in env.items() if k in SLOTS or k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID','AFP_SOURCE_SEARCH_API_KEY')};worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_FAMILY='isolated-infrastructure-probe')
 from .regional_continuation import run as continue_regional
 try:
  for lang in LANGUAGES:
   worker['AFP_PARALLEL_TOPIC']=ident+'-'+lang
   client=(client_factory or CountedClient)(health,dict(worker),root);client.recovery_language=lang
   report['results'].append(continue_regional(folder/'review-queue'/(lang+'.json'),client,data));atomic_json(rp,report)
   if snapshot(db)['cooldown_until_epoch']>time.time():break
  report['status']='regional_recovery_passed' if len(report['results'])==2 and all(row['status']=='approved' for row in report['results']) else 'regional_recovery_blocked'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  report.update(status='regional_recovery_blocked',failure={'kind':'regional_recovery_guard','category':str(exc)} if type(exc)is RecoveryBlocked else failure_details(exc))
 finally:
  state=snapshot(db);record_routing(out,state);report['source_search']=persist_search(db,out)
  if state['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':state['cooldown_until_epoch'],'reason':'regional_only_recovery_service_failure'})
  counters_ok=all(load_json(folder/'review-queue'/(lang+'.json'))['attempts']==rows[lang]['attempts'] and rows[lang]['model_calls_spent']<=load_json(folder/'review-queue'/(lang+'.json'))['model_calls_spent']<=12 for lang in LANGUAGES)
  report['semantic_attempts_unchanged']=counters_ok
  unchanged=immutable(data,out,ident)==before and counters_ok
  if not unchanged:report['status']='regional_recovery_originals_changed'
  report.update(model_calls=state['model_requests_reserved'],originals_unchanged=unchanged,completed_at=utcnow());atomic_json(rp,report)
 return report
