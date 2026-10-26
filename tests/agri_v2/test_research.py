import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import research,cycle
from automation.agri_v2.queue import atomic_json,load_json,utcnow

TOPIC={'id':'agri-123456789abc','title':'نشانه‌های رسیدگی لوبیا','crop':'لوبیا','intent':'maturity','priority':'P1','origin':'NEW','overlap_review_required':False,'related_existing_ids':[]}
QUOTE='Harvest mature beans before pods begin to shatter in the field or the pods will split open, spilling beans onto the ground.'
CLAIM='پیش از بازشدن غلاف و ریختن دانه باید وضعیت رسیدگی محصول در مزرعه بررسی شود.'
COND='محدود به لوبیای خشک در شرایط منبع؛ تاریخ تقویمی یا نسخه عددی برای ایران تعیین نشده است.'
SCOUT={'document_ids':['s0','s1'],'crop_and_intent_match':True,'scope_limitations':'Qualitative common bean maturity only; no local numerical recommendations.','reason':'Two independently fetched university pages cover dry-bean maturity and harvest. معرفت'}
def fixtures():
 docs=[{'url':'https://extension.msu.edu/beans','text':'Document '*45+QUOTE+' end','fetched_at':utcnow(),'sha256':'a'*64},{'url':'https://extension.iastate.edu/beans','text':'Document '*45+QUOTE+' end','fetched_at':utcnow(),'sha256':'b'*64}]
 for d in docs:d['sha256']=hashlib.sha256(d['text'].encode()).hexdigest()
 candidate={'topic_id':TOPIC['id'],'slug':'bean-maturity-check','answers_intent':True,'local_or_numeric_prescription_required':False,'outline':['رسیدگی','پایش','بازار'],'facts':[{'claim':CLAIM,'conditions':COND,'source_url':docs[i%2]['url'],'evidence_quote':QUOTE,'evidence_id':f'd{i%2}-e0'} for i in range(4)]}
 review={'grounded':True,'all_claims_supported':True,'crop_and_intent_match':True,'safe_qualitative':True,'overlap_decision':'distinct','novelty_reason':'این بررسی درباره نشانه رسیدگی است و با موضوع عملکرد در هکتار یکی نیست.','source_scope_limitations':'این منابع خارجی هستند و تقویم یا دستور محلی برای تمام مناطق ایران ارائه نمی‌کنند.'}
 inventory={'source_generated_at':utcnow(),'scope':'all published titles','records':[{'id':1,'title':'موضوع دیگر','url':'https://navar-abyari.ir/other/','status':'publish'}]}
 return docs,candidate,review,inventory
class ResearchTests(unittest.TestCase):
 def test_verified_quotes_build_explicit_ai_not_human_brief(self):
  d,c,r,i=fixtures();b=research.build_brief(TOPIC,d,c,r,i)
  self.assertTrue(b['publish_authorized']);self.assertFalse(b['human_agronomy_review_done']);self.assertIsNone(b['agronomy_reviewer']);self.assertEqual(b['review_mode'],research.MODE)
 def test_invented_quote_rejected(self):
  d,c,r,i=fixtures();c['facts'][0]['evidence_quote']='fabricated quote '*12
  with self.assertRaisesRegex(research.ResearchBlocked,'quote_not'):research.validate_evidence(TOPIC,c,d)
 def test_evidence_id_resolves_to_original_text_not_model_quote(self):
  d,c,r,i=fixtures();c['facts'][0]['evidence_quote']='invented model paraphrase'
  resolved=research.resolve_evidence(c,research.evidence_catalog(d))
  self.assertEqual(resolved['facts'][0]['evidence_quote'],d[0]['text']);research.validate_evidence(TOPIC,resolved,d)
 def test_unknown_evidence_id_rejected(self):
  d,c,r,i=fixtures();c['facts'][0]['evidence_id']='nonexistent'
  with self.assertRaisesRegex(research.ResearchBlocked,'unknown_evidence'):research.resolve_evidence(c,research.evidence_catalog(d))
 def test_numeric_recommendation_rejected(self):
  d,c,r,i=fixtures();c['facts'][0]['claim']+=' ۲۰ درصد'
  with self.assertRaisesRegex(research.ResearchBlocked,'numeric'):research.validate_evidence(TOPIC,c,d)
 def test_independent_review_must_accept_all_claims(self):
  d,c,r,i=fixtures();r['all_claims_supported']=False
  with self.assertRaisesRegex(research.ResearchBlocked,'independent'):research.build_brief(TOPIC,d,c,r,i)
 def test_uncertain_overlap_is_not_permission(self):
  d,c,r,i=fixtures();r['overlap_decision']='uncertain'
  with self.assertRaises(research.ResearchBlocked):research.build_brief(TOPIC,d,c,r,i)
 def test_same_institution_twice_is_not_independent(self):
  d,c,r,i=fixtures();d[1]['url']='https://www.extension.msu.edu/beans';c['facts'][1]['source_url']=d[1]['url'];c['facts'][3]['source_url']=d[1]['url']
  with self.assertRaisesRegex(research.ResearchBlocked,'independent'):research.validate_evidence(TOPIC,c,d)
 def test_conflicting_slug_blocks(self):
  d,c,r,i=fixtures();i['records'][0]['url']='https://navar-abyari.ir/bean-maturity-check/'
  with self.assertRaisesRegex(research.ResearchBlocked,'existing'):research.build_brief(TOPIC,d,c,r,i)
 def test_source_host_allowlist_and_credentials(self):
  for url in ['http://extension.msu.edu/x','https://fake.edu.evil.org/x','https://user:pass@extension.msu.edu/x','https://extension.msu.edu:444/x','https://localhost/x']:
   with self.assertRaises(research.ResearchBlocked):research.source_host(url)
 def test_private_address_rejected_before_open(self):
  with patch.object(research.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch.object(research.urllib.request,'build_opener') as op:
   with self.assertRaisesRegex(research.ResearchBlocked,'non_public'):research.fetch_source('https://extension.msu.edu/x')
   op.assert_not_called()
 def test_feeder_persists_evidence_and_one_brief(self):
  d,c,r,i=fixtures()
  class Client:
   def __init__(self,*a,**k):self.answers=iter([SCOUT,c,r])
   def text(self,p,**kwargs):return next(self.answers)
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'config.json',{'research_feeder':{'enabled':True}});atomic_json(data/'health/latest.json',{'checked_at':utcnow()})
   atomic_json(data/'research-source-catalog.json',{'version':1,'entries':[{'crops':[TOPIC['crop']],'intents':[TOPIC['intent']],'urls':[x['url'] for x in d]}]})
   with patch.object(research,'items',return_value=[TOPIC]),patch.object(research,'update'):
    result=research.prepare_one(i,client_factory=Client,fetcher=lambda u:next(x for x in d if x['url']==u),data=data,out=out)
    self.assertEqual(result['status'],'brief_ready');self.assertTrue((data/'briefs'/f"{TOPIC['id']}.json").exists());self.assertTrue((out/'research-evidence'/TOPIC['id']/'review.json').exists())
    again=research.prepare_one(i,client_factory=Client,data=data,out=out);self.assertEqual(again['status'],'no_research_candidate')
 def test_source_failure_becomes_review_not_fabricated_approval(self):
  d,c,r,i=fixtures()
  class Client:
   def __init__(self,*a,**k):pass
   def text(self,p,**kwargs):return {'urls':[]}
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'config.json',{'research_feeder':{'enabled':True}});atomic_json(data/'health/latest.json',{'checked_at':utcnow()})
   with patch.object(research,'items',return_value=[TOPIC]),patch.object(research,'update'):
    result=research.prepare_one(i,client_factory=Client,data=data,out=out)
   self.assertEqual(result['status'],'research_needs_review');self.assertFalse((data/'briefs').exists())
 def test_new_verified_catalog_allows_only_bounded_source_refresh(self):
  d,c,r,i=fixtures()
  class Client:
   def __init__(self,*a,**k):self.answers=iter([SCOUT,c,r])
   def text(self,p,**kwargs):return next(self.answers)
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out'
   atomic_json(data/'config.json',{'research_feeder':{'enabled':True}});atomic_json(data/'health/latest.json',{'checked_at':utcnow()})
   atomic_json(data/'research-source-catalog.json',{'version':1,'entries':[{'crops':[TOPIC['crop']],'intents':['maturity'],'urls':[x['url'] for x in d]}]})
   atomic_json(out/'research'/f"{TOPIC['id']}.json",{'status':'needs_review','reason':'insufficient_fetchable_institutional_sources','attempts':1,'attempted_at':utcnow()})
   with patch.object(research,'items',return_value=[TOPIC]),patch.object(research,'update'):
    result=research.prepare_one(i,client_factory=Client,fetcher=lambda u:next(x for x in d if x['url']==u),data=data,out=out)
   self.assertEqual(result['status'],'brief_ready');state=load_json(out/'research'/f"{TOPIC['id']}.json");self.assertEqual(state['attempts'],2);self.assertEqual(state['source_catalog_version'],1)
 def test_catalog_refresh_never_resets_exhausted_budget(self):
  d,c,r,i=fixtures()
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'config.json',{'research_feeder':{'enabled':True}})
   atomic_json(data/'research-source-catalog.json',{'version':2,'entries':[{'crops':[TOPIC['crop']],'intents':['maturity'],'urls':[x['url'] for x in d]}]})
   atomic_json(out/'research'/f"{TOPIC['id']}.json",{'status':'needs_review','reason':'insufficient_fetchable_institutional_sources','attempts':2,'source_catalog_version':0})
   with patch.object(research,'items',return_value=[TOPIC]),patch.object(research,'update'),patch.object(research,'ModelClient') as client:
    result=research.prepare_one(i,client_factory=client,data=data,out=out);client.assert_not_called();self.assertEqual(result['status'],'no_research_candidate')
 def test_scheduled_cycle_invokes_feeder_once_when_no_brief(self):
  with tempfile.TemporaryDirectory() as t:
   data=Path(t);atomic_json(data/'config.json',{'publication_enabled':True,'automatic_generation':True,'research_feeder':{'enabled':True}})
   with patch.object(cycle,'DATA',data),patch.object(cycle,'WordPress') as wp,patch.object(research,'prepare_one',return_value={'status':'no_research_candidate'}) as prep:
    result=cycle.run(scheduled=True);prep.assert_called_once();wp.return_value.preflight.assert_called_once();self.assertEqual(result['status'],'no_research_candidate')

class FactFilterTests(unittest.TestCase):
 def _cand(self,n=5):
  d,c,r,i=fixtures();cat=research.evidence_catalog(d)
  c['facts']=[{'claim':CLAIM+' مورد '+'یکدوسه‌چهارپنج'[k],'conditions':COND,'evidence_id':f'd{k%2}-e0'} for k in range(n)]
  return d,c,r,i,cat
 def test_single_numeric_fact_dropped_not_topic(self):
  d,c,r,i,cat=self._cand();c['facts'][0]['claim']+=' U.S. No.1'
  kept,dropped=research.filter_facts(c,cat,d)
  self.assertEqual(len(kept['facts']),4);self.assertEqual(dropped[0]['reason'],'numeric_recommendation_requires_review')
  research.validate_evidence(TOPIC,kept,d);research.build_brief(TOPIC,d,kept,r,i)
 def test_unknown_id_dropped_when_enough_remain(self):
  d,c,r,i,cat=self._cand();c['facts'][1]['evidence_id']='nope'
  kept,dropped=research.filter_facts(c,cat,d);self.assertEqual(len(kept['facts']),4);self.assertEqual(dropped[0]['reason'],'unknown_evidence_id')
 def test_too_few_valid_facts_still_blocks(self):
  d,c,r,i,cat=self._cand(4);c['facts'][0]['claim']+=' ۲۰ درصد'
  with self.assertRaisesRegex(research.ResearchBlocked,'numeric'):research.filter_facts(c,cat,d)
 def test_saved_extraction_salvaged_once_without_extraction_call(self):
  d,c,r,i,cat=self._cand();c['facts'][0]['claim']+=' U.S. No.1'
  calls=[]
  class Client:
   def __init__(self,*a,**k):pass
   def text(self,p,**kwargs):calls.append(p);return r
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'config.json',{'research_feeder':{'enabled':True}});atomic_json(data/'health/latest.json',{'checked_at':utcnow()})
   ev=out/'research-evidence'/TOPIC['id'];atomic_json(ev/'candidate-raw.json',c);atomic_json(ev/'sources.json',{'documents':d})
   atomic_json(out/'research'/f"{TOPIC['id']}.json",{'topic_id':TOPIC['id'],'status':'needs_review','reason':'numeric_recommendation_requires_review','attempts':2,'attempted_at':utcnow()})
   with patch.object(research,'items',return_value=[TOPIC]),patch.object(research,'update'):
    result=research.prepare_one(i,client_factory=Client,fetcher=lambda u:self.fail('no refetch'),data=data,out=out)
    self.assertEqual(result['status'],'brief_ready');self.assertEqual(len(calls),1)
    st=load_json(out/'research'/f"{TOPIC['id']}.json");self.assertTrue(st['salvaged_saved_extraction']);self.assertEqual(st['attempts'],2)
    self.assertTrue((ev/'dropped-facts.json').exists())

if __name__=='__main__':unittest.main()

class SourcePriorityTests(unittest.TestCase):
 def test_covered_topic_precedes_unverified_discovery_without_changing_approvals(self):
  d,c,r,i=fixtures();other=dict(TOPIC,id='agri-aaaaaaaaaaaa',crop='کدو آجیلی',title='کاهش تلفات برداشت کدو آجیلی')
  class Client:
   def __init__(self,*a,**kw):self.answers=iter([SCOUT,c,r])
   def text(self,p,**kwargs):return next(self.answers)
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp)/'data';out=Path(tmp)/'out';atomic_json(data/'config.json',{'research_feeder':{'enabled':True,'prefer_verified_source_catalog':True}});atomic_json(data/'health/latest.json',{'checked_at':utcnow()})
   atomic_json(data/'research-source-catalog.json',{'version':2,'entries':[{'crops':[TOPIC['crop']],'intents':[TOPIC['intent']],'urls':[x['url'] for x in d]}]})
   with patch.object(research,'items',return_value=[other,TOPIC]),patch.object(research,'update'):
    result=research.prepare_one(i,client_factory=Client,fetcher=lambda url:next(x for x in d if x['url']==url),data=data,out=out)
   self.assertEqual(result['topic_id'],TOPIC['id']);self.assertEqual(result['status'],'brief_ready');self.assertFalse((out/'research'/f"{other['id']}.json").exists())

class ReviewShapeTests(unittest.TestCase):
 def test_known_nested_review_is_extracted_without_generated_draft(self):
  d,c,r,i=fixtures();wrapped={'draft':{'content':'Unrequested numbers and mixed language are NOT an article input'},'review':r}
  normalized=research.normalize_review(wrapped);self.assertEqual(normalized,r);self.assertNotIn('draft',normalized)
  brief=research.build_brief(TOPIC,d,c,wrapped,i);self.assertTrue(brief['publish_authorized']);self.assertNotIn('draft',brief)
 def test_wrapping_never_changes_a_false_or_uncertain_decision(self):
  d,c,r,i=fixtures();r['safe_qualitative']=False
  with self.assertRaisesRegex(research.ResearchBlocked,'independent_review_rejected'):research.build_brief(TOPIC,d,c,{'review':r},i)
  r['safe_qualitative']=True;r['overlap_decision']='uncertain'
  with self.assertRaisesRegex(research.ResearchBlocked,'independent_review_rejected'):research.build_brief(TOPIC,d,c,{'review':r},i)
 def test_unknown_wrapper_and_truthy_string_never_approve(self):
  d,c,r,i=fixtures()
  for bad in [{'draft':r},{'review':{'grounded':True}},dict(r,grounded='true')]:
   with self.assertRaisesRegex(research.ResearchBlocked,'review_response_schema_invalid'):research.normalize_review(bad)
