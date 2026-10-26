"""One fresh, explicitly admitted matrix pilot; never resets another family's budget."""
from .queue import DATA,OUT,load_json,get_topic
ID='ops-commercial-matrix-carrot-pilot-v1'
TOPIC='agri-b6f7d6bea16b'
MAX_CALLS=24

def bound(env,data=DATA):
 if env.get('AFP_MATRIX_PILOT_ID')!=ID:return False
 from .operation_request import authorize
 if not authorize(env,data):return False
 row=load_json(data/'status/owner-operation-admission.json')
 return row['request_id']==ID and row['request'].get('topic_id')==TOPIC

def select(env,data=DATA,out=OUT):
 if not bound(env,data):raise ValueError('current_bound_matrix_pilot_required')
 t=get_topic('new',TOPIC,data)
 if TOPIC in load_json(data/'config.json').get('publication_holds',{}):raise ValueError('pilot_topic_on_hold')
 ap=out/'parallel/families/assignments.json'
 if ap.exists():
  rows=load_json(ap)
  if any(r['topic_id']==TOPIC for r in rows.get('families',[])) or TOPIC in rows.get('research_backlog',{}):raise ValueError('pilot_topic_already_owned_or_deferred')
 # No attempt reset, accepted-brief rewrite, saved-article regeneration or published-post edit.
 if (data/'briefs'/(TOPIC+'.json')).exists() or (out/'new'/TOPIC).exists() or (out/'research'/(TOPIC+'.json')).exists():raise ValueError('fresh_pilot_topic_required')
 return [dict(t,family_id='matrix-pilot-01')]
