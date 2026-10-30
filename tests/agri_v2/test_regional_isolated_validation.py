import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_isolated_validation as r
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.pipeline import digest
from automation.agri_v2.client import ModelClient,TextProviderError,CapabilityError
class IsolatedTests(unittest.TestCase):
 def env(self):return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF_NAME':'feat/agri-generator-v2-2905-merge593','GITHUB_RUN_ID':'123',r.SLOT:'fixture-only-not-a-secret'}
 def test_admission_exact_and_forward_only(self):
  req=r.expected();r.validate(req)
  self.assertEqual(req['max_model_calls'],3);self.assertEqual(req['max_source_fetches'],3);self.assertEqual(req['review_wire_contract'],'regional-quote-catalog-v2');self.assertEqual(len(req['source_urls']),3)
  for k,v in [('max_model_calls',4),('max_source_fetches',4),('slot','AGNES_API_KEY'),('review_wire_contract','regional-quote-catalog-v1'),('global_capacity_refresh',True),('reset_attempts',True),('publication_authorized',True),('code_sha256','changed'),('protected_sha256','changed'),('source_urls',list(reversed(req['source_urls']))),('languages',['ru-RU'])]:
   with self.subTest(k=k),self.assertRaises(r.Blocked):r.validate(dict(req,**{k:v}))
 def test_new_phase_requires_exact_manual_identity(self):
  from automation.agri_v2.parallel_control import reserve
  self.assertTrue(reserve(r.PHASE,r.ID,self.env(),put_fn=lambda row:True))
  for ident,env in [('old-id',self.env()),(r.ID,dict(self.env(),GITHUB_EVENT_NAME='schedule')),(r.ID,dict(self.env(),GITHUB_REF_NAME='main'))]:
   with self.assertRaises(ValueError):reserve(r.PHASE,ident,env,put_fn=lambda row:True)
 def test_owned_connection_does_not_claim_health(self):
  c=r.connection(self.env());self.assertEqual(c['slot'],r.SLOT);self.assertNotIn('checked_at',c);self.assertNotIn('eligible_text_slots',c)
  for env in [{k:v for k,v in self.env().items() if k!=r.SLOT},dict(self.env(),AGNES_API_KEY='fixture-only-not-a-secret')]:
   with self.assertRaises((ValueError,CapabilityError)):r.connection(env)
 def test_history_health_and_requests_protected(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';atomic_json(data/'x.json',{});before=r.manifest(data,out);atomic_json(data/r.REQUEST,{});atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{});self.assertEqual(before,r.manifest(data,out))
   for p in [out/'parallel/health/latest.json',out/'infrastructure-probes'/r.base.ID/'report.json',out/'new/topic/review-queue/ar-IQ.json',data/'regional-catalog-validation-request.json']:
    atomic_json(p,{});self.assertNotEqual(before,r.manifest(data,out));p.unlink()
 def test_unknown_report_blocks_all_work(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);atomic_json(out/'infrastructure-probes'/r.ID/'report.json',{'status':'reserved'});f=Mock();s=Mock();fetch=Mock();v=r.run(self.env(),out=out,client_factory=f,reserve_fn=s,fetcher=fetch);self.assertEqual(v['model_calls'],0);f.assert_not_called();s.assert_not_called();fetch.assert_not_called()
 def test_hold_and_remote_conflict_make_zero_calls(self):
  for held,reserved in [(True,True),(False,False)]:
   with tempfile.TemporaryDirectory() as d:
    data=Path(d)/'data';out=Path(d)/'out';atomic_json(data/r.REQUEST,{});f=Mock();s=Mock(return_value=reserved);fetch=Mock()
    with patch.object(r,'validate',return_value=(None,None,None,None)),patch.object(r,'connection',return_value={}),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=held):
     v=r.run(self.env(),data,out,client_factory=f,reserve_fn=s,fetcher=fetch)
    self.assertEqual(v['model_calls'],0);f.assert_not_called();fetch.assert_not_called()
 def fixture_sources(self):
  folder,_,_,urls=r.inputs();pack=load_json(folder/'lifecycle-evidence/sources.json')['documents'];by={d['url']:d for d in pack}
  return urls,[dict(by[u],fetched_at=utcnow(),requested_url=u,redirect_chain=[u]) for u in urls]
 def test_three_fresh_sources_exact_no_cache_or_search(self):
  urls,docs=self.fixture_sources()
  with tempfile.TemporaryDirectory() as d,patch('automation.agri_v2.source_search.search',side_effect=AssertionError('search forbidden')):
   root=Path(d);report={'source_fetches':0};f=Mock(side_effect=docs);found=r.fresh_sources(urls,root,report,f);self.assertEqual(found,docs);self.assertEqual(f.call_count,3);self.assertEqual(report['source_fetches'],3)
   with self.assertRaises(r.Blocked):r.fresh_sources(urls,root,report,f)
   self.assertEqual(f.call_count,3)
 def test_stale_hash_or_redirect_rejection_never_refetched(self):
  urls,docs=self.fixture_sources()
  for changed in [dict(docs[0],fetched_at='2020-01-01T00:00:00Z'),dict(docs[0],sha256='changed'),dict(docs[0],redirect_chain=[urls[0],'https://127.0.0.1/a',docs[0]['url']])]:
   with tempfile.TemporaryDirectory() as d:
    f=Mock(side_effect=[changed]+docs[1:]);report={'source_fetches':0}
    with self.assertRaises(r.Blocked):r.fresh_sources(urls,Path(d),report,f)
    self.assertEqual(f.call_count,3);self.assertEqual(report['source_fetches'],3)
 def test_unavailable_source_no_partial_or_archived_fallback(self):
  urls,docs=self.fixture_sources()
  with tempfile.TemporaryDirectory() as d:
   f=Mock(side_effect=[TimeoutError('sensitive fake body')]+docs[1:]);report={'source_fetches':0}
   with self.assertRaises(r.Blocked):r.fresh_sources(urls,Path(d),report,f)
   self.assertEqual(f.call_count,3);self.assertNotIn('sensitive', ''.join(p.read_text() for p in Path(d).rglob('*.json')))
 def test_materialized_contract_uses_full_new_sources(self):
  _,article,brief,_=r.inputs();_,docs=self.fixture_sources()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rows=r.prepare(article,brief,docs,root)
   for lang,(prompt,rf,sha) in rows.items():
    self.assertEqual([d['text'] for d in prompt['documents']],[d['text'] for d in docs]);self.assertEqual(prompt['_regional_wire_contract'],r.VERSION);row=load_json(root/'contracts'/(lang+'.json'));self.assertLess(row['outbound_characters'],200000);self.assertEqual(row['prompt_sha256'],sha);self.assertEqual(row['response_schema_sha256'],digest(rf['json_schema']['schema']))
 def pool(self,root):
  from automation.agri_v2.parallel_pool import initialize
  db=root/'pool.sqlite';initialize(db,[r.SLOT],text_limit=1,image_limit=1,max_calls=3,per_worker=3)
  return dict(self.env(),AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=r.ID)
 def response(self):return {'model':'agnes-2.5-flash','choices':[{'message':{'content':'{"status":"ok"}'},'finish_reason':'stop'}]}
 def test_health_once_unknown_never_replay_or_rotate(self):
  for failure in [None,TextProviderError(None,'network_or_timeout')]:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);worker=self.pool(root);contract=r.connection(self.env())
    class Fake(ModelClient):
     def request(me,*args,**kwargs):
      self.assertEqual(kwargs['attempts'],1)
      if failure:raise failure
      return self.response()
    c=r.CountedClient(worker,root,contract,base_class=Fake);c.phase='health'
    if failure:
     with self.assertRaises(TextProviderError):c.text(r.HEALTH_PROMPT,response_schema=r.SCHEMA,max_tokens=256,timeout=45)
    else:self.assertEqual(c.text(r.HEALTH_PROMPT,response_schema=r.SCHEMA,max_tokens=256,timeout=45),{'status':'ok'})
    with self.assertRaises(r.Blocked):c.text(r.HEALTH_PROMPT,response_schema=r.SCHEMA,max_tokens=256,timeout=45)
    self.assertEqual(len(list((root/'calls').glob('*.json'))),1);self.assertEqual(c.keys['text'][0][0],r.SLOT);self.assertFalse(c.keys['image'])
 def test_wrong_transport_and_health_budget_before_lease(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);c=r.CountedClient(self.pool(root),root,r.connection(self.env()));c.phase='health'
   for kind,path,payload,timeout in [('image','/images/generations',{},45),('text','/chat/completions',{'model':'wrong'},45),('text','/chat/completions',{'model':'agnes-2.5-flash','max_tokens':257},45)]:
    with self.assertRaises(r.Blocked):c.request(kind,path,payload,timeout)
   self.assertFalse(list((root/'calls').glob('*.json')))
 def test_review_cannot_start_without_health(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);c=r.CountedClient(self.pool(root),root,r.connection(self.env()));c.phase='ar-IQ'
   with self.assertRaises(OSError):c.text('fixture',response_schema={},max_tokens=256,timeout=45)
   self.assertFalse(list((root/'calls').glob('*.json')))
 def test_diagnostics_redacted(self):
  self.assertNotIn('private',str(r.diagnostic(r.Blocked('private secret text'))));self.assertNotIn('private',str(r.diagnostic(RuntimeError('private secret text'))))
 def test_full_isolated_run_negative_leaves_expired_global_health_unchanged(self):
  urls,docs=self.fixture_sources();_,article,brief,_=r.inputs()
  # Exercise the real transport ledger, pool, prompt/schema/catalog projection
  # and all final validators, with a deterministic bound negative, not a model.
  class Fake(ModelClient):
   def request(me,kind,path,payload,timeout,attempts=None):
    if me.phase=='health':return self.response()
    schema=payload['response_format']['json_schema']['schema'];props=schema['properties']
    def sample(s):
     if 'anyOf' in s:return sample(s['anyOf'][-1])
     t=s.get('type')
     if isinstance(t,list):t=next((x for x in t if x!='null'),t[0])
     if 'enum' in s:return s['enum'][0]
     if t=='object':return {k:sample(v) for k,v in s['properties'].items()}
     if t=='array':return [sample(s['items']) for _ in range(s.get('minItems',1))]
     if t=='boolean':return True
     if t=='integer':return s.get('minimum',2)
     if t=='null':return None
     return 'Insufficient local applicability; the original observation does not prove local prescription.'
    raw=sample(schema)
    # Use explicit false decisions for all fact rows; real v2 schema binds each
    # objection to that fact and to a current literal article passage.
    return {'model':'agnes-2.5-flash','choices':[{'message':{'content':json.dumps(raw)},'finish_reason':'stop'}]}
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/r.REQUEST,{});atomic_json(out/'parallel/health/latest.json',{'checked_at':'2020-01-01T00:00:00Z','eligible_text_slots':[]});health=(out/'parallel/health/latest.json').read_bytes();fetch=Mock(side_effect=docs)
   # Real admission/selection already tested above; fixture paths otherwise
   # deliberately lack unrelated production data to prove no dependency.
   def factory(worker,path,contract):return r.CountedClient(worker,path,contract,base_class=Fake)
   with patch.object(r,'validate',return_value=(None,article,brief,urls)),patch.object(r,'connection',return_value={'slot':r.SLOT,'scope':'fixture'}),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False),patch('automation.agri_v2.source_search.search',side_effect=AssertionError('search forbidden')):
    result=r.run(self.env(),data,out,client_factory=factory,reserve_fn=lambda env:True,fetcher=fetch)
   self.assertEqual(result['model_calls'],3,result);self.assertEqual(result['source_fetches'],3,result);self.assertEqual(result['request_receipts'],3);self.assertTrue(result['originals_unchanged']);self.assertEqual(health,(out/'parallel/health/latest.json').read_bytes());self.assertFalse(result['production_readiness_claimed']);self.assertFalse(list((out/'new').rglob('approved.json')));self.assertEqual([x['status'] for x in result['results']],['validated_negative']*2,result)
   self.assertEqual(r.run(self.env(),data,out,client_factory=Mock(),fetcher=Mock())['model_calls'],0)
 def test_failed_health_consumes_only_one_no_fetch(self):
  class Fake(ModelClient):
   def request(me,*a,**k):return {'choices':[{'message':{'content':'{"status":"bad"}'}}]}
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);data=root/'data';out=root/'out';atomic_json(data/r.REQUEST,{});f=Mock()
   with patch.object(r,'validate',return_value=(None,None,None,None)),patch.object(r,'connection',return_value={}),patch('automation.agri_v2.post_hold_validation.circuit'),patch('automation.agri_v2.family_capability_refresh.active_hold',return_value=False):
    result=r.run(self.env(),data,out,client_factory=lambda w,p,c:r.CountedClient(w,p,c,base_class=Fake),reserve_fn=lambda env:True,fetcher=f)
   self.assertEqual(result['model_calls'],1);self.assertEqual(result['source_fetches'],0);f.assert_not_called();self.assertEqual(result['failure']['category'],'isolated_health_response_invalid')
