"""Separately authorized schema-only rechecks: two calls, retained sources only.
Historical attempts, unknown requests and negatives are immutable. No promotion,
search, source fetching, article editing, publication or schedules.
"""
import hashlib,json,time
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours
from .pipeline import digest
from .infrastructure_probe import identity,code_hash,protected,preflight
ID='authorized-regional-schema-two-rechecks-v1'
LANGUAGES=('ar-IQ','en-US')
TOPIC='agri-6fc1032cdf42'
class RecheckBlocked(ValueError):pass

def selected(data=DATA,out=OUT):
 from .staged_rollout import load
 from . import language_review_queue as q
 from .regional_continuation import eligible,confirmed
 from .regional_sources import documents_for,profile
 state=load(out)
 if state['limit']!=1 or len(state['cohort'])!=1 or state['cohort'][0]['topic_id']!=TOPIC:raise RecheckBlocked('exact_single_cohort_required')
 folder=Path(out)/'new'/TOPIC;article=load_json(folder/'article.json');brief=load_json(data/'briefs'/(TOPIC+'.json'));docs={}
 for lang in LANGUAGES:
  row=load_json(q.path(folder,lang));q.source_checked(row,article,folder,data)
  if not eligible(row,folder) or q.published(folder,lang):raise RecheckBlocked('unchanged_fidelity_required')
  root=folder/'regional-research'/lang;old=load_json(root/'continuation.json');prior=root/'continuation-attempts/2'
  if old.get('attempts')!=2 or old.get('status')!='needs_attention' or old.get('last_failure',{}).get('category')!='claim_context_review_required' or not confirmed(prior):raise RecheckBlocked('confirmed_exhausted_protocol_failure_required')
  raw=load_json(prior/'regional-evidence-review-fallback.raw.json')
  if 'regional_review_schema_version' in raw:raise RecheckBlocked('original_protocol_failure_required')
  retained=[]
  from .queue import get_topic
  topic=get_topic('new',TOPIC,data)
  for mode in ('local','international'):
   saved=load_json(root/mode/'documents.json')
   contract={'international_fallback':mode=='international','policy':profile(lang),'topic':{k:topic[k] for k in ('id','title','crop','intent')}}
   if saved.get('contract_sha256')!=digest(contract) or saved.get('publication_authorized') is not False:raise RecheckBlocked('retained_document_binding_changed')
   retained+=saved['documents']
  retained=list({d['url']:d for d in retained}.values())
  if not 1<=len(retained)<=12 or documents_for(retained,lang,True)!=retained or any(d.get('sha256')!=hashlib.sha256(d['text'].encode()).hexdigest() for d in retained):raise RecheckBlocked('retained_documents_invalid')
  docs[lang]=retained
 return folder,article,brief,docs

def expected(data=DATA,out=OUT):
 folder,article,brief,docs=selected(data,out)
 return {'version':1,'request_id':ID,'authorization':'explicit_owner_approval_two_schema_only_regional_rechecks','authorization_source':'https://app.notion.com/chat?t=40841579fa0a8078988900a99eb829d4','topic_id':TOPIC,'languages':list(LANGUAGES),'code_sha256':code_hash(),'article_sha256':digest(article),'brief_sha256':digest(brief),'documents_sha256':{l:digest(docs[l]) for l in LANGUAGES},'protected_sha256':digest(manifest(data,out)),'max_runs':1,'max_model_calls':2,'max_model_calls_per_language':1,'max_search_requests':0,'max_source_fetches':0,'max_site_calls':0,'max_image_calls':0,'article_edits':0,'translation_edits':0,'reset_attempts':False,'publication_authorized':False,'schedule_enabled':False,'promotion_authorized':False}

def validate(req,data=DATA,out=OUT):
 wanted=expected(data,out)
 # The admission file cannot hash itself. All other data/history remains bound.
 if not isinstance(req,dict) or set(req)!=set(wanted) or any(type(req[k])is not type(v) or req[k]!=v for k,v in wanted.items()):raise RecheckBlocked('schema_recheck_binding_changed')
 return selected(data,out)

def manifest(data,out):
 return {k:v for k,v in protected(data,out,ID).items() if k!='data/regional-schema-recheck-request.json'}

def validate_wire(value,schema):
 # Verify the exact native contract locally too; no provider trust shortcut.
 types=schema.get('type');types=types if isinstance(types,list) else [types]
 valid={'object':type(value)is dict,'array':type(value)is list,'integer':type(value)is int,'string':type(value)is str,'boolean':type(value)is bool,'null':value is None}
 if not any(valid.get(t,False) for t in types) or ('enum' in schema and value not in schema['enum']):raise RecheckBlocked('regional_wire_shape_invalid')
 if type(value)is dict:
  props=schema['properties']
  if set(value)!=set(schema['required']):raise RecheckBlocked('regional_wire_shape_invalid')
  for k,v in value.items():validate_wire(v,props[k])
 elif type(value)is list:
  if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',10000):raise RecheckBlocked('regional_wire_shape_invalid')
  for v in value:validate_wire(v,schema['items'])
 elif type(value)is str and len(value)<schema.get('minLength',0):raise RecheckBlocked('regional_wire_shape_invalid')

class CountedClient:
 def __new__(cls,health,worker,root,base_class=None):
  from .parallel_client import ParallelModelClient
  from .healthcheck import TEXT_MODEL
  class Bounded(ParallelModelClient if base_class is None else base_class):
   def request(self,kind,path,payload,timeout,attempts=None):
    lang=self.recheck_language
    if lang not in LANGUAGES or kind!='text' or path!='/chat/completions' or payload.get('model')!=TEXT_MODEL:raise RecheckBlocked('schema_recheck_transport_forbidden')
    if type(payload.get('max_tokens'))is not int or not 256<=payload['max_tokens']<=14000 or len(json.dumps(payload,ensure_ascii=False))>200000 or type(timeout)is not int or not 30<=timeout<=180:raise RecheckBlocked('schema_recheck_transport_budget')
    if payload.get('response_format')!=self.expected_response_format:raise RecheckBlocked('strict_schema_required')
    receipt=root/'calls'/(lang+'.json')
    if receipt.exists() or len(list((root/'calls').glob('*.json')))>=2:raise RecheckBlocked('schema_recheck_consumed_no_replay')
    row={'language':lang,'status':'reserved','request_sha256':digest(payload),'max_attempts':1,'at':utcnow()};atomic_json(receipt,row)
    value=super().request(kind,path,payload,timeout,attempts=1);atomic_json(receipt,dict(row,status='response_received',response_sha256=digest(value)));return value
  return Bounded(health,env=worker,allow_calls=True,capabilities=('text',))

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None):
 return execute(env,data,out,client_factory,reserve_fn,ID,'regional-schema-recheck-request.json',validate,manifest,'regional-schema-recheck')

def execute(env,data,out,client_factory,reserve_fn,request_id,request_file,validate_fn,manifest_fn,phase,wire_contract='regional-keyed-facts-v1'):
 # Shared finite executor. Admissions remain separate and immutable; this helper
 # cannot create a new budget without an exact remotely reserved manual phase.
 identity(env)
 if wire_contract!=('regional-quote-catalog-v1' if phase=='regional-catalog-validation' else 'regional-keyed-facts-v1'):raise RecheckBlocked('regional_validation_wire_phase_mismatch')
 root=Path(out)/'infrastructure-probes'/request_id;rp=root/'report.json'
 if rp.exists():return {'status':'regional_schema_recheck_already_reserved','model_calls':0,'published_posts':0}
 folder,article,brief,docs=validate_fn(load_json(data/request_file),data,out)
 from .post_hold_validation import circuit,ID as health_id
 from .family_capability_refresh import active_hold
 circuit(out)
 if active_hold(out,'text'):return {'status':'regional_schema_recheck_provider_waiting','model_calls':0,'published_posts':0}
 proof=load_json(out/'infrastructure-probes'/health_id/'health-passed.json');health=load_json(out/'parallel/health/latest.json')
 if proof.get('status')!='passed' or not 0<=age_hours(proof['at'])<24 or not 0<=age_hours(health['checked_at'])<24:raise RecheckBlocked('fresh_independent_health_required')
 if client_factory is None:preflight(env,health)
 if reserve_fn is None:
  from .parallel_control import reserve
  admitted=reserve(phase,request_id,env)
 else:admitted=reserve_fn(env)
 if not admitted:return {'status':'regional_schema_recheck_already_reserved','model_calls':0,'published_posts':0}
 before=manifest_fn(data,out);report={'request_id':request_id,'run_id':env['GITHUB_RUN_ID'],'status':'regional_schema_recheck_reserved','started_at':utcnow(),'results':[],'max_model_calls':2,'search_requests':0,'source_fetches':0,'site_calls':0,'image_calls':0,'published_posts':0,'article_edits':0,'translation_edits':0,'attempts_reset':False,'publication_authorized':False,'schedule_enabled':False,'promotion_authorized':False};atomic_json(rp,report)
 from .parallel_pool import SLOTS,initialize,snapshot,routing_counts,routing_backpressure,record_routing
 db=root/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=2,per_worker=1,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker={k:v for k,v in env.items() if k in SLOTS or k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID')};worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_FAMILY='isolated-infrastructure-probe')
 from .regional_sources import review_prompt,response_schema,validate_local_review,VERSION,profile,RegionalBlocked
 from .translation_review_repair import request
 from .claim_policy import validate_regional_objections
 try:
  for lang in LANGUAGES:
   result={'language':lang,'status':'blocked'};work=root/'languages'/lang
   try:
    prompt=review_prompt(article,brief,lang,docs[lang],wire=wire_contract);prompt['fallback_rule']='Review only the retained fetched sources; no new searches or article edits. International fallback requires an explicit local gap and preserved geographic transfer limits. A valid negative is acceptable.'
    schema=response_schema('regional-evidence-review-fallback',prompt)
    worker['AFP_PARALLEL_TOPIC']=TOPIC+'-'+lang
    client=(client_factory or CountedClient)(health,dict(worker),root);client.recheck_language=lang
    client.expected_response_format={'type':'json_schema','json_schema':{'name':'grounded_persian_article','strict':True,'schema':schema}}
    verdict=request(client,work,'regional-evidence-review-fallback',prompt,1)
    # Native schema does not replace server source/quote/semantic validation.
    # request() validates keyed raw before its lossless canonical projection.
    canonical_schema=response_schema('regional-evidence-review-fallback',{k:v for k,v in prompt.items() if k!='_regional_wire_contract'})
    validate_wire(verdict,canonical_schema)
    if {c['fact_id'] for c in verdict['fact_checks']}!={f['fact_id'] for f in brief['approved_facts']}:raise RecheckBlocked('regional_wire_fact_coverage_invalid')
    validate_regional_objections(verdict,article,brief['approved_facts'])
    negative=any(verdict[k] is False for k in ('applicable','no_unsupported_local_prescription','country_limits_retained')) or any(c['supported'] is False for c in verdict['fact_checks'])
    if negative:result['status']='validated_negative'
    else:
     urls=validate_local_review(verdict,article,brief,docs[lang],lang)
     atomic_json(work/'approved.json',{'version':VERSION,'profile':profile(lang),'article_sha256':digest(article),'brief_sha256':digest(brief),'documents':docs[lang],'review':verdict,'source_urls':urls,'reviewed_at':utcnow(),'publication_authorized':False})
     result['status']='regional_evidence_verified_not_promoted'
   except Exception as exc:
    from .failure_diagnostics import failure_details
    result['failure']={'kind':'schema_recheck_guard','category':str(exc)} if type(exc)is RecheckBlocked else failure_details(exc)
   report['results'].append(result);atomic_json(rp,report)
   if snapshot(db)['cooldown_until_epoch']>time.time():break
  report['status']='regional_schema_recheck_passed' if len(report['results'])==2 and all(r['status']=='regional_evidence_verified_not_promoted' for r in report['results']) else 'regional_schema_recheck_blocked'
 finally:
  state=snapshot(db);record_routing(out,state)
  if state['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':state['cooldown_until_epoch'],'reason':'regional_schema_recheck_service_failure'})
  unchanged=manifest_fn(data,out)==before
  if not unchanged:report['status']='regional_schema_recheck_originals_changed'
  report.update(model_calls=state['model_requests_reserved'],request_receipts=len(list((root/'calls').glob('*.json'))),originals_unchanged=unchanged,completed_at=utcnow());atomic_json(rp,report)
 return report
