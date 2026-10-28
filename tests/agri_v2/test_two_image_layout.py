import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import image_quality as q,image_key_routing as routing,curated_continuation as c
from automation.agri_v2 import recovery,image_transport
from automation.agri_v2.image_layout import PRODUCTION_IMAGE_ROLES
from automation.agri_v2.wordpress import WordPress,WPError,illustrated_content
from automation.agri_v2.queue import atomic_json,load_json,DATA
class TwoImageLayoutTests(unittest.TestCase):
 def test_only_two_production_reviews_required(self):
  with patch.object(q,'valid_record') as review:
   q.require_all('/unused',{'id':'fixture'})
   self.assertEqual([call.args[2] for call in review.call_args_list],[1,2])
 def test_exactly_one_inline_image_not_featured_or_legacy_third(self):
  media=[{'url':'https://example.org/'+str(i)} for i in (1,2,3)]
  body=illustrated_content('<p>Intro</p><h2>One</h2><p>A</p><h2>Two</h2><p>B</p>',media,'fixture')
  self.assertEqual(body.count('<figure '),1);self.assertIn(media[1]['url'],body)
  self.assertNotIn(media[0]['url'],body);self.assertNotIn(media[2]['url'],body)
 def test_current_request_needs_only_missing_inline_role(self):
  req=load_json(DATA/'curated-continuation-request.json');c.validate(req)
  self.assertEqual(req['max_new_image_outputs'],1);self.assertEqual(req['max_visual_reviews'],1)
  self.assertEqual(req['key_distribution'],'verified_round_robin');self.assertEqual(PRODUCTION_IMAGE_ROLES,(1,2))
 def test_fresh_process_requests_rotate_without_pinning(self):
  pool=[('AGNES_API_KEY','fixture-a'),('AGNES_API_KEY2','fixture-b'),('AGNES_API_KEY3','fixture-c')]
  with tempfile.TemporaryDirectory() as tmp,patch.object(routing,'OUT',Path(tmp)),patch.object(recovery,'circuit_open',return_value=False),patch.object(image_transport,'shared_evidence',return_value=[]):
   chosen=[routing.route(pool,0,{'GITHUB_ACTIONS':'true'})[0] for _ in range(6)]
   self.assertEqual(chosen,[p[0] for p in pool]*2)
 def test_rotation_never_bypasses_shared_cooldown(self):
  with patch.object(recovery,'circuit_open',return_value=True),patch.object(image_transport,'shared_evidence') as evidence:
   with self.assertRaises(routing.AdmissionBlocked):routing.route([('AGNES_API_KEY2','fixture')],0,{'GITHUB_ACTIONS':'true'})
   evidence.assert_not_called()
 def test_wordpress_uploads_only_two_and_sets_featured(self):
  with tempfile.TemporaryDirectory() as tmp,patch('automation.agri_v2.wordpress.require_all'),patch('automation.agri_v2.wordpress.validate_targets'):
   folder=Path(tmp);topic={'id':'fixture','title':'عنوان آزمایشی','crop':'لوبیا'}
   atomic_json(folder/'wordpress-draft-payload.json',{'slug':'fixture','content':'<p>Intro <a href="https://example.edu/source">منبع</a></p><h2>A</h2><p>B</p>'})
   atomic_json(folder/'article.json',{'faq':[{'question':'این یک پرسش آزمایشی است؟','answer':'این پاسخ صرفاً برای آزمون قالب نوشته شده و توصیه علمی نیست.'}]*3})
   for i in (1,2):(folder/f'image-{i}.webp').write_bytes(b'fixture')
   wp=WordPress({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'},data=folder/'test-data')
   wp.user_id=7;wp.preflight=Mock();wp.verify=Mock(return_value={'public_verified':True});wp.publish_family=lambda folder,topic,result:result;requests=[];uploads=[]
   def call(path,method='GET',data=None,blob=None,headers=None):
    requests.append((path,method,data))
    if path.startswith('posts?') or path.startswith('media?'):return [],{}
    if path=='posts' and method=='POST':return {'id':50},{}
    if path=='media' and method=='POST':
     uploads.append(headers['Content-Disposition']);return {'id':100+len(uploads)},{}
    if path.startswith('media/'):
     ident=int(path.split('/')[1]);return {'id':ident,'source_url':'https://navar-abyari.ir/media/'+str(ident)},{}
    if path.endswith('?context=edit'):return {'author':7,'status':'draft','content':{'raw':'<!-- afp-agri-v2:fixture -->'}},{}
    return {'id':50,'link':'https://navar-abyari.ir/fixture/'},{}
   wp.call=call;wp.inventory=lambda:{'records':[]};wp.publish(folder,topic,{'publish_authorized':True,'sources':[{'url':'https://example.edu/source'}]},True)
   self.assertEqual(len(uploads),2);self.assertFalse(any('image-3' in n for n in uploads))
   updates=[d for p,m,d in requests if p=='posts/50' and d and 'featured_media' in d]
   self.assertEqual(updates[0]['featured_media'],101);self.assertEqual(updates[0]['content'].count('<figure '),1)
 def test_public_verification_accepts_two_and_rejects_wrong_featured(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);rp=folder/'receipt.json';topic={'title':'عنوان آزمایشی'};media=[{'index':i,'id':100+i,'url':'https://navar-abyari.ir/media/'+str(i)} for i in (1,2)]
   atomic_json(rp,{'media':media,'post_id':50,'status':'published','url':'https://navar-abyari.ir/fixture/'})
   wp=WordPress({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'},data=folder/'test-data')
   post={'status':'publish','title':{'rendered':topic['title']},'featured_media':101,'content':{'rendered':media[1]['url']},'link':'https://navar-abyari.ir/fixture/'};wp.call=Mock(return_value=(post,{}))
   response=Mock();response.status=200;response.read.return_value=topic['title'].encode();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
   with patch('automation.agri_v2.wordpress.urllib.request.urlopen',return_value=response):self.assertTrue(wp.verify(50,topic,rp)['public_verified'])
   post['featured_media']=999
   with self.assertRaisesRegex(WPError,'Featured'):wp.verify(50,topic,rp)
