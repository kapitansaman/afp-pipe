"""A single isolated topic, no publication code in the worker."""
import argparse,json,os
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .parallel_client import ParallelModelClient

def run(ident):
 from .research import prepare_one
 inventory=load_json(DATA/'parallel-inventory.json')
 if os.environ.get('AFP_PARALLEL_WORKER')!='1' or os.environ.get('AFP_PARALLEL_TOPIC')!=ident:raise ValueError('Explicit isolated worker required')
 result=prepare_one(inventory,client_factory=ParallelModelClient,only_topic_id=ident)
 result.update(wordpress_write_calls=0,published_posts=0,worker_completed_at=utcnow())
 atomic_json(OUT/'worker-result.json',result);return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--topic',required=True);a=p.parse_args()
 try:r=run(a.topic)
 except Exception:
  # Never copy provider errors/credentials into logs or durable diagnostics.
  r={'status':'worker_deferred_or_failed','topic_id':a.topic,'published_posts':0,'wordpress_write_calls':0,'reason':'Inspect sanitized stage receipts; no raw exception persisted'};atomic_json(OUT/'worker-result.json',r)
 print(json.dumps(r,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
