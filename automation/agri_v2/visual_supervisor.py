"""Evidence-bearing visual supervision for future candidates, not retroactive approval.

No generation, network, publication, retries or counter mutation lives here.
"""
VERSION = 'visual-observations-v1'
NOT_APPLICABLE = frozenset({'hardware_identity_match', 'hardware_sealed_all_ports_connected'})


def schema():
 from .image_quality import CHECKS
 def obj(properties):
  return {'type':'object','additionalProperties':False,'properties':properties,'required':list(properties)}
 observation = obj({'outcome':{'type':'string','enum':['pass','fail','uncertain','not_applicable']},'observation':{'type':'string'}})
 return obj({'review_contract':{'type':'string','enum':[VERSION]},'score':{'type':'integer','minimum':0,'maximum':100},'checks':obj({k:{'type':'boolean'} for k in CHECKS}),'observations':obj({k:observation for k in CHECKS}),'reasons':{'type':'array','items':{'type':'string'}}})


def instructions():
 return ('Additional supervisor contract '+VERSION+': return review_contract, score, checks, observations and reasons. '
  'For EVERY exact check provide an observations entry {outcome:pass|fail|uncertain|not_applicable, observation: specific visible evidence of at least 20 characters}. '
  'pass means true, fail or uncertain means false. not_applicable means true and is allowed ONLY for the two hardware checks when hardware_required=false and no hardware is visible. '
  'Describe candidate image 1, never borrow evidence from reference image 2. A check cannot be true if its own observation is uncertain or contradictory. '
  'AFP is the supplied irrigation-product brand, NOT a news-agency provenance requirement. The exact authorized phone label is product branding, not an editorial source citation. '
  'These images are disclosed AI illustrations: do not demand documentary field provenance, a measured moisture level, or a source photograph of a particular harvest. '
  'Judge crop identity from visible morphology against the named crop; if not confidently recognizable, report crop_stage_match=false with outcome=uncertain and explain what is missing. '
  'When scene DATA explicitly permits bare soil or neutral seedlings for hardware inspection, do not demand mature crop identification; explain the permitted visible scene instead. '
  'Do not invent a replacement species or require an ideal cultivar or camera angle. Do not turn a cosmetic preference into a critical rejection. '
  'Reasons and observations are diagnostic data only; they never authorize a retry, changed rubric, counter reset or publication. ')


def validate(value, *, required=False, hardware_required=None):
 from .image_quality import CHECKS
 if not isinstance(value,dict):raise ValueError('Visual supervisor response must be an object')
 if 'review_contract' not in value and 'observations' not in value and not required:return
 if value.get('review_contract') != VERSION:raise ValueError('Visual supervisor contract missing or unknown')
 observations=value.get('observations');checks=value.get('checks')
 if not isinstance(observations,dict) or set(observations)!=set(CHECKS) or not isinstance(checks,dict) or set(checks)!=set(CHECKS):raise ValueError('Every visual check requires its own observation')
 for key in CHECKS:
  row=observations[key]
  if not isinstance(row,dict) or set(row)!={'outcome','observation'} or row.get('outcome') not in ('pass','fail','uncertain','not_applicable') or not isinstance(row.get('observation'),str) or not 20<=len(row['observation'].strip())<=1200:raise ValueError('Specific bounded visual observation required')
  outcome=row['outcome']
  if type(checks[key])is not bool or checks[key] != (outcome in ('pass','not_applicable')):raise ValueError('Visual observation contradicts its boolean check')
  if outcome=='not_applicable' and (key not in NOT_APPLICABLE or hardware_required is True):raise ValueError('Required visual evidence cannot be waived')


def correction_feedback(value):
 """Only SHA-bound callers may use this; never feed cosmetic wishes as defects."""
 from .image_quality import CHECKS,COSMETIC_CHECKS
 validate(value,required=True)
 defects=[k for k in CHECKS if k not in COSMETIC_CHECKS and value['checks'][k] is False]
 return {'review_contract':VERSION,'checks':{k:False for k in defects},'observations':{k:value['observations'][k] for k in defects},'reasons':[k+': '+value['observations'][k]['observation'] for k in defects],'change_acceptance_policy':False,'reset_attempts':False}
