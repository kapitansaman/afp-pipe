# Separate text and image roles, with real capability renewal

The immutable 20 x 4 family partition and central slots 81–97 are unchanged. `family-model-routing.json` assigns the first three owned slots to text/review and the fourth to image generation: image slots 4, 8, 12, …, 80. There is no cross-family borrowing, automatic promotion or image-key error failover. The image role always uses the configured `agnes-image-2.5-flash` image model at `/images/generations`; text/review uses chat completions, never an image-generation request with the text model.

## Manual renewal modes

The existing parallel Actions workflow now provides:

- `health-refresh`: at most 77 tiny text checks (60 assigned text slots plus 17 central slots), two in flight. Image-only slots are not tested by the text model. Text success grants zero image capability. A fresh role-bound text report is reused without changing its timestamp.
- `image-refresh`: at most four independently assigned image slots per run, one request at a time through the existing repository-wide image lease and shared provider guards. It does not require text success for that key. Each subsequent manual batch skips fresh proven slots and all already-attempted daily slots.

A single create-only daily remote text reservation and per-slot daily image reservations are persisted before provider calls. Existing legacy audit IDs are neither deleted nor reused. Local receipts preserve outcomes; a lost checkpoint with an existing remote reservation fails closed for reconciliation rather than replaying a request. These are manually admitted diagnostic requests, not reset article-stage attempts. No unattended health schedule is enabled.

Authentication/quota/rate rejection affects only the account/slot tested; the same family is not moved to another image key. Transport uncertainty/service failures stop further scheduling for that capability and retain a shared hold. Existing shared image admission and per-account holds are never cleared by renewal.

## Proof and readiness

Image proof requires actual new reference-conditioned image bytes, valid landscape output, the configured image model, the assigned family/slot, allocation/routing binding and its own fresh timestamp. It is not inferred from text, a model catalog or an eligible-slot declaration. Passing this check is NOT visual approval for a publishable article image.

The production client separately intersects health with each role, rejects wrong endpoint/model calls before leasing a key, and requires role-bound actual image proof. Readiness checks the designated image slot for every family, not any healthy slot in the broader four-slot group. Workers still use the existing topic isolation, single publisher, source/quality/overlap gates and preserved original attempt counters.

These changes do not release `research_only_for_scoped_rollout`, enable the scheduler, reopen exhausted articles, or assert an accepted end-to-end pilot. Those remain independent gates. A failed/partial live capability report must be disclosed as such; offline mocks are not production evidence.
