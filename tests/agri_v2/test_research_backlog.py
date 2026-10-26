import concurrent.futures,copy,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import research_backlog as b,family_scheduler as scheduler,source_scout,scoped_sources,research,source_discovery
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.source_loading import load_documents
from automation.agri_v2.source_policy import VERSION as POLICY
from tests.agri_v2 import test_family_scheduler as fixtures

def allocate(data,out):return scheduler.allocate(data,out,allow_deferral=True)

class ResearchBacklogTests(unittest.TestCase):
 def setup(self,root):
  data,out,topics=fixtures.FamilySchedulerTests().setup(root,26)
  atomic_json(data/'family-lifecycle-policy.json',{'max_attempts_per_stage':3})
  with patch.object(scheduler,'items',return_value=topics):assign=scheduler.allocate(data,out)
  return data,out,topics,assign
 def failed(self,data,out,t,reason='scoped_four_to_twelve_facts_required',stage='research_validate_saved',attempts=3):
  ev=out/'new'/t['id']/'lifecycle-evidence';state=out/'new'/t['id']/'lifecycle'/stage/'state.json'
  atomic_json(ev/'sources.json',{'documents':[{'url':'https://x.edu/source'}]})
  atomic_json(ev/'candidate-raw.json',{'answers_intent':True,'facts':[]})
  atomic_json(state,{'attempts':attempts,'status':'failed','last_run_id':'123','failure':{'category':reason},'history':[{'preserve':'original'}]})
  return ev,state
 def gap(self,ev,t,**changes):
  r={'topic_id':t['id'],'source_policy_version':POLICY,'bounded_discovery_completed':True,'temporary_source_failure':False,'requested':5,'source_sufficiency':{'satisfied':False},'blocking_kind':'insufficient_verified_source_coverage'};r.update(changes);atomic_json(ev/'source-discovery-report.json',r)
 def test_exhausted_evidence_moves_to_backlog_and_only_its_family_gets_next_topic(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,topics,a=self.setup(Path(td));ev,sp=self.failed(d,o,topics[0]);before={p:p.read_bytes() for p in (sp,ev/'sources.json',ev/'candidate-raw.json')}
   with patch.object(scheduler,'items',return_value=topics):r=allocate(d,o)
   self.assertEqual(r['assigned_count'],20);self.assertEqual(r['families'][0]['topic_id'],topics[20]['id']);self.assertEqual(r['families'][1:],a['families'][1:]);self.assertEqual(r['research_backlog_count'],1)
   row=r['research_backlog'][topics[0]['id']];self.assertEqual(row['kind'],'evidence_preparation_exhausted');self.assertFalse(row['automatic_retry_authorized']);self.assertFalse(row['publication_authorized']);self.assertEqual(row['attempts_preserved'],3)
   self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertEqual(r['history'][-1]['completion'],'deferred_to_research_backlog')
 def test_transient_or_malformed_model_outputs_do_not_release_ownership(self):
  for code in ('provider_unavailable','text_empty_or_invalid_content','text_json_invalid','unspecified','scoped_review_v2_rejected_or_uncertain'):
   with self.subTest(code=code),tempfile.TemporaryDirectory() as td:
    d,o,topics,a=self.setup(Path(td));self.failed(d,o,topics[0],reason=code)
    with patch.object(scheduler,'items',return_value=topics):r=allocate(d,o)
    self.assertEqual(a['families'],r['families']);self.assertEqual(r['research_backlog_count'],0)
 def test_remaining_attempts_are_not_bypassed_by_evidence_deferral(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,a=self.setup(Path(td));self.failed(d,o,t[0],attempts=2);self.assertIsNone(b.deferral(t[0],d,o))
 def test_bounded_source_gap_can_release_without_resetting_its_one_attempt(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,a=self.setup(Path(td));ev,sp=self.failed(d,o,t[0],reason='unspecified',stage='research_sources',attempts=1);self.gap(ev,t[0]);row=b.deferral(t[0],d,o)
   self.assertEqual(row['kind'],'additional_source_discovery_required');self.assertEqual(load_json(sp)['attempts'],1)
 def test_old_policy_or_temporary_source_failure_is_not_a_research_gap(self):
  for change in ({'source_policy_version':'old-two-source-policy'},{'temporary_source_failure':True},{'source_sufficiency':{'satisfied':True}},{'requested':13},{'topic_id':'agri-ffffffffffff'}):
   with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
    d,o,t,a=self.setup(Path(td));ev,sp=self.failed(d,o,t[0],stage='research_sources',attempts=1);self.gap(ev,t[0],**change);self.assertIsNone(b.deferral(t[0],d,o))
 def test_accepted_work_or_scientific_review_or_hold_never_deferred(self):
  for kind in ('brief','article','receipt','hold','scientific-review','overlap','missing-raw-review-but-attempted'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    d,o,t,a=self.setup(Path(td));ev,sp=self.failed(d,o,t[0]);folder=ev.parent
    if kind=='brief':atomic_json(d/'briefs'/(t[0]['id']+'.json'),{})
    elif kind=='article':atomic_json(folder/'article.json',{})
    elif kind=='receipt':atomic_json(folder/'wordpress-receipt.json',{'public_verified':False})
    elif kind=='hold':atomic_json(d/'config.json',{'publication_holds':{t[0]['id']:'keep'}})
    elif kind=='scientific-review':atomic_json(ev/'review-raw.json',{'decision':'reject'})
    elif kind=='overlap':atomic_json(ev/'overlap.json',{'decision':'overlap'})
    else:atomic_json(folder/'lifecycle/research_review/state.json',{'attempts':1,'status':'failed'})
    self.assertIsNone(b.deferral(t[0],d,o))
 def test_repeat_and_new_catalog_do_not_automatically_return_deferred_topic(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,a=self.setup(Path(td));self.failed(d,o,t[0])
   with patch.object(scheduler,'items',return_value=t):
    first=allocate(d,o);raw=(o/'parallel/families/assignments.json').read_bytes();second=allocate(d,o)
    self.assertEqual(raw,(o/'parallel/families/assignments.json').read_bytes())
    atomic_json(d/'research-source-catalog.json',{'version':900,'entries':[]});third=allocate(d,o)
   self.assertEqual(first['research_backlog'],third['research_backlog']);self.assertEqual(first['families'],second['families'])
 def test_atomic_write_failure_cannot_detach_topic_without_backlog(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,a=self.setup(Path(td));self.failed(d,o,t[0]);path=o/'parallel/families/assignments.json';before=path.read_bytes()
   with patch.object(scheduler,'items',return_value=t),patch.object(scheduler,'atomic_json',side_effect=OSError('disk failure')),self.assertRaises(OSError):allocate(d,o)
   self.assertEqual(before,path.read_bytes())
 def test_concurrent_reassignment_has_no_duplicate_topic_or_history(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,a=self.setup(Path(td));self.failed(d,o,t[0])
   with patch.object(scheduler,'items',return_value=t),concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:rows=list(ex.map(lambda _:allocate(d,o),range(3)))
   self.assertTrue(all(r['families']==rows[0]['families'] for r in rows));self.assertEqual(len(rows[0]['history']),1);self.assertEqual(len({r['topic_id'] for r in rows[0]['families']}),20)
 def test_single_family_pilot_disables_general_reassignment_at_both_allocations(self):
  from tests.agri_v2 import test_family_lifecycle as lifecycle_fixtures
  from automation.agri_v2 import family_lifecycle as lifecycle,white_bean_pilot
  from unittest.mock import Mock
  with tempfile.TemporaryDirectory() as td:
   d,o,t,env,h=lifecycle_fixtures.FamilyLifecycleTests().setup(td)
   t=dict(t,id=white_bean_pilot.TOPIC);env['AFP_WHITE_BEAN_PILOT']='1';wp=Mock()
   wp.inventory.return_value={'source_generated_at':utcnow(),'records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   def worker(topic,workspace,*args):return topic['id'],workspace/'data',workspace/'out',{'topic_id':topic['id'],'status':'blocked'}
   with patch.object(lifecycle,'allocate',return_value={}) as allocation,patch.object(lifecycle,'assigned_topics',return_value=[t]),patch.object(lifecycle,'next_stage',return_value=('blocked','review_required')):
    result=lifecycle.run(env,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   self.assertEqual(result['status'],'completed');self.assertEqual(allocation.call_count,2)
   self.assertTrue(all(c.kwargs=={'allow_deferral':False} for c in allocation.call_args_list))
 def test_diagnostic_allocation_does_not_reassign_without_explicit_deferral_mode(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,a=self.setup(Path(td));self.failed(d,o,t[0])
   with patch.object(scheduler,'items',return_value=t):r=scheduler.allocate(d,o)
   self.assertEqual(r['families'],a['families']);self.assertEqual(r['research_backlog_count'],0)
 def test_corrupt_active_and_deferred_ownership_fails_closed(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,a=self.setup(Path(td));ev,sp=self.failed(d,o,t[0]);a['research_backlog']={t[0]['id']:b.deferral(t[0],d,o)};atomic_json(o/'parallel/families/assignments.json',a)
   with patch.object(scheduler,'items',return_value=t),self.assertRaisesRegex(ValueError,'both active and deferred'):allocate(d,o)

class DiscoveryTests(unittest.TestCase):
 def document(self,url,links=None):
  text='Actual university source with crop scope and original unit evidence. '*20
  return {'url':url,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':utcnow(),'links':links or []}
 def test_catalog_fallback_stays_same_crop_and_never_claims_intent_coverage(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);atomic_json(p/'research-source-catalog.json',{'entries':[{'crops':['bean'],'intents':['storage'],'scope':'Dry bean seed storage only','urls':['https://x.edu/beans']},{'crops':['tomato'],'intents':['yield'],'urls':['https://y.edu/tomato']}]})
   rows=source_discovery.entries_for({'crop':'bean','intent':'yield'},p);self.assertEqual(len(rows),1);self.assertTrue(rows[0]['discovery_only']);self.assertIn('NOT established',rows[0]['scope']);self.assertIn('yield',rows[0]['discovery_terms'])
 def test_pdf_links_are_discovered_only_when_pdf_fetch_is_explicitly_enabled(self):
  for enabled in (False,True):
   with self.subTest(enabled=enabled),tempfile.TemporaryDirectory() as td:
    p=Path(td);seen=[];u='https://x.edu/bean';v='https://y.edu/bean-yield.pdf'
    def fetch(url):seen.append(url);return self.document(url,[{'url':v,'label':'Bean yield trial'}])
    docs,r=source_scout.collect([{'urls':[u],'discovery_terms':['yield']}],fetch,p,research.source_host,p/'ev',allow_pdf=enabled,topic_id='agri-000000000001')
    self.assertEqual(v in seen,enabled);self.assertLessEqual(r['requested'],12)
 def test_link_expansion_not_stopped_just_because_two_unrelated_pages_were_fetched(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);seen=[];u='https://x.edu/bean';v='https://y.edu/bean';pdf='https://x.edu/bean-yield.pdf'
   def fetch(url):seen.append(url);return self.document(url,[{'url':pdf,'label':'yield trial'}])
   source_scout.collect([{'urls':[u,v],'discovery_terms':['yield']}],fetch,p,research.source_host,p/'ev',allow_pdf=True)
   self.assertIn(pdf,seen)
 def test_temporary_fetch_failure_is_never_labeled_insufficient_research(self):
  for exc in (TimeoutError(),OSError('dns failure'),research.ResearchBlocked('scoped_source_http_503')):
   with self.subTest(exc=type(exc).__name__),tempfile.TemporaryDirectory() as td:
    p=Path(td)
    def fetch(u):raise exc
    docs,r=source_scout.collect([{'urls':['https://x.edu/a']}],fetch,p,research.source_host,p/'ev',allow_pdf=True)
    self.assertTrue(r['temporary_source_failure']);self.assertIsNone(r['blocking_kind'])
 def test_empty_catalog_is_documented_as_no_leads_not_no_scientific_literature(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);docs,r=source_scout.collect([],lambda _:None,p,research.source_host,p/'ev',topic_id='agri-000000000001')
   self.assertEqual(r['blocking_kind'],'discovery_catalog_empty');self.assertEqual(r['requested'],0);self.assertEqual(r['source_policy_version'],POLICY)
 def test_old_cache_without_observed_link_support_is_refetched_for_scoped_discovery(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);url='https://x.edu/bean';old=self.document(url);atomic_json(p/'source-cache'/(hashlib.sha256(url.encode()).hexdigest()+'.json'),old);seen=[]
   def fetch(u):seen.append(u);return dict(old,source_link_discovery_version=1)
   load_documents([url],fetch,p,research.source_host,minimum_link_version=1);self.assertEqual(seen,[url])
 def test_scoped_html_retains_safe_observed_links_and_rejects_external_leads(self):
  from tests.agri_v2.test_scoped_sources import ScopedSourceTests
  helper=ScopedSourceTests();body=('<p>'+'Bean research evidence '*40+'</p><a href="/bean-yield.pdf">yield</a><a href="https://evil.org/x">yield</a>').encode();op=helper.setup('text/html',body)
  with patch.object(scoped_sources.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch.object(scoped_sources.urllib.request,'build_opener',return_value=op):doc=scoped_sources.fetch('https://x.edu/bean')
  self.assertEqual(doc['links'],[{'url':'https://x.edu/bean-yield.pdf','label':'yield'}]);self.assertEqual(doc['source_link_discovery_version'],1)
