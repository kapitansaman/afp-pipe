"""Persist bounded search/fetch progress, not scientific acceptance.
Only failed GETs may resume. Unknown model/search requests retain original fences.
"""
import hashlib,time
from urllib.parse import urlsplit
from .queue import atomic_json,load_json,utcnow
from .model_source_repair import RepairBlocked
from .foundation_policy import POLICY
from .source_loading import load_documents,valid_document
from .research import source_host

def digest(value):
 from .web_source_repair import coverage_fingerprint
 return coverage_fingerprint(value)
def read_progress(path,topic,before,plan):
 if not path.exists():return {'version':1,'topic_id':topic['id'],'input_binding':before,'plan_sha256':digest(plan),'rounds':{},'urls':{},'documents':[],'publication_authorized':False,'scientific_acceptance':False}
 r=load_json(path);signature=r.pop('progress_sha256',None)
 if signature!=digest(r) or r.get('version')!=1 or r.get('topic_id')!=topic['id'] or r.get('input_binding')!=before or r.get('plan_sha256')!=digest(plan) or any(r.get(k)is not False for k in ('publication_authorized','scientific_acceptance')):raise RepairBlocked('source_resume_binding_invalid')
 if not isinstance(r.get('urls'),dict) or len(r['urls'])>12 or not isinstance(r.get('rounds'),dict) or set(r['rounds'])-{'1','2'}:raise RepairBlocked('source_resume_budget_invalid')
 for url,row in r['urls'].items():
  source_host(url)
  if type(row.get('transport_attempts')) is not int or not 0<=row['transport_attempts']<=3 or row.get('status') not in ('pending','loaded','temporary','permanent'):raise RepairBlocked('source_resume_budget_invalid')
 for d in r['documents']:
  source_host(d['url'])
  if d.get('sha256')!=hashlib.sha256(d['text'].encode()).hexdigest():raise RepairBlocked('source_resume_document_changed')
 return r

def save(path,row):atomic_json(path,dict(row,progress_sha256=digest(row)))
def wait_record(work,topic,before,progress,complete):
 pending=[r for r in progress['urls'].values() if r['status']=='temporary']
 path=work/'retry.json'
 if complete or not pending:
  row={'version':1,'topic_id':topic['id'],'input_binding':before,'status':'clear','next_attempt_epoch':None}
 else:
  due=[r['next_attempt_epoch'] for r in pending if r['transport_attempts']<3]
  row={'version':1,'topic_id':topic['id'],'input_binding':before,'status':'waiting' if due else 'requires_retrieval_review','next_attempt_epoch':min(due) if due else None}
 row.update(publication_authorized=False,scientific_acceptance=False,original_attempts_reset=False,updated_at=utcnow());atomic_json(path,row)
 return row

def collect(topic,plan,original,work,before,client,out,env,fetcher,search_fn,now=None):
 from . import source_search as search
 from .web_source_repair import cached_coverage
 now=time.time() if now is None else now;path=work/'progress.json';p=read_progress(path,topic,before,plan)
 # Derive admission from the bound progress itself, never from an editable
 # retry timestamp alone. This also covers admission failure before triage.
 retry=work/'retry.json'
 if retry.exists():
  gate=load_json(retry)
  if gate.get('topic_id')!=topic['id'] or gate.get('input_binding')!=before:raise RepairBlocked('source_resume_binding_invalid')
 pending=[r for r in p['urls'].values() if r['status']=='temporary']
 callable_fetch=any(r['status'] in ('pending','temporary') and r['transport_attempts']<3 and r.get('next_attempt_epoch',0)<=now for r in p['urls'].values())
 if pending and not callable_fetch:
  from .parallel_pool import PoolDeferred
  raise PoolDeferred('Temporary source fetch failure; no scientific absence inferred')
 queries=list(plan['queries']);rounds=[];docs=list(original)
 # Stale fetched text is retained for audit, but refetched before triage reuse.
 for d in p['documents']:
  requested=d.get('requested_url',d['url'])
  if valid_document(d,requested,source_host):
   if d['url'] not in {x['url'] for x in docs}:docs.append(d)
  elif requested in p['urls'] and p['urls'][requested]['status']=='loaded':p['urls'][requested].update(status='pending' if p['urls'][requested]['transport_attempts']<3 else 'temporary',next_attempt_epoch=0)
 used=set()
 for n in (1,2):
  key=str(n);round_row=p['rounds'].get(key)
  if round_row is None:
   selected=[q for q in queries if q not in used][:2]
   if not selected:break
   round_row={'round':n,'queries':[],'urls':[],'started_at':utcnow()}
   for i,q in enumerate(selected):
    result=search_fn(q,env,topic['id']+'-round-'+str(n)+'-query-'+str(i));rows=search.validate_results(result['results']);round_row['queries'].append(result)
    # Save each confirmed search before the next request; an uncertain request
    # remains fenced by the enclosing lifecycle attempt, never inferred successful.
    for r in rows:
     url=r['url']
     if url not in p['urls'] and url not in {d['url'] for d in original} and len(p['urls'])<12:p['urls'][url]={'transport_attempts':0,'status':'pending','next_attempt_epoch':0}
     if url in p['urls'] and url not in round_row['urls'] and len(round_row['urls'])<6:round_row['urls'].append(url)
    p['rounds'][key]=round_row;save(path,p)
   # At most six distinct URL admissions per round, twelve per operation.
   owned={u for r in p['rounds'].values() for u in r['urls']}
   p['urls']={u:r for u,r in p['urls'].items() if u in owned};save(path,p)
  used.update(q['query'] for q in round_row['queries'] if 'query' in q)
  due=[u for u in round_row['urls'] if p['urls'][u]['status'] in ('pending','temporary') and p['urls'][u]['transport_attempts']<3 and p['urls'][u].get('next_attempt_epoch',0)<=now]
  # Pending first fetches always run; a temporary failure waits exponentially.
  report_path=work/('round-'+key+'-fetch.json')
  if due:
   loaded=load_documents(due,fetcher,out,source_host,report_path=report_path,minimum_link_version=1);report=load_json(report_path)
   for r in report['sources']:
    row=p['urls'][r['url']];row['transport_attempts']+=1;temporary=r.get('temporary')is True or r.get('category')=='network_or_timeout'
    row.update(status='loaded' if r['status'] in ('fetched','cache_valid') else 'temporary' if temporary else 'permanent',category=r.get('category'),next_attempt_epoch=now+min(21600,900*2**(row['transport_attempts']-1)) if temporary else 0)
   for d in loaded:
    if urlsplit(d.get('requested_url',d['url'])).query:continue
    p['documents']=[old for old in p['documents'] if old['url']!=d['url']]+[d]
    if d['url'] not in {x['url'] for x in docs}:docs.append(d)
   save(path,p)
  else:report={'requested':0,'loaded':0,'sources':[],'network_calls_skipped':True}
  verdict,hit=cached_coverage(topic,plan,docs,client,n,work)
  r=dict(round_row,fetch_report=report,new_document_ids=['s'+str(i) for i in range(len(docs))],fetches_reserved=len(round_row['urls']),coverage=verdict,coverage_cache_hit=hit,publication_authorized=False,completed_at=utcnow());rounds.append(r);atomic_json(work/('round-'+key+'.json'),r);queries=verdict['next_queries']
  if all(v['covered'] for v in verdict['requirements']):break
 complete=bool(rounds) and all(v['covered'] for v in rounds[-1]['coverage']['requirements']);wait=wait_record(work,topic,before,p,complete);save(path,p)
 return docs,rounds,len(p['urls']),not complete and wait['status']!='clear'
