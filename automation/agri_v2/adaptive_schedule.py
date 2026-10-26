"""Measured 20-family cadence, never learned from failure/blocked/partial runs."""
import argparse,concurrent.futures,hashlib,json,math,os,time
from .queue import DATA,OUT,atomic_json,load_json,utcnow,age_hours
from .parallel_capacity import MAX_FAMILIES,CREDENTIAL_SET_ID

def settings(data=DATA):
 p=load_json(data/'adaptive-schedule-policy.json')
 if p.get('version')!=1 or p.get('sample_families')!=MAX_FAMILIES or p.get('min_interval_seconds')!=300 or p.get('max_interval_seconds')!=14400 or p.get('poll_seconds')!=5 or not 1.05<=p.get('safety_factor',0)<=1.5 or not 1.05<=p.get('tail_factor',0)<=1.5:raise ValueError('Invalid bounded adaptive schedule policy')
 return p

def binding(data=DATA):
 from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
 cfg=load_json(data/'config.json');p=load_json(data/'family-lifecycle-policy.json')
 return hashlib.sha256(json.dumps({'cohort':CREDENTIAL_SET_ID,'families':MAX_FAMILIES,'text_model':TEXT_MODEL,'image_model':IMAGE_MODEL,'api_base':API_BASE,'images_per_family':2,'multilingual':cfg.get('multilingual',{}),'requests_per_family':p['max_model_requests_per_family']},sort_keys=True).encode()).hexdigest()

def current(data=DATA,out=OUT):
 p=settings(data);path=out/'parallel/scheduling/state.json'
 state=load_json(path) if path.exists() else {'version':1,'calibrated':False,'interval_seconds':p['initial_reference_seconds'],'history':[]}
 value=state.get('interval_seconds')
 if type(value)is not int or not p['min_interval_seconds']<=value<=p['max_interval_seconds']:raise ValueError('Invalid cadence state; do not silently reset')
 return state

class Observer:
 def __init__(self,topic_ids,run_id,fresh_start,data=DATA,out=OUT,clock=time.monotonic):
  self.ids=set(topic_ids);self.run_id=run_id;self.fresh=fresh_start;self.data=data;self.out=out;self.clock=clock;self.start=clock();self.p=settings(data);self.old=current(data,out);self.interval=self.old['interval_seconds'];self.tail=False;self.proposed=self.interval;self.ready=set();self.finished=set();self.failed=set();self.events=[];self.active=set(self.ids)
 def rounded(self,value):return min(self.p['max_interval_seconds'],max(self.p['min_interval_seconds'],int(math.ceil(value/60)*60)))
 def observe(self,results,active_topic_ids=None):
  self.ready={r['topic_id'] for r in results if r.get('topic_id') in self.ids and r.get('status')=='publication_ready'};self.finished={r['topic_id'] for r in results if r.get('topic_id') in self.ids};self.failed=self.finished-self.ready
  elapsed=max(0,self.clock()-self.start);self.active=(self.ids-self.finished) if active_topic_ids is None else set(active_topic_ids)&self.ids;pending=len(self.active)
  # Only valid built families count. Failed, blocked or quota-deferred workers are not slow successful work.
  if len(self.ids)==MAX_FAMILIES and len(self.ready)>=math.ceil(.8*MAX_FAMILIES) and pending and not self.failed and elapsed>=self.interval and not self.tail:
   self.tail=True;self.proposed=self.rounded(max(self.interval*self.p['tail_factor'],elapsed*self.p['safety_factor']));self.events.append({'event':'at_least_80_percent_built_with_active_tail','elapsed_seconds':round(elapsed,3),'built_families':len(self.ready),'active_families':pending,'proposed_interval_seconds':self.proposed})
  return self.snapshot()
 def snapshot(self):return {'elapsed_seconds':round(max(0,self.clock()-self.start),3),'reference_interval_seconds':self.interval,'proposed_interval_seconds':self.proposed,'built_validated_families':len(self.ready),'terminal_not_built':len(self.failed),'active_families':len(self.active),'completion_definition':'article, required images, reviews and translations validated; publication verified separately','tail_adjustment_observed':self.tail,'events':self.events}
 def finish(self,report,verified_family_ids):
  self.observe(report.get('results',[]));elapsed=max(0,self.clock()-self.start)
  eligible=(len(self.ids)==MAX_FAMILIES and self.fresh and self.ready==self.ids and set(verified_family_ids)==self.ids and not report.get('operational_failures') and report.get('status')=='completed')
  reason='invalid_partial_resumed_or_unpublished_sample_no_learning';new=self.interval
  if eligible:
   measured=self.rounded(elapsed*self.p['safety_factor']);new=max(measured,self.proposed) if self.tail else measured
   reason='first_verified_20_family_calibration' if not self.old.get('calibrated') else ('all_finished_early_reduce_interval' if new<self.interval else 'measured_full_cycle_with_safety_margin')
  row=dict(self.snapshot(),run_id=self.run_id,sample_eligible=eligible,fresh_start=self.fresh,verified_complete_families=len(set(verified_family_ids)&self.ids),decision=reason,interval_seconds=new,observed_at=utcnow())
  state=dict(self.old,version=1,interval_seconds=new,last_observation=row,history=(self.old.get('history',[])+[row])[-30:])
  if eligible:state.update(calibrated=True,calibration_binding=binding(self.data),calibration_run_id=self.run_id,calibrated_at=utcnow(),next_due_epoch=time.time()+max(0,new-elapsed))
  atomic_json(self.out/'parallel/scheduling/state.json',state);return row

def completed(futures,tick,poll_seconds=5):
 pending=set(futures)
 while pending:
  done,pending=concurrent.futures.wait(pending,timeout=poll_seconds,return_when=concurrent.futures.FIRST_COMPLETED)
  tick()
  for future in done:yield future

def scheduled_context(env):
 return env.get('GITHUB_REPOSITORY')=='kapitansaman/afp-pipe' and env.get('GITHUB_WORKFLOW_REF')=='kapitansaman/afp-pipe/.github/workflows/afp-agri-v2-scheduled.yml@refs/heads/main' and env.get('GITHUB_EVENT_NAME') in ('schedule','workflow_dispatch') and str(env.get('GITHUB_RUN_ID','')).isdigit()

def gate(env=None,data=DATA,out=OUT,now=None):
 env=os.environ if env is None else env;now=time.time() if now is None else now;p=settings(data);state=current(data,out)
 if not scheduled_context(env):return {'should_run':False,'reason':'wrong_scheduler_context'}
 if p.get('enabled') is not True:return {'should_run':False,'reason':'automatic_schedule_not_activated'}
 if not state.get('calibrated') or state.get('calibration_binding')!=binding(data):return {'should_run':False,'reason':'verified_20_family_timing_required'}
 from .production_readiness import inspect
 readiness=inspect(data=data,out=out)
 if not readiness['technical_ready']:return {'should_run':False,'reason':'production_readiness_blocked','blockers':readiness['blockers']}
 if now<state.get('next_due_epoch',float('inf')):return {'should_run':False,'reason':'not_due','next_due_epoch':state.get('next_due_epoch')}
 return {'should_run':True,'reason':'due_and_proven_ready','interval_seconds':state['interval_seconds']}

def admitted(env,data=DATA,out=OUT):
 path=out/'parallel/scheduling/admission.json'
 try:
  row=load_json(path)
  return scheduled_context(env) and settings(data).get('enabled') is True and row.get('run_id')==env['GITHUB_RUN_ID'] and row.get('calibration_binding')==binding(data) and 0<=age_hours(row['admitted_at'])<2
 except (OSError,KeyError,TypeError,ValueError):return False

def run(env=None,data=DATA,out=OUT):
 env=dict(os.environ if env is None else env);decision=gate(env,data,out)
 path=out/'parallel/scheduling/latest-gate.json'
 previous=load_json(path) if path.exists() else {}
 if {k:v for k,v in previous.items() if k!='checked_at'}!=decision:atomic_json(path,dict(decision,checked_at=utcnow()))
 if not decision['should_run']:return dict(decision,model_calls=0,published_posts=0)
 atomic_json(out/'parallel/scheduling/admission.json',{'run_id':env['GITHUB_RUN_ID'],'calibration_binding':binding(data),'admitted_at':utcnow()})
 from .family_lifecycle import run as advance
 started=time.time();result=advance(env,data,out)
 # Failed/partial work never causes a rapid paid retry loop. Respect provider Retry-After.
 state=current(data,out);cooldown=load_json(out/'provider-circuit.json') if (out/'provider-circuit.json').exists() else {};state['next_due_epoch']=max(started+state['interval_seconds'],time.time()+settings(data)['min_interval_seconds'],cooldown.get('retry_at_epoch',0) if cooldown.get('open') else 0);atomic_json(out/'parallel/scheduling/state.json',state)
 return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
