"""One Actions runner, 75 credentials, process-safe dynamic leases and shared backpressure.
Only slot names/counters are stored. Never credentials or credential fingerprints.
"""
import contextlib,json,os,sqlite3,time,uuid
from pathlib import Path
SLOTS=['AGNES_API_KEY']+[f'AGNES_API_KEY{i}' for i in range(2,76)]
class PoolDeferred(RuntimeError):pass

@contextlib.contextmanager
def connect(path):
 c=sqlite3.connect(str(path),timeout=15,isolation_level=None);c.row_factory=sqlite3.Row
 try:yield c
 finally:c.close()

def initialize(path,slots,text_limit=15,image_limit=1,max_calls=240,per_worker=16,prior_usage=None):
 if not set(slots)<=set(SLOTS) or len(set(slots))!=len(slots):raise ValueError('Unknown or duplicate slot names')
 prior_usage={} if prior_usage is None else prior_usage
 if any(n not in SLOTS or type(v)is not int or v<0 for n,v in prior_usage.items()):raise ValueError('Invalid prior routing counters')
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with connect(path) as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.executescript('CREATE TABLE IF NOT EXISTS slots(name TEXT PRIMARY KEY, ordinal INTEGER, used INTEGER DEFAULT 0, owner TEXT, kind TEXT, disabled INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY,value REAL); CREATE TABLE IF NOT EXISTS workers(name TEXT PRIMARY KEY,used INTEGER DEFAULT 0);')
  for i,s in enumerate(slots):c.execute('INSERT OR IGNORE INTO slots(name,ordinal,used) VALUES(?,?,?)',(s,i,prior_usage.get(s,0)))
  for k,v in {'sequence':0,'cooldown':0,'text_limit':text_limit,'image_limit':image_limit,'max_calls':max_calls,'per_worker':per_worker,'calls':0,'peak_text_leases':0,'peak_image_leases':0}.items():c.execute('INSERT OR IGNORE INTO meta VALUES(?,?)',(k,v))

def snapshot(path):
 with connect(path) as c:
  m=dict(c.execute('SELECT name,value FROM meta'));rows=[dict(r) for r in c.execute('SELECT name,used,disabled,kind FROM slots ORDER BY ordinal')]
 return {'model_requests_reserved':int(m['calls']),'cooldown_until_epoch':m['cooldown'],'slots':rows,'secret_values_stored':False,'peak_text_leases':int(m.get('peak_text_leases',0)),'peak_image_leases':int(m.get('peak_image_leases',0))}

def defer(path,seconds=3600):
 with connect(path) as c:c.execute("UPDATE meta SET value=MAX(value,?) WHERE name='cooldown'",(time.time()+max(60,seconds),))

@contextlib.contextmanager
def lease(path,kind,eligible,worker='controller',wait=30):
 if kind not in ('text','image') or not eligible:raise PoolDeferred('No eligible capability')
 if not set(eligible)<=set(SLOTS):raise ValueError('Unknown lease slot')
 owner=uuid.uuid4().hex;deadline=time.monotonic()+wait;slot=None
 while slot is None:
  with connect(path) as c:
   c.execute('BEGIN IMMEDIATE')
   m=dict(c.execute('SELECT name,value FROM meta'))
   if m['cooldown']>time.time():c.execute('ROLLBACK');raise PoolDeferred('Shared provider cooldown')
   c.execute('INSERT OR IGNORE INTO workers(name) VALUES(?)',(worker,));used=c.execute('SELECT used FROM workers WHERE name=?',(worker,)).fetchone()[0]
   if m['calls']>=m['max_calls'] or used>=m['per_worker']:c.execute('ROLLBACK');raise PoolDeferred('Bounded model budget consumed')
   busy=c.execute('SELECT COUNT(*) FROM slots WHERE owner IS NOT NULL AND kind=?',(kind,)).fetchone()[0]
   if busy<m[kind+'_limit']:
    q=','.join('?' for _ in eligible)
    row=c.execute('SELECT name FROM slots WHERE name IN ('+q+') AND owner IS NULL AND disabled=0 ORDER BY used,ordinal LIMIT 1',list(eligible)).fetchone()
    if row:
     slot=row[0];c.execute('UPDATE slots SET owner=?,kind=?,used=used+1 WHERE name=?',(owner,kind,slot));c.execute("UPDATE meta SET value=value+1 WHERE name IN ('calls','sequence')");c.execute('UPDATE workers SET used=used+1 WHERE name=?',(worker,));c.execute('UPDATE meta SET value=MAX(value,?) WHERE name=?',(busy+1,'peak_'+kind+'_leases'))
   c.execute('COMMIT')
  if slot is None:
   if time.monotonic()>=deadline:raise PoolDeferred('Eligible credentials busy; defer without provider call')
   time.sleep(.1)
 try:yield slot
 finally:
  with connect(path) as c:c.execute('UPDATE slots SET owner=NULL,kind=NULL WHERE name=? AND owner=?',(slot,owner))

def disable(path,slot):
 with connect(path) as c:c.execute('UPDATE slots SET disabled=1 WHERE name=?',(slot,))

def routing_counts(out):
 from .queue import load_json
 p=Path(out)/'parallel/key-routing.json'
 if p.exists():rows=load_json(p).get('slot_request_counts',{})
 else:
  previous=Path(out)/'parallel/latest.json'
  prior=load_json(previous).get('pool',{}).get('slots',[]) if previous.exists() else []
  rows={r['name']:r['used'] for r in prior}
 if any(k not in SLOTS or type(v)is not int or v<0 for k,v in rows.items()):raise ValueError('Invalid durable key routing; no automatic reset')
 return rows

def record_routing(out,state):
 from .queue import atomic_json,utcnow
 rows={r['name']:int(r['used']) for r in state['slots']}
 prior=routing_counts(out)
 if any(rows.get(k,0)<v for k,v in prior.items()):raise ValueError('Key routing counters regressed')
 atomic_json(Path(out)/'parallel/key-routing.json',{'updated_at':utcnow(),'slot_request_counts':rows,'secret_values_stored':False})
