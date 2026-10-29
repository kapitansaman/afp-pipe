import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import regional_keyed_wire as w
from automation.agri_v2.regional_sources import response_schema,RegionalBlocked,review_prompt,validate_local_review
from automation.agri_v2.translation_review_repair import request,RepairBlocked
from automation.agri_v2.queue import load_json,atomic_json
from automation.agri_v2.client import parse_text_object,ModelOutputError,ModelClient
from automation.agri_v2.failure_diagnostics import failure_details

class RegionalKeyedWireTests(unittest.TestCase):
 def prompt(self):return {'_role_skill':'evidence-reviewer','_role_language':'en-US','_regional_wire_contract':w.VERSION,'task':'fixture keyed review','approved_facts':[{'fact_id':'f0'},{'fact_id':'f1'}],'documents':[{'id':'s0','text':'literal fixture document text'}]}
 def row(self):return {'supported':False,'document_id':None,'quote':'','source_kind':'news','country':None,'scope':'Evidence remains insufficient for this exact fixture.','international_fallback':False,'local_evidence_gap':'','transfer_limits_retained':False}
 def raw(self):return {'regional_review_schema_version':2,'applicable':False,'no_unsupported_local_prescription':True,'country_limits_retained':True,'fact_checks':{'f0':self.row(),'f1':self.row()},'rejection_reasons':[]}
 def test_keys_require_every_fact_once_without_an_inner_id(self):
  schema=response_schema('regional-evidence-review',self.prompt());checks=schema['properties']['fact_checks'];self.assertEqual(checks['type'],'object');self.assertEqual(checks['required'],['f0','f1']);self.assertFalse(checks['additionalProperties'])
  self.assertEqual(set(checks['properties']),{'f0','f1'});self.assertNotIn('fact_id',checks['properties']['f0']['properties'])
 def test_missing_unknown_legacy_array_and_inner_id_are_rejected_not_repaired(self):
  schema=response_schema('regional-evidence-review',self.prompt())
  for checks in [{'f0':self.row()},{'f0':self.row(),'f2':self.row()},[dict(fact_id='f0',**self.row())]*2,{'f0':dict(self.row(),fact_id='f0'),'f1':self.row()}]:
   with self.subTest(checks=type(checks).__name__),self.assertRaises(RegionalBlocked):w.canonical(dict(self.raw(),fact_checks=checks),schema)
 def test_projection_is_lossless_ordered_and_does_not_change_raw_or_negative(self):
  raw=self.raw();raw['fact_checks']={'f1':self.row(),'f0':self.row()};before=copy.deepcopy(raw);result=w.canonical(raw,response_schema('regional-evidence-review',self.prompt()))
  self.assertEqual(raw,before);self.assertEqual([c['fact_id'] for c in result['fact_checks']],['f0','f1']);self.assertFalse(result['applicable'])
  self.assertEqual({c['fact_id']:{k:v for k,v in c.items() if k!='fact_id'} for c in result['fact_checks']},raw['fact_checks'])
  from automation.agri_v2.claim_policy import PolicyBlocked
  with self.assertRaises(PolicyBlocked):validate_local_review(result,{}, {'approved_facts':[{'fact_id':'f0'},{'fact_id':'f1'}]},[{'url':'https://extension.example.edu/fixture','text':'actual fixture'}],'en-US')
 def test_compact_bounds_never_clip_or_synthesize_text(self):
  schema=response_schema('regional-evidence-review',self.prompt());props=schema['properties']['fact_checks']['properties']['f0']['properties'];self.assertEqual(props['scope']['minLength'],30);self.assertNotIn('minLength',props['local_evidence_gap']);self.assertNotIn('minLength',props['quote']);w.validate(self.raw(),schema)
  for field,n in [('quote',1201),('scope',481),('local_evidence_gap',481)]:
   raw=self.raw();raw['fact_checks']['f0'][field]='x'*n;before=copy.deepcopy(raw)
   with self.assertRaises(RegionalBlocked):w.canonical(raw,schema)
   self.assertEqual(raw,before)
 def test_receipt_binds_wire_schema_adapter_and_canonical_hash(self):
  raw=self.raw();client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);first=request(client,root,'regional-evidence-review',self.prompt(),1);second=request(client,root,'regional-evidence-review',self.prompt(),1)
   self.assertEqual(first,second);self.assertEqual(client.text.call_count,1);self.assertEqual(load_json(root/'regional-evidence-review.raw.json'),raw);receipt=load_json(root/'regional-evidence-review.receipt.json');self.assertEqual(receipt['response_adapter'],w.VERSION);self.assertIn('canonical_sha256',receipt);self.assertTrue(client.text.call_args.kwargs['reject_duplicate_keys']);self.assertEqual(client.text.call_args.kwargs['max_tokens'],14000)
   receipt.pop('canonical_sha256');atomic_json(root/'regional-evidence-review.receipt.json',receipt)
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',self.prompt(),1)
   self.assertEqual(client.text.call_count,1)
 def test_invalid_received_wire_is_retained_and_never_billed_again(self):
  raw=dict(self.raw(),fact_checks={'f0':self.row()});client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for _ in range(2):
    with self.assertRaises(RegionalBlocked):request(client,root,'regional-evidence-review',self.prompt(),1)
   self.assertEqual(client.text.call_count,1);self.assertEqual(load_json(root/'regional-evidence-review.raw.json'),raw);self.assertNotIn('canonical_sha256',load_json(root/'regional-evidence-review.receipt.json'))
 def test_unknown_not_replayed_and_missing_schema_hash_fails_closed(self):
  client=Mock();client.text.side_effect=TimeoutError()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(TimeoutError):request(client,root,'regional-evidence-review',self.prompt(),1)
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',self.prompt(),1)
   self.assertEqual(client.text.call_count,1)
  client=Mock();client.text.return_value=self.raw()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);request(client,root,'regional-evidence-review',self.prompt(),1);receipt=load_json(root/'regional-evidence-review.receipt.json');receipt.pop('response_schema_sha256');atomic_json(root/'regional-evidence-review.receipt.json',receipt)
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',self.prompt(),1)
   self.assertEqual(client.text.call_count,1)
 def test_raw_and_canonical_hash_tampering_fail_closed(self):
  for field in ['raw_sha256','canonical_sha256']:
   client=Mock();client.text.return_value=self.raw()
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);request(client,root,'regional-evidence-review',self.prompt(),1);receipt=load_json(root/'regional-evidence-review.receipt.json');receipt[field]='changed';atomic_json(root/'regional-evidence-review.receipt.json',receipt)
    with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',self.prompt(),1)
    self.assertEqual(client.text.call_count,1)
 def test_new_prompt_cannot_reinterpret_old_array_receipts_or_negatives(self):
  legacy={k:v for k,v in self.prompt().items() if k!='_regional_wire_contract'};raw=dict(self.raw(),fact_checks=[dict(fact_id=i,**r) for i,r in self.raw()['fact_checks'].items()]);client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.assertEqual(request(client,root,'regional-evidence-review',legacy,1),raw);before={p.name:p.read_bytes() for p in root.iterdir()}
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',self.prompt(),1)
   self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()});self.assertEqual(client.text.call_count,1)
 def test_real_shared_prompt_keeps_all_article_facts_and_sources(self):
  article={'content_html':'<p>Complete fixture text.</p>','faq':[{'question':'q','answer':'a'}]};facts=[{'fact_id':'f0','claim':'Original fact.'}];docs=[{'url':'https://extension.example.edu/a','text':'Complete source fixture.'}];prompt=review_prompt(article,{'approved_facts':facts},'en-US',docs,wire=w.VERSION)
  self.assertEqual(prompt['_regional_wire_contract'],w.VERSION);self.assertEqual(prompt['article'],article);self.assertEqual(prompt['approved_facts'],facts);self.assertEqual(prompt['documents'][0]['text'],docs[0]['text']);self.assertIn('OBJECT',prompt['task']);self.assertNotIn('fact_checks:[',prompt['task'])
 def test_unknown_wire_version_is_not_silently_downgraded(self):
  with self.assertRaises(RegionalBlocked):response_schema('regional-evidence-review',dict(self.prompt(),_regional_wire_contract='unknown'))
 def test_duplicate_json_keys_are_rejected_before_information_loss(self):
  for raw in ['{"fact_checks":{"f0":1,"f0":2}}','{"x":1,"x":2}','{"fact_checks":{"f0":1,"f\\u0030":2}}']:
   with self.assertRaisesRegex(ModelOutputError,'text_json_duplicate_keys'):parse_text_object(raw,reject_duplicate_keys=True)
  self.assertEqual(parse_text_object('{"x":1,"x":2}'),{'x':2}) # old parser contract is unchanged
  self.assertEqual(failure_details(ModelOutputError('text_json_duplicate_keys'))['category'],'text_json_duplicate_keys')
 def test_keyed_strict_parser_rejects_wrappers_and_truncation_without_repair(self):
  for raw in ['```json\n{"x":1}\n```','prefix {"x":1}',json.dumps('{"x":1}'),' {"x":']:
   with self.assertRaises(ModelOutputError):parse_text_object(raw,reject_duplicate_keys=True)
  self.assertEqual(parse_text_object('```json\n{"x":1}\n```'),{'x':1})
 def test_keyed_transport_uses_strict_parser_and_output_limit_still_blocks(self):
  client=object.__new__(ModelClient);client.record_success=Mock();client.request=Mock(return_value={'choices':[{'message':{'content':'{"x":1,"x":2}'}}]})
  with self.assertRaisesRegex(ModelOutputError,'text_json_duplicate_keys'):client.text('fixture',response_schema={'type':'object'},attempts=1,reject_duplicate_keys=True)
  client.record_success.assert_not_called();client.request.return_value={'choices':[{'finish_reason':'length','message':{'content':'{"x":1}'}}]}
  with self.assertRaisesRegex(ModelOutputError,'text_output_limit'):client.text('fixture',attempts=1,reject_duplicate_keys=True)
  self.assertEqual(client.request.call_count,2)
