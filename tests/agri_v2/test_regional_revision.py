import copy,json,tempfile,unittest,datetime
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_revision as r,regional_sources as regions,source_search,parallel_pool
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.pipeline import digest
from automation.agri_v2.client import TextProviderError
import test_family_lifecycle as fixture
class RegionalRevisionTests(unittest.TestCase):
 def setup(self,t):
  data,out,topic,env,health=fixture.FamilyLifecycleTests().setup(t);topic=dict(topic,id=r.TOPIC,family_id='family-07');folder=out/'new'/r.TOPIC
  atomic_json(folder/'article.json',{'old':'article'});atomic_json(data/'briefs'/(r.TOPIC+'.json'),{'old':'brief'});atomic_json(folder/'wordpress-receipt.json',{'topic_id':r.TOPIC,'post_id':524204,'public_verified':True});atomic_json(data/'regional-research-policy.json',regions.POLICY)
  req={'version':1,'request_id':r.ID,'topic_id':r.TOPIC,'family_id':'family-07','source_post_id':524204,'prepare_authorized':True,'publication_authorized':False,'max_model_calls':8,'max_search_requests':4,'max_revision_runs':1,'reset_original_attempts':False,'required_source_language':'fa-IR','input_binding':r.inputs(data,out)};atomic_json(data/'regional-revision-request.json',req)
  env.update(AFP_SOURCE_SEARCH_API_KEY='private-fixture',AFP_WP_USERNAME='never-forward',AFP_WP_BASE_URL='https://navar-abyari.ir',AFP_WP_APP_PASSWORD='never-forward');return data,out,topic,env,health,req
 def execute(self,data,out,env,prepare):
  with patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None):return r.run(env,data,out,client_factory=Mock(return_value=Mock()),prepare_fn=prepare)
 def test_exact_binding_and_budget_authorization_required(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t);self.assertEqual(r.validate_request(req,data,out),req)
   for k,v in [('publication_authorized',True),('max_model_calls',9),('max_model_calls',True),('max_revision_runs',2),('reset_original_attempts',True),('family_id','family-08')]:
    bad=dict(req,**{k:v})
    with self.assertRaises(ValueError):r.validate_request(bad,data,out)
   atomic_json(out/'new'/r.TOPIC/'article.json',{'changed':True})
   with self.assertRaises(ValueError):r.validate_request(req,data,out)
 def test_wrong_source_cannot_be_revised(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t);atomic_json(out/'new'/r.TOPIC/'wordpress-receipt.json',{'topic_id':r.TOPIC,'post_id':111,'public_verified':True});req['input_binding']=r.inputs(data,out)
   with self.assertRaisesRegex(ValueError,'exact_verified_source'):r.validate_request(req,data,out)
 def test_one_shot_revision_retains_original_bytes_and_removes_wordpress_secrets(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t);before=r.inputs(data,out);factory=Mock(return_value=Mock());prepare=Mock(return_value={'status':'revision_ready_for_publication_review','publication_authorized':False})
   with patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None):
    result=r.run(env,data,out,client_factory=factory,prepare_fn=prepare);again=r.run(env,data,out,client_factory=factory,prepare_fn=prepare)
   self.assertEqual(result['status'],'revision_ready_for_publication_review');self.assertEqual(r.inputs(data,out),before);self.assertEqual(result['post_mutations'],0);self.assertFalse(result['original_attempts_reset']);self.assertEqual(again['status'],'revision_already_reserved_no_replay');self.assertEqual(prepare.call_count,1)
   worker=factory.call_args.kwargs['env'];self.assertEqual(worker['AFP_PARALLEL_FAMILY'],'family-07');self.assertFalse(any(k.startswith('AFP_WP_') for k in worker));self.assertNotIn('private-fixture',json.dumps(result))
 def test_stale_health_does_not_reserve_or_call_models(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t);health['checked_at']='2020-01-01T00:00:00Z';atomic_json(out/'parallel/health/latest.json',health);fn=Mock();result=self.execute(data,out,env,fn)
   self.assertEqual(result['status'],'revision_fresh_text_health_required');self.assertFalse((out/'regional-revisions'/r.ID/'report.json').exists());fn.assert_not_called()
 def test_negative_science_is_not_an_approval_or_automatic_replay(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t);fn=Mock(side_effect=regions.RegionalBlocked('regional_applicability_not_approved'));result=self.execute(data,out,env,fn);again=self.execute(data,out,env,fn)
   self.assertEqual(result['status'],'revision_needs_attention');self.assertFalse(result['publication_authorized']);self.assertEqual(result['failure']['category'],'regional_applicability_not_approved');self.assertEqual(again['status'],'revision_already_reserved_no_replay');self.assertEqual(fn.call_count,1)
 def test_unknown_response_is_fenced_and_never_replayed(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t);fn=Mock(side_effect=TextProviderError(None,'network_or_timeout'));result=self.execute(data,out,env,fn);again=self.execute(data,out,env,fn)
   self.assertEqual(result['status'],'revision_reconciliation_required');self.assertEqual(again['status'],'revision_already_reserved_no_replay');self.assertEqual(fn.call_count,1)
 def test_interrupted_reserved_revision_cannot_be_restarted(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t)
   with self.assertRaises(KeyboardInterrupt):self.execute(data,out,env,Mock(side_effect=KeyboardInterrupt()))
   fn=Mock();result=self.execute(data,out,env,fn);self.assertEqual(result['status'],'revision_already_reserved_no_replay');fn.assert_not_called()
 def test_automatic_event_not_authorized(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,health,req=self.setup(t);env['GITHUB_EVENT_NAME']='schedule'
   with self.assertRaisesRegex(ValueError,'manual_destination'):self.execute(data,out,env,Mock())
 def test_receipt_client_obeys_global_eight_calls_and_keeps_unknown_reservation(self):
  with tempfile.TemporaryDirectory() as t:
   calls=Path(t);client=Mock();client.text.return_value={'response':'data'}
   for i in range(8):r.ReceiptClient(client,calls,'step-'+str(i),'researcher').text({'task':'data'})
   with self.assertRaisesRegex(ValueError,'budget'):r.ReceiptClient(client,calls,'ninth','researcher').text({'task':'data'})
   self.assertEqual(client.text.call_count,8)
 def test_search_planner_requires_two_bounded_distinct_queries_per_phase(self):
  valid={'local_queries':['alfalfa local research','alfalfa technical Iran'],'international_queries':['alfalfa harvest university','alfalfa preharvest soil']};self.assertEqual(r.plan_queries(valid),valid)
  for v in [dict(valid,local_queries=['x']),dict(valid,local_queries=['same query','same query']),dict(valid,international_queries=['x'*241,'valid query'])]:
   with self.assertRaises(ValueError):r.plan_queries(v)
 def test_new_revision_search_namespace_and_hard_four_request_ceiling(self):
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);db=root/'pool.sqlite';source_search.initialize(db,root);client=SimpleNamespace(source_search_env={'AFP_PARALLEL_POOL_DB':str(db),'AFP_SOURCE_SEARCH_API_KEY':'fixture'})
   topic={'id':r.TOPIC,'title':'Original title','crop':'یونجه','intent':'preharvest_water'};plan={'local_queries':['local query one','local query two'],'international_queries':['international one','international two']};seen=[]
   def fake_collect(topic,lang,client,out,folder,search_fn,international):
    for i in range(2):search_fn('query',client.source_search_env,'regional-'+('international' if international else 'local')+'-'+str(i))
    return []
   def search(query,env,ident):
    seen.append(ident)
    with parallel_pool.connect(db) as c:c.execute("UPDATE search_meta SET value=value+1 WHERE name='calls'")
    return {'results':[]}
   with patch.object(regions,'collect',side_effect=fake_collect):
    r.planned_collect(topic,plan,'local',client,root,root/'folder',search);r.planned_collect(topic,plan,'international',client,root,root/'folder',search)
    with self.assertRaises(parallel_pool.PoolDeferred):r.planned_collect(topic,plan,'local',client,root,root/'other',search)
   self.assertEqual(len(seen),4);self.assertTrue(all(i.startswith(r.ID+'-') for i in seen));self.assertEqual(len(set(seen)),4)
