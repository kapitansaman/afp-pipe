"""Exact next-run continuation: 3 spent + <=39 remaining, no historical resets."""
import hashlib
from .queue import load_json,atomic_json
from .three_source_trial import ID,TOPICS
from .role_skills_launch import preserved_files

def original_files(out):
 root=out/'parallel/operations'/ID
 return {str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

def verify_prior(data,out):
 from .family_lifecycle import state
 root=out/'parallel/operations'/ID;r=load_json(root/'prepare.json');ledger=load_json(root/'model-calls.json')
 if r.get('run_id')!='40467890941' or r.get('status')!='three_source_trial_partial' or r.get('topic_ids')!=list(TOPICS) or (r.get('model_calls'),r.get('image_calls'),r.get('published_posts'),r.get('wordpress_calls'),r.get('reserved_total_model_calls'))!=(3,0,0,0,3):raise ValueError('Exact failed original trial required')
 if ledger.get('text')!=3 or ledger.get('image')!=0 or len(ledger.get('history',[]))!=3 or any(sum(x.get('topic_id')==t and x.get('kind')=='text' for x in ledger['history'])!=1 for t in TOPICS):raise ValueError('Original spent calls must remain charged')
 if not preserved_files(out,r['prior_source_files']):raise ValueError('Prior sources changed')
 for p,key in [(out/'parallel/families/assignments.json','assignment_sha256'),(data/'manifest.json','manifest_sha256')]:
  if hashlib.sha256(p.read_bytes()).hexdigest()!=r[key]:raise ValueError('Prior ownership or manifest changed')
 for ident in TOPICS:
  folder=out/'new'/ident;s=state(folder,'research_extract')
  if s.get('attempts')!=1 or s.get('status')!='failed' or s.get('last_run_id')!='40467890941' or (data/'briefs'/(ident+'.json')).exists() or (folder/'wordpress-receipt.json').exists():raise ValueError('Exact one-failed-extraction state required')
 return r

def prepare_topic(topic,data,out,run_id):
 from . import family_lifecycle as f
 from .extraction_feedback import diagnose
 from .scoped_research import stage
 folder=out/'new'/topic['id'];ev=folder/'lifecycle-evidence';raw=ev/'candidate-raw.json'
 if f.state(folder,'research_extract').get('attempts')!=1:raise ValueError('Never reset extraction attempts')
 feedback=diagnose(topic,load_json(raw),load_json(ev/'sources.json')['documents'])
 feedback['old_evidence_ids_are_archived']=topic['intent']=='soil_sensor'
 atomic_json(ev/'extraction-feedback.json',feedback)
 # Preserve old raw + failed state, then the worker legitimately reserves attempt 2.
 f.archive(folder,'research_extract',[raw])
 if topic['intent']=='soil_sensor':
  s=f.state(folder,'research_sources')
  if s.get('attempts')!=1 or s.get('status')!='validated':raise ValueError('Exact prior source attempt required')
  paths=[ev/name for name in ['sources.json','source-discovery-report.json','source-fetch-report.json','source-link-fetch-report.json','source-hub-fetch-report.json','source-link-fetch-report-2.json']]
  result=f.attempt(folder,'research_sources',run_id,lambda:stage(topic,'research_sources',None,data,out),outputs=paths,limit=3)
  if result['status']!='stage_completed':raise ValueError('Refreshed sensor sources unavailable; no model call')
