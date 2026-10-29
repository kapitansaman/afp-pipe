import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2.translation_review_repair import draft_response_schema,request,RepairBlocked
from automation.agri_v2.failure_diagnostics import failure_details

class TranslationDraftWireContractTests(unittest.TestCase):
 def prompt(self):return {'_role_skill':'translator','_role_language':'en-US','task':'Translate the indexed source.','source':[{'id':0,'text':'متن اول'},{'id':1,'text':'متن دوم'}]}
 def test_schema_requires_complete_object_rows_and_no_error_message_field(self):
  s=draft_response_schema('draft',self.prompt());a=s['properties']['translations'];self.assertEqual((a['minItems'],a['maxItems']),(2,2));self.assertEqual(a['items']['required'],['id','text']);self.assertFalse(a['items']['additionalProperties']);self.assertFalse(s['additionalProperties']);self.assertEqual(a['items']['properties']['id']['enum'],[0,1])
 def test_other_tasks_and_ambiguous_indices_do_not_change_wire_contract(self):
  self.assertIsNone(draft_response_schema('review',self.prompt()));p=self.prompt();p['source'][1]['id']=0;self.assertIsNone(draft_response_schema('draft',p))
 def test_request_passes_strict_schema_and_retains_one_attempt(self):
  c=Mock();c.text.return_value={'translations':[{'id':0,'text':'First text'},{'id':1,'text':'Second text'}]}
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);first=request(c,root,'draft',self.prompt(),4);request(c,root,'draft',self.prompt(),4);self.assertEqual(c.text.call_count,1)
   self.assertEqual(c.text.call_args.kwargs['response_schema'],draft_response_schema('draft',self.prompt()));self.assertEqual(c.text.call_args.kwargs['attempts'],1)
   receipt=json.loads((root/'draft.receipt.json').read_text());self.assertIn('response_schema_sha256',receipt)
 def test_unknown_response_is_not_replayed_under_new_schema(self):
  c=Mock();c.text.side_effect=TimeoutError()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(TimeoutError):request(c,root,'draft',self.prompt(),4)
   with self.assertRaises(RepairBlocked):request(c,root,'draft',self.prompt(),4)
  self.assertEqual(c.text.call_count,1)
 def test_static_translation_errors_are_identified_without_raw_provider_text(self):
  self.assertEqual(failure_details(RepairBlocked('invalid_translation_row'))['category'],'invalid_translation_row')
  self.assertEqual(failure_details(RepairBlocked('untrusted provider detail'))['category'],'unspecified')
