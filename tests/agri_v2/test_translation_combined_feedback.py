import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import language_infrastructure_probe as p
from automation.agri_v2.translation_review_repair import merge_verified_issues,RepairBlocked
class TranslationCombinedFeedbackTests(unittest.TestCase):
 def test_same_id_keeps_both_verified_defects_without_duplicate_rows(self):
  m=[{'id':0,'category':'wrong_language','detail':'Actual script residue.'}];s=[{'id':0,'category':'meaning','detail':'Actual meaning changed.'},{'id':1,'detail':'An actual omission.'}]
  result=merge_verified_issues(m,s,2);self.assertEqual(len(result),2);self.assertIn(m[0]['detail'],result[0]['detail']);self.assertIn(s[0]['detail'],result[0]['detail']);self.assertEqual(m[0]['detail'],'Actual script residue.')
 def test_unbound_feedback_never_reaches_editor(self):
  for issue in ({'id':2,'detail':'bad'},{'id':True,'detail':'bad'},{'id':0,'detail':''}):
   with self.assertRaises(RepairBlocked):merge_verified_issues([issue],[],2)
 def exercise(self,initial_review,negative_final=False):
  article={'title':'fixture','content_html':'<p>fixture</p>','faq':[]};source=['متن نخست','متن دوم'];raw={'translations':[{'id':0,'text':'mechanical defect'},{'id':1,'text':'semantic defect'}]}
  responses=[raw,initial_review,{'patches':[{'id':i,'text':'corrected '+str(i)} for i in ([0,1] if not initial_review['faithful'] else [0])]},{'faithful':not negative_final,'reason':'Independent actual final judgment.','issues':[{'id':1,'detail':'Actual meaning defect remains.'}] if negative_final else []}]
  c=Mock();c.text.side_effect=responses
  def normalized(value,batch):
   if value['translations'][0]['text']=='mechanical defect':raise ValueError('Actual script residue.')
   return value['translations']
  with tempfile.TemporaryDirectory() as d,patch('automation.agri_v2.multilingual.source_segments',return_value=(None,source)),patch('automation.agri_v2.multilingual.render_translation',return_value={'language':'en-US','content_html':'fixture'}),patch('automation.agri_v2.translation_chunks.normalize_batch',side_effect=normalized):
   if negative_final:
    with self.assertRaises(p.LanguageProbeBlocked):p.language(c,article,'en-US',Path(d))
    self.assertFalse((Path(d)/'languages/en-US/approved.json').exists())
   else:self.assertEqual(p.language(c,article,'en-US',Path(d))['status'],'fidelity_passed')
  self.assertEqual(c.text.call_count,4);review=json.loads(c.text.call_args_list[1].args[0]);edit=json.loads(c.text.call_args_list[2].args[0]);self.assertIn('verified_mechanical_feedback',review);return edit
 def test_semantic_review_runs_before_single_edit_and_combines_real_defects(self):
  edit=self.exercise({'faithful':False,'reason':'Actual semantic issue.','issues':[{'id':1,'detail':'Actual source meaning changed.'}]});self.assertEqual({r['id'] for r in edit['segments']},{0,1})
 def test_semantic_positive_never_overrides_mechanical_negative(self):
  edit=self.exercise({'faithful':True,'reason':'Semantic meaning faithful.','issues':[]});self.assertEqual([r['id'] for r in edit['segments']],[0])
 def test_negative_final_review_remains_negative_no_second_edit(self):
  self.exercise({'faithful':False,'reason':'Actual semantic issue.','issues':[{'id':1,'detail':'Actual source meaning changed.'}]},True)
