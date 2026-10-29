"""Stable credential-slot ownership; capability is still independently verified.
No credentials/hashes of credentials are stored. No error-triggered borrowing.
"""
import hashlib
import json
from .queue import DATA, load_json
from .parallel_capacity import CREDENTIAL_SET_ID
from .parallel_pool import SLOTS
from .client import CapabilityError

VERSION = 'stable-family-key-ownership-v1'
FAMILIES = ['family-'+str(i).zfill(2) for i in range(1,21)]
# Existing separately admitted operations are not assigned production families.
# They use only the central 17-slot group, never a production family's four.
CENTRAL = {'separate-language-review-queue', 'matrix-pilot-01',
 'alternate-reviewer-only', 'practical-verification-only',
 'five-call-translation-repair-only', 'flash-only-four-segment-diagnostic',
 'one-remaining-tajik-repair', 'one-cleaned-persian-tajik-pair',
 'separately-budgeted-role-skills-launch', 'nonpublishing-ready-storage-pilot',
 'nonpublishing-image-fallback-test', 'nonpublishing-language-fallback-continuation',
 'isolated-infrastructure-probe'}


class FamilyCapabilityRequired(CapabilityError):
 def __init__(self, kind):
  self.kind = kind
  super().__init__('No verified '+kind+' capability in the assigned credential group')


def default_policy():
 return {'version':1, 'policy':VERSION, 'credential_set_id':CREDENTIAL_SET_ID,
         'enabled':True, 'revision':1, 'cross_family_borrowing':False,
         'automatic_reserve_promotion':False,
         'families':{f:SLOTS[4*i:4*i+4] for i,f in enumerate(FAMILIES)},
         'central_slots':SLOTS[80:],
         'central_scope':'independent language backlog and explicitly admitted diagnostics; never automatic family fallback'}


def load(data=DATA):
 path = data/'family-key-allocation.json'
 p = data/'parallel-policy.json'
 required = p.exists() and load_json(p).get('family_key_allocation_required') is True
 if not path.exists():
  if required:
   raise CapabilityError('Required family key allocation missing')
  return None
 row = load_json(path)
 if not isinstance(row,dict) or not isinstance(row.get('families'),dict):
  raise CapabilityError('Invalid family key allocation object')
 if any(type(row.get(k)) is not bool for k in ('enabled','cross_family_borrowing','automatic_reserve_promotion')):
  raise CapabilityError('Exact boolean family key allocation guards required')
 fixed = default_policy()
 for key in ('version','policy','credential_set_id','enabled','cross_family_borrowing','automatic_reserve_promotion','central_scope'):
  if row.get(key) != fixed[key]:
   raise CapabilityError('Invalid fixed family key allocation policy')
 if type(row.get('revision')) is not int or row['revision'] < 1 or set(row.get('families',{})) != set(FAMILIES):
  raise CapabilityError('Invalid family allocation identities')
 groups = list(row['families'].values()) + [row.get('central_slots')]
 if any(not isinstance(group,list) for group in groups) or any(len(group)!=4 for group in groups[:-1]) or len(groups[-1])!=17:
  raise CapabilityError('Exactly four slots per family and seventeen central slots required')
 flat = [slot for group in groups for slot in group]
 if any(not isinstance(slot,str) for slot in flat) or len(flat)!=97 or len(set(flat))!=97 or set(flat)!=set(SLOTS):
  raise CapabilityError('Credential slot ownership must be an exact disjoint 97-slot partition')
 return row


def binding(row):
 return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def slots_for(family, data=DATA):
 row = load(data)
 if row is None:
  return None, None
 if family in FAMILIES:
  return tuple(row['families'][family]), binding(row)
 central = family in CENTRAL if isinstance(family,str) else False
 if isinstance(family,str) and family.startswith('three-source-trial-'):
  from .queue import safe_id
  try:
   safe_id(family[len('three-source-trial-'):]); central = True
  except ValueError:
   pass
 if central:
  return tuple(row['central_slots']), binding(row)
 raise CapabilityError('Known family or explicitly scoped central worker required')


def check_unique_values(env):
 # Compare only in memory, including values outside the current family's group.
 # Aliasing two slots to one actual secret would defeat ownership isolation.
 values = [env.get(slot,'').strip() for slot in SLOTS if env.get(slot,'').strip()]
 if len(values)!=len(set(values)):
  raise CapabilityError('Duplicate configured credential values; allocation cannot establish isolation')


def restrict_env(env, family, data=DATA):
 slots, proof = slots_for(family,data)
 result = dict(env)
 if slots is not None:
  check_unique_values(result)
  for slot in SLOTS:
   if slot not in slots:
    result.pop(slot,None)
 return result, {'family_key_slots':list(slots) if slots is not None else None,
                 'family_key_allocation_sha256':proof}
