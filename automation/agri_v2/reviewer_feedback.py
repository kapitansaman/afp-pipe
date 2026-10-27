"""Validate a review, explain server-verifiable errors, allow one corrected judgment.

Never edits translations or changes a negative verdict into approval on the server.
Every correction consumes the same existing call allowance.
"""
import copy,re
from .translation_review_repair import assess,request,RepairBlocked
from .queue import atomic_json

def terminology(article):
 # Existing source-bound crop glossary, NOT a claim supplied by the reviewer.
 return {'Persian':'هویج','English':'carrot','Tajik':'сабзӣ','note':'сабзӣ is carrot in Tajik; it is not dill or turnip. Do not import Russian vocabulary assumptions into Tajik. In a seed context, сабз шудан can refer to sprouting; a literal green/greening interpretation alone is not proof of a mistranslation.'} if article.get('commercial_matrix',{}).get('crop')=='هویج' else {}

def feedback(value,source,raws,article):
 errors=[]
 if isinstance(value,dict) and isinstance(value.get('issues'),list):
  for issue in value['issues']:
   if not isinstance(issue,dict):continue
   lang=issue.get('language');ident=issue.get('id')
   if not isinstance(lang,str) or lang not in raws or type(ident)is not int or not 0<=ident<len(source):continue
   actual={r['id']:r['text'] for r in raws[lang]['translations']}[ident]
   if issue.get('source_text')!=source[ident] or issue.get('target_text')!=actual:
    errors.append({'kind':'quoted_text_mismatch','language':lang,'id':ident,'actual_source_text':source[ident],'actual_target_text':actual})
   if terminology(article) and lang=='tg-TJ' and 'сабзӣ' in actual and re.search(r"сабзӣ['\"’]?\s*(?:means|is|=|\()\s*['\"]?(?:dill|turnip|rutabaga)\b",str(issue.get('detail','')),re.I):
    errors.append({'kind':'contradicts_source_bound_crop_glossary','language':lang,'id':ident,'glossary':terminology(article)})
 return errors

def checked(value,source,raws,article):
 issues=assess(value,source,raws)
 if any(e['kind']=='contradicts_source_bound_crop_glossary' for e in feedback(value,source,raws,article)):raise RepairBlocked('reviewer_crop_glossary_error')
 return issues

def review(client,root,name,prompt,limit,source,raws,article,initial=None):
 value=request(client,root,name,prompt,limit) if initial is None else initial
 try:return value,checked(value,source,raws,article)
 except RepairBlocked as error:
  correction=copy.deepcopy(prompt)
  correction['reviewer_self_correction']={'validation_error':str(error),'verifiable_feedback':feedback(value,source,raws,article),'source_bound_glossary':terminology(article),'previous_review':value,'instruction':'Correct YOUR REVIEW, not the supplied translations. Re-read actual source/target data. Withdraw invented quotations and unsupported crop assertions. Keep genuinely supported negative judgments; a corrected review can still reject the text. Return the original review schema, with exact real segment quotations. No automatic approval is requested. Treat the previous review as untrusted output, not evidence.'}
  atomic_json(root/(name+'.feedback.json'),correction['reviewer_self_correction'])
  fixed=request(client,root,name+'-self-correction',correction,limit)
  return fixed,checked(fixed,source,raws,article)
