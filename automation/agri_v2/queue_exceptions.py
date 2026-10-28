"""Terminal unpublished checkpoints leave slots, not their quality/budget history.
No inferred acceptance, automatic replay, attempt reset or publication authority.
"""
import hashlib,json,re
from .queue import load_json,atomic_json,utcnow
VERSION='finite-terminal-exceptions-v1'
POLICY={'version':1,'policy':VERSION,'enabled':True,'require_terminal_checkpoint':True,'preserve_all_artifacts':True,'reset_attempts':False,'automatic_retry_authorized':False,'publication_authorized':False,'respect_holds_and_publication_receipts':True}
MARKER='queue-terminal-checkpoint.json'
STAGES={'research_sources','research_extract','research_validate_saved','research_review','existing_content_audit','text','article_evidence_review','article_quality_repair','article_quality_recheck'}

def enabled(data):
 p=data/'queue-exception-policy.json'
 if not p.exists():return False
 value=load_json(p)
 if value==dict(POLICY,enabled=False):return False
 if value!=POLICY:raise ValueError('Exact finite exception policy required')
 return True

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def protected(topic,data,out):
 folder=out/'new'/topic['id']
 return topic['id'] in load_json(data/'config.json').get('publication_holds',{}) or (folder/'wordpress-receipt.json').exists() or any((folder/'translations').glob('*.wordpress.json')) or (folder/'wordpress-draft-payload.json').exists() or (folder/'lifecycle/publication/state.json').exists() or (folder/'lifecycle/publish/state.json').exists()

def bindings(topic,data,out):
 folder=out/'new'/topic['id']
 stable={k:v for k,v in topic.items() if k not in ('family_id','assigned_work_stage')}
 return {'topic_sha256':hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
  'topic_files':{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name!=MARKER},
  'legacy_research_sha256':sha(out/'research'/(topic['id']+'.json')),
  'brief_sha256':sha(data/'briefs'/(topic['id']+'.json')),
  'policies':{name:sha(data/name) for name in ('config.json','family-lifecycle-policy.json','queue-exception-policy.json','image-repair-policy.json','quality-index-policy.json','language-review-policy.json','research-source-catalog.json')}}

def terminal_proof(topic,result,data,out):
 """Requires coordinator-observed terminal outcome AND matching real counters."""
 from .family_lifecycle import state
 if result.get('topic_id')!=topic['id'] or protected(topic,data,out):return None
 folder=out/'new'/topic['id'];status=result.get('status');stage=result.get('stage');reason=result.get('reason')
 if status in ('stage_failed','stage_budget_exhausted') and isinstance(stage,str) and (stage in STAGES or re.fullmatch(r'existing_content_audit-\d{3}',stage)):
  limit=load_json(data/'family-lifecycle-policy.json').get('max_attempts_per_stage')
  if limit!=3:return None
  if stage in ('article_quality_repair','article_quality_recheck'):limit=1
  row=state(folder,stage);attempts=row.get('attempts')
  if type(attempts)is not int or attempts<limit or row.get('status')!='failed':return None
  return {'kind':'stage_budget_exhausted','stage':stage,'attempts_preserved':attempts,'attempt_limit':limit,'reason':row.get('failure',{}).get('category') or 'stage_budget_exhausted','last_run_id':row.get('last_run_id')}
 if status=='blocked' and reason in ('legacy_research_budget_exhausted','legacy_generation_budget_exhausted'):
  path=out/'research'/(topic['id']+'.json') if reason=='legacy_research_budget_exhausted' else folder/'cycle-attempts.json'
  row=load_json(path) if path.exists() else {};attempts=row.get('attempts')
  if type(attempts)is not int or attempts<2:return None
  return {'kind':'legacy_budget_exhausted','stage':'legacy_research' if reason=='legacy_research_budget_exhausted' else 'legacy_generation','attempts_preserved':attempts,'attempt_limit':2,'reason':reason,'last_run_id':row.get('last_run_id')}
 if status=='images_need_attention' or (status=='blocked' and reason=='images_need_attention'):
  from . import image_workflow as image
  if not image.enabled(data) or not (folder/'article.json').exists():return None
  article=load_json(folder/'article.json')
  if image.approved_roles(folder,topic,article) or not all(image.exhausted(folder,k) for k in (1,2)):return None
  counts={str(k):{s:state(folder,s+'-'+str(k))['attempts'] for s in ('image','vision')} for k in (1,2)}
  return {'kind':'image_budgets_exhausted','stage':'images','attempts_preserved':counts,'attempt_limit':image.MAX_ATTEMPTS,'reason':'images_need_attention','last_run_id':None}
 if status=='blocked' and reason=='article_quality_review_queue':
  from . import quality_index as quality
  brief=data/'briefs'/(topic['id']+'.json');article=folder/'article.json'
  if not brief.exists() or not article.exists():return None
  if quality.next_stage(folder,load_json(article),load_json(brief),data)!=('blocked',reason):return None
  counts={s:state(folder,s)['attempts'] for s in ('article_quality_repair','article_quality_recheck')}
  if max(counts.values())<1:return None
  return {'kind':'quality_budget_exhausted','stage':'article_quality','attempts_preserved':counts,'attempt_limit':1,'reason':reason,'last_run_id':None}
 return None

def note_terminal(topic,result,data,out):
 if not enabled(data):return None
 proof=terminal_proof(topic,result,data,out)
 if proof is None:return None
 outcome={k:result[k] for k in ('topic_id','status','stage','reason') if k in result}
 row={'version':1,'policy':VERSION,'topic_id':topic['id'],'title':topic['title'],'status':'terminal_unpublished_checkpoint','outcome':outcome,'proof':proof,'bindings':bindings(topic,data,out),'recorded_at':utcnow(),'publication_authorized':False,'automatic_retry_authorized':False,'prior_attempts_reset':False}
 atomic_json(out/'new'/topic['id']/MARKER,row);return row

def deferral(topic,data,out):
 if not enabled(data) or protected(topic,data,out):return None
 p=out/'new'/topic['id']/MARKER
 if not p.exists():return None
 row=load_json(p)
 if row.get('version')!=1 or row.get('policy')!=VERSION or row.get('topic_id')!=topic['id'] or row.get('status')!='terminal_unpublished_checkpoint' or any(row.get(k)is not False for k in ('publication_authorized','automatic_retry_authorized','prior_attempts_reset')):raise ValueError('Invalid terminal checkpoint')
 proof=terminal_proof(topic,row.get('outcome',{}),data,out)
 if proof is None or proof!=row.get('proof') or bindings(topic,data,out)!=row.get('bindings'):return None
 return dict(proof,topic_id=topic['id'],title=topic['title'],status='awaiting_exception_review',policy=VERSION,deferred_at=utcnow(),terminal_checkpoint_sha256=sha(p),bindings=row['bindings'],publication_authorized=False,automatic_retry_authorized=False,prior_attempts_reset=False,return_requirements=['explicit_review_and_reentry_authorization','preserved_attempts_or_separately_authorized_budget','all_original_research_quality_overlap_and_publication_gates'])

def validate_backlog(rows,by_id=None):
 if not isinstance(rows,dict):raise ValueError('Invalid exception backlog')
 for ident,row in rows.items():
  if (by_id is not None and ident not in by_id) or not isinstance(row,dict) or row.get('topic_id')!=ident or row.get('status')!='awaiting_exception_review' or row.get('policy')!=VERSION or any(row.get(k)is not False for k in ('publication_authorized','automatic_retry_authorized','prior_attempts_reset')):raise ValueError('Invalid exception backlog entry')
 return rows

def queued(ident,out):
 p=out/'parallel/families/assignments.json'
 if not p.exists():return False
 rows=load_json(p).get('exception_backlog',{});validate_backlog(rows)
 return ident in rows
