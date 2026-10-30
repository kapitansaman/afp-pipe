"""Owner-approved new catalog contract check: one AR + one EN, no replay/promotion."""
from .queue import DATA,OUT,load_json
from .pipeline import digest
from .infrastructure_probe import code_hash,protected
from . import regional_schema_recheck as base
from .regional_quote_catalog import VERSION,bound
from .regional_keyed_validation import ID as PRIOR_ID
ID='authorized-catalog-regional-compatibility-v1'
REQUEST='regional-catalog-validation-request.json'

def prior(out):
 value=load_json(out/'infrastructure-probes'/PRIOR_ID/'report.json')
 required={'ar-IQ':{'kind':'validation','category':'regional_literal_technical_evidence_required'},'en-US':{'kind':'validation','category':'claim_context_review_required'}}
 if value.get('request_id')!=PRIOR_ID or value.get('status')!='regional_schema_recheck_blocked' or value.get('model_calls')!=2 or value.get('originals_unchanged') is not True or len(value.get('results',[]))!=2 or {r.get('language'):r.get('failure') for r in value['results']}!=required:raise base.RecheckBlocked('original_keyed_quote_failures_required')
 return value

def manifest(data,out):
 return {k:v for k,v in protected(data,out,ID).items() if k!='data/'+REQUEST}

def expected(data=DATA,out=OUT):
 folder,article,brief,docs=base.selected(data,out)
 from .regional_sources import review_prompt,response_schema
 prompts={lang:review_prompt(article,brief,lang,docs[lang],wire=VERSION) for lang in base.LANGUAGES}
 schemas={lang:response_schema('regional-evidence-review-fallback',prompts[lang]) for lang in base.LANGUAGES}
 catalogs={lang:bound(prompts[lang]) for lang in base.LANGUAGES}
 return {'version':1,'request_id':ID,'authorization':'explicit_owner_approval_one_arabic_one_english_catalog_contract_test','authorization_source':'https://app.notion.com/chat?t=40841579fa0a8078988900a99eb829d4','review_wire_contract':VERSION,'previous_keyed_report_sha256':digest(prior(out)),'topic_id':base.TOPIC,'languages':list(base.LANGUAGES),'code_sha256':code_hash(),'article_sha256':digest(article),'brief_sha256':digest(brief),'documents_sha256':{l:digest(docs[l]) for l in base.LANGUAGES},'response_schema_sha256':{l:digest(schemas[l]) for l in base.LANGUAGES},'quote_catalog_sha256':{l:digest(catalogs[l]) for l in base.LANGUAGES},'protected_sha256':digest(manifest(data,out)),'max_runs':1,'max_model_calls':2,'max_model_calls_per_language':1,'max_search_requests':0,'max_source_fetches':0,'max_site_calls':0,'max_image_calls':0,'article_edits':0,'translation_edits':0,'reset_attempts':False,'publication_authorized':False,'schedule_enabled':False,'promotion_authorized':False}

def validate(req,data=DATA,out=OUT):
 wanted=expected(data,out)
 if not isinstance(req,dict) or set(req)!=set(wanted) or any(type(req[k])is not type(v) or req[k]!=v for k,v in wanted.items()):raise base.RecheckBlocked('catalog_validation_binding_changed')
 return base.selected(data,out)

def run(env,data=DATA,out=OUT,client_factory=None,reserve_fn=None):
 return base.execute(env,data,out,client_factory,reserve_fn,ID,REQUEST,validate,manifest,'regional-catalog-validation',wire_contract=VERSION)
