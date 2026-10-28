import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from tests.agri_v2 import test_web_source_repair as fixtures
from automation.agri_v2 import web_source_repair as w,family_lifecycle as f
from automation.agri_v2.queue import load_json,atomic_json
class SourceCoverageCacheTests(unittest.TestCase):
 def setup(self,td):
  h=fixtures.WebSourceRepairTests();d,o,t,e,health,ev,v=h.setup(Path(td));h.plan_stage(d,o,t,e,ev);docs=load_json(ev/'sources.json')['documents'];return h,d,o,t,e,ev,docs
 def test_same_actual_text_negative_verdict_reused_without_model_or_approval(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev,docs=self.setup(td);client=Mock();client.text.return_value=h.verdict(t,False);value,hit=w.cached_coverage(t,h.plan(t),docs,client,1,ev/'real-search');again,hit2=w.cached_coverage(t,h.plan(t),docs,client,1,ev/'real-search');self.assertFalse(hit);self.assertTrue(hit2);self.assertEqual(value,again);client.text.assert_called_once();self.assertTrue(all(not r['covered'] for r in again['requirements']));self.assertFalse(load_json(next((ev/'real-search/coverage-cache').glob('*.json')))['scientific_acceptance'])
 def test_changed_text_url_topic_requirement_round_or_order_cannot_reuse(self):
  for kind in ('text','url','topic','requirement','round'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    h,d,o,t,e,ev,docs=self.setup(td);p=h.plan(t);client=Mock();client.text.return_value=h.verdict(t,False);w.cached_coverage(t,p,docs,client,1,ev/'real-search');round_number=1
    if kind=='text':docs[0]['text']+=' Changed actual text.'
    if kind=='url':docs[0]['url']+='-different'
    if kind=='topic':t=dict(t,title=t['title']+' changed')
    if kind=='requirement':p['requirements'][0]['need']+=' Changed scope.'
    if kind=='round':round_number=2
    _,hit=w.cached_coverage(t,p,docs,client,round_number,ev/'real-search');self.assertFalse(hit);self.assertEqual(client.text.call_count,2)
 def test_cache_corruption_stops_before_new_model_request(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev,docs=self.setup(td);client=Mock();client.text.return_value=h.verdict(t,False);w.cached_coverage(t,h.plan(t),docs,client,1,ev/'real-search');p=next((ev/'real-search/coverage-cache').glob('*.json'));row=load_json(p);row['verdict']['requirements'][0]['covered']=True;atomic_json(p,row)
   with self.assertRaises(w.RepairBlocked):w.cached_coverage(t,h.plan(t),docs,client,1,ev/'real-search')
   client.text.assert_called_once()
 def test_unknown_request_or_invalid_output_is_never_cached(self):
  from automation.agri_v2.client import TextProviderError
  for kind in ('unknown','invalid'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
    h,d,o,t,e,ev,docs=self.setup(td);client=Mock()
    if kind=='unknown':client.text.side_effect=TextProviderError(None,'text_transport_uncertain')
    else:client.text.return_value={'not':'a verdict'}
    with self.assertRaises(Exception):w.cached_coverage(t,h.plan(t),docs,client,1,ev/'real-search')
    self.assertFalse(list((ev/'real-search/coverage-cache').glob('*.json')))
 def test_temporary_fetch_retry_reuses_triage_but_preserves_original_attempts_and_sources(self):
  with tempfile.TemporaryDirectory() as td:
   h,d,o,t,e,ev,docs=self.setup(td);before=(ev/'sources.json').read_bytes();client=Mock();client.text.return_value=h.verdict(t,False)
   for run in ('first','second'):
    result=f.attempt(ev.parent,'research_refetch',run,lambda:w.refetch(t,client,d,o,e,fetcher=Mock(side_effect=TimeoutError()),search_fn=h.result),limit=1);self.assertEqual(result['status'],'stage_deferred')
   self.assertEqual(client.text.call_count,2);self.assertEqual(f.state(ev.parent,'research_refetch')['attempts'],0);self.assertEqual((ev/'sources.json').read_bytes(),before);receipt=load_json(ev/'model-source-refetch.json');self.assertFalse(receipt['scientific_acceptance']);self.assertFalse(receipt['repair_exhausted']);self.assertTrue(all(x['coverage_cache_hit'] for x in receipt['rounds']))
