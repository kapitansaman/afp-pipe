"""Three corrective rounds after the initial candidate; one approved image suffices.
Never approve by attempt count, reset old counters, or upload a rejected candidate.
"""
import hashlib
from pathlib import Path
from .queue import DATA,load_json,atomic_json,utcnow
from .pipeline import digest
POLICY='three-corrections-single-approved-v1'
MAX_ATTEMPTS=4

def enabled(data=DATA):
 p=data/'image-repair-policy.json'
 return p.exists() and load_json(p)=={'version':1,'enabled':True,'policy':POLICY,'max_corrective_rounds':3,'max_generation_attempts_per_role':4,'max_visual_reviews_per_role':4,'minimum_approved_images':1,'preferred_images':2,'reset_existing_attempts':False}

def selection_path(folder):return Path(folder)/'image-selection.json'
def approved_roles(folder,topic,article):
 from .image_quality import valid_record
 good=[];seen=set()
 for k in (1,2):
  try:
   image=Path(folder)/f'image-{k}.webp';valid_record(image,topic,k,article);sha=hashlib.sha256(image.read_bytes()).hexdigest()
   if sha not in seen:good.append(k);seen.add(sha)
  except (ValueError,OSError,KeyError,TypeError):pass
 return tuple(good)
def exhausted(folder,k):
 from .family_lifecycle import state
 return max(state(Path(folder),'image-'+str(k))['attempts'],state(Path(folder),'vision-'+str(k))['attempts'])>=MAX_ATTEMPTS

def validate_selection(folder,topic,article):
 """This is an additional binding gate; every retained image still needs valid QA."""
 folder=Path(folder);p=selection_path(folder)
 if not p.exists():return (1,2)  # strict legacy default, never implicit single-image approval
 r=load_json(p);roles=r.get('selected_roles')
 if r.get('version')!=1 or r.get('policy')!=POLICY or r.get('topic_id')!=topic.get('id') or r.get('article_sha256')!=digest(article) or roles not in ([1],[2],[1,2]) or any(type(k)is not int for k in roles):raise ValueError('Invalid source-bound image selection')
 omitted=[k for k in (1,2) if k not in roles]
 if r.get('omitted_roles')!=omitted or any(not exhausted(folder,k) for k in omitted):raise ValueError('Image fallback requires exhausted correction history')
 for k in roles:
  image=folder/f'image-{k}.webp';proof=image.with_suffix('.quality.json');expected={'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'review_sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}
  if r.get('retained_bindings',{}).get(str(k))!=expected:raise ValueError('Selected image or review changed')
 if len(roles)==2 and r['retained_bindings']['1']['image_sha256']==r['retained_bindings']['2']['image_sha256']:raise ValueError('Duplicate images cannot fill two slots')
 receipt=folder/'wordpress-receipt.json'
 if receipt.exists():
  prior=load_json(receipt)
  if prior.get('selected_image_roles') is not None and prior['selected_image_roles']!=roles:raise ValueError('Never silently change a published media selection')
 return tuple(roles)

def seal_selection(folder,topic,article,roles):
 from .image_quality import valid_record
 folder=Path(folder)
 if not roles:raise ValueError('No approved image; keep only this family waiting')
 omitted=[k for k in (1,2) if k not in roles]
 if any(not exhausted(folder,k) for k in omitted):raise ValueError('Corrective rounds remain; no premature fallback')
 bindings={}
 for k in roles:
  image=folder/f'image-{k}.webp';valid_record(image,topic,k,article);bindings[str(k)]={'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'review_sha256':hashlib.sha256(image.with_suffix('.quality.json').read_bytes()).hexdigest()}
 atomic_json(selection_path(folder),{'version':1,'policy':POLICY,'topic_id':topic['id'],'article_sha256':digest(article),'selected_roles':list(roles),'omitted_roles':omitted,'retained_bindings':bindings,'at':utcnow(),'forced_approval':False,'attempts_reset':False})
 return validate_selection(folder,topic,article)

def ready(folder,topic,article):
 if not selection_path(folder).exists():return False
 try:
  from .image_quality import require_all
  require_all(folder,topic,article);return True
 except (ValueError,OSError,KeyError,TypeError):return False

def advance(client,folder,topic,article,run_id,data=DATA):
 if not enabled(data):raise ValueError('Explicit bounded image-repair policy required')
 from .family_lifecycle import attempt,state,stage_outputs
 from .image_quality import valid_record,ensure_review,generation_feedback
 from .media_policy import generate_role
 folder=Path(folder);steps=[]
 client.image_rotation_enabled=False
 if ready(folder,topic,article):return {'status':'images_ready','roles':list(validate_selection(folder,topic,article)),'steps':[]}
 for k in (1,2):
  target=folder/f'image-{k}.webp'
  for _ in range(MAX_ATTEMPTS*2+1):
   if k in approved_roles(folder,topic,article):break
   gen=state(folder,'image-'+str(k));vision=state(folder,'vision-'+str(k));proof=load_json(target.with_suffix('.quality.json')) if target.with_suffix('.quality.json').exists() else {}
   from .image_quality import EXPLICIT_REJECTIONS
   known_bad=target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() in EXPLICIT_REJECTIONS
   duplicate=target.exists() and k==2 and 1 in approved_roles(folder,topic,article) and target.read_bytes()==(folder/'image-1.webp').read_bytes()
   needs_generation=duplicate or not target.exists() or known_bad or proof.get('status')=='reviewed' and proof.get('verdict',{}).get('passed') is False
   if needs_generation:
    if gen['attempts']>=MAX_ATTEMPTS or vision['attempts']>=MAX_ATTEMPTS:break
    feedback={'reasons':['The candidate duplicates the retained first image. Make a distinct scene; do not fill both slots with the same image.'],'checks':{'distinct_scene':False}} if duplicate else generation_feedback(folder,k)
    def generate(k=k,target=target,feedback=feedback):
     client.image_feedback=feedback
     blob=generate_role(client,topic,k,article);tmp=target.with_suffix('.tmp');tmp.write_bytes(blob);tmp.replace(target);return {'image_created':k}
    name='image-'+str(k);result=attempt(folder,name,run_id,generate,stage_outputs(folder,name),limit=MAX_ATTEMPTS,allow_same_run=True);steps.append(result)
    if result['status']!='stage_completed':return {'status':'images_deferred','steps':steps,'roles':list(approved_roles(folder,topic,article))}
   if state(folder,'vision-'+str(k))['attempts']>=MAX_ATTEMPTS:break
   name='vision-'+str(k);result=attempt(folder,name,run_id,lambda k=k,target=target:ensure_review(client,target,topic,k,article),stage_outputs(folder,name),limit=MAX_ATTEMPTS,allow_same_run=True);steps.append(result)
   if result['status']=='stage_deferred':return {'status':'images_deferred','steps':steps,'roles':list(approved_roles(folder,topic,article))}
   if result['status']!='stage_completed' and result.get('failure',{}).get('kind')!='image_quality':return {'status':'images_deferred','steps':steps,'roles':list(approved_roles(folder,topic,article))}
 roles=approved_roles(folder,topic,article)
 if roles and all(exhausted(folder,k) for k in (1,2) if k not in roles):
  seal_selection(folder,topic,article,roles);return {'status':'images_ready','roles':list(roles),'fallback_used':len(roles)==1,'steps':steps}
 return {'status':'images_need_attention' if not roles else 'images_deferred','roles':list(roles),'steps':steps}
