# Strict regional review wire contract; historical negatives retained

## Observed failure

Regional-only run 40848560201 made two model requests (one per already linguistically approved cohort language), zero new search requests and zero WordPress/image calls. Both outputs returned `applicable:false` but omitted `regional_review_schema_version`; the English response also omitted `rejection_reasons`. The server correctly blocked both with `claim_context_review_required` and retained the second regional-attempt ceiling. Source articles, translations, fidelity proofs and semantic attempt counters were unchanged. These are protocol-invalid negative responses, not approval and not proof that the underlying claims are applicable.

## Fix

The application-owned local and international-fallback regional tasks now explicitly require schema version 2 and source-bound rejection objects in the task. They also request a strict native JSON schema requiring:

- Version 2, all three independent root flags, exact fact-check count and rejection reasons.
- Fact IDs and document IDs from the actual supplied arrays; unsupported findings may honestly use a null document rather than invent evidence.
- For every objection: a known flag, affected fact IDs, claim type, literal current-article quote and substantive reason.
- No extra object fields; finite array counts and the existing 14,000-token, single-attempt request bound.

New request receipts bind the schema hash before transport. Literal source/quote, study geography, numeric support, technical-source quality, regional applicability and rejection-consistency checks remain authoritative on the server. A well-shaped negative stays negative; structure is not factual approval.

## No recovery by relabeling

No version field or objection is fabricated into historical responses. No old receipt/report is rewritten, no regional attempt counter is reset, no unknown Arabic request is replayed, and no new live test is claimed for this fix. Consumed one-shot operations remain consumed. The original regional two-attempt ceiling is exhausted for these two cohort items and requires an explicit separate recovery decision before more paid continuation work.

Current evidence establishes restored text connectivity and English diagnostic fidelity, not a complete multilingual family. Russian invalid output, Tajik negative recheck, unknown Arabic diagnostic outcome, regional review gates and separate publication/schedule authorization remain distinct release concerns. Infrastructure readiness/capacity does not override any of them.

Verification: all 1,558 offline tests pass, including native schema binding, exact source ID/count bounds, honest unsupported/negative structure, cache reuse, unknown non-replay and diagnostic redaction regressions. No article content was manually inspected or edited as part of this fix.
