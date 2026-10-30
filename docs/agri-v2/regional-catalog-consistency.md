# Regional catalog v2: complete negative decisions and numeric eligibility

## Observed infrastructure failures

Bounded Actions run 40981195958 made exactly two model calls. Catalog v1 produced all five fact keys and literal source selections in each language, but Arabic returned applicable:false with no objection, and English selected a real passage missing required claim numbers. Neither passed. Original reports, reservations, raw responses, admissions, spent counters, articles and translations are immutable.

## Forward-only native contract

`regional-quote-catalog-v2` is the new shared production prompt default; explicit v1 and keyed legacy modes retain their exact original schemas and decoders. It creates no new live mode or admission.

- Every root decision is a strict nested object `{value, objection}`. Nested disjoint `anyOf` branches allow true only with null, false only with an actual current-article objection for the exact flag. Every keyed fact similarly requires null objection when supported, or its own fact_supported objection when unsupported. Each negative has one bound objection; root objections can name multiple affected facts. A single fact cannot borrow another fact's rejection.
- Projection copies each explicit flag, affected fact identity and model reason; it derives no objection, approval, replacement fact, or evidence. Exact catalog article/source passages and original document identity are copied unchanged. The canonical schema and all independent validators are unchanged.
- No article passage means an honest bound negative is impossible: schema construction stops before transport. It does not fabricate a quote or restrict the model to an approval-only response.
- For every fact, application code computes candidate source IDs using **the same necessary numeric-token predicate as validate_local_review**, including its existing deterministic-conversion exemption. A supported:true branch can select only those exact IDs. No candidates means only an honest bound negative is allowed. Unsupported rows may select null; no value substitution, rewriting, fuzzy matching or evidence generation occurs.
- Numeric eligibility is NOT sufficient scientific evidence: it proves neither units, crop/product, semantics, study geography nor transfer applicability. The reviewer must inspect the complete original context and may reject every candidate. Full original sources, article, facts and qualitative-model-knowledge policy remain present. No new quotation or combined passage is fabricated.
- A new immutable catalog snapshot binds exact article/documents, fact hash and full computed selection policy. Native schema, prompt, raw JSON and canonical projection are bound to the receipt. Policy tampering, stale snapshots, duplicate JSON keys, unbound raw outputs and unknown reservations stop without another model call. Invalid responses remain saved, never automatically repaired or turned into positives.

## Limits and verification boundary

One transport attempt, 14,000 output tokens, 180 seconds and the existing 200,000-character ceiling remain unchanged; outer call/attempt budgets are not reset or increased. Local fallback retains its original bounded collection flow and recomputes selection for the actual merged document pack.

This is an offline change only: no new live requests, source fetches/searches, article edits, production promotion, publication or schedule. Offline fixtures test strict decisions, exact numerical predicate, negative honesty, no replay, snapshot binding, native request construction and unchanged source/geographic guards. Native-provider compatibility and scientific acceptance of wire v2 still require a separately authorized bounded live test; offline success is not production readiness.
