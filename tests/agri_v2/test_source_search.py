import concurrent.futures,hashlib,io,json,tempfile,threading,time,unittest,urllib.error
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import source_search as s,source_registry as registry,source_policy
from automation.agri_v2.parallel_pool import connect,initialize as model_initialize,snapshot as model_snapshot,PoolDeferred
from automation.agri_v2.research import source_host
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.execution_recovery import uncertain_outcome

class Response:
 status=200
 def __init__(self,obj):self.obj=obj
 def read(self,n):return json.dumps(self.obj).encode()[:n]
 def __enter__(self):return self
 def __exit__(self,*args):pass

class SourceSearchTests(unittest.TestCase):
 def setup(self,root):
  out=root/'out';db=root/'db';model_initialize(db,['AGNES_API_KEY']);s.initialize(db,out)
  return out,db,{'AFP_PARALLEL_POOL_DB':str(db),'AFP_SOURCE_SEARCH_API_KEY':'PRIVATE-SEARCH-KEY'}
 def rows(self):return [{'url':'https://extension.x.edu/bean','title':'Actual search title','description':'Untrusted search snippet, not scientific evidence'}]
 def opener(self,rows=None):return Mock(open=Mock(return_value=Response({'web':{'results':self.rows() if rows is None else rows}})))
 def no_spacing(self,db):
  with connect(db) as c:c.execute("UPDATE search_meta SET value=0 WHERE name='next_call'")
 def test_real_endpoint_and_secret_only_in_header(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td));op=self.opener();result=s.search('dry bean irrigation soil measurement',env,'request-1',opener=op);req=op.open.call_args.args[0]
   self.assertTrue(req.full_url.startswith(s.ENDPOINT+'?'));self.assertNotIn('PRIVATE',req.full_url);self.assertEqual(req.get_header('X-subscription-token'),env['AFP_SOURCE_SEARCH_API_KEY']);self.assertEqual(result['results'],self.rows());self.assertFalse(result['cached']);self.assertEqual(model_snapshot(db)['model_requests_reserved'],0)
   report=s.persist(db,out);self.assertEqual(report['requests_reserved'],1);self.assertNotIn('PRIVATE',(out/'parallel/source-search/state.json').read_text())
 def test_missing_key_never_calls_search_service_or_reserves(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td));env.pop('AFP_SOURCE_SEARCH_API_KEY');op=self.opener()
   with self.assertRaises(s.SearchConnectionRequired):s.search('dry bean field irrigation',env,'missing',opener=op)
   op.open.assert_not_called();self.assertEqual(s.persist(db,out)['requests_reserved'],0)
 def test_unsafe_and_unadmitted_search_hits_filtered_before_fetch(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td));rows=[{'url':u,'title':'title','description':'snippet'} for u in ['https://evil.org/a','https://127.0.0.1/a','https://x.edu@evil.org/a','http://x.edu/a','https://x.edu/a']]
   result=s.search('dry bean institutional irrigation',env,'q1',opener=self.opener(rows));self.assertEqual([r['url'] for r in result['results']],['https://x.edu/a'])
 def test_actual_results_reused_without_timestamp_refresh_and_persisted(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);out,db,env=self.setup(root);op=self.opener();first=s.search('dry bean field water needs',env,'q1',opener=op);second=s.search('dry bean field water needs',env,'q2',opener=op);self.assertTrue(second['cached']);self.assertEqual(first['checked_at_epoch'],second['checked_at_epoch']);op.open.assert_called_once();s.persist(db,out)
   fresh=root/'newdb';model_initialize(fresh,['AGNES_API_KEY']);s.initialize(fresh,out);env['AFP_PARALLEL_POOL_DB']=str(fresh);third=s.search('dry bean field water needs',env,'q3',opener=op);self.assertTrue(third['cached']);self.assertEqual(first['checked_at_epoch'],third['checked_at_epoch']);op.open.assert_called_once()
 def test_expired_results_require_new_real_search(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td));query='dry bean field water needs';s.search(query,env,'q1',opener=self.opener());self.no_spacing(db)
   with connect(db) as c:c.execute('UPDATE search_cache SET checked=?',(time.time()-22000,))
   op=self.opener();r=s.search(query,env,'q2',opener=op);self.assertFalse(r['cached']);op.open.assert_called_once()
 def test_retry_after_stops_search_only_and_survives_new_runner(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);out,db,env=self.setup(root);err=urllib.error.HTTPError(s.ENDPOINT,429,'unused',{'Retry-After':'7200'},io.BytesIO(b'PRIVATE PROVIDER BODY'));op=Mock(open=Mock(side_effect=err))
   with self.assertRaises(s.SearchProviderError) as caught:s.search('dry bean field water needs',env,'q1',opener=op)
   self.assertEqual(caught.exception.http_status,429);self.assertNotIn('PRIVATE',str(caught.exception));r=s.persist(db,out);self.assertGreater(r['cooldown_until_epoch'],time.time()+7100);self.assertEqual(model_snapshot(db)['cooldown_until_epoch'],0)
   fresh=root/'newdb';model_initialize(fresh,['AGNES_API_KEY']);s.initialize(fresh,out);env['AFP_PARALLEL_POOL_DB']=str(fresh)
   with self.assertRaises(PoolDeferred):s.search('another query for dry bean',env,'q2',opener=op)
   op.open.assert_called_once()
 def test_auth_rejection_not_treated_as_insufficient_scientific_sources(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td));error=urllib.error.HTTPError(s.ENDPOINT,401,'auth',{},io.BytesIO(b'PRIVATE'));op=Mock(open=Mock(side_effect=error))
   with self.assertRaises(s.SearchProviderError) as caught:s.search('dry bean irrigation method',env,'q1',opener=op)
   self.assertEqual(caught.exception.category,'source_search_auth');self.assertFalse(uncertain_outcome(caught.exception))
 def test_transport_uncertainty_keeps_reserved_outcome_and_reconciliation(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td));op=Mock(open=Mock(side_effect=TimeoutError()))
   with self.assertRaises(s.SearchProviderError) as caught:s.search('dry bean irrigation method',env,'q1',opener=op)
   self.assertTrue(uncertain_outcome(caught.exception));self.assertEqual(s.persist(db,out)['unknown_requests'],1)
 def test_request_and_search_budgets_not_reset_by_initialization(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td))
   with connect(db) as c:c.execute("UPDATE search_meta SET value=80 WHERE name='calls'")
   s.initialize(db,out);op=self.opener()
   with self.assertRaises(PoolDeferred):s.search('dry bean water needs',env,'q1',opener=op)
   op.open.assert_not_called();self.assertEqual(s.persist(db,out)['requests_reserved'],80)
 def test_reserved_request_cannot_be_replayed(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td))
   with s.reservation(db,'a'*64,'r1',wait=0):pass
   with self.assertRaises(PoolDeferred):
    with s.reservation(db,'b'*64,'r1',wait=0):pass
 def test_single_flight_search_lock_does_not_lease_a_model_key(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td))
   with s.reservation(db,'a'*64,'r1',wait=0):
    with self.assertRaises(PoolDeferred):
     with s.reservation(db,'b'*64,'r2',wait=0):pass
   self.assertEqual(model_snapshot(db)['model_requests_reserved'],0)
 def test_corrupt_cache_and_cooldown_fail_closed(self):
  for row in [{'version':1,'backend':'brave','cooldown_until_epoch':float('inf'),'cache':{}},{'version':1,'backend':'brave','cooldown_until_epoch':0,'cache':{'a'*64:{'checked':time.time(),'results':[{'url':'https://127.0.0.1','title':'x','description':'x'}]}}}]:
   with self.subTest(row=row),tempfile.TemporaryDirectory() as td:
    root=Path(td);atomic_json(root/'out/parallel/source-search/state.json',row)
    with self.assertRaises(ValueError):s.initialize(root/'db',root/'out')
 def test_no_arbitrary_endpoint_or_backend_from_configuration(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);atomic_json(d/'source-search-policy.json',dict(s.POLICY,backend='untrusted'))
   with self.assertRaises(ValueError):s.enabled(d)
 def test_international_universities_government_and_exact_publishers(self):
  for url in ('https://reading.ac.uk/a','https://uq.edu.au/a','https://iari.ac.in/a','https://www.fao.org/a','https://journals.plos.org/a','https://link.springer.com/a'):
   self.assertTrue(source_host(url))
  for url in ('https://fake.org/a','https://evil-fao.org/a','https://fao.org.evil.com/a','https://evil.ac.uk.evil.org/a','https://127.0.0.1/a'):
   with self.assertRaises(ValueError):source_host(url)
 def test_source_count_and_university_exception_not_confused_with_journal_domain(self):
  a=source_policy.assess([{'url':'https://reading.ac.uk/a'}],source_host);self.assertTrue(a['single_university_exception']);self.assertFalse(a['publication_authorized'])
  b=source_policy.assess([{'url':'https://journals.plos.org/a'}],source_host);self.assertFalse(b['satisfied']);self.assertFalse(b['single_university_exception'])
  self.assertNotEqual(registry.institution('a.ac.uk'),registry.institution('b.ac.uk'));self.assertEqual(registry.institution('extension.reading.ac.uk'),'reading.ac.uk')
 def test_workflow_has_separate_search_secret_not_a_98th_model_key(self):
  root=Path(__file__).resolve().parents[2];text=(root/'.github/workflows/afp-parallel-generator.yml').read_text();self.assertIn('AFP_SOURCE_SEARCH_API_KEY: ${{ secrets.AFP_SOURCE_SEARCH_API_KEY }}',text);self.assertEqual(text.count('secrets.AGNES_API_KEY_'),97)
 def test_error_payload_is_not_labeled_empty_scientific_search(self):
  with tempfile.TemporaryDirectory() as td:
   out,db,env=self.setup(Path(td));op=Mock(open=Mock(return_value=Response({'error':'PRIVATE invalid key detail'})))
   with self.assertRaises(s.SearchProviderError) as caught:s.search('dry bean water needs',env,'q1',opener=op)
   self.assertEqual(caught.exception.category,'source_search_response_invalid');self.assertNotIn('PRIVATE',str(caught.exception));self.assertEqual(s.persist(db,out)['unknown_requests'],0)
