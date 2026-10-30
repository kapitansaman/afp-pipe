"""Offline preparation only. This proposal is NOT an admission or health proof.
No clients, environment credentials, reservations, workflow or queue mutations.
"""
import argparse,hashlib,json
from .queue import DATA,OUT,load_json,safe_id
from .family_model_routing import load as routing,binding
from .staged_rollout import load as staged


def file_hash(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(data=DATA,out=OUT):
 phase=staged(out)
 if phase['limit']!=1 or len(phase['cohort'])!=1:
  raise ValueError('Exactly one existing stage-one cohort required; no selection or escalation')
 member=phase['cohort'][0];ident=safe_id(member['topic_id']);family=member['family_id']
 roles=routing(data)
 if roles is None or family not in roles['families']:
  raise ValueError('Exact owned family model routing required')
 role=roles['families'][family]
 rp=out/'parallel/readiness/latest.json';readiness=load_json(rp)
 if type(readiness.get('families'))is not list:
  raise ValueError('Existing readiness family evidence required')
 matching=[r for r in readiness['families'] if r.get('family_id')==family]
 if len(matching)!=1 or matching[0].get('topic_id')!=ident:
  raise ValueError('Readiness and immutable cohort differ')
 row=matching[0]
 if type(row.get('retry_exhausted'))is not bool or type(row.get('attempts'))is not int:
  raise ValueError('Explicit stage attempt state required')
 folder=out/'new'/ident
 # Hash operational inputs, without copying article prose or historical responses.
 paths={'routing':data/'family-model-routing.json','allocation':data/'family-key-allocation.json',
        'staged_state':out/'parallel/staged-rollout/state.json','readiness':rp}
 for name in ('article.json','wordpress-receipt.json'):
  p=folder/name
  if p.exists():paths[name]=p
 stages={}
 for p in sorted((folder/'lifecycle').glob('*/state.json')):
  v=load_json(p);stages[p.parent.name]={'status':v.get('status'),'attempts':v.get('attempts'),'sha256':file_hash(p)}
 blockers=['separate_paid_capability_authorization_required','dedicated_single_family_executor_and_admission_required',
           'global_readiness_gates_remain_enforced','production_language_acceptance_not_proven_by_isolated_diagnostics']
 if row['retry_exhausted']:blockers.append('existing_stage_budget_exhausted_no_automatic_continuation')
 return {'version':1,'status':'offline_proposal_not_authorized','family_id':family,'topic_id':ident,
         'routing_sha256':binding(roles),'input_sha256':{k:file_hash(v) for k,v in paths.items()},
         'current_stage':{'name':row.get('next_stage'),'attempts':row['attempts'],'retry_exhausted':row['retry_exhausted']},
         'operational_states':stages,
         'proposed_capability_only_budget':{'max_runs':1,'max_text_calls':3,'max_image_calls':1,
          'max_attempts_per_slot':1,'max_parallel_requests':1,'text_slots':role['text_slots'],
          'image_slot':role['image_slot'],'max_search_requests':0,'max_source_fetches':0,'max_site_calls':0},
         'stop_conditions':['provider_hold_or_backpressure','unknown_or_timeout_do_not_replay',
          'any_failed_probe_stop_remaining_calls','input_or_ownership_changed','budget_consumed'],
         'next_phase':'Recalculate bounded multilingual/output work only after capability review; no implied full-cycle budget.',
         'blockers':blockers,'model_calls':0,'image_calls':0,'site_calls':0,'published_posts':0,
         'paid_execution_authorized':False,'publication_authorized':False,'schedule_enabled':False,
         'promotion_authorized':False,'reset_attempts':False,'global_capacity_refresh':False,
         'production_readiness_claimed':False,'capability_success_is_visual_approval':False}


def main():
 argparse.ArgumentParser(description=__doc__).parse_args()
 print(json.dumps(prepare(),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
