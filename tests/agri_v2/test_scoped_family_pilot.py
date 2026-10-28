import tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import scoped_family_pilot as p,family_lifecycle as f,family_capability_refresh as cap
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.pipeline import digest
from automation.agri_v2.healthcheck import IMAGE_MODEL
from tests.agri_v2 import test_family_capability_refresh as fixtures
class ScopedPilotTests(unittest.TestCase):
 def setup(self,root):
  fix=fixtures.CapabilityRefreshTests();d,o,e,roles=fix.setup(root);cap.text(e,d,o,fix.post,Mock(return_value={}));cap.images(e,d,o,fix.probe,Mock(return_value={}))
  atomic_json(d/'family-lifecycle-policy.json',{'version':1,'enabled':True,'publication_enabled':True,'max_families':20,'max_attempts_per_stage':3,'max_model_requests_per_family':14,'max_published_families':20,'preserve_legacy_budgets':True,'research_only_for_scoped_rollout':True});atomic_json(d/'config.json',{'multilingual':{'enabled':False}})
  topics=[{'id':'agri-'+format(i+1,'012x'),'title':'Original topic '+str(i),'crop':'bean','intent':'storage','family_id':'family-'+str(i+1).zfill(2)} for i in range(2)]
  for t in topics:atomic_json(d/'briefs'/(t['id']+'.json'),{'topic_id':t['id'],'review_mode':'automated_scoped_evidence_review_v1','publish_authorized':True})
  e['AFP_SCOPED_FAMILY_PILOT']='1';return d,o,e,roles,topics
 def choose(self,ts,e,d,o):
  with patch.object(p,'check_brief'),patch.object(f,'next_stage',return_value=('text',None)):return p.choose(ts,e,d,o)
 def test_choose_one_stable_owned_family_and_do_not_change_global_hold(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));before=(d/'family-lifecycle-policy.json').read_bytes();r=self.choose(ts,e,d,o);self.assertEqual(r,[ts[0]]);self.assertEqual((d/'family-lifecycle-policy.json').read_bytes(),before);self.assertFalse(load_json(o/p.BASE/'current.json')['original_attempts_reset'])
 def test_exhausted_stage_not_reopened_or_reset(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));file=o/'new'/ts[0]['id']/'lifecycle/text/state.json';atomic_json(file,{'attempts':3,'history':['preserved']});before=file.read_bytes()
   with self.assertRaises(ValueError):self.choose(ts[:1],e,d,o)
   self.assertEqual(file.read_bytes(),before)
 def test_prior_pilot_does_not_silently_switch_family_after_failure(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));self.choose(ts,e,d,o)
   with patch.object(p,'check_brief'),patch.object(f,'next_stage',return_value=('blocked','quality_hold')),self.assertRaises(ValueError):p.choose(ts,e,d,o)
   self.assertEqual(load_json(o/p.BASE/'current.json')['topic_id'],ts[0]['id'])
 def test_worker_admission_binds_run_topic_family_and_brief(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));self.choose(ts,e,d,o);admission=load_json(o/p.BASE/'admissions'/(e['GITHUB_RUN_ID']+'.json'));atomic_json(d/'status/scoped-family-pilot-admission.json',admission);self.assertTrue(p.bound(e,ts[0],d));self.assertFalse(p.bound(dict(e,GITHUB_RUN_ID='999'),ts[0],d));self.assertFalse(p.bound(e,ts[1],d));atomic_json(d/'briefs'/(ts[0]['id']+'.json'),{'changed':True});self.assertFalse(p.bound(e,ts[0],d))
 def test_pilot_flag_alone_never_grants_worker_exception(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));e.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_TOPIC=ts[0]['id']);factory=Mock()
   with self.assertRaises(f.StageBlocked):f.worker(ts[0],load_json(o/'parallel/health/latest.json'),d,o,e,factory)
   factory.assert_not_called()
 def test_only_bound_pilot_can_cross_research_text_gate(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));self.choose(ts,e,d,o);atomic_json(d/'status/scoped-family-pilot-admission.json',load_json(o/p.BASE/'admissions'/(e['GITHUB_RUN_ID']+'.json')));e.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_TOPIC=ts[0]['id']);h=load_json(o/'parallel/health/latest.json')
   with patch.object(f,'next_stage',return_value=('text',None)),patch.object(f,'run_stage') as stage:r=f.worker(ts[0],h,d,o,dict(e,AFP_SCOPED_FAMILY_PILOT=''),Mock());self.assertEqual(r['status'],'research_ready');stage.assert_not_called()
   with patch.object(f,'next_stage',side_effect=[('text',None),('publish',None)]),patch.object(f,'run_stage',return_value={}) as stage:r=f.worker(ts[0],h,d,o,e,Mock());self.assertEqual(r['status'],'publication_ready');stage.assert_called_once()
 def test_missing_actual_image_proof_cannot_select_pilot(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));(o/'parallel/runtime/image'/('AGNES_API_KEY4.json')).unlink()
   with self.assertRaises(ValueError):self.choose(ts[:1],e,d,o)
 def test_missing_public_receipt_never_claims_acceptance(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));self.choose(ts,e,d,o);wp=Mock();r=p.accept(ts[0],wp,d,o);self.assertEqual(r['status'],'pilot_not_yet_publicly_verified');self.assertFalse(r['global_rollout_released']);wp.verify.assert_not_called();self.assertFalse((o/p.BASE/'accepted.json').exists())
 def test_image_qa_rejection_still_blocks_acceptance(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));self.choose(ts,e,d,o);atomic_json(o/'new'/ts[0]['id']/'wordpress-receipt.json',{'public_verified':True,'post_id':1});wp=Mock()
   with patch.object(p,'check_brief'),patch.object(f,'article_checked',return_value={}),patch('automation.agri_v2.image_quality.require_all',side_effect=ValueError('real QA required')),self.assertRaises(ValueError):p.accept(ts[0],wp,d,o)
   wp.verify.assert_not_called();self.assertFalse((o/p.BASE/'accepted.json').exists())
 def test_accepted_pilot_requires_bound_input_images_own_model_and_live_verification(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,e,roles,ts=self.setup(Path(td));t=ts[0];self.choose(ts,e,d,o);folder=o/'new'/t['id'];atomic_json(folder/'wordpress-receipt.json',{'public_verified':True,'post_id':1});(folder/'image-1.webp').write_bytes(b'synthetic QA-approved bytes');article={'title':'synthetic article'};brief=load_json(d/'briefs'/(t['id']+'.json'));atomic_json(folder/'lifecycle-publication-validation.json',{'brief_sha256':digest(brief),'article_sha256':digest(article),'image_sha256':{'1':hashlib.sha256((folder/'image-1.webp').read_bytes()).hexdigest()}});pp=o/'parallel/runtime/image/AGNES_API_KEY4.json';proof=load_json(pp);proof['topic_id']=t['id'];atomic_json(pp,proof);wp=Mock();wp.verify.return_value={'public_verified':True,'post_id':1,'url':'https://example.test/synthetic'}
   with patch.object(p,'check_brief'),patch.object(f,'article_checked',return_value=article),patch('automation.agri_v2.image_quality.require_all'),patch('automation.agri_v2.image_layout.roles_for',return_value=(1,)):r=p.accept(t,wp,d,o)
   wp.verify.assert_called_once();self.assertEqual(r['status'],'scoped_family_pilot_verified');self.assertEqual(r['image_slot'],'AGNES_API_KEY4');self.assertEqual(r['image_model'],IMAGE_MODEL);self.assertFalse(r['global_rollout_released']);self.assertTrue(load_json(d/'family-lifecycle-policy.json')['research_only_for_scoped_rollout'])
 def test_pilot_does_not_claim_manufacturer_or_human_review(self):
  root=Path(__file__).resolve().parents[2];self.assertIn('family-pilot',(root/'.github/workflows/afp-parallel-generator.yml').read_text());self.assertIn('exact_owned_scoped_pilot_admission_required',(root/'automation/agri_v2/family_lifecycle.py').read_text())
