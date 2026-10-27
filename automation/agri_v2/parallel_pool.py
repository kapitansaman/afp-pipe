"""One Actions runner, 97 credentials, process-safe dynamic leases and shared backpressure.
Only slot names/counters are stored. Never credentials or credential fingerprints.
"""
import contextlib,json,math,os,sqlite3,time,uuid
from pathlib import Path
from .parallel_capacity import KEY_LIMIT,MAX_FAMILIES
SLOTS=['AGNES_API_KEY']+[f'AGNES_API_KEY{i}' for i in range(2,KEY_LIMIT+1)]
class PoolDeferred(RuntimeError):pass

@contextlib.contextmanager
def connect(path):
 c=sqlite3.connect(str(path),timeout=15,isolation_level=None);c.row_factory=sqlite3.Row
 try:yield c
 finally:c.close()

def initialize(path,slots,text_limit=MAX_FAMILIES,image_limit=1,max_calls=240,per_worker=16,prior_usage=None,prior_backpressure=None):
 if type(text_limit)is not int or not 1<=text_limit<=MAX_FAMILIES or image_limit!=1:raise ValueError('Bounded text concurrency and single-flight images required')
 if not set(slots)<=set(SLOTS) or len(set(slots))!=len(slots):raise ValueError('Unknown or duplicate slot names')
 prior_usage={} if prior_usage is None else prior_usage
 if any(n not in SLOTS or type(v)is not int or v<0 for n,v in prior_usage.items()):raise ValueError('Invalid prior routing counters')
 prior_backpressure=validate_backpressure({} if prior_backpressure is None else prior_backpressure)
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with connect(path) as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.executescript('CREATE TABLE IF NOT EXISTS slots(name TEXT PRIMARY KEY, ordinal INTEGER, used INTEGER DEFAULT 0, owner TEXT, kind TEXT, disabled INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY,value REAL); CREATE TABLE IF NOT EXISTS workers(name TEXT PRIMARY KEY,used INTEGER DEFAULT 0);')
  if 'cooldown_until_epoch' not in {row[1] for row in c.execute('PRAGMA table_info(slots)')}:c.execute('ALTER TABLE slots ADD COLUMN cooldown_until_epoch REAL DEFAULT 0')
  for i,s in enumerate(slots):c.execute('INSERT OR IGNORE INTO slots(name,ordinal,used) VALUES(?,?,?)',(s,i,prior_usage.get(s,0)))
  for slot,row in prior_backpressure.get('slots',{}).items():c.execute('UPDATE slots SET disabled=MAX(disabled,?),cooldown_until_epoch=MAX(cooldown_until_epoch,?) WHERE name=?',(int(row['disabled']),row['cooldown_until_epoch'],slot))
  for k,v in {'sequence':0,'cooldown':0,'text_limit':text_limit,'image_limit':image_limit,'max_calls':max_calls,'per_worker':per_worker,'calls':0,'peak_text_leases':0,'peak_image_leases':0}.items():c.execute('INSERT OR IGNORE INTO meta VALUES(?,?)',(k,v))
  c.execute("UPDATE meta SET value=MAX(value,?) WHERE name='cooldown'",(prior_backpressure.get('shared_cooldown_until_epoch',0),))

def snapshot(path):
 with connect(path) as c:
  m=dict(c.execute('SELECT name,value FROM meta'));rows=[dict(r) for r in c.execute('SELECT name,used,disabled,kind,cooldown_until_epoch FROM slots ORDER BY ordinal')]
 return {'model_requests_reserved':int(m['calls']),'cooldown_until_epoch':m['cooldown'],'slots':rows,'secret_values_stored':False,'peak_text_leases':int(m.get('peak_text_leases',0)),'peak_image_leases':int(m.get('peak_image_leases',0))}

def defer_slot(path,slot,seconds=3600):
 if slot not in SLOTS:raise ValueError('Unknown cooldown slot')
 if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:raise ValueError('Invalid slot cooldown')
 with connect(path) as c:c.execute('UPDATE slots SET cooldown_until_epoch=MAX(cooldown_until_epoch,?) WHERE name=?',(time.time()+max(60,seconds),slot))

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
    row=c.execute('SELECT name FROM slots WHERE name IN ('+q+') AND owner IS NULL AND disabled=0 AND cooldown_until_epoch<=? ORDER BY used,ordinal LIMIT 1',list(eligible)+[time.time()]).fetchone()
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

def validate_backpressure(row):
 if not isinstance(row,dict) or set(row)-{'slots','shared_cooldown_until_epoch'}:raise ValueError('Invalid durable key backpressure')
 def epoch(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
 if not epoch(row.get('shared_cooldown_until_epoch',0)):raise ValueError('Invalid shared cooldown')
 slots=row.get('slots',{})
 if not isinstance(slots,dict):raise ValueError('Invalid slot backpressure')
 for name,hold in slots.items():
  if name not in SLOTS or not isinstance(hold,dict) or set(hold)!={'disabled','cooldown_until_epoch'} or type(hold['disabled']) is not bool or not epoch(hold['cooldown_until_epoch']):raise ValueError('Invalid slot backpressure')
 return row

def routing_backpressure(out):
 from .queue import load_json
 p=Path(out)/'parallel/key-routing.json'
 return validate_backpressure(load_json(p).get('backpressure',{})) if p.exists() else {}

def record_routing(out,state):
 from .queue import atomic_json,utcnow
 rows={r['name']:int(r['used']) for r in state['slots']}
 prior=routing_counts(out)
 if any(k in rows and rows[k]<v for k,v in prior.items()):raise ValueError('Key routing counters regressed')
 # Ineligible/disabled old slots may be absent from this run, but their counts survive.
 rows=dict(prior,**rows)
 prior_hold=routing_backpressure(out)
 holds=dict(prior_hold.get('slots',{}))
 for row in state['slots']:
  name=row['name'];old=holds.get(name,{'disabled':False,'cooldown_until_epoch':0})
  disabled=row.get('disabled',0)
  if type(disabled) not in (bool,int) or disabled not in (0,1):raise ValueError('Invalid slot disabled state')
  hold={'disabled':bool(disabled) or old['disabled'],'cooldown_until_epoch':max(row.get('cooldown_until_epoch',0),old['cooldown_until_epoch'])}
  if hold['disabled'] or hold['cooldown_until_epoch']:holds[name]=hold
 backpressure=validate_backpressure({'slots':holds,'shared_cooldown_until_epoch':max(state.get('cooldown_until_epoch',0),prior_hold.get('shared_cooldown_until_epoch',0))})
 atomic_json(Path(out)/'parallel/key-routing.json',{'updated_at':utcnow(),'slot_request_counts':rows,'backpressure':backpressure,'secret_values_stored':False})
