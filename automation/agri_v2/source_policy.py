"""Owner-approved source sufficiency, never claim or publication approval.
Single-source exception is restricted to universities already admitted by the
secure source_host validator (.edu). It does not expand trusted domains.
"""
VERSION='university-single-source-v1'
DISCLOSURE='این مقاله بر یک نهاد دانشگاهی تکیه دارد؛ تأیید مستقل چندمنبعی انجام نشده و نتایج فقط در دامنه و شرایط همان شواهد قابل تفسیرند.'
PROMPT=("Source policy university-single-source-v1: one actually fetched, directly relevant university source from an admitted .edu host is sufficient; otherwise two independent institutional publications remain required. Source count never proves relevance or claim support. Do not invent a second source, claim independent corroboration from one publication, or treat mirrored text as independent. Retain all scope, units and geographic limits and explicitly disclose single-university reliance. All substantive and per-fact checks remain mandatory.")

def assess(documents,source_host,independent_count=None):
 hosts={source_host(d['url']) for d in documents}
 universities=sorted(h for h in hosts if h.endswith('.edu'))
 count=len({'.'.join(h.split('.')[-2:]) for h in hosts}) if independent_count is None else independent_count
 return {'version':VERSION,'satisfied':bool(universities) or count>=2,'university_hosts':universities,'independent_institutions':count,'single_university_exception':bool(universities) and count<2,'publication_authorized':False}

def review_flags(review,legacy_flags):
 if 'source_policy_version' not in review:return list(legacy_flags)
 if review['source_policy_version']!=VERSION:raise ValueError('unknown_source_policy_version')
 return [k for k in legacy_flags if k!='independent_sources']+['source_policy_satisfied']

def disclose(limits,assessment):
 return limits+' '+DISCLOSURE if assessment['single_university_exception'] else limits
