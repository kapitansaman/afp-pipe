"""Repository-wide FIFO admission and atomic Git-ref mutex for blog image calls.
No image credential, prompt, response body or post HTML is stored in queue refs.
Only completed Actions owners can be reclaimed; a stale lock has a 30-minute
quarantine. Missing permissions, unreadable state and ambiguous ownership fail closed.
"""
import contextlib,datetime,json,os,random,re,time,urllib.error,urllib.request,uuid
API='https://api.github.com/repos/kapitansaman/afp-pipe'
PREFIX='heads/afp-blog-image-queue/'
LOCK='heads/afp-blog-image-provider-lock-v1'
MESSAGE='AFP blog image lease v1\n'
MAX_WAIT=180;MIN_INTERVAL=60;STALE_QUIET=1800

class ImageQueueBusy(RuntimeError):
 def __init__(self):
  self.retry_at=time.time()+60
  super().__init__('Shared image queue occupied; saved draft deferred, no provider request')

class Client:
 def __init__(self):
  self.token=os.getenv('BLOG_IMAGE_QUEUE_TOKEN','')
  if not self.token:raise RuntimeError('Shared image queue credential unavailable; no provider request')
 def call(self,method,path,data=None,allowed=(200,201,204)):
  if not path.startswith('/'):raise ValueError('Repository-relative queue API path required')
  request=urllib.request.Request(API+path,method=method,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'},data=json.dumps(data).encode()if data is not None else None)
  try:
   with urllib.request.urlopen(request,timeout=25)as response:
    status=response.status;raw=response.read(2*1024*1024)
  except urllib.error.HTTPError as exc:
   status=exc.code;exc.close();raw=b''
  except Exception:raise RuntimeError('Shared image queue API transport uncertain; no provider request')from None
  if status not in allowed:raise RuntimeError('Shared image queue API HTTP '+str(status)+'; no provider request')
  if not raw:return status,None
  try:return status,json.loads(raw)
  except ValueError:raise RuntimeError('Shared image queue API response invalid; no provider request')from None

class Queue:
 def __init__(self,client=None,run=None,source=None,wait=MAX_WAIT,poll=15,minimum_interval=MIN_INTERVAL,attempt=None):
  self.client=client or Client();self.run=run or os.getenv('GITHUB_RUN_ID','');self.source=source or os.getenv('GITHUB_SHA','')
  self.attempt=attempt or os.getenv('GITHUB_RUN_ATTEMPT','1')
  if not re.fullmatch(r'[1-9][0-9]*',self.attempt):raise RuntimeError('Verified Actions attempt required')
  if not re.fullmatch(r'[0-9]+',self.run)or not re.fullmatch(r'[a-f0-9]{40}',self.source):raise RuntimeError('Verified Actions queue owner and source required')
  self.wait=wait;self.poll=poll;self.minimum_interval=minimum_interval;self.retain=False
  self.ticket=PREFIX+f'{int(time.time()*1000):013d}-'+self.run+'-'+self.attempt+'-'+uuid.uuid4().hex
  self.sha=None;self.acquired_at=None
 def get_ref(self,ref):
  if ref!=LOCK and not ref.startswith(PREFIX):raise ValueError('Unknown queue ref')
  status,row=self.client.call('GET','/git/ref/'+ref,allowed=(200,404))
  if status==404:return None
  sha=row.get('object',{}).get('sha')
  if not re.fullmatch(r'[a-f0-9]{40}',str(sha)):raise RuntimeError('Invalid queue ref ownership')
  return sha
 def delete_owned(self,ref,sha):
  if self.get_ref(ref)!=sha:return False
  self.client.call('DELETE','/git/refs/'+ref,allowed=(204,404));return True
 def owner(self,sha):
  _,commit=self.client.call('GET','/git/commits/'+sha)
  message=commit.get('message','')
  if not message.startswith(MESSAGE):raise RuntimeError('Unknown lock owner; manual review required')
  try:owner=json.loads(message[len(MESSAGE):])
  except ValueError:raise RuntimeError('Unreadable lock owner; manual review required')from None
  if not re.fullmatch(r'[0-9]+',str(owner.get('run_id','')))or not re.fullmatch(r'[1-9][0-9]*',str(owner.get('attempt','')))or not str(owner.get('ticket','')).startswith(PREFIX):raise RuntimeError('Unverified queue owner')
  return owner
 def completed(self,run,attempt,quarantine=False):
  _,record=self.client.call('GET','/actions/runs/'+run+'/attempts/'+attempt)
  if record.get('status')!='completed':return False
  if not quarantine:return True
  try:ended=datetime.datetime.fromisoformat(record['updated_at'].replace('Z','+00:00')).timestamp()
  except (KeyError,ValueError,TypeError):return False
  return time.time()-ended>=STALE_QUIET
 def clean_and_list(self):
  _,refs=self.client.call('GET','/git/matching-refs/'+PREFIX+'?per_page=100')
  if not isinstance(refs,list)or len(refs)>=100:raise RuntimeError('Image queue listing incomplete; no provider request')
  tickets=[]
  for row in refs:
   ref=str(row.get('ref','')).removeprefix('refs/');sha=row.get('object',{}).get('sha')
   if not ref.startswith(PREFIX)or not re.fullmatch(r'[a-f0-9]{40}',str(sha)):raise RuntimeError('Invalid image queue ticket')
   name=ref[len(PREFIX):]
   if not re.fullmatch(r'[0-9]{13}-[0-9]+-[1-9][0-9]*-[a-f0-9]{32}',name):raise RuntimeError('Unknown image queue ticket; no provider request')
   run,attempt=name.split('-')[1:3]
   if ref!=self.ticket and self.completed(run,attempt):self.delete_owned(ref,sha)
   else:tickets.append(ref)
  return sorted(tickets)
 def create_ticket(self,blog,asset):
  if not re.fullmatch(r'[a-z0-9_-]{1,40}',blog)or not re.fullmatch(r'[a-f0-9]{32}',asset):raise ValueError('Safe queue identity required')
  _,commit=self.client.call('GET','/git/commits/'+self.source)
  _,row=self.client.call('POST','/git/commits',{'tree':commit['tree']['sha'],'parents':[self.source],'message':MESSAGE+json.dumps({'run_id':self.run,'attempt':self.attempt,'ticket':self.ticket,'blog':blog,'asset_id':asset,'created_at_epoch':time.time()},sort_keys=True)})
  self.sha=row.get('sha')
  if not re.fullmatch(r'[a-f0-9]{40}',str(self.sha)):raise RuntimeError('Queue ticket commit unavailable')
  self.client.call('POST','/git/refs',{'ref':'refs/'+self.ticket,'sha':self.sha},allowed=(201,))
 def try_lock(self):
  status,_=self.client.call('POST','/git/refs',{'ref':'refs/'+LOCK,'sha':self.sha},allowed=(201,422))
  if status==201:
   if self.get_ref(LOCK)!=self.sha:raise RuntimeError('Atomic lock ownership not confirmed')
   self.acquired_at=time.monotonic();return True
  sha=self.get_ref(LOCK)
  if sha:
   owner=self.owner(sha)
   # Never steal a live owner's lock, even if a nominal timeout has elapsed.
   if (owner['run_id']!=self.run or owner['attempt']!=self.attempt)and self.completed(owner['run_id'],owner['attempt'],quarantine=True):self.delete_owned(LOCK,sha)
  return False
 @contextlib.contextmanager
 def slot(self,blog,asset):
  deadline=time.monotonic()+self.wait
  try:
   self.create_ticket(blog,asset)
   while True:
    tickets=self.clean_and_list()
    if tickets and tickets[0]==self.ticket and self.try_lock():break
    if time.monotonic()>=deadline:raise ImageQueueBusy()
    time.sleep(min(self.poll+random.uniform(0,2),max(0,deadline-time.monotonic())))
   yield self
  finally:
   # If release is uncertain, leave refs for conservative completed-owner recovery.
   # No other runner may remove or replace a live owner's lock.
   if self.sha and not self.retain:
    if self.acquired_at is not None:time.sleep(max(0,self.minimum_interval-(time.monotonic()-self.acquired_at)))
    self.delete_owned(LOCK,self.sha)
    self.delete_owned(self.ticket,self.sha)

@contextlib.contextmanager
def provider_slot(blog,asset):
 # Production is hosted in Actions. Offline/local unit fixtures have no Git ref writes.
 if os.getenv('GITHUB_ACTIONS')!='true':yield None;return
 if os.getenv('BLOG_IMAGE_QUEUE_ENABLED')!='1':raise RuntimeError('Hosted image queue not configured; no provider request')
 queue=Queue()
 with queue.slot(blog,asset):yield queue
