import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from automation.agri_v2 import tuning_resume as t,image_backtest as b,cycle,media_policy as m
from automation.agri_v2.queue import DATA,atomic_json,load_json,utcnow
class TuningResumeTests(unittest.TestCase):
 def req(self):return load_json(DATA/'image-tuning-resume-request.json')
 def test_strict_nonpublication_budget(self):
  r=self.req();t.validate(r);r['max_runs']=2
  with self.assertRaises(ValueError):t.validate(r)
 def test_wait_has_no_paid_calls_or_consumed_run(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';r=self.req();r['not_before_epoch']=time.time()+600;atomic_json(data/'image-tuning-resume-request.json',r)
   with patch.object(t,'DATA',data),patch.object(t,'OUT',out),patch.object(t,'update'),patch.object(b,'run') as run:
    self.assertEqual(t.run()['model_calls'],0);run.assert_not_called();self.assertEqual(load_json(out/'image-tuning-resume'/self.req()['request_id']/'receipt.json')['runs_started'],0)
 def test_existing_report_never_retried_even_if_capacity_recovered(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';r=self.req();atomic_json(data/'image-tuning-resume-request.json',r);atomic_json(out/'image-backtests'/r['backtest_request_id']/'report.json',{'status':'stopped_provider_limit_or_failure'})
   with patch.object(t,'DATA',data),patch.object(t,'OUT',out),patch.object(t,'update'),patch.object(b,'run') as run:
    self.assertEqual(t.run()['model_calls'],0);run.assert_not_called()
 def test_due_job_invokes_only_one_bounded_backtest(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';r=self.req();r['not_before_epoch']=time.time()-1;atomic_json(data/'image-tuning-resume-request.json',r);atomic_json(data/'health/latest.json',{'checked_at':utcnow()})
   with patch.object(t,'DATA',data),patch.object(t,'OUT',out),patch.object(t,'circuit_open',return_value=False),patch.object(t,'update'),patch.object(b,'run',return_value={'status':'fixture_complete'}) as run:
    t.run();t.run();self.assertEqual(run.call_count,1)
 def test_expired_evidence_does_not_trigger_mass_key_probe(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d)/'data';out=Path(d)/'out';r=self.req();r['not_before_epoch']=time.time()-1;atomic_json(data/'image-tuning-resume-request.json',r);atomic_json(data/'health/latest.json',{'checked_at':'2020-01-01T00:00:00+00:00'})
   with patch.object(t,'DATA',data),patch.object(t,'OUT',out),patch.object(t,'circuit_open',return_value=False),patch.object(t,'update'),patch.object(b,'run') as run:
    self.assertEqual(t.run()['status'],'needs_fresh_health_evidence');run.assert_not_called()
 def test_scheduled_tuning_does_not_touch_wordpress(self):
  with tempfile.TemporaryDirectory() as d:
   data=Path(d);atomic_json(data/'config.json',{'legacy_one_off_hooks_enabled':True});atomic_json(data/'image-tuning-resume-request.json',self.req())
   with patch.object(cycle,'DATA',data),patch.object(t,'run',return_value={'status':'waiting','model_calls':0}) as run,patch.object(cycle,'WordPress') as wp:
    self.assertEqual(cycle.run(scheduled=True)['model_calls'],0);wp.assert_not_called();run.assert_called_once()
 def test_red_harvest_guide_does_not_leak_to_green_or_pinto_or_other_crop(self):
  red={'crop':'لوبیا قرمز','title':'برداشت لوبیا قرمز'};self.assertEqual(m.reference_images(2,red),m.reference_images())
  for crop in ('لوبیا سبز','لوبیا چیتی','گندم','گوجه فرنگی'):
   self.assertEqual(m.reference_images(2,{'crop':crop,'title':'برداشت '+crop}),m.reference_images())
 def test_provider_deadline_and_retry_after_preserved(self):
  from automation.agri_v2.client import ImageProviderError
  report={'cases':[{'status':'reserved'}]}
  with patch.object(b,'defer_provider',return_value=12345) as defer:
   e=ImageProviderError(503,'image_queue_full','provider_unavailable',900);b.record_provider_failure(e,report);defer.assert_called_once_with(e);self.assertEqual(report['retry_after_seconds'],900);self.assertEqual(report['retry_at_epoch'],12345);self.assertEqual(report['cases'][0]['status'],'provider_rejected')
 def test_exact_reference_echo_not_a_new_model_output(self):
  import base64,io
  from PIL import Image
  from automation.agri_v2.client import render_image,CapabilityError
  out=io.BytesIO();Image.new('RGB',(1312,736),'green').save(out,'PNG');enc=base64.b64encode(out.getvalue()).decode()
  with self.assertRaises(CapabilityError):render_image({'data':[{'b64_json':enc}]},True,['data:image/png;base64,'+enc])
