"""Read-only revision preflight. No model, WordPress mutation or publication path."""
import base64,hashlib,html,json,re,urllib.request,urllib.error
from pathlib import Path
from .queue import DATA,OUT,ROOT,load_json,atomic_json,utcnow
from .pipeline import digest
TOPIC='agri-6fc1032cdf42';ID='alfalfa-readonly-prepublication-v1';SITE='https://navar-abyari.ir'
APPROVED='alfalfa-claim-policy-regional-final-v1'
class ReadBlocked(ValueError):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None
class ReadOnlySite:
 """Only fixed-origin GET. No generic method, request body, upload or publisher API."""
 def __init__(self,env):
  if env.get('AFP_WP_BASE_URL','').rstrip('/')!=SITE or not env.get('AFP_WP_USERNAME') or not env.get('AFP_WP_APP_PASSWORD'):raise ReadBlocked('readonly_credentials_missing_or_origin_invalid')
  self.auth='Basic '+base64.b64encode((env['AFP_WP_USERNAME']+':'+env['AFP_WP_APP_PASSWORD']).encode()).decode();self.count=0;self.opener=urllib.request.build_opener(NoRedirect())
 def get(self,path):
  if not re.fullmatch(r'(users/me|posts(?:/[0-9]+)?|media/[0-9]+)\?[^#]*',path):raise ReadBlocked('readonly_route_not_allowed')
  self.count+=1
  if self.count>350:raise ReadBlocked('readonly_get_budget_exhausted')
  request=urllib.request.Request(SITE+'/wp-json/wp/v2/'+path,headers={'Authorization':self.auth,'Accept':'application/json','User-Agent':'AFP-readonly-prepublication'},method='GET')
  try:
   with self.opener.open(request,timeout=60) as response:
    raw=response.read(4_000_001);headers={k.lower():v for k,v in response.headers.items()}
   if len(raw)>4_000_000:raise ReadBlocked('readonly_response_too_large')
   return json.loads(raw),headers
  except ReadBlocked:raise
  except Exception:raise ReadBlocked('readonly_authenticated_get_failed') from None
 def asset(self,url):
  if not re.fullmatch(re.escape(SITE)+r'/wp-content/uploads/agri-6fc1032cdf42-image-[12]\.webp',url):raise ReadBlocked('readonly_asset_not_allowed')
  self.count+=1
  if self.count>350:raise ReadBlocked('readonly_get_budget_exhausted')
  try:
   with self.opener.open(urllib.request.Request(url,headers={'User-Agent':'AFP-readonly-prepublication'},method='GET'),timeout=60) as response:raw=response.read(4_000_001)
   if len(raw)>4_000_000:raise ReadBlocked('readonly_asset_too_large')
   return raw
  except ReadBlocked:raise
  except Exception:raise ReadBlocked('readonly_asset_get_failed') from None

def owned(post,user_id,receipt):
 raw=post.get('content',{}).get('raw')
 expected={'id':524204,'author':user_id,'status':'publish','slug':'preharvest-alfalfa-irrigation-criteria','link':receipt['url'],'featured_media':receipt['featured_media'],'afp_language':'fa-IR'}
 if type(user_id)is not int or user_id<=0 or receipt.get('post_id')!=524204 or receipt.get('topic_id')!=TOPIC or any(post.get(k)!=v for k,v in expected.items()) or not isinstance(raw,str) or '<!-- afp-agri-v2:'+TOPIC+' -->' not in raw:raise ReadBlocked('readonly_post_identity_changed')
 if hashlib.sha256(raw.encode()).hexdigest()!=receipt.get('publication_content_sha256'):raise ReadBlocked('readonly_post_bytes_changed')
 return {'post_id':524204,'authenticated_owner_id':user_id,'identity_matches':True,'original_publication_bytes_unchanged':True,'content_sha256':receipt['publication_content_sha256'],'modified_gmt':post.get('modified_gmt'),'featured_media':post['featured_media']}

def translations(folder,article):
 result={}
 for lang in ('ru-RU','ar-IQ','tg-TJ','en-US'):
  path=folder/'translations'/(lang+'.json');review=folder/'translations'/(lang+'.fidelity.json')
  row=load_json(path) if path.exists() else None;fidelity=load_json(review) if review.exists() else None
  result[lang]={'status':'missing_translation_for_revised_source' if row is None else 'stale_translation_for_old_source' if row.get('source_article_sha256')!=digest(article) else 'requires_current_independent_review','source_article_sha256':row.get('source_article_sha256') if row else None,'revised_source_sha256':digest(article),'old_review_reused':False,'current_fidelity_accepted':False,'current_regional_accepted':False}
 return result

def protected(data,out):
 paths=list((out/'new'/TOPIC).rglob('*'))+list((out/'regional-revisions').rglob('*'))+list((out/'claim-policy-rechecks').rglob('*'))+[data/'briefs'/(TOPIC+'.json')]
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}

def run(env,data=DATA,out=OUT,site_factory=ReadOnlySite):
 from .parallel_control import BRANCH
 if env.get('GITHUB_EVENT_NAME')!='workflow_dispatch' or env.get('GITHUB_REPOSITORY')!='kapitansaman/afp-pipe' or env.get('GITHUB_REF_NAME')!=BRANCH or not str(env.get('GITHUB_RUN_ID','')).isdigit():raise ReadBlocked('readonly_exact_manual_branch_required')
 root=out/'prepublication-audits'/ID/env['GITHUB_RUN_ID'];rp=root/'report.json'
 if rp.exists():return {'status':'readonly_audit_already_recorded','site_mutations':0,'model_calls':0}
 before=protected(data,out);folder=out/'new'/TOPIC;receipt=load_json(folder/'wordpress-receipt.json')
 approved=out/'claim-policy-rechecks'/APPROVED;source_report=load_json(approved/'report.json');article=load_json(approved/'article.json');brief=load_json(approved/'brief.json')
 if source_report.get('status')!='claim_recheck_ready_for_publication_review' or source_report.get('publication_authorized') is not False or source_report.get('article_sha256')!=digest(article) or source_report.get('brief_sha256')!=digest(brief):raise ReadBlocked('readonly_approved_revision_binding_changed')
 row={'request_id':ID,'run_id':env['GITHUB_RUN_ID'],'topic_id':TOPIC,'started_at':utcnow(),'status':'running','site_mutations':0,'model_calls':0,'image_generation_calls':0,'translation_generation_calls':0,'publication_authorized':False,'revised_article_sha256':digest(article),'revised_brief_sha256':digest(brief),'protected_sha256':digest(before),'max_authenticated_gets_and_assets':350,'safe_to_publish':False}
 atomic_json(rp,row);site=None
 try:
  site=site_factory(env);user,_=site.get('users/me?context=edit&_fields=id');post,_=site.get('posts/524204?context=edit&_fields=id,author,status,slug,link,featured_media,afp_language,content,modified_gmt,title')
  row['live_identity']=owned(post,user.get('id'),receipt)
  atomic_json(root/'current-post.json',{k:post.get(k) for k in ('id','author','status','slug','link','featured_media','afp_language','content','modified_gmt','title')})
  inventory=[];page=1;pages=1
  while page<=pages:
   batch,headers=site.get('posts?status=publish&per_page=100&page='+str(page)+'&_fields=id,title,link,status,modified,slug,afp_language')
   if not isinstance(batch,list):raise ReadBlocked('readonly_inventory_invalid')
   if page==1:
    pages=int(headers.get('x-wp-totalpages','0'))
    if not 1<=pages<=200:raise ReadBlocked('readonly_inventory_budget_invalid')
   inventory.extend(batch);page+=1
  atomic_json(root/'public-inventory.json',{'checked_at':utcnow(),'scope':'all published posts; excludes private drafts','records':inventory})
  previous=load_json(folder/'lifecycle-evidence/existing-content.json');ids=set(previous['related_ids'])
  # Broad multilingual title shortlist, plus ALL historical related IDs. No semantic approval from title matching.
  for p in inventory:
   if re.search(r'یونجه|يونجه|alfalfa|люцерн|юнучқ|برسيم|люцерна',html.unescape(p.get('title',{}).get('rendered','')),re.I):ids.add(p['id'])
  ids.discard(524204)
  if len(ids)>100:raise ReadBlocked('readonly_related_scope_exceeds_budget')
  from .family_trial import existing_document
  docs=[];public_ids={p['id'] for p in inventory};unavailable=[]
  for ident in sorted(ids):
   if ident not in public_ids:unavailable.append({'id':ident,'reason':'not_in_current_public_inventory'});continue
   related,_=site.get('posts/'+str(ident)+'?_fields=id,title,content,link,status')
   docs.append(existing_document(related,ident,SITE))
  atomic_json(root/'fresh-related-content.json',{'topic_id':TOPIC,'related_ids':sorted(ids),'documents':docs,'unavailable':unavailable,'checked_at':utcnow(),'owner_post_excluded':524204})
  old={d['id']:d['sha256'] for d in previous['documents']};fresh={d['id']:d['sha256'] for d in docs}
  row['overlap_scope']={'historical_related_ids':sorted(old),'fresh_related_ids':sorted(fresh),'added_ids':sorted(set(fresh)-set(old)),'removed_or_unavailable_ids':sorted(set(old)-set(fresh)),'changed_content_ids':sorted(i for i in set(old)&set(fresh) if old[i]!=fresh[i]),'all_current_related_texts_fetched':not unavailable and not any(d.get('text_truncated') for d in docs),'semantic_revision_overlap_approved':False,'status':'fresh_scope_collected_requires_revision_specific_semantic_review','self_post_excluded':524204}
  media_results=[]
  for m in receipt['media']:
   index=m['index'];meta,_=site.get('media/'+str(m['id'])+'?_fields=id,source_url,mime_type,post');local=folder/('image-'+str(index)+'.webp');expected=hashlib.sha256(local.read_bytes()).hexdigest()
   if meta.get('id')!=m['id'] or meta.get('source_url')!=m['url'] or meta.get('mime_type')!='image/webp':raise ReadBlocked('readonly_live_media_identity_changed')
   actual=hashlib.sha256(site.asset(m['url'])).hexdigest()
   if actual!=expected:raise ReadBlocked('readonly_live_media_bytes_changed')
   quality=load_json(folder/('image-'+str(index)+'.quality.json'))
   media_results.append({'role':index,'attachment_id':m['id'],'url':m['url'],'sha256':actual,'live_bytes_match_saved':True,'old_review_hash_matches':quality.get('image_sha256')==actual,'revised_article_visual_approval':False,'status':'requires_fresh_visual_binding_to_revised_article'})
  row['images']=media_results;row['translations']=translations(folder,article)
  row.update(status='readonly_prepublication_blocked',blockers=['revision_specific_overlap_review_required','fresh_visual_identity_and_revised_article_binding_required','four_translations_and_independent_reviews_for_revised_source_required','explicit_same_post_update_authorization_required'])
 except ReadBlocked as exc:row.update(status='readonly_prepublication_blocked',failure=str(exc))
 except Exception:row.update(status='readonly_prepublication_blocked',failure='readonly_unexpected_failure_no_provider_or_secret_text_logged')
 finally:
  row.update(completed_at=utcnow(),get_requests=site.count if site else 0,originals_unchanged=protected(data,out)==before)
  if not row['originals_unchanged']:row.update(status='revision_reconciliation_required',failure='readonly_protected_originals_changed')
  atomic_json(rp,row)
 return row
