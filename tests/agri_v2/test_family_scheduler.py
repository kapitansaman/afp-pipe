import concurrent.futures,copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import family_scheduler as f,parallel_controller as controller
from automation.agri_v2.queue import atomic_json,load_json

class FamilySchedulerTests(unittest.TestCase):
 def setup(self,p,n=24):
  d=p/'data';o=p/'out'
  atomic_json(d/'config.json',{'publication_holds':{},'multilingual':{'enabled':False}})
  atomic_json(d/'research-source-catalog.json',{'version':4,'entries':[]})
  topics=[{'id':'agri-'+format(i,'012x'),'title':'موضوع '+str(i),'crop':'لوبیا','intent':'yield' if i%2 else 'storage','origin':'REVIEW','overlap_review_required':bool(i%3==0),'related_existing_ids':[4] if i%3==0 else []} for i in range(n)]
  return d,o,topics
 def test_all_15_get_distinct_queue_topics_even_without_sources_or_specialist_readiness(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t))
   with patch.object(f,'items',return_value=topics):s=f.allocate(d,o)
   self.assertEqual(s['assigned_count'],15);self.assertEqual(s['unique_topic_count'],15)
   self.assertEqual([r['family_id'] for r in s['families']],list(f.FAMILIES));self.assertEqual([r['topic_id'] for r in s['families']],[x['id'] for x in topics[:15]])
   self.assertTrue(all(r['assignment_status']=='assigned' for r in s['families']));self.assertFalse(any(r['publication_authorized_by_assignment'] for r in s['families']))
 def test_repeat_and_catalog_changes_do_not_reshuffle_ownership(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t))
   with patch.object(f,'items',return_value=topics):
    a=f.allocate(d,o);raw=(o/'parallel/families/assignments.json').read_bytes();b=f.allocate(d,o)
    self.assertEqual(raw,(o/'parallel/families/assignments.json').read_bytes())
    atomic_json(d/'research-source-catalog.json',{'version':5,'entries':[{'crops':['لوبیا'],'intents':['storage'],'urls':[]}]});c=f.allocate(d,o)
   self.assertEqual([(r['family_id'],r['topic_id']) for r in a['families']],[(r['family_id'],r['topic_id']) for r in c['families']])
 def test_verified_publication_and_explicit_hold_not_allocated_as_new_work(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t));atomic_json(o/'new'/topics[0]['id']/'wordpress-receipt.json',{'public_verified':True})
   cfg=load_json(d/'config.json');cfg['publication_holds']={topics[1]['id']:'Preserve hold'};atomic_json(d/'config.json',cfg)
   with patch.object(f,'items',return_value=topics):s=f.allocate(d,o)
   self.assertEqual(s['assigned_count'],15);self.assertEqual(s['families'][0]['topic_id'],topics[2]['id'])
 def test_only_completed_family_moves_to_next_topic(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t))
   with patch.object(f,'items',return_value=topics):
    a=f.allocate(d,o);atomic_json(o/'new'/topics[0]['id']/'wordpress-receipt.json',{'public_verified':True});b=f.allocate(d,o)
   self.assertEqual(b['families'][0]['topic_id'],topics[15]['id']);self.assertEqual(a['families'][1:],b['families'][1:]);self.assertEqual(len(b['history']),1)
 def test_pending_required_translations_keep_ownership(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t));cfg=load_json(d/'config.json');cfg['multilingual']['enabled']=True;atomic_json(d/'config.json',cfg)
   with patch.object(f,'items',return_value=topics):
    a=f.allocate(d,o);atomic_json(o/'new'/topics[0]['id']/'wordpress-receipt.json',{'public_verified':True});b=f.allocate(d,o)
   self.assertEqual(a['families'][0]['topic_id'],b['families'][0]['topic_id']);self.assertEqual(b['families'][0]['work_stage'],'translations_pending')
 def test_prior_failed_attempt_budget_is_not_reset_or_used_to_filter_assignment(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t));p=o/'research'/f"{topics[0]['id']}.json";atomic_json(p,{'attempts':2,'status':'needs_review','reason':'budget_exhausted'});before=p.read_bytes()
   with patch.object(f,'items',return_value=topics):s=f.allocate(d,o)
   self.assertEqual(s['families'][0]['topic_id'],topics[0]['id']);self.assertEqual(s['families'][0]['work_stage'],'research_budget_exhausted');self.assertEqual(p.read_bytes(),before)
 def test_concurrent_assignment_has_no_duplicate_owners(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t))
   with patch.object(f,'items',return_value=topics),concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:results=list(ex.map(lambda _:f.allocate(d,o),range(3)))
   self.assertTrue(all(r['families']==results[0]['families'] for r in results))
 def test_corrupt_duplicate_ownership_fails_closed(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t));row={'family_id':'family-01','topic_id':topics[0]['id']}
   atomic_json(o/'parallel/families/assignments.json',{'families':[row,row]})
   with patch.object(f,'items',return_value=topics),self.assertRaises(ValueError):f.allocate(d,o)
 def test_assign_mode_requires_no_health_audit_or_wordpress_access(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t));atomic_json(d/'parallel-policy.json',{'repository':'kapitansaman/afp-pipe','key_limit':75,'max_article_workers':15,'image_concurrency':1,'production_enabled':False,'max_published_posts':0})
   env={'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'kapitansaman/afp-pipe','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123'}
   with patch.object(f,'items',return_value=topics),patch('automation.agri_v2.wordpress.WordPress') as wp:r=controller.run('assign',env,d,o)
   self.assertEqual(r['assigned_count'],15);self.assertEqual(r['model_calls'],0);wp.assert_not_called()
 def test_queue_shortage_is_reported_without_inventing_titles(self):
  with tempfile.TemporaryDirectory() as t:
   d,o,topics=self.setup(Path(t),3)
   with patch.object(f,'items',return_value=topics):s=f.allocate(d,o)
   self.assertEqual(s['assigned_count'],3);self.assertEqual(s['target_families'],15)
