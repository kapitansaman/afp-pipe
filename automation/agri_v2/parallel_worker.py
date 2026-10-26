"""A single isolated topic, no publication code in the worker."""
import argparse,json,os
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .parallel_client import ParallelModelClient

def run(ident):
 if os.environ.get('AFP_FAMILY_LIFECYCLE')=='1':
  from .family_lifecycle import worker
  from .queue import get_topic
  topic=get_topic('new',ident);topic['family_id']=os.environ.get('AFP_PARALLEL_FAMILY')
  result=worker(topic,load_json(DATA/'health/latest.json'));atomic_json(OUT/'worker-result.json',result);return result
 if os.environ.get('AFP_PARALLEL_TRIAL_ID'):
  from .family_trial import run_family
  return run_family(ident)
 from .research import prepare_one
 inventory=load_json(DATA/'parallel-inventory.json')
 if os.environ.get('AFP_PARALLEL_WORKER')!='1' or os.environ.get('AFP_PARALLEL_TOPIC')!=ident:raise ValueError('Explicit isolated worker required')
 from .queue import get_topic
 from .family_scheduler import readiness
 topic=get_topic('new',ident);stage=readiness(topic,DATA,OUT)
 if stage!='ready_for_research':
  result={'status':'assigned_'+stage,'topic_id':ident,'family_id':os.environ.get('AFP_PARALLEL_FAMILY'),'work_stage':stage,'assignment_retained':True,'model_calls':0}
 else:
  result=prepare_one(inventory,client_factory=ParallelModelClient,only_topic_id=ident)
  result.update(family_id=os.environ.get('AFP_PARALLEL_FAMILY'),assignment_retained=True)
 result.update(wordpress_write_calls=0,published_posts=0,worker_completed_at=utcnow())
 atomic_json(OUT/'worker-result.json',result);return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--topic',required=True);a=p.parse_args()
 try:r=run(a.topic)
 except Exception as e:
  from .failure_diagnostics import failure_details
  failure=failure_details(e)
  from .family_trial import TrialValidation
  if isinstance(e,TrialValidation):failure['category']=e.code
  from .parallel_pool import PoolDeferred
  if isinstance(e,PoolDeferred):failure={'kind':'shared_pool','category':'cooldown_or_budget_or_busy'}
  r={'status':'worker_operational_failure','topic_id':a.topic,'family_id':os.environ.get('AFP_PARALLEL_FAMILY'),'published_posts':0,'wordpress_write_calls':0,'failure':failure};atomic_json(OUT/'worker-result.json',r)
  print(json.dumps(r,ensure_ascii=False));return 2
 print(json.dumps(r,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
