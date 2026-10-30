"""Read-only native-contract revalidation; never refreshes or promotes evidence."""
import hashlib,tempfile
from pathlib import Path
from .queue import DATA,OUT,load_json
from .pipeline import digest
from . import regional_arabic_v3_validation as ar,regional_isolated_validation as en
from . import regional_schema_recheck as base,language_review_queue as q
from .regional_sources import validate_local_review,response_schema
from .translation_review_repair import request

class CacheOnly:
 def __init__(self):self._repair_cache_only=True
 def text(self,*a,**kw):raise ValueError('retained_evidence_transport_forbidden')

def revalidate(data=DATA,out=OUT):
 folder=out/'new'/base.TOPIC;article=load_json(folder/'article.json');brief=load_json(data/'briefs'/(base.TOPIC+'.json'));result={}
 for lang,mod in [('ar-IQ',ar),('en-US',en)]:
  root=out/'infrastructure-probes'/mod.ID;report=load_json(root/'report.json')
  if report.get('originals_unchanged') is not True or {'language':lang,'status':'regional_evidence_verified_not_promoted'} not in report.get('results',[]):raise ValueError('retained_positive_report_required')
  docs=[load_json(root/'documents'/(str(i)+'.json')) for i in range(3)]
  if any(d.get('sha256')!=hashlib.sha256(d['text'].encode()).hexdigest() for d in docs):raise ValueError('retained_source_hash_changed')
  q.source_checked(load_json(q.path(folder,lang)),article,folder,data)
  if not q.approved(folder,article,lang):raise ValueError('retained_fidelity_changed')
  with tempfile.TemporaryDirectory() as td:
   prompt,_,_=mod.prepare(article,brief,docs,Path(td))[lang]
   if load_json(Path(td)/'contracts'/(lang+'.json'))!=load_json(root/'contracts'/(lang+'.json')):raise ValueError('retained_materialized_contract_changed')
   v=request(CacheOnly(),root/'languages'/lang,'regional-evidence-review-fallback',prompt,1)
   base.validate_wire(v,response_schema('regional-evidence-review-fallback',{k:x for k,x in prompt.items() if k!='_regional_wire_contract'}))
   urls=validate_local_review(v,article,brief,docs,lang)
   if {c['fact_id'] for c in v['fact_checks']}!={f['fact_id'] for f in brief['approved_facts']}:raise ValueError('retained_fact_coverage_changed')
  result[lang]={'source_request_id':mod.ID,'source_report_sha256':digest(report),'original_reviewed_at':report['completed_at'],'documents':docs,'review':v,'source_urls':urls,'freshness_renewed':False}
 return result
