import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import regional_revision as r,regional_revision_context as c,regional_sources
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.pipeline import digest
import test_regional_revision as fixtures
class RevisionContextTests(unittest.TestCase):
 def setup(self,t):
  data,out,topic,env,health,req=fixtures.RegionalRevisionTests().setup(t);root=out/'regional-revisions'/r.ID
  old={'status':'revision_needs_attention','model_calls':3,'source_search':{'unknown_requests':0},'input_binding':req['input_binding']};atomic_json(root/'report.json',old)
  raws={'search-plan':{},'local-extract':{'answers_intent':False,'facts':[]},'international-extract':{'answers_intent':False,'facts':[]}}
  for name,raw in raws.items():atomic_json(root/'calls'/(name+'.raw.json'),raw);atomic_json(root/'calls'/(name+'.receipt.json'),{'status':'received','raw_sha256':digest(raw)})
  text='Alfalfa harvest traffic requires a firm dry soil surface and sufficient water in the root zone; irrigation scheduling depends on actual soil water measurements. '*7
  docs=[{'url':'https://example.edu/alfalfa','text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}];atomic_json(root/'phases/international/new'/r.TOPIC/'lifecycle-evidence/sources.json',{'documents':docs})
  req2={'version':1,'request_id':c.ID,'revision_request_id':r.ID,'prepare_authorized':True,'publication_authorized':False,'max_remaining_model_calls':5,'max_search_requests':0,'max_continuations':1,'reset_original_attempts':False,'prior_report_sha256':digest(old),'documents_sha256':digest(docs)};atomic_json(data/'regional-revision-context-request.json',req2)
  return data,out,topic,env,root,req2,docs
 def test_only_confirmed_empty_extraction_and_bound_documents_can_resume(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,docs=self.setup(t);self.assertEqual(c.validate(req,data,out)[1],docs)
   atomic_json(root/'calls/international-extract.receipt.json',{'status':'reserved'})
   with self.assertRaisesRegex(ValueError,'uncertain_or_changed'):c.validate(req,data,out)
 def test_no_extra_budget_or_search_or_old_approval_can_be_authorized(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,docs=self.setup(t)
   for k,v in [('max_remaining_model_calls',6),('max_search_requests',1),('publication_authorized',True),('reset_original_attempts',True)]:
    with self.assertRaises(ValueError):c.validate(dict(req,**{k:v}),data,out)
   docs[0]['text']+=' changed';atomic_json(root/'phases/international/new'/r.TOPIC/'lifecycle-evidence/sources.json',{'documents':docs})
   with self.assertRaisesRegex(ValueError,'documents_changed'):c.validate(req,data,out)
 def test_retrieval_keeps_literal_chunks_ids_and_all_source_contexts(self):
  cat=[{'id':str(i),'source_url':'https://example.edu/alfalfa' if i<60 else 'https://other.edu/alfalfa','quote':('harvest irrigation root-zone traffic ' if i%3 else 'unrelated chronology ')+str(i)} for i in range(90)]
  focused=r.focused_catalog(cat);self.assertEqual(len(focused),32);self.assertEqual({x['source_url'] for x in focused},{x['source_url'] for x in cat});self.assertTrue(all(x in cat for x in focused));self.assertEqual(len({x['id'] for x in focused}),32)
 def test_negative_review_stops_no_original_change_no_automatic_replay(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,docs=self.setup(t);before=r.inputs(data,out);old=(root/'report.json').read_bytes();factory=Mock(return_value=Mock())
   with patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(c,'get_topic',return_value=topic),patch.object(r,'extract_review',side_effect=regional_sources.RegionalBlocked('regional_applicability_not_approved')):
    result=c.run(env,data,out,client_factory=factory);again=c.run(env,data,out,client_factory=factory)
   self.assertEqual(result['status'],'revision_needs_attention');self.assertEqual(result['total_revision_receipts'],3);self.assertEqual(result['search_requests'],0);self.assertEqual(result['post_mutations'],0);self.assertEqual(r.inputs(data,out),before);self.assertEqual((root/'report.json').read_bytes(),old);self.assertEqual(again['status'],'context_repair_already_reserved_no_replay');self.assertEqual(factory.call_count,1)
   self.assertNotIn('AFP_SOURCE_SEARCH_API_KEY',factory.call_args.kwargs['env']);self.assertNotIn('AFP_WP_APP_PASSWORD',factory.call_args.kwargs['env'])
 def test_interrupted_continuation_remains_fenced(self):
  with tempfile.TemporaryDirectory() as t:
   data,out,topic,env,root,req,docs=self.setup(t)
   with patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=None),patch.object(c,'get_topic',return_value=topic),patch.object(r,'extract_review',side_effect=KeyboardInterrupt()):
    with self.assertRaises(KeyboardInterrupt):c.run(env,data,out,client_factory=Mock(return_value=Mock()))
   result=c.run(env,data,out,client_factory=Mock());self.assertEqual(result['status'],'context_repair_already_reserved_no_replay')
