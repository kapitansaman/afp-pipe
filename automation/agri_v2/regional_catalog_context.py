"""Forward-only v3: explicit institution metadata + necessary transfer fields.
Never infer trial geography, fill a model answer, or repair historical receipts.
"""
import copy
from urllib.parse import urlsplit
from . import regional_catalog_consistency as previous
from .pipeline import digest
VERSION='regional-quote-catalog-v3'

def fail():
 from .regional_sources import RegionalBlocked
 raise RegionalBlocked('regional_catalog_context_invalid')

def context(prompt):
 from .regional_sources import classification,accepted,profile,documents_for
 lang=prompt.get('regional_profile',{}).get('language')
 if prompt.get('regional_profile')!=profile(lang):fail()
 docs=prompt.get('documents')
 if not isinstance(docs,list) or documents_for(docs,lang,True)!=docs:fail()
 rows=[]
 for doc in docs:
  country,_=classification(urlsplit(doc['url']).hostname)
  # This is ONLY the policy's institution-host label. It is deliberately NOT
  # called study/trial country, nor evidence that a rate transfers locally.
  rows.append({'document_id':doc['id'],'source_institution_country':country,'technical_local_source':accepted(doc['url'],lang)})
 return {'version':VERSION,'documents_sha256':digest(docs),'profile':profile(lang),'documents':rows,'country_semantics':'institution_host_metadata_only_not_trial_geography_or_local_applicability'}

def bound(prompt):
 old=previous.bound(prompt);ctx=context(prompt)
 if prompt.get('source_context_policy')!=ctx:fail()
 return {'version':VERSION,'consistency':old,'source_context_policy':ctx}

def schema(keyed,prompt):
 snapshot=bound(prompt);value=previous.schema(keyed,prompt)
 contexts={d['document_id']:d for d in snapshot['source_context_policy']['documents']}
 passages={p['id']:p for p in snapshot['consistency']['quote_catalog']['source_passages']}
 checks=value['properties']['fact_checks']['properties']
 for ident,item in checks.items():
  branches=[]
  for branch in item['anyOf']:
   fields=branch['properties']
   if fields['supported']['enum']==[False]:branches.append(branch);continue
   groups={}
   for ref in fields['evidence_quote_id']['enum']:
    ctx=contexts[passages[ref]['document_id']]
    key=(ctx['source_institution_country'],ctx['technical_local_source'])
    groups.setdefault(key,[]).append(ref)
   for (country,local),refs in groups.items():
    row=copy.deepcopy(branch);p=row['properties'];p['evidence_quote_id']={'type':'string','enum':refs}
    # Model MUST explicitly supply the matching label, never copied in later.
    # Unknown institutional classification remains unknown/nullable; no guess.
    p['country']={'type':'string','enum':[country]} if country is not None else {'type':['string','null']}
    p['source_kind']['enum']=['technical_publication','research_report','extension_guidance']
    if not local:
     p['international_fallback']={'type':'boolean','enum':[True]}
     p['local_evidence_gap']=dict(p['local_evidence_gap'],minLength=30)
     p['transfer_limits_retained']={'type':'boolean','enum':[True]}
    branches.append(row)
  if not branches:fail()
  item['anyOf']=branches
 return value

def canonical(raw,contract,snapshot):
 # All raw labels/gaps/flags are explicitly validated, then copied unchanged.
 # This decoder NEVER reads a URL to fill country or invents missing prose.
 if not isinstance(snapshot,dict) or snapshot.get('version')!=VERSION:fail()
 previous.validate(raw,contract)
 return previous.canonical(raw,contract,snapshot['consistency'])

def prompt(base):
 value=previous.prompt(base);value['_regional_wire_contract']=VERSION
 value['source_context_policy']=context(value)
 value['task']+=' COUNTRY METADATA CONTRACT: country is the exact source INSTITUTION host-country label from source_context_policy for the document selected by evidence_quote_id. It is NOT trial geography, the target audience country, or scientific/local applicability. Explicitly return the matching known label; do not output null for a known institution label. For unknown institutional labels do not guess from audience language. Keep actual trial geography, uncertainty, cultivar, soil, water, climate and system limits in scope and judge them independently from institution metadata. A foreign supported observation requires an explicit meaningful local_evidence_gap of 30..480 characters, international_fallback:true and transfer_limits_retained:true; scope must be meaningful 30..480 characters. Do not pad, fabricate, or approve merely to satisfy metadata. If source evidence or transfer limits are inadequate, return an honest article-bound negative. The negative branch remains available regardless of known country. These necessary schema constraints cannot establish scientific truth or replace the independent server validators.'
 return value
