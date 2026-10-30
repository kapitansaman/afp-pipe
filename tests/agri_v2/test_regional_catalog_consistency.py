import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import regional_catalog_consistency as c,regional_quote_catalog as old
from automation.agri_v2.regional_sources import review_prompt,response_schema,RegionalBlocked,validate_local_review
from automation.agri_v2.translation_review_repair import request,RepairBlocked
from automation.agri_v2.claim_policy import validate_regional_objections
from automation.agri_v2.pipeline import digest
from automation.agri_v2.queue import load_json,atomic_json

class CatalogConsistencyTests(unittest.TestCase):
 def article(self):return {'content_html':'<p>Measured observation is bounded to its original experiment, not a local prescription.</p>','excerpt':'Independent source context remains necessary.'}
 def docs(self):
  texts=['Qualitative crop and soil observations do not establish a fixed measurement or universal irrigation rule. '*15,'The trial reported 25 mm under measured field conditions, limited to that crop and region. '+'Retain all surrounding experimental and measurement context. '*15,'The separate experiment reported 40 mm, not a substitute for a different threshold. '+'Retain the actual cultivar, water and soil conditions. '*15]
  return [{'url':'https://extension.example.edu/'+str(i),'text':t,'sha256':hashlib.sha256(t.encode()).hexdigest()} for i,t in enumerate(texts)]
 def facts(self):return [{'fact_id':'f0','kind':'source_observation','claim':'Observed threshold 25 mm.'}]
 def prompt(self,facts=None,article=None,docs=None):return review_prompt(self.article() if article is None else article,{'approved_facts':self.facts() if facts is None else facts},'en-US',self.docs() if docs is None else docs,wire=c.VERSION)
 def schema(self,p):return response_schema('regional-evidence-review',p)
 def objection(self,p,flag='applicable',ident='f0'):
  return {'flag':flag,'fact_ids':[ident],'claim_type':'source_observation','article_quote_id':p['quote_catalog']['article_passages'][0]['id'],'reason':'This bounded observation lacks sufficient applicability evidence for the actual claim.'}
 def raw(self,p):
  rows={}
  for ident,row in p['evidence_selection']['facts'].items():
   ids=row['candidate_ids'];supported=bool(ids)
   rows[ident]={'supported':supported,'evidence_quote_id':ids[0] if ids else None,'source_kind':'extension_guidance','country':'US','scope':'Only measured source-region experimental conditions are retained.','international_fallback':True,'local_evidence_gap':'Local evidence does not cover this specific bounded observation.','transfer_limits_retained':True,'objection':None if supported else self.objection(p,'fact_supported',ident)}
  return {'regional_review_schema_version':2,**{flag:{'value':True,'objection':None} for flag in c.FLAGS},'fact_checks':rows}
 def project(self,p,raw=None):return c.canonical(self.raw(p) if raw is None else raw,self.schema(p),c.bound(p))
 def test_explicit_historical_v2_and_v1_remain_distinct(self):
  p=self.prompt();self.assertEqual(p['_regional_wire_contract'],c.VERSION)
  q=review_prompt(self.article(),{'approved_facts':self.facts()},'en-US',self.docs(),wire=old.VERSION);self.assertEqual(q['_regional_wire_contract'],old.VERSION);self.assertNotIn('evidence_selection',q);self.assertIn('rejection_reasons',self.schema(q)['properties']);self.assertNotIn('rejection_reasons',self.schema(p)['properties'])
 def test_candidates_are_exact_same_numeric_predicate_as_server(self):
  from automation.agri_v2.scoped_research import tokens
  p=self.prompt();eligible=p['evidence_selection']['facts']['f0']['candidate_ids'];expected=[q['id'] for q in p['quote_catalog']['source_passages'] if not tokens(self.facts()[0]['claim'])-tokens(q['text'])];self.assertEqual(eligible,expected);self.assertTrue(eligible);self.assertLess(len(eligible),len(p['quote_catalog']['source_passages']))
 def test_multilingual_and_spelled_number_tokens_reuse_existing_parser(self):
  from automation.agri_v2.scoped_research import tokens
  for claim in ['مشاهدهٔ ۲۵ میلی‌متر','Observed 1,000 units','Observed two weeks']:
   p=self.prompt(facts=[{'fact_id':'f0','claim':claim}]);self.assertEqual(p['evidence_selection']['facts']['f0']['required_numeric_tokens'],sorted(tokens(claim)))
 def test_qualitative_knowledge_is_not_removed_by_numeric_gate(self):
  p=self.prompt(facts=[{'fact_id':'f0','kind':'qualitative','claim':'Check actual crop and soil conditions.'}]);self.assertEqual(p['evidence_selection']['facts']['f0']['candidate_ids'],[q['id'] for q in p['quote_catalog']['source_passages']]);self.assertIn('General qualitative model knowledge is permitted',p['task'])
 def test_conversion_exemption_preserves_existing_rules_not_new_evidence(self):
  p=self.prompt(facts=[{'fact_id':'f0','kind':'deterministic_conversion','claim':'Converted result 987654 units.'}]);self.assertEqual(p['evidence_selection']['facts']['f0']['required_numeric_tokens'],[]);self.assertNotIn('987654',json.dumps(p['quote_catalog']))
 def test_no_candidates_permits_only_honest_bound_negative(self):
  p=self.prompt(facts=[{'fact_id':'f0','claim':'Observed 987654 units.'}]);self.assertEqual(p['evidence_selection']['facts']['f0']['candidate_ids'],[]);s=self.schema(p);self.assertEqual(len(s['properties']['fact_checks']['properties']['f0']['anyOf']),1);value=self.project(p);self.assertFalse(value['fact_checks'][0]['supported']);self.assertEqual(value['fact_checks'][0]['quote'],'');validate_regional_objections(value,self.article(),[{'fact_id':'f0'}])
 def test_no_evidence_and_no_article_objection_blocks_before_transport(self):
  p=self.prompt(facts=[{'fact_id':'f0','claim':'Observed 987654 units.'}],article={});client=Mock()
  with tempfile.TemporaryDirectory() as d,self.assertRaises(RegionalBlocked):request(client,Path(d),'regional-evidence-review',p,1)
  client.text.assert_not_called()
 def test_every_false_root_requires_its_own_nonnull_objection(self):
  p=self.prompt()
  for flag in c.FLAGS:
   for reason in ['missing',None]:
    raw=self.raw(p);raw[flag]={'value':False}
    if reason is None:raw[flag]['objection']=None
    with self.subTest(flag=flag,reason=reason),self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_every_unsupported_fact_requires_bound_objection(self):
  p=self.prompt();raw=self.raw(p);raw['fact_checks']['f0'].update(supported=False,evidence_quote_id=None)
  with self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_objection_flag_and_fact_cannot_borrow_another_decision(self):
  p=self.prompt(facts=self.facts()+[{'fact_id':'f1','claim':'Qualitative observation'}]);raw=self.raw(p);raw['fact_checks']['f0'].update(supported=False,objection=self.objection(p,'fact_supported','f1'))
  with self.assertRaises(RegionalBlocked):self.project(p,raw)
  raw=self.raw(p);raw['applicable']={'value':False,'objection':self.objection(p,'country_limits_retained')}
  with self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_positive_root_or_fact_cannot_carry_rejection(self):
  p=self.prompt()
  for mutate in [lambda r:r['applicable'].update(objection=self.objection(p)),lambda r:r['fact_checks']['f0'].update(objection=self.objection(p,'fact_supported'))]:
   raw=self.raw(p);mutate(raw)
   with self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_positive_cannot_select_null_or_numerically_ineligible_id(self):
  p=self.prompt();bad=next(q['id'] for q in p['quote_catalog']['source_passages'] if q['id'] not in p['evidence_selection']['facts']['f0']['candidate_ids'])
  for ref in [None,bad,'invented']:
   raw=self.raw(p);raw['fact_checks']['f0']['evidence_quote_id']=ref
   with self.subTest(ref=ref),self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_projection_preserves_all_explicit_flags_fact_ids_and_objections(self):
  p=self.prompt();raw=self.raw(p)
  for flag in c.FLAGS:raw[flag]={'value':False,'objection':self.objection(p,flag)}
  raw['fact_checks']['f0'].update(supported=False,evidence_quote_id=None,objection=self.objection(p,'fact_supported'));before=copy.deepcopy(raw);value=self.project(p,raw);self.assertEqual(raw,before);self.assertEqual(len(value['rejection_reasons']),4);self.assertTrue(all(value[f]is False for f in c.FLAGS));self.assertFalse(value['fact_checks'][0]['supported']);validate_regional_objections(value,self.article(),self.facts())
 def test_objections_keep_exact_article_text_and_model_reason(self):
  p=self.prompt();raw=self.raw(p);reason=self.objection(p);raw['applicable']={'value':False,'objection':reason};value=self.project(p,raw);r=value['rejection_reasons'][0];self.assertEqual(r['article_quote'],p['quote_catalog']['article_passages'][0]['text']);self.assertEqual(r['reason'],reason['reason']);self.assertEqual(r['fact_ids'],reason['fact_ids'])
 def test_source_id_or_fabricated_text_cannot_be_an_article_objection(self):
  p=self.prompt()
  for ref in [p['quote_catalog']['source_passages'][0]['id'],'invented']:
   raw=self.raw(p);reason=self.objection(p);reason['article_quote_id']=ref;raw['applicable']={'value':False,'objection':reason}
   with self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_projection_copies_literal_source_and_original_document_identity(self):
  p=self.prompt();raw=self.raw(p);value=self.project(p,raw);selected=next(q for q in p['quote_catalog']['source_passages'] if q['id']==raw['fact_checks']['f0']['evidence_quote_id']);self.assertEqual(value['fact_checks'][0]['quote'],selected['text']);self.assertEqual(value['fact_checks'][0]['document_id'],selected['document_id'])
 def test_wrong_types_extra_fields_missing_facts_and_legacy_shape_fail(self):
  p=self.prompt()
  mutations=[lambda r:r['applicable'].update(value=1),lambda r:r.update(applicable=False),lambda r:r.update(rejection_reasons=[]),lambda r:r['fact_checks'].pop('f0'),lambda r:r['fact_checks']['f0'].update(quote='Invented source quote'),lambda r:r['fact_checks']['f0'].update(supported=1)]
  for mutate in mutations:
   raw=self.raw(p);mutate(raw)
   with self.assertRaises(RegionalBlocked):self.project(p,raw)
 def test_empty_article_never_forces_approval_or_invents_negative_evidence(self):
  p=self.prompt(article={});client=Mock();self.assertTrue(p['evidence_selection']['facts']['f0']['candidate_ids']);self.assertEqual(p['quote_catalog']['article_passages'],[])
  with tempfile.TemporaryDirectory() as d,self.assertRaises(RegionalBlocked):request(client,Path(d),'regional-evidence-review',p,1)
  client.text.assert_not_called()
 def test_tampered_policy_fact_article_document_or_catalog_blocks_before_model(self):
  p=self.prompt()
  mutations=[lambda q:q['evidence_selection']['facts']['f0']['candidate_ids'].append('invented'),lambda q:q['evidence_selection'].update(facts_sha256='forged'),lambda q:q['approved_facts'][0].update(claim='Changed 999'),lambda q:q['documents'][0].update(text='Changed'),lambda q:q['article'].update(excerpt='Changed'),lambda q:q['quote_catalog']['source_passages'][0].update(text='Forged')]
  for mutate in mutations:
   q=copy.deepcopy(p);mutate(q);client=Mock()
   with tempfile.TemporaryDirectory() as d,self.assertRaises(RegionalBlocked):request(client,Path(d),'regional-evidence-review',q,1)
   client.text.assert_not_called()
 def test_original_article_fact_and_full_documents_preserved(self):
  p=self.prompt();self.assertEqual(p['article'],self.article());self.assertEqual(p['approved_facts'],self.facts());self.assertEqual([q['text'] for q in p['documents']],[q['text'] for q in self.docs()]);self.assertIn('Matching numbers NEVER proves',p['task'])
 def test_schema_is_strict_object_root_and_only_nested_anyof(self):
  p=self.prompt();s=self.schema(p);self.assertEqual(s['type'],'object');self.assertNotIn('anyOf',s)
  def check(node):
   if type(node)is not dict:return
   self.assertNotIn('if',node);self.assertNotIn('then',node)
   if node.get('type')=='object':self.assertEqual(set(node['required']),set(node['properties']));self.assertIs(node['additionalProperties'],False)
   for v in node.values():
    if type(v)is dict:check(v)
    elif type(v)is list:
     for q in v:check(q)
  check(s)
 def test_receipts_bind_new_policy_raw_projection_and_single_transport_budget(self):
  p=self.prompt();raw=self.raw(p);client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);first=request(client,root,'regional-evidence-review',p,1);self.assertEqual(first,request(client,root,'regional-evidence-review',p,1));self.assertEqual(client.text.call_count,1);receipt=load_json(root/'regional-evidence-review.receipt.json');self.assertEqual(receipt['response_adapter'],c.VERSION);self.assertEqual(receipt['quote_catalog_sha256'],digest(c.bound(p)));self.assertEqual(receipt['raw_sha256'],digest(raw));self.assertEqual(receipt['canonical_sha256'],digest(first));self.assertEqual(load_json(root/'regional-evidence-review.catalog.json'),c.bound(p));args=client.text.call_args.kwargs;self.assertEqual((args['attempts'],args['max_tokens'],args['timeout'],args['reject_duplicate_keys']),(1,14000,180,True))
 def test_invalid_received_negative_is_saved_not_repaired_or_replayed(self):
  p=self.prompt();raw=self.raw(p);raw['applicable']={'value':False,'objection':None};client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for _ in range(2):
    with self.assertRaises(RegionalBlocked):request(client,root,'regional-evidence-review',p,1)
   self.assertEqual(client.text.call_count,1);self.assertEqual(load_json(root/'regional-evidence-review.raw.json'),raw);self.assertNotIn('canonical_sha256',load_json(root/'regional-evidence-review.receipt.json'))
 def test_missing_or_tampered_policy_snapshot_stops_cache_without_call(self):
  for missing in [False,True]:
   p=self.prompt();client=Mock();client.text.return_value=self.raw(p)
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);request(client,root,'regional-evidence-review',p,1);snap=root/'regional-evidence-review.catalog.json'
    if missing:snap.unlink()
    else:
     value=load_json(snap);value['evidence_selection']['facts']['f0']['candidate_ids']=[];atomic_json(snap,value)
    with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',p,1)
    self.assertEqual(client.text.call_count,1)
 def test_unknown_request_stays_reserved_and_never_replays(self):
  p=self.prompt();client=Mock();client.text.side_effect=TimeoutError()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(TimeoutError):request(client,root,'regional-evidence-review',p,1)
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',p,1)
   self.assertEqual(client.text.call_count,1)
 def test_orphan_snapshot_never_overwritten(self):
  p=self.prompt();client=Mock()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);atomic_json(root/'regional-evidence-review.catalog.json',c.bound(p))
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',p,1)
   client.text.assert_not_called()
 def test_literal_candidate_membership_does_not_bypass_source_or_geographic_guards(self):
  p=self.prompt();value=self.project(p);value['fact_checks'][0]['source_kind']='news'
  with self.assertRaises(RegionalBlocked):validate_local_review(value,self.article(),{'approved_facts':self.facts()},self.docs(),'en-US')
  value=self.project(p);value['fact_checks'][0]['transfer_limits_retained']=False
  with self.assertRaises(RegionalBlocked):validate_local_review(value,self.article(),{'approved_facts':self.facts()},self.docs(),'tg-TJ')
 def test_error_diagnostics_are_static_and_redacted(self):
  from automation.agri_v2.failure_diagnostics import failure_details
  self.assertEqual(failure_details(RegionalBlocked('regional_catalog_consistency_invalid'))['category'],'regional_catalog_consistency_invalid')

 def test_native_model_transport_gets_strict_nested_schema_without_retry(self):
  from automation.agri_v2.client import ModelClient
  p=self.prompt();raw=self.raw(p)
  class Client(ModelClient):
   def __init__(self):self.seen=[]
   def request(self,kind,path,payload,timeout,attempts=None):
    self.seen.append((kind,path,payload,timeout,attempts));return {'choices':[{'message':{'content':json.dumps(raw)}}]}
  client=Client()
  with tempfile.TemporaryDirectory() as d:result=request(client,Path(d),'regional-evidence-review',p,1)
  self.assertEqual(result,self.project(p));self.assertEqual(len(client.seen),1);kind,path,payload,timeout,attempts=client.seen[0];self.assertEqual((kind,path,timeout,attempts),('text','/chat/completions',180,1));self.assertTrue(payload['response_format']['json_schema']['strict']);self.assertEqual(payload['response_format']['json_schema']['schema'],self.schema(p))
 def test_duplicate_json_key_still_blocks_before_projection_and_no_replay(self):
  from automation.agri_v2.client import ModelClient,ModelOutputError
  p=self.prompt();raw=self.raw(p);text=json.dumps(raw).replace('"regional_review_schema_version": 2','"regional_review_schema_version": 2, "regional_review_schema_version": 2')
  class Client(ModelClient):
   def __init__(self):self.calls=0
   def request(self,*args,**kwargs):
    self.calls+=1;return {'choices':[{'message':{'content':text}}]}
  client=Client()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(ModelOutputError):request(client,root,'regional-evidence-review',p,1)
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',p,1)
   self.assertEqual(client.calls,1)
