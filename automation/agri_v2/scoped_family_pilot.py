"""One stable, owned scoped pilot; never a global research-rollout waiver."""
import hashlib
from .queue import DATA,OUT,load_json,atomic_json,utcnow
from .pipeline import digest,check_brief
from .family_capability_refresh import text_fresh,image_proofs
from .family_model_routing import load as routing,binding

BASE='parallel/scoped-family-pilot'
def title_hash(topic):return hashlib.sha256(topic['title'].encode()).hexdigest()
def choose(topics,env,data=DATA,out=OUT):
 if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('AFP_SCOPED_FAMILY_PILOT')!='1':raise ValueError('Manual one-family pilot required')
 roles=routing(data);health=load_json(out/'parallel/health/latest.json')
 if roles is None or not text_fresh(health,roles):raise ValueError('Fresh role-bound pilot text capability required')
 from .family_lifecycle import next_stage,state,settings
 current=out/BASE/'current.json';prior=load_json(current) if current.exists() else None
 if prior is not None:
  candidates=[t for t in topics if t['id']==prior['topic_id'] and t['family_id']==prior['family_id']]
  if len(candidates)!=1:raise ValueError('Original pilot ownership changed; no automatic substitute')
 else:candidates=sorted(topics,key=lambda t:t['family_id'])
 proven=set(image_proofs(out,roles));selected=None
 for topic in candidates:
  role=roles['families'][topic['family_id']]
  if role['image_slot'] not in proven or not set(role['text_slots'])&set(health.get('eligible_text_slots',[])):continue
  bp=data/'briefs'/(topic['id']+'.json')
  if not bp.exists():continue
  brief=load_json(bp);check_brief(topic,brief)
  if brief.get('review_mode')!='automated_scoped_evidence_review_v1' or brief.get('publish_authorized') is not True:continue
  stage,reason=next_stage(topic,data,out);attempt=state(out/'new'/topic['id'],stage)
  if stage in ('blocked','complete') or stage.startswith(('research_','existing_content_audit')) or attempt.get('status') in ('reserved','reconciliation_required') or attempt['attempts']>=settings(data)['max_attempts_per_stage']:continue
  if prior is None and stage!='text':continue
  row={'version':1,'topic_id':topic['id'],'family_id':topic['family_id'],'title_sha256':title_hash(topic),'brief_sha256':digest(brief),'family_model_routing_sha256':binding(roles),'publication_scope':'one_owned_family_existing_gates','original_attempts_reset':False}
  if prior is not None and {k:prior.get(k) for k in row}!=row:raise ValueError('Pilot input changed; independent reconciliation required')
  if prior is None:atomic_json(current,dict(row,selected_at=utcnow()))
  admission=dict(row,run_id=env['GITHUB_RUN_ID'],admitted_at=utcnow());atomic_json(out/BASE/'admissions'/(env['GITHUB_RUN_ID']+'.json'),admission)
  selected=topic;break
 if selected is None:raise ValueError('No owned, unexhausted source-approved pilot with independently verified image key')
 return [selected]

def bound(env,topic,data=DATA):
 if env.get('AFP_SCOPED_FAMILY_PILOT')!='1':return False
 p=data/'status/scoped-family-pilot-admission.json'
 if not p.exists():return False
 r=load_json(p);bp=data/'briefs'/(topic['id']+'.json');roles=routing(data)
 return (bp.exists() and roles is not None and r.get('run_id')==env.get('GITHUB_RUN_ID') and r.get('topic_id')==topic['id'] and r.get('family_id')==topic.get('family_id') and r.get('title_sha256')==title_hash(topic) and r.get('brief_sha256')==digest(load_json(bp)) and r.get('family_model_routing_sha256')==binding(roles) and r.get('publication_scope')=='one_owned_family_existing_gates' and r.get('original_attempts_reset') is False)

def accept(topic,wp,data=DATA,out=OUT):
 folder=out/'new'/topic['id'];receipt=folder/'wordpress-receipt.json';current=load_json(out/BASE/'current.json')
 if not receipt.exists() or load_json(receipt).get('public_verified') is not True:return {'status':'pilot_not_yet_publicly_verified','global_rollout_released':False}
 from .family_lifecycle import article_checked
 from .image_quality import require_all
 from .image_layout import roles_for
 from .healthcheck import IMAGE_MODEL
 roles=routing(data);brief=load_json(data/'briefs'/(topic['id']+'.json'));check_brief(topic,brief);article=article_checked(folder,topic,brief);require_all(folder,topic,article)
 if current['brief_sha256']!=digest(brief):raise ValueError('Pilot source brief changed')
 validation=load_json(folder/'lifecycle-publication-validation.json');images={str(k):hashlib.sha256((folder/f'image-{k}.webp').read_bytes()).hexdigest() for k in roles_for(folder)}
 if validation.get('brief_sha256')!=digest(brief) or validation.get('article_sha256')!=digest(article) or validation.get('image_sha256')!=images:raise ValueError('Pilot publication inputs changed')
 slot=roles['families'][topic['family_id']]['image_slot'];proof=load_json(out/'parallel/runtime/image'/(slot+'.json'))
 if proof.get('topic_id')!=topic['id'] or proof.get('family_id')!=topic['family_id'] or proof.get('model')!=IMAGE_MODEL or proof.get('family_model_routing_sha256')!=binding(roles):raise ValueError('Actual owned pilot image generation proof required')
 verified=wp.verify(load_json(receipt)['post_id'],topic,receipt)
 if verified.get('public_verified') is not True:raise ValueError('Live public pilot verification required')
 r={'status':'scoped_family_pilot_verified','checked_at':utcnow(),'topic_id':topic['id'],'family_id':topic['family_id'],'post_id':verified['post_id'],'url':verified['url'],'brief_sha256':digest(brief),'article_sha256':digest(article),'image_sha256':images,'image_slot':slot,'image_model':IMAGE_MODEL,'family_model_routing_sha256':binding(roles),'public_verified':True,'global_rollout_released':False,'schedule_enabled':False,'original_attempts_reset':False}
 atomic_json(out/BASE/'accepted.json',r);return r
