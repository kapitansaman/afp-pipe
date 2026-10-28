"""Read-only deferral decisions. Never resets attempts or promotes rejected work.
The allocation writer commits backlog+ownership in ONE atomic state document.
"""
import hashlib
from .queue import load_json,utcnow
from .source_policy import VERSION as SOURCE_POLICY_VERSION
VERSION=1
# These describe exhausted evidence PREPARATION, not independent scientific review.
EVIDENCE_REPAIR_CODES={'scoped_four_to_twelve_facts_required','saved_evidence_declares_insufficient_scope',
 'two_independent_publications_required','university_or_two_independent_publications_required'}

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

def source_gap(ev,topic_id):
 path=ev/'source-discovery-report.json'
 if not path.exists():return None
 row=load_json(path)
 if row.get('topic_id')!=topic_id or row.get('source_policy_version')!=SOURCE_POLICY_VERSION or row.get('bounded_discovery_completed') is not True:return None
 if row.get('blocking_kind') not in {'insufficient_verified_source_coverage','discovery_catalog_empty'}:return None
 if row.get('temporary_source_failure') is not False:return None
 if not isinstance(row.get('requested'),int) or not 0<=row['requested']<=12:return None
 if row.get('source_sufficiency',{}).get('satisfied') is not False:return None
 return row

def deferral(topic,data,out):
 ident=topic['id'];folder=out/'new'/ident;ev=folder/'lifecycle-evidence'
 cfg=load_json(data/'config.json')
 # Never release accepted/drafted/published work, or override an explicit hold.
 if ident in cfg.get('publication_holds',{}) or (data/'briefs'/(ident+'.json')).exists() or (folder/'article.json').exists() or (folder/'wordpress-receipt.json').exists():return None
 # A rejected scientific review/overlap is not a source-count problem.
 if any((ev/name).exists() for name in ('review-raw.json','overlap-raw.json','overlap.json')):return None
 for stage in ('research_review','existing_content_audit'):
  proof=folder/'lifecycle'/stage/'state.json'
  if proof.exists() and load_json(proof).get('attempts',0)>0:return None
 from .model_source_repair import exhausted_coverage
 coverage=exhausted_coverage(topic,folder,data)
 if coverage is not None:
  p=folder/'lifecycle/research_refetch/state.json';s=load_json(p)
  row=record(topic,'bounded_source_coverage_exhausted','research_refetch',s,ev,p,'bounded_search_coverage_incomplete')
  row['evidence_fingerprints']['model-source-refetch.json']=fingerprint(ev/'model-source-refetch.json')
  return row
 p=folder/'lifecycle/research_sources/state.json'
 s=load_json(p) if p.exists() else {}
 gap=source_gap(ev,ident)
 if gap is not None and s.get('status')=='failed' and s.get('attempts',0)>0:
  from .model_source_repair import discovery_pending,initial_source_gap
  if initial_source_gap(topic,folder) and discovery_pending(topic,folder,data):return None
  return record(topic,'additional_source_discovery_required','research_sources',s,ev,p,gap['blocking_kind'])
 policy=data/'family-lifecycle-policy.json'
 limit=load_json(policy).get('max_attempts_per_stage') if policy.exists() else None
 if limit!=3:return None
 for stage in ('research_validate_saved','research_extract'):
  p=folder/'lifecycle'/stage/'state.json'
  if not p.exists():continue
  s=load_json(p);reason=s.get('failure',{}).get('category')
  if s.get('status')=='failed' and s.get('attempts',0)>=limit and reason in EVIDENCE_REPAIR_CODES:
   # Retain real inputs; a missing/empty provider response alone never qualifies.
   if not (ev/'sources.json').exists() or not (ev/'candidate-raw.json').exists():continue
   return record(topic,'evidence_preparation_exhausted',stage,s,ev,p,reason)
 return None

def record(topic,kind,stage,state,ev,state_path,reason):
 return {'topic_id':topic['id'],'title':topic['title'],'status':'awaiting_research_repair','kind':kind,'stage':stage,'reason':reason,
  'attempts_preserved':state['attempts'],'last_run_id':state.get('last_run_id'),'deferred_at':utcnow(),
  'evidence_fingerprints':{p.name:fingerprint(p) for p in [ev/'source-discovery-report.json',ev/'sources.json',ev/'candidate-raw.json',state_path] if p.exists()},
  'publication_authorized':False,'automatic_retry_authorized':False,
  'return_requirements':['new_verified_relevant_evidence','explicit_valid_attempt_authorization','all_original_quality_and_overlap_gates'],
  'prior_attempts_reset':False}

def validate_backlog(rows,by_id):
 if not isinstance(rows,dict):raise ValueError('Invalid research backlog')
 for ident,row in rows.items():
  if ident not in by_id or not isinstance(row,dict) or row.get('topic_id')!=ident or row.get('status')!='awaiting_research_repair' or row.get('publication_authorized') is not False or row.get('automatic_retry_authorized') is not False:raise ValueError('Invalid research backlog entry; reconcile explicitly')
 return rows
