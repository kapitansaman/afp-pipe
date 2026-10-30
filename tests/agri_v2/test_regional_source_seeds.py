import copy,hashlib,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_sources as r,regional_source_seeds as seeds
from automation.agri_v2.queue import load_json,atomic_json,utcnow
from automation.agri_v2.pipeline import digest

class SourceSeedTests(unittest.TestCase):
 def topic(self):return {'id':'fixture','title':'Fixture measurement criteria','crop':'هویج','intent':'irrig_interval'}
 def doc(self,url,text=None):
  text=text or 'Actual technical context on crop soil and irrigation decisions, without any universal local rate. '*12
  return {'url':url,'requested_url':url,'redirect_chain':[url],'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':utcnow(),'source_link_discovery_version':1}
 def brief(self):return {'sources':[{'url':'https://extension.example.edu/first'},{'url':'https://extension.example.edu/missing'}],'approved_facts':[{'fact_id':'f0','claim':'Qualitative field criteria','source_url':'https://extension.example.edu/first'},{'fact_id':'f1','claim':'A bounded observation of 76543 mm','source_url':'https://extension.example.edu/missing'}]}
 def client(self):return SimpleNamespace(env={'AFP_SOURCE_SEARCH_API_KEY':'fixture-only','AFP_PARALLEL_POOL_DB':'fixture-only'})
 def search(self,urls):return Mock(return_value={'results':[{'url':u,'title':'Technical crop evidence','description':'Discovery only, not approval'} for u in urls]})
 def test_original_fact_sources_with_numeric_gaps_are_ranked_first(self):
  b=self.brief();before=copy.deepcopy(b);self.assertEqual(seeds.ordered(b,[self.doc('https://mcx.gov.ru/local')]),[b['sources'][1]['url'],b['sources'][0]['url']]);self.assertEqual(b,before)
 def test_already_present_numbers_do_not_claim_semantic_support(self):
  b=self.brief();docs=[self.doc('https://mcx.gov.ru/local','Unrelated crop trial of 76543 units. '*30)];self.assertEqual(seeds.ordered(b,docs),[s['url'] for s in b['sources']])
 def test_only_fact_bound_declared_sources_are_used_not_all_links(self):
  b=self.brief();b['sources'].append({'url':'https://extension.example.edu/unrelated'});self.assertEqual(len(seeds.ordered(b,[])),2)
 def test_no_source_url_is_not_fabricated_for_model_knowledge(self):
  b=self.brief();b['approved_facts']=[{'fact_id':'f0','kind':'qualitative','claim':'Observe actual field conditions.'}];self.assertEqual(seeds.ordered(b,[]),[])
 def test_undeclared_commercial_or_unsafe_source_lead_fails_closed(self):
  for url in ['https://extension.example.edu/undeclared','https://commercial.example.com/a','https://127.0.0.1/a']:
   b=self.brief();b['approved_facts'][0]['source_url']=url
   if 'undeclared' not in url:b['sources'].append({'url':url})
   with self.assertRaises(r.RegionalBlocked):seeds.ordered(b,[])
 def test_more_than_six_required_leads_does_not_silently_truncate_or_expand_budget(self):
  urls=['https://extension.example.edu/'+str(i) for i in range(7)];b={'sources':[{'url':u} for u in urls],'approved_facts':[{'fact_id':str(i),'claim':'qualitative','source_url':u} for i,u in enumerate(urls)]}
  with self.assertRaises(r.RegionalBlocked):seeds.ordered(b,[])
 def test_seeded_fallback_uses_only_original_urls_and_no_search_or_planner(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);leads=seeds.ordered(self.brief(),[]);found=['https://extension.example.edu/discovered-'+str(i) for i in range(6)];search=self.search(found);fetch=Mock(side_effect=lambda u:self.doc(u))
   docs=r.collect(self.topic(),'ru-RU',self.client(),root/'out',root/'folder',fetcher=fetch,search_fn=search,international=True,source_seeds=leads)
   self.assertEqual([d['url'] for d in docs][:2],leads);self.assertEqual(fetch.call_count,len(leads));search.assert_not_called();self.assertEqual(len(docs),len(leads));saved=load_json(root/'folder/regional-research/ru-RU/international/documents.json');self.assertIs(saved['scientific_acceptance'],False);self.assertIs(saved['publication_authorized'],False)
 def test_fresh_valid_cache_reused_but_stale_original_text_is_refetched(self):
  for stale in [False,True]:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);lead=self.brief()['sources'][0]['url'];doc=self.doc(lead);doc['fetched_at']='2020-01-01T00:00:00Z' if stale else utcnow();atomic_json(root/'out/source-cache'/(hashlib.sha256(lead.encode()).hexdigest()+'.json'),doc);fetch=Mock(return_value=self.doc(lead));search=self.search([])
    docs=r.collect(self.topic(),'ar-IQ',self.client(),root/'out',root/'folder',fetcher=fetch,search_fn=search,international=True,source_seeds=[lead]);self.assertEqual(fetch.call_count,int(stale));self.assertEqual(len(docs),1)
 def test_changed_seed_binding_does_not_overwrite_or_reuse_historical_search_plan(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);work=root/'folder/regional-research/ru-RU/international';p=work/'search-plan.json';atomic_json(p,{'contract_sha256':'old-contract','queries':['Original first query','Original second query']});before=p.read_bytes();fetch=Mock();search=Mock()
   with self.assertRaises(r.RegionalBlocked):r.collect(self.topic(),'ru-RU',self.client(),root/'out',root/'folder',fetcher=fetch,search_fn=search,international=True,source_seeds=[self.brief()['sources'][0]['url']])
   self.assertEqual(p.read_bytes(),before);fetch.assert_not_called();search.assert_not_called()
 def test_seeds_for_local_phase_duplicates_and_untrusted_hosts_block_before_search(self):
  good=self.brief()['sources'][0]['url']
  for leads,international in [([good],False),([good,good],True),(['https://commercial.example.com/a'],True),([None],True),('not-a-list',True)]:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);fetch=Mock();search=Mock()
    with self.assertRaises(r.RegionalBlocked):r.collect(self.topic(),'ru-RU',self.client(),root/'out',root/'folder',fetcher=fetch,search_fn=search,international=international,source_seeds=leads)
    fetch.assert_not_called();search.assert_not_called()
 def test_redirect_outside_credible_hosts_cannot_admit_seeded_document(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);lead=self.brief()['sources'][0]['url'];doc=self.doc('https://commercial.example.com/end');doc.update(requested_url=lead,redirect_chain=[lead,doc['url']]);fetch=Mock(return_value=doc)
   self.assertEqual(r.collect(self.topic(),'ru-RU',self.client(),root/'out',root/'folder',fetcher=fetch,search_fn=self.search([]),international=True,source_seeds=[lead]),[])
 def test_static_redacted_diagnostics(self):
  from automation.agri_v2.failure_diagnostics import failure_details
  for code in ('regional_declared_source_binding_invalid','regional_declared_source_fetch_cap','regional_source_seed_contract_invalid'):self.assertEqual(failure_details(r.RegionalBlocked(code))['category'],code)

 def test_missing_seeded_source_does_not_trigger_extra_discovery_or_fetch_round(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);urls=seeds.ordered(self.brief(),[]);fetch=Mock(side_effect=TimeoutError());search=Mock()
   result=r.collect(self.topic(),'ar-IQ',SimpleNamespace(env={}),root/'out',root/'folder',fetcher=fetch,search_fn=search,international=True,source_seeds=urls)
   self.assertEqual(result,[]);self.assertEqual(fetch.call_count,len(urls));search.assert_not_called()
 def test_six_seeded_urls_are_the_existing_upper_fetch_limit(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);urls=['https://extension.example.edu/'+str(i) for i in range(6)];fetch=Mock(side_effect=lambda u:self.doc(u));search=Mock()
   docs=r.collect(self.topic(),'ar-IQ',SimpleNamespace(env={}),root/'out',root/'folder',fetcher=fetch,search_fn=search,international=True,source_seeds=urls)
   self.assertEqual(len(docs),6);self.assertEqual(fetch.call_count,6);search.assert_not_called()
 def test_local_first_negative_passes_only_declared_claim_urls_to_fallback(self):
  import test_regional_sources as fixtures
  f=fixtures.RegionalSourcesTests()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=f.data(root);local=f.doc('https://mcx.gov.ru/x');foreign=f.doc('https://extension.example.edu/field');article=f.article();brief=f.brief();brief['sources']=[{'url':foreign['url']}];brief['approved_facts'][0]['source_url']=foreign['url'];client=Mock()
   final=dict(f.current_verdict(foreign),fact_checks=[dict(f.current_verdict(foreign)['fact_checks'][0],document_id='s1')])
   client.text.side_effect=[f.wire_negative(local,quote='Fixture bounded observation',article=article),f.wire_verdict(foreign,canonical=final,article=article,docs=[local,foreign])]
   with patch.object(r,'collect',side_effect=[[local],[foreign]]) as collect:
    result=r.local_research(f.topic(),article,brief,'ru-RU',client,data,root,root/'family',root/'attempt',4)
   self.assertEqual(result,[foreign['url']]);self.assertNotIn('source_seeds',collect.call_args_list[0].kwargs);self.assertEqual(collect.call_args_list[1].kwargs,{'international':True,'source_seeds':[foreign['url']]});self.assertEqual(client.text.call_count,2)
 def test_seeded_contract_cannot_inject_search_queries_through_saved_plan(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);url=self.brief()['sources'][0]['url'];contract={'international_fallback':True,'policy':r.profile('ru-RU'),'topic':{k:self.topic()[k] for k in ('id','title','crop','intent')},'source_seed_urls':[url]};p=root/'folder/regional-research/ru-RU/international/search-plan.json';atomic_json(p,{'contract_sha256':digest(contract),'queries':['Unexpected first query','Unexpected second query']});search=Mock();fetch=Mock()
   with self.assertRaises(r.RegionalBlocked):r.collect(self.topic(),'ru-RU',SimpleNamespace(env={}),root/'out',root/'folder',fetcher=fetch,search_fn=search,international=True,source_seeds=[url])
   search.assert_not_called();fetch.assert_not_called()
