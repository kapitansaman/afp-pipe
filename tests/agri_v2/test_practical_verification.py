import tempfile,unittest
from pathlib import Path
from automation.agri_v2 import practical_verification as p,operation_request as op
from automation.agri_v2.queue import atomic_json
class PracticalVerificationTests(unittest.TestCase):
 def req(self):return {'version':1,'request_id':p.ID,'operation':'nonpublishing-practical-writer-four-translations','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':0,'enable_schedule':False,'reset_attempts':False,'max_total_text_calls':13,'max_writer_calls':1,'max_final_article_reviews':1,'max_translation_languages':4,'max_wordpress_mutations':0,'topic_id':p.TOPIC,'code_revision':'b'*40}
 def test_no_publication_images_budget_reset_or_unbounded_rewrite(self):
  op.validate_request(self.req())
  for k,v in [('max_total_text_calls',14),('max_writer_calls',2),('max_final_article_reviews',0),('max_translation_languages',5),('max_pilot_families',1),('max_wordpress_mutations',1),('max_image_health_calls',1),('enable_schedule',True),('reset_attempts',True)]:
   r=self.req();r[k]=v
   with self.assertRaises(ValueError):op.validate_request(r)
 def test_budget_comes_from_all_five_real_prior_receipts(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)
   for run,calls in p.PRIOR:
    row={'run_id':run,'status':'pilot_incomplete','matrix_pilot':True,'assigned_count':1,'published_posts':0,'pool':{'model_requests_reserved':calls,'peak_image_leases':0},'results':[{'topic_id':p.TOPIC}]};path=out/'parallel/lifecycle/runs'/run/'report.json';atomic_json(path,row)
   self.assertEqual(p.remaining(out),13);row['pool']['model_requests_reserved']=2;atomic_json(path,row)
   with self.assertRaises(ValueError):p.remaining(out)
 def test_saved_continuation_allows_no_new_writer_call(self):
  req=self.req();req.update(request_id=p.CONT_ID,operation='nonpublishing-saved-practical-draft-four-translations',max_total_text_calls=12,max_writer_calls=0,resume_from_request=p.ID);op.validate_request(req)
  for key,value in [('max_writer_calls',1),('max_total_text_calls',13),('max_wordpress_mutations',1),('resume_from_request','other')]:
   bad=dict(req);bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
 def test_saved_review_continuation_has_no_new_writer_or_review_call(self):
  req=self.req();req.update(request_id=p.REVIEW_ID,operation='nonpublishing-reviewed-practical-four-translations',max_total_text_calls=11,max_writer_calls=0,max_final_article_reviews=0,resume_from_request=p.CONT_ID);op.validate_request(req)
  for key,value in [('max_total_text_calls',12),('max_writer_calls',1),('max_final_article_reviews',1),('max_wordpress_mutations',1)]:
   bad=dict(req);bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
 def test_translation_resume_has_no_new_writer_or_review_and_nine_calls(self):
  req=self.req();req.update(request_id=p.TRANSLATION_ID,operation='nonpublishing-resume-practical-translations',max_total_text_calls=9,max_writer_calls=0,max_final_article_reviews=0,resume_from_request=p.REVIEW_ID);op.validate_request(req)
  for key,value in [('max_total_text_calls',10),('max_writer_calls',1),('max_final_article_reviews',1),('reset_attempts',True)]:
   bad=dict(req);bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
 def test_last_five_call_language_repair_does_not_reset_or_publish(self):
  req=self.req();req.update(request_id=p.LANGUAGE_ID,operation='nonpublishing-repair-language-and-verify-four-translations',max_total_text_calls=5,max_writer_calls=0,max_final_article_reviews=0,max_language_repairs=1,max_translation_fidelity_reviews=1,resume_from_request=p.TRANSLATION_ID);op.validate_request(req)
  for key,value in [('max_total_text_calls',6),('max_language_repairs',2),('max_translation_fidelity_reviews',2),('max_writer_calls',1),('max_wordpress_mutations',1),('reset_attempts',True)]:
   bad=dict(req);bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
