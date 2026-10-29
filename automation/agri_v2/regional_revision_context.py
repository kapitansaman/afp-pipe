"""Explicit context-only continuation of confirmed revision extraction.
No new search, old counters reset, negative-to-positive conversion or live writes.
"""
import time
from .queue import DATA,OUT,load_json,atomic_json,utcnow,get_topic,age_hours
from .pipeline import digest
from . import regional_revision as revision
ID='alfalfa-revision-context-repair-v1'
LIMIT=5

def validate(req,data,out):
 root=out/'regional-revisions'/revision.ID;old=load_json(root/'report.json')
 expected={'version':1,'request_id':ID,'revision_request_id':revision.ID,'prepare_authorized':True,'publication_authorized':False,'max_remaining_model_calls':LIMIT,'max_search_requests':0,'max_continuations':1,'reset_original_attempts':False}
 if any(type(req.get(k)) is not type(v) or req.get(k)!=v for k,v in expected.items()) or req.get('prior_report_sha256')!=digest(old) or old.get('status')!='revision_needs_attention' or old.get('model_calls')!=3 or old.get('source_search',{}).get('unknown_requests')!=0:raise ValueError('context_repair_request_or_prior_report_changed')
 revision.validate_request(load_json(data/'regional-revision-request.json'),data,out)
 if old['input_binding']!=revision.inputs(data,out):raise ValueError('context_repair_original_changed')
 calls=root/'calls';receipts=list(calls.glob('*.receipt.json'))
 if {p.name for p in receipts}!={'search-plan.receipt.json','local-extract.receipt.json','international-extract.receipt.json'}:raise ValueError('context_repair_requires_exact_confirmed_prior_calls')
 for p in receipts:
  row=load_json(p);raw=p.with_name(p.name.replace('.receipt.json','.raw.json'))
  if row.get('status')!='received' or row.get('raw_sha256')!=digest(load_json(raw)):raise ValueError('context_repair_prior_call_uncertain_or_changed')
 rejected=load_json(calls/'international-extract.raw.json')
 if rejected.get('answers_intent') is not False or rejected.get('facts')!=[]:raise ValueError('context_repair_only_confirmed_empty_extraction')
 docs=load_json(root/'phases/international/new'/revision.TOPIC/'lifecycle-evidence/sources.json')['documents']
 import hashlib
 from .regional_sources import documents_for
 if not docs or documents_for(docs,'fa-IR',allow_international=True)!=docs or any(d.get('sha256')!=hashlib.sha256(d['text'].encode()).hexdigest() for d in docs):raise ValueError('context_repair_documents_changed')
 if req.get('documents_sha256')!=digest(docs):raise ValueError('context_repair_documents_not_bound')
 return root,docs

def run(env,data=DATA,out=OUT,client_factory=None):
 if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REPOSITORY')!='kapitansaman/afp-pipe' or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ValueError('manual_destination_context_repair_required')
 req=load_json(data/'regional-revision-context-request.json');root=out/'regional-revisions'/revision.ID;sub=root/'continuations'/ID;rp=sub/'report.json'
 if rp.exists():return {'status':'context_repair_already_reserved_no_replay','post_mutations':0,'model_calls':0}
 root,docs=validate(req,data,out);health=load_json(out/'parallel/health/latest.json')
 if not 0<=age_hours(health['checked_at'])<24:return {'status':'revision_fresh_text_health_required','post_mutations':0,'model_calls':0}
 from .provider_diagnostic import active_cooldown
 if active_cooldown(out):return {'status':'revision_provider_cooldown','post_mutations':0,'model_calls':0}
 from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing
 db=sub/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=LIMIT,per_worker=LIMIT,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=revision.TOPIC,AFP_PARALLEL_FAMILY='family-07')
 for k in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD','AFP_SOURCE_SEARCH_API_KEY'):worker.pop(k,None)
 row={'version':1,'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'reserved','started_at':utcnow(),'publication_authorized':False,'post_mutations':0,'new_posts':0,'search_requests':0,'original_attempts_reset':False,'prior_report_sha256':req['prior_report_sha256']};atomic_json(rp,row);atomic_json(sub/'request.json',req)
 try:
  if client_factory is None:
   from .parallel_client import ParallelModelClient
   client_factory=ParallelModelClient
  client=client_factory(health,env=worker,allow_calls=True,capabilities=('text',));calls=root/'calls';topic=get_topic('new',revision.TOPIC,data)
  brief=revision.extract_review(topic,docs,'international-context-repair',client,calls,data,sub);atomic_json(sub/'brief.json',brief)
  from .practical_drafting import generate
  article=generate(revision.ReceiptClient(client,calls,'persian-rewrite','persian-writer'),topic,brief,sub);atomic_json(sub/'article.json',article)
  from .scoped_research import review_article
  review_article(topic,article,brief,sub,revision.ReceiptClient(client,calls,'article-evidence-review','evidence-reviewer'))
  revision.review_region(topic,article,brief,docs,client,calls,sub,data)
  if revision.inputs(data,out)!=load_json(data/'regional-revision-request.json')['input_binding']:raise ValueError('context_repair_original_changed')
  row.update(status='revision_ready_for_publication_review',article_sha256=digest(article),brief_sha256=digest(brief),next_required_gates=['explicit_same_post_revision_transaction','fresh_authenticated_original_bytes_and_identity_check','overlap_scope_revalidation','image_binding_and_visual_review','new_source_bound_translations_and_reviews','public_bytes_verification'])
 except Exception as exc:
  from .failure_diagnostics import failure_details
  from .execution_recovery import uncertain_outcome
  row.update(status='revision_reconciliation_required' if uncertain_outcome(exc) else 'revision_needs_attention',failure=failure_details(exc))
 finally:
  pool=snapshot(db);record_routing(out,pool)
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':pool['cooldown_until_epoch'],'reason':'regional_context_repair_provider_failure'})
  row.update(model_calls=pool['model_requests_reserved'],total_revision_receipts=len(list((root/'calls').glob('*.receipt.json'))),completed_at=utcnow());atomic_json(rp,row)
 return row
