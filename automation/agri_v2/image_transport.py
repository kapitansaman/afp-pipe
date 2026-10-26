"""Repository-wide admission for production image requests; no credential rotation on image errors."""
import contextlib,hashlib,json,os,subprocess,time
from .queue import ROOT
from automation.blog_image_queue import Queue,Client as LeaseClient
class AdmissionBlocked(ValueError):pass
def shared_evidence():
 # Read latest public routing/cooldown evidence; never read secret values from Git.
 subprocess.run(['git','fetch','--quiet','origin','main:refs/remotes/origin/main'],cwd=ROOT,check=True,capture_output=True)
 result=[]
 for path in ['data/agri-v2/key-backpressure.json']:
  p=subprocess.run(['git','show','origin/main:'+path],cwd=ROOT,check=True,capture_output=True)
  try:d=json.loads(p.stdout)
  except ValueError:raise AdmissionBlocked('Unreadable shared provider evidence') from None
  if not isinstance(d,dict):raise AdmissionBlocked('Invalid shared provider evidence')
  result.append(d)
 return result

def shared_guard(slot):
 from .image_key_routing import choose
 # Same classifier before and after the repository-wide lease.
 choose([(slot,'admission-placeholder')],0,shared_evidence(),time.time())

class TokenClient(LeaseClient):
 def __init__(self,token):
  if not token:raise AdmissionBlocked('GitHub image lease unavailable; no provider request')
  self.token=token
@contextlib.contextmanager
def admission(slot,payload,env):
 if env.get('GITHUB_ACTIONS')!='true':yield;return
 token=env.get('BLOG_IMAGE_QUEUE_TOKEN') or env.get('GITHUB_TOKEN')
 shared_guard(slot)
 ident=hashlib.sha256(payload['prompt'].encode()).hexdigest()[:32]
 with Queue(client=TokenClient(token)).slot('agri-v2',ident):
  shared_guard(slot)
  yield
