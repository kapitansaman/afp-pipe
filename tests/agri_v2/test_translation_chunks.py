import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import translation_chunks as t,multilingual as m
from test_multilingual import article,response
class TranslationChunkTests(unittest.TestCase):
 def responder(self,lang='en-US'):
  token={'en-US':'Faithful agricultural translation with preserved meaning. ','ru-RU':'Точный перевод сельскохозяйственного текста без новых фактов. ','tg-TJ':'Тарҷумаи дақиқи кишоварзӣ бо ҳифзи маъно ва маҳдудиятҳо. ','ar-IQ':'ترجمة زراعية دقيقة تحفظ المعنى والقيود دون معلومات جديدة. '}[lang]
  def call(prompt,**kwargs):return {'translations':[{'id':r['id'],'text':token*3} for r in json.loads(prompt)['segments']]}
  return call
 def test_chunked_and_cached_for_all_four_languages(self):
  for lang in m.LANGUAGES:
   with self.subTest(lang=lang),tempfile.TemporaryDirectory() as td:
    a=article();c=Mock();c.text.side_effect=self.responder(lang);folder=Path(td);raw=t.translate_segments(c,a,lang,folder,max_segments=3);calls=c.text.call_count;self.assertGreater(calls,1);self.assertEqual(raw,t.translate_segments(c,a,lang,folder,max_segments=3));self.assertEqual(c.text.call_count,calls);translated=m.render_translation(a,raw,lang);self.assertIn('<table>',translated['content_html']);self.assertIn('https://extension.msu.edu/source',translated['content_html'])
 def test_wrapped_rows_and_inert_numeric_ids_normalized_but_duplicates_rejected(self):
  batch=[{'id':3,'text':'متن 40'}];raw={'result':{'translations':[{'id':'3','text':'Text 40'}]}};self.assertEqual(t.normalize_batch(raw,batch),[{'id':3,'text':'Text 40'}]);raw['result']['translations']*=2
  with self.assertRaises(ValueError):t.normalize_batch(raw,batch)
 def test_uncertain_paid_chunk_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   c=Mock();c.text.side_effect=RuntimeError('provider');folder=Path(td)
   for _ in range(2):
    with self.assertRaises(Exception):t.translate_segments(c,article(),'en-US',folder)
   self.assertEqual(c.text.call_count,1)
 def test_changed_source_cannot_reuse_or_overwrite_prior_translation(self):
  with tempfile.TemporaryDirectory() as td:
   a=article();c=Mock();c.text.side_effect=self.responder();folder=Path(td);t.translate_segments(c,a,'en-US',folder);paid=c.text.call_count;a['title']+=' تغییر'
   with self.assertRaisesRegex(ValueError,'source changed'):t.translate_segments(c,a,'en-US',folder)
   self.assertEqual(c.text.call_count,paid)
 def test_changed_number_is_never_repaired_to_approval(self):
  with self.assertRaisesRegex(ValueError,'numbers'):t.normalize_batch({'translations':[{'id':0,'text':'Changed 41'}]},[{'id':0,'text':'متن 40'}])
 def test_source_present_citation_markup_is_plain_format_repair_not_new_link(self):
  source='متن 40 <a href="https://extension.example.edu/source">منبع</a>.';target='Text 40 <a href="https://extension.example.edu/source">Source</a>.';raw={'translations':[{'id':0,'text':target}]};rows=t.normalize_batch(raw,[{'id':0,'text':source}],{'https://extension.example.edu/source'});self.assertEqual(rows,[{'id':0,'text':'Text 40 Source.'}])
  raw['translations'][0]['text']='Text 40 <a href="https://evil.example/">Source</a>.'
  with self.assertRaises(ValueError):t.normalize_batch(raw,[{'id':0,'text':source}],{'https://extension.example.edu/source'})
 def test_injected_markup_still_rejected_when_absent_from_source(self):
  for text in ['<script>bad</script>','Text <a href="https://evil.example/">bad</a>','<b>Text</b>']:
   with self.assertRaises(ValueError):t.normalize_batch({'translations':[{'id':0,'text':text}]},[{'id':0,'text':'متن'}])
 def test_one_source_bound_language_repair_is_cached(self):
  from test_multilingual import response
  from automation.agri_v2.multilingual import source_segments
  with tempfile.TemporaryDirectory() as td:
   a=article();_,values=source_segments(a);c=Mock();c.text.return_value=response(a,'tg-TJ');folder=Path(td);prior={'translations':[]};row=t.repair_language(c,a,'tg-TJ',folder,values,prior,{'https://extension.msu.edu/source'});again=t.repair_language(c,a,'tg-TJ',folder,values,prior,{'https://extension.msu.edu/source'});self.assertEqual(row,again);self.assertEqual(c.text.call_count,1)
 def test_provider_failure_during_language_repair_is_not_replayed(self):
  from automation.agri_v2.multilingual import source_segments
  with tempfile.TemporaryDirectory() as td:
   a=article();_,values=source_segments(a);c=Mock();c.text.side_effect=RuntimeError('provider');folder=Path(td)
   for _ in range(2):
    with self.assertRaises(Exception):t.repair_language(c,a,'tg-TJ',folder,values,{'translations':[]},{'https://extension.msu.edu/source'})
   self.assertEqual(c.text.call_count,1)
