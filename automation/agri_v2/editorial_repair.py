"""Explicit, content-only two-post presentation repair. No models or new publications."""
import hashlib,json,os
from .queue import DATA,OUT,load_json,atomic_json,utcnow,get_topic
from .wordpress import WordPress,WPError
from .internal_links import augment,selected_links,validate_targets,verify_links
from .editorial_presentation import VERSION,end_sources,verify_sources,related_articles,translated_related
from .multilingual import verify_target
ID='beet-end-sources-related-language-v1';TOPIC='agri-d52cdebf818e'

def validate(req):
 expected=[(524196,'fa-IR'),(524200,'en-US')]
 if req.get('request_id')!=ID or req.get('topic_id')!=TOPIC or req.get('authorized') is not True or req.get('policy')!=VERSION or req.get('max_existing_posts')!=2 or req.get('max_new_posts')!=0 or req.get('max_model_calls')!=0:raise ValueError('Exact two-post editorial request required')
 rows=req.get('posts',[])
 if [(r.get('post_id'),r.get('language')) for r in rows]!=expected or any(not r.get('expected_modified_gmt') for r in rows):raise ValueError('Exact post revisions and languages required')
 return rows

def run(data=DATA,out=OUT,wp=None):
 req=load_json(data/'editorial-repair-request.json');targets=validate(req);rp=out/'editorial-repairs'/ID/'receipt.json'
 if rp.exists():return {'status':'already_reserved_no_replay','request_id':ID,'model_calls':0,'new_posts':0}
 wp=WordPress() if wp is None else wp;wp.preflight();topic=get_topic('new',TOPIC);folder=out/'new'/TOPIC;brief=load_json(data/'briefs'/(TOPIC+'.json'));source_receipt=load_json(folder/'wordpress-receipt.json')
 posts={};prepared={};relations={};marker='<!-- afp-agri-v2:'+TOPIC
 for target in targets:
  p,_=wp.call('posts/'+str(target['post_id'])+'?context=edit');raw=p.get('content',{}).get('raw','');lang=target['language'];expected_marker=marker+(' -->' if lang=='fa-IR' else ':'+lang+' -->')
  if p.get('id')!=target['post_id'] or p.get('author')!=wp.user_id or p.get('status')!='publish' or expected_marker not in raw or p.get('afp_language')!=lang:raise WPError('Published post ownership/language changed')
  if p.get('modified_gmt')!=target['expected_modified_gmt']:raise WPError('Post changed since explicit editorial request')
  if lang!='fa-IR' and p.get('afp_source_post_id')!=524196:raise WPError('Translation source binding changed')
  posts[lang]=p
 inventory=wp.inventory();related=related_articles(topic,posts['fa-IR']['link'],inventory['records']);relations['fa-IR']=related
 relations['en-US']=translated_related(wp,related,'en-US',posts['en-US']['link'])
 for lang,p in posts.items():
  links=relations[lang];validate_targets(links)
  for row in links:verify_target(row['url'],lang)
  raw=p['content']['raw']
  if lang=='fa-IR':
   context=dict(topic,commercial_matrix=source_receipt.get('commercial_matrix'),editorial_related=links)
   raw=augment(raw,context,p['link'])
  elif links:
   import html
   raw+='<p>Related articles: '+' · '.join('<a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['anchor'])+'</a>' for r in links)+'</p>'
  prepared[lang]=end_sources(raw,brief['sources'],lang)
 # Reserve all remote mutations before the first write. A crash cannot replay blindly.
 state={'request_id':ID,'status':'reserved','run_id':os.environ.get('GITHUB_RUN_ID'),'at':utcnow(),'model_calls':0,'new_posts':0,'results':{}};atomic_json(rp,state)
 for lang,p in posts.items():atomic_json(rp.with_name(lang+'-before.json'),p)
 try:
  for lang,p in posts.items():
   current,_=wp.call('posts/'+str(p['id'])+'?context=edit')
   if any(current.get(k)!=p.get(k) for k in ('id','author','status','link','title','featured_media','afp_language','afp_source_post_id','modified_gmt')) or current.get('content',{}).get('raw')!=p['content']['raw']:raise WPError('Post changed during editorial verification')
   wp.call('posts/'+str(p['id']),'POST',{'content':prepared[lang]})
   saved,_=wp.call('posts/'+str(p['id'])+'?context=edit')
   for key in ('id','author','status','link','title','featured_media','afp_language','afp_source_post_id'):
    if saved.get(key)!=p.get(key):raise WPError('Non-content post property changed')
   urls=verify_sources(saved['content']['raw'],brief['sources'],lang);verify_links(saved['content']['raw'],relations[lang])
   public,_=wp.call('posts/'+str(p['id']));verify_sources(public['content']['rendered'],brief['sources'],lang);verify_links(public['content']['rendered'],relations[lang]);verify_target(p['link'],lang)
   receipt_path=folder/'wordpress-receipt.json' if lang=='fa-IR' else folder/'translations'/(lang+'.wordpress.json')
   receipt=load_json(receipt_path);receipt.update(editorial_presentation_policy=VERSION,editorial_source_urls=[s['url'] for s in brief['sources']],editorial_related=relations[lang]);atomic_json(receipt_path,receipt)
   state['results'][lang]={'post_id':p['id'],'url':p['link'],'status':'public_presentation_verified','related_articles':relations[lang],'scientific_sources':urls,'after_sha256':hashlib.sha256(saved['content']['raw'].encode()).hexdigest()};atomic_json(rp,state)
  state.update(status='public_presentation_verified',completed_at=utcnow());atomic_json(rp,state);return state
 except Exception as exc:
  from .failure_diagnostics import failure_details
  state.update(status='repair_stopped_reconciliation_required',failure=failure_details(exc),completed_at=utcnow());atomic_json(rp,state);return state

def reconcile(data=DATA,out=OUT,wp=None):
 """Explicit read-before-write continuation; never replay an uncertain POST."""
 req=load_json(data/'editorial-repair-request.json');targets=validate(req);rp=out/'editorial-repairs'/ID/'receipt.json';state=load_json(rp)
 if state.get('request_id')!=ID or state.get('status')!='repair_stopped_reconciliation_required':raise ValueError('Exact stopped editorial receipt required')
 wp=WordPress() if wp is None else wp;wp.preflight();topic=get_topic('new',TOPIC);folder=out/'new'/TOPIC;brief=load_json(data/'briefs'/(TOPIC+'.json'));source_receipt=load_json(folder/'wordpress-receipt.json');inventory=wp.inventory()
 before={r['language']:load_json(rp.with_name(r['language']+'-before.json')) for r in targets}
 related=related_articles(topic,before['fa-IR']['link'],inventory['records']);relations={'fa-IR':related,'en-US':translated_related(wp,related,'en-US',before['en-US']['link'])};prepared={};current={};write_needed={}
 for target in targets:
  lang=target['language'];p=before[lang];raw=p['content']['raw'];links=relations[lang]
  if p.get('id')!=target['post_id'] or p.get('modified_gmt')!=target['expected_modified_gmt'] or p.get('author')!=wp.user_id or p.get('afp_language')!=lang or p.get('status')!='publish':raise WPError('Backup/request identity mismatch')
  validate_targets(links)
  for link in links:verify_target(link['url'],lang)
  if lang=='fa-IR':raw=augment(raw,dict(topic,commercial_matrix=source_receipt.get('commercial_matrix'),editorial_related=links),p['link'])
  elif links:
   import html
   raw+='<p>Related articles: '+' · '.join('<a href="'+html.escape(r['url'],quote=True)+'">'+html.escape(r['anchor'])+'</a>' for r in links)+'</p>'
  prepared[lang]=end_sources(raw,brief['sources'],lang)
  saved,_=wp.call('posts/'+str(p['id'])+'?context=edit');current[lang]=saved
  if any(saved.get(k)!=p.get(k) for k in ('id','author','status','link','title','featured_media','afp_language','afp_source_post_id')):raise WPError('Live post identity/properties changed')
  live=saved.get('content',{}).get('raw')
  if live==prepared[lang]:write_needed[lang]=False
  elif live==p['content']['raw'] and saved.get('modified_gmt')==p['modified_gmt']:write_needed[lang]=True
  else:raise WPError('Live content is neither original nor exact planned presentation; no replay')
 # Both outcomes have been reconciled before any new write. Preserve the original failure.
 state.setdefault('reconciliation_history',[]).append({'at':utcnow(),'run_id':os.environ.get('GITHUB_RUN_ID'),'write_needed':write_needed});atomic_json(rp,state)
 try:
  for lang,p in before.items():
   if write_needed[lang]:
    check,_=wp.call('posts/'+str(p['id'])+'?context=edit')
    if any(check.get(k)!=current[lang].get(k) for k in ('id','author','status','link','title','featured_media','afp_language','afp_source_post_id','modified_gmt')) or check.get('content',{}).get('raw')!=current[lang].get('content',{}).get('raw'):raise WPError('Post changed during explicit reconciliation')
    wp.call('posts/'+str(p['id']),'POST',{'content':prepared[lang]})
   saved,_=wp.call('posts/'+str(p['id'])+'?context=edit')
   if saved.get('content',{}).get('raw')!=prepared[lang] or any(saved.get(k)!=p.get(k) for k in ('id','author','status','link','title','featured_media','afp_language','afp_source_post_id')):raise WPError('Reconciled post differs from planned content')
   urls=verify_sources(saved['content']['raw'],brief['sources'],lang);verify_links(saved['content']['raw'],relations[lang]);public,_=wp.call('posts/'+str(p['id']));verify_sources(public['content']['rendered'],brief['sources'],lang);verify_links(public['content']['rendered'],relations[lang]);verify_target(p['link'],lang)
   receipt_path=folder/'wordpress-receipt.json' if lang=='fa-IR' else folder/'translations'/(lang+'.wordpress.json');receipt=load_json(receipt_path);receipt.update(editorial_presentation_policy=VERSION,editorial_source_urls=[s['url'] for s in brief['sources']],editorial_related=relations[lang]);atomic_json(receipt_path,receipt)
   state['results'][lang]={'post_id':p['id'],'url':p['link'],'status':'public_presentation_verified','related_articles':relations[lang],'scientific_sources':urls,'new_write_during_reconciliation':write_needed[lang],'after_sha256':hashlib.sha256(prepared[lang].encode()).hexdigest()};atomic_json(rp,state)
  state.update(status='public_presentation_verified',completed_at=utcnow());atomic_json(rp,state);return state
 except Exception as exc:
  from .failure_diagnostics import failure_details
  state.update(status='repair_stopped_reconciliation_required',reconciliation_failure=failure_details(exc));atomic_json(rp,state);return state

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
