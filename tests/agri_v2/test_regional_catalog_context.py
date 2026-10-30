import copy,json,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import regional_catalog_context as c,regional_catalog_consistency as old
from automation.agri_v2.regional_sources import review_prompt,response_schema,RegionalBlocked,validate_local_review
from automation.agri_v2.translation_review_repair import request,RepairBlocked
from automation.agri_v2.pipeline import digest
from automation.agri_v2.queue import OUT,load_json
import test_regional_catalog_consistency as f
class ContextTests(unittest.TestCase):
 def fixture(self,lang='ar-IQ',docs=None):
  z=f.CatalogConsistencyTests();docs=docs if docs is not None else z.docs();p=review_prompt(z.article(),{'approved_facts':z.facts()},lang,docs);return z,p
 def schema(self,p):return response_schema('regional-evidence-review-fallback',p)
 def project(self,p,raw):return c.canonical(raw,self.schema(p),c.bound(p))
 def test_default_v3_distinct_from_explicit_frozen_v2(self):
  z,p=self.fixture();self.assertEqual(p['_regional_wire_contract'],c.VERSION)
  q=review_prompt(z.article(),{'approved_facts':z.facts()},'ar-IQ',z.docs(),wire=old.VERSION);self.assertEqual(q['_regional_wire_contract'],old.VERSION);self.assertNotIn('source_context_policy',q);self.assertEqual(old.bound(q)['version'],old.VERSION)
 def test_institution_label_never_trial_geography_or_acceptance(self):
  z,p=self.fixture();ctx=p['source_context_policy'];self.assertEqual(ctx['country_semantics'],'institution_host_metadata_only_not_trial_geography_or_local_applicability');self.assertTrue(all(d['source_institution_country']=='US' and not d['technical_local_source'] for d in ctx['documents']));self.assertIn('NOT trial geography',p['task']);self.assertIn('General qualitative model knowledge is permitted',p['task'])
 def test_known_country_null_wrong_label_rejected_not_filled(self):
  z,p=self.fixture()
  for country in [None,'IQ','RU','USA']:
   raw=z.raw(p);raw['fact_checks']['f0']['country']=country;before=copy.deepcopy(raw)
   with self.assertRaises(RegionalBlocked):self.project(p,raw)
   self.assertEqual(raw,before)
 def test_foreign_positive_requires_explicit_gap_and_transfer_fields(self):
  z,p=self.fixture()
  for key,value in [('local_evidence_gap','x'*29),('international_fallback',False),('transfer_limits_retained',False),('source_kind','news'),('scope','x'*29)]:
   raw=z.raw(p);raw['fact_checks']['f0'][key]=value
   with self.subTest(key=key),self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_short_meaningless_space_padding_not_server_approval(self):
  z,p=self.fixture();raw=z.raw(p);raw['fact_checks']['f0']['local_evidence_gap']='x'+' '*40;value=self.project(p,raw)
  with self.assertRaises(RegionalBlocked):validate_local_review(value,z.article(),{'approved_facts':z.facts()},z.docs(),'ar-IQ')
 def test_known_local_source_has_no_invented_foreign_gap_requirement(self):
  z,p=self.fixture('en-US');raw=z.raw(p);raw['fact_checks']['f0'].update(local_evidence_gap='',international_fallback=False,transfer_limits_retained=False);value=self.project(p,raw);self.assertEqual(value['fact_checks'][0]['local_evidence_gap'],'');validate_local_review(value,z.article(),{'approved_facts':z.facts()},z.docs(),'en-US')
 def test_country_and_locality_bound_to_selected_passage_not_other_document(self):
  z=f.CatalogConsistencyTests();docs=z.docs()[:2];docs[0]=dict(docs[0],url='https://mcx.gov.ru/a');docs[1]=dict(docs[1],url='https://extension.example.edu/b');facts=[{'fact_id':'f0','claim':'Qualitative observation.'}];p=review_prompt(z.article(),{'approved_facts':facts},'en-US',docs);raw=z.raw(p);row=raw['fact_checks']['f0'];row.update(evidence_quote_id='d0p0',country='RU');self.project(p,raw)
  for mutation in [{'country':'US'},{'international_fallback':False},{'local_evidence_gap':''}]:
   bad=copy.deepcopy(raw);bad['fact_checks']['f0'].update(mutation)
   with self.assertRaises(RegionalBlocked):self.project(p,bad)
  row.update(evidence_quote_id='d1p0',country='US',international_fallback=False,local_evidence_gap='',transfer_limits_retained=False);self.project(p,raw)
 def test_unknown_institution_label_is_not_invented(self):
  z=f.CatalogConsistencyTests();docs=[dict(z.docs()[1],url='https://www.fao.org/a')];p=review_prompt(z.article(),{'approved_facts':z.facts()},'ar-IQ',docs);self.assertIsNone(p['source_context_policy']['documents'][0]['source_institution_country']);raw=z.raw(p);raw['fact_checks']['f0']['country']=None;value=self.project(p,raw);self.assertIsNone(value['fact_checks'][0]['country'])
 def test_explicit_negative_still_possible_with_null_country_no_gap(self):
  z,p=self.fixture();raw=z.raw(p);row=raw['fact_checks']['f0'];row.update(supported=False,evidence_quote_id=None,country=None,local_evidence_gap='',international_fallback=False,transfer_limits_retained=False,objection=z.objection(p,'fact_supported'));before=copy.deepcopy(raw);value=self.project(p,raw);self.assertEqual(raw,before);self.assertFalse(value['fact_checks'][0]['supported']);self.assertEqual(len(value['rejection_reasons']),1)
 def test_no_numeric_candidates_never_become_positive_from_metadata(self):
  z,p=self.fixture();p=review_prompt(z.article(),{'approved_facts':[{'fact_id':'f0','claim':'Observed 987654 units.'}]},'ar-IQ',z.docs());raw=z.raw(p);self.assertFalse(self.project(p,raw)['fact_checks'][0]['supported']);self.assertEqual(len(self.schema(p)['properties']['fact_checks']['properties']['f0']['anyOf']),1)
 def test_projection_copies_model_metadata_without_inference(self):
  z,p=self.fixture();raw=z.raw(p);before=copy.deepcopy(raw);value=self.project(p,raw);self.assertEqual(raw,before)
  for k in ['country','scope','international_fallback','local_evidence_gap','transfer_limits_retained']:self.assertEqual(value['fact_checks'][0][k],raw['fact_checks']['f0'][k])
 def test_context_snapshot_and_inputs_tampering_block_before_model(self):
  z,p=self.fixture()
  for mutate in [lambda x:x['source_context_policy']['documents'][0].update(source_institution_country='IQ'),lambda x:x['source_context_policy']['documents'][0].update(technical_local_source=True),lambda x:x['documents'][0].update(url='https://mcx.gov.ru/a'),lambda x:x['regional_profile'].update(countries=['IQ'])]:
   bad=copy.deepcopy(p);mutate(bad);client=Mock()
   with tempfile.TemporaryDirectory() as d,self.assertRaises(RegionalBlocked):request(client,Path(d),'regional-evidence-review-fallback',bad,1)
   client.text.assert_not_called()
 def test_v3_receipt_binds_catalog_schema_and_no_replay(self):
  z,p=self.fixture();raw=z.raw(p);client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);value=request(client,root,'regional-evidence-review-fallback',p,1);self.assertEqual(value,request(client,root,'regional-evidence-review-fallback',p,1));self.assertEqual(client.text.call_count,1);receipt=load_json(root/'regional-evidence-review-fallback.receipt.json');self.assertEqual(receipt['response_adapter'],c.VERSION);self.assertEqual(receipt['quote_catalog_sha256'],digest(c.bound(p)));self.assertEqual(receipt['raw_sha256'],digest(raw));self.assertTrue(client.text.call_args.kwargs['reject_duplicate_keys'])
 def test_received_invalid_country_keeps_raw_without_canonical_no_second_call(self):
  z,p=self.fixture();raw=z.raw(p);raw['fact_checks']['f0']['country']=None;client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for _ in range(2):
    with self.assertRaises((RegionalBlocked,RepairBlocked)):request(client,root,'regional-evidence-review-fallback',p,1)
   self.assertEqual(client.text.call_count,1);receipt=load_json(root/'regional-evidence-review-fallback.receipt.json');self.assertEqual(receipt['status'],'received');self.assertNotIn('canonical_sha256',receipt);self.assertEqual(load_json(root/'regional-evidence-review-fallback.raw.json'),raw)
 def test_actual_old_paid_arabic_outcome_stays_failed_not_repaired(self):
  root=OUT/'infrastructure-probes/authorized-isolated-regional-v2-three-call-validation-v1';report=load_json(root/'report.json');self.assertEqual(report['results'][0]['failure']['category'],'regional_country_scope_required');raw=load_json(root/'languages/ar-IQ/regional-evidence-review-fallback.raw.json');self.assertTrue(all(r['country'] is None for r in raw['fact_checks'].values()));before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
  from automation.agri_v2 import regional_isolated_validation as frozen
  _,article,brief,_=frozen.inputs();docs=[load_json(root/'documents'/(str(i)+'.json')) for i in range(3)];p=review_prompt(article,brief,'ar-IQ',docs)
  with self.assertRaises(RegionalBlocked):self.project(p,raw)
  self.assertTrue(all(p.read_bytes()==v for p,v in before.items()))
 def test_actual_paid_english_contract_can_be_checked_offline_not_promoted(self):
  root=OUT/'infrastructure-probes/authorized-isolated-regional-v2-three-call-validation-v1'
  from automation.agri_v2 import regional_isolated_validation as frozen
  _,article,brief,_=frozen.inputs();docs=[load_json(root/'documents'/(str(i)+'.json')) for i in range(3)];raw=load_json(root/'languages/en-US/regional-evidence-review-fallback.raw.json');p=review_prompt(article,brief,'en-US',docs);value=self.project(p,raw);self.assertTrue(validate_local_review(value,article,brief,docs,'en-US'));self.assertFalse((root/'languages/en-US/approved.json').exists())
 def test_empty_local_pack_allows_fallback_prompt_but_never_empty_review_transport(self):
  z,p=self.fixture(docs=[]);self.assertEqual(p['source_context_policy']['documents'],[]);client=Mock()
  with tempfile.TemporaryDirectory() as d,self.assertRaises(RegionalBlocked):request(client,Path(d),'regional-evidence-review',p,1)
  client.text.assert_not_called()
 def test_new_guard_is_allowlisted(self):
  from automation.agri_v2.failure_diagnostics import failure_details
  self.assertEqual(failure_details(RegionalBlocked('regional_catalog_context_invalid'))['category'],'regional_catalog_context_invalid')
