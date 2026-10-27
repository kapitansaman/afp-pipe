"""One separately authorized five-call, nonpublishing real-family repair test."""
import hashlib,shutil,time
from .queue import DATA,OUT,atomic_json,load_json,utcnow,get_topic
from .pipeline import digest,check_brief,validate_article,validate_for_publication
from .matrix_pilot import TOPIC
from .practical_verification import EDITORIAL_ID,preserved
from .multilingual import LANGUAGES,render_translation
from .translation_review import binding
ID='ops-translation-local-repair-five-calls-v1'
SOURCE_SHA='0f0b5db296ea501b43e4df91b53b187b13ffa6334f6223f48f8d48d6b150d833'
EDITABLE=['ar-IQ','tg-TJ']

def tree_hashes(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None):
 from .operation_request import authorize
 from .parallel_control import policy,reserve
 if not authorize(env,data) or load_json(data/'status/owner-operation-admission.json')['request_id']!=ID:raise ValueError('exact_five_call_repair_admission_required')
 policy(env,data)
 dest=out/'parallel/operations'/ID;rp=dest/'prepare.json'
 if rp.exists():return {'status':'verification_already_reserved','model_calls':0,'published_posts':0}
 prior=load_json(out/'parallel/operations'/EDITORIAL_ID/'prepare.json')
 if prior.get('original_pilot_plus_verification_calls')!=23 or prior.get('model_calls')!=3 or prior.get('preserved_original_state') is not True or prior.get('published_posts')!=0:raise ValueError('original_23_call_budget_receipt_required')
 source=out/'parallel/writer-verification'/EDITORIAL_ID/TOPIC
 article=load_json(source/'article.json');brief=load_json(data/'briefs'/(TOPIC+'.json'));topic=get_topic('new',TOPIC,data)
 if digest(article)!=SOURCE_SHA:raise ValueError('exact_saved_source_article_required')
 check_brief(topic,brief);validate_article(article,topic,brief);validate_for_publication(article)
 from .scoped_research import validate_article_review_result
 proof=load_json(source/'article-evidence-review.json')
 if proof.get('article_sha256')!=digest(article) or proof.get('brief_sha256')!=digest(brief):raise ValueError('saved_article_review_binding_required')
 validate_article_review_result(article,proof.get('review'))
 prior_review=load_json(source/'translation-fidelity-review.raw.json')
 if prior_review.get('languages')!={'ru-RU':True,'ar-IQ':False,'tg-TJ':False,'en-US':True}:raise ValueError('exact_prior_translation_judgments_required')
 translations={lang:load_json(source/'translations'/(lang+'.json')) for lang in LANGUAGES}
 for lang in LANGUAGES:
  if render_translation(article,load_json(source/'translations'/(lang+'.raw.json')),lang)!=translations[lang]:raise ValueError('source_translation_binding_changed')
 if (reserve if reserve_fn is None else reserve_fn)('operation',ID,env) is None:return {'status':'verification_already_reserved','model_calls':0,'published_posts':0}
 report={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'status':'verification_started','started_at':utcnow(),'topic_id':TOPIC,'max_total_text_calls':5,'max_repair_rounds':2,'editable_languages':EDITABLE,'reviewed_languages':list(LANGUAGES),'separate_authorized_budget':True,'original_pilot_calls_spent':23,'original_pilot_calls_remaining':1,'attempts_reset':False,'image_calls':0,'wordpress_calls':0,'published_posts':0,'schedule_activated':False,'publication_authorized':False,'source_binding':binding(article,translations)};atomic_json(rp,report)
 from .provider_diagnostic import active_cooldown
 until=active_cooldown(out)
 if until:report.update(status='verification_shared_cooldown',cooldown_until_epoch=until,model_calls=0);atomic_json(rp,report);return report
 original=preserved(data,out);source_before=tree_hashes(source)
 from .parallel_pool import initialize,snapshot,routing_counts
 db=dest/'pool.sqlite';h=load_json(out/'parallel/health/latest.json')
 initialize(db,h.get('eligible_text_slots',[]),text_limit=1,image_limit=1,max_calls=5,per_worker=5,prior_usage=routing_counts(out))
 try:
  from .parallel_client import ParallelModelClient
  worker_env=dict(env,AFP_PARALLEL_WORKER='1',AFP_PARALLEL_POOL_DB=str(db),AFP_PARALLEL_TOPIC=TOPIC,AFP_PARALLEL_FAMILY='five-call-translation-repair-only')
  client=(ParallelModelClient if client_factory is None else client_factory)(h,env=worker_env,allow_calls=True,capabilities=('text',))
  client._max_translation_review_repair_calls=5;client._translation_repair_languages=EDITABLE
  folder=out/'parallel/writer-verification'/ID/TOPIC
  if folder.exists():raise ValueError('never_overwrite_reserved_repair_artifacts')
  shutil.copytree(source,folder)
  from .translation_review_repair import run as repair
  result=repair(client,article,translations,folder);report['result']=result
  current={lang:load_json(folder/'translations'/(lang+'.json')) for lang in LANGUAGES}
  report['protected_languages_unchanged']=all((folder/'translations'/(lang+suffix)).read_bytes()==(source/'translations'/(lang+suffix)).read_bytes() for lang in ('ru-RU','en-US') for suffix in ('.json','.raw.json'))
  report['persian_article_unchanged']=(folder/'article.json').read_bytes()==(source/'article.json').read_bytes()
  if not report['protected_languages_unchanged'] or not report['persian_article_unchanged']:raise ValueError('protected_content_changed')
  report['status']='verification_completed' if result.get('four_languages_semantically_reviewed') is True else 'verification_incomplete'
  report['result_binding']=binding(article,current)
 except Exception as exc:
  from .failure_diagnostics import failure_details
  report.update(status='verification_incomplete',failure=failure_details(exc))
 finally:
  report['pool']=snapshot(db);report['model_calls']=report['pool']['model_requests_reserved'];report['preserved_original_state']=preserved(data,out)==original;report['preserved_source_test_artifacts']=tree_hashes(source)==source_before
  if not report['preserved_original_state'] or not report['preserved_source_test_artifacts']:report['status']='verification_original_state_changed'
  until=report['pool'].get('cooldown_until_epoch',0)
  if until>time.time():atomic_json(out/'provider-circuit.json',{'open':True,'request_kind':'text','at':utcnow(),'retry_at_epoch':until,'reason':'five_call_translation_repair_provider_failure','no_secrets':True})
  report['completed_at']=utcnow();atomic_json(rp,report)
 return report
