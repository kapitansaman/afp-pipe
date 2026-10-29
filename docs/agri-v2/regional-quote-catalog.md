# Regional review: select real quote IDs, never model-written quotations

## Evidence of the remaining blocker

Actions 40921432528 returned complete keyed outputs with all five distinct fact IDs in both languages, without the prior output-limit/duplicate-ID failures. Arabic positive output failed literal technical evidence validation; English output failed the source-bound objection check. Neither was approved. The original responses, failures, budgets and counters remain untouched.

## Forward-only catalog contract

The shared production regional prompt now defaults to `regional-quote-catalog-v1`:

1. Deterministic catalogs are built from the exact supplied fetched document texts and the current article's visible HTML text, excerpt, FAQ questions and answers. Each entry has its own ID, original field/document identity, exact start/end offsets and unchanged text. Full original article/facts/source texts remain in the prompt. Catalogs bind article and document hashes.
2. Source passages use overlapping windows up to 1000 characters (minimum 80); article passages up to 600 (minimum 8). Whitespace may be excluded only by adjusting exact boundary offsets, never normalized within a passage. Coverage tests ensure trailing non-whitespace is not dropped. Windows may cut semantic context: the reviewer must inspect the full surrounding original and reject insufficient support, not treat a window as self-sufficient evidence.
3. The native schema accepts `evidence_quote_id` for each unique fact key, and `article_quote_id` for each objection. It does NOT accept model-written `quote`, `document_id` or `article_quote`. IDs are restricted to the exact catalog. An unsupported fact may select null; a supported fact cannot.
4. The adapter copies the selected passage verbatim and derives its document ID from the same entry; the explicit fact key becomes canonical fact_id. Article objections use the selected exact current-article passage. It never searches for a replacement, fuzzy-matches a model quote, fills a missing fact, alters a flag, invents a source, translates a quote, or turns rejection into approval.
5. A catalog snapshot is saved before transport. Receipt binds prompt, native schema, catalog, adapter, raw response and canonical projection hashes. Cached reads require the same intact snapshot. Orphan snapshots, missing/tampered bindings, unknown calls and invalid outputs stop without a new provider request. Raw responses remain unchanged. Duplicate JSON keys are still rejected before parse information loss.
6. Fallback rebuilds the catalog from the actual merged local/international document pack, rather than carrying stale IDs from the first pack.

## What this does not prove or authorize

Literal catalog membership proves provenance, **not scientific relevance, sufficient numeric support, appropriate geography or truth**. All existing independent semantic, literal, numerical, scope/transfer and source-bound negative validators remain. A real but irrelevant passage still must not authorize publication. Empty/insufficient catalogs cannot fabricate evidence or a bound objection.

Existing keyed-v1/schema diagnostic modes are explicitly frozen on their original wire; consumed reports return without replay. Existing request files, unknown outcomes, reservations and counters are not migrated or reset. No new live admission, run ID, token/time/attempt allowance, model/search/source-fetch call, article/translation change, production promotion, publication or schedule is created by this offline change.

Observed stored-source inputs fit the existing 200,000-character transport ceiling in offline sizing checks. Large catalogs fail closed, never silently truncate sources. The 14,000-token/180-second/one-transport-attempt limits remain unchanged. Live provider compatibility and scientific acceptance of this new contract are not yet established.
