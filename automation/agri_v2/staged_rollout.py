"""Manual 1 -> 3 -> 20 acceptance. No inferred pass, silent promotion or model call."""
import hashlib,json
from .queue import load_json,atomic_json,utcnow,get_topic
from .foundation_policy import enabled,POLICY
BASE='parallel/staged-rollout'
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def load(out):
 p=out/BASE/'state.json'
 if not p.exists():return {'version':1,'limit':1,'cohort':[],'accepted':[],'history':[],'schedule_enabled':False,'original_attempts_reset':False}
 r=load_json(p);signature=r.pop('state_sha256',None)
 if signature!=digest(r) or r.get('version')!=1 or type(r.get('limit'))is not int or r['limit'] not in (1,3,20) or not isinstance(r.get('cohort'),list) or len(r['cohort'])>r['limit'] or r.get('schedule_enabled')is not False or r.get('original_attempts_reset')is not False:raise ValueError('Invalid staged rollout state; no escalation')
 # A larger limit requires a bound acceptance record for every preceding phase.
 required=[] if r['limit']==1 else [1] if r['limit']==3 else [1,3]
 if [a.get('limit') for a in r.get('accepted',[])]!=required:raise ValueError('Staged acceptance chain missing')
 for a in r.get('accepted',[]):
  proof=out/BASE/'acceptances'/(a['acceptance_sha256']+'.json')
  if not proof.exists() or digest(load_json(proof))!=a['acceptance_sha256']:raise ValueError('Staged acceptance evidence changed')
  evidence=load_json(proof)
  if evidence.get('limit')!=a['limit'] or len(evidence.get('cohort',[]))!=a['limit'] or len(evidence.get('verified_topics',[]))!=a['limit'] or any(v.get('public_verified')is not True for v in evidence['verified_topics']):raise ValueError('Staged cohort acceptance incomplete')
 return r

def save(out,row):atomic_json(out/BASE/'state.json',dict(row,state_sha256=digest(row)))
def protects_handoff(ident,data,out):
 if not enabled(data):return False
 return any(r['topic_id']==ident for r in load(out)['cohort'])

def choose(topics,data,out,run_id):
 if not enabled(data):return topics,None
 from .family_admission import project
 due,rows=project(topics,data,out);state=load(out);by_id={t['id']:t for t in topics};ready={t['id']:t for t in due}
 from .family_scheduler import family_complete
 # Keep cohort identities across temporary waits. A terminally released topic
 # can be replaced, but its rejection/history is not an acceptance or reset.
 cohort=[]
 for old in state['cohort']:
  ident=old['topic_id']
  if ident in by_id or family_complete(ident,data,out):cohort.append(old)
  else:state['history'].append({'event':'cohort_topic_released_without_acceptance','topic':old,'at':utcnow()})
 excluded={t['topic_id'] for a in state['accepted'] for t in load_json(out/BASE/'acceptances'/(a['acceptance_sha256']+'.json'))['cohort']}
 chosen={t['topic_id'] for t in cohort};stage_by_id={r['topic_id']:r['stage'] for r in rows}
 # Prefer already-approved text, then immutable queue order. This is work
 # prioritization only; publication still goes through every original gate.
 def priority(t):
  stage=stage_by_id[t['id']];return (0 if stage=='publish' else 1 if stage=='images' or str(stage).startswith(('image-','vision-')) else 2 if stage=='text' else 3,t['family_id'])
 for topic in sorted(due,key=priority):
  if len(cohort)>=state['limit']:break
  if topic['id'] in chosen or topic['id'] in excluded:continue
  cohort.append({'topic_id':topic['id'],'family_id':topic['family_id'],'title_sha256':digest(topic['title'])});chosen.add(topic['id'])
 state['cohort']=cohort;save(out,state)
 selected=[ready[r['topic_id']] for r in cohort if r['topic_id'] in ready]
 info={'limit':state['limit'],'cohort':cohort,'selected_count':len(selected),'waiting':[r for r in rows if not r['due']],'manual_verification_required':True,'run_id':run_id,'automatic_promotion':False}
 atomic_json(out/BASE/'latest-selection.json',info);return selected,info

def checkpoints(ident,out):
 runs=[]
 for p in sorted((out/'parallel/lifecycle/runs').glob('*/report.json')):
  r=load_json(p)
  if r.get('status') not in ('completed','completed_with_failures') or r.get('coordinator_failure'):continue
  matching=[x for x in r.get('results',[]) if x.get('topic_id')==ident]
  if len(matching)==1 and matching[0].get('checkpoint_merged')is True and matching[0].get('status') not in ('worker_timed_out','worker_failed','worker_operational_failure','stage_reconciliation_required'):runs.append({'run_id':r['run_id'],'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 if len({r['run_id'] for r in runs})<2:raise ValueError('Two distinct merged checkpoint runs required to prove resumption')
 return runs

def verify_published_bytes(post,receipt):
 expected=receipt.get('publication_content_sha256');raw=post.get('content',{}).get('raw')
 if not isinstance(expected,str) or len(expected)!=64 or not isinstance(raw,str) or hashlib.sha256(raw.encode()).hexdigest()!=expected:raise ValueError('Published content differs from original approved publication bytes')

def verify_topic(member,wp,data,out):
 from .family_scheduler import family_complete
 from .family_lifecycle import article_checked,state
 from .pipeline import check_brief,digest as article_digest
 from .image_quality import require_all
 from .multilingual import LANGUAGES,verify_target
 topic=get_topic('new',member['topic_id'],data);topic['family_id']=member['family_id'];folder=out/'new'/topic['id']
 if digest(topic['title'])!=member['title_sha256'] or not family_complete(topic['id'],data,out):raise ValueError('Cohort not end-to-end complete')
 if any(load_json(p).get('status') in ('reserved','reconciliation_required') for p in (folder/'lifecycle').glob('*/state.json')):raise ValueError('Unconfirmed cohort request')
 brief=load_json(data/'briefs'/(topic['id']+'.json'));check_brief(topic,brief);article=article_checked(folder,topic,brief);require_all(folder,topic,article)
 validation=load_json(folder/'lifecycle-publication-validation.json')
 from .image_layout import roles_for
 images={str(k):hashlib.sha256((folder/f'image-{k}.webp').read_bytes()).hexdigest() for k in roles_for(folder)}
 if validation.get('brief_sha256')!=article_digest(brief) or validation.get('article_sha256')!=article_digest(article) or validation.get('image_sha256')!=images:raise ValueError('Publication input binding changed')
 runs=checkpoints(topic['id'],out);rp=folder/'wordpress-receipt.json';receipt=load_json(rp)
 if receipt.get('topic_id')!=topic['id'] or receipt.get('public_verified')is not True:raise ValueError('Owned verified source required')
 wp.verify(receipt['post_id'],topic,rp)  # existing public GET/validation only
 languages=LANGUAGES if load_json(data/'config.json').get('multilingual',{}).get('enabled') else []
 receipts=[(None,load_json(rp))]+[(lang,load_json(folder/'translations'/(lang+'.wordpress.json'))) for lang in languages];post_ids=[]
 for lang,r in receipts:
  if r.get('public_verified')is not True or type(r.get('post_id'))is not int:raise ValueError('Verified receipt required')
  post,_=wp.call('posts/'+str(r['post_id'])+'?context=edit');marker='<!-- afp-agri-v2:'+topic['id']+(':'+lang if lang else '')+' -->'
  if post.get('status')!='publish' or post.get('author')!=wp.user_id or marker not in post.get('content',{}).get('raw','') or post.get('link')!=r.get('url'):raise ValueError('Public post ownership changed')
  verify_published_bytes(post,r)
  if lang:
   translated=load_json(folder/'translations'/(lang+'.json'))
   if translated.get('source_article_sha256')!=article_digest(article) or post.get('afp_language')!=lang or post.get('afp_source_post_id')!=receipt['post_id'] or r.get('source_post_id')!=receipt['post_id']:raise ValueError('Translation source/language changed')
   import html
   from .display_units import text as display_text
   if post.get('featured_media')!=receipt.get('featured_media') or html.unescape(post.get('title',{}).get('rendered',''))!=display_text(translated['title'],lang):raise ValueError('Published translation title/media changed')
   verify_target(r['url'],lang)
  matches=[]
  from urllib.parse import quote
  for status in ('publish','draft','pending','future','private'):
   found,_=wp.call('posts?slug='+quote(post['slug'])+'&status='+status+'&context=edit');matches.extend(found)
  if len(matches)!=1 or matches[0].get('id')!=r['post_id']:raise ValueError('Duplicate or ambiguous post slug')
  post_ids.append(r['post_id'])
 if len(set(post_ids))!=len(post_ids):raise ValueError('Duplicate publication identities')
 return {'topic_id':topic['id'],'family_id':member['family_id'],'post_ids':post_ids,'checkpoint_runs':runs,'article_sha256':article_digest(article),'brief_sha256':article_digest(brief),'public_verified':True}

def verify(env,data,out,wp=None):
 if not enabled(data) or env.get('GITHUB_EVENT_NAME')!='workflow_dispatch':raise ValueError('Manual staged verification required')
 state=load(out)
 if state['limit']==20:return {'status':'twenty_family_stage_already_released','model_calls':0,'post_mutations':0}
 if len(state['cohort'])!=state['limit']:return {'status':'cohort_not_selected','current_limit':state['limit'],'model_calls':0,'post_mutations':0}
 if wp is None:
  from .wordpress import WordPress
  wp=WordPress()
 wp.preflight();proofs=[]
 try:
  for member in state['cohort']:proofs.append(verify_topic(member,wp,data,out))
 except Exception as e:
  from .failure_diagnostics import failure_details
  result={'status':'staged_acceptance_not_ready','current_limit':state['limit'],'failure':failure_details(e),'model_calls':0,'post_mutations':0,'limit_changed':False};atomic_json(out/BASE/'latest-verification.json',result);return result
 proof={'version':1,'limit':state['limit'],'cohort':state['cohort'],'verified_topics':proofs,'checked_at':utcnow(),'run_id':env.get('GITHUB_RUN_ID'),'model_calls':0,'post_mutations':0,'schedule_enabled':False};sha=digest(proof);atomic_json(out/BASE/'acceptances'/(sha+'.json'),proof)
 old=state['limit'];state['accepted'].append({'limit':old,'acceptance_sha256':sha});state.update(limit=3 if old==1 else 20,cohort=[]);save(out,state)
 return {'status':'staged_acceptance_verified','previous_limit':old,'current_limit':state['limit'],'acceptance_sha256':sha,'model_calls':0,'post_mutations':0,'schedule_enabled':False}
