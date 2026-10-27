"""Source-bound diagnostics, never evidence rewriting or scientific approval."""
import hashlib,json
from .research import evidence_catalog
from .scoped_research import validate_candidate,validate_fact,EvidenceBlocked

def diagnose(topic,value,docs):
 by_id={e['id']:e for e in evidence_catalog(docs)}
 result={'topic_id':topic['id'],'candidate_sha256':hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'scientific_approval':False,'errors':[]}
 try:validate_candidate(topic,value,docs)
 except EvidenceBlocked as e:result['candidate_error']=e.code
 if not isinstance(value,dict):return result
 result['declared_insufficiency']=value.get('insufficiency_reason')
 for i,f in enumerate(value.get('facts',[]) if isinstance(value.get('facts',[]),list) else []):
  try:validate_fact(f,i,by_id)
  except EvidenceBlocked as e:
   entry=by_id.get(f.get('evidence_id')) if isinstance(f,dict) else None
   result['errors'].append({'fact_index':i,'code':e.code,'rejected_fact':f,'literal_evidence':entry})
 return result
