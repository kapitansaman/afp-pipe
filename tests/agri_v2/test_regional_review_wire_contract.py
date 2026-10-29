import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2.regional_sources import response_schema,RegionalBlocked
from automation.agri_v2.translation_review_repair import request,RepairBlocked
from automation.agri_v2.failure_diagnostics import failure_details
class RegionalReviewWireContractTests(unittest.TestCase):
 def prompt(self):return {'_role_skill':'evidence-reviewer','_role_language':'en-US','task':'Regional applicability review.','approved_facts':[{'fact_id':'f0'},{'fact_id':'f1'}],'documents':[{'id':'s0','text':'untrusted institutional excerpt'}]}
 def test_schema_requires_version_objections_and_exact_bound_fact_count(self):
  schema=response_schema('regional-evidence-review',self.prompt());props=schema['properties'];self.assertEqual(props['regional_review_schema_version']['enum'],[2]);self.assertIn('rejection_reasons',schema['required']);self.assertFalse(schema['additionalProperties']);checks=props['fact_checks'];self.assertEqual((checks['minItems'],checks['maxItems']),(2,2));self.assertEqual(checks['items']['properties']['fact_id']['enum'],['f0','f1']);self.assertEqual(checks['items']['properties']['document_id']['enum'],['s0',None]);self.assertFalse(checks['items']['additionalProperties'])
 def test_unsupported_negative_can_report_no_document_without_inventing_one(self):
  schema=response_schema('regional-evidence-review-fallback',self.prompt());props=schema['properties'];self.assertIn(None,props['fact_checks']['items']['properties']['document_id']['enum']);self.assertEqual(props['rejection_reasons']['items']['properties']['fact_ids']['items']['enum'],['f0','f1']);self.assertIn('article_quote',props['rejection_reasons']['items']['required']);self.assertEqual(props['rejection_reasons']['maxItems'],5)
 def test_only_application_owned_regional_task_and_role_get_this_schema(self):
  self.assertIsNone(response_schema('draft',self.prompt()));self.assertIsNone(response_schema('regional-evidence-review',dict(self.prompt(),_role_skill='translator')))
  for value in (dict(self.prompt(),documents=[]),dict(self.prompt(),approved_facts=[{'fact_id':'f0'},{'fact_id':'f0'}])):
   with self.assertRaises(RegionalBlocked):response_schema('regional-evidence-review',value)
 def test_new_receipt_binds_native_schema_and_cached_response_never_replays(self):
  client=Mock();negative={'regional_review_schema_version':2,'applicable':False,'rejection_reasons':[{'reason':'Retained negative, not converted to approval.'}]};client.text.return_value=negative
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);first=request(client,root,'regional-evidence-review',self.prompt(),4);second=request(client,root,'regional-evidence-review',self.prompt(),4);self.assertEqual(first,negative);self.assertEqual(second,negative);self.assertFalse(first['applicable']);self.assertEqual(client.text.call_count,1);self.assertEqual(client.text.call_args.kwargs['response_schema'],response_schema('regional-evidence-review',self.prompt()));self.assertEqual(client.text.call_args.kwargs['attempts'],1);self.assertIn('response_schema_sha256',json.loads((root/'regional-evidence-review.receipt.json').read_text()))
 def test_unknown_regional_request_is_reserved_never_replayed(self):
  client=Mock();client.text.side_effect=TimeoutError()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(TimeoutError):request(client,root,'regional-evidence-review',self.prompt(),4)
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',self.prompt(),4)
  self.assertEqual(client.text.call_count,1)
 def test_invalid_wire_inputs_have_static_redacted_diagnostic(self):
  self.assertEqual(failure_details(RegionalBlocked('regional_review_wire_inputs_invalid'))['category'],'regional_review_wire_inputs_invalid')
