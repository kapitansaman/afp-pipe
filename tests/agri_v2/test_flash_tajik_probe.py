import copy,unittest
from automation.agri_v2 import flash_tajik_probe as f,operation_request as op
class FlashProbeTests(unittest.TestCase):
 def req(self):return {'version':1,'request_id':f.ID,'operation':'nonpublishing-flash-only-tajik-samples','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':0,'enable_schedule':False,'reset_attempts':False,'max_total_text_calls':3,'max_calls_per_model':1,'max_wordpress_mutations':0,'max_image_calls':0,'topic_id':f.TOPIC,'models':f.MODELS,'sample_ids':f.SAMPLE_IDS,'modify_translations':False,'change_default_model':False,'code_revision':'b'*40}
 def test_only_exact_requested_flash_models(self):
  op.validate_request(self.req());self.assertTrue(all('flash' in m and 'pro' not in m for m in f.MODELS))
  for key,value in [('models',['agnes-2.5-pro-beta']),('max_total_text_calls',4),('max_calls_per_model',2),('modify_translations',True),('change_default_model',True)]:
   r=self.req();r[key]=value
   with self.assertRaises(ValueError):op.validate_request(r)
 def test_sample_crop_feedback_and_unchanged_numbers_required(self):
  prompt={'samples':[{'id':35,'source':'هویج 40 °F'}]};good={'previous_crop_claim_correct':False,'translations':[{'id':35,'text':'сабзӣ 40 °F'}],'reason':'The previous reviewer confused Tajik and Russian crop terms.'}
  f.validate_sample(good,prompt)
  for change in ('number','unit','crop','feedback','html','script'):
   bad=copy.deepcopy(good)
   if change=='number':bad['translations'][0]['text']='сабзӣ 45 °F'
   if change=='unit':bad['translations'][0]['text']='сабзӣ 40 °C'
   if change=='crop':bad['translations'][0]['text']='ҷуворимакка 40 °F'
   if change=='feedback':bad['previous_crop_claim_correct']=True
   if change=='html':bad['translations'][0]['text']='<script>сабзӣ 40 °F</script>'
   if change=='script':bad['translations'][0]['text']='هویج 40 °F'
   with self.assertRaises(ValueError):f.validate_sample(bad,prompt)
