import base64,io,json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
from automation.agri_v2 import media_policy as m,image_quality as q
from automation.agri_v2.queue import load_json,atomic_json
class ImageQualityTests(unittest.TestCase):
 def topic(self):return {'id':'agri-af1a4b491d83','crop':'لوبیا قرمز','title':'زمان مناسب برداشت لوبیا قرمز'}
 def good(self):return {'score':95,'checks':{k:True for k in q.CHECKS},'reasons':['test fixture only']}
 def test_reference_scaling_preserves_original_ratio(self):
  raw=base64.b64decode((m.ASSETS/'afp-tape.webp.b64').read_text());im=Image.open(io.BytesIO(raw));p=m.reference_product()
  self.assertLess(abs(im.width/im.height-p.width/p.height),.02)
 def test_seed_color_not_red_pods_and_role2_not_panorama(self):
  p=m.image_prompt(self.topic(),2);self.assertIn('Red refers to seed-coat color',p);self.assertIn('straw-brown',p);self.assertIn('near-overhead',p);self.assertIn('no horizon',p)
 def test_pinto_distinct_seed_color(self):
  t=self.topic();t.update(crop='لوبیا چیتی',title='برداشت لوبیا چیتی');self.assertIn('brown mottling',m.crop_spec(t));self.assertNotIn('deep burgundy',m.crop_spec(t))
 def test_green_bean_not_dry_kidney(self):
  t=self.topic();t.update(crop='لوبیا سبز',title='برداشت لوبیا سبز');self.assertIn('attached green pods',m.crop_spec(t));self.assertNotIn('straw-brown',m.crop_spec(t));self.assertNotIn('straw-brown',m.scene_plan(t,2)['evidence'])
 def test_other_crop_never_forced_to_dry_beans(self):
  p=m.image_prompt({'crop':'گندم','title':'برداشت گندم'},2);self.assertIn('wheat',p);self.assertNotIn('dry bean',p)
 def test_word_boundary_prevents_garlic_from_masir(self):
  self.assertNotIn('garlic',m.crop_spec({'crop':'نامشخص','title':'مسیر آبیاری مزرعه'}))
 def test_article_content_binds_context_not_only_title(self):
  t=self.topic();self.assertNotEqual(m.contract_hash(t,2),m.contract_hash(t,2,{'content_html':'<p>ویژگی خاص مقاله</p>'}))
 def test_three_roles_are_distinct(self):
  plans=[m.scene_plan(self.topic(),i) for i in (1,2,3)];self.assertEqual(len({p['camera'] for p in plans}),3);self.assertFalse(plans[2]['hardware_required']);self.assertIn('authentic packaging',plans[2]['evidence']);self.assertIn('dry common bean',plans[2]['botany'])
 def test_invalid_role_fail_closed(self):
  for i in (0,4,'1',True):
   with self.assertRaises(ValueError):m.scene_plan(self.topic(),i)
 def test_missing_malformed_unknown_never_pass(self):
  for value in ({},{'pass':True,'score':100},None,{'checks':{k:'true' for k in q.CHECKS},'score':100,'reasons':['x']}):
   with self.assertRaises(q.ImageQualityError):q.verdict(value)
 def test_one_failed_critical_check_overrides_score(self):
  v=self.good();v['checks']['packaging_closed_no_protruding_material']=False;v['score']=100;self.assertFalse(q.verdict(v)['passed'])
 def test_no_fast_mode_or_vision_failure_pass(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image-2.webp';p.write_bytes(b'fixture');c=Mock();c.review_image.side_effect=TimeoutError()
   with self.assertRaises(q.ImageQualityError):q.ensure_review(c,p,self.topic(),2)
   self.assertEqual(load_json(q.review_path(p))['status'],'review_unavailable')
   with self.assertRaises(q.ImageQualityError):q.ensure_review(c,p,self.topic(),2)
   self.assertEqual(c.review_image.call_count,1)
 def test_approved_exact_hash_reused_changed_bytes_require_new_review(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image-2.webp';p.write_bytes(b'fixture');c=Mock();c.review_image.return_value=self.good()
   q.ensure_review(c,p,self.topic(),2);q.ensure_review(c,p,self.topic(),2);self.assertEqual(c.review_image.call_count,1)
   p.write_bytes(b'changed')
   with self.assertRaises(q.ImageQualityError):q.valid_record(p,self.topic(),2)
 def test_rejected_image_preserved_not_regenerated_or_reapproved(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image-2.webp';p.write_bytes(b'fixture');c=Mock();v=self.good();v['checks']['product_identity_match']=False;c.review_image.return_value=v
   for _ in range(2):
    with self.assertRaises(q.ImageQualityError):q.ensure_review(c,p,self.topic(),2)
   self.assertEqual(p.read_bytes(),b'fixture');self.assertEqual(c.review_image.call_count,1)
 def test_require_all_fails_without_receipts(self):
  with tempfile.TemporaryDirectory() as d:
   for k in (1,2,3):(Path(d)/f'image-{k}.webp').write_bytes(b'fixture')
   with self.assertRaises(q.ImageQualityError):q.require_all(d,self.topic())
 def test_explicit_negative_receipt_cannot_be_overridden_by_score(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image-2.webp';p.write_bytes(b'fixture');v=q.verdict(self.good());v['passed']=False
   atomic_json(q.review_path(p),{**q.binding(p,self.topic(),2),'status':'reviewed','verdict':v})
   with self.assertRaises(q.ImageQualityError):q.valid_record(p,self.topic(),2)
 def test_native_landscape_pipeline_never_center_crops_wrong_ratio(self):
  from automation.agri_v2.client import render_image,ImageAspectRatioError
  out=io.BytesIO();Image.new('RGB',(1024,768),'green').save(out,'PNG');obj={'data':[{'b64_json':base64.b64encode(out.getvalue()).decode()}]}
  with self.assertRaises(ImageAspectRatioError):render_image(obj,require_landscape=True)
 def test_native_landscape_preserves_bottom_edge_of_whole_scene(self):
  from automation.agri_v2.client import render_image
  im=Image.new('RGB',(1312,736),'white');im.paste('red',(0,700,350,736));out=io.BytesIO();im.save(out,'PNG');obj={'data':[{'b64_json':base64.b64encode(out.getvalue()).decode()}]}
  result=Image.open(io.BytesIO(render_image(obj,require_landscape=True)));self.assertGreater(result.getpixel((50,660))[0],220);self.assertLess(result.getpixel((50,660))[1],60)
 def test_vision_review_has_one_http_attempt_and_closed_package_check(self):
  from automation.agri_v2.client import ModelClient
  c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'message':{'content':json.dumps(self.good())}}]})
  c.review_image(b'fixture',self.topic(),2);self.assertEqual(c.request.call_args.kwargs['attempts'],1);self.assertIn('packaging_closed_no_protruding_material',str(c.request.call_args))
 def test_wordpress_no_new_post_or_upload_for_unreviewed_images(self):
  from automation.agri_v2.wordpress import WordPress
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);atomic_json(p/'wordpress-draft-payload.json',{'slug':'fixture','content':'<p>x</p>'});atomic_json(p/'article.json',{'content_html':'fixture'})
   for i in (1,2,3):(p/f'image-{i}.webp').write_bytes(b'fixture')
   w=WordPress({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'},data=p/'test-data');w.preflight=Mock();w.call=Mock(return_value=([],{}))
   with self.assertRaises(q.ImageQualityError):w.publish(p,self.topic(),{'publish_authorized':True},True)
   self.assertTrue(all(len(x.args)<2 or x.args[1]=='GET' for x in w.call.call_args_list))

 def test_exposed_spool_cannot_pass_as_enclosed_filter(self):
  v=self.good();v['checks']['hardware_identity_match']=False;v['score']=100;self.assertFalse(q.verdict(v)['passed'])
 def test_technical_role_uses_actual_structural_reference_not_just_identity(self):
  self.assertNotEqual(m.reference_images(3,{'title':'نصب فیلتر'}),m.reference_images());self.assertEqual(m.reference_images(1),m.reference_images())
  p=m.image_prompt({'title':'نصب فیلتر'},3);self.assertIn('complete geometry and layout guide',p);self.assertIn('closed black Y-filter',p)
 def test_generate_role_passes_exact_role_references(self):
  c=Mock();c.image.return_value=b'image';self.assertEqual(m.generate_role(c,self.topic(),3),b'image');self.assertEqual(c.image.call_args.kwargs['references'],m.reference_images(3,self.topic()))
 def test_quality_binding_changes_with_structural_guide(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'image.webp';p.write_bytes(b'fixture')
   self.assertNotEqual(q.binding(p,self.topic(),2)['reference_sha256'],q.binding(p,{'title':'نصب فیلتر','id':'fixture'},3)['reference_sha256'])
 def test_writer_still_accepts_plain_text_without_undefined_role(self):
  from automation.agri_v2.client import ModelClient
  c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'message':{'content':'{"title":"fixture"}'}}]})
  self.assertEqual(c.text('fixture'),{'title':'fixture'})

 def test_score_is_advisory_when_all_critical_checks_pass(self):
  v=self.good();v['score']=72;self.assertTrue(q.verdict(v)['passed'])
  v['score']=85;self.assertTrue(q.verdict(v)['passed'])
 def test_cosmetic_scale_does_not_veto_92(self):
  v=self.good();v['score']=92;v['checks']['product_scale_match']=False
  self.assertTrue(q.verdict(v)['passed'])
 def test_every_critical_failure_vetoes_100(self):
  for key in q.CHECKS:
   if key in q.COSMETIC_CHECKS:continue
   v=self.good();v['score']=100;v['checks'][key]=False
   self.assertFalse(q.verdict(v)['passed'],key)
