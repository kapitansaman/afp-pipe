"""One bounded, explicit production cycle; schedules accept only publication-authorized briefs."""
import argparse,json,tempfile
from .image_layout import PRODUCTION_IMAGE_ROLES,IMAGE_LAYOUT
from pathlib import Path
from .queue import DATA,OUT,load_json,atomic_json,get_topic,age_hours,utcnow
from .pipeline import draft,check_brief,digest,validate_article,validate_for_publication
from .wordpress import WordPress,WPError
from .healthcheck import audit
from .progress import update,failed
from .failure_diagnostics import failure_details

def handle_generation_failure(exc):
 # Local parsing/validation/capability errors are NOT provider outages.
 from .client import ImageProviderError,TextProviderError
 if isinstance(exc,ImageProviderError):
  from .pilot_resume import defer_provider
  defer_provider(exc)
 elif isinstance(exc,TextProviderError) and exc.category in {'provider_unavailable','network_or_timeout','rate_limited','quota_limited'}:
  from .recovery import open_circuit
  open_circuit(kind='text',reason=exc.category,retry_after=exc.retry_after_seconds)

def fresh_inventory(wp,snapshot=None):
 # Reuse only the immediately preceding research snapshot, never a cross-run cache.
 if isinstance(snapshot,dict) and snapshot.get('records') and snapshot.get('scope'):
  try:
   if 0<=age_hours(snapshot['source_generated_at'])<5/60:return snapshot
  except (KeyError,ValueError,TypeError):pass
 return wp.inventory()

def run(request_path=None,scheduled=False,_research_done=False,_research_inventory=None):
 config=load_json(DATA/'config.json')
 if config.get('repository')=='kapitansaman/afp-pipe' and not config.get('publication_enabled'):return {'status':'publication_disabled','model_calls':0,'published_posts':0}
 from .safe_activation import authorized as activation_authorized,skip_completed_tuning
 safe_active=scheduled and activation_authorized(DATA)
 deferred=[]
 hooks=load_json(DATA/'config.json').get('legacy_one_off_hooks_enabled',True)
 if hooks and scheduled and (DATA/'image-key-audit-request.json').exists():
  from .image_key_audit import run as audit_images
  audit_result=audit_images()
  if audit_result is not None:return audit_result
 if hooks and scheduled and (DATA/'image-tuning-resume-request.json').exists() and not (safe_active and skip_completed_tuning()):
  from .tuning_resume import run as resume_tuning
  tuning=resume_tuning()
  if tuning is not None:return tuning
 if hooks and safe_active and (DATA/'practical-recheck-request.json').exists():
  from .practical_recheck import run as recheck_existing
  result=recheck_existing()
  if result is not None:return result
 if hooks and safe_active and (DATA/'curated-continuation-request.json').exists():
  from .curated_continuation import REMAINING_ID,resumable,run as continue_curated
  continuation=load_json(DATA/'curated-continuation-request.json')
  receipt=OUT/'curated-continuations'/REMAINING_ID/'receipt.json'
  if continuation.get('request_id')==REMAINING_ID and (not receipt.exists() or resumable(load_json(receipt),continuation)):
   result=continue_curated()
   if result.get('status') in {'provider_cooldown','provider_deferred'}:deferred.append(result)
   else:return result
 config=load_json(DATA/'config.json')
 if not config.get('publication_enabled'):return {'status':'publication_disabled','model_calls':0}
 if scheduled and not config.get('automatic_generation'):return {'status':'automatic_generation_disabled','model_calls':0}
 if safe_active and config.get('runtime_health',{}).get('enabled'):
  from .runtime_health import ensure_fresh
  health=ensure_fresh()
  if health['status'] not in {'health_current','health_refreshed_from_actual_evidence'}:
   update('اتصال نیازمند بررسی محدود است؛ تولید بی‌دلیل اجرا نشد',0,status='health_refresh_required')
   return health
 if hooks and safe_active and (DATA/'production-start-request.json').exists():
  from .prepared_continuation import scheduled_resume
  continuation=scheduled_resume()
  if continuation is not None:
   if continuation.get('status') in {'provider_cooldown','provider_deferred'}:deferred.append(continuation)
   else:return continuation
 if safe_active and config.get('multilingual',{}).get('enabled'):
  from .multilingual import backfill_one
  family=backfill_one(WordPress())
  if family is not None:return family
 if hooks and scheduled and (DATA/'pilot-resume-request.json').exists():
  from .pilot_resume import run as resume_pilot
  recovery=resume_pilot()
  if recovery is not None:
   if safe_active and recovery.get('status') in {'pilot_recovery_budget_exhausted','provider_cooldown','shared_image_admission_deferred','provider_deferred'}:deferred.append(recovery)
   else:return recovery
 if request_path:
  request=load_json(request_path)
  if request.get('publish_authorized') is not True or request.get('max_new_posts')!=1:raise ValueError('Single-post authorization required')
  candidates=[request['topic_id']]
 else:
  candidates=[]
  for p in sorted((DATA/'briefs').glob('*.json')):
   b=load_json(p)
   if b.get('publish_authorized') is True:candidates.append(b['topic_id'])
 for ident in candidates:
  if ident in config.get('publication_holds',{}):continue
  rp=OUT/'new'/ident/'wordpress-receipt.json'
  if rp.exists() and load_json(rp).get('public_verified') is True:continue
  bp=DATA/'briefs'/f'{ident}.json';brief=load_json(bp);topic=get_topic('new',ident);check_brief(topic,brief)
  if brief.get('publish_authorized') is not True:raise ValueError('Brief publication not authorized')
  attempts_path=OUT/'new'/ident/'cycle-attempts.json';attempts=load_json(attempts_path) if attempts_path.exists() else {'attempts':0}
  from .production_recovery import eligible as recovery_eligible,reserve as reserve_recovery,finish as finish_recovery
  recovering=attempts['attempts']>=2 and recovery_eligible(OUT/'new'/ident)
  if attempts['attempts']>=2 and not recovering:
   research_path=OUT/'research'/f'{ident}.json';prior=load_json(research_path) if research_path.exists() else {}
   if prior.get('reason')!='production_retry_budget_exhausted':atomic_json(research_path,dict(prior,topic_id=ident,status='needs_review',reason='production_retry_budget_exhausted',production_attempts=attempts['attempts'],at=utcnow()))
   continue
  # Eligibility first. Published/exhausted work must not freeze the whole queue.
  folder=OUT/'new'/ident;sp=folder/'state.json'
  staged=sp.exists() and load_json(sp).get('status')=='draft_created'
  from .recovery import circuit_open
  blocked=(not staged and circuit_open('image')) or (not staged and not (folder/'article.json').exists() and circuit_open('text'))
  if blocked:
   deferred.append({'status':'provider_cooldown','topic_id':ident});continue
  update('بررسی اتصال و موضوع آماده',5,ident,topic['title'])
  print("Stage: authenticated WordPress preflight",flush=True)
  wp=WordPress();connection=wp.preflight();update('اتصال وردپرس تأیید شد',10)
  print("Stage: fresh public inventory",flush=True)
  inventory=fresh_inventory(wp,_research_inventory) # full inventory, at most five minutes old
  update('موجودی تازه سایت دریافت شد',20)
  hp=DATA/'health/latest.json'
  if not hp.exists() or age_hours(load_json(hp)['checked_at'])>24:
   update('شواهد سلامت منقضی شده؛ بررسی انبوه کلیدها خودکار اجرا نمی‌شود',0,status='health_refresh_required')
   return {'status':'health_evidence_expired','model_calls':0,'published_posts':0}
  if recovering:reserve_recovery(folder)
  else:
   attempts['attempts']+=1;attempts['last_started_at']=utcnow();atomic_json(attempts_path,attempts)
  with tempfile.TemporaryDirectory() as tmp:
   ip=Path(tmp)/'inventory.json';atomic_json(ip,inventory)
   print("Stage: generate or resume one draft and two images",flush=True)
   folder=OUT/'new'/ident;sp=folder/'state.json'
   staged=sp.exists() and load_json(sp).get('status')=='draft_created'
   if staged:
    if load_json(sp).get('brief_sha256')!=digest(brief):raise ValueError('Staged brief changed')
    validate_article(load_json(folder/'article.json'),topic,brief)
    if not (folder/'wordpress-draft-payload.json').exists() or not all((folder/f'image-{n}.webp').exists() for n in PRODUCTION_IMAGE_ROLES):raise ValueError('Staged artifacts incomplete')
   else:
    try:draft(ident,bp,ip,hp,allow_calls=True,translate=True)
    except Exception as exc:
     handle_generation_failure(exc)
     failure=failure_details(exc)
     from .client import ImageProviderError,TextProviderError
     from .image_transport import AdmissionBlocked
     from automation.blog_image_queue import ImageQueueBusy
     transient=isinstance(exc,(ImageProviderError,TextProviderError)) and exc.category in {'provider_unavailable','network_or_timeout','rate_limited'}
     admission=isinstance(exc,(AdmissionBlocked,ImageQueueBusy))
     if admission:
      failure={'kind':'image_admission','category':'admission_deferred'}
      state=load_json(folder/'state.json');state['failure']=failure;atomic_json(folder/'state.json',state)
     if recovering:finish_recovery(folder,'provider_deferred' if transient or admission else 'blocked',failure)
     if transient or admission:
      atomic_json(OUT/'latest-cycle-deferred.json',{'status':'provider_deferred','topic_id':ident,'at':utcnow(),'failure':failure,'original_attempts':attempts['attempts']})
      update('سرویس موقتاً در دسترس نیست؛ متن و تصاویر محفوظ، ادامه محدود پس از مهلت انتظار',40,ident,topic['title'],status='provider_cooldown')
      return {'status':'provider_deferred','topic_id':ident,'failure':failure,'published_posts':0}
     raise
  print("Stage: upload media, publish one owned post and verify public URL",flush=True)
  validate_for_publication(load_json(OUT/'new'/ident/'article.json'))
  update('بارگذاری رسانه و انتشار یک نوشته',80)
  result=wp.publish(OUT/'new'/ident,topic,brief,authorized=True)
  if recovering:finish_recovery(folder,'publication_verified')
  atomic_json(OUT/'latest-cycle.json',{'status':'success','topic_id':ident,'result':result,'connection':connection,'inventory_count':len(inventory['records']),'completed_at':utcnow()})
  update('انتشار و صفحه عمومی تأیید شد',100,status='success')
  return result
 if scheduled and not _research_done and config.get('research_feeder',{}).get('enabled'):
  from .queue_planner import pending_briefs,buffer_limit
  from .recovery import circuit_open
  if circuit_open('text'):
   update('سرویس متن در مهلت انتظار است؛ پژوهش تازه انجام نشد',0,status='provider_cooldown')
   return {'status':'text_provider_cooldown','model_calls':0,'published_posts':0}
  if len(pending_briefs(DATA,OUT))>=buffer_limit(config):
   update('بافر شرح‌های آماده پر است؛ منتظر سرویس تصویر، بدون درخواست تازه',0,topic_id='',topic_title='',status='provider_cooldown' if deferred else 'idle')
   return {'status':'provider_cooldown' if deferred else 'research_buffer_full','model_calls':0,'published_posts':0}
  from .research import prepare_one
  wp=WordPress();wp.preflight();inventory=wp.inventory()
  result=prepare_one(inventory)
  if result.get('status')=='brief_ready':return run(scheduled=True,_research_done=True,_research_inventory=inventory)
  return result
 if deferred:
  update('کار تصویر به تعویق افتاد؛ صف پژوهش و ترجمه مستقل است',0,status='provider_cooldown')
  return {'status':'provider_cooldown','published_posts':0,'model_calls':0}
 update('اجرای زمان‌بند پایان یافت؛ مقاله آماده برای انتشار وجود ندارد',0,topic_id='',topic_title='',status='idle')
 return {'status':'no_ready_unpublished_brief','model_calls':0,'published_posts':0}

def main():
 p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--scheduled',action='store_true');a=p.parse_args()
 try:r=run(a.request,a.scheduled);print(json.dumps(r,ensure_ascii=False));return 0
 except Exception as e:
  failed()
  if isinstance(e,WPError):print("WordPress stage: "+str(e),flush=True)
  elif isinstance(e,ValueError):print("Validation blocked: "+str(e)[:160],flush=True)
  atomic_json(OUT/'latest-cycle-error.json',{'status':'blocked_or_failed','at':utcnow(),'failure':failure_details(e),'reason':'Inspect sanitized failure category and staged state; no raw provider/auth messages persisted.'})
  print('Cycle stopped safely; staged state preserved. No raw credential/provider error is logged.');return 2
if __name__=='__main__':raise SystemExit(main())
