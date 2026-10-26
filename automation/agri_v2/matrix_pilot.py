"""One fresh, explicitly admitted matrix pilot; never resets another family's budget."""
from .queue import DATA,OUT,load_json,get_topic
ID='ops-commercial-matrix-carrot-pilot-v1'
CONTINUATION_ID='ops-commercial-matrix-carrot-continue-v2'
PRIOR_RUN='40315021021'
TOPIC='agri-b6f7d6bea16b'
MAX_CALLS=24

def bound(env,data=DATA):
 if env.get('AFP_MATRIX_PILOT_ID') not in (ID,CONTINUATION_ID):return False
 from .operation_request import authorize
 if not authorize(env,data):return False
 row=load_json(data/'status/owner-operation-admission.json')
 return row['request_id']==env['AFP_MATRIX_PILOT_ID'] and row['request'].get('topic_id')==TOPIC

def select(env,data=DATA,out=OUT):
 if not bound(env,data):raise ValueError('current_bound_matrix_pilot_required')
 t=get_topic('new',TOPIC,data)
 if TOPIC in load_json(data/'config.json').get('publication_holds',{}):raise ValueError('pilot_topic_on_hold')
 ap=out/'parallel/families/assignments.json'
 if ap.exists():
  rows=load_json(ap)
  if any(r['topic_id']==TOPIC for r in rows.get('families',[])) or TOPIC in rows.get('research_backlog',{}):raise ValueError('pilot_topic_already_owned_or_deferred')
 # No attempt reset, accepted-brief rewrite, saved-article regeneration or published-post edit.
 if env.get('AFP_MATRIX_PILOT_ID')==CONTINUATION_ID:
  budget(env,data,out)
  folder=out/'new'/TOPIC
  st=load_json(folder/'lifecycle/research_extract/state.json')
  if st.get('attempts')!=1 or st.get('last_run_id')!=PRIOR_RUN or st.get('failure',{}).get('category')!='numeric_units_not_in_literal_source':raise ValueError('exact_preserved_first_extraction_required')
  if (data/'briefs'/(TOPIC+'.json')).exists() or (folder/'article.json').exists() or (folder/'wordpress-receipt.json').exists():raise ValueError('never_replace_reviewed_or_published_work')
  if not (folder/'lifecycle-evidence/candidate-raw.json').exists() or not (folder/'lifecycle-evidence/sources.json').exists():raise ValueError('saved_source_and_candidate_required')
 elif (data/'briefs'/(TOPIC+'.json')).exists() or (out/'new'/TOPIC).exists() or (out/'research'/(TOPIC+'.json')).exists():raise ValueError('fresh_pilot_topic_required')
 return [dict(t,family_id='matrix-pilot-01')]


def budget(env,data=DATA,out=OUT):
 if env.get('AFP_MATRIX_PILOT_ID')!=CONTINUATION_ID:return MAX_CALLS
 row=load_json(out/'parallel/lifecycle/runs'/PRIOR_RUN/'report.json')
 if row.get('run_id')!=PRIOR_RUN or row.get('status')!='pilot_incomplete' or row.get('matrix_pilot') is not True or row.get('assigned_count')!=1 or row.get('published_posts')!=0 or row.get('pool',{}).get('model_requests_reserved')!=1 or row.get('pool',{}).get('peak_image_leases')!=0:raise ValueError('prior_pilot_budget_receipt_required')
 if {r['topic_id'] for r in row.get('results',[])}!={TOPIC}:raise ValueError('prior_pilot_topic_receipt_required')
 return MAX_CALLS-1
