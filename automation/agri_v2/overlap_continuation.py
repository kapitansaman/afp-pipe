"""Keep approved overlap evidence immutable; compare fresh non-owned context separately."""
from .queue import load_json,atomic_json

def bound(topic,data,out,wp):
 from .scoped_research import MODE,validate_overlap,content_digest,EvidenceBlocked
 from .pipeline import check_brief,digest
 bp=data/'briefs'/(topic['id']+'.json');folder=out/'new'/topic['id']
 if not bp.exists():return None
 brief=load_json(bp)
 if brief.get('review_mode')!=MODE:return None
 check_brief(topic,brief);bundle=load_json(folder/'lifecycle-evidence/existing-content.json');validate_overlap(topic,bundle,brief['overlap_audit'])
 if content_digest(bundle)!=brief['overlap_audit'].get('existing_content_sha256'):raise EvidenceBlocked('approved_overlap_binding_changed')
 owned=[];rp=folder/'wordpress-receipt.json'
 if rp.exists():
  receipt=load_json(rp)
  if receipt.get('public_verified')is not True or receipt.get('topic_id')!=topic['id']:raise EvidenceBlocked('owned_overlap_receipt_not_verified')
  validation=load_json(folder/'lifecycle-publication-validation.json')
  if validation.get('article_sha256')!=digest(load_json(folder/'article.json')) or validation.get('brief_sha256')!=digest(brief):raise EvidenceBlocked('owned_overlap_source_binding_changed')
  rows=[(None,receipt)]
  from .multilingual import LANGUAGES
  for lang in LANGUAGES:
   p=folder/'translations'/(lang+'.wordpress.json')
   if p.exists() and load_json(p).get('public_verified')is True:rows.append((lang,load_json(p)))
  for lang,r in rows:
   ident=r.get('post_id')
   if type(ident)is not int:raise EvidenceBlocked('owned_overlap_identity_unconfirmed')
   post,_=wp.call('posts/'+str(ident)+'?context=edit');marker='<!-- afp-agri-v2:'+topic['id']+(':'+lang if lang else '')+' -->'
   if post.get('id')!=ident or post.get('status')!='publish' or post.get('author')!=wp.user_id or post.get('link')!=r.get('url') or marker not in post.get('content',{}).get('raw',''):raise EvidenceBlocked('owned_overlap_identity_unconfirmed')
   from .staged_rollout import verify_published_bytes
   verify_published_bytes(post,r)
   if lang and (post.get('afp_language')!=lang or post.get('afp_source_post_id')!=receipt['post_id'] or r.get('source_post_id')!=receipt['post_id']):raise EvidenceBlocked('owned_overlap_identity_unconfirmed')
   if ident in bundle['related_ids']:raise EvidenceBlocked('owned_overlap_id_in_original_review')
   owned.append(ident)
 return {'bundle':bundle,'owned_ids':owned,'brief_sha256':digest(brief)}

def compare(topic,binding,fresh,out,run_id):
 from .scoped_research import EvidenceBlocked,content_digest
 old=binding['bundle']
 def context(b):return {'ids':sorted(b['related_ids']),'documents':sorted((d['id'],d['sha256'],d['text_truncated'])for d in b['documents']),'unavailable':b['unavailable']}
 same=context(old)==context(fresh)
 snapshot={'topic_id':topic['id'],'run_id':str(run_id),'original_overlap_sha256':content_digest(old),'fresh_overlap_sha256':content_digest(fresh),'brief_sha256':binding['brief_sha256'],'verified_owned_ids_excluded':binding['owned_ids'],'non_owned_context_unchanged':same,'fresh_bundle':fresh,'approval_granted':False,'original_evidence_overwritten':False}
 atomic_json(out/'new'/topic['id']/'lifecycle-evidence/overlap-refresh'/(str(run_id)+'.json'),snapshot)
 if not same:raise EvidenceBlocked('approved_overlap_context_changed_requires_review')
 return snapshot
