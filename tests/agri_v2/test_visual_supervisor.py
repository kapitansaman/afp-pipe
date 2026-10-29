import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import visual_supervisor as s,image_quality as q,image_workflow as w
from automation.agri_v2.client import ModelClient,CapabilityError,ModelOutputError
from automation.agri_v2.queue import atomic_json,load_json

class VisualSupervisorTests(unittest.TestCase):
 def good(self):
  return {'review_contract':s.VERSION,'score':81,'checks':dict.fromkeys(q.CHECKS,True),'observations':{k:{'outcome':'pass','observation':'Candidate-specific visible feature inspected independently.'} for k in q.CHECKS},'reasons':['Automated fixture, not actual crop or human approval.']}
 def client(self,value,finish='stop'):
  c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value)}}]});c.record_success=Mock();return c
 def topic(self):return {'id':'fixture','crop':'گندم','title':'آبیاری گندم'}
 def test_schema_covers_every_check_and_observation(self):
  schema=s.schema();self.assertEqual(set(schema['properties']['observations']['required']),set(q.CHECKS));self.assertFalse(schema['additionalProperties'])
 def test_no_structural_acceptance_without_evidence(self):
  c=self.client({'score':100,'checks':dict.fromkeys(q.CHECKS,True),'reasons':['fixture']})
  with self.assertRaises(CapabilityError):c.review_image(b'fixture',self.topic(),1)
  c.record_success.assert_not_called();self.assertEqual(c.request.call_count,1)
 def test_unknown_marker_never_downgrades_to_legacy(self):
  v=self.good();v['review_contract']='unknown'
  with self.assertRaises(q.ImageQualityError):q.verdict(v)
 def test_observations_without_marker_never_downgrade(self):
  v=self.good();del v['review_contract']
  with self.assertRaises(q.ImageQualityError):q.verdict(v)
 def test_missing_check_observation_rejected(self):
  v=self.good();del v['observations']['crop_stage_match']
  with self.assertRaises(ValueError):s.validate(v,required=True)
 def test_non_boolean_rejected(self):
  v=self.good();v['checks']['crop_stage_match']=1
  with self.assertRaises(ValueError):s.validate(v,required=True)
 def test_uncertain_true_rejected(self):
  v=self.good();v['observations']['crop_stage_match']['outcome']='uncertain'
  with self.assertRaises(q.ImageQualityError):q.verdict(v)
 def test_uncertain_false_cannot_pass_with_perfect_score(self):
  v=self.good();v['score']=100;v['checks']['crop_stage_match']=False;v['observations']['crop_stage_match']['outcome']='uncertain';self.assertFalse(q.verdict(v)['passed'])
 def test_cosmetic_false_does_not_force_regeneration(self):
  v=self.good();v['checks']['role_camera_match']=False;v['observations']['role_camera_match']['outcome']='fail';self.assertTrue(q.verdict(v)['passed']);self.assertEqual(s.correction_feedback(v)['checks'],{})
 def test_not_applicable_never_waives_crop_or_product(self):
  for key in ('crop_stage_match','product_identity_match','phone_label_correct'):
   v=self.good();v['observations'][key]['outcome']='not_applicable'
   with self.assertRaises(ValueError):s.validate(v,required=True,hardware_required=False)
 def test_hardware_can_be_absent_only_if_not_required(self):
  v=self.good();v['observations']['hardware_identity_match']['outcome']='not_applicable';s.validate(v,required=True,hardware_required=False)
  with self.assertRaises(ValueError):s.validate(v,required=True,hardware_required=True)
 def test_short_generic_or_oversized_observations_rejected(self):
  for text in ('ok',' '*30,'a'*1201):
   v=self.good();v['observations']['crop_stage_match']['observation']=text
   with self.assertRaises(ValueError):s.validate(v,required=True)
 def test_client_sends_strict_schema_and_one_attempt(self):
  c=self.client(self.good());c.review_image(b'fixture',self.topic(),1);args=c.request.call_args;self.assertEqual(args.kwargs['attempts'],1);body=args.args[2];self.assertTrue(body['response_format']['json_schema']['strict']);self.assertEqual(body['max_tokens'],6500);self.assertIn('NOT a news-agency',str(body));self.assertIn('not documentary',str(body).lower());c.record_success.assert_called_once()
 def test_truncated_or_filtered_response_never_records_success(self):
  for finish,code in [('length','text_output_limit'),('content_filter','text_content_filtered')]:
   c=self.client(self.good(),finish)
   with self.assertRaisesRegex(ModelOutputError,code):c.review_image(b'fixture',self.topic(),1)
   c.record_success.assert_not_called();self.assertEqual(c.request.call_count,1)
 def test_verdict_preserves_evidence_without_changing_decision(self):
  v=self.good();r=q.verdict(v);self.assertEqual(r['observations'],v['observations']);self.assertEqual(r['review_contract'],s.VERSION);self.assertTrue(r['passed'])
 def test_feedback_is_current_hash_bound_and_critical_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image-1.webp';p.write_bytes(b'candidate');v=self.good()
   for k in ('crop_stage_match','role_camera_match'):v['checks'][k]=False;v['observations'][k]['outcome']='fail'
   row=q.verdict(v);atomic_json(q.review_path(p),{'status':'reviewed','image_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'verdict':row})
   feedback=q.generation_feedback(d,1);self.assertEqual(set(feedback['checks']),{'crop_stage_match'});self.assertFalse(feedback['reset_attempts']);self.assertFalse(feedback['change_acceptance_policy']);self.assertNotIn('role_camera_match',str(feedback))
   p.write_bytes(b'changed');self.assertIsNone(q.generation_feedback(d,1))
 def test_unavailable_evidence_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image-1.webp';p.write_bytes(b'candidate');c=self.client({})
   for _ in range(2):
    with self.assertRaises(q.ImageQualityError):q.ensure_review(c,p,self.topic(),1)
   self.assertEqual(c.request.call_count,1);self.assertEqual(p.read_bytes(),b'candidate')
 def test_no_legacy_artifacts_rewritten_during_validation(self):
  v={'score':90,'checks':dict.fromkeys(q.CHECKS,True),'reasons':['Historical fixture only.']};before=copy.deepcopy(v);self.assertTrue(q.verdict(v)['passed']);self.assertEqual(v,before)
 def test_generator_receives_targeted_feedback_as_untrusted_data(self):
  from automation.agri_v2.media_policy import generate_role
  v=self.good();v['checks']['crop_stage_match']=False;v['observations']['crop_stage_match']['outcome']='uncertain';c=Mock();c.image_feedback=s.correction_feedback(v);c.image.return_value=b'new';generate_role(c,self.topic(),1)
  text=c.image.call_args.args[0];self.assertIn('correct actual defects, not scores',text);self.assertIn('crop_stage_match',text);self.assertIn('reset_attempts',text);c.image.assert_called_once()
 def test_same_candidate_is_not_re_reviewed_for_better_verdict(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image-1.webp';p.write_bytes(b'candidate');v=self.good();v['checks']['crop_stage_match']=False;v['observations']['crop_stage_match']['outcome']='fail';c=self.client(v)
   for _ in range(2):
    with self.assertRaises(q.ImageQualityError):q.ensure_review(c,p,self.topic(),1)
   self.assertEqual(c.request.call_count,1);self.assertEqual(load_json(q.review_path(p))['verdict']['review_contract'],s.VERSION)

 def test_supervised_rejection_flows_to_generator_then_independent_recheck(self):
  from tests.agri_v2 import test_image_fallback as fixtures
  outer=self
  class Client:
   def __init__(self):self.generated=[];self.reviews=0;self.feedback=[]
   def image(self,prompt,references=None):
    self.generated.append(prompt);self.feedback.append(copy.deepcopy(getattr(self,'image_feedback',None)));return ('candidate-'+str(len(self.generated))).encode()
   def review_image(self,*args):
    self.reviews+=1;value=outer.good()
    if self.reviews==1:value['checks']['crop_stage_match']=False;value['observations']['crop_stage_match']['outcome']='uncertain'
    return value
  with tempfile.TemporaryDirectory() as d:
   data,folder,topic,article=fixtures.ImageFallbackTests().fixture(d);c=Client();result=w.advance(c,folder,topic,article,'test-run',data)
   self.assertEqual(result['status'],'images_ready');self.assertEqual(len(c.generated),3);self.assertEqual(c.reviews,3);self.assertIsNone(c.feedback[0]);self.assertEqual(set(c.feedback[1]['checks']),{'crop_stage_match'});self.assertIn('uncertain',str(c.feedback[1]));self.assertFalse(c.feedback[1]['reset_attempts'])
   self.assertEqual(len(list((folder/'lifecycle/image-1/rejected').glob('*/image-1.webp'))),1);q.require_all(folder,topic,article)
   w.advance(c,folder,topic,article,'next-run',data);self.assertEqual(c.reviews,3);self.assertEqual(len(c.generated),3)
 def test_supervised_exhaustion_never_creates_an_approval_or_resets_budget(self):
  from tests.agri_v2 import test_image_fallback as fixtures
  from automation.agri_v2.family_lifecycle import state
  outer=self
  class Client:
   def __init__(self):self.calls=0
   def image(self,*args,**kwargs):self.calls+=1;return ('candidate-'+str(self.calls)).encode()
   def review_image(self,*args):
    value=outer.good();value['checks']['crop_stage_match']=False;value['observations']['crop_stage_match']['outcome']='uncertain';return value
  with tempfile.TemporaryDirectory() as d:
   data,folder,topic,article=fixtures.ImageFallbackTests().fixture(d);c=Client();result=w.advance(c,folder,topic,article,'test-run',data)
   self.assertEqual(result['status'],'images_need_attention');self.assertEqual(c.calls,8);self.assertFalse(w.selection_path(folder).exists())
   for kind in (1,2):self.assertEqual(state(folder,'image-'+str(kind))['attempts'],4)
   w.advance(c,folder,topic,article,'next-run',data);self.assertEqual(c.calls,8)
