import copy,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2.translation_numeric_locale import tokens,same,VERSION
from automation.agri_v2 import family07_decimal_continuation as r,retained_russian_fidelity as ru
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json
from automation.agri_v2.pipeline import digest
from automation.agri_v2.translation_chunks import normalize_batch
from automation.agri_v2.multilingual import source_segments,render_translation
from automation.agri_v2.parallel_control import reserve

class NumericLocaleTests(unittest.TestCase):
 def test_decimal_comma_ru_tg_exact_value_and_precision(self):
  for lang in ('ru-RU','tg-TJ'):
   self.assertTrue(same('۰٫۳۰ and 0.10','0,30 и 0,10',lang));self.assertTrue(same('2 and 0.30','2 и 0.30',lang))
   for target in ('0,31','0,3','30','0,300'):self.assertFalse(same('0.30',target,lang))
 def test_english_arabic_unspecified_keep_strict_legacy(self):
  for lang in ('en-US','ar-IQ',None):self.assertFalse(same('0.30','0,30',lang))
 def test_no_thousands_or_mixed_punctuation_guess(self):
  for source,target in [('1000','1,000'),('1234.50','1.234,50'),('1234.50','1,234.50'),('0.30','0,30,50')]:self.assertFalse(same(source,target,'ru-RU'))
 def test_compare_does_not_mutate_text_or_source_pipeline_numbers(self):
  from automation.agri_v2.pipeline import numbers
  source='0.30';target='0,30';self.assertTrue(same(source,target,'ru-RU'));self.assertEqual(target,'0,30');self.assertEqual(numbers(target),{'0','30'})
 def test_normalize_batch_explicit_language_preserves_original_comma_bytes(self):
  raw={'translations':[{'id':0,'text':'0,30'}]};batch=[{'id':0,'text':'0.30'}];self.assertEqual(normalize_batch(raw,batch,target_language='ru-RU'),raw['translations'])
  with self.assertRaisesRegex(ValueError,'changed numbers'):normalize_batch(raw,batch)
 def test_wrong_value_and_operators_still_rejected(self):
  for source,target in [('0.30','0,31'),('< 0.30','> 0,30')]:
   with self.assertRaises(ValueError):normalize_batch({'translations':[{'id':0,'text':target}]},[{'id':0,'text':source}],target_language='ru-RU')
 def setup(self,root):
  d=root/'data';o=root/'out';shutil.copytree(DATA,d);shutil.copytree(OUT/'new'/r.TOPIC,o/'new'/r.TOPIC);folder=o/'new'/r.TOPIC
  atomic_json(folder/'review-queue/ru-RU.json',load_json(Path(__file__).parent/'fixtures/family07-decimal/russian-queue.json'))
  for suffix in ('.json','.raw.json','.fidelity.json'):(folder/'translations'/('ru-RU'+suffix)).unlink(missing_ok=True)
  return d,o,folder
 def hashes(self,root):return {str(p.relative_to(root)):digest(p.read_bytes().hex()) for p in root.rglob('*') if p.is_file()}
 def test_received_russian_review_and_full_draft_revalidate_read_only(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o,folder=self.setup(root);before=self.hashes(root)
   with patch('automation.agri_v2.client.ModelClient.text',side_effect=AssertionError('No new model request')):proof=ru.revalidate(d,o)
   self.assertEqual(proof['review']['faithful'],True);self.assertEqual(proof['review']['issues'],[]);self.assertEqual(proof['model_calls'],0);self.assertEqual(proof['numeric_validation_policy'],VERSION);self.assertEqual(before,self.hashes(root));self.assertTrue(proof['partial_edit_retained_not_applied'])
 def test_unchanged_positive_receipt_can_be_adopted_without_reset_or_edit_replay(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d,o,folder=self.setup(root);row=load_json(folder/'review-queue/ru-RU.json');old=self.hashes(folder/'review-queue/attempts/ru-RU/3');candidate=(folder/'review-queue/candidate-ru-RU.json').read_bytes();result=r.reconcile_russian(d,o)
   self.assertEqual(result['model_calls'],0);new=load_json(folder/'review-queue/ru-RU.json');self.assertEqual((new['attempts'],new['model_calls_spent'],new['status']),(3,7,'approved'));self.assertEqual(old,self.hashes(folder/'review-queue/attempts/ru-RU/3'));self.assertEqual(candidate,(folder/'review-queue/candidate-ru-RU.json').read_bytes());self.assertTrue(r.q.approved(folder,load_json(folder/'article.json'),'ru-RU'))
 def test_tampered_draft_or_review_cannot_be_promoted(self):
  for name in ('draft.raw.json','review-0.raw.json'):
   with tempfile.TemporaryDirectory() as td:
    root=Path(td);d,o,folder=self.setup(root);atomic_json(folder/'review-queue/attempts/ru-RU/3'/name,{'changed':True})
    with self.assertRaises(ValueError):ru.revalidate(d,o)
    self.assertFalse((folder/'translations/ru-RU.json').exists())
 def test_nonmechanical_pending_defect_not_silently_dismissed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,folder=self.setup(Path(td));row=load_json(folder/'review-queue/ru-RU.json');row['pending_issues'].append({'id':0,'detail':'real semantic defect'});atomic_json(folder/'review-queue/ru-RU.json',row)
   with self.assertRaises(ValueError):ru.revalidate(d,o)
 def test_existing_russian_target_never_overwritten(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,folder=self.setup(Path(td));atomic_json(folder/'translations/ru-RU.json',{'existing':True})
   with self.assertRaises(ValueError):r.reconcile_russian(d,o)
   self.assertEqual(load_json(folder/'translations/ru-RU.json'),{'existing':True})
 def test_admission_five_remaining_and_no_paid_russian_repair(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';a={};b={};rows={l:{} for l in r.LANGS+r.RETAINED}
   with patch.object(r,'inputs',return_value=(o/'new'/r.TOPIC,a,b,rows,[])),patch.object(r,'prior_proof',return_value={}),patch.object(r.transport,'capability_proof',return_value={}):
    req=r.expected(d,o);r.validate(req,d,o)
    for key,value in [('max_text_calls',6),('combined_prior_and_new_text_cap',11),('russian_model_calls',1),('max_source_fetches',1),('max_runs',2),('max_site_calls',1),('publication_authorized',True),('schedule_enabled',True),('reset_attempts',True)]:
     with self.subTest(key=key),self.assertRaises(r.Blocked):r.validate(dict(req,**{key:value}),d,o)
 def test_narrow_mutable_scope_all_attempt_history_is_protected(self):
  for path in ['review-queue/attempts/ru-RU/3/draft.raw.json','review-queue/candidate-ru-RU.json','regional-research/ru-RU/approved.json','review-queue/ar-IQ.json','translations/en-US.json','article.json']:self.assertFalse(r.mutable('out/new/'+r.TOPIC+'/'+path))
  for path in ['review-queue/ru-RU.json','translations/ru-RU.raw.json','review-queue/attempts/tg-TJ/3/draft.raw.json','regional-research/tg-TJ/approved.json']:self.assertTrue(r.mutable('out/new/'+r.TOPIC+'/'+path))
 def test_unknown_new_reservation_is_never_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);atomic_json(root/'out/infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});fn=Mock()
   with patch.object(r,'identity'):report=r.run({},root/'data',root/'out',reserve_fn=fn,client_factory_fn=fn)
   self.assertEqual(report['model_calls'],0);fn.assert_not_called()
 def test_manual_phase_only(self):
  env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123','GITHUB_TOKEN':'fake'}
  self.assertTrue(reserve(r.PHASE,r.ID,env,put_fn=lambda row:True))
  for change in [{'GITHUB_EVENT_NAME':'schedule'},{'GITHUB_REF_NAME':'main'}]:
   with self.assertRaises(ValueError):reserve(r.PHASE,r.ID,dict(env,**change),put_fn=Mock())
