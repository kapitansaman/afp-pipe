"""Allowlisted diagnostics only: never persist exception text or provider body."""
def failure_details(exc):
 from .client import ImageProviderError,TextProviderError,ModelOutputError,CapabilityError
 from .image_quality import ImageQualityError
 if isinstance(exc,ImageProviderError):kind='image_provider'
 elif isinstance(exc,TextProviderError):kind='text_provider'
 elif isinstance(exc,ModelOutputError):kind='model_output'
 elif isinstance(exc,ImageQualityError):kind='image_quality'
 elif isinstance(exc,CapabilityError):kind='capability_or_protocol'
 elif isinstance(exc,ValueError):kind='validation'
 else:kind='unexpected'
 allowed={'invalid_auth','forbidden','quota_limited','rate_limited','model_unavailable','request_rejected','provider_unavailable','http_error','network_or_timeout','text_empty_or_invalid_content','text_json_invalid','text_model_mismatch','text_content_missing','text_incomplete_response'}
 validation_codes={'Draft must cite approved sources inline':'missing_approved_inline_citation','Unexpected mixed-language output; editorial revision required':'unexpected_mixed_language','Draft must contain 550–2500 meaningful words':'article_length_out_of_bounds','Unapproved numeric token in draft':'unapproved_numeric_claim'}
 validation_codes.update({'Exact owned approved fact references required':'unapproved_fact_reference','Approved source binding required':'unapproved_source_binding','Four to five substantive grounded sections required':'grounded_section_count_invalid','Substantive nonduplicate paragraph length required':'grounded_paragraph_length_or_duplicate','At least eight grounded paragraphs required':'grounded_paragraph_count_invalid','Plain reader-facing prose required':'grounded_plain_prose_required','Structured grounded article required':'grounded_article_schema_invalid','Persian article contains unrelated CJK script':'unexpected_mixed_language','Exactly three grounded FAQs required':'grounded_faq_schema_invalid'})
 validation_codes.update({'Generated title changed canonical intent':'canonical_title_mismatch','Canonical queue title required':'canonical_queue_title_missing','Ambiguous or missing article object':'article_object_ambiguous_or_missing','Article JSON object required':'article_json_object_required','Conflicting article HTML fields':'article_html_fields_conflict','Article HTML required':'article_html_required','Conflicting FAQ fields':'article_faq_fields_conflict','Irreparable article HTML nesting':'article_html_nesting_invalid','Duplicate substantive article paragraph':'article_duplicate_substantive_paragraph','Excerpt cannot be derived from existing prose':'article_excerpt_missing'})
 category=validation_codes.get(str(exc)) if type(exc)is ValueError else getattr(exc,'category',None)
 allowed.update({'source_search_quota_exhausted','source_search_rate_limited','source_search_auth','source_search_unavailable','source_search_response_invalid'})
 allowed.update(validation_codes.values())
 row={'kind':kind,'category':category if category in allowed else 'unspecified'}
 status=getattr(exc,'http_status',None)
 if type(status)is int and 100<=status<=599:row['http_status']=status
 return row
