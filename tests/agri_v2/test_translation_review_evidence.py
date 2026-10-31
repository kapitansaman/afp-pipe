import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import translation_review_evidence as e
from automation.agri_v2 import translation_review_repair as r
from automation.agri_v2.tajik_full_verification import check_review
class ReviewEvidenceTests(unittest.TestCase):
 def issue(self,target='Айдаҳо',**kw):
  return dict(dict(id=0,category='wrong_language',detail='A reported mixed-script defect',source_text='آیداهو',target_text=target,offending_text=target,evidence_code='mixed_script'),**kw)
 def test_current_cyrillic_cannot_be_called_mixed_script(self):
  with self.assertRaisesRegex(r.RepairBlocked,'mixed_script_evidence_absent'):e.validate_issue(self.issue(),'آیداهو','Айдаҳо')
 def test_old_latin_quote_rejected_on_corrected_target(self):
  with self.assertRaisesRegex(r.RepairBlocked,'quote_absent'):e.validate_issue(self.issue(offending_text='Айдaҳо'),'آیداهو','Айдаҳо')
 def test_old_full_pair_is_rejected(self):
  with self.assertRaisesRegex(r.RepairBlocked,'not_current_pair'):e.validate_issue(self.issue('Айдaҳо'),'آیداهو','Айдаҳо')
 def test_real_mixed_script_remains_negative(self):
  e.validate_issue(self.issue('Айдaҳо'),'آیداهو','Айдaҳо')
 def test_real_semantic_defect_not_suppressed(self):
  e.validate_issue(self.issue(category='meaning',evidence_code='semantic'),'آیداهو','Айдаҳо')
 def test_missing_evidence_is_not_auto_bound(self):
  with self.assertRaises(r.RepairBlocked):e.validate_issue({'category':'meaning','detail':'No actual quotation'},'آیداهو','Айдаҳо')
 def test_script_code_cannot_mask_semantic_issue(self):
  with self.assertRaises(r.RepairBlocked):e.validate_issue(self.issue('Айдaҳо',category='meaning'),'آیداهو','Айдaҳо')
 def test_false_arabic_claim_rejected(self):
  with self.assertRaises(r.RepairBlocked):e.validate_issue(self.issue(evidence_code='arabic_residue'),'آیداهو','Айдаҳо')
 def test_actual_arabic_residue_retained(self):
  e.validate_issue(self.issue('Айдаҳо خاک',offending_text='خاک',evidence_code='arabic_residue'),'آیداهو','Айдаҳо خاک')
 def test_other_language_remains_independent_semantic_review(self):
  e.validate_issue(self.issue('wrong English',evidence_code='other_language'),'آیداهو','wrong English')
 def test_strict_check_blocks_cached_unbound_negative(self):
  v={'faithful':False,'reason':'no','issues':[self.issue()]}
  with self.assertRaisesRegex(r.RepairBlocked,'mixed_script_evidence_absent'):check_review(v,['آیداهو'],{'translations':[{'id':0,'text':'Айдаҳо'}]}, {},require_evidence=True)
 def test_prepare_preserves_input_and_adds_versioned_contract(self):
  p={'task':'Review','_role_skill':'translation-reviewer','_role_language':'tg-TJ','source':[{'id':0,'text':'آیداهو'}],'target':[{'id':0,'text':'Айдаҳо'}]};old=copy.deepcopy(p);new=e.prepare(p)
  self.assertEqual(p,old);self.assertEqual(new['_translation_evidence_contract'],e.VERSION)
  schema=e.schema('review-1',new);self.assertIn('offending_text',schema['properties']['issues']['items']['required']);self.assertIsNone(e.schema('review-1',p))
 def test_no_new_model_call_or_old_receipt_rebinding(self):
  from automation.agri_v2.queue import atomic_json
  from automation.agri_v2.pipeline import digest
  class NoCalls:
   def text(self,*a,**kw):raise AssertionError('No API allowed')
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);atomic_json(root/'review-1.receipt.json',{'prompt_sha256':digest({'task':'old'}),'max_calls':1});before=(root/'review-1.receipt.json').read_bytes()
   with self.assertRaisesRegex(r.RepairBlocked,'binding_changed'):r.request(NoCalls(),root,'review-1',{'task':'new evidence contract'},4)
   self.assertEqual(before,(root/'review-1.receipt.json').read_bytes())
 def test_actual_saved_tajik_patch_has_no_mixed_script(self):
  root=Path(__file__).resolve().parents[2]/'artifacts/agri-v2/new/agri-6fc1032cdf42/review-queue/attempts/tg-TJ/3';p=root/'edit.raw.json'
  if not p.exists():self.skipTest('Live cache not included in this checkout')
  import re
  rows=json.loads(p.read_text())['patches'];self.assertEqual({x['id'] for x in rows},{20,22,74})
  for row in rows:self.assertIsNone(re.search(e.MIXED,row['text']))
 def test_real_negative_is_not_converted_to_approval(self):
  v={'faithful':False,'reason':'Genuine unresolved meaning','issues':[self.issue(category='meaning',evidence_code='semantic')]}
  with patch('automation.agri_v2.tajik_full_verification.feedback',return_value=[]):
   issues=check_review(v,['آیداهو'],{'translations':[{'id':0,'text':'Айдаҳо'}]}, {},require_evidence=True)
  self.assertEqual(issues[0]['category'],'meaning');self.assertFalse(v['faithful'])
 def test_new_transport_has_native_schema_and_immutable_receipt(self):
  from automation.agri_v2.queue import load_json
  from automation.agri_v2.pipeline import digest
  p=e.prepare({'task':'Review','_role_skill':'translation-reviewer','_role_language':'tg-TJ','source':[{'id':0,'text':'آیداهو'}],'target':[{'id':0,'text':'Айдаҳо'}]})
  class Client:
   def __init__(self):self.calls=0
   def text(self,text,**kw):self.calls+=1;self.kw=kw;return {'faithful':True,'reason':'Compared current pair','issues':[]}
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);c=Client();v=r.request(c,root,'review-1',p,4);self.assertEqual(c.calls,1)
   self.assertEqual(c.kw['attempts'],1);self.assertEqual(c.kw['response_schema'],e.schema('review-1',p))
   receipt=load_json(root/'review-1.receipt.json');self.assertEqual(receipt['raw_sha256'],digest(v));self.assertEqual(receipt['response_schema_sha256'],digest(c.kw['response_schema']))
   self.assertEqual(r.request(c,root,'review-1',p,4),v);self.assertEqual(c.calls,1)
