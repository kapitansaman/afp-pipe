"""Read-only readiness audit; local evidence is not a live credential or publication test."""
import json
from .queue import DATA,OUT,load_json,atomic_json,utcnow,age_hours
from .parallel_capacity import KEY_LIMIT,MAX_FAMILIES,CREDENTIAL_SET_ID

def inspect(data=DATA,out=OUT,wp=None):
 gates={};warnings=[]
 def add(name,passed,detail):gates[name]={'passed':passed is True,'detail':detail}
 policy=load_json(data/'parallel-policy.json');lifecycle=load_json(data/'family-lifecycle-policy.json');cfg=load_json(data/'config.json')
 add('configured_capacity',policy.get('key_limit')==KEY_LIMIT and policy.get('max_article_workers')==MAX_FAMILIES,'97 credential slots and 20 isolated families; configuration only')
 hp=out/'parallel/health/latest.json';health=load_json(hp) if hp.exists() else {}
 from .healthcheck import TEXT_MODEL,IMAGE_MODEL,API_BASE
 from .parallel_pool import SLOTS
 try:fresh=0<=age_hours(health['checked_at'])<24
 except (KeyError,ValueError,TypeError):fresh=False
 bound=(health.get('repository')=='kapitansaman/afp-pipe' and health.get('credential_set_id')==CREDENTIAL_SET_ID and (health.get('text_model'),health.get('image_model'),health.get('api_base'))==(TEXT_MODEL,IMAGE_MODEL,API_BASE) and fresh and health.get('audit_status')=='completed')
 add('fresh_text_capacity',bound and len(set(health.get('eligible_text_slots',[]))&set(SLOTS))>=MAX_FAMILIES,'Actual fresh proof bound to the 97-key cohort, with at least 20 eligible text credentials')
 image_proven=False;image_proven_slots=set()
 for slot in set(health.get('eligible_image_slots',[]))&set(SLOTS):
  proof=out/'parallel/runtime/image'/(slot+'.json')
  if not proof.exists():continue
  row=load_json(proof)
  try:
   valid=(row.get('slot')==slot and row.get('repository')=='kapitansaman/afp-pipe' and row.get('credential_set_id')==CREDENTIAL_SET_ID and row.get('model')==IMAGE_MODEL and row.get('verification') in ('actual_successful_parallel_response','actual_successful_parallel_capability_probe') and 0<=age_hours(row['verified_at'])<24)
   image_proven|=valid
   if valid:image_proven_slots.add(slot)
  except (KeyError,ValueError,TypeError):pass
 add('fresh_image_capacity',bound and image_proven,'Separate actual successful fresh bound image proof; text success is not image approval')
 from .family_model_routing import load as load_roles,slots as model_slots,binding as routing_binding
 roles=load_roles(data)
 if roles is not None:
  proof_slots=set()
  from .family_capability_refresh import image_proofs
  proof_slots=set(image_proofs(out,roles));image_proven_slots &= proof_slots
  gates['fresh_image_capacity']['passed']=bound and bool(image_proven_slots)
 key_allocation=None
 if policy.get('family_key_allocation_required') is True or (data/'family-key-allocation.json').exists():
  try:
   from .family_keys import load as key_policy,binding as key_binding
   allocation=key_policy(data)
   key_allocation={'allocation_sha256':key_binding(allocation),'families':[{
    'family_id':family,'assigned_slots':slots,
    'eligible_text_slots':[n for n in slots if bound and n in health.get('eligible_text_slots',[]) and (roles is None or n in model_slots(family,'text',data))],
    'proven_image_slots':[n for n in slots if bound and n in image_proven_slots and (roles is None or n in model_slots(family,'image',data))]} for family,slots in allocation['families'].items()],
    'central_slots':allocation['central_slots'],'automatic_family_fallback':False}
   add('family_key_allocation',True,'Exact disjoint 20 x 4 family ownership plus 17 central slots')
   add('family_owned_text_capacity',all(r['eligible_text_slots'] for r in key_allocation['families']),'Each family needs its own fresh text-capable credential; global healthy count is insufficient')
   add('family_owned_image_capacity',all(r['proven_image_slots'] for r in key_allocation['families']),'Each family needs its own actual fresh image proof; no borrowing from central/other families')
  except (ValueError,KeyError,TypeError,RuntimeError):
   add('family_key_allocation',False,'Missing or invalid required family key allocation; no shared-pool fallback')
 auth_path=out/'parallel/readiness/authenticated-preflight.json';auth=load_json(auth_path) if auth_path.exists() else {}
 if wp is not None:
  try:
   me=wp.preflight();schema,_=wp.call('posts',method='OPTIONS');bridge={'afp_language','afp_source_post_id'}<=set(schema.get('schema',{}).get('properties',{}))
   auth={'checked_at':utcnow(),'origin':'https://navar-abyari.ir','can_publish':me.get('can_publish') is True,'language_bridge':bridge,'roles':me.get('roles',[]),'post_mutations':0};atomic_json(auth_path,auth)
  except Exception as e:auth={'checked_at':utcnow(),'can_publish':False,'language_bridge':False,'error_type':type(e).__name__,'post_mutations':0};atomic_json(auth_path,auth)
 try:auth_fresh=0<=age_hours(auth['checked_at'])<24 and auth.get('origin')=='https://navar-abyari.ir'
 except (KeyError,ValueError,TypeError):auth_fresh=False
 add('authenticated_publisher',auth_fresh and auth.get('can_publish') is True,'Current authenticated read-only preflight; credentials were not inspected locally')
 add('translation_bridge',not cfg.get('multilingual',{}).get('enabled') or auth_fresh and auth.get('language_bridge') is True,'Registered afp_language and afp_source_post_id fields are required for multilingual publication')
 add('scoped_rollout_released',lifecycle.get('research_only_for_scoped_rollout') is False,'General scoped families are still research-only until the live pilot is accepted')
 add('lifecycle_enabled',lifecycle.get('enabled') is True and lifecycle.get('publication_enabled') is True,'Lifecycle and single gated publisher must both be enabled')
 families=[]
 from .family_scheduler import assigned_topics
 from .family_lifecycle import next_stage,state
 ap=out/'parallel/families/assignments.json'
 if ap.exists():
  for t in assigned_topics(load_json(ap),data):
   stage,reason=next_stage(t,data,out);attempt=state(out/'new'/t['id'],stage);exhausted=attempt['attempts']>=lifecycle['max_attempts_per_stage'];families.append({'family_id':t['family_id'],'topic_id':t['id'],'next_stage':stage,'reason':reason,'attempts':attempt['attempts'],'retry_exhausted':exhausted})
 add('distinct_assigned_families',len(families)==MAX_FAMILIES and len({r['topic_id'] for r in families})==MAX_FAMILIES,'Exactly one distinct immutable queue topic per family')
 add('work_remaining_with_budget',any(not r['retry_exhausted'] and r['next_stage'] not in ('blocked','complete') for r in families),'Do not repeatedly launch only blocked or exhausted work')
 if 'administrator' in auth.get('roles',[]):warnings.append('Publisher account is administrator; a dedicated least-privilege Author account is recommended, not silently substituted.')
 warnings+=['Fresh text/image health expires after 24h. Manual role-bound daily capability renewal is available; unattended renewal is not enabled.','Worker subprocess timeout is 900s; image requests may each take 600s. A full family may checkpoint/defer across Actions.','A full first 20-family end-to-end run has not been demonstrated by offline concurrency tests.','Source deficiencies, rejected overlap reviews and exhausted stage budgets are not repaired by increasing schedule frequency.']
 blockers=[name for name,v in gates.items() if not v['passed']]
 result={'status':'readiness_checked' if not blockers else 'readiness_blocked','checked_at':utcnow(),'technical_ready':not blockers,'blockers':blockers,'gates':gates,'warnings':warnings,'families':families,'research_backlog':load_json(ap).get('research_backlog',{}) if ap.exists() else {},'model_calls':0,'image_calls':0,'post_mutations':0,'authenticated_check_performed':wp is not None,'family_key_allocation':key_allocation}
 return result

def run(data=DATA,out=OUT):
 from .wordpress import WordPress
 try:wp=WordPress()
 except Exception:wp=None
 result=inspect(data,out,wp);atomic_json(out/'parallel/readiness/latest.json',result);return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
