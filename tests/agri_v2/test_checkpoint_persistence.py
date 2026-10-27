import base64,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import checkpoint_persistence as p,execution_recovery as recovery
from automation.agri_v2.queue import atomic_json,load_json

class CheckpointPersistenceTests(unittest.TestCase):
 def git(self,root,*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
 def setup(self,root):
  remote=root/'remote.git';remote.mkdir();self.git(remote,'init','--bare');work=root/'work';work.mkdir();self.git(work,'init');self.git(work,'config','user.name','Offline tester');self.git(work,'config','user.email','offline@example.invalid')
  atomic_json(work/'artifacts/agri-v2/new/agri-000000000001/old.json',{'old':True});(work/'unrelated.txt').write_text('original');self.git(work,'add','.');self.git(work,'commit','-m','initial');self.git(work,'branch','-M',p.BRANCH);self.git(work,'remote','add','origin',str(remote));self.git(work,'push','-u','origin',p.BRANCH)
  return remote,work
 def remote_commit(self,remote):return self.git(remote,'rev-parse','refs/heads/'+p.BRANCH)
 def test_deletion_and_archive_are_committed_together_without_resurrection(self):
  with tempfile.TemporaryDirectory() as td:
   remote,work=self.setup(Path(td));folder=work/'artifacts/agri-v2/new/agri-000000000001';old=folder/'old.json';archive=folder/'lifecycle/text/rejected/1/old.json';archive.parent.mkdir(parents=True);old.rename(archive)
   head=self.git(work,'rev-parse','HEAD');p.persist(work,{})
   tree=self.git(remote,'ls-tree','-r','--name-only',self.remote_commit(remote));self.assertNotIn(str(old.relative_to(work)),tree.splitlines());self.assertIn(str(archive.relative_to(work)),tree.splitlines());self.assertFalse(old.exists());self.assertEqual(self.git(work,'rev-parse','HEAD'),head)
 def test_unrelated_worktree_and_index_are_untouched(self):
  with tempfile.TemporaryDirectory() as td:
   remote,work=self.setup(Path(td));(work/'unrelated.txt').write_text('staged secret-free unrelated edit');self.git(work,'add','unrelated.txt');before=(work/'.git/index').read_bytes();atomic_json(work/'artifacts/agri-v2/new/agri-000000000001/result.json',{'good':True});p.persist(work,{})
   self.assertEqual((work/'.git/index').read_bytes(),before);self.assertEqual((work/'unrelated.txt').read_text(),'staged secret-free unrelated edit');self.assertEqual(self.git(remote,'show',self.remote_commit(remote)+':unrelated.txt'),'original')
 def test_push_failure_retains_local_outputs_and_deletions_for_recovery(self):
  with tempfile.TemporaryDirectory() as td:
   remote,work=self.setup(Path(td));old=work/'artifacts/agri-v2/new/agri-000000000001/old.json';old.unlink();new=old.with_name('saved.json');atomic_json(new,{'keep':True});remote_before=self.remote_commit(remote)
   with self.assertRaises(RuntimeError):p.persist(work,{},push_fn=lambda *_:False)
   self.assertFalse(old.exists());self.assertTrue(new.exists());self.assertEqual(self.remote_commit(remote),remote_before)
 def test_concurrent_same_path_change_never_overwritten(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);remote,work=self.setup(root);other=root/'other';self.git(root,'clone','--branch',p.BRANCH,str(remote),str(other));self.git(other,'config','user.name','Other');self.git(other,'config','user.email','other@example.invalid');rel='artifacts/agri-v2/new/agri-000000000001/old.json';atomic_json(other/rel,{'remote':True});self.git(other,'add','.');self.git(other,'commit','-m','concurrent');self.git(other,'push');atomic_json(work/rel,{'local':True})
   with self.assertRaises(RuntimeError):p.persist(work,{})
   self.assertEqual(load_json(work/rel),{'local':True});self.assertIn('remote',self.git(remote,'show',self.remote_commit(remote)+':'+rel))
 def test_unrelated_remote_commit_survives_checkpoint(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);remote,work=self.setup(root);other=root/'other';self.git(root,'clone','--branch',p.BRANCH,str(remote),str(other));self.git(other,'config','user.name','Other');self.git(other,'config','user.email','other@example.invalid');(other/'remote-only.txt').write_text('preserved');self.git(other,'add','.');self.git(other,'commit','-m','unrelated');self.git(other,'push');atomic_json(work/'artifacts/agri-v2/new/agri-000000000001/result.json',{'local':True});p.persist(work,{})
   self.assertEqual(self.git(remote,'show',self.remote_commit(remote)+':remote-only.txt'),'preserved')
 def test_second_pass_is_idempotent(self):
  with tempfile.TemporaryDirectory() as td:
   remote,work=self.setup(Path(td));atomic_json(work/'artifacts/agri-v2/new/agri-000000000001/result.json',{'new':True});first=p.persist(work,{});second=p.persist(work,{});self.assertEqual(self.remote_commit(remote),first);self.assertIn(second,(None,first))
 def prepare_fence(self,work):
  data=work/'data/agri-v2';out=work/'artifacts/agri-v2';atomic_json(data/'execution-recovery-policy.json',recovery.POLICY);env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':recovery.REPO,'GITHUB_RUN_ID':'123','GITHUB_TOKEN':'test-only'};topics=[{'id':'agri-000000000001','family_id':'family-01'}]
  def call(method,payload=None):
   if method=='GET':return None
   raw=base64.b64decode(payload['content']);path=work/recovery.FLIGHT;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);self.git(work,'add',recovery.FLIGHT);self.git(work,'commit','-m','remote intent');self.git(work,'push');return {'content':{'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}}
  recovery.begin(env,topics,data,out,call)
  report={'run_id':'123','status':'completed','results':[{'topic_id':topics[0]['id'],'status':'blocked','checkpoint_merged':True}]};atomic_json(out/'parallel/lifecycle/runs/123/report.json',report)
  return env,out
 def test_fence_closes_only_in_same_commit_as_all_results(self):
  with tempfile.TemporaryDirectory() as td:
   remote,work=self.setup(Path(td));env,out=self.prepare_fence(work);commit=p.persist(work,env);row=json.loads(self.git(remote,'show',commit+':'+recovery.FLIGHT));self.assertEqual(row['status'],'checkpointed');self.assertTrue(row['all_selected_workers_merged']);self.assertEqual(len(row['checkpoint_digest']),64);self.assertEqual(self.git(remote,'show',commit+':artifacts/agri-v2/parallel/lifecycle/runs/123/report.json'),(out/'parallel/lifecycle/runs/123/report.json').read_text().strip())
 def test_missing_worker_and_push_failure_keep_remote_fence_inflight(self):
  for missing in (True,False):
   with self.subTest(missing=missing),tempfile.TemporaryDirectory() as td:
    remote,work=self.setup(Path(td));env,out=self.prepare_fence(work)
    if missing:atomic_json(out/'parallel/lifecycle/runs/123/report.json',{'run_id':'123','status':'completed','results':[]});p.persist(work,env)
    else:
     with self.assertRaises(RuntimeError):p.persist(work,env,push_fn=lambda *_:False)
    row=json.loads(self.git(remote,'show',self.remote_commit(remote)+':'+recovery.FLIGHT));self.assertEqual(row['status'],'in_flight')
 def test_lost_push_acknowledgement_adopts_durable_result_without_replay(self):
  with tempfile.TemporaryDirectory() as td:
   remote,work=self.setup(Path(td));env,out=self.prepare_fence(work);calls=[]
   def lost_ack(commit,attempt):calls.append(commit);self.git(work,'push','origin',commit+':refs/heads/'+p.BRANCH);return False
   result=p.persist(work,env,push_fn=lost_ack);self.assertEqual(len(calls),1);self.assertEqual(result,self.remote_commit(remote));self.assertEqual(load_json(work/recovery.FLIGHT)['status'],'checkpointed')

 def test_crash_after_remote_commit_before_local_ref_update_is_recoverable(self):
  with tempfile.TemporaryDirectory() as td:
   remote,work=self.setup(Path(td));env,out=self.prepare_fence(work);original=p.git;crashed=[]
   def crash(args,*a,**kw):
    if args[0]=='update-ref' and not crashed:crashed.append(True);raise RuntimeError('simulated process crash')
    return original(args,*a,**kw)
   with patch.object(p,'git',side_effect=crash),self.assertRaises(RuntimeError):p.persist(work,env)
   self.assertEqual(json.loads(self.git(remote,'show',self.remote_commit(remote)+':'+recovery.FLIGHT))['status'],'checkpointed');self.assertEqual(load_json(work/recovery.FLIGHT)['status'],'in_flight')
   committed=self.remote_commit(remote);self.assertEqual(p.persist(work,env),committed);self.assertEqual(load_json(work/recovery.FLIGHT)['status'],'checkpointed')
 def test_remote_ownership_change_blocks_even_if_local_assignment_unchanged(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);remote,work=self.setup(root);other=root/'other';self.git(root,'clone','--branch',p.BRANCH,str(remote),str(other));self.git(other,'config','user.name','Other');self.git(other,'config','user.email','other@example.invalid');atomic_json(other/'artifacts/agri-v2/parallel/families/assignments.json',{'changed':True});self.git(other,'add','.');self.git(other,'commit','-m','new ownership');self.git(other,'push');atomic_json(work/'artifacts/agri-v2/new/agri-000000000001/result.json',{'local':True})
   with self.assertRaises(RuntimeError):p.persist(work,{})
   self.assertTrue((work/'artifacts/agri-v2/new/agri-000000000001/result.json').exists())
