"""Bounded regional evidence continuation for immutable linguistically approved output.
Not another translation attempt, never resets old counters or replays unknown work.
Shares the existing <=12 model-call/item and <=8 model-call/run outer budgets.
"""
import datetime
from .queue import load_json,atomic_json,utcnow,get_topic
from .pipeline import digest
MAX_ATTEMPTS=2

def path(folder,lang):return folder/'regional-research'/lang/'continuation.json'

def confirmed(root):
 rows=list(root.glob('*.receipt.json'))
 for p in rows:
  row=load_json(p);raw=p.with_name(p.name.replace('.receipt.json','.raw.json'))
  if row.get('status')!='received' or not raw.exists() or row.get('raw_sha256')!=digest(load_json(raw)):return False
 return bool(rows)

def eligible(row,folder):
 from .language_review_queue import approved
 article=load_json(folder/'article.json')
 if row.get('pending_issues') or not approved(folder,article,row['language']):return False
 if row.get('status')=='approved':return True
 if row.get('status')!='needs_attention' or row.get('last_failure',{}).get('kind')!='admission_deferred':return False
 # Narrow migration of a confirmed research-only admission failure, not a
 # negative linguistic verdict or unknown provider/search outcome.
 root=folder/'review-queue/attempts'/row['language']/str(row['attempts'])
 receipts=list(root.glob('*.receipt.json'))
 if not receipts or not all(p.name.startswith('regional-') for p in receipts) or not confirmed(root):return False
 local=folder/'regional-research'/row['language']/'local'
 try:
  queries=load_json(local/'search-plan.json')['queries']
  return len(queries)==2 and all(load_json(local/('search-'+str(i)+'.json')).get('query_sha256')==digest(q) for i,q in enumerate(queries))
 except (FileNotFoundError,KeyError,TypeError,ValueError):return False

def due(folder,lang):
 p=path(folder,lang)
 if not p.exists():return True
 row=load_json(p)
 if row.get('status')=='reserved':return True # reconcile locally, no new request
 if row.get('status')!='waiting' or row.get('attempts',0)>=MAX_ATTEMPTS:return False
 ts=row.get('next_attempt_at')
 return not ts or datetime.datetime.fromisoformat(ts.replace('Z','+00:00'))<=datetime.datetime.now(datetime.timezone.utc)

def run(p,client,data):
 from . import language_review_queue as queue
 from .regional_sources import local_research,require_local,profile
 from .failure_diagnostics import failure_details
 from .execution_recovery import uncertain_outcome
 row=load_json(p);folder=p.parent.parent;lang=row['language'];article=load_json(folder/'article.json')
 if not eligible(row,folder):raise ValueError('regional_continuation_requires_unchanged_linguistic_approval')
 queue.source_checked(row,article,folder,data)
 topic=get_topic('new',row['topic_id'],data);brief=load_json(data/'briefs'/(topic['id']+'.json'))
 binding={'regional_profile_sha256':digest(profile(lang)),'topic_id':topic['id'],'language':lang,'article_sha256':digest(article),'brief_sha256':digest(brief),'translation_sha256':digest(load_json(queue.target(folder,lang))),'fidelity_sha256':digest(load_json(queue.proof_path(folder,lang)))}
 pp=path(folder,lang);state=load_json(pp) if pp.exists() else {'version':1,'binding':binding,'attempts':0,'model_calls_spent':0,'status':'waiting','history':[]}
 if state.get('version')!=1 or state.get('binding')!=binding:raise ValueError('regional_continuation_binding_changed')
 if state['status']=='reserved':
  # Even an old positive fidelity verdict cannot resolve unknown research.
  state.update(status='reconciliation_required',next_attempt_at=None);atomic_json(pp,state)
  return {'topic_id':topic['id'],'language':lang,'status':state['status'],'model_calls':0}
 if not due(folder,lang):return {'status':'regional_not_due','model_calls':0}
 remaining=queue.policy(data)['max_model_calls_per_item']-row['model_calls_spent'];limit=min(4,remaining)
 if limit<=0:state.update(status='needs_attention',next_attempt_at=None);atomic_json(pp,state);return {'status':'regional_budget_exhausted','model_calls':0}
 n=state['attempts']+1;root=folder/'regional-research'/lang/'continuation-attempts'/str(n)
 if root.exists():raise ValueError('regional_continuation_attempt_already_exists')
 state.update(status='reserved',attempts=n,started_at=utcnow());state['history'].append({'event':'reserved','attempt':n,'max_calls':limit,'at':utcnow()});atomic_json(pp,state)
 try:
  local_research(topic,article,brief,lang,client,data,folder.parent.parent,folder,root,limit)
  require_local(article,brief,lang,data,folder)
  # No translator, editor or fidelity reviewer was run; verify original proof again.
  if not queue.approved(folder,article,lang):raise ValueError('regional_continuation_linguistic_output_changed')
  state.update(status='approved',next_attempt_at=None)
 except Exception as exc:
  state['last_failure']=failure_details(exc)
  if uncertain_outcome(exc):state.update(status='reconciliation_required',next_attempt_at=None)
  else:state.update(status='needs_attention' if n>=MAX_ATTEMPTS else 'waiting',next_attempt_at=None if n>=MAX_ATTEMPTS else (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=6)).isoformat())
 spent=len(list(root.glob('*.receipt.json')));row['model_calls_spent']+=spent;state['model_calls_spent']+=spent
 if row['model_calls_spent']>queue.policy(data)['max_model_calls_per_item']:raise ValueError('regional_continuation_exceeded_existing_total_budget')
 state['history'].append({'event':'finished','attempt':n,'reserved_model_calls':spent,'status':state['status'],'at':utcnow()});atomic_json(pp,state)
 row['regional_research_status']=state['status'];row['history'].append({'event':'regional_research_continuation','attempt':n,'model_calls':spent,'status':state['status'],'semantic_attempts_unchanged':row['attempts'],'at':utcnow()})
 if state['status']=='approved':row.update(status='approved',next_attempt_at=None,reason='unchanged_fidelity_and_independent_regional_evidence_verified')
 atomic_json(p,row)
 return {'topic_id':topic['id'],'language':lang,'status':'approved' if state['status']=='approved' else 'regional_'+state['status'],'model_calls':spent,'semantic_attempts_unchanged':row['attempts']}
