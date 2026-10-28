"""Queue ownership is independent from research/publication readiness.
Exactly one distinct unfinished queue topic per family; assignments survive runs.
"""
import contextlib,fcntl,hashlib,os,tempfile
from pathlib import Path
from .queue import DATA,OUT,items,load_json,atomic_json,safe_id,utcnow
from .parallel_capacity import MAX_FAMILIES
FAMILIES=tuple(f'family-{i:02d}' for i in range(1,MAX_FAMILIES+1))

def published(ident,out):
 p=out/'new'/ident/'wordpress-receipt.json'
 return p.exists() and load_json(p).get('public_verified') is True

def family_complete(ident,data,out):
 if not published(ident,out):return False
 cfg=load_json(data/'config.json')
 if not cfg.get('multilingual',{}).get('enabled'):return True
 from .multilingual import LANGUAGES
 for lang in LANGUAGES:
  p=out/'new'/ident/'translations'/(lang+'.wordpress.json')
  if not p.exists() or load_json(p).get('public_verified') is not True:return False
 return True

def readiness(topic,data=DATA,out=OUT):
 """Diagnostic only: NEVER removes a topic from family ownership."""
 from .research import QUALITATIVE
 ident=topic['id'];cfg=load_json(data/'config.json')
 if ident in cfg.get('publication_holds',{}):return 'publication_hold'
 if published(ident,out):return 'translations_pending'
 bp=data/'briefs'/f'{ident}.json'
 if bp.exists():
  from .pipeline import check_brief
  try:
   b=load_json(bp);check_brief(topic,b)
   return 'ready_for_drafting' if b.get('publish_authorized') is True else 'brief_needs_review'
  except (ValueError,KeyError,TypeError):return 'brief_needs_review'
 rp=out/'research'/f'{ident}.json';prior=load_json(rp) if rp.exists() else {}
 if prior.get('attempts',0)>=2:return 'research_budget_exhausted'
 if prior.get('status')=='needs_review':
  route={'review_origin_needs_existing_content_audit':'existing_content_audit_required','quantitative_or_specialist_scope':'scope_review_required','insufficient_fetchable_institutional_sources':'source_discovery_required','source_scout_scope_requires_review':'scope_review_required'}
  return route.get(prior.get('reason'),'research_needs_review')
 if topic.get('overlap_review_required') and topic.get('related_existing_ids'):return 'existing_content_audit_required'
 if topic.get('intent') not in QUALITATIVE:return 'scope_review_required'
 cp=data/'research-source-catalog.json';c=load_json(cp) if cp.exists() else {'entries':[]}
 if not any(topic['crop'] in e['crops'] and topic['intent'] in e['intents'] for e in c['entries']):return 'source_discovery_required'
 return 'ready_for_research'

@contextlib.contextmanager
def allocation_lock(out):
 name=hashlib.sha256(str(Path(out).resolve()).encode()).hexdigest()[:24]
 with open(Path(tempfile.gettempdir())/('afp-family-'+name+'.lock'),'a') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)

def allocate(data=DATA,out=OUT,*,allow_deferral=False):
 path=out/'parallel/families/assignments.json'
 with allocation_lock(out):
  queue=items('new',data);by_id={t['id']:t for t in queue}
  state=load_json(path) if path.exists() else {'version':1,'queue':'new','allocation_order':'immutable_manifest_order','families':[],'history':[],'publication_authorized_by_assignment':False}
  old=state.get('families',[])
  if not isinstance(old,list) or len({r['family_id'] for r in old})!=len(old) or len({r['topic_id'] for r in old})!=len(old):raise ValueError('Duplicate family or topic ownership; manual reconciliation required')
  if any(r['family_id'] not in FAMILIES or r['topic_id'] not in by_id for r in old):raise ValueError('Assignment not in immutable queue')
  from .research_backlog import deferral,validate_backlog
  backlog=validate_backlog(state.get('research_backlog',{}),by_id)
  from .queue_exceptions import deferral as exception_deferral,validate_backlog as validate_exceptions
  exceptions=validate_exceptions(state.get('exception_backlog',{}),by_id)
  if set(exceptions)&(set(backlog)|{r['topic_id'] for r in old}):raise ValueError('Topic both active/research-deferred and exception-queued')
  if set(backlog)&{r['topic_id'] for r in old}:raise ValueError('Topic both active and deferred; explicit reconciliation required')
  kept={};history=list(state.get('history',[]))
  for row in old:
   from .language_review_queue import released
   complete=family_complete(row['topic_id'],data,out)
   from .staged_rollout import protects_handoff
   handed_off=released(row['topic_id'],data,out) and not protects_handoff(row['topic_id'],data,out)
   if complete or handed_off:history.append(dict(row,completed_at=utcnow(),completion='verified_source_and_required_translations' if complete else 'verified_source_languages_handed_to_review_queue'))
   else:
    deferred=deferral(by_id[row['topic_id']],data,out) if allow_deferral else None
    if deferred is not None:
     backlog[row['topic_id']]=dict(deferred,previous_family_id=row['family_id'])
     history.append(dict(row,completed_at=deferred['deferred_at'],completion='deferred_to_research_backlog',reason=deferred['reason']))
    else:
     terminal=exception_deferral(by_id[row['topic_id']],data,out) if allow_deferral else None
     if terminal is None:kept[row['family_id']]=row
     else:
      exceptions[row['topic_id']]=dict(terminal,previous_family_id=row['family_id'])
      history.append(dict(row,completed_at=terminal['deferred_at'],completion='deferred_to_exception_backlog',reason=terminal['reason']))
  used={r['topic_id'] for r in kept.values()};held=load_json(data/'config.json').get('publication_holds',{})
  # Completed, held, already-owned and explicitly deferred topics are unavailable.
  # New topics are not prefiltered by source readiness; only diagnosed deferrals free a family.
  candidates=(t for t in queue if t['id'] not in used and t['id'] not in held and t['id'] not in backlog and t['id'] not in exceptions and not published(t['id'],out))
  rows=[]
  for family in FAMILIES:
   row=kept.get(family)
   if row is None:
    topic=next(candidates,None)
    if topic is None:continue
    used.add(topic['id']);row={'family_id':family,'topic_id':topic['id'],'title':topic['title'],'assigned_at':utcnow(),'assignment_status':'assigned'}
   topic=by_id[row['topic_id']];safe_id(row['topic_id'])
   row=dict(row,title=topic['title'],work_stage=readiness(topic,data,out),publication_authorized_by_assignment=False)
   rows.append(row)
  state=dict(state,families=rows,history=history,research_backlog=backlog,research_backlog_count=len(backlog),exception_backlog=exceptions,exception_backlog_count=len(exceptions),assigned_count=len(rows),target_families=MAX_FAMILIES,unique_topic_count=len({r['topic_id'] for r in rows}),model_calls=0,wordpress_write_calls=0)
  if not path.exists() or load_json(path)!=state:atomic_json(path,state)
  return state

def assigned_topics(state,data=DATA):
 by_id={t['id']:t for t in items('new',data)}
 return [dict(by_id[r['topic_id']],family_id=r['family_id'],assigned_work_stage=r['work_stage']) for r in state['families']]
