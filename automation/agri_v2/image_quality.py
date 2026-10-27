"""Fail-closed vision gate bound to exact image, topic, role, recipe and reference bytes."""
import hashlib,json
from .image_layout import PRODUCTION_IMAGE_ROLES,IMAGE_LAYOUT
from pathlib import Path
from .queue import atomic_json,load_json,utcnow
from .media_policy import POLICY,contract_hash,reference_images
from .healthcheck import TEXT_MODEL
REVIEW_POLICY='agri-vision-qa-v12-critical-checks'
LEGACY_REVIEW_POLICIES=frozenset({'agri-vision-qa-v9-topic-routed-gt90','agri-vision-qa-v10-practical85','agri-vision-qa-v11-illustrative85'})
PREVIOUS_REVIEW_POLICY='agri-vision-qa-v9-topic-routed-gt90'
SCORE_POLICY='advisory_only'
COSMETIC_CHECKS=frozenset({'product_scale_match','role_camera_match','product_fully_in_frame'})
BOTANICAL_REJECTIONS={'32479ccc8fc41e0d8f141e29a4d1158d8de736b092c17ca977efc03d5f50f391':'Direct inspection contradicted prior automated approval: broad serrated leaves, not fine divided carrot true leaves or narrow emerging cotyledons. Do not reuse this image as a carrot illustration.'}
EXPLICIT_REJECTIONS=frozenset(set(BOTANICAL_REJECTIONS)|{'4935cbd90642507446c0f5bd91c61e7e33e631d32de4292b9b0a148a2f10d49a'})
CHECKS=('hardware_identity_match','hardware_sealed_all_ports_connected','crop_stage_match','role_camera_match','topic_evidence_match','product_identity_match','single_product','product_scale_match','product_fully_in_frame','package_separate_from_plumbing','physical_geometry_plausible','packaging_closed_no_protruding_material','no_people','no_added_text','phone_label_correct')
class ImageQualityError(ValueError):pass
def verdict(value):
 if not isinstance(value,dict):raise ImageQualityError('Vision verdict must be an object')
 checks=value.get('checks');score=value.get('score');reasons=value.get('reasons')
 if not isinstance(checks,dict) or any(type(checks.get(k))is not bool for k in CHECKS):raise ImageQualityError('Missing, unknown or non-boolean vision check')
 if type(score)is not int or not 0<=score<=100:raise ImageQualityError('Invalid vision score')
 if not isinstance(reasons,list) or not reasons or any(not isinstance(x,str) or not x.strip() for x in reasons):raise ImageQualityError('Vision review reasons required')
 return {'passed':all(checks[k] for k in CHECKS if k not in COSMETIC_CHECKS),'checks':{k:checks[k] for k in CHECKS},'score':score,'reasons':[x[:500] for x in reasons[:12]]}
def binding(path,topic,kind,article=None):
 return {'image_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'contract_sha256':contract_hash(topic,kind,article),'reference_sha256':hashlib.sha256(json.dumps({'generation':reference_images(kind,topic),'identity':reference_images()},sort_keys=True).encode()).hexdigest(),'policy':POLICY,'role':kind,'topic_id':topic.get('id'),'review_model':TEXT_MODEL,'review_policy':REVIEW_POLICY}
def review_path(path):return Path(path).with_suffix('.quality.json')
def reject_known(path):
 if hashlib.sha256(Path(path).read_bytes()).hexdigest() in EXPLICIT_REJECTIONS:raise ImageQualityError('Independently rejected image; a historical model score cannot approve it')

def matching_evidence(row,expected):
 return all(row.get(k)==v for k,v in expected.items() if k!='review_policy') and row.get('review_policy') in LEGACY_REVIEW_POLICIES|{REVIEW_POLICY}

def valid_record(path,topic,kind,article=None):
 reject_known(path)
 rp=review_path(path)
 if not rp.exists():raise ImageQualityError('Image has no current visual review')
 row=load_json(rp);expected=binding(path,topic,kind,article)
 if not matching_evidence(row,expected):raise ImageQualityError('Image/contract/reference review binding changed')
 if row.get('status')!='reviewed':raise ImageQualityError('Image review unavailable; no upload')
 evaluated=verdict(row.get('verdict'))
 if not evaluated['passed']:raise ImageQualityError('Image rejected under current practical policy; no upload')
 if row.get('review_policy') not in {PREVIOUS_REVIEW_POLICY,'agri-vision-qa-v11-illustrative85'} and row.get('verdict',{}).get('passed') is not True:raise ImageQualityError('Explicit current-policy rejection retained')
 if row.get('review_policy') in LEGACY_REVIEW_POLICIES:
  return {**row,'verdict':evaluated,'acceptance':'owner_authorized_global_policy_reassessment','evaluated_under_policy':REVIEW_POLICY,'new_visual_review_claimed':False}
 return row

def ensure_review(client,path,topic,kind,article=None):
 reject_known(path)
 path=Path(path);rp=review_path(path);expected=binding(path,topic,kind,article)
 if rp.exists():
  row=load_json(rp)
  if matching_evidence(row,expected):return valid_record(path,topic,kind,article)
 row={**expected,'checked_at':utcnow(),'reviewer':'automated_multimodal_model','human_review_claimed':False,'status':'review_started','no_auto_regeneration':True}
 atomic_json(rp,row) # reserve before call: crash or unavailable review never becomes pass
 try:
  result=verdict(client.review_image(path.read_bytes(),topic,kind,article));row.update(status='reviewed',verdict=result)
 except Exception as exc:
  row.update(status='review_unavailable',error_type=type(exc).__name__)
  atomic_json(rp,row);raise ImageQualityError('Visual review unavailable or malformed; no upload') from None
 atomic_json(rp,row)
 if not result['passed']:raise ImageQualityError('Image rejected by visual QA; preserve bytes, no upload or automatic regeneration')
 return row

def require_all(folder,topic,article=None):
 for kind in PRODUCTION_IMAGE_ROLES:valid_record(Path(folder)/f'image-{kind}.webp',topic,kind,article)


def generation_feedback(folder,kind):
 """Return only an actual SHA-bound rejected candidate, including its archive.
 No feedback can change the critical acceptance checks or reset attempts.
 """
 folder=Path(folder);name='image-'+str(kind)+'.webp'
 candidates=[folder/name]
 archived=folder/'lifecycle'/('image-'+str(kind))/'rejected'
 candidates+=sorted(archived.glob('*/'+name),key=lambda p:int(p.parent.name) if p.parent.name.isdigit() else -1,reverse=True)
 for image in candidates:
  rp=review_path(image)
  if not image.is_file() or not rp.is_file():continue
  row=load_json(rp);actual=hashlib.sha256(image.read_bytes()).hexdigest()
  if actual in BOTANICAL_REJECTIONS:return {'rejected_image_sha256':actual,'checks':{'crop_stage_match':False},'reasons':[BOTANICAL_REJECTIONS[actual]],'prior_model_approval_overruled_by_direct_inspection':True}
  if row.get('status')=='reviewed' and row.get('verdict',{}).get('passed') is False and row.get('image_sha256')==hashlib.sha256(image.read_bytes()).hexdigest():
   return {'rejected_image_sha256':row['image_sha256'],'checks':row['verdict'].get('checks',{}),'reasons':row['verdict'].get('reasons',[])}
 return None
