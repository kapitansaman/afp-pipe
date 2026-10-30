import copy,json,tempfile,unittest,hashlib,re
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import regional_quote_catalog as c
from automation.agri_v2.regional_sources import review_prompt,response_schema,RegionalBlocked,validate_local_review
from automation.agri_v2.translation_review_repair import request,RepairBlocked
from automation.agri_v2.queue import load_json,atomic_json
from automation.agri_v2.pipeline import digest
from automation.agri_v2.quality_index import article_text
from automation.agri_v2.claim_policy import PolicyBlocked

class QuoteCatalogTests(unittest.TestCase):
 def article(self):return {'content_html':'<p>مشاهدهٔ آزمایشی، نه توصیهٔ محلی.</p>','excerpt':'Current excerpt observation.','faq':[{'question':'Which conditions matter?','answer':'Measured soil and crop conditions matter.'}]}
 def docs(self):
  text='Actual measured soil and crop conditions must be stated; no universal local irrigation rule follows. '*15
  return [{'url':'https://extension.example.edu/a','text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}]
 def prompt(self):return review_prompt(self.article(),{'approved_facts':[{'fact_id':'f0','claim':'Qualitative fixture.'}]},'en-US',self.docs(),wire=c.VERSION)
 def raw(self,p=None,negative=False):
  p=p or self.prompt();cat=p['quote_catalog'];row={'supported':True,'evidence_quote_id':cat['source_passages'][0]['id'],'source_kind':'extension_guidance','country':'US','scope':'Measured soil and crop conditions only, not universal recommendations.','international_fallback':True,'local_evidence_gap':'Local evidence does not cover this exact bounded observation.','transfer_limits_retained':True}
  reasons=[{'flag':'applicable','fact_ids':['f0'],'claim_type':'source_observation','article_quote_id':cat['article_passages'][0]['id'],'reason':'Fixture objection requires independent scientific assessment.'}] if negative else []
  return {'regional_review_schema_version':2,'applicable':not negative,'no_unsupported_local_prescription':True,'country_limits_retained':True,'fact_checks':{'f0':row},'rejection_reasons':reasons}
 def test_every_passage_has_exact_offsets_and_original_language(self):
  p=self.prompt();cat=c.bound(p);docs={d['id']:d for d in p['documents']}
  for passage in cat['source_passages']:
   self.assertEqual(passage['text'],docs[passage['document_id']]['text'][passage['start']:passage['end']]);self.assertTrue(80<=len(passage['text'])<=1000)
  self.assertTrue(any('مشاهده' in q['text'] for q in cat['article_passages']))
  for passage in cat['article_passages']:self.assertIn(passage['text'],article_text(self.article()));self.assertTrue(8<=len(passage['text'])<=600)
 def test_overlapping_windows_cover_all_nonwhitespace_without_losing_tail(self):
  for text in [' '*10+'x'*990+'Z','x'*1000+'Z','x'*1300+' '*20,'x'*70,'x'*80,'x'*2100+' '*20+'Z',('αβγ\n'*400)]:
   rows=c.spans(text,1000,300,80)
   if len(text.strip())<80:self.assertEqual(rows,[]);continue
   covered=set(i for start,end,_ in rows for i in range(start,end));self.assertTrue(all(i in covered for i,v in enumerate(text) if not v.isspace()))
   for start,end,quote in rows:self.assertEqual(quote,text[start:end]);self.assertTrue(80<=len(quote)<=1000)
 def test_catalog_includes_excerpt_and_each_faq_component_not_brief(self):
  cat=self.prompt()['quote_catalog'];fields={p['field'] for p in cat['article_passages']};self.assertTrue({'content_html_visible','excerpt','faq.0.question','faq.0.answer'}<=fields)
 def test_schema_exposes_ids_not_model_written_quote_or_document_id(self):
  p=self.prompt();s=response_schema('regional-evidence-review',p);props=s['properties']['fact_checks']['properties']['f0']['properties'];self.assertNotIn('quote',props);self.assertNotIn('document_id',props);self.assertEqual(props['evidence_quote_id']['enum'],[x['id'] for x in p['quote_catalog']['source_passages']]+[None]);reason=s['properties']['rejection_reasons']['items']['properties'];self.assertNotIn('article_quote',reason);self.assertIn('article_quote_id',reason)
 def test_projection_uses_exact_selected_source_and_article_quotes(self):
  p=self.prompt();raw=self.raw(p,negative=True);before=copy.deepcopy(raw);result=c.canonical(raw,response_schema('regional-evidence-review',p),c.bound(p));self.assertEqual(raw,before);self.assertFalse(result['applicable']);self.assertEqual(result['fact_checks'][0]['quote'],p['quote_catalog']['source_passages'][0]['text']);self.assertEqual(result['fact_checks'][0]['document_id'],'s0');self.assertEqual(result['rejection_reasons'][0]['article_quote'],p['quote_catalog']['article_passages'][0]['text'])
 def test_wrong_source_id_unknown_article_id_and_free_quote_rejected(self):
  p=self.prompt();s=response_schema('regional-evidence-review',p)
  for mutate in [lambda r:r['fact_checks']['f0'].update(evidence_quote_id='invented'),lambda r:r['fact_checks']['f0'].update(evidence_quote_id=p['quote_catalog']['article_passages'][0]['id']),lambda r:r['fact_checks']['f0'].update(quote='Invented quote'),lambda r:r['rejection_reasons'][0].update(article_quote_id='invented')]:
   raw=self.raw(p,negative=True);mutate(raw)
   with self.assertRaises(RegionalBlocked):c.canonical(raw,s,c.bound(p))
 def test_supported_fact_cannot_select_null_and_unsupported_null_is_not_approval(self):
  p=self.prompt();raw=self.raw(p);raw['fact_checks']['f0']['evidence_quote_id']=None;s=response_schema('regional-evidence-review',p)
  with self.assertRaises(RegionalBlocked):c.canonical(raw,s,c.bound(p))
  raw['fact_checks']['f0']['supported']=False;raw['applicable']=False;result=c.canonical(raw,s,c.bound(p));self.assertFalse(result['fact_checks'][0]['supported']);self.assertEqual(result['fact_checks'][0]['quote'],'');self.assertIsNone(result['fact_checks'][0]['document_id'])
  with self.assertRaises(PolicyBlocked):validate_local_review(result,self.article(),{'approved_facts':[{'fact_id':'f0'}]},self.docs(),'en-US')
 def test_catalog_tampering_or_changed_source_article_stops_before_model(self):
  p=self.prompt()
  for mutate in [lambda q:q['quote_catalog']['source_passages'][0].update(text='Invented'),lambda q:q['quote_catalog']['source_passages'][0].update(document_id='s9'),lambda q:q['documents'][0].update(text='Changed source'),lambda q:q['article'].update(excerpt='Changed article'),lambda q:q['quote_catalog']['article_passages'][0].update(start=999)]:
   bad=copy.deepcopy(p);mutate(bad);client=Mock()
   with tempfile.TemporaryDirectory() as d,self.assertRaises(RegionalBlocked):request(client,Path(d),'regional-evidence-review',bad,1)
   client.text.assert_not_called()
 def test_receipt_snapshot_raw_and_canonical_are_bound_and_never_replayed(self):
  p=self.prompt();raw=self.raw(p);client=Mock();client.text.return_value=raw
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);first=request(client,root,'regional-evidence-review',p,1);second=request(client,root,'regional-evidence-review',p,1);self.assertEqual(first,second);self.assertEqual(client.text.call_count,1);self.assertEqual(load_json(root/'regional-evidence-review.raw.json'),raw);receipt=load_json(root/'regional-evidence-review.receipt.json');self.assertEqual(receipt['response_adapter'],c.VERSION);self.assertEqual(receipt['quote_catalog_sha256'],digest(p['quote_catalog']));self.assertEqual(load_json(root/'regional-evidence-review.catalog.json'),p['quote_catalog']);self.assertEqual(receipt['canonical_sha256'],digest(first));self.assertEqual(client.text.call_args.kwargs['attempts'],1);self.assertTrue(client.text.call_args.kwargs['reject_duplicate_keys']);self.assertEqual(client.text.call_args.kwargs['max_tokens'],14000)
 def test_missing_or_tampered_snapshot_blocks_cached_response_without_calls(self):
  for missing in [True,False]:
   p=self.prompt();client=Mock();client.text.return_value=self.raw(p)
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);request(client,root,'regional-evidence-review',p,1);snapshot=root/'regional-evidence-review.catalog.json'
    if missing:snapshot.unlink()
    else:atomic_json(snapshot,{'forged':True})
    with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',p,1)
    self.assertEqual(client.text.call_count,1)
 def test_orphan_catalog_is_not_overwritten_or_used_as_authority(self):
  p=self.prompt();client=Mock()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);atomic_json(root/'regional-evidence-review.catalog.json',p['quote_catalog'])
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',p,1)
   client.text.assert_not_called()
 def test_unknown_stays_reserved_and_does_not_consume_another_call(self):
  p=self.prompt();client=Mock();client.text.side_effect=TimeoutError()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with self.assertRaises(TimeoutError):request(client,root,'regional-evidence-review',p,1)
   with self.assertRaises(RepairBlocked):request(client,root,'regional-evidence-review',p,1)
   self.assertEqual(client.text.call_count,1);self.assertTrue((root/'regional-evidence-review.catalog.json').exists())
 def test_source_identity_is_derived_from_selected_passage_not_another_document(self):
  p=self.prompt();other=dict(self.docs()[0],url='https://extension.other.edu/b',text='Different actual source passage with all conditions clearly stated. '*20);p=review_prompt(self.article(),{'approved_facts':[{'fact_id':'f0'}]},'en-US',[self.docs()[0],other],wire=c.VERSION);raw=self.raw(p);selected=next(x for x in p['quote_catalog']['source_passages'] if x['document_id']=='s1');raw['fact_checks']['f0']['evidence_quote_id']=selected['id'];result=c.canonical(raw,response_schema('regional-evidence-review',p),c.bound(p));self.assertEqual(result['fact_checks'][0]['document_id'],'s1');self.assertEqual(result['fact_checks'][0]['quote'],selected['text'])
 def test_positive_literal_membership_does_not_bypass_numeric_or_geographic_guards(self):
  p=self.prompt();value=c.canonical(self.raw(p),response_schema('regional-evidence-review',p),c.bound(p));brief={'approved_facts':[{'fact_id':'f0','claim':'Threshold 987654 mm','kind':'source_observation'}]}
  with self.assertRaises(RegionalBlocked):validate_local_review(value,self.article(),brief,self.docs(),'en-US')
  value['fact_checks'][0]['transfer_limits_retained']=False
  with self.assertRaises(RegionalBlocked):validate_local_review(value,self.article(),{'approved_facts':[{'fact_id':'f0','claim':'General fixture'}]},self.docs(),'tg-TJ')
 def test_empty_article_catalog_cannot_manufacture_a_bound_objection(self):
  p=review_prompt({}, {'approved_facts':[{'fact_id':'f0'}]},'en-US',self.docs(),wire=c.VERSION);s=response_schema('regional-evidence-review',p);self.assertEqual(s['properties']['rejection_reasons']['maxItems'],0);self.assertEqual(p['quote_catalog']['article_passages'],[])
 def test_full_article_and_sources_are_not_removed_or_rewritten_in_prompt(self):
  p=self.prompt();self.assertEqual(p['article'],self.article());self.assertEqual(p['documents'][0]['text'],self.docs()[0]['text']);self.assertIn('Membership proves literal origin only',p['task'])
 def test_too_large_catalog_is_rejected_not_silently_truncated(self):
  docs=[dict(id='s0',text='x'*450000)]
  with self.assertRaises(RegionalBlocked):c.build(self.article(),docs)
