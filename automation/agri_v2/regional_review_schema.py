"""Strict regional review transport; shape is not semantic approval."""
def obj(properties):return {'type':'object','additionalProperties':False,'properties':properties,'required':list(properties)}
def schema(facts):
 ids=[f['fact_id'] for f in facts]
 quotes=list(dict.fromkeys(f['evidence_quote'] for f in facts))
 if not ids or any(not isinstance(q,str) or len(q.strip())<80 for q in quotes):raise ValueError('regional_strict_literal_catalog_required')
 boolean={'type':'boolean'};text={'type':'string'}
 check=obj({'fact_id':{'type':'string','enum':ids},'supported':boolean,'document_id':{'type':'string','enum':['s0']},'quote':{'type':'string','enum':quotes},'source_kind':{'type':'string','enum':['technical_publication','research_report','extension_guidance']},'country':text,'scope':text,'international_fallback':boolean,'local_evidence_gap':text,'transfer_limits_retained':boolean})
 issue=obj({'flag':{'type':'string','enum':['applicable','no_unsupported_local_prescription','country_limits_retained','fact_supported']},'fact_ids':{'type':'array','items':{'type':'string','enum':ids}},'claim_type':{'type':'string','enum':['general_principle','source_observation','local_recommendation']},'article_quote':text,'reason':text})
 return obj({'regional_review_schema_version':{'type':'integer','enum':[2]},'rejection_reasons':{'type':'array','items':issue},'applicable':boolean,'no_unsupported_local_prescription':boolean,'country_limits_retained':boolean,'fact_checks':{'type':'array','items':check}})
