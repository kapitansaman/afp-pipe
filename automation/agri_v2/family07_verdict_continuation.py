"""New owner-requested forward continuation; nine remaining text calls, no fetch/replay."""
import json,shutil,time
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours,get_topic
from .pipeline import digest
from .infrastructure_probe import identity,code_hash,protected
from . import family07_multilingual as previous,language_review_queue as q,regional_sources as regional
from . import single_family_capability as capability
from .regional_explicit_decision import VERSION
from .retained_regional_positive import CacheOnly
ID='authorized-family07-explicit-verdict-nine-remaining-v1'
PHASE='family07-verdict-continuation';REQUEST='family07-verdict-continuation-request.json'
TOPIC=previous.TOPIC;FAMILY=previous.FAMILY;LANGS=previous.LANGS;RETAINED=previous.RETAINED
Blocked=previous.Blocked

def mutable(rel):
 if any(rel.startswith('out/new/'+TOPIC+'/'+prefix+l) for l in RETAINED for prefix in ('review-queue/','regional-research/','translations/')):return False
 return previous.mutable(rel)
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
  if row['article_sha256']!=digest(article) or q.published(folder,l) or (l in LANGS and (folder/'regional-research'/l/'approved.json').exists()):raise Blocked('unchanged_unpublished_unapproved_inputs_required')
 for l in LANGS:
  row=rows[l]
  if (row['status'],row['attempts'],row['model_calls_spent'])!=({'ru-RU':('needs_attention',2,3),'tg-TJ':('waiting',2,2)}[l]):raise Blocked('exact_two_spent_missing_language_attempts_required')
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
  if rows[l]['status']!='approved' or rows[l]['attempts']!=3 or rows[l]['model_calls_spent']!=5 or not q.approved(folder,article,l) or not q.regional_ready(rows[l],folder,data):raise Blocked('retained_fidelity_and_exhausted_counters_required')
 urls=ordered(brief,[])
 if len(urls)!=3:raise Blocked('exact_three_declared_sources_required')
 return folder,article,brief,rows,urls


def prior_proof(data=DATA,out=OUT):
 from .source_loading import valid_document
 from .research import source_host
 from .translation_review_repair import request
 folder,article,brief,rows,urls=inputs(data,out);root=out/'infrastructure-probes'/previous.ID;report=load_json(root/'report.json')
 if report.get('status')!='family07_multilingual_blocked' or report.get('failure',{}).get('category')!='regional_literal_technical_evidence_required' or report.get('model_calls')!=1 or report.get('source_fetches')!=3 or report.get('originals_unchanged')is not True:raise Blocked('exact_completed_previous_run_required')
 docs=[load_json(root/'documents'/(str(i)+'.json')) for i in range(3)]
 if [d['url'] for d in docs]!=urls or any(not valid_document(d,url,source_host) for d,url in zip(docs,urls)):raise Blocked('cached_sources_expired_no_implicit_fetch')
 rawpath=root/'regional/ru-RU/regional-evidence-review-fallback.raw.json';raw=load_json(rawpath)
 canonical=request(CacheOnly(),root/'regional/ru-RU','regional-evidence-review-fallback',previous.prompt(article,brief,docs,'ru-RU'),1)
 if any(row['supported']is not False for row in canonical['fact_checks']) or any(raw[k]['value']is not True for k in ('applicable','country_limits_retained','no_unsupported_local_prescription')):raise Blocked('bound_previous_decision_shape_changed')
 return {'report_sha256':digest(report),'raw_sha256':digest(raw),'canonical_sha256':digest(canonical),'documents':docs,'prior_text_calls':1,'prior_source_fetches':3,'historical_result_changed':False}

def prompt(article,brief,docs,lang):
 p=regional.review_prompt(article,brief,lang,docs,wire=VERSION)
 p['fallback_rule']='The retained, bound, completed local search pack was empty. These unchanged fresh original sources are international fallback only. Keep meaningful local evidence gaps and actual transfer limits. Never force approval.'
 p['prior_consistency_notice']={'untrusted_diagnostic_data':True,'observation':'A previous response used negative source-support booleans with explanations describing support. Do not repeat this ambiguity. Independently evaluate each exact bounded claim and explicitly choose the new enum; never merely flip old flags.','historical_raw_unchanged':True}
 return p

def expected(data=DATA,out=OUT):
 folder,a,b,rows,urls=inputs(data,out);p=previous.capability_proof(data,out);old=prior_proof(data,out)
 return {'version':1,'request_id':ID,'authorization':'owner_requested_fix_using_nine_remaining_text_calls_no_new_sources','authorization_source':'https://app.notion.com/chat?t=40841579fa0a8078988900a99eb829d4',
 'family_id':FAMILY,'topic_id':TOPIC,'code_sha256':code_hash(),'protected_sha256':digest(manifest(data,out)),'article_sha256':digest(a),'brief_sha256':digest(b),'queue_sha256':{l:digest(r) for l,r in rows.items()},'prior_proof_sha256':digest(old),'scoped_capability_sha256':digest(p),'source_urls':urls,'languages':list(LANGS),'wire':VERSION,
 'role_slots':{'translator':capability.TEXT[0],'fidelity_reviewer':capability.TEXT[1],'regional_reviewer':capability.TEXT[2]},'max_runs':1,'max_text_calls':9,'combined_prior_and_new_text_cap':10,'max_regional_calls_per_language':1,'max_semantic_calls_per_language':4,'max_source_fetches':0,'max_search_requests':0,'max_site_calls':0,'max_image_calls':0,'max_attempts_per_request':1,'max_in_flight':1,'conditional_internal_evidence_adoption_authorized':True,'publication_authorized':False,'schedule_enabled':False,'stage_promotion_authorized':False,'reset_attempts':False,'global_capacity_refresh':False,'max_automatic_attempts':3,'max_model_calls_per_item':12}
def validate(req,data=DATA,out=OUT):
 v=expected(data,out)
 if type(req)is not dict or set(req)!=set(v) or any(type(req[k])is not type(x) or req[k]!=x for k,x in v.items()):raise Blocked('verdict_continuation_admission_changed')
 return inputs(data,out)
def client_factory(worker,root,data,out):
 client=previous.CountedClient(worker,root,data,out,request_id=ID,max_calls=9,manifest_fn=manifest);transport=client.request
 def checked(*args,**kwargs):
  from .source_loading import valid_document
  from .research import source_host
  docs=[load_json(out/'infrastructure-probes'/previous.ID/'documents'/(str(i)+'.json')) for i in range(3)]
  if any(not valid_document(d,d['url'],source_host) for d in docs):raise Blocked('cached_sources_expired_no_implicit_fetch')
  return transport(*args,**kwargs)
 client.request=checked;return client
save_approval=previous.save_approval
def run(env,data=DATA,out=OUT,client_factory_fn=None,reserve_fn=None):
 identity(env);root=out/'infrastructure-probes'/ID;rp=root/'report.json'
 if rp.exists():return {'status':'family07_verdict_already_reserved_no_replay','model_calls':0,'source_fetches':0}
 folder,article,brief,rows,urls=validate(load_json(data/REQUEST),data,out)
 capability.guards(out);capability.check_unique_values(env)
 if any(not env.get(s,'').strip() for s in capability.TEXT):raise Blocked('owned_credentials_missing')
 old=prior_proof(data,out);docs=old['documents']
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
 if not admitted:return {'status':'family07_verdict_already_reserved_no_replay','model_calls':0,'source_fetches':0}
 before=manifest(data,out);r={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'family07_verdict_reserved','started_at':utcnow(),
  'model_calls':0,'source_fetches':0,'max_text_calls':9,'max_source_fetches':0,'prior_text_calls':1,'combined_text_cap':10,'site_calls':0,'image_calls':0,'search_requests':0,'published_posts':0,
  'publication_authorized':False,'schedule_enabled':False,'stage_promotion_authorized':False,'attempts_reset':False,'global_capacity_refresh':False,
  'conditional_internal_evidence_adoption_authorized':True,'results':[]};atomic_json(rp,r)
 from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing
 from .translation_review_repair import request
 from .regional_schema_recheck import validate_wire
 from .role_skills import enrich
 db=root/'pool.sqlite';initialize(db,list(capability.TEXT),text_limit=1,image_limit=1,max_calls=9,per_worker=9,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker={k:env[k] for k in capability.TEXT};worker.update({k:env[k] for k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID') if k in env});worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=ID,AFP_PARALLEL_FAMILY=FAMILY)
 try:
  client=(client_factory_fn or client_factory)(worker,root,data,out)
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
   if updated['attempts']!=3 or not rows[lang]['model_calls_spent']+1<=updated['model_calls_spent']<=rows[lang]['model_calls_spent']+5:raise Blocked('original_item_budget_or_attempt_count_changed')
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
  r['status']='family07_verdict_verified_not_published'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  r.update(status='family07_verdict_blocked',failure={'kind':'bounded_guard','category':str(exc)} if type(exc)is Blocked else failure_details(exc))
 finally:
  state=snapshot(db);record_routing(out,state);r['model_calls']=state['model_requests_reserved'];r['combined_text_calls']=1+r['model_calls'];r['originals_unchanged']=manifest(data,out)==before
  if not r['originals_unchanged']:r['status']='family07_verdict_originals_changed'
  r['queue_counters']={l:{k:load_json(q.path(folder,l)).get(k) for k in ('status','attempts','model_calls_spent')} for l in LANGS+RETAINED}
  r['completed_at']=utcnow();atomic_json(rp,r)
 return r
