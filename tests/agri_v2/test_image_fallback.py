import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import image_workflow as w,image_quality as q,family_lifecycle as f,multilingual as m
from automation.agri_v2.queue import DATA,atomic_json,load_json
from automation.agri_v2.image_layout import roles_for
from automation.agri_v2.wordpress import illustrated_content,WordPress
from automation.agri_v2.parallel_pool import PoolDeferred
class FakeClient:
 def __init__(self,plans):self.plans=copy.deepcopy(plans);self.images=[];self.reviews=[];self.feedback=[]
 def image(self,prompt,references=None):
  self.images.append(prompt);self.feedback.append(copy.deepcopy(getattr(self,'image_feedback',None)));return ('candidate-'+str(len(self.images))).encode()
 def review_image(self,blob,topic,kind,article=None):
  self.reviews.append(kind);good=self.plans[kind].pop(0) if self.plans[kind] else False
  return {'score':85 if good else 30,'checks':{k:(good if k=='crop_stage_match' else True) for k in q.CHECKS},'reasons':['Correct crop' if good else 'Wrong crop: preserve actual carrot leaf morphology']}
class ImageFallbackTests(unittest.TestCase):
 def fixture(self,tmp):
  root=Path(tmp);data=root/'data';folder=root/'out';folder.mkdir();atomic_json(data/'image-repair-policy.json',load_json(DATA/'image-repair-policy.json'));topic={'id':'agri-000000000001','title':'چرا بذر هویج سبز نمی‌شود؟','crop':'هویج'};a={'title':topic['title'],'excerpt':'آزمون','content_html':'<p>متن آزمایشی</p>'};atomic_json(folder/'article.json',a);return data,folder,topic,a
 def test_two_approved_images_and_repeat_have_no_extra_calls(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[True],2:[True]});r=w.advance(c,folder,t,a,'1',data);self.assertEqual(r['roles'],[1,2]);self.assertEqual(len(c.images),2);q.require_all(folder,t,a);w.advance(c,folder,t,a,'2',data);self.assertEqual(len(c.images),2)
 def test_initial_plus_three_corrections_then_single_without_failed_upload(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[True],2:[False]*4});r=w.advance(c,folder,t,a,'1',data);self.assertEqual(r['status'],'images_ready');self.assertEqual(r['roles'],[1]);self.assertTrue(r['fallback_used']);self.assertEqual(len(c.images),5);self.assertEqual(f.state(folder,'image-2')['attempts'],4);self.assertEqual(f.state(folder,'vision-2')['attempts'],4);self.assertEqual(len(list((folder/'lifecycle/image-2/rejected').glob('*/image-2.webp'))),3);self.assertTrue(all(c.feedback[i] for i in [2,3,4]));q.require_all(folder,t,a);self.assertEqual(roles_for(folder),(1,));self.assertNotIn('<figure',illustrated_content(a['content_html'],[{'url':'https://example.com/approved.webp'}],t['crop']))
 def test_fourth_candidate_can_pass_without_fallback(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[True],2:[False,False,False,True]});r=w.advance(c,folder,t,a,'1',data);self.assertEqual(r['roles'],[1,2]);self.assertEqual(f.state(folder,'image-2')['attempts'],4)
 def test_role_two_alone_can_be_featured(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);r=w.advance(FakeClient({1:[False]*4,2:[True]}),folder,t,a,'1',data);self.assertEqual(r['roles'],[2]);q.require_all(folder,t,a)
 def test_zero_approved_never_creates_selection_or_pass(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[False]*4,2:[False]*4});r=w.advance(c,folder,t,a,'1',data);self.assertEqual(r['status'],'images_need_attention');self.assertEqual(len(c.images),8);self.assertFalse(w.selection_path(folder).exists())
   with self.assertRaises(ValueError):q.require_all(folder,t,a)
   w.advance(c,folder,t,a,'2',data);self.assertEqual(len(c.images),8)
 def test_changed_source_or_retained_image_cannot_reuse_selection(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);w.advance(FakeClient({1:[True],2:[False]*4}),folder,t,a,'1',data)
   with self.assertRaises(ValueError):q.require_all(folder,t,dict(a,excerpt='changed'))
   (folder/'image-1.webp').write_bytes(b'changed')
   with self.assertRaises(ValueError):q.require_all(folder,t,a)
 def test_premature_single_selection_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);w.advance(FakeClient({1:[True],2:[True]}),folder,t,a,'1',data)
   with self.assertRaises(ValueError):w.seal_selection(folder,t,a,(1,))
 def test_generation_deferral_does_not_spend_invalid_candidate_budget(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[],2:[]});c.image=Mock(side_effect=PoolDeferred('wait'));r=w.advance(c,folder,t,a,'1',data);self.assertEqual(r['status'],'images_deferred');self.assertEqual(f.state(folder,'image-1')['attempts'],0);c.image.assert_called_once()
 def test_review_admission_deferral_is_not_a_rejected_image(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[],2:[]});c.review_image=Mock(side_effect=PoolDeferred('wait'));r=w.advance(c,folder,t,a,'1',data);self.assertEqual(r['status'],'images_deferred');self.assertEqual(f.state(folder,'vision-1')['attempts'],0);self.assertEqual(len(c.images),1)
 def test_prior_three_attempts_are_preserved_not_granted_three_more(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[True],2:[False]*4});w.advance(c,folder,t,a,'old',data)
   # Build exact legacy three-attempt checkpoint by restoring its archived third candidate.
   image=folder/'image-2.webp';qa=image.with_suffix('.quality.json');image.write_bytes((folder/'lifecycle/image-2/rejected/3/image-2.webp').read_bytes());qa.write_bytes((folder/'lifecycle/image-2/rejected/3/image-2.quality.json').read_bytes());__import__('shutil').rmtree(folder/'lifecycle/image-2/rejected/3');w.selection_path(folder).unlink()
   for stage in ['image-2','vision-2']:
    row=f.state(folder,stage);row['attempts']=3;row['history']=row['history'][:3];atomic_json(f.row_path(folder,stage),row)
   c=FakeClient({1:[],2:[False]});r=w.advance(c,folder,t,a,'new',data);self.assertEqual(len(c.images),1);self.assertEqual(r['roles'],[1]);self.assertEqual(f.state(folder,'image-2')['attempts'],4);self.assertEqual(len(f.state(folder,'image-2')['history']),4)
 def test_selected_roles_are_strict_integers(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);atomic_json(w.selection_path(folder),{'selected_roles':[True]})
   with self.assertRaises(ValueError):roles_for(folder)
 def test_single_image_localization_never_duplicates_featured_or_adds_upload(self):
  from test_multilingual import article,response
  a=article();row=m.render_translation(a,response(a),'en-US');body=m.localized_body(row,[{'id':11,'url':'https://navar-abyari.ir/a.webp'}],{'en-US':[]});self.assertNotIn('<figure',body);self.assertNotIn('a.webp',body)
  with self.assertRaises(ValueError):m.localized_body(row,[],{'en-US':[]})
 def test_identical_images_are_not_counted_twice(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);c=FakeClient({1:[True],2:[True]*4});c.image=lambda *args,**kw:b'same pixels';r=w.advance(c,folder,t,a,'1',data);self.assertEqual(r['roles'],[1]);self.assertEqual(f.state(folder,'image-2')['attempts'],4)
 def test_wordpress_uploads_only_retained_role_two_without_inline_duplicate(self):
  with tempfile.TemporaryDirectory() as d,patch('automation.agri_v2.wordpress.validate_targets'):
   data,folder,t,a=self.fixture(d);a['faq']=[{'question':'این پرسش صرفاً برای آزمون قالب است؟','answer':'این پاسخ صرفاً برای آزمون مسیر انتشار نوشته شده و توصیهٔ کشاورزی محسوب نمی‌شود.'}]*3;atomic_json(folder/'article.json',a);w.advance(FakeClient({1:[False]*4,2:[True]}),folder,t,a,'1',data);atomic_json(folder/'wordpress-draft-payload.json',{'slug':'fixture','content':a['content_html']})
   wp=WordPress({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'});wp.user_id=7;wp.preflight=Mock();wp.publish_family=lambda *args:args[-1];post={};uploads=[]
   def call(path,method='GET',data=None,blob=None,headers=None):
    if path.startswith('posts?') or path.startswith('media?'):return [],{}
    if path=='posts':
     post.update(data,id=50,author=7,title={'rendered':t['title']},content={'raw':data['content'],'rendered':data['content']},link='https://navar-abyari.ir/fixture/');return post,{}
    if path=='media':uploads.append(headers['Content-Disposition']);return {'id':101},{}
    if path.startswith('media/'):return {'id':101,'source_url':'https://navar-abyari.ir/media/101'},{}
    if method=='POST':
     if 'content' in data:post['content']={'raw':data['content'],'rendered':data['content']}
     post.update({k:v for k,v in data.items() if k!='content'})
    return post,{}
   wp.call=call;response=Mock();response.status=200;response.read.return_value=t['title'].encode();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
   with patch('automation.agri_v2.wordpress.urllib.request.urlopen',return_value=response):r=wp.publish(folder,t,{'publish_authorized':True},True)
   self.assertTrue(r['public_verified']);self.assertEqual(len(uploads),1);self.assertIn('image-2',uploads[0]);self.assertEqual(post['featured_media'],101);self.assertNotIn('<figure',post['content']['rendered']);self.assertEqual(load_json(folder/'wordpress-receipt.json')['selected_image_roles'],[2])
 def test_four_translations_reuse_one_media_without_uploads_or_duplicate_images(self):
  from test_multilingual import article,response
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);a=article();atomic_json(folder/'article.json',a);media=[{'index':2,'id':12,'url':'https://navar-abyari.ir/uploads/b.webp'}];atomic_json(folder/'wordpress-receipt.json',{'media':media,'selected_image_roles':[2]});atomic_json(folder/'wordpress-draft-payload.json',{'slug':'source'});atomic_json(data/'config.json',{'multilingual':{'enabled':True}});atomic_json(data/'internal-links.json',{'related':[]});atomic_json(data/'internal-links-i18n.json',{'languages':{lang:[] for lang in m.LANGUAGES}})
   for lang in m.LANGUAGES:atomic_json(folder/'translations'/f'{lang}.json',m.render_translation(a,response(a,lang),lang))
   class WP:
    user_id=7
    def __init__(self):self.posts={};self.requests=[]
    def call(self,path,method='GET',data=None):
     self.requests.append((path,method))
     if method=='OPTIONS':return {'schema':{'properties':{'afp_language':{},'afp_source_post_id':{}}}},{}
     if path.startswith('posts?'):
      import urllib.parse
      query=urllib.parse.parse_qs(urllib.parse.urlsplit(path).query);return [p for p in self.posts.values() if p['slug']==query['slug'][0] and p['status']==query['status'][0]],{}
     if path=='posts':
      ident=100+len(self.posts);p=dict(data,id=ident,author=7,title={'rendered':data['title']},content={'raw':data['content'],'rendered':data['content']},link='https://navar-abyari.ir/'+data['slug']+'/');self.posts[ident]=p;return p,{}
     ident=int(path.split('/')[1].split('?')[0]);p=self.posts[ident]
     if method=='POST':p.update(data)
     return p,{}
   wp=WP()
   with patch.object(m,'DATA',data),patch.object(m,'verify_target',return_value=True):
    m.publish_family(wp,folder,t,{'post_id':500});result=m.publish_family(wp,folder,t,{'post_id':500})
   self.assertEqual(len(wp.posts),4);self.assertTrue(all(x.get('public_verified') for x in result['translations'].values()));self.assertFalse(any(p.startswith('media') for p,method in wp.requests));self.assertEqual({p['featured_media'] for p in wp.posts.values()},{12});self.assertTrue(all('<figure' not in p['content']['rendered'] for p in wp.posts.values()))
 def test_same_run_exception_is_image_only_not_a_text_retry_reset(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(f.StageBlocked):f.attempt(Path(d),'text','1',lambda:None,allow_same_run=True)
 def test_live_test_scope_forbids_every_wordpress_mutation_and_activation(self):
  from automation.agri_v2.image_fallback_verification import expected_request
  from automation.agri_v2.operation_request import validate_request
  r=dict(expected_request(),code_revision='a'*40);self.assertEqual(validate_request(r),r);self.assertEqual(r['max_wordpress_mutations'],0);self.assertEqual(r['max_image_calls'],1);self.assertEqual(r['remaining_generation_attempts'],1)
  for key,value in [('max_wordpress_mutations',1),('enable_schedule',True),('reset_attempts',True),('max_image_calls',2),('max_total_model_calls',19)]:
   with self.assertRaises(ValueError):validate_request(dict(r,**{key:value}))
 def test_single_selection_cannot_silently_switch_after_publication_receipt(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);w.advance(FakeClient({1:[True],2:[False]*4}),folder,t,a,'1',data);atomic_json(folder/'wordpress-receipt.json',{'selected_image_roles':[2]})
   with self.assertRaises(ValueError):q.require_all(folder,t,a)
 def test_zero_approved_image_never_sends_a_wordpress_post(self):
  with tempfile.TemporaryDirectory() as d,patch('automation.agri_v2.wordpress.validate_targets'):
   data,folder,t,a=self.fixture(d);w.advance(FakeClient({1:[False]*4,2:[False]*4}),folder,t,a,'1',data);atomic_json(folder/'wordpress-draft-payload.json',{'slug':'fixture','content':a['content_html']});wp=WordPress({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'});wp.user_id=7;wp.preflight=Mock();wp.call=Mock(return_value=([],{}))
   with self.assertRaises(ValueError):wp.publish(folder,t,{'publish_authorized':True},True)
   self.assertFalse(any((c.args[1] if len(c.args)>1 else c.kwargs.get('method'))=='POST' for c in wp.call.call_args_list))
 def test_selected_review_tampering_invalidates_fallback(self):
  with tempfile.TemporaryDirectory() as d:
   data,folder,t,a=self.fixture(d);w.advance(FakeClient({1:[True],2:[False]*4}),folder,t,a,'1',data);p=folder/'image-1.quality.json';r=load_json(p);r['verdict']['score']=99;atomic_json(p,r)
   with self.assertRaises(ValueError):q.require_all(folder,t,a)
