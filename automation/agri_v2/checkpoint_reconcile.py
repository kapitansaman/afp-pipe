"""Explicit read-only remote reconciliation of a narrowly known pre-publication failure.
Never clears unknown worker/stage outcomes, changes reports/attempts, or claims success.
The proof and closing fence are committed together by scoped checkpoint persistence.
"""
import hashlib,subprocess
from urllib.parse import quote
from .queue import load_json,atomic_json,utcnow,get_topic
from .execution_recovery import FLIGHT,VERSION,REPO,BRANCH,fingerprint,ReconciliationRequired

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def reconcile(env,data,out,wp=None,durable_check=None):
 if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch':raise ReconciliationRequired('Manual checkpoint reconciliation required')
 root=data.parent.parent;fp=data/'status/lifecycle-flight.json';row=load_json(fp)
 if row.get('version')!=1 or row.get('policy')!=VERSION or row.get('repository')!=REPO or row.get('branch')!=BRANCH or row.get('status')!='in_flight':raise ReconciliationRequired('Exact in-flight intent required')
 run=row['run_id']
 if not isinstance(run,str) or not run.isdigit() or run==env.get('GITHUB_RUN_ID'):raise ReconciliationRequired('Distinct original numeric run required')
 if load_json(out/'parallel/lifecycle/runs'/run/'report.json').get('source_search',{}).get('unknown_requests',0):raise ReconciliationRequired('Unknown original search outcome must not replay')
 ap=out/'parallel/recovery/admissions'/(run+'.json');admission=load_json(ap);rp=out/'parallel/lifecycle/runs'/run/'report.json';report=load_json(rp)
 ids=[m['topic_id']for m in row['topics']];results=report.get('results',[]);pubs=report.get('publication_results',[])
 if admission.get('run_id')!=run or admission.get('reserved_row_sha256')!=fingerprint(row) or admission.get('intent')!=row:raise ReconciliationRequired('Intent proof changed')
 if report.get('run_id')!=run or report.get('status')!='completed_with_failures' or report.get('coordinator_failure',{}).get('kind')!='unexpected' or len(set(ids))!=len(ids) or not ids:raise ReconciliationRequired('Known failed coordinator checkpoint required')
 if len(results)!=len(ids) or {r.get('topic_id')for r in results}!=set(ids) or any(r.get('checkpoint_merged')is not True or r.get('status')!='publication_ready' for r in results):raise ReconciliationRequired('All original workers must be merged and publication-ready')
 if len(pubs)!=len(ids) or {r.get('topic_id')for r in pubs}!=set(ids) or any(r.get('status')!='stage_failed' or r.get('failure',{}).get('kind')!='validation' for r in pubs) or report.get('published_posts')!=0:raise ReconciliationRequired('Only known pre-publication validation failures can be reconciled here')
 paths=[fp,ap,rp];topics=[]
 for ident in ids:
  topic=get_topic('new',ident,data);folder=out/'new'/ident;topics.append(topic)
  if (folder/'wordpress-receipt.json').exists():raise ReconciliationRequired('Existing publication requires separate receipt reconciliation')
  states=list((folder/'lifecycle').glob('*/state.json'))
  if not states or any(load_json(p).get('status')in ('reserved','reconciliation_required')for p in states):raise ReconciliationRequired('Unknown original stage outcome must not replay')
  ps=load_json(folder/'lifecycle/publish/state.json')
  if ps.get('status')!='failed' or ps.get('last_run_id')!=run or ps.get('failure',{}).get('kind')!='validation':raise ReconciliationRequired('Original publication failure changed')
  for p in (folder/'review-queue').glob('*.json'):
   if load_json(p).get('status')in ('reserved','reconciliation_required','publication_reconciliation_required'):raise ReconciliationRequired('Unknown language outcome must not replay')
  paths.extend(p for p in folder.rglob('*')if p.is_file());paths.append(data/'briefs'/(ident+'.json'))
 # All evidence must already be in the checked-out durable Git tree, not just local files.
 if durable_check is None:
  def durable_check(paths):
   for p in paths:
    rel=str(p.resolve().relative_to(root.resolve()));r=subprocess.run(['git','show','HEAD:'+rel],cwd=root,capture_output=True,timeout=30)
    if r.returncode or r.stdout!=p.read_bytes():raise ReconciliationRequired('Evidence is not durably committed')
 durable_check(paths)
 if wp is None:
  from .wordpress import WordPress
  wp=WordPress()
 wp.preflight();absence=[]
 for topic in topics:
  brief=load_json(data/'briefs'/(topic['id']+'.json'));slug=brief['slug']
  for status in ('publish','draft','pending','future','private'):
   found,_=wp.call('posts?slug='+quote(slug)+'&status='+status+'&context=edit')
   if not isinstance(found,list) or found:raise ReconciliationRequired('Remote publication is present or ambiguous; do not replay')
  absence.append({'topic_id':topic['id'],'slug':slug,'all_statuses_absent':True})
 proof={'version':1,'original_run_id':run,'manual_run_id':env['GITHUB_RUN_ID'],'checked_at':utcnow(),'original_report_sha256':sha(rp),'evidence_sha256':{str(p.relative_to(root)):sha(p)for p in sorted(set(paths))},'remote_slug_absence':absence,'model_calls':0,'post_mutations':0,'attempts_reset':False,'publication_success_claimed':False,'original_coordinator_failure_preserved':True}
 proof_sha=fingerprint(proof);atomic_json(out/'parallel/recovery/reconciliations'/(run+'.json'),proof)
 closed=dict(row,status='checkpointed',checkpointed_at=utcnow(),all_selected_workers_merged=True,checkpoint_report_sha256=sha(rp),checkpoint_digest=proof_sha,manual_reconciliation_proof_sha256=proof_sha)
 atomic_json(fp,closed)
 return {'status':'known_failed_checkpoint_reconciled','original_run_id':run,'proof_sha256':proof_sha,'model_calls':0,'post_mutations':0,'attempts_reset':False,'stage_limit_changed':False}
