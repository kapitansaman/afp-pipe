"""Coordinator for 20 isolated research workers and one output writer.
Legacy rollout modes remain research-only; advance runs gated resumable families.
"""
import argparse,concurrent.futures,hashlib,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
from .queue import DATA,OUT,ROOT,items,load_json,atomic_json,utcnow,age_hours,safe_id
from .parallel_control import policy,reserve
from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing
from .parallel_capacity import MAX_FAMILIES
# Historical first-research ledger stays consumed; expansion does not replay it.
ID='parallel-15-research-rollout-v1'

def eligible_topics(inventory,data=DATA,out=OUT,limit=MAX_FAMILIES):
 # Compatibility name: these are now ASSIGNED topics, not source-readiness-filtered topics.
 from .family_scheduler import allocate,assigned_topics
 state=allocate(data,out)
 return assigned_topics(state,data)[:limit],{}

def atomic_copy(source,destination):
 """A failed copy cannot truncate a previously valid checkpoint file."""
 destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
 fd,name=tempfile.mkstemp(prefix='.checkpoint-',dir=destination.parent);os.close(fd)
 try:shutil.copy2(source,name);os.replace(name,destination)
 finally:
  if os.path.exists(name):os.unlink(name)
 return str(destination)

def checkpoint_retirements(source,destination):
 """Only explicit, byte-identical stage archives retire an active output.
 Missing files alone are not deletion authority: a timed-out worker may be partial.
 Validate all conflicts before copying any worker state or advancing counters.
 """
 from .family_lifecycle import stage_outputs
 retired=[]
 for stage_folder in sorted((source/'lifecycle').glob('*')):
  if not stage_folder.is_dir():continue
  stage=stage_folder.name;state=stage_folder/'state.json';old=destination/'lifecycle'/stage/'state.json'
  if state.exists() and old.exists():
   attempts=load_json(state).get('attempts',0);prior=load_json(old).get('attempts',0)
   if type(attempts)is not int or type(prior)is not int or attempts<prior:raise ValueError('Stage attempts decreased; never reset during merge')
  for active in stage_outputs(source,stage):
   target=destination/active.relative_to(source)
   if active.exists() or not target.exists():continue
   archives=list((stage_folder/'rejected').glob('*/'+active.name))+list((stage_folder/'deferred').glob('*/'+active.name))
   if not archives:continue
   expected=hashlib.sha256(target.read_bytes()).hexdigest()
   matching=[a for a in archives if a.is_file() and hashlib.sha256(a.read_bytes()).hexdigest()==expected]
   if not matching:raise ValueError('Archived output conflict; coordinator changed since worker copy')
   retired.append((target,destination/matching[0].relative_to(source),expected))
 from .model_source_repair import checkpoint_retirements as source_retirements
 return retired+source_retirements(source,destination)

def merge_worker(ident,worker_data,worker_out,data=DATA,out=OUT):
 safe_id(ident)
 bp=worker_data/'briefs'/f'{ident}.json';dest_brief=data/'briefs'/bp.name
 if bp.exists() and dest_brief.exists() and dest_brief.read_bytes()!=bp.read_bytes():raise ValueError('Existing brief changed; never overwrite')
 retired=checkpoint_retirements(worker_out/'new'/ident,out/'new'/ident)
 for rel in ['research/'+ident+'.json','research-evidence/'+ident,'new/'+ident]:
  source=worker_out/rel;dest=out/rel
  if source.is_dir():shutil.copytree(source,dest,dirs_exist_ok=True,copy_function=atomic_copy)
  elif source.exists():atomic_copy(source,dest)
 # Persist archived bytes before removing a retired active copy. Repeating a merge
 # is safe even if interrupted between the copy and this reconciliation.
 for active,archived,expected in retired:
  if not archived.is_file() or hashlib.sha256(archived.read_bytes()).hexdigest()!=expected:raise ValueError('Archived output not durably copied')
  if active.exists():
   if hashlib.sha256(active.read_bytes()).hexdigest()!=expected:raise ValueError('Archived output conflict during merge')
   active.unlink()
 if bp.exists():atomic_copy(bp,dest_brief)
 from .source_loading import valid_document
 from .research import source_host
 for source in (worker_out/'source-cache').glob('*.json'):
  document=load_json(source);requested=document.get('requested_url',document.get('url',''))
  # Cache is optional: reject an invalid/stale cache entry, not the family's already validated work.
  if source.name!=hashlib.sha256(requested.encode()).hexdigest()+'.json' or not valid_document(document,requested,source_host):continue
  dest=out/'source-cache'/source.name;dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists() or age_hours(document['fetched_at'])<age_hours(load_json(dest)['fetched_at']):shutil.copyfile(source,dest)
 for source in (worker_out/'parallel-runtime').rglob('*.json'):
  dest=out/'parallel/runtime'/source.relative_to(worker_out/'parallel-runtime');dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists() or age_hours(load_json(source)['verified_at'])<age_hours(load_json(dest)['verified_at']):shutil.copyfile(source,dest)

def launch_worker(topic,workspace,pool_db,health,inventory,data=DATA,out=OUT,env=None):
 env=dict(os.environ if env is None else env);ident=topic['id'];base=workspace/ident;wd=base/'data';wo=base/'out'
 from .family_keys import restrict_env
 env,key_context=restrict_env(env,topic.get('family_id'),data)
 shutil.copytree(data,wd)
 if env.get('AFP_SCOPED_FAMILY_PILOT')=='1':
  admission=load_json(out/'parallel/scoped-family-pilot/admissions'/(env['GITHUB_RUN_ID']+'.json'))
  if admission.get('topic_id')!=ident or admission.get('family_id')!=topic.get('family_id'):raise ValueError('Owned pilot worker identity mismatch')
  atomic_json(wd/'status/scoped-family-pilot-admission.json',admission)
 # A research worker cannot be blocked by another topic's historical ready-brief buffer.
 kept_brief=(data/'briefs'/f'{ident}.json')
 saved_brief=kept_brief.read_bytes() if kept_brief.exists() else None
 shutil.rmtree(wd/'briefs',ignore_errors=True);(wd/'briefs').mkdir()
 if saved_brief is not None:(wd/'briefs'/f'{ident}.json').write_bytes(saved_brief)
 cache=out/'source-cache'
 if cache.exists():
  from .source_loading import valid_document
  from .research import source_host
  for entry in cache.glob('*.json'):
   try:
    document=load_json(entry);requested=document.get('requested_url',document.get('url',''))
    if entry.name!=hashlib.sha256(requested.encode()).hexdigest()+'.json' or not valid_document(document,requested,source_host):continue
   except (ValueError,KeyError,TypeError):continue
   target=wo/'source-cache'/entry.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(entry,target)
 atomic_json(wd/'health/latest.json',health);atomic_json(wd/'parallel-inventory.json',inventory)
 for rel in ['research/'+ident+'.json','research-evidence/'+ident,'new/'+ident]:
  src=out/rel;dst=wo/rel
  if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True)
  elif src.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
 if env.get('AFP_PARALLEL_TRIAL_ID'):
  from .family_trial import ID as trial_id
  if env['AFP_PARALLEL_TRIAL_ID']!=trial_id:raise ValueError('Unknown trial identity')
  source=out/'parallel/trials'/trial_id/'inputs'/(ident+'.json')
  target=wo/'parallel/trials'/trial_id/'inputs'/(ident+'.json');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 from .healthcheck import TEXT_MODEL,IMAGE_MODEL
 run_id=str(env.get('GITHUB_RUN_ID',''))
 if not run_id.isdigit():raise ValueError('Verified run identity required for family context')
 atomic_json(wo/'new'/ident/'family-context'/(run_id+'.json'),{'family_id':topic.get('family_id'),'topic_id':ident,'title':topic['title'],'title_sha256':hashlib.sha256(topic['title'].encode()).hexdigest(),'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'context_isolation':'one owned topic and output directory; other families outputs not supplied','scope':'planned requests, not model success or publication approval',**key_context})
 for name in ['provider-circuit.json']:
  if (out/name).exists():wo.mkdir(parents=True,exist_ok=True);shutil.copyfile(out/name,wo/name)
 env.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_TOPIC=ident,AFP_PARALLEL_FAMILY=topic.get('family_id','unassigned'),AFP_PARALLEL_POOL_DB=str(pool_db),AFP_AGRI_DATA_DIR=str(wd),AFP_AGRI_OUT_DIR=str(wo),AFP_PROGRESS_ENABLED='0')
 # WordPress secrets are unavailable to article workers; read-only inventory is supplied once.
 for name in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):env.pop(name,None)
 try:
  from .matrix_pilot import bound as matrix_bound
  worker_timeout=2400 if matrix_bound(env,data) else 900
  completed=subprocess.run([sys.executable,'-m','automation.agri_v2.parallel_worker','--topic',ident],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=worker_timeout,check=False)
  rp=wo/'worker-result.json';result=load_json(rp) if rp.exists() else {'status':'worker_missing_result','topic_id':ident,'published_posts':0}
  if not isinstance(result,dict) or result.get('topic_id')!=ident:raise ValueError('Worker result identity mismatch')
  result['worker_exit_code']=completed.returncode
  if completed.returncode and result.get('status') not in ('worker_operational_failure','trial_operational_failure'):result.update(status='worker_operational_failure',failure={'kind':'unexpected','category':'worker_nonzero_exit'})
 except subprocess.TimeoutExpired:result={'status':'worker_timed_out','topic_id':ident,'published_posts':0}
 return ident,wd,wo,result

def run(mode='plan',env=None,data=DATA,out=OUT,reserve_fn=reserve,inventory_fn=None,worker_fn=launch_worker):
 env=os.environ if env is None else env;p=policy(env,data)
 if mode=='regional-revision':
  from .regional_revision import run as revision
  return revision(env,data,out)
 if mode=='checkpoint-reconcile':
  from .checkpoint_reconcile import reconcile
  return reconcile(env,data,out)
 if mode=='rollout-verify':
  from .staged_rollout import verify
  return verify(env,data,out)
 if mode=='rollout-plan':
  from .staged_rollout import load
  from .family_admission import project
  from .family_scheduler import allocate,assigned_topics
  topics=assigned_topics(allocate(data,out),data);due,rows=project(topics,data,out)
  return {'status':'staged_rollout_plan','rollout':load(out),'families':rows,'due_count':len(due),'model_calls':0,'post_mutations':0}
 if mode=='editorial-repair-reconcile':
  from .editorial_repair import reconcile
  return reconcile(data,out)
 if mode=='editorial-repair':
  from .editorial_repair import run as repair_editorial
  return repair_editorial(data,out)
 if mode=='image-followup':
  from .image_capability_followup import run as followup
  return followup(env,data,out)
 if mode=='image-refresh-all':
  from .family_capability_refresh import images
  return images(env,data,out,limit=20)
 if mode in ('health-refresh','image-refresh'):
  from .family_capability_refresh import text,images
  return (text if mode=='health-refresh' else images)(env,data,out)
 if mode=='source-search-check':
  from .source_search_check import run as check_search
  return check_search(env,data,out)
 if mode=='readiness':
  from .production_readiness import run as check_readiness
  return check_readiness(data,out)
 if mode=='family-pilot':
  from .family_lifecycle import run as advance
  return advance(dict(env,AFP_SCOPED_FAMILY_PILOT='1'),data,out)
 if mode in ('advance','white-bean-pilot'):
  from .family_lifecycle import run as advance
  env=dict(env);env.pop('AFP_WHITE_BEAN_PILOT',None);env.pop('AFP_SCOPED_FAMILY_PILOT',None)
  if mode=='white-bean-pilot':env['AFP_WHITE_BEAN_PILOT']='1'
  return advance(env,data,out)
 if mode=='trial':
  from .family_trial import run as trial
  return trial(env,data,out)
 if mode in ('assign','plan','research','bootstrap'):
  from .family_scheduler import allocate
  assignments=allocate(data,out)
  if mode=='assign':
   result=dict(assignments,status='families_assigned',run_id=env['GITHUB_RUN_ID'],published_posts=0,production_enabled=False)
   atomic_json(out/'parallel/latest-assignment.json',result)
   return result
 if mode in ('audit','bootstrap'):
  from .parallel_audit import run as audit
  checked=audit(env,data,out)
  if mode=='audit' or checked.get('status')!='completed' or not checked.get('eligible_text_slots'):return checked
  mode='research'
 if mode not in ('plan','research'):raise ValueError('Publication/image stages are not enabled by first rollout')
 from .recovery import circuit_open
 if circuit_open('text'):return {'status':'shared_text_cooldown','model_calls':0,'published_posts':0}
 hp=out/'parallel/health/latest.json'
 if not hp.exists():return {'status':'parallel_text_audit_required','published_posts':0,'model_calls':0}
 h=load_json(hp)
 if h.get('audit_status')!='completed':return {'status':'parallel_audit_incomplete','published_posts':0,'model_calls':0}
 if h.get('repository')!=p['repository'] or h.get('credential_set_id')!=p['credential_set_id'] or not 0<=age_hours(h['checked_at'])<24 or not h.get('eligible_text_slots'):return {'status':'fresh_parallel_text_health_required','published_posts':0,'model_calls':0}
 if inventory_fn is None:
  from .wordpress import WordPress
  wp=WordPress();wp.preflight();inventory=wp.inventory()
 else:inventory=inventory_fn()
 from .pipeline import fresh_inventory
 # Validate read-only inventory using the existing complete-inventory contract.
 with tempfile.TemporaryDirectory() as t:
  ip=Path(t)/'inventory.json';atomic_json(ip,inventory);fresh_inventory(ip)
 topics,skipped=eligible_topics(inventory,data,out,MAX_FAMILIES)
 report={'request_id':ID,'phase':mode,'status':'planned','run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'target_workers':MAX_FAMILIES,'selected_topics':[{'id':t['id'],'title':t['title'],'family_id':t.get('family_id'),'work_stage':t.get('assigned_work_stage')} for t in topics],'selected_count':len(topics),'eligible_text_slots':len(h['eligible_text_slots']),'max_text_requests_per_worker':3,'skipped':skipped,'results':[],'published_posts':0,'wordpress_write_calls':0,'image_calls':0,'original_attempts_reset':False,'production_enabled':False}
 dest=out/'parallel/research-runs'/ID;rp=dest/'report.json'
 if mode=='plan':atomic_json(out/'parallel/latest-plan.json',report);return report
 if not topics:report.update(status='no_source_ready_research_candidates',completed_at=utcnow());atomic_json(rp,report);return report
 if rp.exists() or reserve_fn('research',ID,env) is None:return {'status':'already_reserved','published_posts':0,'model_calls':0}
 atomic_json(rp,report)
 with tempfile.TemporaryDirectory(prefix='afp-parallel-') as td:
  workspace=Path(td);db=workspace/'pool.sqlite'
  initialize(db,h['eligible_text_slots'],text_limit=min(MAX_FAMILIES,len(h['eligible_text_slots'])),image_limit=1,max_calls=3*len(topics),per_worker=3,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
  started=time.monotonic()
  with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_FAMILIES,len(topics))) as executor:
   futures={executor.submit(worker_fn,t,workspace,db,h,inventory,data,out,env):t for t in topics}
   for future in concurrent.futures.as_completed(futures):
    topic=futures[future]
    try:
     ident,wd,wo,result=future.result()
     if ident!=topic['id'] or result.get('topic_id')!=ident:raise ValueError('Worker identity mismatch')
     merge_worker(ident,wd,wo,data,out)
    except Exception:result={'status':'worker_or_merge_failed','topic_id':topic['id'],'published_posts':0,'reason':'Inspect sanitized receipts; no automatic replay'}
    result['family_id']=topic.get('family_id')
    report['results'].append(result);report.update(status='running',completed_workers=len(report['results']));atomic_json(rp,report)
  pool_state=snapshot(db);record_routing(out,pool_state)
  if pool_state['cooldown_until_epoch']>time.time():
   atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':pool_state['cooldown_until_epoch'],'reason':'parallel_worker_shared_provider_limit','no_secrets':True})
  report.update(status='research_batch_completed',elapsed_seconds=round(time.monotonic()-started,2),pool=pool_state,completed_at=utcnow());atomic_json(rp,report)
 from .family_scheduler import allocate
 allocate(data,out)
 atomic_json(out/'parallel/latest.json',report);return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['assign','plan','audit','research','bootstrap','trial','advance','white-bean-pilot','readiness','source-search-check','health-refresh','image-refresh','image-refresh-all','image-followup','family-pilot','editorial-repair','editorial-repair-reconcile','rollout-plan','rollout-verify','checkpoint-reconcile','regional-revision'],default='plan');a=p.parse_args()
 result=run(a.mode);print(json.dumps({k:v for k,v in result.items() if k not in {'cases','pool','selected_topics','results'}},ensure_ascii=False));return 2 if result.get('status') in {'revision_needs_attention','revision_reconciliation_required','revision_already_reserved_no_replay','revision_fresh_text_health_required','revision_provider_cooldown','repair_stopped_reconciliation_required','already_reserved_no_replay','missing_or_duplicate_credentials','stopped_shared_provider_limit','parallel_audit_incomplete','trial_completed_with_operational_failures','trial_setup_failed','completed_with_failures','readiness_blocked','reconciliation_required','search_connection_blocked','incomplete_provider_failure','family_text_capacity_incomplete','capability_already_reserved_no_replay','capability_reconciliation_required','shared_text_cooldown','shared_image_cooldown','followup_already_reserved_no_replay','followup_reconciliation_required','followup_waiting_other_19','followup_waiting_accepted_pilot','followup_admission_blocked_not_sent','followup_failed','followup_failed_invalid_image','staged_acceptance_not_ready','cohort_not_selected'} else 0
if __name__=='__main__':raise SystemExit(main())
