"""Read-only due-work projection. Ownership, attempts and unknown outcomes never change."""
import time
from .queue import load_json,atomic_json,utcnow
from .foundation_policy import enabled

def decision(topic,data,out,now=None):
 from .family_lifecycle import next_stage,state,settings
 now=time.time() if now is None else now;folder=out/'new'/topic['id'];stage,reason=next_stage(topic,data,out)
 def result(due,why=None,at=None):return {'topic_id':topic['id'],'family_id':topic.get('family_id'),'stage':stage,'due':due,'reason':why,'next_attempt_epoch':at,'publication_authorized':False}
 if stage in ('blocked','complete'):return result(False,reason or stage)
 # Any unconfirmed request relevant to this topic needs explicit reconciliation.
 for p in sorted((folder/'lifecycle').glob('*/state.json')):
  row=load_json(p)
  if row.get('status') in ('reserved','reconciliation_required'):return result(False,'request_outcome_requires_reconciliation')
 if stage=='publish' and (folder/'wordpress-receipt.json').exists() and load_json(folder/'wordpress-receipt.json').get('public_verified')is True:
  from .language_review_queue import due,publication_due
  entries=[load_json(p) for p in (folder/'review-queue').glob('*.json')]
  if not any(due(r) or publication_due(r) for r in entries):return result(False,'translation_review_backoff')
  from .family_capability_refresh import active_hold
  return result(not active_hold(out,'text'),'provider_cooldown' if active_hold(out,'text') else None)
 if stage=='images':
  from .image_workflow import exhausted,approved_roles
  article=load_json(folder/'article.json')
  if not approved_roles(folder,topic,article) and all(exhausted(folder,k) for k in (1,2)):return result(False,'image_budgets_exhausted')
 else:
  row=state(folder,stage);limit=1 if stage in ('research_discover','research_refetch','article_quality_repair','article_quality_recheck') else settings(data)['max_attempts_per_stage']
  if row['attempts']>=limit:return result(False,'stage_budget_exhausted')
 if stage=='research_refetch':
  ev=folder/'lifecycle-evidence';p=ev/'real-search/progress.json'
  if p.exists():
   from .source_repair_resume import read_progress
   from .model_source_repair import binding,PLAN
   plan=load_json(ev/PLAN)['plan'];progress=read_progress(p,topic,binding(topic,ev),plan)
   pending=[r for r in progress['urls'].values() if r['status']=='temporary']
   if pending:
    due=[r.get('next_attempt_epoch',0) for r in pending if r['transport_attempts']<3]
    if not due:return result(False,'source_retrieval_requires_review')
    if min(due)>now:return result(False,'source_fetch_backoff',min(due))
 # Respect local provider holds before allocating a subprocess or paid budget.
 from .family_capability_refresh import active_hold
 kind='image' if stage.startswith('image-') else 'text'
 if stage=='images' and any(active_hold(out,k) for k in ('text','image')):return result(False,'provider_cooldown')
 if stage not in ('research_sources','research_validate_saved','existing_content_audit_finalize') and active_hold(out,kind):return result(False,'provider_cooldown')
 return result(True)

def project(topics,data,out,now=None):
 rows=[];due=[]
 for topic in topics:
  try:r=decision(topic,data,out,now)
  except (ValueError,KeyError,TypeError,OSError,AttributeError):r={'topic_id':topic['id'],'family_id':topic.get('family_id'),'stage':None,'due':False,'reason':'admission_evidence_invalid','next_attempt_epoch':None,'publication_authorized':False}
  rows.append(r)
  if r['due']:due.append(topic)
 image_rows=[r for r in rows if r['stage']=='images' or str(r['stage']).startswith(('image-','vision-'))]
 atomic_json(out/'parallel/families/due-work.json',{'version':1,'checked_at':utcnow(),'families':rows,'due_count':len(due),'model_calls':0,'wordpress_write_calls':0,'attempts_reset':False})
 atomic_json(out/'parallel/families/image-work.json',{'version':1,'checked_at':utcnow(),'families':image_rows,'approved_text_regeneration_authorized':False,'attempts_reset':False})
 return due,rows
