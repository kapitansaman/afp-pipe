import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_explicit_decision as v,regional_sources as regional,family07_verdict_continuation as r
from automation.agri_v2 import regional_arabic_v3_validation as ar
from automation.agri_v2.queue import DATA,OUT,load_json,atomic_json
from automation.agri_v2.pipeline import digest
from automation.agri_v2.parallel_pool import initialize,snapshot
from automation.agri_v2.parallel_control import reserve

class ExplicitDecisionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.article=load_json(OUT/'new'/r.TOPIC/'article.json');cls.brief=load_json(DATA/'briefs'/(r.TOPIC+'.json'));cls.docs=[load_json(OUT/'infrastructure-probes'/r.previous.ID/'documents'/(str(i)+'.json')) for i in range(3)]
  cls.p=r.prompt(cls.article,cls.brief,cls.docs,'ru-RU');cls.schema=regional.response_schema('regional-evidence-review-fallback',cls.p);cls.bound=v.bound(cls.p)
  cls.yes=load_json(OUT/'infrastructure-probes'/ar.ID/'languages/ar-IQ/regional-evidence-review-fallback.raw.json')
  # Synthetic positive fixture: map identical literal passages across pack ordering.
  # Never alter the historical raw receipt or infer a production verdict.
  oldcat=load_json(OUT/'infrastructure-probes'/ar.ID/'languages/ar-IQ/regional-evidence-review-fallback.catalog.json')['consistency']['quote_catalog']
  olddocs=[load_json(OUT/'infrastructure-probes'/ar.ID/'documents'/(str(i)+'.json')) for i in range(3)]
  newcat=cls.bound['previous']['consistency']['quote_catalog']
  for row in cls.yes['fact_checks'].values():
   passage=next(p for p in oldcat['source_passages'] if p['id']==row['evidence_quote_id']);url=olddocs[int(passage['document_id'][1:])]['url'];newdoc='s'+str(next(i for i,d in enumerate(cls.docs) if d['url']==url))
   row['evidence_quote_id']=next(p['id'] for p in newcat['source_passages'] if p['document_id']==newdoc and p['text']==passage['text'])
   row.pop('supported');row['source_support_decision']=v.YES
  cls.no=load_json(OUT/'infrastructure-probes'/r.previous.ID/'regional/ru-RU/regional-evidence-review-fallback.raw.json')
  for row in cls.no['fact_checks'].values():row.pop('supported');row['source_support_decision']=v.NO;row['objection']['defect']='missing_source_support'
 def test_explicit_positive_maps_without_inference(self):
  raw=copy.deepcopy(self.yes);result=v.canonical(raw,self.schema,self.bound);self.assertTrue(all(c['supported'] for c in result['fact_checks']));self.assertEqual(raw,self.yes)
  regional.validate_local_review(result,self.article,self.brief,self.docs,'ru-RU')
 def test_negative_remains_negative_even_with_positive_explanation(self):
  raw=copy.deepcopy(self.no);result=v.canonical(raw,self.schema,self.bound);self.assertTrue(all(c['supported']is False for c in result['fact_checks']));self.assertEqual(raw,self.no)
  with self.assertRaises(ValueError):regional.validate_local_review(result,self.article,self.brief,self.docs,'ru-RU')
 def test_legacy_boolean_not_silently_converted(self):
  raw=copy.deepcopy(self.yes);row=raw['fact_checks']['f0'];row['supported']=True;row.pop('source_support_decision')
  with self.assertRaises(ValueError):v.canonical(raw,self.schema,self.bound)
 def test_positive_requires_null_objection(self):
  raw=copy.deepcopy(self.yes);raw['fact_checks']['f0']['objection']=self.no['fact_checks']['f0']['objection']
  with self.assertRaises(ValueError):v.canonical(raw,self.schema,self.bound)
 def test_negative_requires_genuine_typed_defect_field(self):
  for change in ('missing','unknown','null'):
   raw=copy.deepcopy(self.no)
   if change=='missing':raw['fact_checks']['f0']['objection'].pop('defect')
   elif change=='unknown':raw['fact_checks']['f0']['objection']['defect']='this_is_supported'
   else:raw['fact_checks']['f0']['objection']=None
   with self.assertRaises(ValueError):v.canonical(raw,self.schema,self.bound)
 def test_enum_unknown_missing_or_contradictory_extra_field_rejected(self):
  for value in ('true',False,'approve',None):
   raw=copy.deepcopy(self.yes);raw['fact_checks']['f0']['source_support_decision']=value
   with self.assertRaises(ValueError):v.canonical(raw,self.schema,self.bound)
 def test_numeric_country_and_foreign_scope_constraints_unchanged(self):
  for key,value in [('country',None),('local_evidence_gap','short'),('transfer_limits_retained',False),('international_fallback',False),('scope','short')]:
   raw=copy.deepcopy(self.yes);raw['fact_checks']['f0'][key]=value
   with self.assertRaises(ValueError):v.canonical(raw,self.schema,self.bound)
 def test_bound_document_tamper_rejected(self):
  p=copy.deepcopy(self.p);p['documents'][0]['text']+=' changed'
  with self.assertRaises(ValueError):v.bound(p)
 def test_old_schema_is_untouched(self):
  from automation.agri_v2.regional_catalog_context import VERSION
  old=regional.review_prompt(self.article,self.brief,'ru-RU',self.docs,wire=VERSION);schema=regional.response_schema('regional-evidence-review-fallback',old)
  for item in schema['properties']['fact_checks']['properties'].values():
   for branch in item['anyOf']:self.assertIn('supported',branch['properties']);self.assertNotIn('source_support_decision',branch['properties'])
 def test_new_projection_is_cacheable_with_raw_receipt_and_schema_hash(self):
  from automation.agri_v2.translation_review_repair import request
  from automation.agri_v2.retained_regional_positive import CacheOnly
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);client=Mock();client.text.return_value=self.yes
   x=request(client,root,'regional-evidence-review-fallback',self.p,1);self.assertEqual(x,request(CacheOnly(),root,'regional-evidence-review-fallback',self.p,1));client.text.assert_called_once()
   receipt=load_json(root/'regional-evidence-review-fallback.receipt.json');self.assertEqual(receipt['response_adapter'],v.VERSION);self.assertEqual(receipt['raw_sha256'],digest(self.yes))
 def test_prior_report_unknown_is_never_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);atomic_json(root/'out/infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});fn=Mock()
   with patch.object(r,'identity'):result=r.run({},root/'data',root/'out',client_factory_fn=fn,reserve_fn=fn)
   self.assertEqual(result['model_calls'],0);fn.assert_not_called()
 def test_new_manual_phase_exact_only(self):
  env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123','GITHUB_TOKEN':'fake'}
  self.assertTrue(reserve(r.PHASE,r.ID,env,put_fn=lambda row:True))
  for change in [{'GITHUB_EVENT_NAME':'schedule'},{'GITHUB_REF_NAME':'main'}]:
   with self.assertRaises(ValueError):reserve(r.PHASE,r.ID,dict(env,**change),put_fn=Mock())
 def test_retained_approved_languages_and_previous_failed_run_protected(self):
  for path in ['out/new/'+r.TOPIC+'/review-queue/ar-IQ.json','out/new/'+r.TOPIC+'/regional-research/en-US/approved.json','out/infrastructure-probes/'+r.previous.ID+'/report.json','out/new/'+r.TOPIC+'/article.json']:self.assertFalse(r.mutable(path))
  self.assertTrue(r.mutable('out/new/'+r.TOPIC+'/review-queue/attempts/ru-RU/3/draft.raw.json'))
 def test_remaining_budget_denies_incomplete_repair_before_transport(self):
  from automation.agri_v2.family07_multilingual import CountedClient,Blocked
  class Fake:
   def request(self,*a,**kw):raise AssertionError('Transport must not occur')
  with tempfile.TemporaryDirectory() as td,patch.object(r.capability,'guards'),patch.object(r.previous,'capability_proof'):
   root=Path(td);pool=root/'pool.sqlite';initialize(pool,list(r.capability.TEXT),max_calls=9,per_worker=9);worker={s:'fake-'+s for s in r.capability.TEXT};worker['AFP_PARALLEL_POOL_DB']=str(pool);client=CountedClient(worker,root/'request',root/'data',root/'out',base_class=Fake,request_id=r.ID,max_calls=9,manifest_fn=lambda *a:{})
   client.phase='semantic';client.language='tg-TJ';client.sequence=['draft','review']
   for i in range(8):atomic_json(root/'request/calls/ru-RU'/(str(i)+'.json'),{'stage':'review','request_sha256':str(i)})
   from automation.agri_v2.healthcheck import TEXT_MODEL
   payload={'model':TEXT_MODEL,'messages':[{'content':json.dumps({'task':'Correct ONLY listed target IDs'})}],'max_tokens':14000}
   with self.assertRaisesRegex(Blocked,'repair_and_recheck'):client.request('text','/chat/completions',payload,180,attempts=1)
   self.assertEqual(snapshot(pool)['model_requests_reserved'],0)
 def test_exact_admission_nine_remaining_and_zero_new_fetch(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';a=self.article;b=self.brief;rows={l:{'status':'fixture'} for l in r.LANGS+r.RETAINED};old={'documents':self.docs}
   with patch.object(r,'inputs',return_value=(o/'new'/r.TOPIC,a,b,rows,[d['url'] for d in self.docs])),patch.object(r,'prior_proof',return_value=old),patch.object(r.previous,'capability_proof',return_value={'fixture':True}):
    req=r.expected(d,o);r.validate(req,d,o)
    for key,value in [('max_text_calls',10),('combined_prior_and_new_text_cap',11),('max_source_fetches',1),('max_search_requests',1),('max_site_calls',1),('max_runs',2),('max_in_flight',2),('reset_attempts',True),('publication_authorized',True),('schedule_enabled',True),('role_slots',{})]:
     with self.subTest(key=key),self.assertRaises(r.Blocked):r.validate(dict(req,**{key:value}),d,o)
 def test_continuation_orchestration_zero_fetch_combined_spend_and_no_retained_edits(self):
  import shutil
  from automation.agri_v2.parallel_pool import lease
  from automation.agri_v2.queue import utcnow
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d=root/'data';o=root/'out';shutil.copytree(DATA,d);folder=o/'new'/r.TOPIC;shutil.copytree(OUT/'new'/r.TOPIC,folder);rows={l:load_json(r.q.path(folder,l)) for l in r.LANGS+r.RETAINED};atomic_json(d/r.REQUEST,{'fixture':True});env={s:'fake-'+s for s in r.capability.TEXT};env['GITHUB_RUN_ID']='123'
   class FakeClient:
    def __init__(self,worker,path,*args):self.worker=worker;self.root=path
   def review(client,*args):
    with lease(client.worker['AFP_PARALLEL_POOL_DB'],'text',[r.capability.TEXT[2]],r.ID,wait=0):atomic_json(client.root/'calls'/client.language/'0.json',{'stage':'regional','status':'response_received'})
    return v.canonical(self.yes,self.schema,self.bound)
   def semantic(path,client,data):
    lang=client.language;shadow=path.parent.parent;row=load_json(path);self.assertEqual(row['model_calls_spent'],rows[lang]['model_calls_spent']+1)
    for slot in r.capability.TEXT[:2]:
     with lease(client.worker['AFP_PARALLEL_POOL_DB'],'text',[slot],r.ID,wait=0):pass
    atomic_json(shadow/'review-queue/attempts'/lang/'3/draft.receipt.json',{'status':'received'})
    for suffix in ('.json','.raw.json','.fidelity.json'):atomic_json(shadow/'translations'/(lang+suffix),{'fixture':True})
    row.update(status='approved',attempts=3,model_calls_spent=row['model_calls_spent']+2);atomic_json(path,row);return {'language':lang,'status':'approved','model_calls':2}
   with patch.object(r,'identity'),patch.object(r,'validate',return_value=(folder,self.article,self.brief,rows,[d['url'] for d in self.docs])),patch.object(r,'prior_proof',return_value={'documents':self.docs}),patch.object(r.capability,'guards'),patch.object(r.capability,'check_unique_values'),patch('automation.agri_v2.translation_review_repair.request',side_effect=review),patch.object(r.q,'run_item',side_effect=semantic),patch.object(r.q,'approved',return_value=True),patch('automation.agri_v2.scoped_sources.fetch',side_effect=AssertionError('No source fetch authorized')):
    report=r.run(env,d,o,client_factory_fn=FakeClient,reserve_fn=lambda e:True)
   self.assertEqual(report['status'],'family07_verdict_verified_not_published');self.assertEqual((report['model_calls'],report['combined_text_calls'],report['source_fetches']),(6,7,0));self.assertTrue(report['originals_unchanged'])
   for lang in r.RETAINED:self.assertEqual(load_json(r.q.path(folder,lang)),rows[lang])
   for key in ('image_calls','site_calls','search_requests','published_posts'):self.assertEqual(report[key],0)
