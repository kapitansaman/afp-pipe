import tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import four_family_research as p,operation_request as op,family_lifecycle as f
from automation.agri_v2.queue import DATA,OUT,atomic_json,load_json,utcnow
from automation.agri_v2.healthcheck import TEXT_MODEL
from automation.agri_v2.parallel_pool import PoolDeferred

class FourFamilyResearchTests(unittest.TestCase):
 def request(self):return dict(p.expected_request(),code_revision='a'*40)
 def env(self):return {'GITHUB_RUN_ID':'7654321','AFP_WP_BASE_URL':'test-only','AFP_WP_USERNAME':'test-only','AFP_WP_APP_PASSWORD':'test-only'}
 def fixture(self,root):
  data=root/'data';out=root/'out'
  for name in ('manifest.json','parallel-policy.json'):atomic_json(data/name,load_json(DATA/name))
  for entry in load_json(DATA/'manifest.json')['files']:
   rel=Path(*Path(entry['path']).parts[2:]);(data/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DATA/rel,data/rel)
  atomic_json(data/'status/owner-operation-admission.json',{'request_id':p.ID})
  for ident in p.FAMILIES.values():shutil.copytree(OUT/'new'/ident,out/'new'/ident)
  atomic_json(out/'new/protected/proof.json',{'attempts':3})
  atomic_json(out/'parallel/families/assignments.json',{'families':[{'family_id':k,'topic_id':v} for k,v in p.FAMILIES.items()]})
  h=load_json(OUT/'parallel/health/latest.json');h['checked_at']=utcnow();atomic_json(out/'parallel/health/latest.json',h)
  return data,out
 def test_exact_request_rejects_expanded_scope(self):
  self.assertEqual(op.validate_request(self.request())['request_id'],p.ID)
  for key,value in [('max_total_text_calls',9),('max_text_calls_per_family',3),('max_image_calls',1),('max_wordpress_mutations',1),('enable_schedule',True),('reset_attempts',True),('family_topics',{})]:
   row=self.request();row[key]=value
   with self.assertRaises(ValueError):op.validate_request(row)
 def test_budget_two_per_family_and_eight_total(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for ident in p.FAMILIES.values():
    for _ in range(2):p.charge(root,ident,'text',TEXT_MODEL)
    with self.assertRaises(PoolDeferred):p.charge(root,ident,'text',TEXT_MODEL)
   self.assertEqual(load_json(root/'model-calls.json')['text'],8)
 def test_image_unknown_topic_and_model_never_charged(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);ident=next(iter(p.FAMILIES.values()))
   for topic,kind,model in [(ident,'image',TEXT_MODEL),('other','text',TEXT_MODEL),(ident,'text','other')]:
    with self.assertRaises(ValueError):p.charge(root,topic,kind,model)
   self.assertFalse((root/'model-calls.json').exists())
 def test_no_writer_image_translation_or_publisher_stage(self):
  for stage in ('text','images','publish','translation','source_publish','complete','blocked') :self.assertFalse(p.permitted(stage))
  for stage in ('research_validate_saved','research_review','existing_content_audit-004','existing_content_audit_finalize'):self.assertTrue(p.permitted(stage))
 def test_unadmitted_run_stops_before_reservation(self):
  reserve=Mock()
  with patch.object(op,'authorize',return_value=False):
   with self.assertRaises(ValueError):p.run(self.env(),reserve_fn=reserve)
  reserve.assert_not_called()
 def test_advance_local_is_free_and_stops_after_two_paid_stages(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);topic={'id':next(iter(p.FAMILIES.values()))};stages=iter([('research_validate_saved',''),('existing_content_audit-000',''),('existing_content_audit-001',''),('existing_content_audit-002','')])
   def execute(topic,stage,*args):
    if not p.local_stage(stage):p.charge(root,topic['id'],'text',TEXT_MODEL)
   def attempt(folder,stage,run,fn,**kwargs):fn();return {'status':'stage_completed'}
   with patch.object(f,'settings',return_value={'max_attempts_per_stage':3}),patch.object(f,'next_stage',side_effect=lambda *a:next(stages)),patch.object(f,'run_stage',side_effect=execute),patch.object(f,'attempt',side_effect=attempt),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=0):
    result=p.advance(topic,self.env(),Mock(),root,root/'data',root/'out')
   self.assertEqual(result['status'],'bounded_checkpoint_saved');self.assertEqual(load_json(root/'model-calls.json')['text'],2);self.assertEqual(len(result['steps']),3)
 def test_existing_exhausted_attempts_are_not_reset(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);topic={'id':next(iter(p.FAMILIES.values()))};folder=root/'out/new'/topic['id'];atomic_json(f.row_path(folder,'research_review'),{'attempts':3,'history':[]})
   client=Mock()
   with patch.object(f,'settings',return_value={'max_attempts_per_stage':3}),patch.object(f,'next_stage',return_value=('research_review','')),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=0):
    result=p.advance(topic,self.env(),client,root,root/'data',root/'out')
   self.assertEqual(result['status'],'stage_budget_exhausted');client.assert_not_called();self.assertEqual(load_json(f.row_path(folder,'research_review'))['attempts'],3)
 def test_provider_hold_makes_zero_requests(self):
  with tempfile.TemporaryDirectory() as t:
   data,out=self.fixture(Path(t));factory=Mock()
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy'),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=1):result=p.run(self.env(),data,out,client_factory=factory,reserve_fn=Mock(return_value={}))
   self.assertEqual(result['status'],'four_family_research_provider_deferred');self.assertEqual(result['model_calls'],0);factory.assert_not_called()
 def test_run_isolates_changed_corpus_and_family_failure(self):
  with tempfile.TemporaryDirectory() as t:
   data,out=self.fixture(Path(t));root=out/'parallel/operations'/p.ID;seen=[];ids=list(p.FAMILIES.values())
   def prefetch(topics,inventory,wp,dest,run,**kwargs):
    self.assertEqual(kwargs.get('data'),data)
    for topic in topics:
     ident=topic['id'];row=load_json(out/'new'/ident/'lifecycle-evidence/existing-content.json')
     if ident==ids[0]:row['related_ids']=[987654321]
     atomic_json(dest/'new'/ident/'lifecycle-evidence/existing-content.json',row)
    return {'status':'completed'}
   class Fake:
    def __init__(self,h,env,**kwargs):seen.append(env)
   def advance(topic,*args):
    if topic['id']==ids[1]:raise ValueError('test family failure')
    return {'status':'bounded_checkpoint_saved','next_stage':'research_review'}
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_control.policy'),patch('automation.agri_v2.provider_diagnostic.active_cooldown',return_value=0),patch('automation.agri_v2.scoped_research.prefetch_existing',side_effect=prefetch),patch('automation.agri_v2.pipeline.fresh_inventory'):
    result=p.run(self.env(),data,out,client_factory=Fake,reserve_fn=Mock(return_value={}),wp_factory=lambda:Mock(inventory=lambda:{}),advance_fn=advance)
    replay=p.run(self.env(),data,out,reserve_fn=Mock(return_value={}))
   self.assertEqual([x['status'] for x in result['results']],['existing_content_changed_requires_reaudit','family_needs_review','bounded_checkpoint_saved','bounded_checkpoint_saved'],str(result))
   self.assertEqual(replay['status'],'four_family_research_already_reserved');self.assertEqual(result['image_calls'],0);self.assertEqual(result['wordpress_mutations'],0)
   self.assertEqual(len(seen),3)
   for env in seen:self.assertFalse(any(k.startswith('AFP_WP_') for k in env))
   for key in ('other_topics_unchanged','prior_selected_snapshots_unchanged','assignments_unchanged','manifest_unchanged'):self.assertTrue(result[key])
 def test_second_phase_reads_only_current_receipt(self):
  with tempfile.TemporaryDirectory() as t:
   data=Path(t)/'data';out=Path(t)/'out';atomic_json(data/'status/owner-operation-admission.json',{'request_id':p.ID});atomic_json(out/'parallel/operations'/p.ID/'prepare.json',{'run_id':'7654321','status':'four_family_research_complete'})
   with patch.object(op,'authorize',return_value=True):
    self.assertTrue(p.result(self.env(),data,out)['verification_phase_only'])
    with self.assertRaises(ValueError):p.result({'GITHUB_RUN_ID':'other'},data,out)
