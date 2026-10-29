"""Claim-level research contract. Admission is not truth; old approvals are not upgraded."""
VERSION = 'claim-context-research-v1'
CONTEXT_FIELDS = ('publisher', 'publication_date', 'species', 'cultivar', 'geography',
                  'climate', 'season', 'soil', 'water_quality', 'irrigation_method', 'trial_conditions')
CLAIM_TYPES = ('general_principle', 'source_observation')
CODES = frozenset(('claim_policy_version_required', 'claim_context_schema_required',
    'claim_context_not_source_bound', 'claim_type_required', 'claim_conflict_schema_required',
    'claim_conflict_cause_not_source_bound', 'claim_context_review_required'))
class PolicyBlocked(ValueError):
    pass

COMMON = ("Evaluate publisher credibility, exact claim support, and applicability SEPARATELY. "
    "Admit government national/provincial/municipal agencies, official extension and research centres, "
    "universities and specialist scientific publications only within their actual expertise and supported scope. "
    "A government domain, university name or source count is NOT proof of a claim. Municipal water restrictions "
    "can establish that dated local restriction, not automatically crop water requirements. Official news is "
    "dated context, not agronomic evidence. Commercial seed/input specifications require disclosed commercial "
    "interest and independent support for material agronomic benefits; they do not bypass the secure host registry. "
    "Search relevant local evidence first; a precise documented local gap may be filled by international evidence "
    "with original crop, cultivar, climate, soil, water, season and method limits. Never infer study geography "
    "from publisher country or language. Missing conditions stay unknown, never guessed. Distinguish a general "
    "principle, a bounded source observation, and a local operational recommendation. A foreign observation "
    "does not need local replication merely to be reported as foreign; a local instruction DOES need matching "
    "evidence. Do not average incompatible studies or invent why results differ. Check species/cultivar, "
    "climate/season, soil/water, irrigation, measurement basis, outcome and units; explain a cause only when "
    "the source supports it. Otherwise state that the cause is unresolved or the studies are not comparable. "
    "In public prose distinguish a direct institutional finding from an explicitly limited editorial synthesis; "
    "do not attribute synthesis to the source or mention AI/models. Audit full article, excerpt, tables and FAQs. "
    "Negative findings remain negative; no silent reapproval or invented evidence.")

def extraction_contract():
    return {'version': VERSION, 'required_root_fields': ['research_policy_version', 'conflicts'],
        'research_policy_version': VERSION,
        'per_fact_required': {'claim_type': list(CLAIM_TYPES),
            'study_context': {k: {'value': 'literal source substring or null',
                'quote': 'literal substring from THIS fact evidence passage containing value, or null'} for k in CONTEXT_FIELDS}},
        'conflicts': 'Array, empty only if no conflicting results. Each row: fact_indices:[at least two distinct zero-based indices from facts], status:explained|unresolved|not_comparable, reason:explicit explanation >=30 chars, cause_quote:literal causal source passage or null. explained requires a cause_quote in one cited fact passage; otherwise null. Never invent causal explanations.',
        'rules': COMMON + ' Return EVERY study_context key; absent/unreported fields must be {value:null,quote:null}. '
            'Context metadata is not additional approved prose or numerical authority. Preserve the existing fact/numeric schema.'}

def validate_candidate(candidate, facts):
    if 'research_policy_version' not in candidate:
        if any('research_policy_version' in f for f in facts):
            raise PolicyBlocked('claim_policy_version_required')
        return
    if candidate['research_policy_version'] != VERSION:
        raise PolicyBlocked('claim_policy_version_required')
    for f in facts:
        if f.get('claim_type') not in CLAIM_TYPES or (f.get('kind') == 'source_observation' and f.get('claim_type') != 'source_observation'):
            raise PolicyBlocked('claim_type_required')
        context = f.get('study_context')
        if not isinstance(context, dict) or set(context) != set(CONTEXT_FIELDS):
            raise PolicyBlocked('claim_context_schema_required')
        for item in context.values():
            if not isinstance(item, dict) or set(item) != {'value', 'quote'}:
                raise PolicyBlocked('claim_context_schema_required')
            value, quote = item['value'], item['quote']
            if value is None and quote is None:
                continue
            if not isinstance(value, str) or not value.strip() or not isinstance(quote, str) or not quote.strip():
                raise PolicyBlocked('claim_context_schema_required')
            if value not in quote or quote not in f['evidence_quote']:
                raise PolicyBlocked('claim_context_not_source_bound')
    conflicts = candidate.get('conflicts')
    if not isinstance(conflicts, list):
        raise PolicyBlocked('claim_conflict_schema_required')
    for row in conflicts:
        if not isinstance(row, dict):
            raise PolicyBlocked('claim_conflict_schema_required')
        ids = row.get('fact_indices'); status = row.get('status'); reason = row.get('reason')
        if (not isinstance(ids, list) or len(ids) < 2 or any(type(i) is not int or not 0 <= i < len(facts) for i in ids)
                or len(set(ids)) != len(ids) or status not in {'explained', 'unresolved', 'not_comparable'}
                or not isinstance(reason, str) or len(reason.strip()) < 30):
            raise PolicyBlocked('claim_conflict_schema_required')
        quote = row.get('cause_quote')
        if status == 'explained':
            if not isinstance(quote, str) or len(quote.strip()) < 30 or not any(quote in facts[i]['evidence_quote'] for i in ids):
                raise PolicyBlocked('claim_conflict_cause_not_source_bound')
        elif quote is not None:
            raise PolicyBlocked('claim_conflict_cause_not_source_bound')

def review_contract(candidate, facts):
    if candidate.get('research_policy_version') != VERSION:
        return None
    return {'version': VERSION, 'required_root_fields': ['research_policy_version', 'context_checks', 'conflicts_reviewed'],
        'research_policy_version': VERSION, 'conflicts_reviewed': 'honest boolean; true only after checking all differences, including omitted conflicts',
        'context_checks': [{'fact_id': f['fact_id'], 'claim_type': f['claim_type'],
            'context_supported': 'boolean', 'publisher_expertise_supported': 'boolean',
            'reason': 'specific source-bound reasoning >=30 characters'} for f in facts if f.get('kind') != 'deterministic_conversion'],
        'conflicts': candidate['conflicts'], 'rules': COMMON + ' Literal context binding is mechanical, not semantic approval. '
            'Reject invented or misclassified conditions even when copied words occur in the passage. '
            'For every false global flag retain the detailed rejection_reasons contract and exact fact IDs.'}

def validate_review(review, facts):
    current = [f for f in facts if f.get('research_policy_version') == VERSION]
    if not current:
        return
    if (review.get('research_policy_version') != VERSION or review.get('conflicts_reviewed') is not True):
        raise PolicyBlocked('claim_context_review_required')
    rows = review.get('context_checks')
    by_id = {f['fact_id']: f for f in current}
    if (not isinstance(rows, list) or len(rows) != len(by_id) or any(not isinstance(c, dict) for c in rows)
            or {c.get('fact_id') for c in rows} != set(by_id)):
        raise PolicyBlocked('claim_context_review_required')
    for c in rows:
        if (c.get('claim_type') != by_id[c['fact_id']]['claim_type'] or c.get('context_supported') is not True
                or c.get('publisher_expertise_supported') is not True or not isinstance(c.get('reason'), str)
                or len(c['reason'].strip()) < 30):
            raise PolicyBlocked('claim_context_review_required')


def regional_contract():
    return {'version': VERSION, 'required_root_fields': ['regional_review_schema_version', 'rejection_reasons'],
        'regional_review_schema_version': 2,
        'rejection_reasons': 'Array, empty only with a positive verdict. Every negative root flag or fact needs a row: '
            '{flag:applicable|no_unsupported_local_prescription|country_limits_retained|fact_supported, '
            'fact_ids:[affected actual IDs], claim_type:general_principle|source_observation|local_recommendation, '
            'article_quote:exact contiguous text from CURRENT article HTML visible text, excerpt or FAQ, '
            'reason:specific evidence-based defect >=30 chars}. Never quote a brief as if it were the article. '
            'A negative without a bound objection stays blocked, never becomes approval.', 'rules': COMMON}


def validate_regional_objections(value, article, facts):
    # Legacy saved reviews retain old rules; every newly requested review carries schema 2.
    if not isinstance(value, dict) or 'regional_review_schema_version' not in value:
        return
    from .quality_index import article_text
    if value['regional_review_schema_version'] != 2:
        raise PolicyBlocked('claim_context_review_required')
    ids = {f['fact_id'] for f in facts}; rows = value.get('rejection_reasons')
    negatives = {k for k in ('applicable', 'no_unsupported_local_prescription', 'country_limits_retained') if value.get(k) is False}
    negative_facts = {c.get('fact_id') for c in value.get('fact_checks', []) if isinstance(c, dict) and c.get('supported') is False}
    required = negatives | ({'fact_supported'} if negative_facts else set())
    if not isinstance(rows, list):
        raise PolicyBlocked('claim_context_review_required')
    for row in rows:
        if (not isinstance(row, dict) or row.get('flag') not in required or not isinstance(row.get('fact_ids'), list)
                or not row['fact_ids'] or any(not isinstance(i, str) or i not in ids for i in row['fact_ids'])
                or row.get('claim_type') not in (*CLAIM_TYPES, 'local_recommendation')
                or not isinstance(row.get('article_quote'), str) or len(row['article_quote']) < 8
                or row['article_quote'] not in article_text(article)
                or not isinstance(row.get('reason'), str) or len(row['reason'].strip()) < 30):
            raise PolicyBlocked('claim_context_review_required')
    if {row['flag'] for row in rows} != required:
        raise PolicyBlocked('claim_context_review_required')
    if negative_facts - {i for row in rows if row['flag'] == 'fact_supported' for i in row['fact_ids']}:
        raise PolicyBlocked('claim_context_review_required')
