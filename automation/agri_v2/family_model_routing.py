"""Independent model roles inside the immutable four-slot family partition."""
import hashlib,json
from .queue import DATA,load_json
from .family_keys import load as allocation,FAMILIES
from .client import CapabilityError

def expected(data=DATA):
 a=allocation(data)
 if a is None:raise CapabilityError('Owned family allocation required')
 return {'version':1,'allocation_sha256':__import__('automation.agri_v2.family_keys',fromlist=['binding']).binding(a),'cross_family_borrowing':False,'image_fallback':False,'families':{f:{'text_slots':a['families'][f][:3],'image_slot':a['families'][f][3]} for f in FAMILIES}}

def load(data=DATA):
 p=data/'family-model-routing.json';policy=data/'parallel-policy.json'
 if not p.exists():
  if policy.exists() and load_json(policy).get('family_model_routing_required'):raise CapabilityError('Family model routing required')
  return None
 r=load_json(p)
 if r!=expected(data):raise CapabilityError('Exact independent text/image family routing required')
 return r

def binding(row):return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def slots(family,kind,data=DATA):
 r=load(data)
 if r is None or family not in r['families']:return None
 if kind not in ('text','image'):raise CapabilityError('Unknown capability role')
 row=r['families'][family]
 return row['text_slots'] if kind=='text' else [row['image_slot']]
