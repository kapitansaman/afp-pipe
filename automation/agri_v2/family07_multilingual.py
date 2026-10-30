"""Owner-approved bounded missing-language completion and conditional internal adoption.
No site, image, search, global-health promotion or attempt reset. One-shot only.
"""
import json,shutil,time
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours,get_topic
from .pipeline import digest
from .infrastructure_probe import identity,code_hash,protected
from . import language_review_queue as q
from . import regional_sources as regional
from .retained_regional_positive import revalidate
from . import single_family_capability as capability
ID='authorized-family07-multilingual-ten-call-v1'
REQUEST='family07-multilingual-request.json'
PHASE='family07-multilingual'
TOPIC='agri-6fc1032cdf42';FAMILY='family-07';LANGS=('ru-RU','tg-TJ');RETAINED=('ar-IQ','en-US')
class Blocked(ValueError):pass

def mutable(rel):
 prefix='out/new/'+TOPIC+'/'
 if not rel.startswith(prefix):return False
 p=rel[len(prefix):]
 if p in ['regional-research/'+l+'/approved.json' for l in LANGS+RETAINED]:return True
 if p in ['review-queue/'+l+'.json' for l in LANGS+RETAINED]:return True
 if p in ['review-queue/candidate-'+l+'.json' for l in LANGS]:return True
 if any(p.startswith('review-queue/attempts/'+l+'/3/') for l in LANGS):return True
 return p in ['translations/'+l+suffix for l in LANGS for suffix in ('.json','.raw.json','.fidelity.json')]

def manifest(data,out):return {k:v for k,v in protected(data,out,ID).items() if k!='data/'+REQUEST and not mutable(k)}

def inputs(data=DATA,out=OUT):
 from .staged_rollout import load
 from .family_model_routing import load as roles
 from .regional_source_seeds import ordered
 state=load(out)
 if state['limit']!=1 or len(state['cohort'])!=1 or state['cohort'][0]['topic_id']!=TOPIC or state['cohort'][0]['family_id']!=FAMILY:raise Blocked('exact_family07_cohort_required')
 if roles(data)['families'][FAMILY]!={'text_slots':list(capability.TEXT),'image_slot':capability.IMAGE}:raise Blocked('exact_owned_text_roles_required')
 folder=out/'new'/TOPIC;article=load_json(folder/'article.json');brief=load_json(data/'briefs'/(TOPIC+'.json'));rows={l:load_json(q.path(folder,l)) for l in LANGS+RETAINED}
 for l,row in rows.items():
  q.source_checked(row,article,folder,data)
  if row['article_sha256']!=digest(article) or q.published(folder,l) or (folder/'regional-research'/l/'approved.json').exists():raise Blocked('unchanged_unpublished_unapproved_inputs_required')
 for l in LANGS:
  row=rows[l]
  if row['status']!='waiting' or row['attempts']!=2 or row['model_calls_spent']!=2 or row.get('last_failure',{}).get('category')!='regional_applicability_not_approved':raise Blocked('exact_two_spent_missing_language_attempts_required')
  if any((folder/'translations'/(l+s)).exists() for s in ('.json','.raw.json','.fidelity.json')) or (folder/'review-queue'/('candidate-'+l+'.json')).exists() or (folder/'review-queue/attempts'/l/'3').exists():raise Blocked('missing_target_only_no_replay')
  local=folder/'regional-research'/l/'local';topic=get_topic('new',TOPIC,data)
  contract={'international_fallback':False,'policy':regional.profile(l),'topic':{k:topic[k] for k in ('id','title','crop','intent')}}
  docs=load_json(local/'documents.json');plan=load_json(local/'search-plan.json')
  if docs.get('contract_sha256')!=digest(contract) or docs.get('documents')!=[] or plan.get('contract_sha256')!=digest(contract) or plan.get('publication_authorized') is not False:raise Blocked('bound_completed_empty_local_pack_required')
  queries=plan.get('queries')
  if not isinstance(queries,list) or len(queries)!=2 or len(set(queries))!=2:raise Blocked('bound_local_queries_required')
  from .source_search import validate_results
  for i,query in enumerate(queries):
   report=load_json(local/('search-'+str(i)+'.json'))
   if report.get('query_sha256')!=digest(query) or report.get('publication_authorized') is not False:raise Blocked('local_search_receipt_changed')
   validate_results(report['result']['results'])
  from .regional_continuation import confirmed
  if not confirmed(folder/'review-queue/attempts'/l/'2'):raise Blocked('unknown_old_request_never_replayed')
 for l in RETAINED:
  if rows[l]['status']!='needs_attention' or rows[l]['attempts']!=3 or rows[l]['model_calls_spent']!=5 or not q.approved(folder,article,l):raise Blocked('retained_fidelity_and_exhausted_counters_required')
 urls=ordered(brief,[])
 if len(urls)!=3:raise Blocked('exact_three_declared_sources_required')
 return folder,article,brief,rows,urls

def capability_proof(data=DATA,out=OUT):
 from .family_model_routing import load,binding
 from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
 root=out/'infrastructure-probes'/capability.ID;proof=load_json(root/'scoped-proof.json');report=load_json(root/'report.json')
 if report.get('status')!='single_family_capability_verified_not_promoted' or report.get('originals_unchanged') is not True or report.get('model_calls')!=3 or report.get('image_calls')!=1 or proof.get('family_id')!=FAMILY or proof.get('request_id')!=capability.ID or proof.get('text_slots')!=list(capability.TEXT) or proof.get('family_model_routing_sha256')!=binding(load(data)) or (proof.get('text_model'),proof.get('image_model'),proof.get('api_base'))!=(TEXT_MODEL,IMAGE_MODEL,API_BASE) or proof.get('credential_set_id')!=capability.CREDENTIAL_SET_ID or proof.get('production_readiness_claimed') is not False:raise Blocked('bound_scoped_capability_required')
 if not 0<=age_hours(proof['verified_at'])<24:raise Blocked('scoped_capability_expired_no_implicit_probe')
 if [(r.get('slot'),r.get('status')) for r in report['cases']]!=[(s,'verified') for s in capability.TEXT+(capability.IMAGE,)]:raise Blocked('actual_owned_slot_success_required')
 return proof

def expected(data=DATA,out=OUT):
 folder,a,b,rows,urls=inputs(data,out);p=capability_proof(data,out);retained=revalidate(data,out)
 return {'version':1,'request_id':ID,'authorization':'owner_approved_ten_text_three_fetch_and_conditional_internal_adoption',
  'authorization_source':'https://app.notion.com/chat?t=40841579fa0a8078988900a99eb829d4','family_id':FAMILY,'topic_id':TOPIC,
  'code_sha256':code_hash(),'protected_sha256':digest(manifest(data,out)),'article_sha256':digest(a),'brief_sha256':digest(b),
  'queue_sha256':{l:digest(r) for l,r in rows.items()},'retained_positives_sha256':digest(retained),'scoped_capability_sha256':digest(p),
  'source_urls':urls,'languages':list(LANGS),'reuse_languages':list(RETAINED),'role_slots':{'translator':capability.TEXT[0],'fidelity_reviewer':capability.TEXT[1],'regional_reviewer':capability.TEXT[2]},
  'max_runs':1,'max_text_calls':10,'max_regional_calls_per_language':1,'max_semantic_calls_per_language':4,'max_source_fetches':3,
  'max_search_requests':0,'max_site_calls':0,'max_image_calls':0,'max_attempts_per_request':1,'max_in_flight':1,
  'conditional_internal_evidence_adoption_authorized':True,'publication_authorized':False,'schedule_enabled':False,
  'stage_promotion_authorized':False,'reset_attempts':False,'global_capacity_refresh':False,'max_automatic_attempts':3,'max_model_calls_per_item':12}

def validate(req,data=DATA,out=OUT):
 v=expected(data,out)
 if type(req)is not dict or set(req)!=set(v) or any(type(req[k])is not type(x) or req[k]!=x for k,x in v.items()):raise Blocked('multilingual_admission_changed')
 return inputs(data,out)

def prompt(article,brief,docs,lang):
 from .regional_catalog_context import VERSION
 p=regional.review_prompt(article,brief,lang,docs,wire=VERSION)
 p['fallback_rule']='The retained completed local search pack is empty. Independently review these freshly fetched declared original sources for this specific language audience. Require explicit local evidence gaps and actual geographic transfer limits; never invent localization or force approval.'
 return p

class CountedClient:
 def __new__(cls,worker,root,data,out,base_class=None,request_id=ID,max_calls=10,manifest_fn=manifest):
  from .client import ModelClient,TextProviderError
  from .parallel_pool import lease
  from .healthcheck import TEXT_MODEL
  class Bounded(ModelClient if base_class is None else base_class):
   def __init__(self):self.env=worker;self.used={'text':0,'image':0};self.keys={'text':[],'image':[]};self.image_rotation_enabled=False;self.phase='regional';self.language=None;self.sequence=[];self.protected=manifest_fn(data,out)
   def record_success(self,*a,**kw):pass # No global/runtime health promotion.
   def text(self,*a,**kw):kw['reject_duplicate_keys']=True;return super().text(*a,**kw)
   def request(self,kind,path,payload,timeout,attempts=None):
    capability.guards(out);capability_proof(data,out)
    if manifest_fn(data,out)!=self.protected:raise Blocked('protected_inputs_changed_before_transport')
    if self.language not in LANGS or kind!='text' or path!='/chat/completions' or payload.get('model')!=TEXT_MODEL or attempts!=1:raise Blocked('exact_owned_text_transport_required')
    if type(timeout)is not int or not 30<=timeout<=180 or type(payload.get('max_tokens'))is not int or not 256<=payload['max_tokens']<=14000 or len(json.dumps(payload,ensure_ascii=False))>200000:raise Blocked('transport_size_or_timeout_budget')
    try:p=json.loads(payload['messages'][-1]['content'])
    except (TypeError,ValueError,KeyError,IndexError):raise Blocked('materialized_task_required') from None
    if self.phase=='regional':
     if payload.get('response_format')!=self.expected_response_format or digest(payload['messages'][-1]['content'])!=self.expected_prompt_sha256:raise Blocked('regional_materialized_contract_changed')
     stage='regional';slot=capability.TEXT[2]
    elif self.phase=='semantic':
     task=p.get('task','')
     stage='draft' if task.startswith('Translate all indexed Persian segments') else 'review' if task.startswith('Independent fidelity review') else 'edit' if task.startswith('Correct ONLY listed target IDs') else None
     if 'reviewer_feedback' in p or stage is None or self.sequence+[stage]!=['draft','review','edit','review'][:len(self.sequence)+1]:raise Blocked('only_draft_review_single_repair_recheck_allowed')
     slot=capability.TEXT[1] if stage=='review' else capability.TEXT[0]
     if stage=='draft' and payload.get('response_format',{}).get('type')!='json_schema':raise Blocked('strict_indexed_draft_schema_required')
    else:raise Blocked('unknown_transport_phase')
    receipts=list((root/'calls').glob('*/*.json'));owned=[p for p in receipts if p.parent.name==self.language]
    if len(receipts)>=max_calls or len(owned)>=5 or any(load_json(p).get('request_sha256')==digest(payload) for p in owned) or (stage=='regional' and any(load_json(p).get('stage')=='regional' for p in owned)):raise Blocked('consumed_transport_no_replay')
    if self.phase=='semantic' and sum(load_json(p).get('stage')!='regional' for p in owned)>=4:raise Blocked('semantic_budget_consumed')
    if stage=='edit' and max_calls-len(receipts)<2:raise Blocked('repair_and_recheck_must_both_fit_remaining_budget')
    receipt=root/'calls'/self.language/(str(len(owned))+'.json');row={'language':self.language,'stage':stage,'slot':slot,'status':'reserved','request_sha256':digest(payload),'at':utcnow(),'max_attempts':1}
    with lease(worker['AFP_PARALLEL_POOL_DB'],'text',[slot],request_id,wait=0):
     atomic_json(receipt,row);self.keys['text']=[(slot,worker[slot])]
     try:value=super().request(kind,path,payload,timeout,attempts=1)
     except Exception as exc:
      if isinstance(exc,TextProviderError):capability.keep_failure(worker['AFP_PARALLEL_POOL_DB'],out,slot,{'http_status':exc.http_status,'retry_after_seconds':exc.retry_after_seconds},'text')
      else:capability.keep_failure(worker['AFP_PARALLEL_POOL_DB'],out,slot,{'http_status':None},'text')
      raise
    atomic_json(receipt,dict(row,status='response_received',response_sha256=digest(value)))
    if self.phase=='semantic':self.sequence.append(stage)
    return value
  return Bounded()

def save_approval(folder,lang,article,brief,docs,review,provenance,data=DATA):
 path=folder/'regional-research'/lang/'approved.json'
 if path.exists():raise Blocked('existing_approval_never_overwritten')
 urls=regional.validate_local_review(review,article,brief,docs,lang)
 atomic_json(path,{'version':regional.VERSION,'profile':regional.profile(lang),'article_sha256':digest(article),'brief_sha256':digest(brief),
  'documents':docs,'review':review,'source_urls':urls,'reviewed_at':provenance['reviewed_at'],'publication_authorized':False,'adoption_provenance':provenance})
 regional.require_local(article,brief,lang,data,folder)

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None,fetcher=None):
 identity(env);root=out/'infrastructure-probes'/ID;rp=root/'report.json'
 if rp.exists():return {'status':'family07_multilingual_already_reserved_no_replay','model_calls':0,'source_fetches':0}
 folder,article,brief,rows,urls=validate(load_json(data/REQUEST),data,out)
 capability.guards(out);capability.check_unique_values(env)
 if any(not env.get(s,'').strip() for s in capability.TEXT):raise Blocked('owned_credentials_missing')
 retained=revalidate(data,out)
 from .parallel_pool import routing_backpressure
 prior=routing_backpressure(out);now=time.time()
 if prior.get('shared_cooldown_until_epoch',0)>now:raise Blocked('durable_shared_cooldown')
 for slot in capability.TEXT:
  hold=prior.get('slots',{}).get(slot,{})
  if hold.get('disabled') or hold.get('cooldown_until_epoch',0)>now:raise Blocked('owned_slot_unavailable_no_borrowing')
 if reserve_fn is None:
  from .parallel_control import reserve
  admitted=reserve(PHASE,ID,env)
 else:admitted=reserve_fn(env)
 if not admitted:return {'status':'family07_multilingual_already_reserved_no_replay','model_calls':0,'source_fetches':0}
 before=manifest(data,out);r={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'family07_multilingual_reserved','started_at':utcnow(),
  'model_calls':0,'source_fetches':0,'max_text_calls':10,'max_source_fetches':3,'site_calls':0,'image_calls':0,'search_requests':0,'published_posts':0,
  'publication_authorized':False,'schedule_enabled':False,'stage_promotion_authorized':False,'attempts_reset':False,'global_capacity_refresh':False,
  'conditional_internal_evidence_adoption_authorized':True,'results':[]};atomic_json(rp,r)
 from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing
 from .source_loading import valid_document
 from .scoped_sources import fetch
 from .research import source_host
 from .translation_review_repair import request
 from .regional_schema_recheck import validate_wire
 from .role_skills import enrich
 db=root/'pool.sqlite';initialize(db,list(capability.TEXT),text_limit=1,image_limit=1,max_calls=10,per_worker=10,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker={k:env[k] for k in capability.TEXT};worker.update({k:env[k] for k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID') if k in env});worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=ID,AFP_PARALLEL_FAMILY=FAMILY)
 try:
  docs=[]
  for i,url in enumerate(urls):
   fp=root/'fetches'/(str(i)+'.json')
   if fp.exists():raise Blocked('source_fetch_consumed')
   atomic_json(fp,{'url':url,'status':'reserved','max_attempts':1});r['source_fetches']+=1;atomic_json(rp,r)
   d=(fetcher or fetch)(url)
   if not valid_document(d,url,source_host) or d.get('source_link_discovery_version',0)<1 or any(regional.documents_for([d],l,True)!=[d] for l in LANGS+RETAINED):raise Blocked('fresh_original_source_invalid')
   docs.append(d);atomic_json(root/'documents'/(str(i)+'.json'),d);atomic_json(fp,{'url':url,'status':'received_valid','document_sha256':digest(d)})
  # Fresh text cannot be silently substituted into historical model verdicts.
  if manifest(data,out)!=before:raise Blocked('protected_inputs_changed_before_adoption')
  fresh={d['url']:d['sha256'] for d in docs}
  for l,v in retained.items():
   if {d['url']:d['sha256'] for d in v['documents']}!=fresh:raise Blocked('source_text_changed_retained_review_not_rebound')
   save_approval(folder,l,article,brief,v['documents'],v['review'],{'request_id':ID,'source_request_id':v['source_request_id'],'source_report_sha256':v['source_report_sha256'],'reviewed_at':v['original_reviewed_at'],'freshness_renewed':False},data)
   if not q.approved(folder,article,l):raise Blocked('retained_translation_changed')
   row=load_json(q.path(folder,l));row['history'].append({'event':'explicit_validated_regional_evidence_adoption','request_id':ID,'source_request_id':v['source_request_id'],'at':utcnow(),'model_calls':0,'attempts_unchanged':row['attempts']});row.update(status='approved',next_attempt_at=None,reason='unchanged_fidelity_and_retained_regional_review_verified');atomic_json(q.path(folder,l),row);r['results'].append({'language':l,'status':'retained_evidence_adopted','model_calls':0})
  client=(client_factory or CountedClient)(worker,root,data,out)
  for lang in LANGS:
   r['active_language']=lang;atomic_json(rp,r)
   client.language=lang;client.phase='regional';client.sequence=[];regional_error=None;p=prompt(article,brief,docs,lang);schema=regional.response_schema('regional-evidence-review-fallback',p)
   value=dict(p);role=value.pop('_role_skill');language=value.pop('_role_language',None);text=json.dumps(json.loads(enrich(value,role,language)),ensure_ascii=False)
   client.expected_response_format={'type':'json_schema','json_schema':{'name':'grounded_persian_article','strict':True,'schema':schema}};client.expected_prompt_sha256=digest(text)
   try:
    verdict=request(client,root/'regional'/lang,'regional-evidence-review-fallback',p,1)
    validate_wire(verdict,regional.response_schema('regional-evidence-review-fallback',{k:v for k,v in p.items() if k!='_regional_wire_contract'}))
    regional.validate_local_review(verdict,article,brief,docs,lang)
    save_approval(folder,lang,article,brief,docs,verdict,{'request_id':ID,'reviewed_at':utcnow(),'freshness_renewed':False},data)
   except Exception as exc:
    regional_error=exc;raise
   finally:
    # Count the new regional reservation even if conversion/validation is negative.
    spent=len(list((root/'calls'/lang).glob('*.json')));row=load_json(q.path(folder,lang))
    if spent:
     row['model_calls_spent']+=spent;row['history'].append({'event':'explicit_bounded_regional_review','request_id':ID,'model_calls':spent,'attempts_unchanged':row['attempts'],'at':utcnow()});row.update(status='needs_attention',next_attempt_at=None,reason='bounded_regional_phase_pending_or_blocked')
     if regional_error is not None:
      from .failure_diagnostics import failure_details
      from .execution_recovery import uncertain_outcome
      row['last_failure']=failure_details(regional_error)
      if uncertain_outcome(regional_error):row.update(status='reconciliation_required',reason='uncertain_regional_response_never_replayed')
     atomic_json(q.path(folder,lang),row)
   # Semantic work is staged in this request's isolated workspace, not old paths.
   shadow=root/'work'/lang/'new'/TOPIC
   for name in ('article.json','article-evidence-review.json'):
    target=shadow/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/name,target)
   target=shadow/'regional-research'/lang/'approved.json';target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/'regional-research'/lang/'approved.json',target)
   row=load_json(q.path(folder,lang));row.update(status='waiting',next_attempt_at=utcnow());atomic_json(q.path(shadow,lang),row);client.phase='semantic'
   result=q.run_item(q.path(shadow,lang),client,data)
   updated=load_json(q.path(shadow,lang))
   if updated['attempts']!=3 or not rows[lang]['model_calls_spent']<=updated['model_calls_spent']<=7:raise Blocked('original_item_budget_or_attempt_count_changed')
   # Retain every new attempt/candidate, including a rejected or unknown one.
   for src in (shadow/'review-queue').rglob('*'):
    if not src.is_file():continue
    rel=src.relative_to(shadow);dst=folder/rel
    if rel.as_posix()=='review-queue/'+lang+'.json':continue # Commit queue status last.
    if not mutable('out/new/'+TOPIC+'/'+rel.as_posix()):raise Blocked('unexpected_semantic_work_path')
    if dst.exists():raise Blocked('old_semantic_artifact_never_overwritten')
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
   if result['status']=='approved':
    if not q.approved(shadow,article,lang):raise Blocked('validated_shadow_fidelity_required')
    for suffix in ('.json','.raw.json','.fidelity.json'):
     src=q.target(shadow,lang) if suffix=='.json' else shadow/'translations'/(lang+suffix);dst=folder/'translations'/(lang+suffix)
     if dst.exists():raise Blocked('existing_target_never_overwritten')
     dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    if not q.approved(folder,article,lang):raise Blocked('adopted_fidelity_binding_changed')
   atomic_json(q.path(folder,lang),updated)
   r['results'].append(result);atomic_json(rp,r)
   if result['status']!='approved':raise Blocked('semantic_result_remains_blocked_no_more_calls')
  if not all(q.approved(folder,article,l) and q.regional_ready(load_json(q.path(folder,l)),folder,data) for l in LANGS+RETAINED):raise Blocked('all_language_acceptance_required')
  r['status']='family07_multilingual_verified_not_published'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  r.update(status='family07_multilingual_blocked',failure={'kind':'bounded_guard','category':str(exc)} if type(exc)is Blocked else failure_details(exc))
 finally:
  state=snapshot(db);record_routing(out,state);r['model_calls']=state['model_requests_reserved'];r['originals_unchanged']=manifest(data,out)==before
  if not r['originals_unchanged']:r['status']='family07_multilingual_originals_changed'
  r['queue_counters']={l:{k:load_json(q.path(folder,l)).get(k) for k in ('status','attempts','model_calls_spent')} for l in LANGS+RETAINED}
  r['completed_at']=utcnow();atomic_json(rp,r)
 return r
