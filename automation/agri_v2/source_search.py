"""Brave Search adapter: fixed endpoint, secret header, shared bounded admission.
Search hits are untrusted discovery metadata, never extracted scientific evidence.
"""
import contextlib,hashlib,json,math,os,sqlite3,time,urllib.error,urllib.parse,urllib.request,uuid
from .parallel_pool import connect,PoolDeferred
from .queue import load_json,atomic_json,utcnow
ENDPOINT='https://api.search.brave.com/res/v1/web/search'
POLICY={'version':1,'enabled':True,'backend':'brave','rounds':2,'queries_per_round':2,'results_per_query':6,'max_source_fetches':12,'max_search_requests_per_run':80,'search_concurrency':1,'search_cache_hours':6,'reset_original_attempts':False,'publication_authorized':False}
class SearchConnectionRequired(ValueError):pass
class SearchProviderError(RuntimeError):
 def __init__(self,status,category,retry_after=None):
  self.http_status=status;self.category=category;self.retry_after_seconds=retry_after
  super().__init__(category)

def enabled(data):
 p=data/'source-search-policy.json'
 if not p.exists():return False
 r=load_json(p)
 if r==dict(POLICY,enabled=False):return False
 if r!=POLICY:raise ValueError('Exact source search policy required')
 return True

def require(env):
 key=env.get('AFP_SOURCE_SEARCH_API_KEY','').strip()
 if not key:raise SearchConnectionRequired('brave_search_key_required')
 if not env.get('AFP_PARALLEL_POOL_DB'):raise SearchConnectionRequired('shared_search_admission_required')
 return key

def query_key(query):return hashlib.sha256(('brave-web-v1\n'+query).encode()).hexdigest()

def validate_results(rows):
 from .research import source_host
 if not isinstance(rows,list) or len(rows)>6:raise ValueError('Invalid search cache results')
 result=[];seen=set()
 for row in rows:
  if not isinstance(row,dict) or set(row)!={'url','title','description'} or any(not isinstance(row[k],str) for k in row):raise ValueError('Invalid search cache row')
  source_host(row['url'])
  if len(row['title'])>400 or len(row['description'])>1200:raise ValueError('Oversized search cache row')
  if row['url'] not in seen:result.append(row);seen.add(row['url'])
 return result

def initialize(db,out):
 p=out/'parallel/source-search/state.json';prior=load_json(p) if p.exists() else {'version':1,'backend':'brave','cooldown_until_epoch':0,'cache':{}}
 if not isinstance(prior,dict) or prior.get('version')!=1 or prior.get('backend')!='brave' or not isinstance(prior.get('cache'),dict):raise ValueError('Invalid source search state')
 cooldown=prior.get('cooldown_until_epoch')
 if type(cooldown) not in (int,float) or not math.isfinite(cooldown) or cooldown<0:raise ValueError('Invalid source search cooldown')
 with connect(db) as c:
  c.executescript('CREATE TABLE IF NOT EXISTS search_meta(name TEXT PRIMARY KEY,value REAL); CREATE TABLE IF NOT EXISTS search_cache(query_id TEXT PRIMARY KEY,checked REAL,results TEXT); CREATE TABLE IF NOT EXISTS search_requests(request_id TEXT PRIMARY KEY,query_id TEXT,status TEXT); CREATE TABLE IF NOT EXISTS search_lock(id INTEGER PRIMARY KEY,owner TEXT);')
  c.execute('INSERT OR IGNORE INTO search_lock VALUES(1,NULL)')
  for name,value in {'calls':0,'cooldown':cooldown,'next_call':0}.items():c.execute('INSERT OR IGNORE INTO search_meta VALUES(?,?)',(name,value))
  c.execute("UPDATE search_meta SET value=MAX(value,?) WHERE name='cooldown'",(cooldown,))
  for q,row in prior['cache'].items():
   if not isinstance(q,str) or len(q)!=64 or any(ch not in '0123456789abcdef' for ch in q) or not isinstance(row,dict) or type(row.get('checked')) not in (int,float) or not math.isfinite(row['checked']):raise ValueError('Invalid source search cache')
   if 0<=time.time()-row['checked']<21600:c.execute('INSERT OR IGNORE INTO search_cache VALUES(?,?,?)',(q,row['checked'],json.dumps(validate_results(row.get('results')))))

def persist(db,out):
 with connect(db) as c:
  if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='search_meta'").fetchone():return {'status':'not_used','requests_reserved':0}
  meta=dict(c.execute('SELECT name,value FROM search_meta'));rows=c.execute('SELECT query_id,checked,results FROM search_cache ORDER BY checked DESC LIMIT 500').fetchall()
  cache={r[0]:{'checked':r[1],'results':validate_results(json.loads(r[2]))} for r in rows if 0<=time.time()-r[1]<21600}
  unknown=c.execute("SELECT COUNT(*) FROM search_requests WHERE status='reserved'").fetchone()[0]
 atomic_json(out/'parallel/source-search/state.json',{'version':1,'backend':'brave','updated_at':utcnow(),'cooldown_until_epoch':meta['cooldown'],'cache':cache,'secret_values_stored':False})
 return {'backend':'brave','requests_reserved':int(meta['calls']),'unknown_requests':unknown,'cache_entries':len(cache),'cooldown_until_epoch':meta['cooldown'],'secret_values_stored':False}

@contextlib.contextmanager
def reservation(db,query_id,request_id,wait=120):
 owner=uuid.uuid4().hex;deadline=time.monotonic()+wait
 while True:
  with connect(db) as c:
   c.execute('BEGIN IMMEDIATE');m=dict(c.execute('SELECT name,value FROM search_meta'))
   if not m:c.execute('ROLLBACK');raise SearchConnectionRequired('shared_search_admission_required')
   old=c.execute('SELECT status FROM search_requests WHERE request_id=?',(request_id,)).fetchone()
   if old:c.execute('ROLLBACK');raise PoolDeferred('Search request already reserved; no replay')
   if m['cooldown']>time.time() or m['calls']>=80:c.execute('ROLLBACK');raise PoolDeferred('Search-only cooldown or request budget')
   busy=c.execute('SELECT owner FROM search_lock WHERE id=1').fetchone()[0]
   if busy is None and m['next_call']<=time.time():
    c.execute('UPDATE search_lock SET owner=? WHERE id=1',(owner,));c.execute('INSERT INTO search_requests VALUES(?,?,?)',(request_id,query_id,'reserved'));c.execute("UPDATE search_meta SET value=value+1 WHERE name='calls'");c.execute('COMMIT');break
   c.execute('ROLLBACK')
  if time.monotonic()>=deadline:raise PoolDeferred('Search admission busy; no search API call')
  time.sleep(.1)
 try:yield
 finally:
  with connect(db) as c:
   c.execute('UPDATE search_lock SET owner=NULL WHERE id=1 AND owner=?',(owner,));c.execute("UPDATE search_meta SET value=MAX(value,?) WHERE name='next_call'",(time.time()+1,))

def search(query,env,request_id,opener=None):
 key=require(env)
 if not isinstance(query,str) or not 8<=len(query)<=240 or len(query.split())>60:raise ValueError('Bounded search query required')
 db=env['AFP_PARALLEL_POOL_DB'];qid=query_key(query)
 with connect(db) as c:
  hit=c.execute('SELECT checked,results FROM search_cache WHERE query_id=?',(qid,)).fetchone()
  if hit and 0<=time.time()-hit[0]<21600:return {'query_id':qid,'query':query,'cached':True,'checked_at_epoch':hit[0],'results':validate_results(json.loads(hit[1]))}
 from .research import NoRedirect,source_host
 with reservation(db,qid,request_id):
  with connect(db) as c:
   hit=c.execute('SELECT checked,results FROM search_cache WHERE query_id=?',(qid,)).fetchone()
   if hit and 0<=time.time()-hit[0]<21600:
    c.execute("UPDATE search_requests SET status='cache_served' WHERE request_id=?",(request_id,))
    return {'query_id':qid,'query':query,'cached':True,'checked_at_epoch':hit[0],'results':validate_results(json.loads(hit[1]))}
  req=urllib.request.Request(ENDPOINT+'?'+urllib.parse.urlencode({'q':query,'count':6,'country':'ALL','search_lang':'en','safesearch':'moderate'}),headers={'Accept':'application/json','X-Subscription-Token':key,'User-Agent':'AFP-source-discovery/2'})
  try:
   with (urllib.request.build_opener(NoRedirect()) if opener is None else opener).open(req,timeout=20) as response:
    blob=response.read(1_000_001)
    if response.status!=200 or len(blob)>1_000_000:raise SearchProviderError(200,'source_search_response_invalid')
    obj=json.loads(blob)
   if not isinstance(obj,dict) or 'error' in obj:raise SearchProviderError(200,'source_search_response_invalid')
   raw=obj.get('web',{}).get('results',[])
   if not isinstance(raw,list):raise SearchProviderError(200,'source_search_response_invalid')
   rows=[]
   for row in raw[:6]:
    if not isinstance(row,dict) or not isinstance(row.get('url'),str):continue
    try:source_host(row['url'])
    except ValueError:continue
    rows.append({'url':row['url'],'title':str(row.get('title',''))[:400],'description':str(row.get('description',''))[:1200]})
   rows=validate_results(rows);checked=time.time()
   with connect(db) as c:
    c.execute('INSERT OR REPLACE INTO search_cache VALUES(?,?,?)',(qid,checked,json.dumps(rows)));c.execute("UPDATE search_requests SET status='responded' WHERE request_id=?",(request_id,))
   return {'query_id':qid,'query':query,'cached':False,'checked_at_epoch':checked,'results':rows}
  except urllib.error.HTTPError as e:
   status=e.code
   from .provider_retry import retry_seconds
   retry=retry_seconds(e.headers.get('Retry-After'));e.close()
   category='source_search_rate_limited' if status==429 else 'source_search_auth' if status in (401,403) else 'source_search_unavailable'
   with connect(db) as c:
    c.execute("UPDATE search_requests SET status='http_error' WHERE request_id=?",(request_id,));c.execute("UPDATE search_meta SET value=MAX(value,?) WHERE name='cooldown'",(time.time()+max(60,retry or (3600 if status in (401,403,429) else 60)),))
   raise SearchProviderError(status,category,retry) from None
  except SearchProviderError as exc:
   if exc.http_status==200:
    with connect(db) as c:c.execute("UPDATE search_requests SET status='invalid_response' WHERE request_id=?",(request_id,))
   raise
  except (OSError,TimeoutError,ValueError,AttributeError,TypeError):
   with connect(db) as c:c.execute("UPDATE search_meta SET value=MAX(value,?) WHERE name='cooldown'",(time.time()+60,))
   raise SearchProviderError(None,'source_search_unavailable') from None
