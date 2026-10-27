import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import translation_review_repair as r,multilingual as m
from automation.agri_v2.queue import atomic_json,load_json
from test_multilingual import article,response

class ReviewRepairTests(unittest.TestCase):
 def setup(self,d):
  a=article();f=Path(d);raws={lang:response(a,lang) for lang in m.LANGUAGES};rows={lang:m.render_translation(a,raws[lang],lang) for lang in m.LANGUAGES}
  for lang in m.LANGUAGES:atomic_json(f/'translations'/(lang+'.raw.json'),raws[lang]);atomic_json(f/'translations'/(lang+'.json'),rows[lang])
  return a,f,raws,rows
 def verdict(self,a,raws,failed=()):
  _,source=m.source_segments(a)
  return {'faithful':not failed,'languages':{lang:lang not in failed for lang in m.LANGUAGES},'reason':'Compared actual source meaning, crop, units and limitations, not stylistic preferences.','issues':[{'language':lang,'id':0,'source_text':source[0],'target_text':raws[lang]['translations'][0]['text'],'category':'meaning','detail':'This segment changes the source meaning.'} for lang in failed]}
 def client(self,values,limit=5):
  client=Mock();client._max_translation_review_repair_calls=limit;client.text.side_effect=values;return client
 def test_pass_once_no_repair_and_zero_call_resume(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);c=self.client([self.verdict(a,raws)])
   self.assertTrue(r.run(c,a,rows,f)['four_languages_semantically_reviewed']);self.assertEqual(c.text.call_count,1)
   c=self.client([]);r.run(c,a,rows,f);c.text.assert_not_called()
 def test_selective_two_language_fix_keeps_approved_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);before={lang:(f/'translations'/(lang+'.json')).read_bytes() for lang in ('ru-RU','en-US')}
   failed=('ar-IQ','tg-TJ');changed=copy.deepcopy(raws);patches=[]
   for lang in failed:
    text=raws[lang]['translations'][0]['text']+' '+('تصحيح' if lang=='ar-IQ' else 'Ислоҳ');patches.append({'language':lang,'id':0,'text':text});changed[lang]['translations'][0]['text']=text
   c=self.client([self.verdict(a,raws,failed),{'patches':patches},self.verdict(a,changed)])
   result=r.run(c,a,rows,f);self.assertEqual(result['repair_rounds'],1);self.assertEqual(c.text.call_count,3)
   for lang in before:self.assertEqual(before[lang],(f/'translations'/(lang+'.json')).read_bytes())
   for lang in failed:self.assertEqual(load_json(f/'translations'/(lang+'.raw.json')),changed[lang])
   self.assertTrue((f/'translation-review-repair-v1/original-translations.json').exists())
   r.validate(load_json(f/'translation-fidelity-review.json')['review'])
 def test_two_round_cap_retains_originals_and_holds_only_family(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);v=self.verdict(a,raws,('ar-IQ',));p={'patches':[{'language':'ar-IQ','id':0,'text':raws['ar-IQ']['translations'][0]['text']}]}
   c=self.client([v,p,v,p,v]);result=r.run(c,a,rows,f)
   self.assertFalse(result['four_languages_semantically_reviewed']);self.assertEqual(c.text.call_count,5);self.assertEqual(result['pending_languages'],['ar-IQ']);self.assertTrue(r.hold_matches(f,a,rows));self.assertFalse((f/'translation-fidelity-review.json').exists())
   for lang in m.LANGUAGES:self.assertEqual(load_json(f/'translations'/(lang+'.json')),rows[lang])
   c=self.client([]);r.run(c,a,rows,f);c.text.assert_not_called()
 def test_one_call_outer_cap_does_not_implicitly_buy_repairs(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);c=self.client([self.verdict(a,raws,('ar-IQ',))],1);result=r.run(c,a,rows,f)
   self.assertEqual(c.text.call_count,1);self.assertFalse(result['four_languages_semantically_reviewed'])
 def test_invented_quotation_and_style_are_not_repair_authority(self):
  for mode in ('quote','style','contradiction'):
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
    a,f,raws,rows=self.setup(d);v=self.verdict(a,raws,('ar-IQ',))
    if mode=='quote':v['issues'][0]['target_text']='Text never present'
    if mode=='style':v['issues'][0]['category']='style'
    if mode=='contradiction':v['issues']=[]
    c=self.client([v]);self.assertFalse(r.run(c,a,rows,f)['four_languages_semantically_reviewed']);self.assertEqual(c.text.call_count,1)
 def test_numbers_html_and_unrequested_ids_never_promoted(self):
  for kind in ('number','html','id'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
    a,f,raws,rows=self.setup(d);v=self.verdict(a,raws,('ar-IQ',));p={'language':'ar-IQ','id':1 if kind=='id' else 0,'text':raws['ar-IQ']['translations'][0]['text']+(' 99' if kind=='number' else '<script>x</script>' if kind=='html' else '')}
    c=self.client([v,{'patches':[p]}]);self.assertFalse(r.run(c,a,rows,f)['four_languages_semantically_reviewed']);self.assertEqual(load_json(f/'translations/ar-IQ.json'),rows['ar-IQ'])
 def test_provider_failure_is_not_retried_or_relabelled_content(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);c=self.client([RuntimeError('provider unavailable')])
   with self.assertRaises(RuntimeError):r.run(c,a,rows,f)
   self.assertFalse((f/'translation-repair-hold.json').exists());c=self.client([]);result=r.run(c,a,rows,f);c.text.assert_not_called();self.assertFalse(result['four_languages_semantically_reviewed'])
 def test_cached_response_tampering_is_detected(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);r.run(self.client([self.verdict(a,raws)]),a,rows,f)
   atomic_json(f/'translation-review-repair-v1/review-0.raw.json',{'changed':True});c=self.client([]);self.assertFalse(r.run(c,a,rows,f)['four_languages_semantically_reviewed']);c.text.assert_not_called()
 def test_interrupted_promotion_recovers_without_model_calls(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);changed=copy.deepcopy(raws);patches=[]
   for lang in ('ar-IQ','tg-TJ'):
    text=raws[lang]['translations'][0]['text']+' '+('تصحيح' if lang=='ar-IQ' else 'Ислоҳ');changed[lang]['translations'][0]['text']=text;patches.append({'language':lang,'id':0,'text':text})
   c=self.client([self.verdict(a,raws,('ar-IQ','tg-TJ')),{'patches':patches},self.verdict(a,changed)])
   real=r.atomic_json
   def interrupted(path,value):
    if path==f/'translations/tg-TJ.json':raise RuntimeError('interrupted promotion')
    return real(path,value)
   with patch.object(r,'atomic_json',side_effect=interrupted):
    with self.assertRaises(RuntimeError):r.run(c,a,rows,f)
   r.recover_if_approved(f,a)
   for lang in m.LANGUAGES:self.assertEqual(load_json(f/'translations'/(lang+'.json')),m.render_translation(a,changed[lang],lang))
   self.assertEqual(c.text.call_count,3)
 def test_source_change_is_not_silently_rebound(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);r.run(self.client([self.verdict(a,raws)]),a,rows,f);a['title']='منبع عوض شد';c=self.client([])
   with self.assertRaises(ValueError):r.run(c,a,rows,f)
   c.text.assert_not_called()
 def test_second_round_edits_only_language_still_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);one=copy.deepcopy(raws);two=copy.deepcopy(raws);patches=[]
   for lang in ('ar-IQ','tg-TJ'):
    text=raws[lang]['translations'][0]['text']+' '+('تصحيح' if lang=='ar-IQ' else 'Ислоҳ');one[lang]['translations'][0]['text']=text;patches.append({'language':lang,'id':0,'text':text})
   two=copy.deepcopy(one);two['tg-TJ']['translations'][0]['text']+=' Дақиқ'
   c=self.client([self.verdict(a,raws,('ar-IQ','tg-TJ')),{'patches':patches},self.verdict(a,one,('tg-TJ',)),{'patches':[{'language':'tg-TJ','id':0,'text':two['tg-TJ']['translations'][0]['text']}]},self.verdict(a,two)])
   self.assertEqual(r.run(c,a,rows,f)['repair_rounds'],2);self.assertEqual(c.text.call_count,5)
   last_repair=json.loads(c.text.call_args_list[3].args[0]);self.assertEqual({i['language'] for i in last_repair['issues']},{'tg-TJ'})
   final={lang:load_json(f/'translations'/(lang+'.json')) for lang in m.LANGUAGES};cached=self.client([]);self.assertTrue(r.run(cached,a,final,f)['four_languages_semantically_reviewed']);cached.text.assert_not_called()
 def test_family_worker_returns_local_hold_not_batch_abort(self):
  from automation.agri_v2 import family_lifecycle as lifecycle
  from test_family_lifecycle import FamilyLifecycleTests
  with tempfile.TemporaryDirectory() as d:
   data,out,topic,env,health=FamilyLifecycleTests().setup(d);client=Mock()
   with patch.object(lifecycle,'next_stage',side_effect=[('translation_fidelity_review',None),('blocked','translation_editorial_review_required')]),patch.object(lifecycle,'run_stage',return_value={'four_languages_semantically_reviewed':False,'other_families_continue':True}):
    result=lifecycle.worker(topic,health,data,out,env,lambda *a,**kw:client)
   self.assertEqual(result['status'],'blocked');self.assertEqual(result['reason'],'translation_editorial_review_required');self.assertEqual(result['published_posts'],0)
 def test_lifecycle_review_stage_routes_to_repair_engine(self):
  from automation.agri_v2 import family_lifecycle as lifecycle
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);topic={'id':'topic'};data=f/'data';out=f/'out';atomic_json(data/'briefs/topic.json',{})
   for lang in m.LANGUAGES:atomic_json(out/'new/topic/translations'/(lang+'.json'),rows[lang])
   client=Mock()
   with patch.object(lifecycle,'check_brief'),patch.object(lifecycle,'article_checked',return_value=a),patch.object(r,'run',return_value={'repaired':True}) as repair:
    result=lifecycle.run_stage(topic,'translation_fidelity_review',client,data,out)
   self.assertEqual(result,{'repaired':True});self.assertEqual(repair.call_args.args[0],client)
 def test_protected_language_is_never_edited(self):
  with tempfile.TemporaryDirectory() as d:
   a,f,raws,rows=self.setup(d);c=self.client([self.verdict(a,raws,('en-US',))]);c._translation_repair_languages=['ar-IQ','tg-TJ']
   result=r.run(c,a,rows,f);self.assertFalse(result['four_languages_semantically_reviewed']);self.assertEqual(c.text.call_count,1);self.assertEqual(load_json(f/'translations/en-US.json'),rows['en-US'])
