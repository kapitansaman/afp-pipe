import contextlib,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import persian_source_pilot as p,operation_request as op
from automation.agri_v2.queue import atomic_json,load_json,DATA,OUT
from automation.agri_v2.wordpress import WordPress,WPError
class PersianSourcePilotTests(unittest.TestCase):
 def test_exact_scope_has_zero_models_one_source_and_no_translations(self):
  req=dict(p.expected_request(),code_revision='a'*40);op.validate_request(req)
  for k,v in [('max_total_model_calls',1),('max_image_calls',1),('max_total_posts',2),('max_translations',1),('max_media_uploads',2),('max_wordpress_mutations',6),('enable_schedule',True),('reset_attempts',True),('required_selected_roles',[2])]:
   with self.assertRaises(ValueError):op.validate_request(dict(req,**{k:v}))
 def wp(self,root):return p.SourceOnlyPublisher({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'},root,{'title':'fixture'},'fixture-slug')
 def test_original_publisher_remains_inherited(self):self.assertIs(p.SourceOnlyPublisher.publish,WordPress.publish);self.assertIs(p.SourceOnlyPublisher.verify,WordPress.verify)
 def test_translations_not_called_even_if_approved(self):
  with tempfile.TemporaryDirectory() as d,patch('automation.agri_v2.multilingual.publish_family') as publish:
   r=self.wp(Path(d)).publish_family(Path(d),{}, {'public_verified':True});self.assertTrue(r['source_only']);self.assertTrue(r['translation_publication_skipped']);publish.assert_not_called()
 def test_source_draft_identity_and_translation_fields_are_guarded(self):
  with tempfile.TemporaryDirectory() as d,patch.object(WordPress,'call') as call:
   wp=self.wp(Path(d))
   for data in [{'title':'wrong','slug':'fixture-slug','status':'draft'},{'title':'fixture','slug':'wrong','status':'draft'},{'title':'fixture','slug':'fixture-slug','status':'publish'},{'title':'fixture','slug':'fixture-slug','status':'draft','afp_language':'en-US'}]:
    with self.assertRaises(WPError):wp.call('posts','POST',data)
   call.assert_not_called()
 def test_only_one_create_and_upload_and_five_mutations(self):
  with tempfile.TemporaryDirectory() as d,patch.object(WordPress,'call',return_value=({},{})) as call:
   wp=self.wp(Path(d));wp.call('posts','POST',{'title':'fixture','slug':'fixture-slug','status':'draft'});wp.call('media','POST',blob=b'fixture');wp.call('media/1','POST',{'post':1});wp.call('posts/1','POST',{'status':'draft'});wp.call('posts/1','POST',{'status':'publish'})
   with self.assertRaises(WPError):wp.call('posts/1','POST',{'status':'publish'})
   self.assertEqual(call.call_count,5);self.assertEqual(load_json(Path(d)/'wordpress-mutations.json')['reserved_mutations'],5)
 def test_unknown_mutation_method_or_route_is_forbidden(self):
  with tempfile.TemporaryDirectory() as d,patch.object(WordPress,'call') as call:
   wp=self.wp(Path(d))
   for route,method in [('posts/1','DELETE'),('users/me','POST'),('posts/1?force=true','POST')]:
    with self.assertRaises(WPError):wp.call(route,method,{'status':'publish'})
   call.assert_not_called()
 def test_existing_local_source_is_publication_ready_without_translation_calls(self):
  topic,brief,article,source,folder=p.validate_source(DATA,OUT);self.assertEqual(topic['id'],p.TOPIC);self.assertTrue(brief['publish_authorized'])
 @contextlib.contextmanager
 def fixture(self,t):
  root=Path(t);data=root/'data';out=root/'out';folder=out/'new'/p.TOPIC;source=out/'source';topic={'id':p.TOPIC,'title':'fixture'};brief={'slug':'fixture-slug'};article={'title':'fixture'}
  atomic_json(data/'status/owner-operation-admission.json',{'request_id':p.ID});atomic_json(folder/'article.json',article);atomic_json(folder/'review-queue/tg-TJ.json',{'attempts':2,'model_calls_spent':7});atomic_json(source/'article.json',article);atomic_json(out/'provider-circuit.json',{'open':True,'retry_at_epoch':9999999999});atomic_json(out/'parallel/families/assignments.json',{'owners':[1]})
  with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy',return_value={}),patch.object(p,'validate_source',return_value=(topic,brief,article,source,folder)):
   yield data,out,folder,source
 def test_source_pilot_publication_keeps_queue_owner_and_provider_hold(self):
  with tempfile.TemporaryDirectory() as t,self.fixture(t) as (data,out,folder,source):
   env={'GITHUB_RUN_ID':'123'};wp=Mock();wp.preflight.return_value={'can_publish':True};p.prepare(env,data,out,reserve_fn=lambda *_:{},wp_factory=lambda:wp)
   def publish(wp,topic,data,out):
    atomic_json(folder/'wordpress-receipt.json',{'post_id':1,'url':'https://navar-abyari.ir/fixture/','public_verified':True});return {'published_posts':1,'public_verified':True}
   with patch('automation.agri_v2.family_lifecycle.publish_ready',side_effect=publish) as call:r=p.pilot(env,data,out,wp_factory=lambda:wp)
   self.assertEqual(r['status'],'source_only_pilot_public_verified');self.assertEqual(r['published_posts'],1);self.assertEqual(r['model_calls'],0);self.assertEqual(r['image_calls'],0);self.assertFalse(r['schedule_activated']);self.assertTrue(r['provider_circuit_unchanged']);self.assertTrue(r['assignments_unchanged']);self.assertTrue(r['protected_existing_files_unchanged']);self.assertEqual(load_json(folder/'review-queue/tg-TJ.json')['attempts'],2);self.assertEqual(call.call_count,1)
 def test_failed_public_verification_does_not_claim_success(self):
  with tempfile.TemporaryDirectory() as t,self.fixture(t) as (data,out,folder,source):
   env={'GITHUB_RUN_ID':'123'};wp=Mock();wp.preflight.return_value={'can_publish':True};p.prepare(env,data,out,reserve_fn=lambda *_:{},wp_factory=lambda:wp)
   with patch('automation.agri_v2.family_lifecycle.publish_ready',side_effect=WPError('fixture')):r=p.pilot(env,data,out,wp_factory=lambda:wp)
   self.assertEqual(r['status'],'source_only_pilot_blocked');self.assertEqual(r['published_posts'],0)
 def test_pilot_reservation_prevents_repeat_publication(self):
  with tempfile.TemporaryDirectory() as t,self.fixture(t) as (data,out,folder,source):
   env={'GITHUB_RUN_ID':'123'};wp=Mock();wp.preflight.return_value={'can_publish':True};p.prepare(env,data,out,reserve_fn=lambda *_:{},wp_factory=lambda:wp);atomic_json(out/'parallel/operations'/p.ID/'pilot-reserved.json',{'at':'prior'})
   with patch('automation.agri_v2.family_lifecycle.publish_ready') as call:r=p.pilot(env,data,out,wp_factory=lambda:wp)
   self.assertEqual(r['status'],'source_only_pilot_already_reserved');call.assert_not_called()
 def test_no_admission_no_wordpress_calls(self):
  with patch.object(op,'authorize',return_value=False):
   with self.assertRaises(ValueError):p.prepare({})
