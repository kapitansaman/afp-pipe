"""Read-only, allow-listed public dashboard snapshot. No model or WordPress calls."""
import argparse,datetime,hashlib,json,re
from pathlib import Path

BRANCH='feat/agri-generator-v2-2905-merge593'
LANGS=('ru-RU','ar-IQ','tg-TJ','en-US')
def read(path,default=None):
 try:return json.loads(Path(path).read_text(encoding='utf-8'))
 except (OSError,ValueError):return {} if default is None else default

def sha(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def stamp(row):return row.get('completed_at') or row.get('updated_at') or row.get('checked_at') or row.get('started_at') or ''
def run_url(row):
 run=str(row.get('run_id',''))
 return 'https://github.com/kapitansaman/afp-pipe/actions/runs/'+run if run.isdigit() else None

def verified_post(row):
 from urllib.parse import urlsplit
 try:
  u=urlsplit(row.get('url',''))
  return row.get('public_verified') is True and u.scheme=='https' and u.hostname=='navar-abyari.ir' and not u.username and not u.password and u.port in (None,443) and isinstance(row.get('title'),str) and bool(row['title'].strip())
 except (ValueError,TypeError):return False

def build(root,commit='',now=None):
 root=Path(root);data=root/'data/agri-v2';out=root/'artifacts/agri-v2'
 now=now or datetime.datetime.now(datetime.timezone.utc)
 cfg=read(data/'config.json');policy=read(data/'parallel-policy.json');life=read(data/'family-lifecycle-policy.json');live=read(data/'status/live.json');manifest=read(data/'manifest.json')
 # Missing fields remain unknown; no unavailable metric is silently shown as zero.
 counts=manifest.get('counts',{});metrics=live.get('metrics',{})
 published=metrics.get('published_verified');total=counts.get('new')
 state=read(out/'parallel/families/assignments.json');families=[]
 for owner in state.get('families',[]):
  ident=owner.get('topic_id','')
  if not re.fullmatch(r'agri-[a-f0-9]{12}',ident):continue
  folder=out/'new'/ident
  checkpoints=[dict(read(p),stage=p.parent.name) for p in folder.glob('lifecycle/*/state.json')]
  last=max(checkpoints,key=stamp,default={})
  families.append({'id':ident,'family':owner.get('family_id'),'title':owner.get('title') or ident,'stage':last.get('stage') or owner.get('work_stage') or 'unknown','status':last.get('status') or 'assigned','attempts':last.get('attempts'),'at':stamp(last) or owner.get('assigned_at'),'reason':last.get('failure',{}).get('category'),'public_verified':read(folder/'wordpress-receipt.json').get('public_verified') is True})
 # Scan the actual durable rows, not just a potentially old queue index.
 reviews=[]
 for pattern in ('new/*/review-queue/*.json','parallel/writer-verification/*/*/review-queue/*.json'):
  for p in sorted(out.glob(pattern)):
   r=read(p)
   if r.get('language') not in LANGS or not re.fullmatch(r'agri-[a-f0-9]{12}',str(r.get('topic_id',''))):continue
   reviews.append({k:r.get(k) for k in ('topic_id','title','language','article_sha256','status','attempts','model_calls_spent','next_attempt_at','experimental_only','reason','publication_next_attempt_at')} | {'state_url':'https://github.com/kapitansaman/afp-pipe/blob/'+BRANCH+'/'+str(p.relative_to(root))})
 canonical_languages={(r['topic_id'],r['language'],r.get('article_sha256')) for r in reviews if not r.get('experimental_only') and re.fullmatch(r'[a-f0-9]{64}',str(r.get('article_sha256','')))}
 reviews=[r for r in reviews if not (r.get('experimental_only') and (r['topic_id'],r['language'],r.get('article_sha256')) in canonical_languages)]
 health=read(out/'parallel/health/latest.json')
 bound=bool(policy.get('credential_set_id')) and health.get('repository')==policy.get('repository')=='kapitansaman/afp-pipe' and health.get('credential_set_id')==policy['credential_set_id'] and health.get('audit_status')=='completed'
 health_view={'bound':bound,'checked_at':health.get('checked_at') if bound else None,'text_ok':len(health.get('eligible_text_slots',[])) if bound else None,'image_ok':len(health.get('eligible_image_slots',[])) if bound else None,'capacity':policy.get('key_limit'),'text_model':health.get('text_model') if bound else cfg.get('text_model'),'image_model':health.get('image_model') if bound else cfg.get('image_model'),'run_url':run_url(health) if bound else None}
 ops=[]
 for p in (out/'parallel/operations').glob('*/prepare.json'):
  r=read(p)
  if stamp(r):ops.append((stamp(r),p,r))
 latest=max(ops,key=lambda x:x[0],default=None);experiment=None
 if latest:
  _,p,r=latest;ident=r.get('topic_id');folder=out/'parallel/writer-verification'/p.parent.name/str(ident)
  if r.get('request_id') in ('ops-role-skills-controlled-launch-v1','ops-role-skills-image-feedback-continuation-v2','ops-role-skills-image-pair-final-v3','ops-image-three-corrections-single-fallback-test-v1','ops-image-fallback-language-only-after-cooldown-v1','ops-one-approved-persian-source-single-image-v1'):folder=out/'new'/str(ident)
  article=read(folder/'article.json');quality=read(folder/'language-quality-status.json');evidence=read(folder/'article-evidence-review.json');tg=read(folder/'translations/tg-TJ.json')
  quality_bound=bool(article) and quality.get('source_article_sha256')==sha(article) and bool(tg) and quality.get('translation_sha256')==sha(tg)
  brief=read(data/'briefs'/(str(ident)+'.json'))
  source_ok=bool(article) and bool(brief) and evidence.get('article_sha256')==sha(article) and evidence.get('brief_sha256')==sha(brief) and all(evidence.get('review',{}).get(k) is True for k in ('all_article_claims_supported','no_additional_numbers_or_advice','units_geography_product_preserved','answers_canonical_intent','no_fabricated_human_review'))
  experiment={'topic_id':ident,'title':article.get('title') or r.get('title') or ident or 'آزمون فنی','status':r.get('status'),'at':stamp(r),'run_url':run_url(r),'operation':p.parent.name,'model':r.get('model') or r.get('models',{}).get('default_text'),'model_calls':quality.get('model_calls_across_both_runs') if quality_bound else r.get('model_calls'),'published_posts':r.get('published_posts'),'source_reviewed':source_ok,'tajik_quality_pending':quality_bound and quality.get('status')=='experimental_draft_pending_independent_language_quality_check','native_review_done':quality.get('independent_native_language_review_done') is True if quality_bound else None,'image_calls':r.get('image_calls'),'wordpress_calls':r.get('wordpress_calls'),'failed_stage':r.get('failed_stage'),'nonpublishing_test':r.get('request_id') in ('ops-image-three-corrections-single-fallback-test-v1','ops-image-fallback-language-only-after-cooldown-v1'),'test_passed':r.get('status')=='image_fallback_verification_passed','selected_image_roles':r.get('selected_image_roles') or r.get('image_result',{}).get('roles',[]),'fallback_used':r.get('image_result',{}).get('fallback_used',False),'source_only':r.get('source_only') is True,'source_public_verified':r.get('source_public_verified') is True,'image_test_passed':r.get('image_test_passed') is True,'translation_test_passed':r.get('translation_test_passed') is True,'provider_waiting':max(r.get('provider_retry_at_epoch',0),r.get('pool',{}).get('cooldown_until_epoch',0))>now.timestamp()}
 canonical=read(out/'parallel/lifecycle/latest.json')
 publications=[]
 canonical_posts=[]
 for receipt in (out/'new').glob('*/wordpress-receipt.json'):
  row=read(receipt);article=read(receipt.parent/'article.json');candidate={**row,'title':article.get('title') or row.get('title')}
  if verified_post(candidate):canonical_posts.append(candidate)
 if canonical_posts:published=max(published if type(published)is int else 0,len(canonical_posts))
 for row in canonical_posts+[live.get('latest_publication',{})]+live.get('recent_publications',[]):
  if verified_post(row) and row['url'] not in {p['url'] for p in publications}:
   publications.append({k:row.get(k) for k in ('title','url','published_at','verified_at','public_verified')})
 publications.sort(key=lambda r:r.get('published_at') or r.get('verified_at') or '',reverse=True)
 validation=read(out/'parallel/image-fallback/implementation-validation.json') or read(out/'parallel/role-skills/implementation-validation.json') or read(out/'parallel/language-review-queue/implementation-validation.json')
 return {'version':2,'generated_at':now.isoformat(),'source':{'branch':BRANCH,'commit':commit},'automation':{'schedule_enabled':life.get('schedule_enabled'),'automatic_generation':cfg.get('automatic_generation'),'legacy_publication_enabled':cfg.get('publication_enabled'),'gated_publisher_enabled':life.get('publication_enabled'),'research_only':life.get('research_only_for_scoped_rollout'),'independent_languages':cfg.get('multilingual',{}).get('independent_publication'),'configured_workers':policy.get('max_article_workers')},'metrics':{'total':total,'remaining':max(total-published,0) if type(total)is int and type(published)is int else None,'published':published,'published_as_of':live.get('updated_at'),'merge':counts.get('merge'),'hold':counts.get('hold'),'review_waiting':sum(r['status'] not in ('published','approved') for r in reviews),'review_approved':sum(r['status']=='approved' for r in reviews),'assigned':len(families)},'health':health_view,'experiment':experiment,'reviews':reviews,'families':families,'publications':publications,'last_lifecycle':{'status':canonical.get('status'),'at':stamp(canonical),'run_url':run_url(canonical),'published_posts':canonical.get('published_posts')},'local_tests':{'passed':validation.get('tests_passed'),'at':validation.get('validated_at'),'live_test':False}}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));parser.add_argument('--output',type=Path,required=True);parser.add_argument('--commit',default='');a=parser.parse_args();result=build(a.root,a.commit);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Dashboard snapshot built (read-only).')
