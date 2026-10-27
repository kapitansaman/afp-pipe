import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import role_skills as s
from automation.agri_v2 import role_skills_launch as launch
from automation.agri_v2 import operation_request as op
from automation.agri_v2.queue import DATA,load_json,atomic_json
from automation.agri_v2.translation_review_repair import request
class RoleSkillsTests(unittest.TestCase):
 def test_all_roles_are_concise_and_distinct(self):
  packs=[s.pack(r) for r in s.ROLES];self.assertTrue(all(p and len(p['instructions'])<7000 for p in packs));self.assertEqual(len({p['sha256'] for p in packs}),len(s.ROLES))
 def test_tajik_reference_only_attached_to_tajik(self):
  self.assertIn('киштзор',s.pack('translator','tg-TJ')['instructions']);self.assertNotIn('киштзор',s.pack('translator','en-US')['instructions']);self.assertIn('сабзӣ',s.pack('translation-reviewer','tg-TJ')['instructions'])
 def test_enrichment_preserves_task_schema_and_source(self):
  row={'task':'Translate','source':[{'id':0,'text':'هویج'}],'output':{'translations':[]}};copy_row=copy.deepcopy(row);result=json.loads(s.enrich(json.dumps(row),'translator','tg-TJ'));self.assertEqual(row,copy_row);self.assertEqual(result['source'],row['source']);self.assertEqual(result['output'],row['output']);self.assertEqual(result['role_skill']['id'],'translator')
 def test_proxy_forwards_budget_and_does_not_make_extra_calls(self):
  client=Mock();client.__dict__['_max_translation_review_repair_calls']=2;proxy=s.RoleClient(client,'evidence-reviewer');proxy.text('{"task":"Review"}',attempts=1);self.assertEqual(client.text.call_count,1);self.assertEqual(proxy.__dict__['_max_translation_review_repair_calls'],2);self.assertEqual(json.loads(client.text.call_args.args[0])['role_skill']['id'],'evidence-reviewer')
 def test_unknown_skill_or_conflicting_binding_is_rejected(self):
  with self.assertRaises(ValueError):s.pack('../escape')
  with self.assertRaises(ValueError):s.enrich({'role_skill':{'id':'forged'}},'translator')
 def test_missing_fixture_pack_does_not_borrow_other_workspace(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(json.loads(s.enrich({'task':'Review'},'evidence-reviewer',data=Path(d))),{'task':'Review'})
 def test_skill_is_bound_to_durable_receipt_before_model_call(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);c=Mock();c.text.return_value={'faithful':True};prompt={'_role_skill':'translation-reviewer','_role_language':'tg-TJ','task':'Review'};request(c,root,'review',prompt,4);raw=c.text.call_args.args[0];self.assertIn('role_skill',json.loads(raw));self.assertNotIn('_role_skill',json.loads(raw));first=load_json(root/'review.receipt.json');self.assertTrue(first['prompt_sha256']);request(c,root,'review',prompt,4);self.assertEqual(c.text.call_count,1)
 def test_role_stage_mapping_not_shared_across_families(self):
  c=Mock();self.assertEqual(s.for_stage(c,'text').role,'persian-writer');self.assertEqual(s.for_stage(c,'research_extract').role,'researcher');self.assertEqual(s.for_stage(c,'article_evidence_review').role,'evidence-reviewer');self.assertIs(s.for_stage(c,'language_primary-en-US'),c)
 def test_request_has_exact_limits_and_cannot_enable_timer(self):
  req=dict(launch.expected_request(),code_revision='a'*40);self.assertEqual(op.validate_request(req),req)
  for key,value in [('enable_schedule',True),('reset_attempts',True),('max_image_calls',4),('max_total_text_calls',20),('max_total_posts',6)]:
   with self.assertRaises(ValueError):op.validate_request(dict(req,**{key:value}))
 def test_launch_source_is_current_reviewed_immutable_pair(self):
  topic,brief,a,source,dest=launch.source_inputs();self.assertEqual(topic['id'],launch.TOPIC);self.assertEqual(launch.digest(a),launch.SOURCE_SHA);self.assertEqual(load_json(dest/'lifecycle/text/state.json')['attempts'],3)
 def test_preservation_allows_additions_never_existing_file_changes(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d);atomic_json(f/'old.json',{'attempts':3});old=launch.files_hash(f);atomic_json(f/'new.json',{'valid':True});self.assertTrue(launch.preserved_files(f,old));atomic_json(f/'old.json',{'attempts':0});self.assertFalse(launch.preserved_files(f,old))
 def test_launch_prerequisite_failure_never_probes_or_adopts_source(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';source=out/'source';dest=out/'dest';source.mkdir(parents=True);dest.mkdir();atomic_json(out/'parallel/families/assignments.json',{'owners':[1]})
   check=Mock(return_value={'gates':{k:{'passed':False} for k in ['fresh_text_capacity','authenticated_publisher','translation_bridge','lifecycle_enabled']}});image=Mock()
   with patch.object(launch,'admission'),patch('automation.agri_v2.parallel_control.policy'),patch.object(launch,'source_inputs',return_value=({'title':'test'},{},{},source,dest)):
    r=launch.prepare({'GITHUB_RUN_ID':'12'},data,out,reserve_fn=lambda *a:True,image_fn=image,readiness_fn=check)
   self.assertEqual(r['status'],'launch_prerequisites_blocked');image.assert_not_called();self.assertFalse((dest/'article.json').exists())
 def test_launch_one_failed_probe_cannot_admit_pilot(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';source=out/'source';dest=out/'dest';source.mkdir(parents=True);dest.mkdir();atomic_json(out/'parallel/families/assignments.json',{})
   gates={k:{'passed':True} for k in ['fresh_text_capacity','authenticated_publisher','translation_bridge','lifecycle_enabled']};gates['fresh_image_capacity']={'passed':False};image=Mock(return_value={'image_calls':1,'status':'failed'})
   with patch.object(launch,'admission'),patch('automation.agri_v2.parallel_control.policy'),patch.object(launch,'source_inputs',return_value=({'title':'test'},{},{},source,dest)):
    r=launch.prepare({'GITHUB_RUN_ID':'12'},data,out,reserve_fn=lambda *a:True,image_fn=image,readiness_fn=lambda *a:{'gates':gates})
   self.assertEqual(r['status'],'launch_prerequisites_blocked');self.assertEqual(r['image_calls'],1);self.assertEqual(image.call_count,1);self.assertEqual(image.call_args.kwargs['request_id'],launch.ID)
 def test_publisher_limits_mutations_and_creates_before_sending(self):
  from automation.agri_v2.wordpress import WordPress
  with tempfile.TemporaryDirectory() as d,patch.object(WordPress,'call',return_value=({},{})) as send:
   root=Path(d);wp=launch.BoundedPublisher.create({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'},root)
   for i in range(5):wp.call('posts','POST',{})
   with self.assertRaises(ValueError):wp.call('posts','POST',{})
   self.assertEqual(send.call_count,5)
   for i in range(10):wp.call('posts/1','POST',{})
   with self.assertRaises(ValueError):wp.call('media','POST',{})
   with self.assertRaises(ValueError):wp.call('posts/1','DELETE')
   self.assertEqual(send.call_count,15);self.assertEqual(load_json(root/'wordpress-mutations.json')['reserved_mutations'],15)
 def test_image_feedback_adds_skill_not_a_false_approval_or_contract_change(self):
  from automation.agri_v2.media_policy import contract_hash,generate_role
  topic={'id':'agri-000000000001','crop':'هویج','title':'چرا بذر هویج سبز نمی‌شود؟'};before=contract_hash(topic,2);c=Mock();c.image_feedback={'reasons':['wrong broad-leaf crop'],'checks':{'crop_stage_match':False}};generate_role(c,topic,2)
  prompt=c.image.call_args.args[0];self.assertIn('Daucus carota',prompt);self.assertIn('wrong broad-leaf crop',prompt);self.assertEqual(before,contract_hash(topic,2));self.assertEqual(c.image.call_count,1)
 def test_image_continuation_has_explicit_finite_combined_budget(self):
  r=dict(launch.expected_request(launch.CONT_ID),code_revision='b'*40);self.assertEqual(op.validate_request(r),r);self.assertEqual(r['max_image_calls'],1);self.assertEqual(r['max_image_health_calls'],0);self.assertEqual(r['max_combined_model_calls'],24);self.assertEqual(r['prior_reserved_model_calls'],6)
  for key,value in [('max_image_calls',2),('max_total_text_calls',18),('max_combined_model_calls',25),('replace_rejected_image_sha256','c'*64),('reset_attempts',True)]:
   with self.assertRaises(ValueError):op.validate_request(dict(r,**{key:value}))
 def test_image_continuation_refuses_changed_rejected_candidate_before_probe(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';dest=root/'dest';dest.mkdir();(dest/'image-2.webp').write_bytes(b'changed');atomic_json(root/'parallel/operations'/launch.ID/'prepare.json',{'status':'controlled_launch_blocked','failed_stage':'vision-2','model_calls':3,'image_calls':3,'wordpress_calls':0,'protected_existing_files_unchanged':True,'experimental_source_unchanged':True,'assignments_unchanged':True});reserve=Mock()
   with patch.object(launch,'admission'),patch('automation.agri_v2.parallel_control.policy'),patch.object(launch,'source_inputs',return_value=({}, {}, {},source,dest)):
    with self.assertRaises(ValueError):launch.prepare_continuation({'GITHUB_RUN_ID':'99'},root,root,reserve_fn=reserve)
   reserve.assert_not_called()
