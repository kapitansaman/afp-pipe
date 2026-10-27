import datetime,json,tempfile,unittest
from pathlib import Path
from automation.agri_v2.dashboard_snapshot import build,sha,verified_post
class DashboardSnapshotTests(unittest.TestCase):
 def write(self,root,path,value):
  p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False));return p
 def test_missing_evidence_stays_unknown_and_does_not_authorize(self):
  with tempfile.TemporaryDirectory() as d:
   r=build(Path(d));self.assertIsNone(r['metrics']['published']);self.assertIsNone(r['metrics']['remaining']);self.assertIsNone(r['automation']['schedule_enabled']);self.assertFalse(r['health']['bound']);self.assertEqual(r['reviews'],[])
 def test_verified_publications_only_no_foreign_or_script_urls(self):
  valid={'url':'https://navar-abyari.ir/article/','title':'خبر','public_verified':True}
  self.assertTrue(verified_post(valid))
  for patch in ({'url':'javascript:alert(1)'},{'url':'https://navar-abyari.ir.evil.test/a'},{'url':'https://user:pass@navar-abyari.ir/a'},{'public_verified':False},{'title':''}):self.assertFalse(verified_post(dict(valid,**patch)))
 def test_97_cohort_required_before_showing_healthy_keys(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.write(root,'data/agri-v2/parallel-policy.json',{'credential_set_id':'new97','repository':'kapitansaman/afp-pipe','key_limit':97});self.write(root,'artifacts/agri-v2/parallel/health/latest.json',{'repository':'kapitansaman/afp-pipe','credential_set_id':'old30','audit_status':'completed','eligible_text_slots':['secret-name']});r=build(root);self.assertFalse(r['health']['bound']);self.assertIsNone(r['health']['text_ok']);self.assertNotIn('secret-name',json.dumps(r))
 def test_queue_scanned_even_when_index_outdated(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.write(root,'artifacts/agri-v2/new/agri-000000000001/review-queue/tg-TJ.json',{'topic_id':'agri-000000000001','language':'tg-TJ','status':'needs_attention','attempts':3,'model_calls_spent':9});self.write(root,'artifacts/agri-v2/parallel/language-review-queue/index.json',{'items':[]});r=build(root);self.assertEqual(r['metrics']['review_waiting'],1);self.assertEqual(r['reviews'][0]['attempts'],3)
 def test_raw_secrets_and_prompts_are_never_copied(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.write(root,'data/agri-v2/config.json',{'api_key':'DO_NOT_EXPORT','automatic_generation':False});self.write(root,'artifacts/agri-v2/parallel/operations/test/prepare.json',{'started_at':'2026-10-27T00:00:00Z','prompt':'DO_NOT_EXPORT','authorization':'DO_NOT_EXPORT','run_id':'123'});s=json.dumps(build(root));self.assertNotIn('DO_NOT_EXPORT',s);self.assertIn('/runs/123',s)
 def test_latest_experiment_does_not_replace_production_or_imply_publication(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for name,stamp in [('old','2026-10-26T00:00:00Z'),('new','2026-10-27T00:00:00Z')]:self.write(root,'artifacts/agri-v2/parallel/operations/'+name+'/prepare.json',{'completed_at':stamp,'status':'model_approved','published_posts':0})
   self.write(root,'artifacts/agri-v2/parallel/lifecycle/latest.json',{'completed_at':'2026-10-25T00:00:00Z','status':'pilot_incomplete'});r=build(root);self.assertEqual(r['experiment']['operation'],'new');self.assertEqual(r['last_lifecycle']['status'],'pilot_incomplete');self.assertEqual(r['experiment']['published_posts'],0);self.assertIsNone(r['metrics']['published'])
 def test_positive_model_verdict_does_not_override_pending_native_quality(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);article={'title':'مقاله'};tg={'title':'Тарҷума'};base='artifacts/agri-v2/parallel/writer-verification/test/agri-000000000001/'
   self.write(root,'artifacts/agri-v2/parallel/operations/test/prepare.json',{'completed_at':'2026-10-27T00:00:00Z','topic_id':'agri-000000000001','status':'verified'});self.write(root,base+'article.json',article);self.write(root,base+'translations/tg-TJ.json',tg);self.write(root,base+'language-quality-status.json',{'source_article_sha256':sha(article),'translation_sha256':sha(tg),'status':'experimental_draft_pending_independent_language_quality_check','automated_fidelity_review_passed':True,'independent_native_language_review_done':False});r=build(root);self.assertTrue(r['experiment']['tajik_quality_pending']);self.assertFalse(r['experiment']['native_review_done'])
 def test_collection_is_read_only_and_numbers_are_not_hardcoded(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.write(root,'data/agri-v2/manifest.json',{'counts':{'new':10,'merge':2,'hold':3}});p=self.write(root,'data/agri-v2/status/live.json',{'metrics':{'published_verified':2}});before=p.read_bytes();r=build(root);self.assertEqual(r['metrics']['remaining'],8);self.assertEqual(p.read_bytes(),before)
 def test_source_approval_requires_all_evidence_flags_and_matching_brief(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);article={'title':'مقاله'};brief={'facts':[]};ident='agri-000000000001';base='artifacts/agri-v2/parallel/writer-verification/test/'+ident+'/'
   self.write(root,'artifacts/agri-v2/parallel/operations/test/prepare.json',{'completed_at':'2026-10-27T00:00:00Z','topic_id':ident});self.write(root,base+'article.json',article);self.write(root,'data/agri-v2/briefs/'+ident+'.json',brief);self.write(root,base+'article-evidence-review.json',{'article_sha256':sha(article),'brief_sha256':sha(brief),'review':{'all_article_claims_supported':True,'no_additional_numbers_or_advice':False}});self.assertFalse(build(root)['experiment']['source_reviewed'])
