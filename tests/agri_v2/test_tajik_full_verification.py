import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import tajik_full_verification as f,persian_clarity as p,operation_request as op
from automation.agri_v2.queue import load_json,get_topic
from automation.agri_v2.pipeline import digest
from automation.agri_v2.multilingual import source_segments
from test_multilingual import article,response
class TajikFullTests(unittest.TestCase):
 def req(self):return {'version':1,'request_id':f.ID,'operation':'nonpublishing-clean-persian-full-tajik-flash3','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':0,'enable_schedule':False,'reset_attempts':False,'max_total_text_calls':8,'max_wordpress_mutations':0,'max_image_calls':0,'topic_id':f.TOPIC,'model':f.MODEL,'max_tajik_repair_rounds':2,'max_reviewer_self_corrections':1,'max_revised_source_articles':1,'max_translation_languages':1,'change_default_model':False,'code_revision':'b'*40}
 def fixture(self):
  a=article();raw=response(a,'tg-TJ');_,source=source_segments(a);return a,raw,source
 def test_admission_cannot_expand_or_select_paid_model(self):
  op.validate_request(self.req())
  for key,val in [('max_total_text_calls',9),('model','agnes-2.5-pro-beta'),('max_tajik_repair_rounds',3),('max_reviewer_self_corrections',2),('max_translation_languages',4),('change_default_model',True)]:
   req=self.req();req[key]=val
   with self.assertRaises(ValueError):op.validate_request(req)
 def test_real_persian_revision_is_bound_and_reaudited_not_approved_by_edit(self):
  ident=f.TOPIC;old=load_json('artifacts/agri-v2/parallel/writer-verification/ops-practical-editorial-completion-v6/'+ident+'/article.json');brief=load_json('data/agri-v2/briefs/'+ident+'.json');patch=load_json('data/agri-v2/editorial-corrections/persian-carrot-clarity-v1.json');before=digest(old)
  new,receipt=p.apply(old,get_topic('new',ident),brief,patch)
  self.assertEqual(digest(old),before);self.assertNotEqual(digest(new),before);self.assertEqual(new['title'],old['title']);self.assertTrue(receipt['independent_evidence_review_required']);self.assertNotIn('رشدیس',str(new));self.assertNotIn('استقرار پوچ',str(new));self.assertNotIn('شرایط رویایی',str(new))
  bad=copy.deepcopy(patch);bad['changes'][0]['old_text']='changed'
  with self.assertRaises(ValueError):p.apply(old,get_topic('new',ident),brief,bad)
 def test_structural_ids_are_unambiguous_numeric_strings_ok(self):
  a,raw,source=self.fixture();raw['translations'][0]['id']='0';self.assertEqual(f.canonical_rows(raw,source)['translations'][0]['id'],0)
  raw['translations'][1]['id']=0
  with self.assertRaises(ValueError):f.canonical_rows(raw,source)
 def test_mechanical_defect_is_feedback_not_silent_acceptance(self):
  a,raw,source=self.fixture();raw['translations'][0]['text']='Тарҷумаidan';normal,issues=f.mechanical(a,raw,source);self.assertEqual(issues[0]['id'],0);self.assertIn('Latin',issues[0]['detail'])
  raw['translations'][0]['text']='Тарҷума 999';_,issues=f.mechanical(a,raw,source);self.assertEqual(issues[0]['category'],'number_unit')
 def test_review_does_not_require_echoed_paragraphs_and_groups_duplicate_ids(self):
  a,raw,source=self.fixture();v={'faithful':False,'reason':'Meaning changed.','issues':[{'id':'0','category':'meaning','detail':'The actual meaning was changed.'},{'id':0,'category':'omission','detail':'An actual source qualifier was omitted.'}]}
  self.assertEqual(len(f.check_review(v,source,raw,a)),1)
  bad=copy.deepcopy(v);bad['faithful']=True
  with self.assertRaises(ValueError):f.check_review(bad,source,raw,a)
 def test_unrequested_text_is_never_rewritten(self):
  a,raw,source=self.fixture();before=copy.deepcopy(raw);result=f.edit_rows({'patches':[{'id':0,'text':'Ислоҳ'}]},[{'id':0}],raw,source)
  self.assertEqual(before,raw);self.assertEqual(result['translations'][1:],raw['translations'][1:])
  with self.assertRaises(ValueError):f.edit_rows({'patches':[{'id':1,'text':'Ислоҳ'}]},[{'id':0}],raw,source)
 def test_one_shared_review_self_correction_never_forces_pass(self):
  a,raw,source=self.fixture();bad={'faithful':True,'reason':'Contradiction','issues':[{'id':0,'category':'meaning','detail':'Bad meaning'}]};good={'faithful':False,'reason':'One real issue remains.','issues':[{'id':0,'category':'meaning','detail':'Actual source meaning differs.'}]}
  with tempfile.TemporaryDirectory() as d:
   c=Mock();c.text.side_effect=[bad,good];value,issues=f.reviewed(c,Path(d),'review0',a,source,raw);self.assertFalse(value['faithful']);self.assertEqual(c.text.call_count,2)
   c.text.side_effect=[bad]
   with self.assertRaises(ValueError):f.reviewed(c,Path(d),'review1',a,source,raw)
   self.assertEqual(c.text.call_count,3)
