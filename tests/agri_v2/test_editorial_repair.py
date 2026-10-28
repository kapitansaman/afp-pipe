import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import editorial_repair as r
from automation.agri_v2.editorial_presentation import VERSION,START,END
from automation.agri_v2.queue import DATA,load_json,atomic_json
class EditorialRepairTests(unittest.TestCase):
 def setup(self,root):
  data=root/'data';out=root/'out';req=load_json(DATA/'editorial-repair-request.json');atomic_json(data/'editorial-repair-request.json',req);folder=out/'new'/r.TOPIC
  atomic_json(data/'briefs'/(r.TOPIC+'.json'),{'sources':[{'url':'https://example.edu/beets'}]});atomic_json(folder/'wordpress-receipt.json',{'post_id':524196,'commercial_matrix':{'version':'search-to-drip-content-matrix-v1','cta_mode':'none'}});atomic_json(folder/'translations/en-US.wordpress.json',{'post_id':524200})
  posts={};mutations=[]
  for row in req['posts']:
   lang=row['language'];ident=row['post_id'];marker='<!-- afp-agri-v2:'+r.TOPIC+(' -->' if lang=='fa-IR' else ':'+lang+' -->')
   posts[ident]={'id':ident,'author':7,'status':'publish','modified_gmt':row['expected_modified_gmt'],'title':{'raw':'Title','rendered':'Title'},'link':'https://navar-abyari.ir/'+str(ident)+'/','featured_media':80,'afp_language':lang,'afp_source_post_id':0 if lang=='fa-IR' else 524196,'content':{'raw':marker+'<p>متن <a href="https://example.edu/beets">منبع</a></p><p><a href="https://example.edu/beets">منبع</a></p><figure><img src="https://navar-abyari.ir/media/81"/></figure><h2>FAQ</h2><p>Answer</p>'}}
  wp=Mock();wp.user_id=7;wp.site='https://navar-abyari.ir';wp.inventory.return_value={'records':[{'id':42,'title':'کاشت چغندر لبویی','language':'fa-IR','status':'publish','url':'https://navar-abyari.ir/beet-growing/'}]}
  def call(path,method='GET',data=None):
   if path.startswith('posts/42?'):return {'afp_translation_links':{'en-US':'https://navar-abyari.ir/beet-growing-en/'}},{}
   if path.startswith('posts?slug=beet-growing-en'):return [{'id':43,'status':'publish','afp_language':'en-US','afp_source_post_id':42,'link':'https://navar-abyari.ir/beet-growing-en/','title':{'rendered':'Growing table beet'}}],{}
   ident=int(path.split('/')[1].split('?')[0]);p=posts[ident]
   if method=='POST':mutations.append((ident,copy.deepcopy(data)));p['content']['raw']=data['content'];p['modified_gmt']='changed'
   value=copy.deepcopy(p);value['content']['rendered']=value['content']['raw'];return value,{}
  wp.call=call
  return data,out,wp,posts,mutations
 def test_exact_content_only_two_post_repair_preserves_prose_images_title_and_languages(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r,'get_topic',return_value={'crop':'چغندر لبویی','title':'برداشت چغندر لبویی'}),patch.object(r,'verify_target') as verify,patch.object(r,'validate_targets'),patch('automation.agri_v2.client.ModelClient.request',side_effect=AssertionError('No model calls')):
   data,out,wp,posts,mutations=self.setup(Path(td));before=copy.deepcopy(posts);result=r.run(data,out,wp)
   self.assertEqual(result['status'],'public_presentation_verified');self.assertEqual(len(mutations),2)
   for ident,payload in mutations:
    self.assertEqual(set(payload),{'content'});body=payload['content'];self.assertEqual(body.count('href="https://example.edu/beets"'),1);self.assertTrue(body.endswith(END));self.assertLess(body.index('FAQ'),body.index(START));self.assertIn('<figure><img src="https://navar-abyari.ir/media/81"/></figure>',body)
    for key in ('title','featured_media','afp_language','afp_source_post_id'):self.assertEqual(posts[ident][key],before[ident][key])
   self.assertIn('Growing table beet',posts[524200]['content']['raw']);self.assertNotIn('beet-growing/"',posts[524200]['content']['raw']);self.assertIn('beet-growing/"',posts[524196]['content']['raw']);self.assertEqual(len(list((out/'editorial-repairs'/r.ID).glob('*-before.json'))),2)
   self.assertEqual(r.run(data,out,wp)['status'],'already_reserved_no_replay');self.assertEqual(len(mutations),2)
 def test_revision_ownership_or_language_change_blocks_all_writes(self):
  for kind in ('modified_gmt','author','afp_language','afp_source_post_id'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td,patch.object(r,'get_topic',return_value={'crop':'چغندر لبویی'}):
    data,out,wp,posts,mutations=self.setup(Path(td));posts[524200][kind]='wrong'
    with self.assertRaises(r.WPError):r.run(data,out,wp)
    self.assertEqual(mutations,[])
 def test_partial_write_retains_backup_and_blocks_replay(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r,'get_topic',return_value={'crop':'چغندر لبویی'}),patch.object(r,'verify_target'),patch.object(r,'validate_targets'):
   data,out,wp,posts,mutations=self.setup(Path(td));original=wp.call
   def broken(path,method='GET',data=None):
    if path=='posts/524200' and method=='POST':raise RuntimeError('Connection lost; outcome unknown')
    return original(path,method,data)
   wp.call=broken;result=r.run(data,out,wp);self.assertEqual(result['status'],'repair_stopped_reconciliation_required');self.assertEqual(len(mutations),1);self.assertEqual(r.run(data,out,wp)['status'],'already_reserved_no_replay');self.assertEqual(len(mutations),1)
 def test_no_relevant_language_target_does_not_insert_random_link(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r,'get_topic',return_value={'crop':'چغندر لبویی'}),patch.object(r,'verify_target'),patch.object(r,'validate_targets'):
   data,out,wp,posts,mutations=self.setup(Path(td));wp.inventory.return_value={'records':[]};result=r.run(data,out,wp);self.assertEqual(result['status'],'public_presentation_verified');self.assertEqual(result['results']['fa-IR']['related_articles'],[]);self.assertNotIn('Related articles:',posts[524200]['content']['raw'])
 def test_request_cannot_expand_post_set_or_use_models(self):
  req=load_json(DATA/'editorial-repair-request.json')
  for key,value in (('max_model_calls',1),('max_new_posts',1),('max_existing_posts',3),('authorized',False)):
   bad=copy.deepcopy(req);bad[key]=value
   with self.assertRaises(ValueError):r.validate(bad)

 def test_reconciliation_reads_existing_persian_update_and_writes_only_untouched_english(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r,'get_topic',return_value={'crop':'چغندر لبویی'}),patch.object(r,'verify_target'),patch.object(r,'validate_targets'):
   data,out,wp,posts,mutations=self.setup(Path(td))
   with patch.object(r,'verify_sources',side_effect=ValueError('Old WP wrapper validation')):first=r.run(data,out,wp)
   self.assertEqual(first['status'],'repair_stopped_reconciliation_required');self.assertEqual(len(mutations),1)
   final=r.reconcile(data,out,wp);self.assertEqual(final['status'],'public_presentation_verified');self.assertEqual([i for i,p in mutations],[524196,524200]);self.assertFalse(final['results']['fa-IR']['new_write_during_reconciliation']);self.assertTrue(final['results']['en-US']['new_write_during_reconciliation']);self.assertIn('failure',final)
 def test_reconciliation_blocks_newer_live_content_before_any_additional_write(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r,'get_topic',return_value={'crop':'چغندر لبویی'}),patch.object(r,'verify_target'),patch.object(r,'validate_targets'):
   data,out,wp,posts,mutations=self.setup(Path(td))
   with patch.object(r,'verify_sources',side_effect=ValueError('Old wrapper')):r.run(data,out,wp)
   posts[524196]['content']['raw']+='<p>Human update</p>'
   with self.assertRaises(r.WPError):r.reconcile(data,out,wp)
   self.assertEqual(len(mutations),1)
 def test_reconciliation_never_replays_successful_but_unconfirmed_write(self):
  with tempfile.TemporaryDirectory() as td,patch.object(r,'get_topic',return_value={'crop':'چغندر لبویی'}),patch.object(r,'verify_target'),patch.object(r,'validate_targets'):
   data,out,wp,posts,mutations=self.setup(Path(td));original=wp.call
   def unknown(path,method='GET',data=None):
    value=original(path,method,data)
    if path=='posts/524200' and method=='POST':raise RuntimeError('Response lost after committed update')
    return value
   wp.call=unknown;self.assertEqual(r.run(data,out,wp)['status'],'repair_stopped_reconciliation_required');self.assertEqual(len(mutations),2)
   final=r.reconcile(data,out,wp);self.assertEqual(final['status'],'public_presentation_verified');self.assertFalse(final['results']['en-US']['new_write_during_reconciliation']);self.assertEqual(len(mutations),2)
