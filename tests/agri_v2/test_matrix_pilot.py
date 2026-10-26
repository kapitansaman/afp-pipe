import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from automation.agri_v2 import matrix_pilot as m,operation_request as op,family_lifecycle as f
from automation.agri_v2.queue import atomic_json,load_json,items
import test_family_lifecycle as fixture
class MatrixPilotTests(unittest.TestCase):
 def req(self):return {'version':1,'request_id':m.ID,'operation':'one-commercial-matrix-family','authorized':True,'max_text_health_calls':0,'max_image_health_calls':0,'max_pilot_families':1,'enable_schedule':False,'reset_attempts':False,'code_revision':'b'*40,'topic_id':m.TOPIC,'max_worker_model_calls':24,'max_image_generations':2,'max_source_posts':1,'max_translations':4,'max_total_posts':5}
 def test_exact_single_family_and_no_budget_reset_or_schedule(self):
  op.validate_request(self.req())
  for key,value in [('topic_id','agri-000000000001'),('max_worker_model_calls',25),('max_image_generations',3),('max_source_posts',2),('max_translations',5),('max_total_posts',6),('reset_attempts',True),('enable_schedule',True)]:
   bad=self.req();bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
 def test_pilot_requires_current_owner_admission(self):
  self.assertFalse(m.bound({}));self.assertFalse(m.bound({'AFP_MATRIX_PILOT_ID':m.ID}))
 def test_fresh_topic_only_no_overwrite_hold_or_double_owner(self):
  t=next(x for x in items('new') if x['id']==m.TOPIC)
  for case in ['clean','hold','owned','backlog','old_output','old_brief','old_research']:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as td:
    d=Path(td)/'data';o=Path(td)/'out';atomic_json(d/'config.json',{'publication_holds':{m.TOPIC:'keep'} if case=='hold' else {}})
    if case=='owned':atomic_json(o/'parallel/families/assignments.json',{'families':[{'topic_id':m.TOPIC}],'research_backlog':{}})
    if case=='backlog':atomic_json(o/'parallel/families/assignments.json',{'families':[],'research_backlog':{m.TOPIC:{}}})
    if case=='old_output':atomic_json(o/'new'/m.TOPIC/'cycle-attempts.json',{'attempts':2})
    if case=='old_brief':atomic_json(d/'briefs'/(m.TOPIC+'.json'),{'approved':True})
    if case=='old_research':atomic_json(o/'research'/(m.TOPIC+'.json'),{'attempts':2})
    with patch.object(m,'bound',return_value=True),patch.object(m,'get_topic',return_value=t):
     if case=='clean':self.assertEqual([x['id'] for x in m.select({},d,o)],[m.TOPIC])
     else:
      with self.assertRaises(ValueError):m.select({},d,o)
 def test_current_operation_selects_matrix_mode_not_old_whitebean(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'data';o=Path(td)/'out';atomic_json(d/'status/owner-operation-admission.json',{'request_id':m.ID});atomic_json(o/'parallel/operations'/m.ID/'prepare.json',{'run_id':'10','status':'pilot_prerequisites_passed'})
   with patch.object(op,'authorize',return_value=True),patch('automation.agri_v2.parallel_controller.run',return_value={}) as run:op.pilot({'GITHUB_RUN_ID':'10'},d,o)
   self.assertEqual(run.call_args.args[0],'advance');self.assertEqual(run.call_args.args[1]['AFP_MATRIX_PILOT_ID'],m.ID);self.assertNotIn('AFP_FULL_QUEUE_RESEARCH_ONLY',run.call_args.args[1])
 def test_coordinator_keeps_20_owner_assignments_untouched_and_one_publisher(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=fixture.FamilyLifecycleTests().setup(td);t=dict(t,id=m.TOPIC);e['AFP_MATRIX_PILOT_ID']=m.ID;wp=Mock();wp.inventory.return_value={'source_generated_at':__import__('automation.agri_v2.queue',fromlist=['utcnow']).utcnow(),'scope':'all public posts','records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   def worker(topic,workspace,db,*args):return topic['id'],workspace/'data',workspace/'out',{'topic_id':topic['id'],'status':'publication_ready'}
   with patch.object(m,'bound',return_value=True),patch.object(m,'select',return_value=[t]),patch.object(f,'allocate',side_effect=AssertionError('Do not change 20 ownership assignments')),patch.object(f,'next_stage',return_value=('publish',None)),patch.object(f,'publish_ready',return_value={'published_posts':5}) as publish,patch.object(f,'family_complete',return_value=True):r=f.run(e,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   self.assertEqual(r['assigned_count'],1);self.assertEqual(r['max_total_model_calls'],24);self.assertEqual(r['published_posts'],5);self.assertTrue(r['matrix_pilot_complete']);self.assertEqual(publish.call_count,1)
 def test_no_success_claim_when_pilot_did_not_complete(self):
  with tempfile.TemporaryDirectory() as td:
   d,o,t,e,h=fixture.FamilyLifecycleTests().setup(td);e['AFP_MATRIX_PILOT_ID']=m.ID;wp=Mock();wp.inventory.return_value={'source_generated_at':__import__('automation.agri_v2.queue',fromlist=['utcnow']).utcnow(),'scope':'all public posts','records':[{'id':1,'title':'Other','url':'https://navar-abyari.ir/other/','status':'publish'}]}
   def worker(topic,workspace,db,*args):return topic['id'],workspace/'data',workspace/'out',{'topic_id':topic['id'],'status':'stage_failed'}
   with patch.object(m,'bound',return_value=True),patch.object(m,'select',return_value=[t]),patch.object(f,'allocate',side_effect=AssertionError()),patch.object(f,'next_stage',return_value=('blocked','evidence')),patch.object(f,'family_complete',return_value=False):r=f.run(e,d,o,worker_fn=worker,wp_factory=lambda:wp,reserve_fn=lambda *_:{})
   self.assertEqual(r['status'],'pilot_incomplete');self.assertEqual(r['published_posts'],0)
