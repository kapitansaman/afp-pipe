import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_sources as r,regional_continuation as c,language_review_queue as q,multilingual as m
from automation.agri_v2.queue import atomic_json,load_json,utcnow
from automation.agri_v2.pipeline import digest
from automation.agri_v2.translation_review_repair import request
from automation.agri_v2.client import TextProviderError
from automation.agri_v2.parallel_pool import PoolDeferred
from test_multilingual import article,response
class RegionalContinuationTests(unittest.TestCase):
 def setup(self,t,status='approved',calls=3):
  root=Path(t);data=root/'data';out=root/'out';topic={'id':'agri-000000000001','title':'هویج','crop':'هویج','intent':'irrig_interval'};folder=out/'new'/topic['id'];lang='en-US';a=article();raw=response(a,lang);target=m.render_translation(a,raw,lang)
  atomic_json(data/'regional-research-policy.json',r.POLICY);atomic_json(data/'language-review-policy.json',q.DEFAULT_POLICY);atomic_json(data/'briefs'/(topic['id']+'.json'),{'approved_facts':[]});atomic_json(folder/'article.json',a);atomic_json(q.target(folder,lang),target);atomic_json(q.target(folder,lang).with_suffix('.raw.json'),raw);atomic_json(q.proof_path(folder,lang),{'article_sha256':digest(a),'translation_sha256':digest(target),'review':{'faithful':True,'issues':[]}})
  row={'topic_id':topic['id'],'language':lang,'title':topic['title'],'status':status,'article_sha256':digest(a),'attempts':3,'model_calls_spent':calls,'history':[],'next_attempt_at':None};atomic_json(q.path(folder,lang),row)
  return data,out,topic,folder,lang,a,row
 def execute(self,data,topic,folder,lang,client,callback):
  ready=[]
  def research(*args):callback(*args);ready.append(True)
  def require(*args):
   if not ready:raise r.RegionalBlocked('language_requires_independent_regional_research')
   return ['https://example.edu/evidence']
  with patch.object(q,'source_checked'),patch.object(c,'get_topic',return_value=topic),patch.object(r,'local_research',side_effect=research),patch.object(r,'require_local',side_effect=require):return q.run_item(q.path(folder,lang),client,data)
 def test_local_and_international_requests_have_distinct_stable_identities(self):
  from test_regional_sources import RegionalSourcesTests
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);factory=RegionalSourcesTests();topic=factory.topic();docs=[factory.doc('https://one.ac.ir/carrot'),factory.doc('https://other.edu/carrot')];seen=set()
   def search(query,env,ident):
    if ident in seen:raise PoolDeferred('Search request already reserved; no replay')
    seen.add(ident);return {'results':[{'url':d['url'],'title':'Observed technical lead','description':'Discovery not evidence'} for d in docs]}
   client=SimpleNamespace(env={'AFP_SOURCE_SEARCH_API_KEY':'fixture','AFP_PARALLEL_POOL_DB':'fixture'})
   for international in (False,True):r.collect(topic,'fa-IR',client,root,root/'family',fetcher=lambda u:next(d for d in docs if d['url']==u),search_fn=search,international=international)
   self.assertEqual(len(seen),4);self.assertEqual(sum('-local-' in s for s in seen),2);self.assertEqual(sum('-international-' in s for s in seen),2)
 def test_existing_fidelity_can_get_regional_evidence_without_fourth_semantic_attempt(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t);client=Mock();client.text.return_value={'approved':True};files=[q.target(folder,lang),q.target(folder,lang).with_suffix('.raw.json'),q.proof_path(folder,lang)];before=[p.read_bytes() for p in files]
   def research(topic,a,b,lang,client,data,out,folder,root,limit):request(client,root,'regional-evidence-review',{'task':'Independent evidence review'},limit)
   result=self.execute(data,topic,folder,lang,client,research);after=load_json(q.path(folder,lang));self.assertEqual(result['status'],'approved');self.assertEqual(after['attempts'],3);self.assertEqual(after['model_calls_spent'],4);self.assertEqual([p.read_bytes() for p in files],before);self.assertEqual(load_json(c.path(folder,lang))['attempts'],1);self.assertEqual(client.text.call_count,1)
 def test_no_research_call_when_existing_total_item_budget_is_exhausted(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t,calls=12);client=Mock()
   result=self.execute(data,topic,folder,lang,client,lambda *_:self.fail('No remaining budget'));self.assertEqual(result['status'],'regional_budget_exhausted');client.text.assert_not_called();self.assertEqual(load_json(q.path(folder,lang))['model_calls_spent'],12)
 def test_unknown_research_response_requires_reconciliation_and_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t);client=Mock();client.text.side_effect=TextProviderError(None,'network_or_timeout')
   def research(topic,a,b,lang,client,data,out,folder,root,limit):request(client,root,'regional-evidence-review',{'task':'Independent evidence review'},limit)
   result=self.execute(data,topic,folder,lang,client,research);self.assertEqual(result['status'],'regional_reconciliation_required');self.assertEqual(load_json(q.path(folder,lang))['attempts'],3);self.assertEqual(load_json(q.path(folder,lang))['model_calls_spent'],4)
   result=self.execute(data,topic,folder,lang,client,research);self.assertEqual(result['status'],'not_due');self.assertEqual(client.text.call_count,1)
 def test_reserved_continuation_never_replays_on_an_old_linguistic_approval(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t);client=Mock()
   # Simulate interruption after durable reservation, before any provider response.
   def stop(*args):raise KeyboardInterrupt()
   with self.assertRaises(KeyboardInterrupt):self.execute(data,topic,folder,lang,client,stop)
   self.assertEqual(load_json(c.path(folder,lang))['status'],'reserved')
   result=self.execute(data,topic,folder,lang,client,lambda *_:self.fail('Uncertain work replayed'));self.assertEqual(result['status'],'reconciliation_required');client.text.assert_not_called()
 def test_genuine_negative_or_unbound_linguistic_proof_is_never_promoted(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t,status='needs_attention');row['pending_issues']=[{'id':0,'detail':'Meaning defective'}];atomic_json(q.path(folder,lang),row);self.assertFalse(c.eligible(row,folder));row.pop('pending_issues');self.assertFalse(c.eligible(row,folder))
   atomic_json(q.proof_path(folder,lang),{'article_sha256':digest(a),'review':{'faithful':False,'issues':[]}});self.assertFalse(c.eligible(dict(row,status='approved'),folder))
 def test_legacy_admission_failure_requires_confirmed_regional_responses_and_local_search(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t,status='needs_attention');row['last_failure']={'kind':'admission_deferred','category':'model_capacity_deferred'};root=folder/'review-queue/attempts'/lang/'3';raw={'queries':['two local searches','another local query']};atomic_json(root/'regional-query-plan.raw.json',raw);atomic_json(root/'regional-query-plan.receipt.json',{'status':'received','raw_sha256':digest(raw)});self.assertFalse(c.eligible(row,folder))
   local=folder/'regional-research'/lang/'local';atomic_json(local/'search-plan.json',raw)
   for i,query in enumerate(raw['queries']):atomic_json(local/('search-'+str(i)+'.json'),{'query_sha256':digest(query),'result':{'results':[]}})
   self.assertTrue(c.eligible(row,folder));atomic_json(root/'regional-query-plan.receipt.json',{'status':'reserved'});self.assertFalse(c.eligible(row,folder))
 def test_rejected_regional_work_backs_off_without_changing_linguistic_attempts(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t);client=Mock()
   def reject(*_):raise r.RegionalBlocked('regional_applicability_not_approved')
   result=self.execute(data,topic,folder,lang,client,reject);self.assertEqual(result['status'],'regional_waiting');state=load_json(c.path(folder,lang));self.assertIsNotNone(state['next_attempt_at']);self.assertFalse(c.due(folder,lang));self.assertEqual(load_json(q.path(folder,lang))['attempts'],3)
 def test_continuation_binding_rejects_changed_brief_and_does_not_reset_ledger(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,folder,lang,a,row=self.setup(t);client=Mock()
   def reject(*_):raise r.RegionalBlocked('regional_applicability_not_approved')
   self.execute(data,topic,folder,lang,client,reject);state=load_json(c.path(folder,lang));state.update(status='waiting',next_attempt_at='2020-01-01T00:00:00+00:00');atomic_json(c.path(folder,lang),state);atomic_json(data/'briefs'/(topic['id']+'.json'),{'approved_facts':['changed']})
   with self.assertRaisesRegex(ValueError,'binding_changed'):self.execute(data,topic,folder,lang,client,lambda *_:self.fail('Changed input accepted'))
   self.assertEqual(load_json(c.path(folder,lang))['attempts'],1);client.text.assert_not_called()
