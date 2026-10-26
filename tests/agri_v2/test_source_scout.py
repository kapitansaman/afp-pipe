import hashlib,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import Mock,patch
from email.message import Message
from automation.agri_v2 import research
from automation.agri_v2.source_loading import load_documents,valid_document
from automation.agri_v2.source_scout import scout,collect,select,ScoutBlocked
from automation.agri_v2.queue import utcnow,load_json

U='https://extension.one.edu/pumpkin-storage';V='https://extension.two.edu/pumpkin-storage'
def doc(u,**extra):
 text='Pumpkin fruit postharvest handling and storage evidence. '*30
 return dict(url=u,text=text,sha256=hashlib.sha256(text.encode()).hexdigest(),fetched_at=utcnow(),**extra)
def decision(ids=None,match=True):return dict(document_ids=['s0','s1'] if ids is None else ids,crop_and_intent_match=match,scope_limitations='Whole mature fruit only; not extracted edible seeds or local temperature prescriptions.',reason='The fetched independent institutions discuss the same crop part and storage intent.')
class Response:
 status=200
 def __init__(self,body=None,content='text/html'):
  self.body=body if body is not None else b'<main>'+b'Pumpkin storage evidence. '*40+b'</main>';self.headers=Message();self.headers['Content-Type']=content
 def read(self,n):return self.body[:n]
 def __enter__(self):return self
 def __exit__(self,*a):pass
class ScoutTests(unittest.TestCase):
 def test_no_catalog_means_no_model_url_hallucination(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);c=Mock();f=Mock()
   with self.assertRaisesRegex(ScoutBlocked,'insufficient'):scout({'id':'x'},[],c,f,p,research.source_host,p/'ev')
   c.text.assert_not_called();f.assert_not_called();self.assertEqual(load_json(p/'ev/source-scout-report.json')['model_calls'],0)
 def test_valid_selection_is_not_publication_authorization(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);c=Mock();c.text.return_value=decision()
   result=scout({'id':'x'},[{'urls':[U,V]}],c,doc,p,research.source_host,p/'ev')
   self.assertEqual(len(result),2);self.assertEqual(c.text.call_args.kwargs,{'attempts':1})
   self.assertFalse(load_json(p/'ev/source-scout-report.json')['publication_authorized'])
 def test_unknown_duplicate_single_institution_or_scope_failure_blocks(self):
  for d,reason in [(decision(['s0','invented']),'unknown'),(decision(['s0','s0']),'duplicate'),(decision([]),'independent'),(decision(match=False),'scope')]:
   with self.subTest(reason=reason):
    c=Mock();c.text.return_value=d
    with self.assertRaisesRegex(ScoutBlocked,reason):select({'id':'x'},[],[doc(U),doc(V)],c,research.source_host)
 def test_non_boolean_scope_and_missing_reason_block(self):
  for d in [dict(decision(),crop_and_intent_match='true'),dict(decision(),reason='ok'),dict(decision(),urls=['https://invented.edu'])]:
   c=Mock();c.text.return_value=d
   with self.assertRaises(ScoutBlocked):select({'id':'x'},[],[doc(U),doc(V)],c,research.source_host)
 def test_real_observed_links_not_guessed_paths(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);seen=[]
   def fetch(u):
    seen.append(u)
    return doc(u,links=[{'url':V,'label':'Pumpkin storage'}, {'url':'https://evil.org/pumpkin','label':'Pumpkin'}, {'url':U+'?secret=1','label':'Pumpkin'}])
   docs,r=collect([{'urls':[U],'discovery_terms':['pumpkin']}],fetch,p,research.source_host,p/'ev')
   self.assertEqual(seen,[U,V]);self.assertEqual(r['independent_institutions'],2);self.assertEqual(r['observed_links'][0]['observed_on'],U)
 def test_broken_seeds_recover_from_configured_hub_within_total_budget(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);hub='https://extension.one.edu/vegetables';seen=[]
   def fetch(u):
    seen.append(u)
    if u==U:raise ValueError('404')
    return doc(u,links=[{'url':V,'label':'Pumpkin storage'}])
   docs,r=collect([{'urls':[U],'discovery_urls':[hub],'discovery_terms':['pumpkin']}],fetch,p,research.source_host,p/'ev')
   self.assertEqual(seen,[U,hub,V]);self.assertLessEqual(r['requested'],12)
 def test_fetch_validation_failure_never_enters_documents_or_cache(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);bad=doc(U);bad['sha256']='fake'
   self.assertEqual(load_documents([U],lambda _:bad,p,research.source_host),[]);self.assertFalse((p/'source-cache').exists())
 def test_redirect_canonical_document_validates_and_deduplicates(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);canonical=U+'/new'
   def fetch(u):return doc(canonical,requested_url=u,redirect_chain=[u,canonical])
   docs=load_documents([U,U+'/old'],fetch,p,research.source_host)
   self.assertEqual(len(docs),1);self.assertEqual(docs[0]['url'],canonical)
 def test_redirect_cache_cannot_claim_unvalidated_final_url(self):
  bad=doc(V,requested_url=U,redirect_chain=[U])
  self.assertFalse(valid_document(bad,U,research.source_host))

class SafeFetchTests(unittest.TestCase):
 def dns(self,h,*a,**kw):return [(2,1,6,'',('127.0.0.1' if h.startswith('private.') else '8.8.8.8',443))]
 def redir(self,u,target):return urllib.error.HTTPError(u,301,'redirect',{'Location':target},None)
 def test_safe_redirect_and_link_extraction(self):
  op=Mock();op.open.side_effect=[self.redir(U,V),Response(b'<main>'+b'Pumpkin evidence. '*60+b'<a href="/pumpkin-care">pumpkin care</a></main>')]
  with patch.object(research.socket,'getaddrinfo',side_effect=self.dns),patch.object(research.urllib.request,'build_opener',return_value=op):d=research.fetch_source(U)
  self.assertEqual(d['url'],V);self.assertEqual(d['requested_url'],U);self.assertEqual(d['redirect_chain'],[U,V]);self.assertEqual(d['links'][0]['url'],'https://extension.two.edu/pumpkin-care')
 def test_redirect_private_http_credentials_and_noninstitutional_rejected(self):
  for target in ['https://private.one.edu/x','http://extension.two.edu/x','https://user:secret@extension.two.edu/x','https://evil.example/x']:
   with self.subTest(target=target):
    op=Mock();op.open.side_effect=[self.redir(U,target),Response()]
    with patch.object(research.socket,'getaddrinfo',side_effect=self.dns),patch.object(research.urllib.request,'build_opener',return_value=op):
     with self.assertRaises(research.ResearchBlocked):research.fetch_source(U)
    self.assertEqual(op.open.call_count,1)
 def test_redirect_loop_and_limit(self):
  for targets in [[V,U],[U+'/'+str(i) for i in range(6)]]:
   op=Mock();op.open.side_effect=[self.redir(U,t) for t in targets]
   with patch.object(research.socket,'getaddrinfo',side_effect=self.dns),patch.object(research.urllib.request,'build_opener',return_value=op):
    with self.assertRaisesRegex(research.ResearchBlocked,'redirect'):research.fetch_source(U)
   self.assertLessEqual(op.open.call_count,5)
 def test_bad_hosts_pdf_oversize_and_short_text_rejected(self):
  for u in ['https://.extension.umn.edu/x','https://a..edu/x','https://-bad.edu/x','https://good.edu:bad/x','https://good.edu/\npath']:
   with self.assertRaises(research.ResearchBlocked):research.source_host(u)
  for r in [Response(b'PDF data','application/pdf'),Response(b'x'*1500001),Response(b'<main>short</main>')]:
   op=Mock();op.open.return_value=r
   with patch.object(research.socket,'getaddrinfo',side_effect=self.dns),patch.object(research.urllib.request,'build_opener',return_value=op):
    with self.assertRaises(research.ResearchBlocked):research.fetch_source(U)
