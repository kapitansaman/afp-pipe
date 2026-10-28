import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from automation.agri_v2 import content_matrix as m,internal_links as links,scoped_research as s
from automation.agri_v2.queue import items
class ContentMatrixTests(unittest.TestCase):
 def topic(self,intent='yield'):return next(t for t in items('new') if t['intent']==intent)
 def test_all_2905_keep_exact_titles_and_no_automatic_delete_or_publication(self):
  ts=items('new');self.assertEqual(len(ts),2905)
  for t in ts:
   c=m.contract(t);self.assertEqual(c['canonical_title'],t['title']);self.assertEqual(c['topic_id'],t['id']);self.assertEqual(c['queue_action'],'retain_canonical_title');self.assertFalse(c['publication_authorized']);self.assertNotEqual(c['irrigation_relationship'],'unclassified');self.assertEqual(c['content_gap_status'],'requires_actual_existing_content_audit')
 def test_direct_irrigation_has_equipment_invitation_not_efficacy_claim(self):
  c=m.contract(self.topic('irrig_duration'));self.assertEqual(c['irrigation_relationship'],'direct');self.assertEqual(c['cta_mode'],'equipment_selection');self.assertIn('No invented model',c['product_scope'])
 def test_crop_traffic_topic_needs_approved_irrigation_fact_for_bridge(self):
  t=self.topic('yield');self.assertEqual(m.contract(t)['cta_mode'],'none')
  brief={'approved_facts':[{'fact_id':'f0','claim':'رطوبت خاک در همین آزمایش گزارش شده است.'}]};c=m.contract(t,brief);self.assertEqual(c['bridge_fact_ids'],['f0']);self.assertEqual(c['cta_mode'],'source_supported_bridge')
  self.assertEqual(m.contract(t,{'outline':['آبیاری'],'sources':[{'excerpt':'آبیاری'}],'approved_facts':[]})['cta_mode'],'none')
 def test_distant_topic_no_forced_tape_even_with_water_word(self):
  c=m.contract(self.topic('storage'),{'approved_facts':[{'fact_id':'f0','claim':'آبیاری در مزرعه'}]});self.assertEqual(c['cta_mode'],'none');self.assertFalse(m.links_enabled(c))
 def test_unknown_topic_gets_no_commercial_recommendation(self):
  c=m.contract({'title':'موضوع با تیپ'});self.assertEqual(c['irrigation_relationship'],'unclassified');self.assertFalse(m.links_enabled(c))
 def test_model_cannot_supply_or_modify_commercial_authority(self):
  t=self.topic();b={'approved_facts':[]};a=m.attach({'commercial_matrix':{'cta_mode':'buy_now'}},t,b);m.validate(a,t,b);a['commercial_matrix']['cta_mode']='equipment_selection'
  with self.assertRaises(ValueError):m.validate(a,t,b)
 def test_no_cta_suppresses_forced_primary_links_but_preserves_citations(self):
  t=self.topic('storage');t=dict(t,commercial_matrix=m.contract(t));body='<p>متن <a href="https://one.edu/source">منبع</a></p>';out=links.augment(body,t,'https://navar-abyari.ir/new-topic/')
  self.assertEqual(links.external_links(out),['https://one.edu/source']);self.assertNotIn('product-category',out);self.assertNotIn('برای آشنایی',out)
 def test_direct_cta_real_targets_idempotent_and_not_guarantee(self):
  t=self.topic('irrig_duration');t=dict(t,commercial_matrix=m.contract(t));body='<p>متن <a href="https://one.edu/source">منبع</a></p>';u='https://navar-abyari.ir/new-topic/';out=links.augment(body,t,u)
  self.assertIn('product-category',out);self.assertIn('تضمین عملکرد نیست',out);self.assertEqual(links.augment(out,t,u),out);self.assertEqual(links.external_links(out),links.external_links(body))
 def test_new_article_needs_commercial_skeptical_review_flags(self):
  t=self.topic('irrig_duration');article=m.attach({'title':t['title'],'content_html':'<p>متن</p>'},t,{'approved_facts':[]});brief={'approved_facts':[],'source_scope_limitations':'No local advice'};client=Mock();client.text.return_value={k:True for k in ['all_article_claims_supported','no_additional_numbers_or_advice','units_geography_product_preserved','answers_canonical_intent','no_fabricated_human_review']};client.text.return_value['reason']='Actual source limits and exact facts were inspected without approving any unsupported local recommendation.'
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):s.review_article(t,article,brief,Path(td),client)
   client.text.return_value.update(reader_question_answered_before_promotion=True,product_claims_not_invented=True,irrigation_bridge_supported_or_omitted=True);s.review_article(t,article,brief,Path(td),client)
   client.text.return_value['product_claims_not_invented']=False
   with self.assertRaises(ValueError):s.review_article(t,article,brief,Path(td),client)
 def test_same_language_translation_can_omit_unrelated_equipment_links(self):
  from automation.agri_v2.multilingual import localized_body
  row={'language':'en-US','title':'Storage','content_html':'<h2>Storage</h2><p>Scope <a href="https://example.edu/source">Source</a></p>','faq':[{'question':'Question?','answer':'Answer'}]*3};media=[{'url':'https://navar-abyari.ir/one.webp'},{'url':'https://navar-abyari.ir/two.webp'}]
  text=localized_body(row,media,{'en-US':[]});self.assertNotIn('Irrigation equipment:',text);self.assertIn('Frequently asked questions',text);self.assertIn('two.webp',text)
 def test_limited_export_unknown_is_not_zero_demand_or_a_gap(self):
  from automation.agri_v2.queue import atomic_json
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);atomic_json(d/'search-demand-map.json',{'version':1,'method':'normalized_exact_full_title_or_leading_title_clause_only','content_gap_inferred':False,'matched_topic_ids':['known']})
   self.assertEqual(m.demand_status({'id':'known'},d),'exact_phrase_observed_in_supplied_export');self.assertEqual(m.demand_status({'id':'other'},d),'unknown_not_an_exact_match_in_limited_export')
   c=m.contract(self.topic(),data=d);self.assertEqual(c['queue_action'],'retain_canonical_title');self.assertEqual(c['content_gap_status'],'requires_actual_existing_content_audit')
 def test_unverified_demand_map_not_admitted(self):
  from automation.agri_v2.queue import atomic_json
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);atomic_json(d/'search-demand-map.json',{'version':1,'method':'guess','content_gap_inferred':True,'matched_topic_ids':['fake']})
   with self.assertRaises(ValueError):m.demand_status({'id':'fake'},d)
 def test_commercial_review_flags_do_not_retroactively_change_old_articles(self):
  self.assertEqual(m.commercial_review_flags({'title':'old'}),[]);self.assertEqual(len(m.commercial_review_flags({'commercial_matrix':{}})),3)
 def test_commercial_article_requires_review_even_with_legacy_brief(self):
  from unittest.mock import patch
  from automation.agri_v2 import family_lifecycle as f
  from automation.agri_v2.queue import atomic_json
  t=self.topic('irrig_duration');brief={'publish_authorized':True};article=m.attach({'title':t['title']},t,brief)
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';atomic_json(d/'config.json',{'publication_holds':{},'multilingual':{'enabled':False}});atomic_json(d/'briefs'/(t['id']+'.json'),brief);atomic_json(o/'new'/t['id']/'article.json',article)
   with patch.object(f,'check_brief'),patch.object(f,'article_checked',return_value=article):self.assertEqual(f.next_stage(t,d,o),('article_evidence_review',None))
