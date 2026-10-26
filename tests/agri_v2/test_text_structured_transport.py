import json,unittest
from unittest.mock import Mock
from automation.agri_v2.client import ModelClient,ModelOutputError
class StructuredTransportTests(unittest.TestCase):
 def test_text_schema_is_sent_to_provider_not_just_prompt(self):
  c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'message':{'content':'{"sections":[]}'},'finish_reason':'stop'}]});c.record_success=Mock();schema={'type':'object','additionalProperties':False,'properties':{'sections':{'type':'array'}},'required':['sections']};c.text('fixture',attempts=1,response_schema=schema);payload=c.request.call_args.args[2];self.assertEqual(payload['response_format'],{'type':'json_schema','json_schema':{'name':'grounded_persian_article','strict':True,'schema':schema}});self.assertEqual(c.request.call_count,1)
 def test_incomplete_response_is_not_accepted_even_when_json_parses(self):
  for reason in ['length','content_filter']:
   c=object.__new__(ModelClient);c.request=Mock(return_value={'choices':[{'message':{'content':'{}'},'finish_reason':reason}]});c.record_success=Mock()
   with self.assertRaisesRegex(ModelOutputError,'text_incomplete_response'):c.text('fixture')
   c.record_success.assert_not_called()
