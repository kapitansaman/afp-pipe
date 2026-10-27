import copy,tempfile,unittest
from pathlib import Path
from automation.agri_v2 import editorial_translation_patch as p
from automation.agri_v2.pipeline import digest
from automation.agri_v2.queue import atomic_json,load_json
class EditorialPatchTests(unittest.TestCase):
 def setup(self,td):
  data=Path(td)/'data';folder=Path(td)/'out';article={'title':'source'};raw={'translations':[{'id':57,'text':'14 то 21 рӯз тӯл мекаشد'}]};patch={'language':'tg-TJ','source_article_sha256':digest(article),'raw_translation_sha256':digest(raw),'updates':[{'id':57,'old_text':raw['translations'][0]['text'],'new_text':'14 то 21 рӯз тӯл мекашад'}],'reason':'One mixed-script verb corrected; numeric range and source meaning unchanged.'};path=data/'editorial-corrections/tajik-mixed-script-v1.json';atomic_json(path,{'version':1,'patches':[patch]});return data,folder,article,raw,patch,path
 def test_exact_patch_retains_original_raw_and_requires_independent_review(self):
  with tempfile.TemporaryDirectory() as td:
   data,folder,article,raw,patch,path=self.setup(td);before=copy.deepcopy(raw);edited=p.apply(raw,article,'tg-TJ',folder,data);self.assertEqual(raw,before);self.assertIn('мекашад',edited['translations'][0]['text']);receipt=load_json(folder/'translations/tg-TJ.editorial-correction.json');self.assertTrue(receipt['independent_fidelity_review_required']);self.assertEqual(receipt['new_model_calls'],0);self.assertFalse(receipt['human_review_claimed'])
 def test_other_source_or_other_raw_cannot_acquire_the_patch(self):
  with tempfile.TemporaryDirectory() as td:
   data,folder,article,raw,patch,path=self.setup(td);self.assertEqual(p.apply(raw,{'title':'changed'},'tg-TJ',folder,data),raw);changed=copy.deepcopy(raw);changed['translations'][0]['text']+=' other';self.assertEqual(p.apply(changed,article,'tg-TJ',folder,data),changed)
 def test_editorial_patch_cannot_change_numbers(self):
  with tempfile.TemporaryDirectory() as td:
   data,folder,article,raw,patch,path=self.setup(td);patch['updates'][0]['new_text']='14 то 22 рӯз тӯл мекашад';atomic_json(path,{'version':1,'patches':[patch]})
   with self.assertRaisesRegex(ValueError,'numbers'):p.apply(raw,article,'tg-TJ',folder,data)
