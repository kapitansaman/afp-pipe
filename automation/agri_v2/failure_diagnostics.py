"""Allowlisted diagnostics only: never persist exception text or provider body."""
SOURCE_REPAIR_CODES=frozenset(('invalid_model_source_repair_policy', 'source_coverage_cache_binding_invalid', 'source_resume_binding_invalid', 'source_resume_budget_invalid', 'source_resume_document_changed', 'source_coverage_document_binding_changed', 'source_coverage_missing_final_gap', 'source_coverage_missing_reason', 'source_coverage_missing_search_plan', 'source_coverage_queries_invalid', 'source_coverage_receipt_input_changed', 'source_coverage_receipt_invalid', 'source_coverage_requirements_missing', 'source_coverage_requires_actual_text', 'source_coverage_schema', 'source_coverage_unbound', 'source_plan_duplicate_or_fragment', 'source_plan_gap_required', 'source_plan_identity_or_schema', 'source_plan_lead_reason_required', 'source_plan_lead_schema', 'source_plan_leads_invalid', 'source_plan_queries_invalid', 'source_refetch_not_admitted', 'source_repair_archive_collision', 'source_repair_archived_output_conflict', 'source_repair_coordinator_sources_changed', 'source_repair_input_changed', 'source_repair_not_admitted', 'source_repair_original_sources_not_archived', 'source_repair_output_changed_before_merge', 'source_repair_raw_identity_changed', 'web_source_gap_required', 'web_source_plan_schema', 'web_source_queries_invalid', 'web_source_requirement_schema', 'web_source_requirements_required'))

def failure_details(exc):
 from .client import ImageProviderError,TextProviderError,ModelOutputError,CapabilityError
 from .image_quality import ImageQualityError
 from .parallel_pool import PoolDeferred
 from .image_transport import AdmissionBlocked
 from automation.blog_image_queue import ImageQueueBusy
 if isinstance(exc,(PoolDeferred,AdmissionBlocked,ImageQueueBusy)):
  pool_codes={'No eligible capability':'pool_capability_missing','Shared provider cooldown':'shared_provider_cooldown','Bounded model budget consumed':'model_request_budget_deferred','Eligible credentials busy; defer without provider call':'pool_credentials_busy','Temporary source fetch failure; no scientific absence inferred':'source_fetch_temporarily_unavailable'}
  category='shared_image_queue_busy' if isinstance(exc,ImageQueueBusy) else 'image_admission_blocked' if isinstance(exc,AdmissionBlocked) else pool_codes.get(str(exc),'model_capacity_deferred')
  return {'kind':'source_fetch_deferred' if category=='source_fetch_temporarily_unavailable' else 'admission_deferred','category':category}
 if isinstance(exc,ImageProviderError):kind='image_provider'
 elif isinstance(exc,TextProviderError):kind='text_provider'
 elif isinstance(exc,ModelOutputError):kind='model_output'
 elif isinstance(exc,ImageQualityError):kind='image_quality'
 elif isinstance(exc,CapabilityError):kind='capability_or_protocol'
 elif isinstance(exc,ValueError):kind='validation'
 else:kind='unexpected'
 allowed={'invalid_auth','forbidden','quota_limited','rate_limited','model_unavailable','request_rejected','provider_unavailable','http_error','network_or_timeout','text_empty_or_invalid_content','text_json_invalid','text_json_duplicate_keys','text_model_mismatch','text_content_missing','text_incomplete_response','text_output_limit','text_content_filtered'}
 validation_codes={'Draft must cite approved sources inline':'missing_approved_inline_citation','Unexpected mixed-language output; editorial revision required':'unexpected_mixed_language','Draft must contain 550–2500 meaningful words':'article_length_out_of_bounds','Unapproved numeric token in draft':'unapproved_numeric_claim'}
 validation_codes.update({'Unsafe markup in plain text field':'translation_plain_text_markup_invalid','Translation changed comparison operators':'translation_comparison_changed'})
 validation_codes.update({'Exact owned approved fact references required':'unapproved_fact_reference','Approved source binding required':'unapproved_source_binding','Four to five substantive grounded sections required':'grounded_section_count_invalid','Substantive nonduplicate paragraph length required':'grounded_paragraph_length_or_duplicate','At least eight grounded paragraphs required':'grounded_paragraph_count_invalid','Plain reader-facing prose required':'grounded_plain_prose_required','Structured grounded article required':'grounded_article_schema_invalid','Persian article contains unrelated CJK script':'unexpected_mixed_language','Exactly three grounded FAQs required':'grounded_faq_schema_invalid'})
 validation_codes.update({'Generated title changed canonical intent':'canonical_title_mismatch','Canonical queue title required':'canonical_queue_title_missing','Ambiguous or missing article object':'article_object_ambiguous_or_missing','Article JSON object required':'article_json_object_required','Conflicting article HTML fields':'article_html_fields_conflict','Article HTML required':'article_html_required','Conflicting FAQ fields':'article_faq_fields_conflict','Irreparable article HTML nesting':'article_html_nesting_invalid','Duplicate substantive article paragraph':'article_duplicate_substantive_paragraph','Excerpt cannot be derived from existing prose':'article_excerpt_missing','Exactly three reviewed FAQs required':'article_faq_count_invalid','Complete FAQ question and answer required':'article_faq_fields_incomplete','FAQ entries must be objects':'article_faq_entry_schema_invalid'})
 image_codes={'Image rejected by visual QA; preserve bytes, no upload or automatic regeneration':'image_critical_checks_failed','Visual review unavailable or malformed; no upload':'image_review_unavailable','Image rejected under current practical policy; no upload':'image_critical_checks_failed','Image/contract/reference review binding changed':'image_review_binding_changed'}
 category=image_codes.get(str(exc)) if isinstance(exc,ImageQualityError) else validation_codes.get(str(exc)) if type(exc)is ValueError else getattr(exc,'category',None)
 capability_codes={'Known family or explicitly scoped central worker required':'worker_scope_not_admitted','No verified text capability in the assigned credential group':'owned_text_capability_missing'}
 if isinstance(exc,CapabilityError) and str(exc) in capability_codes:category=capability_codes[str(exc)]
 allowed.update(capability_codes.values())
 allowed.update(image_codes.values())
 allowed.update({'source_search_quota_exhausted','source_search_rate_limited','source_search_auth','source_search_unavailable','source_search_response_invalid'})
 from .translation_review_repair import RepairBlocked as TranslationRepairBlocked
 translation_codes={'invalid_translation_row','missing_translation_segments','translation_IDs_unbound','translation_IDs_missing','review_shape_invalid','invalid_language_review','review_quoted_text_not_present','contradictory_language_review','review_repair_call_budget_exhausted','uncertain_repair_request_not_replayed','repair_schema_binding_changed','regional_wire_conversion_incomplete_no_replay','regional_quote_catalog_binding_changed','regional_quote_catalog_unbound'}
 if isinstance(exc,TranslationRepairBlocked) and str(exc) in translation_codes:category=str(exc)
 allowed.update(translation_codes)
 from .model_source_repair import RepairBlocked
 if type(exc) is RepairBlocked and str(exc) in SOURCE_REPAIR_CODES:category=str(exc)
 allowed.update(SOURCE_REPAIR_CODES)
 from .display_units import UnitReviewRequired
 if type(exc) is UnitReviewRequired:category='display_unit_review_required'
 allowed.add('display_unit_review_required')
 allowed.update(validation_codes.values())
 from .regional_sources import RegionalBlocked,DIAGNOSTIC_CODES
 if type(exc) is RegionalBlocked and str(exc) in DIAGNOSTIC_CODES:category=str(exc)
 allowed.update(DIAGNOSTIC_CODES)
 from .claim_policy import PolicyBlocked,CODES as CLAIM_CODES
 if type(exc) is PolicyBlocked and str(exc) in CLAIM_CODES:category=str(exc)
 allowed.update(CLAIM_CODES)
 row={'kind':kind,'category':category if category in allowed else 'unspecified'}
 status=getattr(exc,'http_status',None)
 if type(status)is int and 100<=status<=599:row['http_status']=status
 return row
