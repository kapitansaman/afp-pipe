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
 def test_continuation_cannot_reset_or_expand_remaining_budget(self):
  req=self.req();req.update(request_id=m.CONTINUATION_ID,operation='continue-commercial-matrix-family',max_worker_model_calls=23,prior_run_id=m.PRIOR_RUN);op.validate_request(req)
  for key,value in [('max_worker_model_calls',24),('prior_run_id','another'),('max_image_generations',3),('reset_attempts',True)]:
   bad=dict(req);bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
 def test_remaining_budget_requires_exact_actual_zero_publication_receipt(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);row={'run_id':m.PRIOR_RUN,'status':'pilot_incomplete','matrix_pilot':True,'assigned_count':1,'published_posts':0,'pool':{'model_requests_reserved':1,'peak_image_leases':0},'results':[{'topic_id':m.TOPIC}]};p=out/'parallel/lifecycle/runs'/m.PRIOR_RUN/'report.json';atomic_json(p,row);e={'AFP_MATRIX_PILOT_ID':m.CONTINUATION_ID};self.assertEqual(m.budget(e,out=out),23)
   row['pool']['model_requests_reserved']=2;atomic_json(p,row)
   with self.assertRaises(ValueError):m.budget(e,out=out)
 def test_literal_short_temperature_quote_valid_but_invented_or_unitless_is_not(self):
  from automation.agri_v2.scoped_research import validate_fact
  entry={'id':'e','source_url':'https://extension.usu.edu/carrots','quote':'Carrots can be sown after soils reach 40°F. Maintain a uniform and moist soil surface.'}
  fact={'evidence_id':'e','kind':'source_observation','claim':'در منبع، دمای خاک برای کاشت هویج 40 درجه فارنهایت ذکر شده است.','conditions':'این مشاهده مربوط به راهنمای یوتا در آمریکاست و توصیهٔ محلی برای ایران یا تضمین سبزشدن نیست.','numeric_bindings':[{'value':'40','unit_quote':'40°F','geographic_scope':'Utah, USA','product_scope':'carrot seed establishment'}]}
  validate_fact(fact,0,{'e':entry})
  for badquote in ['40','41°F']:
   bad=__import__('copy').deepcopy(fact);bad['numeric_bindings'][0]['unit_quote']=badquote
   with self.assertRaises(ValueError):validate_fact(bad,0,{'e':entry})
 def test_recheck_request_bound_to_18_remaining_calls(self):
  req=self.req();req.update(request_id=m.RECHECK_ID,operation='recheck-commercial-matrix-overlap',max_worker_model_calls=18,prior_run_id=m.RECHECK_PRIOR_RUN);op.validate_request(req)
  for key,value in [('max_worker_model_calls',19),('prior_run_id',m.PRIOR_RUN),('enable_schedule',True),('reset_attempts',True),('max_pilot_families',2)]:
   bad=dict(req);bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
 def test_recheck_budget_counts_both_actual_prior_runs(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);base={'status':'pilot_incomplete','matrix_pilot':True,'assigned_count':1,'published_posts':0}
   first=dict(base,run_id=m.PRIOR_RUN,pool={'model_requests_reserved':1,'peak_image_leases':0},results=[{'topic_id':m.TOPIC}]);atomic_json(out/'parallel/lifecycle/runs'/m.PRIOR_RUN/'report.json',first)
   second=dict(base,run_id=m.RECHECK_PRIOR_RUN,pool={'model_requests_reserved':5,'peak_image_leases':0},results=[{'topic_id':m.TOPIC,'stage':'existing_content_audit-004','failure':{'category':'existing_content_overlap_or_uncertain'}}]);p=out/'parallel/lifecycle/runs'/m.RECHECK_PRIOR_RUN/'report.json';atomic_json(p,second)
   e={'AFP_MATRIX_PILOT_ID':m.RECHECK_ID};self.assertEqual(m.budget(e,out=out),18)
   for key,value in [('published_posts',1),('assigned_count',2),('pool',{'model_requests_reserved':6,'peak_image_leases':0})]:
    bad=dict(second);bad[key]=value;atomic_json(p,bad)
    with self.assertRaises(ValueError):m.budget(e,out=out)
 def test_text_retry_cannot_expand_budget_or_reset_accepted_research(self):
  req=self.req();req.update(request_id=m.TEXT_ID,operation='retry-commercial-matrix-text',max_worker_model_calls=15,prior_run_id=m.TEXT_PRIOR_RUN);op.validate_request(req)
  for key,value in [('max_worker_model_calls',16),('prior_run_id',m.PRIOR_RUN),('enable_schedule',True),('reset_attempts',True)]:
   bad=dict(req);bad[key]=value
   with self.assertRaises(ValueError):op.validate_request(bad)
