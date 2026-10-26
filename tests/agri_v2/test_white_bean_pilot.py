import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2 import white_bean_pilot as p,scoped_research as s,scoped_review_v2 as r
from automation.agri_v2.queue import atomic_json,load_json,utcnow

class WhiteBeanPilotTests(unittest.TestCase):
 def fixture(self):
  # Synthetic table fixtures, never production evidence or reviewer approval.
  topic={'id':p.TOPIC,'title':'میزان برداشت لوبیا سفید در هکتار','intent':'yield','crop':'لوبیا سفید'}
  old={'topic_id':p.TOPIC,'slug':'white-bean-yield-hectare-range','outline':['محصول دانه خشک','داده منطقه‌ای آزمایش','محدودیت تعمیم'],'product_definition':'دانه خشک لوبیای سفید با تفکیک رده بازار و بدون فرض هم‌ارزی رقم محلی'}
  text='[page 3] Table 1. 2022 Great Northern Variety Trial— Scottsbluff Ag Lab. Ent PEDIGREE Yield at 14% Flowering Maturity Plant Height Test Weight Moisture no lbs/acre days days inches lbs/bu % gr 15 White Pearl 3633 47 83 17.1 59.2 10.6 34.1 [page 4] Table 2. 2022 Great Northern Variety Trial— Mitchell Ag Lab. Ent PEDIGREE Yield at 14% Flowering Maturity Plant Height Test Weight Moisture no lbs/acre days days inches lbs/bu % gr 15 White Pearl 5057 50 103 16.9 59.4 11.6 40.8 '+'trial conditions and original source notes. '*20
  text2='Great Northerns, navy beans or mixes of beans, are the most likely to be sold as whole seeds in unprocessed form. In Missouri, rains at the time of harvest can cause discoloration in the seed, especially of a navy (white) bean type. '+'This independent production guide concerns harvested dry seed, market classes and harvest quality in its original regional setting. '*10
  docs=[{'url':u,'requested_url':u,'redirect_chain':[u],'text':t,'fetched_at':utcnow(),'sha256':hashlib.sha256(t.encode()).hexdigest()} for u,t in [(p.PDF,text),(p.IOWA,text2)]]
  return topic,old,docs
 def candidate(self):
  topic,old,docs=self.fixture();c=p.build_candidate(topic,old,docs);return topic,old,docs,c,s.validate_candidate(topic,c,docs)
 def good_review(self,facts):
  return {**{k:True for k in r.FLAGS},'decision':'pass','human_review_claimed':False,'limitations':'These are explicitly foreign original source observations; no forecast for Iran, local cultivar equivalence or human agronomy review has been inferred.','fact_checks':[{'fact_id':f['fact_id'],'supported':True,'scope_and_units_correct':True,'reason':'The original observation and its explicit geographic, cultivar and moisture limits remain unchanged.','evidence_quote':f['evidence_quote'][:90]} for f in facts],'rejection_reasons':[]}
 def test_real_units_not_bushel_guesses_and_scope_unchanged(self):
  t,old,d,c,f=self.candidate();self.assertEqual(c['outline'],old['outline']);self.assertEqual(c['slug'],old['slug']);self.assertEqual(c['review_schema_version'],2);self.assertEqual([x['conversion']['target_value'] for x in f if 'conversion' in x],['4072.052','5668.144']);self.assertNotIn('bushel',json.dumps(c));self.assertEqual(len(f),6)
 def test_table_other_column_cannot_be_yield(self):
  t,old,d,c,f=self.candidate();b=c['facts'][0]['numeric_bindings'][0];b['value']='47'
  with self.assertRaises(ValueError):p.table_measurement(b,f[0]['evidence_quote'])
 def test_cultivar_row_must_be_unique_and_unit_and_basis_exact(self):
  t,old,d,c,f=self.candidate();b=c['facts'][0]['numeric_bindings'][0]
  for field,value in [('unit','bu/acre'),('moisture_basis','unadjusted'),('row_label','other cultivar')]:
   bad=copy.deepcopy(b);bad['table_measurement'][field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):p.table_measurement(bad,f[0]['evidence_quote'])
 def test_source_table_must_not_be_a_title_list_or_invented_quote(self):
  self.assertEqual(p.table_windows('Table 1. 2022 Great Northern Variety Trial— Scottsbluff Ag Lab. List of tables only.'),[])
  t,old,d,c,f=self.candidate();b=c['facts'][0]['numeric_bindings'][0];b['unit_quote']=b['unit_quote'].replace('3633','9999')
  with self.assertRaises(ValueError):p.table_measurement(b,f[0]['evidence_quote'])
 def test_detailed_review_requires_bound_quote_and_specific_reason(self):
  t,old,d,c,f=self.candidate();v=self.good_review(f);r.validate(v,f);s.validate_review(v,f);v['fact_checks'][0]['evidence_quote']='This fabricated source quotation is not found in the original table or production guide.'
  with self.assertRaisesRegex(s.EvidenceBlocked,'per_fact_review_quote_not_bound'):r.validate(v,f)
 def test_negative_findings_require_affected_facts_and_reasons(self):
  t,old,d,c,f=self.candidate();v=self.good_review(f);v['decision']='reject';v['units_and_denominators_correct']=False
  with self.assertRaisesRegex(s.EvidenceBlocked,'specific_rejection_reasons_required'):r.validate(v,f)
 def test_inconsistent_review_is_not_passed_or_silently_reversed(self):
  t,old,d,c,f=self.candidate();v=self.good_review(f);v['decision']='reject';v['all_claims_supported']=False;v['rejection_reasons']=[{'flag':'all_claims_supported','fact_ids':['f0'],'reason':'A specific allegedly unsupported source claim must still agree with the corresponding per-fact supported decision.'}]
  with self.assertRaisesRegex(s.EvidenceBlocked,'contradictory'):r.validate(v,f)
 def test_real_negative_review_remains_rejected(self):
  t,old,d,c,f=self.candidate();v=self.good_review(f);v['decision']='reject';v['all_claims_supported']=False;v['fact_checks'][0]['supported']=False;v['rejection_reasons']=[{'flag':'all_claims_supported','fact_ids':['f0'],'reason':'This alleged observation is not supported by the original source measurement as independently assessed by the reviewer.'}]
  with self.assertRaisesRegex(s.EvidenceBlocked,'v2_rejected_or_uncertain'):r.validate(v,f)
 def test_long_table_evidence_roundtrips_without_truncating_unit_context(self):
  t,old,d,c,f=self.candidate();review=self.good_review(f);text='مقاله موجود تنها درباره آماده‌سازی زمین است و هیچ اطلاعات عملکرد یا مشاهده رقم و واحد اندازه‌گیری مربوط به این موضوع را بیان نمی‌کند.';bundle={'topic_id':p.TOPIC,'related_ids':[12],'documents':[{'id':12,'text':text,'text_truncated':False,'sha256':hashlib.sha256(text.encode()).hexdigest()}],'unavailable':[]};overlap={'topic_id':p.TOPIC,'decision':'distinct','human_review_claimed':False,'novelty_reason':'The existing full article addresses land preparation only, and does not answer dry-white-bean yield or the limitations of interpreting any regional trial.','article_checks':[{'id':12,'already_answers_intent':False,'evidence_quote':text,'gap_reason':'The real source paragraph concerns preparation, rather than harvested dry-white-bean yield in a particular trial and its measurement basis.'}],'existing_content_sha256':s.content_digest(bundle)}
  brief=s.build_brief(t,c,d,review,overlap,{'source_generated_at':utcnow(),'records':[]});self.assertTrue(s.verify_brief(brief));self.assertEqual(brief['scoped_review_schema_version'],2);brief['approved_facts'][-1]['conversion']['target_value']='9000'
  with self.assertRaises(s.EvidenceBlocked):s.verify_brief(brief)
 def test_revision_preserves_prior_files_and_attempt_counters(self):
  t,old,docs=self.fixture()
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';ev=out/'new'/p.TOPIC/'lifecycle-evidence';counter=out/'new'/p.TOPIC/'lifecycle/research_review/state.json';atomic_json(ev/'candidate.json',old);atomic_json(ev/'sources.json',{'documents':[{'previous':'source'}]});atomic_json(ev/'review-raw.json',{'decision':'reject'});atomic_json(counter,{'attempts':1,'history':[{'status':'failed'}]});before=counter.read_bytes();fetcher=Mock(side_effect=docs);proof=p.prepare(t,data,out,fetcher);self.assertFalse(proof['approved']);self.assertFalse(proof['prior_review_overridden']);self.assertEqual(counter.read_bytes(),before);self.assertEqual(load_json(ev/'revisions'/p.REVISION/'previous/candidate.json'),old);self.assertEqual(p.prepare(t,data,out,fetcher),proof);self.assertEqual(fetcher.call_count,2)
 def test_revision_cannot_replace_approved_brief_or_other_family(self):
  t,old,docs=self.fixture()
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';atomic_json(out/'new'/p.TOPIC/'lifecycle-evidence/candidate.json',old);atomic_json(data/'briefs'/(p.TOPIC+'.json'),{'approved':True})
   with self.assertRaisesRegex(ValueError,'never_replace'):p.prepare(t,data,out,Mock(side_effect=docs))
   with self.assertRaisesRegex(ValueError,'explicit_white_bean'):p.prepare(dict(t,id='agri-000000000001'),data,out)
 def test_pilot_flag_only_set_by_explicit_pilot_mode(self):
  from automation.agri_v2 import parallel_controller as ctrl
  with patch.object(ctrl,'policy'),patch('automation.agri_v2.family_lifecycle.run',return_value={}) as run:
   ctrl.run('white-bean-pilot',env={});self.assertEqual(run.call_args.args[0]['AFP_WHITE_BEAN_PILOT'],'1');ctrl.run('advance',env={'AFP_WHITE_BEAN_PILOT':'1'});self.assertNotIn('AFP_WHITE_BEAN_PILOT',run.call_args.args[0])

 def test_exactly_one_existing_family_selected_without_reassignment(self):
  rows=[{'id':'agri-'+str(i).zfill(12),'family_id':'family-'+str(i)} for i in range(14)]+[{'id':p.TOPIC,'family_id':'family-05'}];before=copy.deepcopy(rows);self.assertEqual(p.select_topics(rows),[rows[-1]]);self.assertEqual(rows,before)
  with self.assertRaises(ValueError):p.select_topics(rows[:-1])
  with self.assertRaises(ValueError):p.select_topics(rows+[rows[-1]])
 def test_incomplete_revision_never_overwrites_archived_previous_evidence(self):
  t,old,docs=self.fixture()
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';dest=out/'new'/p.TOPIC/'lifecycle-evidence/revisions'/p.REVISION/'previous/candidate.json';atomic_json(dest,old);before=dest.read_bytes()
   with self.assertRaisesRegex(ValueError,'incomplete_revision'):p.prepare(t,data,out,Mock(side_effect=docs))
   self.assertEqual(dest.read_bytes(),before)
 def test_expired_pilot_evidence_not_silently_refreshed_or_reapproved(self):
  t,old,docs=self.fixture()
  with tempfile.TemporaryDirectory() as td:
   data=Path(td)/'data';out=Path(td)/'out';ev=out/'new'/p.TOPIC/'lifecycle-evidence';atomic_json(ev/'candidate.json',old);p.prepare(t,data,out,Mock(side_effect=docs));before=(ev/'sources.json').read_bytes()
   with patch.object(p,'age_hours',return_value=7),self.assertRaisesRegex(ValueError,'expired'):p.prepare(t,data,out,Mock(side_effect=docs))
   self.assertEqual((ev/'sources.json').read_bytes(),before)
