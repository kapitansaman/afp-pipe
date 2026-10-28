import unittest
from automation.agri_v2 import editorial_presentation as e,internal_links as links,multilingual as m
class EditorialPresentationTests(unittest.TestCase):
 def sources(self):return [{'url':'https://extension.usu.edu/beets','title':'Beets in the garden'},{'url':'https://example.edu/unused'}]
 def test_one_end_source_not_repeated_inline_and_faq_stays_before_it(self):
  body='<p>متن <a href="https://extension.usu.edu/beets">منبع</a>.</p><table><tr><td>داده <a href="https://extension.usu.edu/beets">منبع</a></td></tr></table><h2>سؤالات متداول</h2><p>پاسخ</p>'
  r=e.end_sources(body,self.sources());self.assertEqual(links.external_links(r),['https://extension.usu.edu/beets']);self.assertNotIn('>منبع</a>',r);self.assertTrue(r.endswith(e.END));self.assertLess(r.index('سؤالات متداول'),r.index(e.START));self.assertEqual(e.end_sources(r,self.sources()),r);self.assertNotIn('unused',r)
 def test_semantic_anchor_text_and_other_content_are_preserved(self):
  body='<!-- owned --><p>برای <a href="https://extension.usu.edu/beets"><strong>مشاهده دانشگاهی عملکرد</strong></a> این متن.</p><img src="https://navar-abyari.ir/a.webp"/><a href="https://navar-abyari.ir/related/">مطلب مرتبط</a>'
  r=e.end_sources(body,self.sources());self.assertIn('<strong>مشاهده دانشگاهی عملکرد</strong>',r);self.assertIn('<!-- owned -->',r);self.assertIn('<img src="https://navar-abyari.ir/a.webp"/>',r);self.assertIn('href="https://navar-abyari.ir/related/"',r)
 def test_unknown_source_missing_citation_or_moved_footer_is_blocked(self):
  for body in ('<p>No citation</p>','<p><a href="https://evil.invalid/">Source</a></p>'):
   with self.assertRaises(ValueError):e.end_sources(body,self.sources())
  r=e.end_sources('<p><a href="https://extension.usu.edu/beets">منبع</a></p>',self.sources())
  with self.assertRaises(ValueError):e.verify_sources(r+'<p>After sources</p>',self.sources())
 def topic(self):return {'crop':'چغندر لبویی','title':'میزان برداشت چغندر لبویی در هکتار'}
 def row(self,i,title,language='fa-IR',status='publish'):return {'id':i,'title':title,'language':language,'status':status,'url':'https://navar-abyari.ir/article-'+str(i)+'/'}
 def test_related_is_exact_crop_language_and_published_never_random_or_self(self):
  rows=[self.row(1,'کاشت چغندر لبویی'),self.row(2,'برداشت چغندر قند'),self.row(3,'کاشت لوبیا چیتی'),self.row(4,'کاشت چغندر لبویی','en-US'),self.row(5,'کاشت چغندر لبویی',status='draft'),self.row(6,'کاشت چغندر لبویی'),self.row(7,'دستور پخت چغندر لبویی')]
  result=e.related_articles(self.topic(),rows[5]['url'],rows);self.assertEqual([x['post_id'] for x in result],[1]);self.assertEqual(e.related_articles(self.topic(),'https://navar-abyari.ir/current/',[]),[])
 def test_related_still_selected_when_commercial_cta_is_none(self):
  from automation.agri_v2.content_matrix import VERSION
  t=dict(self.topic(),commercial_matrix={'version':VERSION,'cta_mode':'none'});t['editorial_related']=e.related_articles(t,'https://navar-abyari.ir/current/',[self.row(1,'کاشت چغندر لبویی')]);rows=links.selected_links(t,'https://navar-abyari.ir/current/');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['kind'],'related');self.assertIn('کاشت چغندر لبویی',links.augment('<p>متن</p>',t,'https://navar-abyari.ir/current/'))
 def test_translated_counterpart_requires_exact_language_and_actual_published_post(self):
  class WP:
   def __init__(self,lang):self.lang=lang
   def call(self,path):
    if 'afp_translation_links' in path:return {'afp_translation_links':{'en-US':'https://navar-abyari.ir/beets-en/'}},{}
    return [{'id':2,'status':'publish','afp_language':self.lang,'afp_source_post_id':1,'link':'https://navar-abyari.ir/beets-en/','title':{'rendered':'Growing table beets'}}],{}
  self.assertEqual(e.translated_related(WP('fa-IR'),[{'post_id':1}],'en-US','https://navar-abyari.ir/current-en/'),[])
  self.assertEqual(e.translated_related(WP('en-US'),[{'post_id':1}],'ru-RU','https://navar-abyari.ir/current-ru/'),[])
  r=e.translated_related(WP('en-US'),[{'post_id':1}],'en-US','https://navar-abyari.ir/current-en/');self.assertEqual(r[0]['anchor'],'Growing table beets')
 def test_each_language_has_final_sources_after_faq(self):
  for lang,label in e.LABELS.items():
   if lang=='fa-IR':continue
   row={'language':lang,'title':'Title','content_html':'<p>Fact <a href="https://extension.usu.edu/beets">Source</a></p>','faq':[{'question':'Q','answer':'A'}]}
   body=m.localized_body(row,[{'url':'https://navar-abyari.ir/image.webp'}],{lang:[]});self.assertEqual(e.verify_sources(body,self.sources(),lang),['https://extension.usu.edu/beets']);self.assertIn('<h2>'+label+'</h2>',body);self.assertLess(body.index(m.FAQ_LABEL[lang]),body.index(e.START))
