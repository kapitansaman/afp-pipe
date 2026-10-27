import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import quality_index as q,scoped_research as s,family_lifecycle as f,image_quality as image
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json
from automation.agri_v2.pipeline import digest
class PublishableQualityTests(unittest.TestCase):
 def article(self):return {'content_html':'<p>این مقاله درباره جوانه‌زنی لوبیا و محدودیت‌های منبع است.</p>','excerpt':'محدودیت‌های عمومی منبع','faq':[]}
 def review(self,score=70):
  # 25+30+0+0+15 = 70: imperfect prose/marketing must not demand perfection.
  return {'quality_policy':q.VERSION,'dimensions':{'answer_usefulness':25,'source_fidelity':30,'readability':0,'commercial_fit':0,'language_and_units':score-55},'critical_issues':[],'reason':'پاسخ قابل استفاده است، هرچند نگارش و ارتباط تجاری آن می‌تواند بهتر باشد.'}
 def test_seventy_is_enough_without_all_dimensions_perfect(self):
  r=q.evaluate(self.article(),self.review());self.assertEqual(r['score'],70);self.assertTrue(r['accepted']);s.validate_article_review_result(self.article(),self.review())
 def test_sixty_nine_is_queued_not_auto_approved(self):
  r=self.review();r['dimensions']['language_and_units']=14;self.assertFalse(q.evaluate(self.article(),r)['accepted'])
  with self.assertRaises(s.EvidenceBlocked):s.validate_article_review_result(self.article(),r)
 def test_total_is_computed_not_trusted(self):
  r=self.review();r['score']=1;self.assertEqual(q.evaluate(self.article(),r)['score'],70)
 def test_material_error_vetoes_even_one_hundred(self):
  r=self.review();r['dimensions']=dict(q.DIMENSIONS);r['critical_issues']=[{'code':'wrong_crop_or_product','article_quote':'جوانه‌زنی لوبیا','reason':'محصول عنوان با محصول بیان‌شده در ادعا متفاوت است.'}]
  self.assertEqual(q.evaluate(self.article(),r)['score'],100);self.assertFalse(q.evaluate(self.article(),r)['accepted'])
 def test_unknown_or_invented_critical_objection_is_not_valid_evidence(self):
  for code,quote in [('awkward_style','جوانه‌زنی لوبیا'),('wrong_crop_or_product','عبارتی که در مقاله وجود ندارد')]:
   r=self.review();r['critical_issues']=[{'code':code,'article_quote':quote,'reason':'این توضیح به یک ایراد مشخص در متن اشاره می‌کند.'}]
   with self.assertRaises(ValueError):q.evaluate(self.article(),r)
 def test_malformed_or_overrange_scores_never_pass(self):
  for val in [True,25.5,-1,26]:
   r=self.review();r['dimensions']['answer_usefulness']=val
   with self.assertRaises(ValueError):q.evaluate(self.article(),r)
 def test_low_score_is_durable_and_only_one_repair_is_routed(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);a=self.article();b={'topic_id':'fixture'};r=self.review();r['dimensions']['readability']=0;r['dimensions']['language_and_units']=10
   with self.assertRaises(s.EvidenceBlocked):s.save_article_review(a,b,folder,r)
   self.assertEqual(load_json(folder/'quality-review-queue.json')['status'],'automatic_repair_pending');self.assertEqual(q.next_stage(folder,a,b,DATA),('article_quality_repair',None))
   atomic_json(f.row_path(folder,'article_quality_repair'),{'attempts':1});self.assertEqual(q.next_stage(folder,a,b,DATA),('blocked','article_quality_review_queue'));self.assertFalse((folder/'article-evidence-review.json').exists())
 def test_changed_article_cannot_reuse_score(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);a=self.article();b={'topic_id':'fixture'};s.save_article_review(a,b,folder,self.review());self.assertTrue(q.bound(folder,a,b)['accepted']);self.assertIsNone(q.bound(folder,dict(a,excerpt='متن جدید'),b))
 def test_repair_then_one_independent_recheck_no_loop(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);a=self.article();b={};atomic_json(folder/'quality-repair/receipt.json',{'repaired_article_sha256':digest(a),'brief_sha256':digest(b)});atomic_json(f.row_path(folder,'article_quality_repair'),{'attempts':1})
   self.assertEqual(q.next_stage(folder,a,b,DATA),('article_quality_recheck',None));atomic_json(f.row_path(folder,'article_quality_recheck'),{'attempts':1});self.assertEqual(q.next_stage(folder,a,b,DATA),('blocked','article_quality_review_queue'))
 def test_image_index_ignores_model_aesthetic_score_but_not_wrong_crop(self):
  checks=dict.fromkeys(image.CHECKS,True)
  for k in image.COSMETIC_CHECKS:checks[k]=False
  r=q.image_index(checks,image.COSMETIC_CHECKS);self.assertEqual(r['score'],85);self.assertTrue(r['accepted']);checks['crop_stage_match']=False;self.assertFalse(q.image_index(checks,image.COSMETIC_CHECKS)['accepted'])
 def test_role_stage_mapping_keeps_repair_and_recheck_separate(self):
  from automation.agri_v2.role_skills import for_stage
  c=Mock();self.assertEqual(for_stage(c,'article_quality_repair').role,'persian-writer');self.assertEqual(for_stage(c,'article_quality_recheck').role,'evidence-reviewer')
 def test_actual_repair_preserves_original_and_never_approves_itself(self):
  ident='agri-c2b086b47679';fixture=load_json(Path(__file__).parent/'fixtures/quality-repair-article.json');a=fixture['article'];b=fixture['brief']
  from automation.agri_v2.queue import get_topic
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);r=self.review();r['dimensions']['language_and_units']=10
   with self.assertRaises(s.EvidenceBlocked):s.save_article_review(a,b,folder,r)
   c=Mock();c.text.return_value=copy.deepcopy(a);c.text.return_value['excerpt']='خاک سرد و نمناک و بافت خاک در بررسی سبزشدن بذر لوبیا اهمیت دارند.'
   result=q.repair(get_topic('new',ident),a,b,folder,c);self.assertTrue(result['independent_recheck_required']);self.assertEqual(load_json(folder/'quality-repair/original-article.json'),a);self.assertFalse((folder/'article-evidence-review.json').exists());self.assertEqual(q.next_stage(folder,load_json(folder/'article.json'),b,DATA),('article_quality_recheck',None));c.text.assert_called_once()
   with self.assertRaises(ValueError):q.repair(get_topic('new',ident),a,b,folder,c)

 def test_polish_cannot_compensate_for_unusable_source_fidelity(self):
  r=self.review();r['dimensions']=dict(q.DIMENSIONS);r['dimensions']['source_fidelity']=0
  self.assertEqual(q.evaluate(self.article(),r)['score'],70);self.assertFalse(q.evaluate(self.article(),r)['accepted'])
 def test_worker_continues_one_quality_repair_then_recheck_without_reset(self):
  from test_family_lifecycle import FamilyLifecycleTests
  with tempfile.TemporaryDirectory() as d:
   data,out,topic,env,health=FamilyLifecycleTests().setup(d);factory=Mock()
   stages=[('article_evidence_review',None),('article_quality_repair',None),('article_quality_repair',None),('article_quality_recheck',None),('publish',None)]
   with patch.object(f,'next_stage',side_effect=stages),patch.object(f,'run_stage',side_effect=[s.EvidenceBlocked('article_quality_below_publication_threshold'),{'repaired':True},{'reviewed':True}]):
    result=f.worker(topic,health,data,out,env,client_factory=factory)
   self.assertEqual(result['status'],'publication_ready')
   for stage in ('article_evidence_review','article_quality_repair','article_quality_recheck'):self.assertEqual(f.state(out/'new'/topic['id'],stage)['attempts'],1)
