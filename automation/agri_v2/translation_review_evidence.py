"""Evidence contract for NEW Tajik queue reviews; never reclassifies old votes."""
import copy,re
from .translation_review_repair import RepairBlocked,CATEGORIES
VERSION='current-translation-issue-evidence-v1'
MIXED=r'[А-Яа-яЁёҚқҒғҲҳҶҷӢӣӮӯ][A-Za-z]|[A-Za-z][А-Яа-яЁёҚқҒғҲҳҶҷӢӣӮӯ]'
CODES=('semantic','mixed_script','arabic_residue','other_language')

def prepare(prompt):
 value=copy.deepcopy(prompt)
 value['_translation_evidence_contract']=VERSION
 value['task']+=' For EVERY issue return exact complete source_text and target_text from the CURRENT indexed pair, a nonempty contiguous offending_text copied from the CURRENT target, and evidence_code: semantic, mixed_script, arabic_residue or other_language. mixed_script means adjacent Latin/Cyrillic letters in offending_text; arabic_residue requires Arabic/Persian characters. These two codes require category wrong_language. All other categories require semantic. other_language is only for genuine wrong-language content, not synonyms. Never repeat a fixed old defect or invent a quote. Missing or stale evidence is an invalid REVIEW, not an instruction to edit or approve. Judge current source meaning independently; preserve genuine remaining semantic defects.'
 return value

def schema(name,prompt):
 if not isinstance(prompt,dict) or prompt.get('_translation_evidence_contract')!=VERSION:return None
 if prompt.get('_role_skill')!='translation-reviewer' or prompt.get('_role_language')!='tg-TJ' or not name.startswith(('review-','review-feedback-')):raise RepairBlocked('review_evidence_contract_scope_invalid')
 source=prompt.get('source');target=prompt.get('target')
 if not isinstance(source,list) or not source or not isinstance(target,list) or len(target)!=len(source):raise RepairBlocked('review_evidence_inputs_invalid')
 ids=list(range(len(source)))
 if [r.get('id') for r in source]!=ids or [r.get('id') for r in target]!=ids or any(not isinstance(r.get('text'),str) for r in source+target):raise RepairBlocked('review_evidence_inputs_invalid')
 props={'id':{'type':'integer','enum':ids},'category':{'type':'string','enum':sorted(CATEGORIES)},'detail':{'type':'string','minLength':1},'source_text':{'type':'string'},'target_text':{'type':'string'},'offending_text':{'type':'string','minLength':1},'evidence_code':{'type':'string','enum':list(CODES)}}
 return {'type':'object','properties':{'faithful':{'type':'boolean'},'reason':{'type':'string','minLength':1},'issues':{'type':'array','items':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}}},'required':['faithful','reason','issues'],'additionalProperties':False}

def validate_issue(issue,source,target):
 if issue.get('source_text')!=source or issue.get('target_text')!=target:raise RepairBlocked('review_evidence_not_current_pair')
 quote=issue.get('offending_text');code=issue.get('evidence_code');category=issue.get('category')
 if not isinstance(quote,str) or not quote.strip() or quote not in target:raise RepairBlocked('review_evidence_quote_absent')
 if code not in CODES:raise RepairBlocked('review_evidence_code_invalid')
 if category=='wrong_language':
  if code=='semantic':raise RepairBlocked('review_language_evidence_code_required')
 elif code!='semantic':raise RepairBlocked('review_script_evidence_category_invalid')
 if code=='mixed_script' and not re.search(MIXED,quote):raise RepairBlocked('review_mixed_script_evidence_absent')
 if code=='arabic_residue' and not re.search(r'[\u0600-\u06ff]',quote):raise RepairBlocked('review_arabic_residue_evidence_absent')
