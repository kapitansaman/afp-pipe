"""Zero-call Russian reconciliation + at most five remaining Tajik text calls."""
import json,shutil,time
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .pipeline import digest
from .infrastructure_probe import identity,code_hash,protected
from . import family07_verdict_continuation as previous, family07_multilingual as transport, language_review_queue as q,regional_sources as regional
from . import single_family_capability as capability
from .regional_explicit_decision import VERSION
from .retained_russian_fidelity import revalidate as russian
ID='authorized-family07-decimal-reconcile-five-remaining-v1'
PHASE='family07-decimal-continuation';REQUEST='family07-decimal-continuation-request.json'
TOPIC=previous.TOPIC;FAMILY=previous.FAMILY;LANGS=('tg-TJ',);RETAINED=('ar-IQ','en-US','ru-RU')
Blocked=transport.Blocked

def mutable(rel):
 prefix='out/new/'+TOPIC+'/'
 if rel==prefix+'review-queue/ru-RU.json' or rel in [prefix+'translations/ru-RU'+suffix for suffix in ('.json','.raw.json','.fidelity.json')]:return True
 if rel.startswith(prefix) and ('/tg-TJ/' in rel or rel.endswith('tg-TJ.json') or '/tg-TJ.' in rel or rel.endswith('candidate-tg-TJ.json')):return transport.mutable(rel)
 return False
def manifest(data,out):return {k:v for k,v in protected(data,out,ID).items() if k!='data/'+REQUEST and not mutable(k)}
def inputs(data=DATA,out=OUT):
 from .staged_rollout import load
 from .family_model_routing import load as roles
 from .regional_source_seeds import ordered
 state=load(out)
 if state['limit']!=1 or len(state['cohort'])!=1 or state['cohort'][0]['topic_id']!=TOPIC or state['cohort'][0]['family_id']!=FAMILY:raise Blocked('exact_family07_cohort_required')
 if roles(data)['families'][FAMILY]!={'text_slots':list(capability.TEXT),'image_slot':capability.IMAGE}:raise Blocked('exact_owned_text_roles_required')
 folder=out/'new'/TOPIC;article=load_json(folder/'article.json');brief=load_json(data/'briefs'/(TOPIC+'.json'));rows={l:load_json(q.path(folder,l)) for l in LANGS+RETAINED}
 for lang,row in rows.items():
  q.source_checked(row,article,folder,data)
  if q.published(folder,lang) or row['article_sha256']!=digest(article):raise Blocked('unchanged_unpublished_input_required')
 for lang in ('ar-IQ','en-US'):
  if (rows[lang]['status'],rows[lang]['attempts'],rows[lang]['model_calls_spent'])!=('approved',3,5) or not q.approved(folder,article,lang) or not q.regional_ready(rows[lang],folder,data):raise Blocked('retained_approved_languages_required')
 row=rows['tg-TJ']
 if (row['status'],row['attempts'],row['model_calls_spent'])!=('waiting',2,2):raise Blocked('exact_unspent_tajik_final_attempt_required')
 if any((folder/'translations'/('tg-TJ'+suffix)).exists() for suffix in ('.json','.raw.json','.fidelity.json')) or (folder/'review-queue/attempts/tg-TJ/3').exists() or (folder/'review-queue/candidate-tg-TJ.json').exists() or (folder/'regional-research/tg-TJ/approved.json').exists():raise Blocked('missing_tajik_only_no_replay')
 # The prior bound empty-local pack stays immutable and remains required.
 from .regional_continuation import confirmed
 from .regional_sources import profile
 from .queue import get_topic
 topic=get_topic('new',TOPIC,data);contract={'international_fallback':False,'policy':profile('tg-TJ'),'topic':{k:topic[k] for k in ('id','title','crop','intent')}};local=folder/'regional-research/tg-TJ/local';pack=load_json(local/'documents.json');plan=load_json(local/'search-plan.json')
 if pack.get('contract_sha256')!=digest(contract) or pack.get('documents')!=[] or plan.get('contract_sha256')!=digest(contract) or plan.get('publication_authorized')is not False or len(plan.get('queries',[]))!=2 or not confirmed(folder/'review-queue/attempts/tg-TJ/2'):raise Blocked('bound_completed_empty_local_pack_required')
 from .source_search import validate_results
 for i,query in enumerate(plan['queries']):
  receipt=load_json(local/('search-'+str(i)+'.json'))
  if receipt.get('query_sha256')!=digest(query) or receipt.get('publication_authorized')is not False:raise Blocked('local_search_receipt_changed')
  validate_results(receipt['result']['results'])
 russian(data,out)
 return folder,article,brief,rows,ordered(brief,[])
def cached_documents(out):
 from .source_loading import valid_document
 from .research import source_host
 docs=[load_json(out/'infrastructure-probes'/transport.ID/'documents'/(str(i)+'.json')) for i in range(3)]
 if any(not valid_document(d,d['url'],source_host) for d in docs):raise Blocked('cached_sources_expired_no_implicit_fetch')
 return docs
def prior_proof(data=DATA,out=OUT):
 root=out/'infrastructure-probes'/previous.ID;report=load_json(root/'report.json');older=load_json(out/'infrastructure-probes'/transport.ID/'report.json')
 if report.get('status')!='family07_verdict_blocked' or report.get('failure',{}).get('category')!='semantic_result_remains_blocked_no_more_calls' or report.get('model_calls')!=4 or report.get('combined_text_calls')!=5 or report.get('originals_unchanged')is not True or older.get('model_calls')!=1 or older.get('source_fetches')!=3 or older.get('originals_unchanged')is not True:raise Blocked('exact_five_spent_prior_calls_required')
 docs=cached_documents(out)
 from .regional_source_seeds import ordered
 brief=load_json(data/'briefs'/(TOPIC+'.json'));approved=load_json(out/'new'/TOPIC/'regional-research/ru-RU/approved.json')
 if [d['url'] for d in docs]!=ordered(brief,[]) or {d['url']:d['sha256'] for d in docs}!={d['url']:d['sha256'] for d in approved['documents']}:raise Blocked('exact_original_source_text_required')
 return {'report_sha256':digest(report),'earlier_report_sha256':digest(older),'documents':docs,'russian_reconciliation_sha256':digest(russian(data,out)),'prior_text_calls':5,'historical_result_changed':False}
def expected(data=DATA,out=OUT):
 folder,a,b,rows,urls=inputs(data,out);proof=transport.capability_proof(data,out);old=prior_proof(data,out)
 return {'version':1,'request_id':ID,'authorization':'owner_requested_fix_decimal_comparison_and_use_five_remaining_tajik_calls','authorization_source':'https://app.notion.com/chat?t=40841579fa0a8078988900a99eb829d4','family_id':FAMILY,'topic_id':TOPIC,'code_sha256':code_hash(),'protected_sha256':digest(manifest(data,out)),'article_sha256':digest(a),'brief_sha256':digest(b),'queue_sha256':{l:digest(r) for l,r in rows.items()},'prior_proof_sha256':digest(old),'scoped_capability_sha256':digest(proof),'wire':VERSION,'source_urls':urls,'languages':list(LANGS),'russian_model_calls':0,'max_runs':1,'max_text_calls':5,'combined_prior_and_new_text_cap':10,'max_regional_calls_per_language':1,'max_semantic_calls_per_language':4,'max_source_fetches':0,'max_search_requests':0,'max_site_calls':0,'max_image_calls':0,'max_attempts_per_request':1,'max_in_flight':1,'role_slots':{'translator':capability.TEXT[0],'fidelity_reviewer':capability.TEXT[1],'regional_reviewer':capability.TEXT[2]},'conditional_internal_evidence_adoption_authorized':True,'publication_authorized':False,'schedule_enabled':False,'stage_promotion_authorized':False,'reset_attempts':False,'global_capacity_refresh':False,'max_automatic_attempts':3,'max_model_calls_per_item':12}
def validate(req,data=DATA,out=OUT):
 v=expected(data,out)
 if type(req)is not dict or set(req)!=set(v) or any(type(req[k])is not type(x) or req[k]!=x for k,x in v.items()):raise Blocked('decimal_continuation_admission_changed')
 return inputs(data,out)
def client_factory(worker,root,data,out):
 client=transport.CountedClient(worker,root,data,out,request_id=ID,max_calls=5,manifest_fn=manifest);request=client.request
 def checked(*args,**kwargs):cached_documents(out);return request(*args,**kwargs)
 client.request=checked;return client
def reconcile_russian(data,out):
 proof=russian(data,out);folder=out/'new'/TOPIC;lang='ru-RU';row=load_json(q.path(folder,lang))
 for suffix,value in [('.raw.json',proof['raw']),('.json',proof['rendered']),('.fidelity.json',{'article_sha256':proof['article_sha256'],'translation_sha256':digest(proof['rendered']),'review':proof['review'],'reviewed_at':proof['reviewed_at'],'reconciliation_provenance':{k:v for k,v in proof.items() if k not in ('raw','rendered','review')},'request_id':ID})]:
  path=folder/'translations'/(lang+suffix)
  if path.exists():raise Blocked('existing_russian_target_never_overwritten')
  atomic_json(path,value)
 if not q.approved(folder,load_json(folder/'article.json'),lang):raise Blocked('reconciled_russian_fidelity_binding_required')
 row['history'].append({'event':'source_bound_decimal_locale_reconciliation','request_id':ID,'at':utcnow(),'model_calls':0,'attempts_unchanged':3,'spent_unchanged':7,'review_receipt_sha256':proof['review_receipt_sha256'],'partial_edit_retained_not_applied':True});row.update(status='approved',next_attempt_at=None,reason='received_positive_review_and_locale_numeric_gates_passed');atomic_json(q.path(folder,lang),row)
 return {'language':lang,'status':'received_positive_review_reconciled','model_calls':0}
prompt=previous.prompt;save_approval=transport.save_approval
def run(env,data=DATA,out=OUT,client_factory_fn=None,reserve_fn=None):
 identity(env);root=out/'infrastructure-probes'/ID;rp=root/'report.json'
 if rp.exists():return {'status':'family07_decimal_already_reserved_no_replay','model_calls':0,'source_fetches':0}
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
 if not admitted:return {'status':'family07_decimal_already_reserved_no_replay','model_calls':0,'source_fetches':0}
 before=manifest(data,out);r={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'family07_decimal_reserved','started_at':utcnow(),
  'model_calls':0,'source_fetches':0,'max_text_calls':5,'max_source_fetches':0,'prior_text_calls':5,'combined_text_cap':10,'site_calls':0,'image_calls':0,'search_requests':0,'published_posts':0,
  'publication_authorized':False,'schedule_enabled':False,'stage_promotion_authorized':False,'attempts_reset':False,'global_capacity_refresh':False,
  'conditional_internal_evidence_adoption_authorized':True,'results':[]};atomic_json(rp,r)
 from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing
 from .translation_review_repair import request
 from .regional_schema_recheck import validate_wire
 from .role_skills import enrich
 db=root/'pool.sqlite';initialize(db,list(capability.TEXT),text_limit=1,image_limit=1,max_calls=5,per_worker=5,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker={k:env[k] for k in capability.TEXT};worker.update({k:env[k] for k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID') if k in env});worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=ID,AFP_PARALLEL_FAMILY=FAMILY)
 try:
  r['results'].append(reconcile_russian(data,out));atomic_json(rp,r)
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
  r['status']='family07_decimal_verified_not_published'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  r.update(status='family07_decimal_blocked',failure={'kind':'bounded_guard','category':str(exc)} if type(exc)is Blocked else failure_details(exc))
 finally:
  state=snapshot(db);record_routing(out,state);r['model_calls']=state['model_requests_reserved'];r['combined_text_calls']=5+r['model_calls'];r['originals_unchanged']=manifest(data,out)==before
  if not r['originals_unchanged']:r['status']='family07_decimal_originals_changed'
  r['queue_counters']={l:{k:load_json(q.path(folder,l)).get(k) for k in ('status','attempts','model_calls_spent')} for l in LANGS+RETAINED}
  r['completed_at']=utcnow();atomic_json(rp,r)
 return r
