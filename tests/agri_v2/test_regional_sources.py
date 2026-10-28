import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_sources as r, source_registry as registry
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.pipeline import digest
from automation.agri_v2.research import source_host,ResearchBlocked
class RegionalSourcesTests(unittest.TestCase):
 def topic(self):return {'id':'agri-regional','title':'معیارهای آبیاری هویج','crop':'هویج','intent':'irrig_interval'}
 def doc(self,url='https://research.ac.ir/carrot'):
  text='Local technical evidence for carrot irrigation uses field soil moisture observations, exact crop growth stage and measured root-zone conditions; no universal irrigation interval is justified. '*5
  return {'url':url,'requested_url':url,'redirect_chain':[url],'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':utcnow(),'source_link_discovery_version':1}
 def brief(self):return {'sources':[{'url':'https://research.ac.ir/carrot'}],'approved_facts':[{'fact_id':'f0','claim':'تصمیم آبیاری با پایش رطوبت خاک انجام می‌شود.','conditions':'شرایط خاک و مرحله رشد باید مشخص شود.','kind':'qualitative'}], 'scoped_review':{'regional_research_version':r.VERSION,'regional_sources_prioritized':True,'international_transfer_limits_retained':True,'regional_source_gap':''}}
 def verdict(self,doc=None):
  doc=doc or self.doc();country,_=r.classification(__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(doc['url']).hostname)
  return {'applicable':True,'no_unsupported_local_prescription':True,'country_limits_retained':True,'fact_checks':[{'fact_id':'f0','supported':True,'document_id':'s0','quote':doc['text'][:190],'source_kind':'technical_publication','country':country,'scope':'Measured soil conditions and crop stage only; no universal climate or country prescription.','international_fallback':True,'local_evidence_gap':'Local official documents did not substantiate the required soil measurement method.','transfer_limits_retained':True}]}
 def data(self,p):
  d=p/'data';atomic_json(d/'regional-research-policy.json',r.POLICY);return d
 def test_profiles_are_geographic_not_legacy_locale_suffixes(self):
  self.assertEqual(r.profile('fa-IR')['countries'],['IR']);self.assertEqual(r.profile('tg-TJ')['countries'],['TJ']);self.assertEqual(r.profile('ru-RU')['countries'],['RU'])
  self.assertIn('EG',r.profile('ar-IQ')['countries']);self.assertIn('MA',r.profile('ar-IQ')['countries']);self.assertEqual(len(r.profile('ar-IQ')['countries']),22)
  self.assertIn('GB',r.profile('en-US')['countries']);self.assertIn('CA',r.profile('en-US')['countries']);self.assertNotIn('IR',r.profile('en-US')['countries'])
 def test_arabic_label_is_not_iraq_only(self):
  from automation.agri_v2.multilingual import LABELS,LANGUAGES
  self.assertIn('Arab countries',LABELS['ar-IQ']);self.assertIn('ar-IQ',LANGUAGES)
 def test_verified_official_hosts_are_admitted(self):
  for url in ['https://www.areeo.ac.ir/fa','https://research.ac.ir/x','https://agri.gov.ir/x','https://min.gov.tj/x','https://mcx.gov.ru/x','https://agri.gov.sa/x','https://agri.gov.eg/x','https://agriculture.govt.nz/x','https://agriculture.gc.ca/x']:
   self.assertTrue(source_host(url))
 def test_country_tld_is_not_official_approval(self):
  for url in ['https://commercial.ir/x','https://random.ru/x','https://random.tj/x','https://research.gov.ir.evil.org/x','https://evilgov.ir/x']:
   with self.assertRaises(ResearchBlocked):source_host(url)
 def test_ssrf_and_url_guards_still_apply(self):
  for url in ['http://agri.gov.ir/x','https://user:pass@agri.gov.ir/x','https://127.0.0.1/x','https://agri.gov.ir:8443/x','https://agri.gov.ir\\@evil.org/x']:
   with self.assertRaises(ResearchBlocked):source_host(url)
 def test_international_sources_are_fallback_not_local(self):
  self.assertFalse(r.accepted('https://extension.example.edu/field','fa-IR'));self.assertTrue(r.credible('https://extension.example.edu/field'))
  self.assertTrue(r.credible('https://www.fao.org/field'));self.assertFalse(r.accepted('https://min.gov.ir/x','tg-TJ'))
 def test_official_news_is_context_not_technical_evidence(self):
  self.assertTrue(r.accepted('https://www.irna.ir/news/x','fa-IR',technical=False));self.assertFalse(r.accepted('https://www.irna.ir/news/x','fa-IR'));self.assertFalse(r.credible('https://www.irna.ir/news/x'))
  self.assertTrue(r.accepted('https://khovar.tj/news/x','tg-TJ',technical=False));self.assertFalse(registry.university('khovar.tj'))
 def test_independent_institutions_are_not_all_collapsed_to_ac_ir(self):
  self.assertNotEqual(registry.institution('research.one.ac.ir'),registry.institution('research.two.ac.ir'));self.assertEqual(registry.institution('www.one.ac.ir'),registry.institution('library.one.ac.ir'))
 def test_regional_redirect_to_foreign_is_not_local_evidence(self):
  d=self.doc('https://one.edu/carrot');d.update(requested_url='https://agri.gov.ir/x',redirect_chain=['https://agri.gov.ir/x',d['url']]);self.assertEqual(r.documents_for([d],'fa-IR'),[]);self.assertEqual(r.documents_for([d],'fa-IR',allow_international=True),[d])
 def test_policy_is_exact_not_truthy_toggle(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.assertFalse(r.enabled(p));data=self.data(p);self.assertTrue(r.enabled(data));v=copy.deepcopy(r.POLICY);v['foreign_fallback']=True;atomic_json(data/'regional-research-policy.json',v)
   with self.assertRaises(r.RegionalBlocked):r.enabled(data)
 def test_brief_approval_is_not_silently_backfilled(self):
  with tempfile.TemporaryDirectory() as t:
   data=self.data(Path(t));b=self.brief()
   with self.assertRaises(r.RegionalBlocked):r.require_brief(b,data)
   b['regional_research']=r.bind_brief(b);r.require_brief(b,data);b['approved_facts'][0]['claim']='متن تغییر کرده'
   with self.assertRaises(r.RegionalBlocked):r.require_brief(b,data)
 def test_international_brief_requires_explicit_gap_and_independent_review(self):
  b=self.brief();b['sources'][0]['url']='https://extension.example.edu/x'
  with self.assertRaises(r.RegionalBlocked):r.bind_brief(b)
  b['scoped_review']['regional_source_gap']='Iranian technical documents did not cover the exact root-zone measurement method.';self.assertEqual(r.bind_brief(b)['profile']['language'],'fa-IR')
  b['scoped_review']['international_transfer_limits_retained']=False
  with self.assertRaises(r.RegionalBlocked):r.bind_brief(b)
 def test_local_review_requires_every_actual_fact(self):
  b=self.brief();d=self.doc();v=self.verdict(d);self.assertEqual(r.validate_local_review(v,{},b,[d],'fa-IR'),[d['url']]);v['fact_checks']=[]
  with self.assertRaises(r.RegionalBlocked):r.validate_local_review(v,{},b,[d],'fa-IR')
 def test_local_review_never_accepts_news_or_invented_quotes(self):
  for mutation in [('quote','Invented source quote with enough characters but not present in the supplied technical document.'),('source_kind','news'),('supported',False),('country','RU')]:
   v=self.verdict();v['fact_checks'][0][mutation[0]]=mutation[1]
   with self.assertRaises(r.RegionalBlocked):r.validate_local_review(v,{},self.brief(),[self.doc()],'fa-IR')
 def test_foreign_evidence_needs_transfer_limits_and_precise_local_gap(self):
  d=self.doc('https://extension.example.edu/field');v=self.verdict(d)
  self.assertEqual(r.validate_local_review(v,{},self.brief(),[d],'tg-TJ'),[d['url']])
  for k,value in [('international_fallback',False),('local_evidence_gap','weak'),('transfer_limits_retained',False)]:
   bad=copy.deepcopy(v);bad['fact_checks'][0][k]=value
   with self.assertRaises(r.RegionalBlocked):r.validate_local_review(bad,{},self.brief(),[d],'tg-TJ')
 def test_numbers_cannot_be_substituted_during_localization(self):
  b=self.brief();b['approved_facts'][0].update(claim='آستانه 25 میلی‌متر است.',kind='source_observation')
  with self.assertRaises(r.RegionalBlocked):r.validate_local_review(self.verdict(),{},b,[self.doc()],'fa-IR')
 def test_negative_and_missing_flags_are_not_approval(self):
  for k in ('applicable','country_limits_retained','no_unsupported_local_prescription'):
   v=self.verdict();v.pop(k)
   with self.assertRaises(r.RegionalBlocked):r.validate_local_review(v,{},self.brief(),[self.doc()],'fa-IR')
 def test_search_fetch_is_bounded_region_filtered_and_persisted(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);client=SimpleNamespace(env={'AFP_SOURCE_SEARCH_API_KEY':'fixture-only','AFP_PARALLEL_POOL_DB':'fixture-only'})
   docs=[self.doc('https://one.ac.ir/carrot'),self.doc('https://other.edu/carrot')]
   fn=Mock(return_value={'results':[{'url':d['url'],'title':'Carrot technical guide','description':'Discovery only'} for d in docs]});fetch=Mock(side_effect=lambda url:next(d for d in docs if d['url']==url))
   for _ in range(2):loaded=r.collect(self.topic(),'fa-IR',client,root/'out',root/'family',fetcher=fetch,search_fn=fn)
   self.assertEqual([d['url'] for d in loaded],[docs[0]['url']]);self.assertEqual(fn.call_count,2);self.assertEqual(fetch.call_count,1)
   self.assertTrue((root/'family/regional-research/fa-IR/local/search-plan.json').exists())
 def test_sufficient_local_review_does_not_search_international(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=self.data(root);d=self.doc('https://mcx.gov.ru/x');client=Mock();client.text.return_value=self.verdict(d)
   with patch.object(r,'collect',return_value=[d]) as collect:r.local_research(self.topic(),{},self.brief(),'ru-RU',client,data,root,root/'family',root/'attempt',4)
   self.assertEqual(collect.call_count,1);self.assertEqual(client.text.call_count,1)
 def test_weak_local_evidence_triggers_international_then_scientific_review(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=self.data(root);local=self.doc('https://mcx.gov.ru/x');foreign=self.doc('https://extension.example.edu/field');client=Mock();client.text.side_effect=[{'applicable':False},self.verdict(foreign)]
   with patch.object(r,'collect',side_effect=[[local],[foreign]]) as collect:
    # fallback is s1 in the merged documents, not s0 from an old pack
    client.text.side_effect=[{'applicable':False},dict(self.verdict(foreign),fact_checks=[dict(self.verdict(foreign)['fact_checks'][0],document_id='s1')])]
    urls=r.local_research(self.topic(),{},self.brief(),'ru-RU',client,data,root,root/'family',root/'attempt',4)
   self.assertEqual(urls,[foreign['url']]);self.assertEqual(collect.call_count,2);self.assertTrue(collect.call_args.kwargs['international']);self.assertEqual(client.text.call_count,2)
   client.text.reset_mock();r.require_local({},self.brief(),'ru-RU',data,root/'family');client.text.assert_not_called()
 def test_no_local_documents_still_allow_credible_international_completion(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=self.data(root);d=self.doc('https://extension.example.edu/field');client=Mock();client.text.return_value=self.verdict(d)
   with patch.object(r,'collect',side_effect=[[],[d]]):self.assertEqual(r.local_research(self.topic(),{},self.brief(),'tg-TJ',client,data,root,root/'family',root/'attempt',4),[d['url']])
   self.assertEqual(client.text.call_count,1)
 def test_unavailable_all_sources_never_create_approval(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=self.data(root);client=Mock()
   with patch.object(r,'collect',return_value=[]),self.assertRaises(r.RegionalBlocked):r.local_research(self.topic(),{},self.brief(),'tg-TJ',client,data,root,root/'family',root/'attempt',4)
   client.text.assert_not_called();self.assertFalse((root/'family/regional-research/tg-TJ/approved.json').exists())
 def test_local_proof_binds_article_brief_and_literal_fetched_text(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=self.data(root);folder=root/'family';d=self.doc('https://mcx.gov.ru/x');client=Mock();client.text.return_value=self.verdict(d);b=self.brief();a={'title':'source'}
   with patch.object(r,'collect',return_value=[d]):r.local_research(self.topic(),a,b,'ru-RU',client,data,root,folder,root/'attempt',4)
   with self.assertRaises(r.RegionalBlocked):r.require_local({'title':'changed'},b,'ru-RU',data,folder)
   p=folder/'regional-research/ru-RU/approved.json';v=load_json(p);v['documents'][0]['text']+='tampered';atomic_json(p,v)
   with self.assertRaises(r.RegionalBlocked):r.require_local(a,b,'ru-RU',data,folder)
 def test_footer_contains_local_references_only_at_end(self):
  from test_multilingual import article,response
  from automation.agri_v2.multilingual import localized_body,render_translation
  from automation.agri_v2.editorial_presentation import verify_sources
  a=article();row=render_translation(a,response(a,'en-US'),'en-US');url='https://agriculture.gov.au/carrot';body=localized_body(row,[{'url':'https://navar-abyari.ir/img.webp'}],{'en-US':[]},regional_sources=[url]);self.assertIn(url,body);self.assertIn(url,verify_sources(body,[{'url':url}]+[{'url':u} for u,t in __import__('automation.agri_v2.internal_links',fromlist=['anchors']).anchors(row['content_html'])],'en-US'))
 def test_legacy_approved_language_is_due_for_regional_research_without_reset(self):
  from automation.agri_v2 import language_review_queue as q
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=self.data(root);folder=root/'family';atomic_json(folder/'article.json',{});atomic_json(data/'briefs/x.json',self.brief());row={'status':'approved','language':'ru-RU','topic_id':'x','attempts':2,'model_calls_spent':5}
   self.assertTrue(q.regional_due(row,folder,data));self.assertEqual(row['attempts'],2);self.assertFalse(q.regional_ready(row,folder,data));atomic_json(folder/'translations/ru-RU.wordpress.json',{'public_verified':True});self.assertFalse(q.regional_due(row,folder,data))
 def test_uncertain_regional_request_is_never_replayed_as_legacy_linguistic_success(self):
  from test_language_review_queue import LanguageReviewQueueTests
  from test_multilingual import response
  from automation.agri_v2 import language_review_queue as q,multilingual as m
  with tempfile.TemporaryDirectory() as t:
   data,out,folder,a,topic=LanguageReviewQueueTests().setup(t);atomic_json(data/'regional-research-policy.json',r.POLICY);lang='ru-RU';raw=response(a,lang);rendered=m.render_translation(a,raw,lang);atomic_json(q.target(folder,lang),rendered);atomic_json(q.target(folder,lang).with_suffix('.raw.json'),raw);atomic_json(q.proof_path(folder,lang),{'article_sha256':digest(a),'translation_sha256':digest(rendered),'review':{'faithful':True,'issues':[]}})
   state=q.ensure(topic,a,folder,lang);state.update(status='reserved',attempts=1,next_attempt_at=utcnow(),history=[{'max_calls':4}]);atomic_json(q.path(folder,lang),state);client=Mock();result=q.run_item(q.path(folder,lang),client,data)
   self.assertEqual(result['status'],'reconciliation_required');client.text.assert_not_called();self.assertEqual(load_json(q.path(folder,lang))['model_calls_spent'],4)
 def test_production_wordpress_blocks_old_brief_before_any_remote_mutation(self):
  from automation.agri_v2.wordpress import WordPress
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);data=self.data(root);wp=WordPress({'AFP_WP_BASE_URL':'https://navar-abyari.ir','AFP_WP_USERNAME':'fixture','AFP_WP_APP_PASSWORD':'fixture'},data=data);wp.call=Mock();wp.preflight=Mock()
   with self.assertRaises(r.RegionalBlocked):wp.publish(root/'family',{'id':'x'},dict(self.brief(),publish_authorized=True),True)
   wp.call.assert_not_called();wp.preflight.assert_not_called()
 def test_worker_regional_source_stage_is_search_only_with_shared_credentials(self):
  from test_family_lifecycle import FamilyLifecycleTests
  from automation.agri_v2 import family_lifecycle as f
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health=FamilyLifecycleTests().setup(t);atomic_json(data/'regional-research-policy.json',r.POLICY);env.update(AFP_SOURCE_SEARCH_API_KEY='fixture-only',AFP_PARALLEL_POOL_DB='fixture-only');factory=Mock()
   def run(topic,stage,client,*_):
    self.assertEqual(stage,'research_sources');self.assertEqual(client.source_search_env['AFP_PARALLEL_POOL_DB'],'fixture-only');return {'fetched_sources':1}
   with patch.object(f,'next_stage',side_effect=[('research_sources',None),('blocked','test_finished')]),patch.object(f,'run_stage',side_effect=run):result=f.worker(topic,health,data,out,env,factory)
   factory.assert_not_called();self.assertEqual(result['status'],'blocked')
 def test_missing_search_secret_defers_before_any_stage_attempt(self):
  from test_family_lifecycle import FamilyLifecycleTests
  from automation.agri_v2 import family_lifecycle as f
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health=FamilyLifecycleTests().setup(t);atomic_json(data/'regional-research-policy.json',r.POLICY)
   with patch.object(f,'next_stage',return_value=('research_sources',None)),patch.object(f,'attempt') as attempt:
    result=f.worker(topic,health,data,out,env,Mock())
   self.assertEqual(result['status'],'capability_required');attempt.assert_not_called()
 def test_new_and_historical_route_contracts_are_separate(self):
  from automation.agri_v2.research_routes import plan
  old=plan(self.topic());new=plan(dict(self.topic(),regional_research_enabled=True));self.assertNotIn('regional_profile',old);self.assertEqual(new['regional_profile']['language'],'fa-IR');self.assertIn('ایران',new['search_queries'][0]);self.assertIn('university extension',old['search_queries'][0])
