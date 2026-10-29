import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from automation.agri_v2.queue import atomic_json,load_json
from automation.agri_v2 import scoped_research as s,three_source_trial as t,operation_request as op
BASE=load_json(Path(__file__).parent/'fixtures/three-source-saved-extractions.json')
class ExtractionSalvageTests(unittest.TestCase):
 def test_saved_continuation_has_only_36_remaining_not_42(self):
  r=t.expected_request(t.SAVED_ID);op.validate_request(dict(r,code_revision='a'*40));self.assertEqual((r['max_total_model_calls'],r['max_total_text_calls'],r['max_model_calls_per_family']),(36,21,12));self.assertEqual(r['prior_total_model_calls']+r['max_total_model_calls'],42)
  with self.assertRaises(ValueError):op.validate_request(dict(r,code_revision='a'*40,max_total_model_calls=42))
 def test_actual_saved_outputs_drop_invalid_facts_without_rewriting(self):
  for ident,row in BASE.items():
   with self.subTest(topic=ident):
    candidate,report=s.normalize_saved_candidate(row['topic'],row['candidate'],row['sources']['documents']);self.assertEqual(len(candidate['facts']),7 if ident==t.TOPICS[2] else 5);self.assertFalse(report['claims_rewritten']);self.assertFalse(report['scientific_rejection_overridden']);self.assertTrue(report['independent_review_still_required']);s.validate_candidate(row['topic'],candidate,row['sources']['documents'])
    self.assertTrue(all(f['claim'] in [x['claim'] for x in row['candidate']['facts']] for f in candidate['facts']))
 def test_new_extraction_rejects_legacy_response_without_backfilling_context(self):
  for ident,row in BASE.items():
   with self.subTest(topic=ident),tempfile.TemporaryDirectory() as d:
    data=Path(d)/'data';out=Path(d)/'out';ev=out/'new'/ident/'lifecycle-evidence';atomic_json(ev/'sources.json',row['sources']);client=Mock();client.text.return_value=copy.deepcopy(row['candidate'])
    from automation.agri_v2.claim_policy import PolicyBlocked
    with patch.object(s,'entries_for',return_value=[]),self.assertRaises(PolicyBlocked):s.stage(row['topic'],'research_extract',client,data,out)
    client.text.assert_called_once();self.assertEqual(load_json(ev/'candidate-raw.json'),row['candidate']);self.assertFalse((ev/'candidate.json').exists());self.assertFalse((data/'briefs'/(ident+'.json')).exists())
 def test_scientific_insufficiency_never_flipped_or_approved(self):
  row=BASE[t.TOPICS[2]];raw=copy.deepcopy(row['candidate']);raw['answers_intent']=False
  with self.assertRaises(s.EvidenceBlocked):s.normalize_saved_candidate(row['topic'],raw,row['sources']['documents'])
 def test_too_few_valid_facts_still_reject(self):
  row=BASE[t.TOPICS[0]];raw=copy.deepcopy(row['candidate']);raw['facts']=raw['facts'][:3]
  with self.assertRaises(s.EvidenceBlocked):s.normalize_saved_candidate(row['topic'],raw,row['sources']['documents'])
