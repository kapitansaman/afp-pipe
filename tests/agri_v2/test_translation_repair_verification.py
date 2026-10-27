import unittest,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import operation_request as op,translation_repair_verification as v
from automation.agri_v2.queue import atomic_json
class RepairOperationTests(unittest.TestCase):
 def request(self):
  return {'version':1,'request_id':v.ID,'operation':'nonpublishing-semantic-local-repair','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':0,'enable_schedule':False,'reset_attempts':False,'max_total_text_calls':5,'max_repair_rounds':2,'max_wordpress_mutations':0,'max_image_calls':0,'topic_id':v.TOPIC,'source_request':v.EDITORIAL_ID,'source_article_sha256':v.SOURCE_SHA,'editable_languages':v.EDITABLE,'review_languages':4,'separate_authorized_budget':True,'code_revision':'b'*40}
 def test_exact_new_budget_request_only(self):
  op.validate_request(self.request())
  for key,val in [('max_total_text_calls',6),('reset_attempts',True),('max_wordpress_mutations',1),('max_image_calls',1),('editable_languages',['ru-RU','ar-IQ','tg-TJ','en-US']),('separate_authorized_budget',False),('enable_schedule',True)]:
   req=self.request();req[key]=val
   with self.assertRaises(ValueError):op.validate_request(req)
 def test_routes_prepare_without_wp_or_image_preflight(self):
  with patch.object(op,'load_owner_request',return_value={'request_id':v.ID}),patch.object(v,'run',return_value={'status':'verification_completed'}) as run,patch('automation.agri_v2.production_readiness.run') as readiness:
   self.assertEqual(op.prepare({})['status'],'verification_completed');run.assert_called_once();readiness.assert_not_called()
 def test_pilot_phase_is_no_call_no_publication(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';atomic_json(data/'status/owner-operation-admission.json',{'request_id':v.ID});atomic_json(out/'parallel/operations'/v.ID/'prepare.json',{'status':'verification_completed'})
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_controller.run') as run:
    result=op.pilot({},data,out)
   self.assertEqual(result['model_calls'],0);self.assertEqual(result['published_posts'],0);run.assert_not_called()
 def test_no_admission_means_no_reservation_or_provider(self):
  reserve=Mock();factory=Mock()
  with patch.object(op,'authorize',return_value=False):
   with self.assertRaises(ValueError):v.run({},client_factory=factory,reserve_fn=reserve)
  reserve.assert_not_called();factory.assert_not_called()
