# Semantic translation review → local repair → recheck

Implemented in `translation_review_repair.py` and wired into the practical
family lifecycle's `translation_fidelity_review` stage. Historical one-shot
verification operations remain unchanged; this commit does not trigger them.

- Reviewer receives the actual indexed Persian/target segments. A rejection
  must quote the exact full source/target segment and identify a semantic
  defect, not a synonym, preferred style, or paragraph length.
- Editor may change only the language/segment IDs identified by that review.
  HTML, numbers, script, crop identity, source and product/scope constraints
  remain checked. Healthy translations and all source text stay unchanged.
- Maximum two repair rounds: one initial review + at most two pairs of
  edit/review calls (five text requests maximum). The existing outer family,
  pilot and provider budgets still apply; no allowance is added or reset.
- Every paid call is reserved once and bound to its prompt/raw response.
  Cached responses are revalidated. A missing response after reservation is
  uncertain and is never automatically billed again. Provider errors retain
  their existing circuit/admission handling, not an editorial retry loop.
- Candidates and originals are retained. Corrections are promoted only after
  an all-four positive fidelity judgment. An interrupted promotion can finish
  by replaying checked cached responses, with no new model calls.
- If unresolved, a source/translation-bound hold blocks **this family** from
  publication. Other family workers continue via the existing coordinator.
  This does not enable partial-language publication: the existing all-four
  publication requirement is retained. A failed language's candidates remain
  available for editorial work; approved outputs are not regenerated.
- Source-article scientific review, images, single-publisher gates, ownership,
  original attempts and schedule OFF are unchanged.

## Verification in this change

688 local regression tests passed, including selective one/two-round repairs,
healthy-output byte preservation, factual/number/HTML rejection, invented
review quote rejection, call caps, cache reuse/tamper detection, provider
failures, interrupted promotion recovery and lifecycle routing/local hold.
These tests use controlled model responses: they are not a live model-quality
or publication test.

An isolated copy of the real saved carrot family was also checked with a zero
model-call allowance. It correctly withheld semantic approval and changed no
original artifacts. No API/image/WordPress calls or scheduling changes were
made. The prior Arabic/Tajik semantic holds are **not** resolved by this test.
The original pilot remains 23/24 calls spent; this change does not silently
replenish its remaining single call.
