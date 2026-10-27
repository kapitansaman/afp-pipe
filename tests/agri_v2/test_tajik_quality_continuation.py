import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import operation_request as op,tajik_quality_continuation as q,tajik_full_verification as f
from test_multilingual import article,response
from automation.agri_v2.multilingual import source_segments
class FinalTajikRoundTests(unittest.TestCase):
 def req(self):return {'version':1,'request_id':q.ID,'operation':'nonpublishing-final-tajik-reference-feedback','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':0,'enable_schedule':False,'reset_attempts':False,'max_total_text_calls':4,'prior_same_budget_calls':4,'total_authorized_budget':8,'max_wordpress_mutations':0,'max_image_calls':0,'topic_id':q.TOPIC,'model':'agnes-3.0-flash','source_request':q.PRIOR,'max_additional_tajik_repair_rounds':1,'max_total_tajik_repair_rounds':2,'change_default_model':False,'code_revision':'b'*40}
 def test_remaining_budget_cannot_be_reset(self):
  op.validate_request(self.req())
  for key,value in [('max_total_text_calls',5),('prior_same_budget_calls',0),('total_authorized_budget',9),('max_additional_tajik_repair_rounds',2)]:
   req=self.req();req[key]=value
   with self.assertRaises(ValueError):op.validate_request(req)
 def test_false_positive_review_gets_one_paid_correction_not_forced_approval(self):
  a=article();raw=response(a,'tg-TJ');_,source=source_segments(a);source[0]='مزرعه';raw['translations'][0]['text']='бӯрон';old={'faithful':True,'reason':'Everything correct','issues':[]};negative={'faithful':False,'reason':'The field was incorrectly translated as storm.','issues':[{'id':0,'category':'meaning','detail':'A farm is not a storm.'}]};client=Mock();client.text.return_value=negative
  with tempfile.TemporaryDirectory() as d:value,issues=f.reviewed(client,Path(d),'qa',a,source,raw,limit=4,initial=old)
  self.assertFalse(value['faithful']);self.assertEqual(client.text.call_count,1);self.assertEqual(issues[0]['id'],0)
