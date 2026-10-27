import copy,datetime,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import language_review_queue as q,multilingual as m,family_scheduler as s
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.pipeline import digest
from test_multilingual import article,response
class LanguageReviewQueueTests(unittest.TestCase):
 def setup(self,d):
  root=Path(d);data=root/'data';out=root/'out';t={'id':'agri-000000000001','title':'هویج'};folder=out/'new'/t['id'];a=article();atomic_json(folder/'article.json',a);atomic_json(data/'config.json',{'multilingual':{'enabled':True,'independent_publication':True}});atomic_json(data/'language-review-policy.json',q.DEFAULT_POLICY);return data,out,folder,a,t
 def test_distinct_language_rows_source_bound_no_attempt_reset(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);q.handoff(t,a,f);self.assertEqual(len(q.entries(out)),4);r=load_json(q.path(f,'tg-TJ'));r['attempts']=2;r['model_calls_spent']=7;atomic_json(q.path(f,'tg-TJ'),r)
   a['excerpt']='متن روشن‌تر';q.ensure(t,a,f,'tg-TJ');r=load_json(q.path(f,'tg-TJ'));self.assertEqual(r['attempts'],2);self.assertEqual(r['model_calls_spent'],7);self.assertEqual(r['article_sha256'],digest(a));self.assertTrue(r['history'])
 def test_failed_attempts_back_off_then_need_attention_never_auto_approve(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);q.ensure(t,a,f,'ru-RU');atomic_json(q.target(f,'ru-RU').with_suffix('.raw.json'),response(a,'ru-RU'));atomic_json(q.target(f,'ru-RU'),m.render_translation(a,response(a,'ru-RU'),'ru-RU'));c=Mock();c.text.side_effect=RuntimeError('provider unavailable')
   for n in range(3):
    state=load_json(q.path(f,'ru-RU'));state['next_attempt_at']='2020-01-01T00:00:00+00:00';atomic_json(q.path(f,'ru-RU'),state)
    with patch.object(q,'source_checked'):q.run_item(q.path(f,'ru-RU'),c,data)
    state=load_json(q.path(f,'ru-RU'));self.assertEqual(state['attempts'],n+1);self.assertFalse(q.approved(f,a,'ru-RU'))
   self.assertEqual(state['status'],'needs_attention');self.assertEqual(c.text.call_count,3);self.assertFalse(q.due(state))
 def test_positive_review_approves_only_one_unchanged_source_language(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);q.handoff(t,a,f);raw=response(a,'ru-RU');atomic_json(q.target(f,'ru-RU').with_suffix('.raw.json'),raw);atomic_json(q.target(f,'ru-RU'),m.render_translation(a,raw,'ru-RU'));c=Mock();c.text.return_value={'faithful':True,'reason':'Compared actual target/source meaning and scope.','issues':[]}
   with patch.object(q,'source_checked'):result=q.run_item(q.path(f,'ru-RU'),c,data)
   self.assertEqual(result['status'],'approved');self.assertTrue(q.approved(f,a,'ru-RU'));self.assertFalse(q.approved(f,a,'tg-TJ'));self.assertEqual(load_json(q.path(f,'tg-TJ'))['status'],'waiting')
   a['excerpt']='منبع تغییر کرده';self.assertFalse(q.approved(f,a,'ru-RU'))
 def test_reserved_uncertain_attempt_not_billed_again(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);row=q.ensure(t,a,f,'ru-RU');row.update(status='reserved',attempts=1,history=[{'max_calls':4}]);atomic_json(q.path(f,'ru-RU'),row);c=Mock();q.run_item(q.path(f,'ru-RU'),c,data);c.text.assert_not_called();self.assertEqual(load_json(q.path(f,'ru-RU'))['model_calls_spent'],4)
 def test_handoff_releases_owner_but_does_not_claim_family_complete(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);atomic_json(f/'wordpress-receipt.json',{'public_verified':True});q.handoff(t,a,f);self.assertFalse(q.released(t['id'],data,out));atomic_json(f/'lifecycle-publication-validation.json',{'article_sha256':digest(a)});self.assertTrue(q.released(t['id'],data,out));self.assertFalse(s.family_complete(t['id'],data,out))
 def test_index_retains_needs_attention_items(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);r=q.ensure(t,a,f,'tg-TJ');r['attempts']=3;q.defer(r,q.path(f,'tg-TJ'),'persistent defect',data);index=q.index(out);self.assertEqual(index['item_count'],1);self.assertEqual(index['items'][0]['status'],'needs_attention')
 def test_false_review_and_invented_quote_cannot_approve(self):
  a=article();_,source=m.source_segments(a);raw=response(a,'ru-RU')
  for value in [{'faithful':True,'reason':'yes','issues':[{'id':0,'detail':'A real error'}]},{'faithful':False,'reason':'no','issues':[{'id':0,'detail':'A real error','target_text':'invented text'}]}]:
   with self.assertRaises(ValueError):q.review_value(value,source,raw)
 def test_healthy_language_first_pass_uses_worker_not_backlog(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);lang=q.primary_next(t,a,f,data);self.assertEqual(lang,m.LANGUAGES[0])
   raw=response(a,lang);atomic_json(q.target(f,lang).with_suffix('.raw.json'),raw);atomic_json(q.target(f,lang),m.render_translation(a,raw,lang));c=Mock();c.text.return_value={'faithful':True,'reason':'Actual source compared','issues':[]}
   with patch.object(q,'source_checked'):q.run_item(q.path(f,lang),c,data)
   self.assertEqual(q.primary_next(t,a,f,data),m.LANGUAGES[1]);self.assertFalse(q.due(load_json(q.path(f,lang))))
 def test_failed_language_does_not_block_remaining_primary_languages(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);lang=q.primary_next(t,a,f,data);c=Mock();c.text.side_effect=ValueError('bad translation')
   with patch.object(q,'source_checked'):q.run_item(q.path(f,lang),c,data)
   self.assertEqual(q.primary_next(t,a,f,data),m.LANGUAGES[1]);row=load_json(q.path(f,lang));self.assertEqual(row['status'],'waiting');self.assertFalse(q.due(row))
 def test_source_changes_do_not_keep_previous_language_approval(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);r=q.ensure(t,a,f,'ru-RU');r.update(status='approved',attempts=1,primary_finished=True);atomic_json(q.path(f,'ru-RU'),r);a['excerpt']='متن تازه';r=q.ensure(t,a,f,'ru-RU');self.assertEqual(r['status'],'waiting');self.assertEqual(r['attempts'],1);self.assertTrue(r['primary_finished'])
 def test_exhausted_legacy_language_is_not_replayed_in_primary_worker(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);lang=m.LANGUAGES[0];p=f/'lifecycle'/('translation-'+lang)/'state.json';atomic_json(p,{'attempts':3,'status':'failed'});before=p.read_bytes();self.assertEqual(q.primary_next(t,a,f,data),m.LANGUAGES[1]);self.assertEqual(before,p.read_bytes());self.assertTrue(load_json(q.path(f,lang))['primary_finished'])
 def test_publication_failure_has_separate_bounded_backoff(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);p=q.path(f,'ru-RU');r=q.ensure(t,a,f,'ru-RU');r['status']='approved';atomic_json(p,r)
   self.assertTrue(q.publication_due(r))
   for _ in range(3):q.publication_failed(p,ValueError('unmapped localized link'))
   r=load_json(p);self.assertEqual(r['status'],'publication_needs_attention');self.assertEqual(r['publication_attempts'],3);self.assertFalse(q.publication_due(r));self.assertEqual(r['model_calls_spent'],0)
 def test_failed_primary_worker_continues_to_source_publication(self):
  from automation.agri_v2 import family_lifecycle as lifecycle
  from test_family_lifecycle import FamilyLifecycleTests
  with tempfile.TemporaryDirectory() as d:
   data,out,t,env,health=FamilyLifecycleTests().setup(d);folder=out/'new'/t['id'];atomic_json(data/'language-review-policy.json',q.DEFAULT_POLICY);q.ensure(t,article(),folder,'ru-RU')
   with patch.object(lifecycle,'next_stage',side_effect=[('language_primary-ru-RU',None),('publish',None)]),patch.object(lifecycle,'run_stage',side_effect=ValueError('invalid target')),patch('automation.agri_v2.recovery.circuit_open',return_value=False):result=lifecycle.worker(t,health,data,out,env,lambda *args,**kw:Mock())
   self.assertEqual(result['status'],'publication_ready');self.assertEqual(result['steps'][0]['status'],'stage_failed');self.assertTrue(load_json(q.path(folder,'ru-RU'))['primary_finished'])
 def test_unavailable_provider_hands_off_language_without_blocking_source(self):
  from automation.agri_v2 import family_lifecycle as lifecycle
  from test_family_lifecycle import FamilyLifecycleTests
  with tempfile.TemporaryDirectory() as d:
   data,out,t,env,health=FamilyLifecycleTests().setup(d);folder=out/'new'/t['id'];atomic_json(data/'language-review-policy.json',q.DEFAULT_POLICY);q.ensure(t,article(),folder,'ru-RU');factory=Mock()
   with patch.object(lifecycle,'next_stage',side_effect=[('language_primary-ru-RU',None),('publish',None)]),patch('automation.agri_v2.recovery.circuit_open',return_value=True):result=lifecycle.worker(t,health,data,out,env,factory)
   self.assertEqual(result['status'],'publication_ready');factory.assert_not_called();self.assertFalse(q.due(load_json(q.path(folder,'ru-RU'))))
 def test_bad_locale_does_not_block_approved_sibling_or_duplicate_posts(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);q.handoff(t,a,f);media=[{'index':1,'id':11,'url':'https://navar-abyari.ir/a.webp'},{'index':2,'id':12,'url':'https://navar-abyari.ir/b.webp'}]
   atomic_json(data/'internal-links.json',{'related':[]});atomic_json(data/'internal-links-i18n.json',{'languages':{lang:[] for lang in m.LANGUAGES}});atomic_json(f/'wordpress-draft-payload.json',{'slug':'carrot'});atomic_json(f/'wordpress-receipt.json',{'media':media})
   for lang in ['ru-RU','en-US']:
    raw=response(a,lang);row=m.render_translation(a,raw,lang);atomic_json(q.target(f,lang),row);atomic_json(q.target(f,lang).with_suffix('.raw.json'),raw);atomic_json(q.proof_path(f,lang),{'article_sha256':digest(a),'translation_sha256':digest(row),'review':{'faithful':True,'issues':[]}});r=load_json(q.path(f,lang));r['status']='approved';atomic_json(q.path(f,lang),r)
   class WP:
    user_id=7
    def __init__(self):self.posts={};self.creates=0
    def call(self,path,method='GET',data=None):
     if method=='OPTIONS':return {'schema':{'properties':{'afp_language':{},'afp_source_post_id':{}}}},{}
     if path.startswith('posts?'):return [],{}
     if path=='posts':
      self.creates+=1;p=dict(data,id=100,author=7,title={'rendered':data['title']},content={'raw':data['content'],'rendered':data['content']},link='https://navar-abyari.ir/carrot-en-us/');self.posts[100]=p;return p,{}
     p=self.posts[int(path.split('/')[1].split('?')[0])]
     if method=='POST':p.update(data)
     return p,{}
   def body(row,*_):
    if row['language']=='ru-RU':raise ValueError('unmapped locale link')
    return '<p>'+media[1]['url']+'</p>'
   wp=WP()
   with patch.object(m,'DATA',data),patch.object(m,'localized_body',side_effect=body),patch.object(m,'verify_target',return_value=True):
    result=m.publish_family(wp,f,t,{'post_id':500});again=m.publish_family(wp,f,t,{'post_id':500})
   self.assertEqual(result['translations']['ru-RU']['status'],'publication_deferred');self.assertTrue(result['translations']['en-US']['public_verified']);self.assertEqual(wp.creates,1);self.assertTrue(again['translations']['en-US']['public_verified']);self.assertEqual(load_json(q.path(f,'ru-RU'))['publication_attempts'],1)
 def test_persian_residue_is_repaired_locally_not_rejected_repeatedly(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);q.ensure(t,a,f,'en-US');raw=response(a,'en-US');original=raw['translations'][0]['text'];raw['translations'][0]['text']+=' متن فارسی';atomic_json(f/'review-queue/candidate-en-US.json',{'article_sha256':digest(a),'raw':raw});c=Mock();c.text.side_effect=[{'patches':[{'id':0,'text':original}]},{'faithful':True,'reason':'Source meaning restored','issues':[]}]
   with patch.object(q,'source_checked'):result=q.run_item(q.path(f,'en-US'),c,data)
   self.assertEqual(result['status'],'approved');self.assertEqual(c.text.call_count,2);self.assertEqual(load_json(q.target(f,'en-US').with_suffix('.raw.json'))['translations'][1:],raw['translations'][1:])
 def test_tajik_reviewer_corrects_own_crop_glossary_error_before_editing(self):
  with tempfile.TemporaryDirectory() as d:
   data,out,f,a,t=self.setup(d);a['commercial_matrix']={'crop':'هویج'};atomic_json(f/'article.json',a);q.ensure(t,a,f,'tg-TJ');raw=response(a,'tg-TJ');i=len(m.source_segments(a)[0].texts);raw['translations'][i]['text']+=' сабзӣ';atomic_json(q.target(f,'tg-TJ').with_suffix('.raw.json'),raw);atomic_json(q.target(f,'tg-TJ'),m.render_translation(a,raw,'tg-TJ'));c=Mock();c.text.side_effect=[{'faithful':False,'reason':'Crop mismatch','issues':[{'id':i,'category':'crop_product','detail':'сабзӣ means dill'}]},{'faithful':True,'reason':'The crop glossary confirms carrot, prior claim withdrawn','issues':[]}]
   with patch.object(q,'source_checked'):result=q.run_item(q.path(f,'tg-TJ'),c,data)
   self.assertEqual(result['status'],'approved');self.assertEqual(c.text.call_count,2);self.assertIn('reviewer_feedback',c.text.call_args.args[0]);self.assertFalse(list((f/'review-queue/attempts/tg-TJ/1').glob('edit.receipt.json')))
