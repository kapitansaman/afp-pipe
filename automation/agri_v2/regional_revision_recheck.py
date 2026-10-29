"""Final bounded recheck of an explicitly prepared corrected proposal.
Three remaining review calls of the original eight; no writer/search/live mutation.
"""
import time,hashlib
from .queue import DATA,OUT,load_json,atomic_json,utcnow,get_topic,age_hours
from .pipeline import digest
from . import regional_revision as r
ID='alfalfa-prepared-scientific-recheck-v1'
NAMES={'search-plan','local-extract','international-extract','international-context-repair-extract','international-context-repair-fact-review'}

def validate(req,data,out):
 root=out/'regional-revisions'/r.ID;proposal=load_json(data/'alfalfa-scientific-proposal.json');process=load_json(data/'regional-revision-local-process.json')
 expected={'version':1,'request_id':ID,'revision_request_id':r.ID,'prepare_authorized':True,'publication_authorized':False,'max_remaining_model_calls':3,'max_search_requests':0,'max_rechecks':1,'reset_original_attempts':False}
 if any(type(req.get(k)) is not type(v) or req.get(k)!=v for k,v in expected.items()) or req.get('proposal_sha256')!=digest(proposal) or req.get('local_process_sha256')!=digest(process):raise ValueError('prepared_recheck_request_or_proposal_changed')
 prior=load_json(root/'continuations/alfalfa-revision-context-repair-v1/report.json')
 if req.get('context_report_sha256')!=digest(prior) or prior.get('status')!='revision_needs_attention' or prior.get('total_revision_receipts')!=5:raise ValueError('prepared_recheck_prior_report_changed')
 r.validate_request(load_json(data/'regional-revision-request.json'),data,out)
 calls=root/'calls';receipts=list(calls.glob('*.receipt.json'))
 if {p.name.removesuffix('.receipt.json') for p in receipts}!=NAMES:raise ValueError('prepared_recheck_requires_five_confirmed_calls')
 for p in receipts:
  row=load_json(p);raw=p.with_name(p.name.replace('.receipt.json','.raw.json'))
  if row.get('status')!='received' or row.get('raw_sha256')!=digest(load_json(raw)):raise ValueError('prepared_recheck_unknown_or_changed_call')
 docs=load_json(root/'phases/international/new'/r.TOPIC/'lifecycle-evidence/sources.json')['documents']
 if digest(docs)!=req.get('documents_sha256') or proposal.get('documents_sha256')!=digest(docs) or any(d.get('sha256')!=hashlib.sha256(d['text'].encode()).hexdigest() for d in docs):raise ValueError('prepared_recheck_documents_changed')
 from .scoped_research import validate_candidate,tokens
 topic=get_topic('new',r.TOPIC,data);candidate=proposal['candidate'];facts=validate_candidate(topic,candidate,docs)
 import re
 if proposal.get('scientific_approval') is not False or proposal.get('publication_authorized') is not False or proposal.get('request_id')!=ID:raise ValueError('prepared_recheck_no_prior_approval_allowed')
 if any(f['kind']!='qualitative' or tokens(f['claim']+' '+f['conditions']) or re.search(r'(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)[\s‌-]*(?:روز|هفته|ماه|سال|اینچ|میلی.?متر|سانتی.?متر|متر|درصد)\b',f['claim']) for f in facts):raise ValueError('prepared_recheck_no_disguised_measurement')
 # The diagnostic history describes process, not scientific adequacy.
 oldplan=load_json(root/'search-plan.json');local=load_json(root/'phases/local/new'/r.TOPIC/'lifecycle-evidence/sources.json')['documents'];gap=load_json(root/'calls/local-extract.raw.json')
 if process.get('local_queries')!=oldplan['local_queries'] or process.get('local_document_urls')!=[d['url'] for d in local] or process.get('local_gap')!=gap.get('insufficiency_reason') or process.get('scientific_acceptance') is not False:raise ValueError('prepared_recheck_local_process_changed')
 return root,proposal,docs,topic,candidate,facts

def run(env,data=DATA,out=OUT,client_factory=None):
 if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REPOSITORY')!='kapitansaman/afp-pipe' or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ValueError('manual_destination_prepared_recheck_required')
 root=out/'regional-revisions'/r.ID;sub=root/'continuations'/ID;rp=sub/'report.json'
 if rp.exists():return {'status':'prepared_recheck_already_reserved_no_replay','post_mutations':0,'model_calls':0}
 req=load_json(data/'alfalfa-scientific-recheck-request.json');root,proposal,docs,topic,candidate,facts=validate(req,data,out);health=load_json(out/'parallel/health/latest.json')
 if not 0<=age_hours(health['checked_at'])<24:return {'status':'revision_fresh_text_health_required','post_mutations':0,'model_calls':0}
 from .provider_diagnostic import active_cooldown
 if active_cooldown(out):return {'status':'revision_provider_cooldown','post_mutations':0,'model_calls':0}
 from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing
 db=sub/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=3,per_worker=3,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=r.TOPIC,AFP_PARALLEL_FAMILY='family-07')
 for k in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD','AFP_SOURCE_SEARCH_API_KEY'):worker.pop(k,None)
 row={'version':1,'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'reserved','started_at':utcnow(),'publication_authorized':False,'post_mutations':0,'new_posts':0,'search_requests':0,'original_attempts_reset':False,'proposal_sha256':digest(proposal),'prior_report_sha256':req['context_report_sha256']};atomic_json(rp,row);atomic_json(sub/'request.json',req)
 try:
  if client_factory is None:
   from .parallel_client import ParallelModelClient
   client_factory=ParallelModelClient
  client=client_factory(health,env=worker,allow_calls=True,capabilities=('text',));calls=root/'calls'
  brief=r.review_candidate(topic,candidate,facts,docs,'prepared-qualitative',client,calls,data,sub/'lifecycle-evidence');atomic_json(sub/'brief.json',brief)
  from .practical_drafting import normalize
  article,normalization=normalize(proposal['article'],topic,brief);atomic_json(sub/'article.json',article);atomic_json(sub/'normalization.json',normalization)
  from .scoped_research import review_article
  review_article(topic,article,brief,sub,r.ReceiptClient(client,calls,'article-evidence-review','evidence-reviewer'))
  r.review_region(topic,article,brief,docs,client,calls,sub,data)
  if r.inputs(data,out)!=load_json(data/'regional-revision-request.json')['input_binding']:raise ValueError('prepared_recheck_original_changed')
  row.update(status='revision_ready_for_publication_review',article_sha256=digest(article),brief_sha256=digest(brief),next_required_gates=['explicit_same_post_revision_transaction','fresh_authenticated_original_bytes_and_identity_check','overlap_scope_revalidation','image_binding_and_visual_review','new_source_bound_translations_and_reviews','public_bytes_verification'])
 except Exception as exc:
  from .failure_diagnostics import failure_details
  from .execution_recovery import uncertain_outcome
  row.update(status='revision_reconciliation_required' if uncertain_outcome(exc) else 'revision_needs_attention',failure=failure_details(exc))
 finally:
  pool=snapshot(db);record_routing(out,pool)
  if pool['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':pool['cooldown_until_epoch'],'reason':'prepared_revision_provider_failure'})
  row.update(model_calls=pool['model_requests_reserved'],total_revision_receipts=len(list((root/'calls').glob('*.receipt.json'))),completed_at=utcnow());atomic_json(rp,row)
 return row
