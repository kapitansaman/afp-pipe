"""Explicit foundation controls; no change to scientific or paid-attempt authority."""
from .queue import load_json
POLICY={'version':1,'enabled':True,'source_retry_base_seconds':900,'source_retry_max_seconds':21600,'source_max_transport_attempts_per_url':3,'max_unique_repair_urls':12,'max_search_rounds':2,'preserve_original_attempts':True,'staged_family_limits':[1,3,20],'automatic_promotion':False,'schedule_enabled':False}
def enabled(data):
 p=data/'generator-foundation-policy.json'
 if not p.exists():
  lifecycle=data/'family-lifecycle-policy.json'
  if lifecycle.exists() and load_json(lifecycle).get('foundation_admission_required')is True:raise ValueError('Required generator foundation policy missing')
  return False
 if load_json(p)!=POLICY:raise ValueError('Exact generator foundation policy required')
 return True
