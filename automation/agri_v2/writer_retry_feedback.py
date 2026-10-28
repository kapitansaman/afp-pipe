"""Allowlisted prior rejection diagnostics for a NEW, already-authorized text attempt.
No previous prose is edited, and feedback cannot approve a claim or reset budget.
"""
import hashlib
from .queue import load_json
GUIDANCE={
 'unexpected_mixed_language':'Write the reader-facing body, headings, excerpt and every FAQ entirely in Persian. Do not emit CJK fragments or unrelated language tokens. Approved source URLs and exact scientific Latin names are not a license for mixed-language prose. Recompose supported prose; never hide, encode or mechanically delete rejected characters to bypass validation.',
 'unapproved_numeric_claim':'Only numeric_authority_contract grants numeric authority. Omit unsupported measurements or metadata years; do not spell them out to evade checks or invent conversions.',
 'missing_approved_inline_citation':'Cite the exact approved source URL beside the supported claim. Do not invent a URL or use a bibliography as a replacement for inline evidence.',
 'article_duplicate_substantive_paragraph':'Remove duplication by writing fresh supported prose, not padding. No new agronomic claims.',
 'canonical_title_mismatch':'Title and topic identity belong to the application. Generate only the requested prose fields without rewriting canonical intent.'}

def feedback(folder):
 p=folder/'lifecycle/text/state.json';state=load_json(p) if p.exists() else {};history=state.get('history',[])
 if not isinstance(history,list):history=[]
 codes=[]
 for row in history[-3:]:
  if not isinstance(row,dict) or row.get('status')!='failed':continue
  f=row.get('failure',{});code=f.get('category') if isinstance(f,dict) else None
  if code in GUIDANCE and code not in codes:codes.append(code)
 archives=folder/'lifecycle/text/rejected';hashes=[]
 for n in (1,2,3):
  p=archives/str(n)/'practical-text-candidate.json'
  if p.is_file():hashes.append({'attempt':n,'raw_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 return {'version':1,'rejections':[{'category':code,'correction_contract':GUIDANCE[code]} for code in codes],'archived_candidates':hashes,'scientific_approval':False,'attempt_reset_authorized':False,'validator_bypass_authorized':False,'prior_prose_rewritten':False}
