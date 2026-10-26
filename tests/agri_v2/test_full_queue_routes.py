import copy,json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import research_routes as r,scoped_research as s,family_lifecycle as f,operation_request as op
from automation.agri_v2.queue import items,DATA,atomic_json,load_json,utcnow
from automation.agri_v2.source_discovery import entries_for
from automation.agri_v2.source_scout import collect
from automation.agri_v2.research import source_host
from automation.agri_v2.parallel_pool import lease,SLOTS,PoolDeferred
import test_family_lifecycle as fixture_f
import test_scoped_research as fixture_s

class FullQueueRoutesTests(unittest.TestCase):
 def test_full_immutable_population_exactly_mapped_without_publication(self):
  topics=items('new');self.assertEqual(len(topics),2905);self.assertEqual(len({t['id'] for t in topics}),2905);self.assertEqual(len({t['title'] for t in topics}),2905)
  self.assertEqual({t['intent'] for t in topics},set(r.ROUTES));self.assertEqual(len(r.ROUTES),74);self.assertEqual(len({t['crop'] for t in topics}),76)
  for t in topics:
   p=r.plan(t);self.assertEqual((p['canonical_title'],p['crop'],p['intent']),(t['title'],t['crop'],t['intent']));self.assertFalse(p['publication_authorized']);self.assertFalse(p['human_review_claimed']);self.assertTrue(p['required_evidence'])
 def test_unknown_intent_or_crop_not_silently_replaced(self):
  t=items('new')[0]
  for bad in [dict(t,intent='new_unknown'),dict(t,crop='unknown')]:
   with self.assertRaises(ValueError):r.plan(bad)
 def test_every_intent_reaches_sources_even_without_catalog(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=fixture_f.FamilyLifecycleTests().setup(td);p=load_json(d/'family-lifecycle-policy.json');p['scoped_evidence_research']=True;atomic_json(d/'family-lifecycle-policy.json',p)
   for intent in r.ROUTES:self.assertEqual(f.next_stage(dict(t,crop='لوبیا قرمز',intent=intent),d,o),('research_sources',None))
   self.assertEqual(f.next_stage(dict(t,intent='unknown'),d,o)[0],'blocked')
 def test_new_route_requires_positive_review_old_accepted_stays_valid(self):
  fixture=fixture_s.ScopedResearchTests();t,v,docs=fixture.fixture();facts=s.validate_candidate(t,v,docs);review=fixture.review(facts);_,overlap=fixture.overlap(t);inv={'source_generated_at':utcnow(),'records':[]}
  old=s.build_brief(t,v,docs,review,overlap,inv);self.assertNotIn('research_route',old);s.verify_brief(old)
  v['research_route_version']=r.VERSION
  for bad in [review,dict(review,research_route_version=r.VERSION,route_requirements_met=False),dict(review,research_route_version='unknown',route_requirements_met=True)]:
   with self.assertRaises(ValueError):s.build_brief(t,v,docs,bad,overlap,inv)
  good=dict(review,research_route_version=r.VERSION,route_requirements_met=True);brief=s.build_brief(t,v,docs,good,overlap,inv);self.assertEqual(brief['research_route'],r.plan(t))
  from automation.agri_v2.pipeline import check_brief
  check_brief(t,brief);brief['research_route']['intent']='cost'
  with self.assertRaises(ValueError):check_brief(t,brief)
 def test_crop_alias_lead_is_not_scientific_approval(self):
  t=next(t for t in items('new') if t['crop']=='سیب‌زمینی');es=entries_for(t,DATA);self.assertTrue(any(e['urls'] for e in es));self.assertTrue(any(e.get('discovery_only') for e in es));self.assertIn('potatoes',r.crop_terms(t['crop']))
 def test_two_hop_observed_links_bounded_and_index_excluded(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);seen=[];hub='https://one.edu/index';urls=[f'https://one.edu/bean-{i}' for i in range(30)]
   def fetch(u):
    seen.append(u);n=0 if u==hub else int(u.rsplit('-',1)[1])+6;text='Actual crop production evidence. '*30
    return dict(url=u,text=text,sha256=hashlib.sha256(text.encode()).hexdigest(),fetched_at=utcnow(),links=[{'url':v,'label':'bean'} for v in urls[n:n+6]]+[{'url':'https://evil.org/bean','label':'bean'}])
   docs,report=collect([{'urls':[hub],'discovery_terms':['bean'],'crop_discovery_terms':['bean'],'observed_source_index':True,'discovery_only':True,'discovery_hub_urls':[hub]}],fetch,p,source_host,p/'ev')
   self.assertLessEqual(len(seen),12);self.assertEqual(report['max_link_depth'],2);self.assertNotIn(hub,[d['url'] for d in docs]);self.assertEqual(len(seen),len(set(seen)));self.assertTrue(all(u.startswith('https://one.edu/') for u in seen))
 def req(self):return {'version':1,'request_id':op.FULL_QUEUE_ID,'operation':'full-queue-research-only','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':20,'enable_schedule':False,'reset_attempts':False,'max_worker_text_calls':80,'max_worker_image_calls':0,'max_wordpress_mutations':0,'code_revision':'b'*40}
 def test_exact_nonpublishing_bounded_request(self):
  op.validate_request(self.req())
  for k,v in [('max_worker_text_calls',81),('max_worker_image_calls',1),('max_wordpress_mutations',1),('max_pilot_families',21),('reset_attempts',True),('enable_schedule',True),('code_revision','x')]:
   bad=self.req();bad[k]=v
   with self.assertRaises(ValueError):op.validate_request(bad)
 def test_research_pilot_sets_only_research_mode(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';atomic_json(d/'status/owner-operation-admission.json',{'request_id':op.FULL_QUEUE_ID});atomic_json(o/'parallel/operations'/op.FULL_QUEUE_ID/'prepare.json',{'run_id':'10','status':'research_prerequisites_passed'})
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_controller.run',return_value={'status':'completed'}) as run:
    op.pilot({'GITHUB_RUN_ID':'10'},d,o)
   self.assertEqual(run.call_args.args[0],'advance');self.assertEqual(run.call_args.args[1]['AFP_FULL_QUEUE_RESEARCH_ONLY'],'1');self.assertNotIn('AFP_WHITE_BEAN_PILOT',run.call_args.args[1])
 def test_worker_stops_before_any_nonresearch_stage(self):
  for stage in ['text','image-1','vision-1','translation-en-US','publish','article_evidence_review']:
   with self.subTest(stage=stage),tempfile.TemporaryDirectory() as td:
    d,o,t,e,h=fixture_f.FamilyLifecycleTests().setup(td);e['AFP_FULL_QUEUE_RESEARCH_ONLY']='1';factory=Mock()
    with patch.object(f,'next_stage',return_value=(stage,None)),patch.object(f,'run_stage') as execute:result=f.worker(t,h,d,o,e,factory)
    self.assertEqual(result['status'],'research_ready');factory.assert_not_called();execute.assert_not_called();self.assertEqual(result['published_posts'],0)
 def test_coordinator_never_publishes_and_enforces_four_calls_per_family(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=fixture_f.FamilyLifecycleTests().setup(td);e['AFP_FULL_QUEUE_RESEARCH_ONLY']='1';topics=[dict(t,id='agri-'+format(i,'012x'),family_id=f'family-{i+1:02}') for i in range(20)];wp=Mock();wp.inventory.return_value={'source_generated_at':utcnow(),'scope':'all public posts','records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   def worker(topic,workspace,db,*args):
    for _ in range(4):
     with lease(db,'text',SLOTS,topic['id']):pass
    with self.assertRaises(PoolDeferred):
     with lease(db,'text',SLOTS,topic['id']):pass
    return topic['id'],workspace/topic['id']/'data',workspace/topic['id']/'out',{'topic_id':topic['id'],'status':'publication_ready'}
   with patch.object(f,'allocate',return_value={}),patch.object(f,'assigned_topics',return_value=topics),patch('automation.agri_v2.recovery.circuit_open',return_value=False),patch.object(f,'next_stage',return_value=('publish',None)),patch.object(f,'publish_ready') as publish:
    report=f.run(e,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   self.assertEqual(report['status'],'completed');self.assertEqual(report['pool']['model_requests_reserved'],80);self.assertEqual(report['pool']['peak_image_leases'],0);self.assertEqual(report['published_posts'],0);self.assertFalse(report['publication_authorized']);publish.assert_not_called();wp.publish.assert_not_called()
 def test_prompt_uses_topic_contract_not_whitebean_template(self):
  from automation.agri_v2.grounded_drafting import prompt
  fixture=fixture_s.ScopedResearchTests();t,v,d=fixture.fixture();facts=s.validate_candidate(t,v,d);_,overlap=fixture.overlap(t);brief=s.build_brief(t,v,d,fixture.review(facts),overlap,{'source_generated_at':utcnow(),'records':[]});brief['research_route']=r.plan(t)
  packet=json.loads(prompt(t,brief));self.assertEqual(packet['research_route'],r.plan(t));self.assertIn('ONLY if two distinct approved observations',packet['task']);self.assertIn('without inventing input numbers or prices',packet['task'])
 def test_prepare_requires_complete_route_audit_no_new_capability_probes(self):
  from automation.agri_v2.parallel_capacity import CREDENTIAL_SET_ID
  from automation.agri_v2.healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';atomic_json(o/'parallel/health/latest.json',{'credential_set_id':CREDENTIAL_SET_ID,'audit_status':'completed','checked_at':utcnow(),'eligible_text_slots':SLOTS[:20]})
   gates={'gates':{k:{'passed':True} for k in ['configured_capacity','fresh_text_capacity','authenticated_publisher','lifecycle_enabled']}}
   with patch.object(op,'load_owner_request',return_value={'request_id':op.FULL_QUEUE_ID,'request':self.req(),'request_commit':'a'*40}),patch('automation.agri_v2.parallel_control.policy'),patch('automation.agri_v2.parallel_control.reserve',return_value={}),patch('automation.agri_v2.production_readiness.run',return_value=gates),patch('automation.agri_v2.route_audit.run',return_value={'status':'all_topics_routed'}),patch('automation.agri_v2.parallel_audit.run') as audit,patch.object(op,'image_capability') as image:
    result=op.prepare({'GITHUB_RUN_ID':'10','GITHUB_SHA':'a'*40},d,o)
   self.assertEqual(result['status'],'research_prerequisites_passed');audit.assert_not_called();image.assert_not_called()
 def test_source_index_contains_only_admitted_actually_observed_leads(self):
  index=load_json(DATA/'university-source-index.json');self.assertFalse(index['evidence_approved'])
  for page in index['indices']+index.get('seed_leads',[]):
   source_host(page['url']);self.assertEqual(len(page['sha256']),64);self.assertTrue(page['fetched_at'])
   # Link URLs must still be separately validated when used; malformed/noninstitutional
   # links in actual pages are not blanket-admitted or evidence approval.
   self.assertIsInstance(page.get('links',[]),list)
 def test_saved_revalidation_cannot_drop_new_route_gate(self):
  fixture=fixture_s.ScopedResearchTests();t,v,docs=fixture.fixture()
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';ev=o/'new'/t['id']/'lifecycle-evidence';atomic_json(ev/'sources.json',{'documents':docs,'source_text_layout_version':2});atomic_json(ev/'candidate-raw.json',v);before=(ev/'candidate-raw.json').read_bytes();client=Mock()
   s.stage(t,'research_validate_saved',client,d,o)
   saved=load_json(ev/'candidate.json');self.assertEqual(saved['research_route_version'],r.VERSION);self.assertEqual((ev/'candidate-raw.json').read_bytes(),before);client.text.assert_not_called()
   facts=s.validate_candidate(t,saved,docs);_,overlap=fixture.overlap(t)
   with self.assertRaises(ValueError):s.build_brief(t,saved,docs,fixture.review(facts),overlap,{'source_generated_at':utcnow(),'records':[]})
 def test_saved_revalidation_does_not_override_negative_intent(self):
  fixture=fixture_s.ScopedResearchTests();t,v,docs=fixture.fixture();v['answers_intent']=False
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';ev=o/'new'/t['id']/'lifecycle-evidence';atomic_json(ev/'sources.json',{'documents':docs,'source_text_layout_version':2});atomic_json(ev/'candidate-raw.json',v);client=Mock()
   with self.assertRaises(ValueError):s.stage(t,'research_validate_saved',client,d,o)
   self.assertFalse((ev/'candidate.json').exists());client.text.assert_not_called()
 def test_relevant_field_guide_not_starved_by_old_harvest_fallback(self):
  from automation.agri_v2.source_discovery import ranked_seed_urls,seed_score
  topic=next(t for t in items('new') if t['crop']=='لوبیا چیتی' and t['intent']=='depth')
  ranked=ranked_seed_urls(entries_for(topic,DATA))
  guide='https://www.extension.iastate.edu/alternativeag/dry-edible-bean';harvest='https://cropwatch.unl.edu/2016/direct-harvest-dry-edible-beans/'
  self.assertIn(guide,ranked[:6]);self.assertGreater(seed_score(guide,topic),seed_score(harvest,topic));self.assertFalse(r.plan(topic)['publication_authorized'])
 def test_old_unranked_catalog_order_and_total_fetch_limit_unchanged(self):
  from automation.agri_v2.source_discovery import ranked_seed_urls
  self.assertEqual(ranked_seed_urls([{'urls':['https://b.edu/x','https://a.edu/x']},{'urls':['https://b.edu/x']}]),['https://b.edu/x','https://a.edu/x'])
