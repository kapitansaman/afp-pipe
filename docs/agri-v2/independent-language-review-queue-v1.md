# Independent language publication and bounded review queue

## Behavior

- Normal workers give each target language its first bounded translation / fidelity pass. Healthy languages are not sent through the slow retry backlog.
- A failed translation, invalid reviewer response, unavailable provider or exhausted worker pool hands only that language to `new/<topic>/review-queue/<language>.json`. Source article and other approved languages may proceed through the existing single publisher. Research, scientific-evidence, image/vision, ownership and publication-hold gates are unchanged.
- Failed candidates, reviewer feedback, receipts and counters remain on disk. Later attempts repair indexed defects, recheck mechanical constraints and obtain a fresh source-bound fidelity verdict. The reviewer gets one bounded self-correction when its judgment contradicts quoted text/schema or the existing Tajik crop glossary. No code path turns a negative verdict into approval based on age or attempt count.
- Approval binds the current source article, rendered translation and raw segments. Editing either side invalidates approval. Publication still requires existing WordPress language/media/ownership/public-URL checks.
- A locale-local publication error does not block siblings. It has a separate three-failure limit, with 6 / 24 hour backoff, then `publication_needs_attention`. Shared authentication/rate-limit/server failures are not bypassed. Marker/slug/receipt reconciliation remains; no second publisher or extra image uploads were introduced.
- Family owners can be released only after the source is publicly verified, its publication-validation hash matches, and all required language states are durably handed off. This is recorded as a handoff, NOT as a completed four-language family.

## Bounded retry policy

- Three translation/review attempts total per language, including its normal first pass; at most four model-request reservations per attempt, twelve total for this new ledger.
- After a failed first/second attempt: wait at least 6 / 24 hours, respectively. After the third failed attempt, keep the item visible as `needs_attention`; do not automatically approve or buy another attempt.
- An ordinary admitted non-pilot lifecycle run can process at most two due backlog items, serially, with a separate explicitly reported maximum of eight calls. Primary language work remains inside the existing family pool limit. Global cooldowns and cumulative key routing remain active.
- A wait time is eligibility, not a scheduled job. Scheduling remains OFF; retries happen only in a later independently admitted ordinary run. Research-only, matrix-pilot and white-bean-pilot runs do not drain this backlog.
- Default text model remains Flash 2.5. Tajik uses the already-tested Flash 3 client with model-identity verification. No Pro or undiscovered Flash 2 text model is used.
- Old stage/chunk/experimental counters are retained, not reset. This new retry policy is not a renewal of any previous experimental authorization.

## Current Tajik experimental case

The carrot topic `agri-b6f7d6bea16b` is indexed separately under its existing experimental folder. It retains two completed repair rounds and seven calls from the earlier eight-call authorization. The remaining spelling discrepancy (`кштзор` versus supplied `киштзор`, segments 39/43/49) is recorded. It stays `needs_attention`, experimental-only: no third repair, extra call, production import or publication was authorized by adding this entry. Native-language quality approval has not been obtained.

## Visibility

`artifacts/agri-v2/parallel/language-review-queue/index.json` lists topic, language, status, attempts, conservative request counts, next eligibility and state-file path. Approved, waiting and attention-required records remain visible. Per-language history/candidates/receipts live alongside each article rather than inside the immutable 2905 / 593 / 370 title queues.

## Verification

Local unit/regression tests cover source/target binding, reviewer contradictions and feedback, targeted repair, retained old counters, interrupted reservations, bounded backoff, ownership handoff, continuation to source publication after a language failure/provider unavailability, and successful sibling publication without duplicate posts. No live paid generation, images or WordPress publication was executed for this implementation.
