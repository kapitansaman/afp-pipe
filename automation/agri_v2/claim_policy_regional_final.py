"""Owner-authorized, create-once regional-only final review. No search, writer or live publisher."""
import hashlib,time
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow,get_topic,age_hours
from .pipeline import digest
from . import regional_revision as revision,claim_policy,claim_policy_continuation as prior,claim_policy_recheck as initial
ID='alfalfa-claim-policy-regional-final-v1'
LIMIT=1
PRIOR='alfalfa-prepared-scientific-recheck-v1'
CODE_FILES=('claim_policy.py','claim_policy_recheck.py','scoped_research.py','scoped_review_v2.py',
 'regional_sources.py','regional_revision.py','research_review_contract.py','role_skills.py','pipeline.py','parallel_control.py',
 'claim_policy_continuation.py','claim_policy_regional_final.py','regional_review_schema.py','client.py','failure_diagnostics.py','translation_review_repair.py','parallel_client.py')

def code_binding():
 return {name:hashlib.sha256((ROOT/'automation/agri_v2'/name).read_bytes()).hexdigest() for name in CODE_FILES}

def protected_binding(data,out):
 """Includes all old calls/reports and owned family artifacts, not just the article."""
 old=out/'regional-revisions'/revision.ID;family=out/'new'/revision.TOPIC
 paths=list(old.rglob('*'))+list(family.rglob('*'))+list((out/'claim-policy-rechecks'/prior.ID).rglob('*'))+list((out/'claim-policy-rechecks'/initial.ID).rglob('*'))+list((data/'status/parallel-reservations').glob(prior.ID+'.json'))+[data/'alfalfa-claim-policy-recheck-request.json',data/'alfalfa-claim-policy-context-seed.json']+[data/'briefs'/(revision.TOPIC+'.json'),data/'alfalfa-scientific-proposal.json',data/'regional-revision-local-process.json']
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}

def validate(req,data,out):
 expected={'version':1,'request_id':ID,'topic_id':revision.TOPIC,'source_post_id':524204,
  'prepare_authorized':True,'publication_authorized':False,'max_model_calls':1,
  'max_search_requests':0,'max_runs':1,'reset_original_attempts':False,'policy_version':claim_policy.VERSION}
 if not isinstance(req,dict) or any(type(req.get(k)) is not type(v) or req.get(k)!=v for k,v in expected.items()):raise ValueError('regional_final_request_invalid')
 if req.get('code_binding')!=code_binding():raise ValueError('regional_final_code_changed')
 root=out/'claim-policy-rechecks'/prior.ID
 for path,sha in req.get('predecessor_files',{}).items():
  if digest(load_json(root/path))!=sha:raise ValueError('regional_final_predecessor_changed')
 required={'report.json','request.json','candidate.json','brief.json','article.json','lifecycle-evidence/fact-review.json','article-evidence-review.json','regional-review.raw.json'}
 names={'claim-policy-continuation-fact-review','article-evidence-review','persian-regional-review'}
 required.update('calls/'+n+ext for n in names for ext in ('.raw.json','.receipt.json'))
 if set(req.get('predecessor_files',{}))!=required:raise ValueError('regional_final_predecessor_binding_required')
 report=load_json(root/'report.json')
 if report.get('request_id')!=prior.ID or report.get('model_calls')!=3 or report.get('originals_unchanged') is not True or report.get('post_mutations')!=0 or report.get('failure')!={'kind':'validation','category':'claim_context_review_required'}:raise ValueError('regional_final_predecessor_state_invalid')
 for name in names:
  receipt=load_json(root/'calls'/(name+'.receipt.json'));raw=load_json(root/'calls'/(name+'.raw.json'))
  if receipt.get('status')!='received' or receipt.get('raw_sha256')!=digest(raw):raise ValueError('regional_final_unconfirmed_prior_response')
 oldroot=out/'claim-policy-rechecks'/initial.ID;previous_request=load_json(root/'request.json')
 if digest(load_json(oldroot/'report.json'))!=previous_request.get('predecessor_report_sha256') or digest(load_json(oldroot/'calls/context-annotation.receipt.json'))!=previous_request.get('predecessor_receipt_sha256') or (oldroot/'calls/context-annotation.raw.json').exists():raise ValueError('regional_final_initial_uncertain_request_changed')
 # Revalidate saved source/identity bindings and both exact accepted reviews locally.
 oldreq=load_json(data/'alfalfa-claim-policy-recheck-request.json')
 if digest(oldreq)!=req.get('original_request_sha256'):raise ValueError('regional_final_original_request_changed')
 proposal,docs,topic=initial.validate_inputs(oldreq,data,out)
 candidate=load_json(root/'candidate.json');brief=load_json(root/'brief.json');article=load_json(root/'article.json')
 from .scoped_research import validate_candidate,validate_review,validate_article_review_result
 from .scoped_review_v2 import validate as validate_detailed
 facts=validate_candidate(topic,candidate,docs);scientific=load_json(root/'lifecycle-evidence/fact-review.json')
 if scientific!=load_json(root/'calls/claim-policy-continuation-fact-review.raw.json'):raise ValueError('regional_final_scientific_receipt_mismatch')
 validate_review(scientific,facts);validate_detailed(scientific,facts)
 if brief.get('approved_facts')!=facts or brief.get('scoped_review')!=scientific or brief.get('publish_authorized') is not False:raise ValueError('regional_final_scientific_binding_invalid')
 audited=load_json(root/'article-evidence-review.json')
 if audited.get('article_sha256')!=digest(article) or audited.get('brief_sha256')!=digest(brief):raise ValueError('regional_final_article_binding_invalid')
 if audited.get('review')!=load_json(root/'calls/article-evidence-review.raw.json'):raise ValueError('regional_final_article_receipt_mismatch')
 validate_article_review_result(article,audited['review'])
 if len({f['source_url'] for f in facts})!=1:raise ValueError('regional_final_single_cited_document_required')
 return article,brief,docs,topic

class BoundedReviewClient:
 def __init__(self,base,facts):self.base=base;self.facts=facts
 def text(self,prompt,**kwargs):
  from .regional_review_schema import schema
  kwargs.update(attempts=1,max_tokens=20000,timeout=180,response_schema=schema(self.facts))
  return self.base.text(prompt,**kwargs)

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None):
 from .parallel_control import BRANCH
 if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REPOSITORY')!='kapitansaman/afp-pipe' or env.get('GITHUB_REF_NAME')!=BRANCH or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ValueError('claim_recheck_manual_branch_required')
 root=out/'claim-policy-rechecks'/ID;rp=root/'report.json'
 if rp.exists():return {'status':'claim_recheck_already_reserved_no_replay','model_calls':0,'post_mutations':0}
 req=load_json(data/'alfalfa-claim-policy-regional-final-request.json');article,brief,docs,topic=validate(req,data,out)
 health=load_json(out/'parallel/health/latest.json')
 if not 0<=age_hours(health['checked_at'])<24:return {'status':'revision_fresh_text_health_required','post_mutations':0,'model_calls':0}
 from .provider_diagnostic import active_cooldown
 if active_cooldown(out):return {'status':'revision_provider_cooldown','post_mutations':0,'model_calls':0}
 from .parallel_control import reserve
 reservation=(reserve if reserve_fn is None else reserve_fn)('claim-policy-regional-final',ID,env)
 if reservation is None:return {'status':'claim_recheck_already_reserved_no_replay','model_calls':0,'post_mutations':0}
 before=protected_binding(data,out)
 from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing
 db=root/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=LIMIT,per_worker=LIMIT,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=revision.TOPIC,AFP_PARALLEL_FAMILY='family-07')
 for key in list(worker):
  if key.startswith('AFP_WP_') or key in ('AFP_SOURCE_SEARCH_API_KEY','FTP_PASSWORD'):worker.pop(key,None)
 row={'version':1,'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'reserved','started_at':utcnow(),'max_model_calls':LIMIT,'publication_authorized':False,'post_mutations':0,'new_posts':0,'search_requests':0,'writer_calls':0,'original_attempts_reset':False,'input_binding':revision.inputs(data,out),'protected_sha256':digest(before),'prior_model_calls_preserved':12,'uncertain_predecessor_request_preserved':True,'accepted_reviews_reused_without_model_calls':2,'policy_version':claim_policy.VERSION}
 atomic_json(rp,row);atomic_json(root/'request.json',req)
 calls=root/'calls'
 try:
  if client_factory is None:
   from .parallel_client import ParallelModelClient
   client_factory=ParallelModelClient
  client=BoundedReviewClient(client_factory(health,env=worker,allow_calls=True,capabilities=('text',)),brief['approved_facts'])
  atomic_json(root/'article.json',article);atomic_json(root/'brief.json',brief)
  facts=brief['approved_facts']
  revision.review_region(topic,article,brief,[d for d in docs if d['url'] in {f['source_url'] for f in facts}],client,calls,root,data)
  row.update(status='claim_recheck_ready_for_publication_review',article_sha256=digest(article),brief_sha256=digest(brief),next_required_gates=['explicit_same_post_revision_transaction','fresh_authenticated_original_identity_and_bytes','overlap_scope_revalidation','image_binding_and_visual_review','new_source_bound_translations_and_reviews','public_bytes_verification'])
 except Exception as exc:
  from .failure_diagnostics import failure_details
  from .execution_recovery import uncertain_outcome
  row.update(status='revision_reconciliation_required' if uncertain_outcome(exc) else 'revision_needs_attention',failure=failure_details(exc))
 finally:
  state=snapshot(db);record_routing(out,state)
  unchanged=protected_binding(data,out)==before
  if not unchanged:row.update(status='revision_reconciliation_required',failure={'kind':'validation','category':'protected_originals_changed'})
  if state['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':state['cooldown_until_epoch'],'reason':'claim_recheck_provider_failure'})
  row.update(model_calls=state['model_requests_reserved'],originals_unchanged=unchanged,review_receipts=len(list(calls.glob('*.receipt.json'))),completed_at=utcnow());atomic_json(rp,row)
 return row
