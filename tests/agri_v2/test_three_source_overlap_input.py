import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import three_source_trial as t,operation_request as op
from automation.agri_v2.queue import atomic_json,load_json
class TrialOverlapInputTests(unittest.TestCase):
 def test_exact_zero_call_continuation_does_not_expand_original_budget(self):
  r=t.expected_request(t.OVERLAP_ID);op.validate_request(dict(r,code_revision='a'*40));self.assertEqual((r['prior_total_model_calls'],r['max_total_model_calls'],r['max_total_text_calls'],r['max_model_calls_per_family']),(6,36,21,12));self.assertFalse(r['reset_attempts']);self.assertFalse(r['enable_schedule'])
 def test_prepare_fetches_full_overlap_inputs_before_isolated_worker(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';atomic_json(data/'manifest.json',{'counts':{'new':2905,'merge':593,'hold':370}});atomic_json(out/'parallel/families/assignments.json',{'families':[]});wp=Mock();wp.preflight.return_value={'can_publish':True};wp.inventory.return_value={'records':[]};topics=[{'id':x,'title':'fixture','intent':'soil_sensor','crop':'لوبیا چیتی'} for x in t.TOPICS]
   def fetch(all_topics,inventory,publisher,target,run_id):
    self.assertEqual([x['id'] for x in all_topics],list(t.TOPICS));self.assertIs(publisher,wp)
    for topic in all_topics:atomic_json(target/'new'/topic['id']/'lifecycle-evidence/existing-content.json',{'topic_id':topic['id'],'related_ids':[],'documents':[],'unavailable':[]})
    return {'families':3,'article_refs_loaded':0}
   with patch.object(t,'admitted'),patch('automation.agri_v2.parallel_control.policy'),patch('automation.agri_v2.three_source_repair.verify_prior',return_value={'prior_source_files':{}}),patch.object(t,'get_topic',side_effect=topics),patch('automation.agri_v2.scoped_research.entries_for',return_value=[{}]),patch('automation.agri_v2.pipeline.fresh_inventory'),patch('automation.agri_v2.scoped_research.prefetch_existing',side_effect=fetch) as prefetched:
    r=t.prepare({'GITHUB_RUN_ID':'999'},data,out,reserve_fn=lambda *a:{'reserved':True},wp_factory=lambda:wp,request_id=t.OVERLAP_ID)
   prefetched.assert_called_once();self.assertEqual(r['status'],'three_source_trial_prepared');self.assertEqual(r['existing_content_fetch']['families'],3);self.assertEqual(r['model_calls'],0);self.assertEqual(r['wordpress_calls'],0)
   for ident in t.TOPICS:self.assertTrue((out/'new'/ident/'lifecycle-evidence/existing-content.json').exists())
