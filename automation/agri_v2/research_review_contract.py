"""Explicit response shape for NEW source reviews, never a missing-flag repair."""
from .research_routes import VERSION
BASE_FLAGS=('all_claims_supported','crop_species_and_product_match','answers_exact_intent','units_and_denominators_correct','geography_and_transfer_limits_retained','no_iranian_prescription_inferred','independent_sources','no_unsafe_input_rates','source_policy_satisfied')
def contract(candidate,facts):
 full=candidate.get('research_route_version')==VERSION;detailed=candidate.get('review_schema_version')==2
 required=list(BASE_FLAGS)+['source_policy_version','human_review_claimed','limitations','fact_checks']
 if full:required+=['research_route_version','route_requirements_met']
 if detailed:required+=['decision','rejection_reasons']
 return {'version':1,'required_root_fields':required,'boolean_fields':list(BASE_FLAGS)+(['route_requirements_met'] if full else []),'research_route_version':VERSION if full else None,'source_policy_version':'university-single-source-v1','exact_fact_ids':[f['fact_id'] for f in facts],'human_review_claimed':False,'missing_flag_is_not_approval':True,'honest_negative_must_remain_negative':True,'concise_output_contract':'Evaluate every fact and all global flags. Keep each fact reason concise and limitations focused; do not repeat full documents or draft an article. Never omit a required field to save tokens. A route false remains a rejection. independent_sources is descriptive under the explicit source policy, not a forced true value.'}

def legacy_task(text,candidate):
 if candidate.get('research_route_version')==VERSION:
  text=text.replace('Return {','Return {research_route_version:'+VERSION+',route_requirements_met:boolean,',1)
  text+=' Both research_route_version and route_requirements_met are MANDATORY root fields of this response, not optional commentary. Return an honest boolean; missing is not pass. Never infer a pass from the requested JSON shape.'
 return text
