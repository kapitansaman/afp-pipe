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
