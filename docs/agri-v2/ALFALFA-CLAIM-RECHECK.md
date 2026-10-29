# Alfalfa claim-policy recheck

One owner-authorized manual run, `alfalfa-claim-policy-recheck-v1`, on the production feature branch. This is not activation of production or authorization to replace a WordPress post.

## Scope

Reuses the exact corrected proposal and fetched documents from the previous regional revision. It does not treat the previous factual or quality approvals as current approval. The old eight calls, raw outputs, article, receipt, images and translation artifacts remain byte-preserved.

At most four new **text** calls:
1. Annotate each exact proposed claim with its source-bound context and claim class. This cannot rewrite claim prose, evidence IDs or source URLs, and is not scientific approval.
2. Independent scientific review under the new claim-context contract, with specific source-bound objections.
3. Independent audit of the normalized proposal article, including excerpt, tables, FAQ and commercial claims.
4. Independent regional applicability audit, with the new exact-current-article quotation requirement.

The run stops on a negative, missing field, uncertain outcome, stale health, provider cooldown or changed input. It does not repair an article or keep calling to obtain approval. Missing context is unknown, not fabricated. No new search or writer call, no model-driven unit conversions, no live WordPress mutation, no image regeneration, and no translation/publication are allowed.

## Safety

- Exact code and input bindings; all eight historical receipts must have confirmed matching raw output.
- Existing publication identity and original source bindings are verified from the saved owned-post receipt. This is not a fresh authenticated check of the live page.
- A create-only **remote** reservation precedes model calls. A rerun cannot replay paid calls even if the local report/checkpoint is lost.
- Local report reservation fences interrupted work; unknown outcomes remain unknown.
- A shared pool enforces four calls, one concurrent text request, existing routing counts, cooldowns and capability constraints. No routing counter or old family retry budget is reset.
- Search, FTP and all WordPress environment variables are stripped from the review client.
- Protected original files are hashed before/after; drift requires reconciliation.
- Results go under `artifacts/agri-v2/claim-policy-rechecks/alfalfa-claim-policy-recheck-v1/`. Existing sanitized checkpoint persistence saves them; no production flags are changed.

The manual `claim-policy-recheck` mode is added to the existing GitHub workflow. A positive result is only `claim_recheck_ready_for_publication_review`. Same-post update authorization, fresh authenticated identity/byte verification, overlap scope, existing-image review, new source-bound translation reviews and public verification still remain.

Validation: 1,409 tests passed with external network blocked (`python tests/agri_v2/run_offline.py`), including 13 new recheck safety tests. `git diff --check` passed.

## Separate three-call continuation

The first run stopped before scientific review. Its historical generic error cannot distinguish output exhaustion from filtering. New responses distinguish `text_output_limit` and `text_content_filtered`; both remain hard stops, never approval or automatic retries. No provider body or secrets are logged.

Owner-authorized mode `claim-policy-continuation`, ID `alfalfa-claim-policy-continuation-v1`, permits at most three independent reviews with a new create-only remote reservation. All eight earlier receipts and the first incomplete run remain byte-preserved; its request is never replayed. Exact predecessor request/report/receipt, provisional context seed, original inputs and current code are hash-bound. Late predecessor output blocks continuation.

The redundant annotation model call is removed. The seed is manual, provisional metadata, NOT approval. Four guide-level general principles are not classified as experimental observations. Only literal species labels within exact evidence passages are populated; other context is unknown within those bounded passages, not asserted absent from the entire publication. Publisher location is not study geography. No prose, IDs, sources, dates, rates or causes are rewritten or invented. Independent scientific review must still reject misclassification or inadequate scope.

Remaining calls: independent source/context review, full article review, regional review. Each has one attempt, a bounded 20,000-token output allowance and 180-second timeout. Regional review receives the actual cited cached document, excluding six irrelevant cached documents. No search, writing, images, translation, live site access or publication. Pool limits, capability/cooldown/routing gates and original-byte checks remain. Negative or incomplete reviews stop, without repair loops.

Continuation validation: 1,420 offline tests passed with external network blocked, including ten continuation safety tests and one additional diagnostic-redaction test. `git diff --check` passed.
