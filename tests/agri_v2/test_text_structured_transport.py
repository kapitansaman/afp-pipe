import json,unittest
from unittest.mock import Mock
from automation.agri_v2.client import ModelClient,ModelOutputError
class StructuredTransportTests(unittest.TestCase):
 def test_text_schema_is_sent_to_provider_not_just_prompt(self):
  c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'message':{'content':'{"sections":[]}'},'finish_reason':'stop'}]});c.record_success=Mock();schema={'type':'object','additionalProperties':False,'properties':{'sections':{'type':'array'}},'required':['sections']};c.text('fixture',attempts=1,response_schema=schema);payload=c.request.call_args.args[2];self.assertEqual(payload['response_format'],{'type':'json_schema','json_schema':{'name':'grounded_persian_article','strict':True,'schema':schema}});self.assertEqual(c.request.call_count,1)
 def test_incomplete_response_is_not_accepted_even_when_json_parses(self):
  for reason,category in [('length','text_output_limit'),('content_filter','text_content_filtered')]:
   c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'message':{'content':'{}'},'finish_reason':reason}]});c.record_success=Mock()
   with self.assertRaisesRegex(ModelOutputError,category):c.text('fixture')
   c.record_success.assert_not_called()

 def test_safe_diagnostics_preserve_only_allowlisted_reason(self):
  from automation.agri_v2.failure_diagnostics import failure_details
  for category in ('text_output_limit','text_content_filtered','text_incomplete_response'):
   self.assertEqual(failure_details(ModelOutputError(category)),{'kind':'model_output','category':category})
  self.assertEqual(failure_details(ModelOutputError('SECRET PROVIDER BODY'))['category'],'unspecified')
