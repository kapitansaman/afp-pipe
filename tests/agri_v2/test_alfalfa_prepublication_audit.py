import copy,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import alfalfa_prepublication_audit as a
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.pipeline import digest
from automation.agri_v2.parallel_control import BRANCH
class AuditTests(unittest.TestCase):
 def fixture(self,t):
  data=Path(t)/'data';out=Path(t)/'out';folder=out/'new'/a.TOPIC
  raw='<!-- afp-agri-v2:'+a.TOPIC+' -->content'
  receipt={'post_id':524204,'topic_id':a.TOPIC,'url':a.SITE+'/preharvest-alfalfa-irrigation-criteria/','featured_media':524205,'publication_content_sha256':hashlib.sha256(raw.encode()).hexdigest(),'media':[{'index':i,'id':524204+i,'url':a.SITE+'/wp-content/uploads/'+a.TOPIC+'-image-'+str(i)+'.webp'} for i in (1,2)]}
  atomic_json(folder/'wordpress-receipt.json',receipt)
  post={'id':524204,'author':1,'status':'publish','slug':'preharvest-alfalfa-irrigation-criteria','link':receipt['url'],'featured_media':524205,'afp_language':'fa-IR','content':{'raw':raw},'modified_gmt':'2026-10-29T00:00:00'}
  atomic_json(folder/'lifecycle-evidence/existing-content.json',{'related_ids':[],'documents':[]})
  article={'content_html':'new source'};brief={'publish_authorized':False}
  root=out/'claim-policy-rechecks'/a.APPROVED
  atomic_json(root/'article.json',article);atomic_json(root/'brief.json',brief);atomic_json(root/'report.json',{'status':'claim_recheck_ready_for_publication_review','publication_authorized':False,'article_sha256':digest(article),'brief_sha256':digest(brief)})
  for i in (1,2):
   (folder/('image-'+str(i)+'.webp')).write_bytes(b'webp');atomic_json(folder/('image-'+str(i)+'.quality.json'),{'image_sha256':hashlib.sha256(b'webp').hexdigest()})
  atomic_json(folder/'translations/en-US.json',{'source_article_sha256':'OLD'})
  env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_REF_NAME':BRANCH,'GITHUB_RUN_ID':'123'}
  site=Mock();site.count=0;site.asset.return_value=b'webp'
  def get(path):
   if path.startswith('users/me?'):return {'id':1},{}
   if path.startswith('posts/524204?'):return post,{}
   if path.startswith('posts?'):return [],{'x-wp-totalpages':'1'}
   if path.startswith('media/'):
    ident=int(path.split('/')[1].split('?')[0]);m=next(m for m in receipt['media'] if m['id']==ident)
    return {'id':ident,'source_url':m['url'],'mime_type':'image/webp'},{}
   raise AssertionError('Unexpected route')
  site.get.side_effect=get
  return data,out,folder,env,site,post,receipt
 def test_exact_identity_and_raw_bytes_required(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,folder,env,site,post,receipt=self.fixture(t);self.assertTrue(a.owned(post,1,receipt)['identity_matches'])
   for key,value in [('id',1),('author',2),('status','draft'),('featured_media',9),('slug','other'),('afp_language','en-US')]:
    with self.subTest(key=key),self.assertRaises(a.ReadBlocked):a.owned(dict(post,**{key:value}),1,receipt)
   with self.assertRaises(a.ReadBlocked):a.owned(dict(post,content={'raw':post['content']['raw']+'edit'}),1,receipt)
 def test_only_get_and_fixed_origin_routes(self):
  site=a.ReadOnlySite({'AFP_WP_BASE_URL':a.SITE,'AFP_WP_USERNAME':'test','AFP_WP_APP_PASSWORD':'not-real'})
  for path in ('https://example.com','posts/1','posts/1?context=edit#fragment','settings?x=1','../posts?x=1'):
   with self.subTest(path=path),self.assertRaises(a.ReadBlocked):site.get(path)
  with self.assertRaises(TypeError):site.get('posts?x=1',method='POST')
  with self.assertRaises(a.ReadBlocked):site.asset('https://example.com/img.webp')
 def test_no_secret_or_provider_requests_and_no_old_approval_transfer(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,folder,env,site,post,receipt=self.fixture(t);before=a.protected(data,out)
   result=a.run(env,data,out,site_factory=lambda e:site)
   self.assertEqual(result['status'],'readonly_prepublication_blocked');self.assertFalse(result['safe_to_publish']);self.assertEqual(result['site_mutations'],0);self.assertEqual(result['model_calls'],0);self.assertEqual(result['translation_generation_calls'],0)
   self.assertEqual(before,a.protected(data,out));self.assertTrue(result['originals_unchanged']);self.assertEqual(result['translations']['en-US']['status'],'stale_translation_for_old_source');self.assertFalse(result['translations']['en-US']['old_review_reused']);self.assertTrue(all(not m['revised_article_visual_approval'] for m in result['images']))
 def test_identity_drift_stops_before_inventory_and_images(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,folder,env,site,post,receipt=self.fixture(t);post['content']['raw']+='changed'
   result=a.run(env,data,out,site_factory=lambda e:site)
   self.assertEqual(result['failure'],'readonly_post_bytes_changed');self.assertEqual(site.get.call_count,2);site.asset.assert_not_called()
 def test_old_report_is_not_replayed_and_no_secret_error_text_saved(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,folder,env,site,post,receipt=self.fixture(t);site.get.side_effect=RuntimeError('SECRET TOKEN')
   result=a.run(env,data,out,site_factory=lambda e:site);again=a.run(env,data,out,site_factory=Mock(side_effect=AssertionError()))
   self.assertNotIn('SECRET',str(result));self.assertEqual(again['status'],'readonly_audit_already_recorded')
 def test_wrong_run_context_never_opens_site(self):
  factory=Mock()
  with self.assertRaises(a.ReadBlocked):a.run({},site_factory=factory)
  factory.assert_not_called()
 def test_source_approval_hash_drift_blocks_site_access(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,folder,env,site,post,receipt=self.fixture(t);atomic_json(out/'claim-policy-rechecks'/a.APPROVED/'article.json',{'changed':True});factory=Mock()
   with self.assertRaises(a.ReadBlocked):a.run(env,data,out,site_factory=factory)
   factory.assert_not_called()
