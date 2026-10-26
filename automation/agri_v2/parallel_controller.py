"""Coordinator for 15 isolated research workers and one output writer.
Legacy rollout modes remain research-only; advance runs gated resumable families.
"""
import argparse,concurrent.futures,hashlib,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
from .queue import DATA,OUT,ROOT,items,load_json,atomic_json,utcnow,age_hours,safe_id
from .parallel_control import policy,reserve
from .parallel_pool import initialize,snapshot,routing_counts,record_routing
ID='parallel-15-research-rollout-v1'

def eligible_topics(inventory,data=DATA,out=OUT,limit=15):
 # Compatibility name: these are now ASSIGNED topics, not source-readiness-filtered topics.
 from .family_scheduler import allocate,assigned_topics
 state=allocate(data,out)
 return assigned_topics(state,data)[:limit],{}

def merge_worker(ident,worker_data,worker_out,data=DATA,out=OUT):
 safe_id(ident)
 bp=worker_data/'briefs'/f'{ident}.json';dest_brief=data/'briefs'/bp.name
 if bp.exists() and dest_brief.exists() and dest_brief.read_bytes()!=bp.read_bytes():raise ValueError('Existing brief changed; never overwrite')
 for rel in ['research/'+ident+'.json','research-evidence/'+ident,'new/'+ident]:
  source=worker_out/rel;dest=out/rel
  if source.is_dir():shutil.copytree(source,dest,dirs_exist_ok=True)
  elif source.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
 if bp.exists():dest_brief.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(bp,dest_brief)
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
 shutil.copytree(data,wd)
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
 for name in ['provider-circuit.json']:
  if (out/name).exists():wo.mkdir(parents=True,exist_ok=True);shutil.copyfile(out/name,wo/name)
 env.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_TOPIC=ident,AFP_PARALLEL_FAMILY=topic.get('family_id','unassigned'),AFP_PARALLEL_POOL_DB=str(pool_db),AFP_AGRI_DATA_DIR=str(wd),AFP_AGRI_OUT_DIR=str(wo),AFP_PROGRESS_ENABLED='0')
 # WordPress secrets are unavailable to article workers; read-only inventory is supplied once.
 for name in ('AFP_WP_BASE_URL','AFP_WP_USERNAME','AFP_WP_APP_PASSWORD'):env.pop(name,None)
 try:
  completed=subprocess.run([sys.executable,'-m','automation.agri_v2.parallel_worker','--topic',ident],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=900,check=False)
  rp=wo/'worker-result.json';result=load_json(rp) if rp.exists() else {'status':'worker_missing_result','topic_id':ident,'published_posts':0}
  if not isinstance(result,dict) or result.get('topic_id')!=ident:raise ValueError('Worker result identity mismatch')
  result['worker_exit_code']=completed.returncode
  if completed.returncode and result.get('status') not in ('worker_operational_failure','trial_operational_failure'):result.update(status='worker_operational_failure',failure={'kind':'unexpected','category':'worker_nonzero_exit'})
 except subprocess.TimeoutExpired:result={'status':'worker_timed_out','topic_id':ident,'published_posts':0}
 return ident,wd,wo,result

def run(mode='plan',env=None,data=DATA,out=OUT,reserve_fn=reserve,inventory_fn=None,worker_fn=launch_worker):
 env=os.environ if env is None else env;p=policy(env,data)
 if mode in ('advance','white-bean-pilot'):
  from .family_lifecycle import run as advance
  env=dict(env);env.pop('AFP_WHITE_BEAN_PILOT',None)
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
 topics,skipped=eligible_topics(inventory,data,out,15)
 report={'request_id':ID,'phase':mode,'status':'planned','run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'target_workers':15,'selected_topics':[{'id':t['id'],'title':t['title'],'family_id':t.get('family_id'),'work_stage':t.get('assigned_work_stage')} for t in topics],'selected_count':len(topics),'eligible_text_slots':len(h['eligible_text_slots']),'max_text_requests_per_worker':3,'skipped':skipped,'results':[],'published_posts':0,'wordpress_write_calls':0,'image_calls':0,'original_attempts_reset':False,'production_enabled':False}
 dest=out/'parallel/research-runs'/ID;rp=dest/'report.json'
 if mode=='plan':atomic_json(out/'parallel/latest-plan.json',report);return report
 if not topics:report.update(status='no_source_ready_research_candidates',completed_at=utcnow());atomic_json(rp,report);return report
 if rp.exists() or reserve_fn('research',ID,env) is None:return {'status':'already_reserved','published_posts':0,'model_calls':0}
 atomic_json(rp,report)
 with tempfile.TemporaryDirectory(prefix='afp-parallel-') as td:
  workspace=Path(td);db=workspace/'pool.sqlite'
  initialize(db,h['eligible_text_slots'],text_limit=min(15,len(h['eligible_text_slots'])),image_limit=1,max_calls=3*len(topics),per_worker=3,prior_usage=routing_counts(out))
  started=time.monotonic()
  with concurrent.futures.ThreadPoolExecutor(max_workers=min(15,len(topics))) as executor:
   futures={executor.submit(worker_fn,t,workspace,db,h,inventory,data,out,env):t for t in topics}
   for future in concurrent.futures.as_completed(futures):
    topic=futures[future]
    try:
     ident,wd,wo,result=future.result();merge_worker(ident,wd,wo,data,out)
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
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['assign','plan','audit','research','bootstrap','trial','advance','white-bean-pilot'],default='plan');a=p.parse_args()
 result=run(a.mode);print(json.dumps({k:v for k,v in result.items() if k not in {'cases','pool','selected_topics','results'}},ensure_ascii=False));return 2 if result.get('status') in {'missing_or_duplicate_credentials','stopped_shared_provider_limit','parallel_audit_incomplete','trial_completed_with_operational_failures','trial_setup_failed','completed_with_failures'} else 0
if __name__=='__main__':raise SystemExit(main())
