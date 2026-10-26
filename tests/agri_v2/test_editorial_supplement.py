import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import editorial_supplement as e
from automation.agri_v2 import family_lifecycle as f
from automation.agri_v2.queue import atomic_json,load_json
class EditorialSupplementTests(unittest.TestCase):
 def brief(self):return {'approved_facts':[{'fact_id':x,'claim':'مشاهده منبع بدون پیش‌بینی','conditions':'محدود به همان محل و محصول','source_url':'https://extension.example.edu/doc'} for x in ['f0','f1','f2','f3','f0-conversion-0','f1-conversion-0']],'sources':[{'url':'https://extension.example.edu/doc'}]}
 def test_one_separate_attempt_does_not_reset_original_three(self):
  with tempfile.TemporaryDirectory() as t:
   folder=Path(t);atomic_json(f.row_path(folder,'text'),{'attempts':3,'history':[{'status':'failed'}]});before=f.row_path(folder,'text').read_bytes();call=Mock(side_effect=ValueError('bad'))
   self.assertEqual(f.attempt(folder,e.STAGE,'11',call,limit=1)['status'],'stage_failed');self.assertEqual(f.attempt(folder,e.STAGE,'12',call,limit=1)['status'],'stage_budget_exhausted');self.assertEqual(call.call_count,1);self.assertEqual(f.row_path(folder,'text').read_bytes(),before)
 def test_server_owned_plan_contains_only_actual_approved_fact_ids(self):
  b=self.brief();p=e.plan(b);self.assertEqual([v['id'] for v in p],['p'+str(i) for i in range(8)]);self.assertNotIn('source_scope_limitations',str(p))
 def test_wrong_family_or_absent_explicit_request_is_not_admitted(self):
  with tempfile.TemporaryDirectory() as t:
   self.assertFalse(e.authorized({'id':'other'}, {},Path(t),Path(t)));self.assertFalse(e.authorized({'id':e.TOPIC},{'AFP_WHITE_BEAN_PILOT':'1'},Path(t),Path(t)))
 def test_invalid_editorial_shape_never_writes_an_article(self):
  with tempfile.TemporaryDirectory() as t:
   folder=Path(t);client=Mock();client.text.return_value={'paragraphs':[]}
   with self.assertRaises(ValueError):e.generate(client,{'id':e.TOPIC,'title':'عنوان'},self.brief(),folder)
   self.assertFalse((folder/'article.json').exists());self.assertEqual(client.text.call_count,1)
