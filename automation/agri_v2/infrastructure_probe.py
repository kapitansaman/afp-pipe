"""One isolated live text-cycle probe; no site, search, images or translations."""
import base64,hashlib,json,time,urllib.request,urllib.error
from pathlib import Path
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow,age_hours,items
from .pipeline import digest,check_brief
ID='mixed-knowledge-infrastructure-probe-v1'
CONTINUATION_ID='mixed-knowledge-infrastructure-continuation-v1'
REQUESTS={ID:'infrastructure-probe-request.json',CONTINUATION_ID:'infrastructure-probe-continuation-request.json'}
LIMIT=4
STAGES=('writer','review','repair','recheck')
class ProbeBlocked(ValueError):pass

def code_hash():
 paths=sorted((ROOT/'automation/agri_v2').rglob('*.py'))+sorted((DATA/'role-skills').glob('*.md'))+[ROOT/'.github/workflows/afp-parallel-generator.yml',ROOT/'.github/scripts/persist-agri-v2.sh']
 return digest({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})

def select(data=DATA,out=OUT):
 from .queue_exceptions import queued
 cfg=load_json(data/'config.json')
 for topic in items('new',data):
  ident=topic['id'];p=data/'briefs'/(ident+'.json')
  if not p.exists() or ident in cfg.get('publication_holds',{}) or queued(ident,out) or (out/'new'/ident/'wordpress-receipt.json').exists():continue
  try:
   brief=load_json(p);check_brief(topic,brief)
   if brief.get('review_mode')!='automated_scoped_evidence_review_v1':continue
  except (ValueError,KeyError,TypeError,OSError):continue
  return topic,brief
 raise ProbeBlocked('probe_no_source_ready_unpublished_input')

def expected(topic,brief,request_id=ID):
 if request_id not in REQUESTS:raise ProbeBlocked('probe_unknown_admission')
 return {'version':1,'request_id':request_id,'max_runs':1,'max_model_calls':LIMIT,'max_repairs':1,'max_input_chars_per_call':200000,'max_output_tokens_per_call':14000,'max_search_requests':0,'max_image_calls':0,'max_translation_calls':0,'max_site_calls':0,'publication_authorized':False,'schedule_enabled':False,'reset_attempts':False,'topic_id':topic['id'],'topic_sha256':digest(topic),'brief_sha256':digest(brief),'code_sha256':code_hash()}

def validate(req,data=DATA,out=OUT,request_id=ID):
 topic,brief=select(data,out)
 if not isinstance(req,dict) or set(req)!=set(expected(topic,brief,request_id)) or any(type(req.get(k))is not type(v) or req.get(k)!=v for k,v in expected(topic,brief,request_id).items()):raise ProbeBlocked('probe_request_or_inputs_changed')
 from .quality_index import policy
 if not policy(data):raise ProbeBlocked('probe_independent_quality_policy_required')
 return topic,brief

def identity(env):
 from .parallel_control import BRANCH,REPO
 if env.get('GITHUB_ACTIONS')!='true' or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REPOSITORY')!=REPO or env.get('GITHUB_REF_NAME')!=BRANCH or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ProbeBlocked('probe_exact_manual_identity_required')

def reserve(env,request_id=ID):
 if request_id not in REQUESTS:raise ProbeBlocked('probe_unknown_admission')
 from .parallel_control import BRANCH,REPO,NoRedirect
 identity(env)
 if not env.get('GITHUB_TOKEN'):raise ProbeBlocked('probe_durable_reservation_missing')
 row={'request_id':request_id,'run_id':env['GITHUB_RUN_ID'],'status':'reserved','max_model_calls':LIMIT,'publication_authorized':False,'at':utcnow()}
 payload={'message':'Reserve one isolated infrastructure probe [skip ci]','branch':BRANCH,'content':base64.b64encode((json.dumps(row,indent=2)+'\n').encode()).decode()}
 req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/contents/data/agri-v2/status/parallel-reservations/'+request_id+'.json',data=json.dumps(payload).encode(),method='PUT',headers={'Authorization':'Bearer '+env['GITHUB_TOKEN'],'Content-Type':'application/json','Accept':'application/vnd.github+json'})
 try:
  with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as response:return response.status==201
 except urllib.error.HTTPError as exc:
  status=exc.code;exc.close()
  if status==422:return False
  raise ProbeBlocked('probe_reservation_rejected_no_calls') from None
 except Exception:raise ProbeBlocked('probe_reservation_uncertain_no_calls') from None

def protected(data,out,request_id=ID):
 values={}
 for scope,root in [('data',Path(data)),('out',Path(out))]:
  for p in root.rglob('*'):
   if not p.is_file():continue
   rel=p.relative_to(root).as_posix()
   if scope=='out' and (rel.startswith(('infrastructure-probes/'+request_id+'/','parallel-runtime/')) or rel in ('parallel/key-routing.json','provider-circuit.json','.writer.lock')):continue
   values[scope+'/'+rel]=hashlib.sha256(p.read_bytes()).hexdigest()
 return values

class CountedClient:
 """Intercept all transport requests, not just calls to a writer helper."""
 def __new__(cls,health,worker,root,base_class=None):
  from .parallel_client import ParallelModelClient
  from .healthcheck import TEXT_MODEL
  class Bounded(ParallelModelClient if base_class is None else base_class):
   def request(self,kind,path,payload,timeout,attempts=None):
    stage=self.probe_stage
    if stage not in STAGES or kind!='text' or path!='/chat/completions' or payload.get('model')!=TEXT_MODEL:raise ProbeBlocked('probe_transport_not_allowed')
    if type(payload.get('max_tokens'))is not int or not 256<=payload['max_tokens']<=14000 or len(json.dumps(payload,ensure_ascii=False))>200000 or not 30<=timeout<=180:raise ProbeBlocked('probe_transport_budget_exceeded')
    receipt=root/'calls'/(stage+'.json')
    if receipt.exists() or len(list((root/'calls').glob('*.json')))>=LIMIT:raise ProbeBlocked('probe_request_consumed_no_replay')
    row={'stage':stage,'status':'reserved','request_sha256':digest(payload),'at':utcnow(),'max_attempts':1};atomic_json(receipt,row)
    value=super().request(kind,path,payload,timeout,attempts=1)
    atomic_json(receipt,dict(row,status='response_received',response_sha256=digest(value),completed_at=utcnow()))
    return value
  client=Bounded(health,env=worker,allow_calls=True,capabilities=('text',));client.image_rotation_enabled=False;return client

def stages(client,topic,brief,folder,report):
 from .role_skills import RoleClient
 from .practical_drafting import generate
 from .scoped_research import review_article,EvidenceBlocked
 from .quality_index import bound,repair
 stage='writer';client.probe_stage=stage;report['current_stage']=stage
 article=generate(RoleClient(client,'persian-writer'),topic,brief,folder);atomic_json(folder/'article.json',article);report['steps'].append({'stage':stage,'status':'validated'})
 stage='review';client.probe_stage=stage;report['current_stage']=stage
 try:review_article(topic,article,brief,folder,RoleClient(client,'evidence-reviewer'))
 except EvidenceBlocked:
  assessment=bound(folder,article,brief)
  if not assessment or assessment['accepted']:raise
  report['steps'].append({'stage':stage,'status':'rejected','score':assessment['score']})
  # Preserve the actual negative before the same review paths are used by recheck.
  for name in ('article-evidence-review.raw.json','article-quality-index.json','quality-review-queue.json'):
   source=folder/name;target=folder/'initial-review'/name
   if source.exists():
    if target.exists():raise ProbeBlocked('probe_negative_archive_already_exists')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
  stage='repair';client.probe_stage=stage;report['current_stage']=stage
  repair(topic,article,brief,folder,RoleClient(client,'persian-writer'));report['repair_exercised']=True;report['steps'].append({'stage':stage,'status':'completed_pending_recheck'})
  article=load_json(folder/'article.json');stage='recheck';client.probe_stage=stage;report['current_stage']=stage
  review_article(topic,article,brief,folder,RoleClient(client,'evidence-reviewer'))
 report['steps'].append({'stage':stage,'status':'validated','score':bound(folder,article,brief)['score']})
 report.update(status='probe_text_cycle_passed',article_sha256=digest(article),production_readiness_claimed=False)

def preflight(env,health):
 # Real production constructor, no request/lease: catch ownership/configuration
 # mismatches BEFORE consuming the remote one-shot reservation.
 from .parallel_client import ParallelModelClient
 from .parallel_pool import SLOTS
 worker={k:v for k,v in env.items() if k in SLOTS or k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID')}
 worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB='preflight-no-request',AFP_PARALLEL_FAMILY='isolated-infrastructure-probe')
 client=ParallelModelClient(health,env=worker,allow_calls=True,capabilities=('text',))
 return {'eligible_owned_text_slots':[slot for slot,_ in client.keys['text']],'transport_calls':0}

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None,request_id=ID):
 if request_id not in REQUESTS:raise ProbeBlocked('probe_unknown_admission')
 identity(env);root=Path(out)/'infrastructure-probes'/request_id;rp=root/'report.json'
 if rp.exists():return {'status':'probe_already_reserved_no_replay','model_calls':0,'site_calls':0}
 topic,brief=validate(load_json(data/REQUESTS[request_id]),data,out,request_id)
 health=load_json(out/'parallel/health/latest.json')
 if not 0<=age_hours(health['checked_at'])<24 or not health.get('eligible_text_slots'):raise ProbeBlocked('probe_fresh_text_health_required')
 from .provider_diagnostic import active_cooldown
 if active_cooldown(out):return {'status':'probe_provider_waiting','model_calls':0,'site_calls':0}
 if client_factory is None:preflight(env,health)
 if not (reserve(env,request_id) if reserve_fn is None else reserve_fn(env)):return {'status':'probe_already_reserved_no_replay','model_calls':0,'site_calls':0}
 before=protected(data,out,request_id)
 report={'request_id':request_id,'run_id':env['GITHUB_RUN_ID'],'status':'probe_reserved','started_at':utcnow(),'topic_id':topic['id'],'brief_sha256':digest(brief),'max_model_calls':LIMIT,'max_repairs':1,'repair_exercised':False,'steps':[],'site_calls':0,'site_mutations':0,'image_calls':0,'search_calls':0,'translation_calls':0,'publication_authorized':False,'schedule_enabled':False,'attempts_reset':False,'production_readiness_claimed':False,'protected_before_sha256':digest(before),'source_selection':'first_valid_unpublished_unheld_nonexception_scoped_queue_entry'};atomic_json(rp,report)
 from .parallel_pool import initialize,snapshot,routing_counts,routing_backpressure,record_routing,SLOTS
 db=root/'pool.sqlite';initialize(db,health['eligible_text_slots'],text_limit=1,image_limit=1,max_calls=LIMIT,per_worker=LIMIT,prior_usage=routing_counts(out),prior_backpressure=routing_backpressure(out))
 worker={k:v for k,v in env.items() if k in SLOTS or k in ('GITHUB_ACTIONS','GITHUB_REPOSITORY','GITHUB_REF_NAME','GITHUB_RUN_ID')};worker.update(AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=topic['id'],AFP_PARALLEL_FAMILY='isolated-infrastructure-probe')
 try:
  client=(client_factory or CountedClient)(health,worker,root);stages(client,topic,brief,root/'draft',report)
 except Exception as exc:
  from .failure_diagnostics import failure_details
  from .scoped_research import EvidenceBlocked
  report.update(status='probe_text_cycle_blocked',failure={'kind':'probe_guard','category':str(exc)} if type(exc)is ProbeBlocked else {'kind':'semantic_gate','category':exc.code} if isinstance(exc,EvidenceBlocked) else failure_details(exc))
 finally:
  state=snapshot(db);record_routing(out,state)
  if state['cooldown_until_epoch']>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':state['cooldown_until_epoch'],'reason':'infrastructure_probe_shared_provider_limit'})
  unchanged=protected(data,out,request_id)==before
  if not unchanged:report['status']='probe_originals_changed_reconciliation_required'
  report.update(model_calls=state['model_requests_reserved'],request_receipts=len(list((root/'calls').glob('*.json'))),originals_unchanged=unchanged,completed_at=utcnow());atomic_json(rp,report)
 return report
