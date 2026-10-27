"""One nonpublishing acceptance test of the practical writer and four translations."""
import hashlib,time
from .queue import DATA,OUT,load_json,atomic_json,get_topic,utcnow
from .matrix_pilot import TOPIC,MAX_CALLS
ID='ops-practical-writer-translation-v1'
CONT_ID='ops-practical-saved-draft-v2'
PRIOR=[('40315021021',1),('40315988391',5),('40318477742',3),('40319208113',1),('40321377851',1)]

def remaining(out=OUT,continuation=False):
 for run,calls in PRIOR:
  row=load_json(out/'parallel/lifecycle/runs'/run/'report.json')
  if row.get('run_id')!=run or row.get('status')!='pilot_incomplete' or row.get('matrix_pilot') is not True or row.get('assigned_count')!=1 or row.get('published_posts')!=0 or row.get('pool',{}).get('model_requests_reserved')!=calls or row.get('pool',{}).get('peak_image_leases')!=0:raise ValueError('preserved_pilot_budget_receipts_required')
  if {r.get('topic_id') for r in row.get('results',[])}!={TOPIC}:raise ValueError('preserved_pilot_topic_receipt_required')
 if continuation:
  first=load_json(out/'parallel/operations'/ID/'prepare.json')
  if first.get('status')!='verification_incomplete' or first.get('failed_stage')!='writer' or first.get('failure',{}).get('category')!='article_length_out_of_bounds' or first.get('model_calls')!=1 or first.get('preserved_original_state') is not True or first.get('published_posts')!=0:raise ValueError('exact_preserved_practical_draft_receipt_required')
 return MAX_CALLS-sum(calls for _,calls in PRIOR)-(1 if continuation else 0)

def preserved(data=DATA,out=OUT):
 paths=[data/'manifest.json',data/'config.json',data/'briefs'/(TOPIC+'.json'),out/'parallel/families/assignments.json']
 paths+=sorted((out/'new'/TOPIC).rglob('*'))
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None):
 from .operation_request import authorize
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id'] not in (ID,CONT_ID):raise ValueError('current_practical_verification_admission_required')
 from .parallel_control import policy,reserve
 policy(env,data)
 rid=load_json(data/'status/owner-operation-admission.json')['request_id'];continuation=rid==CONT_ID
 dest=out/'parallel/operations'/rid;rp=dest/'prepare.json'
 if rp.exists():return {'status':'verification_already_reserved','model_calls':0,'published_posts':0}
 limit=remaining(out,continuation)
 if limit!=(12 if continuation else 13):raise ValueError('exact_original_remaining_budget_required')
 if (reserve if reserve_fn is None else reserve_fn)('operation',rid,env) is None:return {'status':'verification_already_reserved','model_calls':0,'published_posts':0}
 report={'request_id':rid,'run_id':env['GITHUB_RUN_ID'],'started_at':utcnow(),'status':'verification_started','strategy':'practical-direct-html-v1','topic_id':TOPIC,'original_pilot_calls_spent':12 if continuation else 11,'max_total_text_calls':limit,'max_writer_calls':0 if continuation else 1,'max_final_article_reviews':1,'image_calls':0,'wordpress_calls':0,'published_posts':0,'schedule_activated':False,'attempts_reset':False,'publication_authorized':False,'full_publication_proved':False,'steps':[]};atomic_json(rp,report)
 from .provider_diagnostic import active_cooldown
 until=active_cooldown(out)
 if until:report.update(status='verification_shared_cooldown',cooldown_until_epoch=until,completed_at=utcnow());atomic_json(rp,report);return report
 original=preserved(data,out);stage='initialize'
 from .parallel_pool import initialize,snapshot,routing_counts
 db=dest/'pool.sqlite';h=load_json(out/'parallel/health/latest.json')
 initialize(db,h.get('eligible_text_slots',[]),text_limit=1,image_limit=1,max_calls=limit,per_worker=limit,prior_usage=routing_counts(out))
 try:
  from .parallel_client import ParallelModelClient
  worker_env=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=TOPIC,AFP_PARALLEL_FAMILY='practical-verification-only')
  client=(ParallelModelClient if client_factory is None else client_factory)(h,env=worker_env,allow_calls=True,capabilities=('text',))
  topic=get_topic('new',TOPIC,data);brief=load_json(data/'briefs'/(TOPIC+'.json'))
  from .pipeline import check_brief,digest
  check_brief(topic,brief);report['accepted_brief_sha256']=digest(brief)
  folder=out/'parallel/writer-verification'/rid/TOPIC
  from .practical_drafting import generate
  stage='writer'
  if continuation:
   from .practical_drafting import normalize
   raw=load_json(out/'parallel/writer-verification'/ID/TOPIC/'practical-text-candidate.json');atomic_json(folder/'practical-text-candidate.json',raw);article,normalization=normalize(raw,topic,brief);normalization['reused_from_request']=ID;normalization['new_writer_calls']=0;atomic_json(folder/'practical-text-normalization.json',normalization)
  else:article=generate(client,topic,brief,folder)
  atomic_json(folder/'article.json',article);report['steps'].append({'stage':stage,'status':'validated','normalization':load_json(folder/'practical-text-normalization.json')});atomic_json(rp,report)
  stage='final_article_evidence_review'
  from .scoped_research import review_article
  review_article(topic,article,brief,folder,client);report['steps'].append({'stage':stage,'status':'validated'});atomic_json(rp,report)
  from .translation_chunks import translate_segments
  from .multilingual import LANGUAGES,render_translation
  for lang in LANGUAGES:
   stage='translation-'+lang;raw=translate_segments(client,article,lang,folder);path=folder/'translations'/(lang+'.json');atomic_json(path.with_suffix('.raw.json'),raw);row=render_translation(article,raw,lang);atomic_json(path,row);report['steps'].append({'stage':stage,'status':'validated','source_article_sha256':row['source_article_sha256']});atomic_json(rp,report)
  report['status']='verification_completed'
 except Exception as exc:
  from .failure_diagnostics import failure_details
  failure=failure_details(exc)
  from .scoped_research import EvidenceBlocked
  if isinstance(exc,EvidenceBlocked):failure['category']=exc.code
  report.update(status='verification_incomplete',failed_stage=stage,failure=failure)
 finally:
  report['pool']=snapshot(db);report['model_calls']=report['pool']['model_requests_reserved'];report['original_pilot_plus_verification_calls']=(12 if continuation else 11)+report['model_calls'];report['preserved_original_state']=preserved(data,out)==original
  if not report['preserved_original_state']:report['status']='verification_original_state_changed'
  until=report['pool'].get('cooldown_until_epoch',0)
  if until>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':until,'reason':'practical_verification_shared_provider_failure','no_secrets':True})
  report['completed_at']=utcnow();atomic_json(rp,report)
 return report
