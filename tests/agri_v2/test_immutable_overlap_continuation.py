import copy,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import scoped_research as s,overlap_continuation as c
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2.pipeline import digest
class ImmutableOverlapContinuationTests(unittest.TestCase):
 def setup(self,td):
  root=Path(td);d=root/'data';o=root/'out';t={'id':'agri-000000000001','family_id':'family-01','crop':'یونجه','title':'آبیاری یونجه','related_existing_ids':[11]};folder=o/'new'/t['id'];bundle={'topic_id':t['id'],'family_id':t['family_id'],'related_ids':[11],'documents':[{'id':11,'sha256':'a'*64,'text_truncated':False}],'unavailable':[],'fetched_at':'old'};brief={'review_mode':s.MODE,'overlap_audit':{'existing_content_sha256':s.content_digest(bundle)}};atomic_json(d/'briefs'/(t['id']+'.json'),brief);atomic_json(folder/'lifecycle-evidence/existing-content.json',bundle);wp=Mock();wp.user_id=7;return d,o,t,folder,bundle,brief,wp
 def run_fetch(self,d,o,t,bundle,wp,inventory=None):
  inventory=inventory or {'records':[{'id':11,'title':'یونجه پیشین'}]}
  def collect(topics,*a,**k):
   self.seen=topics;return {t['id']:copy.deepcopy(bundle)}
  with patch('automation.agri_v2.pipeline.check_brief'),patch.object(s,'validate_overlap'),patch('automation.agri_v2.family_trial.collect_existing',side_effect=collect):return s.prefetch_existing([t],inventory,wp,o,'999',data=d)
 def test_approved_snapshot_never_changes_when_context_unchanged(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,t,f,b,brief,wp=self.setup(td);p=f/'lifecycle-evidence/existing-content.json';before=p.read_bytes();fresh=copy.deepcopy(b);fresh['fetched_at']='new';self.run_fetch(d,o,t,fresh,wp);self.assertEqual(before,p.read_bytes());proof=load_json(f/'lifecycle-evidence/overlap-refresh/999.json');self.assertTrue(proof['non_owned_context_unchanged']);self.assertFalse(proof['approval_granted'])
 def owned(self,f,t,brief,wp):
  raw='<!-- afp-agri-v2:'+t['id']+' -->\n<p>approved</p>';article={'title':t['title']};atomic_json(f/'article.json',article);atomic_json(f/'lifecycle-publication-validation.json',{'article_sha256':digest(article),'brief_sha256':digest(brief)});receipt={'topic_id':t['id'],'post_id':22,'url':'https://navar-abyari.ir/owned/','public_verified':True,'publication_content_sha256':hashlib.sha256(raw.encode()).hexdigest()};atomic_json(f/'wordpress-receipt.json',receipt);wp.call.return_value=({'id':22,'status':'publish','author':7,'link':receipt['url'],'content':{'raw':raw}},{});return receipt
 def test_only_authenticated_unchanged_owned_source_excluded(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,t,f,b,brief,wp=self.setup(td);self.owned(f,t,brief,wp);self.run_fetch(d,o,t,b,wp,{'records':[{'id':22,'title':t['title']},{'id':11,'title':'یونجه قبلی'}]});self.assertEqual(self.seen[0]['related_existing_ids'],[11]);self.assertEqual(load_json(f/'lifecycle-evidence/overlap-refresh/999.json')['verified_owned_ids_excluded'],[22])
 def test_foreign_or_edited_post_is_never_excluded(self):
  for kind in ('author','marker','bytes'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory()as td:
    d,o,t,f,b,brief,wp=self.setup(td);self.owned(f,t,brief,wp);post=wp.call.return_value[0]
    if kind=='author':post['author']=99
    elif kind=='marker':post['content']['raw']='foreign'
    else:post['content']['raw']+='edited'
    with self.assertRaises(ValueError):self.run_fetch(d,o,t,b,wp)
 def test_new_nonowned_context_blocks_without_rewriting_approval(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,t,f,b,brief,wp=self.setup(td);p=f/'lifecycle-evidence/existing-content.json';before=p.read_bytes();fresh=copy.deepcopy(b);fresh['related_ids'].append(33);fresh['documents'].append({'id':33,'sha256':'b'*64,'text_truncated':False})
   with self.assertRaisesRegex(s.EvidenceBlocked,'context_changed'):self.run_fetch(d,o,t,fresh,wp,{'records':[{'id':11,'title':'یونجه'},{'id':33,'title':'یونجه جدید'}]})
   self.assertEqual(before,p.read_bytes());self.assertFalse(load_json(f/'lifecycle-evidence/overlap-refresh/999.json')['non_owned_context_unchanged'])
 def test_changed_or_unavailable_context_blocks(self):
  for kind in ('content','unavailable','truncated'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory()as td:
    d,o,t,f,b,brief,wp=self.setup(td);fresh=copy.deepcopy(b)
    if kind=='content':fresh['documents'][0]['sha256']='b'*64
    elif kind=='unavailable':fresh['unavailable']=[{'id':11}]
    else:fresh['documents'][0]['text_truncated']=True
    with self.assertRaises(s.EvidenceBlocked):self.run_fetch(d,o,t,fresh,wp)
 def test_corrupt_original_binding_blocks_before_remote(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,t,f,b,brief,wp=self.setup(td);b['documents'][0]['sha256']='b'*64;atomic_json(f/'lifecycle-evidence/existing-content.json',b)
   with self.assertRaisesRegex(s.EvidenceBlocked,'binding_changed'):self.run_fetch(d,o,t,b,wp)
   wp.call.assert_not_called()
 def test_unapproved_research_keeps_existing_collection_behavior(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,t,f,b,brief,wp=self.setup(td);(d/'briefs'/(t['id']+'.json')).unlink();fresh=copy.deepcopy(b);fresh['fetched_at']='new';self.run_fetch(d,o,t,fresh,wp);self.assertEqual(load_json(f/'lifecycle-evidence/existing-content.json')['fetched_at'],'new')
 def test_oversized_approved_context_never_overwrites_original(self):
  with tempfile.TemporaryDirectory()as td:
   d,o,t,f,b,brief,wp=self.setup(td);before=(f/'lifecycle-evidence/existing-content.json').read_bytes()
   with self.assertRaisesRegex(s.EvidenceBlocked,'exceeds_budget'):self.run_fetch(d,o,t,b,wp,{'records':[{'id':i,'title':'یونجه'}for i in range(102)]})
   self.assertEqual(before,(f/'lifecycle-evidence/existing-content.json').read_bytes())
