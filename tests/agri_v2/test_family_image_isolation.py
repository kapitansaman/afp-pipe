import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2 import image_key_routing as r,parallel_controller as c

class FamilyImageIsolationTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','AFP_PARALLEL_WORKER':'1','AFP_PARALLEL_POOL_DB':'/tmp/test-pool.db','AFP_PARALLEL_TOPIC':'agri-000000000001'}
 def test_verified_parallel_path_accepts_slot97_but_legacy_does_not(self):
  pool=[('AGNES_API_KEY97','synthetic-test-only')];self.assertEqual(r.choose(pool,0,[],1,r.allowed_slots(self.env()))[0][0],'AGNES_API_KEY97')
  with self.assertRaises(r.AdmissionBlocked):r.choose(pool,0,[],1)
 def test_expansion_does_not_bypass_shared_billing_hold(self):
  with self.assertRaises(r.AdmissionBlocked):r.choose([('AGNES_API_KEY97','synthetic-test-only')],0,[{'shared_block':'billing_required'}],1,r.allowed_slots(self.env()))
 def test_other_repository_does_not_gain_extended_slots(self):
  env=dict(self.env(),GITHUB_REPOSITORY='getsalet/nono')
  with self.assertRaises(r.AdmissionBlocked):r.choose([('AGNES_API_KEY97','test-only')],0,[],1,r.allowed_slots(env))
 def test_worker_receives_only_owned_output_context_and_no_wp_secrets(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);d=p/'data';o=p/'out';w=p/'workspace';ident='agri-000000000001';other='agri-000000000002';atomic_json(d/'config.json',{});atomic_json(d/'briefs'/(ident+'.json'),{'owned':True});atomic_json(d/'briefs'/(other+'.json'),{'not_owned':True});atomic_json(o/'new'/ident/'own.json',{'owned':True});atomic_json(o/'new'/other/'foreign.json',{'foreign':True})
   def launch(*args,**kwargs):
    env=kwargs['env'];wo=Path(env['AFP_AGRI_OUT_DIR']);wd=Path(env['AFP_AGRI_DATA_DIR']);self.assertFalse((wo/'new'/other).exists());self.assertFalse((wd/'briefs'/(other+'.json')).exists());self.assertNotIn('AFP_WP_APP_PASSWORD',env);self.assertNotIn('AFP_WP_USERNAME',env);atomic_json(wo/'worker-result.json',{'topic_id':ident,'status':'research_ready'});return Mock(returncode=0)
   with patch.object(c.subprocess,'run',side_effect=launch):
    _,wd,wo,result=c.launch_worker({'id':ident,'title':'Own exact title','family_id':'family-01'},w,p/'pool.db',{}, {},d,o,{'GITHUB_RUN_ID':'999','AFP_WP_USERNAME':'synthetic','AFP_WP_APP_PASSWORD':'synthetic'})
   ctx=load_json(wo/'new'/ident/'family-context/999.json');self.assertEqual(ctx['topic_id'],ident);self.assertEqual(ctx['family_id'],'family-01');self.assertEqual(ctx['title'],'Own exact title')
