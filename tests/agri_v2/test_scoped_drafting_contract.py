import json,unittest
from automation.agri_v2.pipeline import article_prompt,drafting_brief
class ScopedDraftingContractTests(unittest.TestCase):
 def brief(self):return {'review_mode':'automated_scoped_evidence_review_v1','title':'موضوع','outline':['دانسته ها'],'sources':[{'url':'https://extension.example.edu/trial','excerpt':'Unapproved table mean 9999 and storage 16 percent','sha256':'not-needed-by-writer'}],'approved_facts':[{'fact_id':'f0','kind':'source_observation','claim':'مشاهده عملکرد 3633 پوند در ایکر است.','conditions':'این مشاهده صرفاً مربوط به رقم و محل منبع است.','source_url':'https://extension.example.edu/trial','evidence_quote':'Huge raw source table with unapproved mean 9999'}]}
 def test_writer_gets_only_approved_claims_not_raw_tables(self):
  v=drafting_brief(self.brief());text=json.dumps(v,ensure_ascii=False);self.assertNotIn('9999',text);self.assertNotIn('evidence_quote',text);self.assertIn('3633',text);self.assertIn('source_url',text)
 def test_prompt_requires_exact_citations_and_approved_numbers(self):
  p=json.loads(article_prompt({'title':'موضوع'},self.brief()));c=p['approved_claim_contract'];self.assertEqual(c['numeric_tokens_allowed_exactly'],['3633']);self.assertIn('<a href=',c['requirements']);self.assertIn('no rounding',c['requirements']);self.assertNotIn('9999',json.dumps(p,ensure_ascii=False))
 def test_other_approved_brief_modes_are_not_mutated(self):
  v=self.brief();v['review_mode']='human_review';self.assertIs(drafting_brief(v),v)
