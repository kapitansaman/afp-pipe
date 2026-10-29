import copy,hashlib,tempfile,unittest
from pathlib import Path
from automation.agri_v2 import scoped_research as s
from automation.agri_v2.queue import utcnow,atomic_json,load_json
from automation.agri_v2.pipeline import check_brief

class ScopedResearchTests(unittest.TestCase):
 def fixture(self):
  topic={'id':'agri-000000000001','title':'میزان برداشت لوبیا قرمز در هکتار','intent':'yield','crop':'لوبیا قرمز'}
  texts=['Red kidney dry beans yielded 2000 pounds per acre in the stated North Dakota trial. Weather, market class and harvested dry seed basis must be retained. '+'Cultivar performance depends on trial site and climate; experimental averages are not promises for other regions. '*3,'Different independent university notes identify white navy and red kidney market classes; harvest losses and seed moisture change the measured marketable seed yield. '+'Independent publication discusses cultivar class and maturity at harvest, not irrigation or fertilizer doses. '*3]
  docs=[{'url':u,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'fetched_at':utcnow()} for u,text in zip(['https://www.ndsu.edu/beans','https://extension.psu.edu/beans'],texts)]
  value={'topic_id':topic['id'],'answers_intent':True,'local_prescription':False,'product_definition':'بذر خشک لوبیای قرمز در آزمایش منبع، نه لوبیای سبز یا تضمین مزرعه ایران','slug':'red-kidney-bean-yield','outline':['دامنه مشاهده','شرایط منبع','محدودیت انتقال'],'facts':[
   {'kind':'source_observation','claim':'عملکرد گزارش‌شده در آزمایش منبع 2000 پوند در ایکر بوده است.','conditions':'این مشاهده برای بذر خشک لوبیای قرمز در آزمایش داکوتای شمالی است و برای ایران توصیه یا تضمین عملکرد نیست.','evidence_id':'d0-e0','numeric_bindings':[{'value':'2000','unit_quote':'2000 pounds per acre','geographic_scope':'North Dakota trial','product_scope':'red kidney dry seed'}]},
   {'kind':'qualitative','claim':'تفاوت شرایط اقلیم و محل آزمایش باید در تفسیر عملکرد حفظ شود.','conditions':'نتیجه آزمایش یک محل را نمی‌توان پیش‌بینی محصول مزرعه دیگر دانست و محدودیت انتقال باقی است.','evidence_id':'d0-e0','numeric_bindings':[]},
   {'kind':'qualitative','claim':'رده بازار لوبیای خشک سفید و لوبیای قرمز در تحلیل باید از هم جدا شود.','conditions':'این تمایز مربوط به رده بازار و محصول بذر خشک است و شاهدی برای هم‌ارزی ارقام ایران نیست.','evidence_id':'d1-e0','numeric_bindings':[]},
   {'kind':'qualitative','claim':'افت برداشت و رطوبت بذر بر مقدار محصول قابل فروش اثر می‌گذارند.','conditions':'در تفسیر نتیجه، مبنای محصول و وضعیت برداشت همان منبع باید حفظ شود و ادعای محلی تازه نشود.','evidence_id':'d1-e0','numeric_bindings':[]}]}
  return topic,value,docs
 def review(self,facts):return {**{k:True for k in ['all_claims_supported','crop_species_and_product_match','answers_exact_intent','units_and_denominators_correct','geography_and_transfer_limits_retained','no_iranian_prescription_inferred','independent_sources','no_unsafe_input_rates']},'human_review_claimed':False,'limitations':'The original geography, harvested product and units remain explicit; no Iranian recommendation or human scientific review is inferred.','fact_checks':[{'fact_id':f['fact_id'],'supported':True,'scope_and_units_correct':True} for f in facts]}
 def test_scoped_number_is_literal_and_conversion_is_server_computed(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);self.assertEqual(len(facts),5);self.assertEqual(facts[-1]['conversion']['target_value'],'2241.702');self.assertEqual(facts[-1]['conversion']['target_unit'],'kg/ha')
 def test_invented_number_or_unit_binding_rejected(self):
  for change in [{'claim':'عملکرد منبع برای هر هکتار برابر 9999 کیلوگرم گزارش می‌شود.'},{'numeric_bindings':[]},{'numeric_bindings':[{'value':'2000','unit_quote':'invented 2000 kg per hectare','geographic_scope':'Iran','product_scope':'beans'}]}]:
   t,v,d=self.fixture();v['facts'][0].update(change)
   with self.subTest(change=change),self.assertRaises(s.EvidenceBlocked):s.validate_candidate(t,v,d)
 def test_scope_mismatch_and_local_prescription_cannot_be_approved(self):
  t,v,d=self.fixture();v['local_prescription']=True
  with self.assertRaises(s.EvidenceBlocked):s.validate_candidate(t,v,d)
  v['local_prescription']=False;v['answers_intent']=False
  with self.assertRaises(s.EvidenceBlocked):s.validate_candidate(t,v,d)
 def test_two_hosts_with_syndicated_text_are_not_independent(self):
  t,v,d=self.fixture();d[1]['text']=d[0]['text'];self.assertEqual(len(s.institutions(d)),1)
 def test_numeric_intent_cannot_be_passed_with_only_qualitative_facts(self):
  t,v,d=self.fixture();v['facts'][0]=dict(v['facts'][1]);
  with self.assertRaises(s.EvidenceBlocked):s.validate_candidate(t,v,d)
 def test_each_fact_requires_a_separate_positive_scope_review(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);r=self.review(facts);s.validate_review(r,facts);r['fact_checks'][-1]['scope_and_units_correct']=False
  with self.assertRaises(s.EvidenceBlocked):s.validate_review(r,facts)
 def test_no_fabricated_human_approval(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);r=self.review(facts);r['human_review_claimed']=True
  with self.assertRaises(s.EvidenceBlocked):s.validate_review(r,facts)
 def overlap(self,t):
  text='این مقاله موجود درباره آماده‌سازی زمین و نگهداری محصول است و مقدار عملکرد بذر خشک یا شرایط آزمایش‌ها را پاسخ نمی‌دهد. '
  bundle={'topic_id':t['id'],'related_ids':[12],'documents':[{'id':12,'text':text,'text_truncated':False,'sha256':hashlib.sha256(text.encode()).hexdigest()}],'unavailable':[]}
  value={'topic_id':t['id'],'decision':'distinct','human_review_claimed':False,'novelty_reason':'The existing full text addresses preparation and storage only; it contains no measured dry-seed yield discussion with trial context and unit limits.','article_checks':[{'id':12,'already_answers_intent':False,'evidence_quote':text,'gap_reason':'The actual paragraph concerns land preparation and storage rather than a scoped dry-bean yield analysis for the new intent.'}]}
  value['existing_content_sha256']=s.content_digest(bundle);return bundle,value
 def test_overlap_audit_binds_every_real_article_quote(self):
  t,v,d=self.fixture();b,r=self.overlap(t);s.validate_overlap(t,b,r);r['article_checks'][0]['evidence_quote']='A fabricated article excerpt that does not appear anywhere in the actual page content.'
  with self.assertRaises(s.EvidenceBlocked):s.validate_overlap(t,b,r)
 def test_missing_truncated_overlapping_or_uncertain_content_never_passes(self):
  for case in ['missing','truncated','overlap','uncertain','already_answered']:
   t,v,d=self.fixture();b,r=self.overlap(t)
   if case=='missing':b['unavailable']=[{'id':12}]
   elif case=='truncated':b['documents'][0]['text_truncated']=True
   elif case=='already_answered':r['article_checks'][0]['already_answers_intent']=True
   else:r['decision']=case
   with self.subTest(case=case),self.assertRaises(s.EvidenceBlocked):s.validate_overlap(t,b,r)
 def test_scoped_brief_round_trip_and_mutated_conversion_blocked(self):
  t,v,d=self.fixture();facts=s.validate_candidate(t,v,d);b,overlap=self.overlap(t);r=self.review(facts);inventory={'source_generated_at':utcnow(),'records':[]};brief=s.build_brief(t,v,d,r,overlap,inventory);check_brief(t,brief);self.assertIsNone(brief['agronomy_reviewer']);brief['approved_facts'][-1]['conversion']['target_value']='9999'
  with self.assertRaises(s.EvidenceBlocked):check_brief(t,brief)
 def test_ambiguous_ton_or_bushel_mass_is_not_converted(self):
  for q in ['2 tons per acre','2 bushels per acre']:
   facts=[{'fact_id':'f0','source_url':'https://x.edu/a','evidence_quote':q,'conditions':'Source-specific scope, never a local recommendation.','numeric_bindings':[{'value':'2','unit_quote':q}]}];self.assertEqual(s.derived_conversions(facts),[])
 def test_article_review_is_independent_and_bound_to_article_bytes(self):
  from unittest.mock import Mock
  t,v,d=self.fixture();client=Mock();client.text.return_value={**{k:True for k in ['all_article_claims_supported','no_additional_numbers_or_advice','units_geography_product_preserved','answers_canonical_intent','no_fabricated_human_review']},'reason':'Every actual claim retains the original crop, product and units and no foreign trial is presented as an Iranian recommendation.'}
  with tempfile.TemporaryDirectory() as td:
   f=Path(td);s.review_article(t,{'title':t['title']},{'approved_facts':[],'source_scope_limitations':'No local rates'},f,client);self.assertTrue((f/'article-evidence-review.json').exists());client.text.return_value['answers_canonical_intent']=False
   with self.assertRaises(s.EvidenceBlocked):s.review_article(t,{'title':t['title']},{'approved_facts':[],'source_scope_limitations':'No local rates'},f,client)
 def test_real_scoped_stages_replace_dead_end_without_fake_approval(self):
  from unittest.mock import Mock
  from automation.agri_v2 import family_lifecycle as f
  from automation.agri_v2 import claim_policy as policy
  t,v,docs=self.fixture();v.update(research_policy_version=policy.VERSION,conflicts=[])
  for fact in v['facts']:
   fact['claim_type']='source_observation' if fact['kind']=='source_observation' else 'general_principle'
   fact['study_context']={k:{'value':None,'quote':None} for k in policy.CONTEXT_FIELDS}
  facts=s.validate_candidate(t,v,docs);bundle,overlap=self.overlap(t)
  review=dict(self.review(facts),research_route_version=s.ROUTE_VERSION,route_requirements_met=True,research_policy_version=policy.VERSION,conflicts_reviewed=True,decision='pass',rejection_reasons=[])
  review['context_checks']=[{'fact_id':fact['fact_id'],'claim_type':fact['claim_type'],'context_supported':True,'publisher_expertise_supported':True,'reason':'The literal source supports this limited claim and its actual context.'} for fact in facts if fact['kind']!='deterministic_conversion']
  for check,fact in zip(review['fact_checks'],facts):check.update(reason='The source supports this claim with the original scope and units.',evidence_quote=fact['evidence_quote'][:90])
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';ev=out/'new'/t['id']/'lifecycle-evidence';atomic_json(ev/'sources.json',{'documents':docs,'source_text_layout_version':2});atomic_json(ev/'existing-content.json',bundle);atomic_json(data/'config.json',{'publication_holds':{},'multilingual':{'enabled':False}});atomic_json(data/'scoped-source-catalog.json',{'entries':[{'crops':[t['crop']],'intents':[t['intent']],'scope':'Exact crop, product and geographic source limits','urls':[]}]});atomic_json(data/'parallel-inventory.json',{'source_generated_at':utcnow(),'records':[]});atomic_json(data/'family-lifecycle-policy.json',{'version':1,'max_families':20,'max_attempts_per_stage':3,'max_model_requests_per_family':14,'max_published_families':20,'preserve_legacy_budgets':True,'scoped_evidence_research':True})
   rp=out/'research'/(t['id']+'.json');atomic_json(rp,{'attempts':0,'status':'needs_review','reason':'quantitative_or_specialist_scope'});before=rp.read_bytes();self.assertEqual(f.next_stage(t,data,out)[0],'research_extract');client=Mock();client.text.side_effect=[v,overlap,review]
   s.stage(t,'research_extract',client,data,out);self.assertEqual(f.next_stage(t,data,out)[0],'existing_content_audit-000');s.stage(t,'existing_content_audit',client,data,out);self.assertEqual(f.next_stage(t,data,out)[0],'research_review');s.stage(t,'research_review',client,data,out);self.assertEqual(f.next_stage(t,data,out)[0],'text');self.assertEqual(rp.read_bytes(),before);self.assertIsNone(load_json(data/'briefs'/(t['id']+'.json'))['agronomy_reviewer'])
 def test_crop_boundary_does_not_mix_mungbean_with_vetch_or_machinery(self):
  self.assertTrue(s.crop_in_title('ماش','زمان برداشت ماش؛ نشانه رسیدگی'));self.assertFalse(s.crop_in_title('ماش','برداشت ماشک'));self.assertFalse(s.crop_in_title('ماش','ماشین برداشت لوبیا'));self.assertTrue(s.crop_in_title('گوجه‌فرنگی','تراکم گوجه فرنگی در مزرعه'))
 def test_full_overlap_scope_is_batched_not_silently_truncated(self):
  t,v,d=self.fixture();b,r=self.overlap(t);b['documents']=[dict(b['documents'][0],id=i,text='evidence '+str(i)+' '+'x '*5000,sha256=str(i)) for i in range(17)];b['related_ids']=list(range(17));groups=s.overlap_groups(b);self.assertGreater(len(groups),1);self.assertEqual([i for g in groups for i in g['related_ids']],list(range(17)));self.assertTrue(all(len(g['documents'])<=3 for g in groups))
 def test_unit_before_value_in_a_structured_table_is_convertible(self):
  f={'fact_id':'f0','source_url':'https://x.edu/tomato','evidence_quote':'Plant population per acre | Measurements: 3,630–4,356','conditions':'Florida field tomato observation only; retain all original crop and unit limits.','numeric_bindings':[{'value':'3,630','unit_quote':'Plant population per acre | Measurements: 3,630–4,356'}]};converted=s.derived_conversions([f]);self.assertEqual(converted[0]['conversion']['target_unit'],'plants/ha');self.assertEqual(converted[0]['conversion']['target_value'],'8969.925')
 def test_each_overlap_batch_must_pass_before_aggregate_approval(self):
  from unittest.mock import Mock
  t,v,docs=self.fixture();bundle,value=self.overlap(t)
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';ev=out/'new'/t['id']/'lifecycle-evidence';atomic_json(data/'scoped-source-catalog.json',{'entries':[{'crops':[t['crop']],'intents':[t['intent']],'scope':'Exact crop/product scope','urls':[]}]});atomic_json(ev/'sources.json',{'documents':docs,'source_text_layout_version':2});atomic_json(ev/'candidate.json',v);atomic_json(ev/'existing-content.json',bundle)
   self.assertEqual(s.overlap_next(t,ev)[0],'existing_content_audit-000');client=Mock();client.text.return_value=value;s.stage(t,'existing_content_audit-000',client,data,out);self.assertEqual(s.overlap_next(t,ev)[0],'existing_content_audit_finalize');s.stage(t,'existing_content_audit_finalize',client,data,out);self.assertEqual(load_json(ev/'overlap.json')['decision'],'distinct');self.assertEqual(client.text.call_count,1)
 def test_saved_source_cache_must_match_url_hash_and_literal_document(self):
  from automation.agri_v2.parallel_controller import merge_worker
  t,v,docs=self.fixture();d=docs[0];d['text']+=' Additional literal institutional source context.'*5;d['sha256']=hashlib.sha256(d['text'].encode()).hexdigest();d['requested_url']=d['url'];d['redirect_chain']=[d['url']]
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);wd=root/'wd';wo=root/'wo';data=root/'data';out=root/'out';name=hashlib.sha256(d['url'].encode()).hexdigest()+'.json';atomic_json(wo/'source-cache'/name,d);merge_worker(t['id'],wd,wo,data,out);self.assertEqual(load_json(out/'source-cache'/name)['sha256'],d['sha256']);d['text']='tampered '*100;atomic_json(wo/'source-cache'/name,d)
   before=(out/'source-cache'/name).read_bytes();merge_worker(t['id'],wd,wo,data,out);self.assertEqual(before,(out/'source-cache'/name).read_bytes())
 def test_saved_repair_preserves_claims_and_does_not_flip_scientific_rejection(self):
  t,v,d=self.fixture();v['facts'][0]['kind']='qualitative';candidate,report=s.normalize_saved_candidate(t,v,d);self.assertEqual(candidate['facts'][0]['claim'],v['facts'][0]['claim']);self.assertEqual(candidate['facts'][0]['kind'],'source_observation');self.assertFalse(report['claims_rewritten']);self.assertFalse(report['scientific_rejection_overridden']);v['answers_intent']=False
  with self.assertRaises(s.EvidenceBlocked):s.normalize_saved_candidate(t,v,d)
 def test_saved_repair_drops_bad_fact_only_when_four_grounded_facts_remain(self):
  t,v,d=self.fixture();bad=dict(v['facts'][0],claim='عملکرد کاملاً ساختگی برابر 9999 کیلوگرم در هکتار است.');v['facts'].append(bad);candidate,report=s.normalize_saved_candidate(t,v,d);self.assertEqual(len(candidate['facts']),4);self.assertEqual(report['dropped_facts'][0]['index'],4)
  v['facts']=v['facts'][1:]
  with self.assertRaises(s.EvidenceBlocked):s.normalize_saved_candidate(t,v,d)
 def test_literal_english_word_measurements_are_not_new_model_numbers(self):
  self.assertEqual(s.tokens('sixteen weeks and two-cut system'),{'16','2'});self.assertEqual(s.tokens('one publication and two opinions'),set())

 def test_overlap_quote_packet_preserves_every_character_and_article_identity(self):
  t,v,d=self.fixture();b,r=self.overlap(t);text=b['documents'][0]['text']*30;b['documents'][0]['text']=text;packet=s.overlap_review_packet(b);self.assertEqual(''.join(q['text'] for q in packet[0]['full_text_chunks']),text);self.assertEqual(packet[0]['article_id'],12)
 def test_overlap_selected_quote_is_bound_server_side_not_generated(self):
  t,v,d=self.fixture();b,r=self.overlap(t);r['article_checks'][0].pop('evidence_quote');r['article_checks'][0]['quote_id']='12:0';bound=s.bind_overlap_quotes(b,r);s.validate_overlap(t,b,bound);self.assertEqual(bound['article_checks'][0]['evidence_quote'],b['documents'][0]['text']);r['article_checks'][0]['id']=1
  with self.assertRaises(s.EvidenceBlocked):s.bind_overlap_quotes(b,r)
 def test_conflicting_generated_quote_cannot_override_source(self):
  t,v,d=self.fixture();b,r=self.overlap(t);r['article_checks'][0]['quote_id']='12:0';r['article_checks'][0]['evidence_quote']='Fabricated quote'
  with self.assertRaises(s.EvidenceBlocked):s.bind_overlap_quotes(b,r)

 def test_only_positive_overlap_vocabulary_is_canonicalized(self):
  t,v,d=self.fixture();b,r=self.overlap(t)
  for word in ('new','novel'):
   r['decision']=word;result=s.bind_overlap_quotes(b,r);self.assertEqual(result['original_decision'],word);s.validate_overlap(t,b,result)
  for word in ('overlap','uncertain','not distinct','maybe new'):
   r['decision']=word
   with self.assertRaises(s.EvidenceBlocked):s.validate_overlap(t,b,s.bind_overlap_quotes(b,r))
 def test_positive_vocabulary_never_overrides_article_rejection(self):
  t,v,d=self.fixture();b,r=self.overlap(t);r['decision']='new';r['article_checks'][0]['already_answers_intent']=True
  with self.assertRaises(s.EvidenceBlocked):s.validate_overlap(t,b,s.bind_overlap_quotes(b,r))
 def test_conflicting_overlap_review_never_auto_approved(self):
  t,v,d=self.fixture();b,r=self.overlap(t)
  for decision,flag in [('overlap',False),('distinct',True)]:
   x=copy.deepcopy(r);x['decision']=decision;x['article_checks'][0]['already_answers_intent']=flag
   self.assertTrue(s.overlap_decision_conflict(x))
   with self.assertRaisesRegex(s.EvidenceBlocked,'overlap_review_decision_conflict'):s.validate_overlap(t,b,x)
 def test_consistent_overlap_and_uncertainty_remain_rejected(self):
  t,v,d=self.fixture();b,r=self.overlap(t)
  for decision,flag in [('overlap',True),('uncertain',False),('uncertain',True)]:
   x=copy.deepcopy(r);x['decision']=decision;x['article_checks'][0]['already_answers_intent']=flag
   self.assertFalse(s.overlap_decision_conflict(x))
   with self.assertRaisesRegex(s.EvidenceBlocked,'existing_content_overlap_or_uncertain'):s.validate_overlap(t,b,x)
