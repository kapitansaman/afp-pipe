import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import semantic_prepublication as s
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json,utcnow
from automation.agri_v2.image_quality import CHECKS
from automation.agri_v2.parallel_control import BRANCH,REPO
class SemanticTests(unittest.TestCase):
 def inputs(self):
  req=load_json(DATA/'alfalfa-semantic-prepublication-request.json');req['code_binding']=s.code_binding()
  with patch.object(s,'age_hours',return_value=0):return s.validate(req,DATA,OUT)
 def test_original_request_stays_invalid_after_infrastructure_change(self):
  with self.assertRaisesRegex(s.GateBlocked,'input_or_code_changed'):s.validate(load_json(DATA/'alfalfa-semantic-prepublication-request.json'),DATA,OUT)
 def overlap(self,batch,passed=True):
  return {'revision_overlap_acceptable':passed,'reason':'A bounded same-post correction retains its exact intent without fabricating a new topic or scientific approval.','article_checks':[{'article_id':d['id'],'already_answers_same_core_intent':False,'material_conflict_or_duplication':not passed,'existing_quote_id':str(d['id'])+':0','reason':'Full existing text was checked against the exact corrected article, not inferred solely from its title.'} for d in batch['documents']]}
 def vision(self,passed=True):return {'score':90,'checks':{k:passed for k in CHECKS},'crop_identity_confident':passed,'supports_revised_article_as_illustration':passed,'botanical_reason':'Visible leaf grouping and margins were inspected directly; uncertain morphology is never accepted merely from a green field.','reasons':['Actual supplied image and revised article inspected independently.']}
 def test_real_complete_bound_inputs_and_five_full_batches(self):
  a,b,bundle=self.inputs();batches=s.overlap_batches(bundle)
  self.assertEqual(len(batches),5);self.assertEqual([d['id'] for g in batches for d in g['documents']],[d['id'] for d in bundle['documents']]);self.assertTrue(all(sum(len(d['text']) for d in g['documents'])<=45000 for g in batches))
 def test_budget_and_publication_cannot_be_expanded(self):
  req=load_json(DATA/'alfalfa-semantic-prepublication-request.json')
  for k,v in [('max_model_calls',13),('publication_authorized',True),('max_runs',2),('new_images',True),('max_search_requests',1),('reset_attempts',True)]:
   with self.subTest(k=k),self.assertRaises(s.GateBlocked):s.validate(dict(req,**{k:v}),DATA,OUT)
 def test_input_and_code_bindings_block_drift(self):
  req=load_json(DATA/'alfalfa-semantic-prepublication-request.json')
  for k in ('input_files','code_binding'):
   with self.subTest(k=k),self.assertRaises(s.GateBlocked):s.validate(dict(req,**{k:{}}),DATA,OUT)
 def test_overlap_requires_every_exact_article_and_literal_quote(self):
  batch=s.overlap_batches(self.inputs()[2])[0];good=self.overlap(batch);s.validate_overlap(good,batch)
  for field,value in [('article_id',999),('existing_quote_id','invented-quote'),('reason','short')]:
   bad=copy.deepcopy(good);bad['article_checks'][0][field]=value
   with self.subTest(field=field),self.assertRaises(s.GateBlocked):s.validate_overlap(bad,batch)
  with self.assertRaises(s.GateBlocked):s.validate_overlap(dict(good,article_checks=good['article_checks'][:-1]),batch)
 def test_negative_or_uncertain_visual_is_never_promoted(self):
  self.assertTrue(s.validate_visual(self.vision())['passed'])
  for k in ('crop_identity_confident','supports_revised_article_as_illustration'):
   bad=self.vision();bad[k]=False
   with self.subTest(k=k),self.assertRaises(s.GateBlocked):s.validate_visual(bad)
  with self.assertRaises(s.GateBlocked):s.validate_visual(self.vision(False))
 def test_receipt_reserves_before_call_and_never_replays_unknown(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);client=Mock();client.text.side_effect=TimeoutError('private')
   with self.assertRaises(TimeoutError):s.call(client,root,'one',{'task':'test'})
   self.assertEqual(load_json(root/'one.receipt.json')['status'],'reserved')
   with self.assertRaises(s.GateBlocked):s.call(client,root,'one',{'task':'test'})
   self.assertEqual(client.text.call_count,1)
 def test_each_text_call_has_one_attempt_and_bounded_output(self):
  with tempfile.TemporaryDirectory() as t:
   client=Mock();client.text.return_value={'ok':True};s.call(client,Path(t),'one',{'task':'test'})
   self.assertEqual(client.text.call_args.kwargs['attempts'],1);self.assertEqual(client.text.call_args.kwargs['max_tokens'],20000)
 def test_negative_image_preserves_both_reviews_and_never_starts_translations(self):
  article,brief,bundle=self.inputs();count=[]
  def fake(client,root,name,prompt,schema=None,vision=None):
   count.append(name)
   if name.startswith('revision-overlap-'):return self.overlap(s.overlap_batches(bundle)[int(name.rsplit('-',1)[1])])
   if name.startswith('image-'):return self.vision(False if name.startswith('image-2') else True)
   raise AssertionError('No translations allowed after negative image')
  with tempfile.TemporaryDirectory() as t,patch.object(s,'call',side_effect=fake):
   with self.assertRaisesRegex(s.GateBlocked,'overlap_or_visual'):s.stages(Mock(),Path(t),article,brief,bundle,{'id':s.TOPIC,'crop':'یونجه','title':'آخرین آبیاری یونجه پیش از برداشت؛ معیارهای قطع و کاهش آب','intent':'preharvest_water'},OUT/'new'/s.TOPIC)
   state=load_json(Path(t)/'blocked-gates.json');self.assertEqual(state['rejected_or_uncertain_image_roles'],[2]);self.assertFalse(state['translations_started']);self.assertEqual(len(count),7)
 def test_negative_overlap_still_covers_all_five_batches_and_both_images(self):
  article,brief,bundle=self.inputs();names=[]
  def fake(client,root,name,prompt,schema=None,vision=None):
   names.append(name)
   if name.startswith('revision-overlap-'):
    i=int(name.rsplit('-',1)[1]);return self.overlap(s.overlap_batches(bundle)[i],passed=i!=0)
   if name.startswith('image-'):return self.vision()
   raise AssertionError('Translation after rejected overlap')
  with tempfile.TemporaryDirectory() as t,patch.object(s,'call',side_effect=fake):
   with self.assertRaises(s.GateBlocked):s.stages(Mock(),Path(t),article,brief,bundle,{'id':s.TOPIC,'crop':'یونجه','title':'آخرین آبیاری یونجه پیش از برداشت؛ معیارهای قطع و کاهش آب','intent':'preharvest_water'},OUT/'new'/s.TOPIC)
  self.assertEqual(len(names),7)
 def test_wrong_event_blocks_before_reservation(self):
  reserve=Mock()
  with self.assertRaises(s.GateBlocked):s.run({},reserve_fn=reserve)
  reserve.assert_not_called()
 def test_remote_duplicate_blocks_without_local_report(self):
  article,brief,bundle=self.inputs();env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REPOSITORY':REPO,'GITHUB_REF_NAME':BRANCH,'GITHUB_RUN_ID':'123'}
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'alfalfa-semantic-prepublication-request.json',{});atomic_json(out/'parallel/health/latest.json',{'checked_at':utcnow(),'eligible_text_slots':[]});factory=Mock()
   with patch.object(s,'validate',return_value=(article,brief,bundle)),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None):result=s.run(env,data,out,client_factory=factory,reserve_fn=lambda e:False)
   self.assertEqual(result['status'],'semantic_already_reserved_no_replay');factory.assert_not_called()
 def test_model_environment_has_no_site_search_ftp_or_repo_credentials(self):
  article,brief,bundle=self.inputs();env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REPOSITORY':REPO,'GITHUB_REF_NAME':BRANCH,'GITHUB_RUN_ID':'123','AFP_WP_APP_PASSWORD':'secret','AFP_SOURCE_SEARCH_API_KEY':'secret','FTP_PASSWORD':'secret','GITHUB_TOKEN':'secret','AGNES_API_KEY1':'test'}
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'alfalfa-semantic-prepublication-request.json',{});atomic_json(out/'parallel/health/latest.json',{'checked_at':utcnow(),'eligible_text_slots':['AGNES_API_KEY']});factory=Mock(return_value=Mock())
   with patch.object(s,'validate',return_value=(article,brief,bundle)),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(s,'get_topic',return_value={'id':s.TOPIC}),patch.object(s,'stages',side_effect=s.GateBlocked('semantic_visual_crop_or_article_rejected')):result=s.run(env,data,out,client_factory=factory,reserve_fn=lambda e:True)
   worker=factory.call_args.kwargs['env'];self.assertFalse(set(worker)&{'AFP_WP_APP_PASSWORD','AFP_SOURCE_SEARCH_API_KEY','FTP_PASSWORD','GITHUB_TOKEN'});self.assertTrue(result['originals_unchanged']);self.assertFalse(result['publication_authorized'])

 def test_positive_gates_make_only_four_new_translations_and_one_independent_review(self):
  article,brief,bundle=self.inputs();names=[];langs=('ru-RU','ar-IQ','tg-TJ','en-US')
  def fake(client,root,name,prompt,schema=None,vision=None):
   names.append(name)
   if name.startswith('revision-overlap-'):return self.overlap(s.overlap_batches(bundle)[int(name.rsplit('-',1)[1])])
   if name.startswith('image-'):return self.vision()
   if name.startswith('translation-'):return {'translations':[]}
   return {'faithful':True,'languages':{l:True for l in langs},'reason':'Every actual target was independently compared to the exact corrected source.','language_reasons':{l:'The actual target preserves crop identity, all claims, Kansas/USA scope and the explicit absence of Iranian fixed rates or dates.' for l in langs}}
  def render(source,raw,lang):return {'language':lang,'title':'Translated title','excerpt':'Translated excerpt','content_html':'<p>Translated source text</p>','faq':[{'question':'Q','answer':'A'}]*3,'source_article_sha256':s.digest(source)}
  with tempfile.TemporaryDirectory() as t,patch.object(s,'call',side_effect=fake),patch('automation.agri_v2.multilingual.render_translation',side_effect=render):
   result=s.stages(Mock(),Path(t),article,brief,bundle,{'id':s.TOPIC,'crop':'یونجه','title':'آخرین آبیاری یونجه','intent':'preharvest_water'},OUT/'new'/s.TOPIC)
   self.assertEqual(len(names),12);self.assertEqual(sum(n.startswith('translation-') for n in names),4);self.assertTrue(result['four_language_fidelity_reviewed']);self.assertTrue(result['regional_publication_review_pending']);self.assertFalse(load_json(Path(t)/'translation-fidelity-review.json')['publication_authorized'])
 def test_visual_incomplete_response_stays_unknown_and_unreplayed(self):
  from automation.agri_v2.client import ModelOutputError
  with tempfile.TemporaryDirectory() as t:
   client=Mock();client.request.return_value={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
   with self.assertRaisesRegex(ModelOutputError,'text_output_limit'):s.call(client,Path(t),'vision',{'image_sha256':'bound'},s.visual_schema(),vision=['data:image/webp;base64,AA=='])
   with self.assertRaises(s.GateBlocked):s.call(client,Path(t),'vision',{'image_sha256':'bound'},s.visual_schema(),vision=[])
   self.assertEqual(client.request.call_count,1);client.record_success.assert_not_called()
