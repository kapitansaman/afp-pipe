import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import controlled_start as c
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.image_quality import REVIEW_POLICY,SCORE_POLICY
class ControlledStartTests(unittest.TestCase):
 def setup(self,tmp):
  root=Path(tmp);data=root/'data';out=root/'out';cfg={'repository':c.REPO,'credential_set_id':'test30','automatic_generation':True,'publication_enabled':True,'max_posts_per_run':1,'publication_holds':{'held':'retain'},'cutover':{'status':'ready_for_production'},'controlled_start':{'active':True,'request_id':c.ID,'max_cycles':1}}
  atomic_json(data/'config.json',cfg);atomic_json(data/'health/latest.json',{'repository':c.REPO,'credential_set_id':'test30','checked_at':utcnow(),'image_model':'agnes-image-2.5-flash','eligible_text_slots':['AGNES_API_KEY2'],'eligible_image_slots':['AGNES_API_KEY2','AGNES_API_KEY3']})
  rows=[]
  for slot in ('AGNES_API_KEY2','AGNES_API_KEY3'):
   image=out/'model-matrix'/c.MATRIX/(slot+'.webp');image.parent.mkdir(parents=True,exist_ok=True);image.write_bytes(b'fixture-'+slot.encode());rows.append({'model':'agnes-image-2.5-flash','slot':slot,'mode':'reference','state':'healthy','valid_image':True,'native_landscape_16_9':True,'image_path':str(image.relative_to(out)),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest()})
  matrix=out/'model-matrix'/c.MATRIX/'report.json';atomic_json(matrix,{'status':'completed','run_id':'123','cases':rows})
  proof=out/'activation-readiness'/c.ID/'report.json';atomic_json(proof,{'repository':c.REPO,'credential_set_id':'test30','checked_at':utcnow(),'source_paused':True,'matrix_run_conclusion':'success','matrix_run_id':'123','wordpress_connection':{'can_publish':True},'preserved_publication_holds':{'held':'retain'},'matrix_report_sha256':hashlib.sha256(matrix.read_bytes()).hexdigest()})
  req={'request_id':c.ID,'authorized':True,'mode':'one_manual_source_ready_critical_checks','max_posts_per_run':1,'max_cycles':1,'preserve_publication_holds':True,'review_policy':REVIEW_POLICY,'score_policy':SCORE_POLICY,'readiness_report_sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}
  return root,data,out,cfg,req
 def env(self,event='workflow_dispatch'):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':c.REPO,'GITHUB_EVENT_NAME':event,'GITHUB_RUN_ID':'123'}
 def test_fresh_matching_proofs_allow_only_quality_gated_pipeline(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,data,out,cfg,req=self.setup(tmp);self.assertTrue(c.authorized(req,data,out,root))
 def test_tampered_image_proof_blocks(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,data,out,cfg,req=self.setup(tmp);next((out/'model-matrix'/c.MATRIX).glob('*.webp')).write_bytes(b'changed')
   with self.assertRaises(ValueError):c.authorized(req,data,out,root)
 def test_preserved_hold_cannot_be_removed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,data,out,cfg,req=self.setup(tmp);cfg['publication_holds']={};atomic_json(data/'config.json',cfg)
   with self.assertRaises(ValueError):c.authorized(req,data,out,root)
 def test_cron_is_rejected_without_reserving_or_running(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,data,out,cfg,req=self.setup(tmp);remote=Mock();r=c.reserve(cfg,self.env('schedule'),remote);self.assertFalse(r['allowed']);remote.assert_not_called()
 def test_durable_reservation_cannot_replay(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,data,out,cfg,req=self.setup(tmp);remote=Mock(side_effect=[True,False])
   with patch.object(c,'OUT',out):self.assertTrue(c.reserve(cfg,self.env(),remote)['allowed']);self.assertFalse(c.reserve(cfg,self.env(),remote)['allowed'])
 def test_finish_pauses_and_keeps_holds_and_original_counters(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,data,out,cfg,req=self.setup(tmp)
   with patch.object(c,'DATA',data),patch.object(c,'OUT',out),patch('automation.agri_v2.progress.publish_file',return_value=True):
    c.finish({'allowed':True,'run_id':'123'},result={'status':'published','public_verified':True,'url':'https://navar-abyari.ir/example/'})
   fresh=load_json(data/'config.json');self.assertFalse(fresh['publication_enabled']);self.assertFalse(fresh['automatic_generation']);self.assertEqual(fresh['publication_holds'],{'held':'retain'})
 def test_disabled_control_keeps_normal_pipeline_behavior(self):self.assertIsNone(c.reserve({},self.env(),Mock()))
