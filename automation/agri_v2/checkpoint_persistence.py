"""Path-scoped Git transaction. No worktree/index reset; deletions survive.
The remote run fence closes in the SAME commit as all observed worker state.
"""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
from .queue import ROOT
from .parallel_control import BRANCH
from .execution_recovery import FLIGHT,checkpoint_candidate
REF='refs/afp/agri-v2-checkpoint'
SCOPES=('artifacts/agri-v2','data/agri-v2/config.json','data/agri-v2/briefs','data/agri-v2/health/latest.json',FLIGHT)

def git(args,root,env=None,data=None,check=True):
 r=subprocess.run(['git',*args],cwd=root,env=env,input=data,capture_output=True,timeout=120)
 if check and r.returncode:raise RuntimeError('Agriculture checkpoint failed at '+args[0]+'; local evidence retained')
 return r

def allowed(path):
 p=Path(path)
 return not p.is_absolute() and '..' not in p.parts and any(path==scope or path.startswith(scope+'/') for scope in SCOPES) and p.name!='.writer.lock' and not p.name.startswith(('.tmp-','.checkpoint-'))

def entries(root,ref,paths):
 if not paths:return {}
 raw=git(['ls-tree','-r','-z',ref,'--',*paths],root).stdout;values={}
 for row in raw.split(b'\0'):
  if row:
   meta,name=row.split(b'\t',1);values[name.decode()]=meta.split()[2].decode()
 return values

def changed_paths(root,baseline):
 paths=set()
 for args in (['diff','--name-only','-z',baseline,'--',*SCOPES],['ls-files','-z','--others','--exclude-standard','--',*SCOPES],['ls-files','-z','--others','--ignored','--exclude-standard','--',*SCOPES]):
  paths.update(p.decode() for p in git(args,root).stdout.split(b'\0') if p)
 return sorted(p for p in paths if allowed(p))

def persist(root=ROOT,env=None,push_fn=None):
 root=Path(root);env=dict(os.environ if env is None else env)
 baseline=REF if git(['rev-parse','--verify',REF],root,check=False).returncode==0 else 'HEAD'
 paths=changed_paths(root,baseline);closing,flight_before=checkpoint_candidate(root,env)
 flight=root/FLIGHT
 # A local in-flight record without a matching admission is NOT authority to
 # alter or clear the remote fence. Other evidence may still be checkpointed.
 if flight.exists():
  row=json.loads(flight.read_text())
  if row.get('status')=='in_flight' and flight_before is None:paths=[p for p in paths if p!=FLIGHT]
 if closing is not None and FLIGHT not in paths:paths.append(FLIGHT)
 if not paths:return None
 baseline_state={p:b for p,b in entries(root,baseline,SCOPES).items() if allowed(p)}
 before=entries(root,baseline,paths);desired={}
 for p in paths:
  path=root/p
  if path.is_symlink() or path.exists() and not path.is_file():raise RuntimeError('Only scoped regular files and tracked deletions may be checkpointed')
  desired[p]=git(['hash-object','-w','--stdin'],root,data=path.read_bytes()).stdout.decode().strip() if path.exists() else None
 if flight_before is not None:
  before[FLIGHT]=flight_before;baseline_state[FLIGHT]=flight_before
  if closing is None:desired[FLIGHT]=flight_before
 closed_bytes=None
 if closing is not None:
  binding={'baseline':git(['rev-parse',baseline],root).stdout.decode().strip(),'scoped_changes':{p:v for p,v in desired.items() if p!=FLIGHT}}
  closing['checkpoint_digest']=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
  closed_bytes=(json.dumps(closing,ensure_ascii=False,indent=2)+'\n').encode()
  desired[FLIGHT]=git(['hash-object','-w','--stdin'],root,data=closed_bytes).stdout.decode().strip()
 with tempfile.TemporaryDirectory(prefix='afp-agri-checkpoint-') as tmp:
  git_env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'),GIT_AUTHOR_NAME='github-actions[bot]',GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',GIT_COMMITTER_NAME='github-actions[bot]',GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
  for attempt in range(3):
   git(['fetch','--quiet','origin',BRANCH],root)
   parent=git(['rev-parse','origin/'+BRANCH],root).stdout.decode().strip();remote=entries(root,parent,paths)
   # A push can have succeeded before its acknowledgement/local ref update.
   # Adopt that exact already-durable closing record, never re-run the work.
   if closing is not None and remote.get(FLIGHT) not in (before.get(FLIGHT),desired[FLIGHT]):
    raw=git(['show',parent+':'+FLIGHT],root).stdout
    try:prior=json.loads(raw)
    except ValueError:raise RuntimeError('Invalid concurrent lifecycle fence') from None
    if prior.get('status')=='checkpointed' and prior.get('run_id')==closing['run_id'] and prior.get('checkpoint_digest')==closing['checkpoint_digest']:
     desired[FLIGHT]=remote[FLIGHT];closed_bytes=raw
   remote_state={p:b for p,b in entries(root,parent,SCOPES).items() if allowed(p)}
   if any(remote_state.get(p) not in (baseline_state.get(p),desired.get(p,baseline_state.get(p))) for p in set(baseline_state)|set(remote_state)):raise RuntimeError('Concurrent agriculture state changed; local evidence retained')
   if any(remote.get(p) not in (before.get(p),desired[p]) for p in paths):raise RuntimeError('Concurrent agriculture checkpoint edit; no overwrite; local evidence retained')
   if all(remote.get(p)==desired[p] for p in paths):commit=parent
   else:
    git(['read-tree',parent],root,git_env)
    records=b''.join(((b'0 '+b'0'*40) if blob is None else b'100644 '+blob.encode())+b'\t'+p.encode()+b'\0' for p,blob in desired.items())
    git(['update-index','-z','--index-info'],root,git_env,records)
    tree=git(['write-tree'],root,git_env).stdout.decode().strip()
    commit=git(['commit-tree',tree,'-p',parent],root,git_env,b'Record bounded agriculture checkpoints and lifecycle fence [skip ci]\n').stdout.decode().strip()
    success=(git(['push','--quiet','origin',commit+':refs/heads/'+BRANCH],root,check=False).returncode==0) if push_fn is None else push_fn(commit,attempt)
    if not success:continue
   git(['update-ref',REF,commit],root)
   if closed_bytes is not None:
    # Keep the local fence consistent for a second persistence pass; the
    # published Git tree is already complete before this local convenience.
    fd,name=tempfile.mkstemp(prefix='.tmp-',dir=flight.parent)
    try:
     with os.fdopen(fd,'wb') as handle:handle.write(closed_bytes);handle.flush();os.fsync(handle.fileno())
     os.replace(name,flight)
    finally:
     if os.path.exists(name):os.unlink(name)
   return commit
 raise RuntimeError('Agriculture checkpoint push unconfirmed; fence and local evidence retained')

def main():
 commit=persist();print('Agriculture checkpoint: '+str(commit or 'no scoped changes'))
if __name__=='__main__':main()
