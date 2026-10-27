# Repair for rejected raw research routing

Observed during live run `40522647019`: many families re-entered `research_validate_saved` because `candidate-raw.json` existed, even though that unchanged raw response explicitly declared insufficient scope or could not retain four source-bound facts. File existence incorrectly selected local salvage as the next useful stage.

The router now performs a read-only deterministic salvage check against the current topic and saved sources:

- Salvageable raw evidence still uses the existing local validation stage; no new extraction request is needed.
- A known semantic rejection routes only to the **original** `research_extract` stage. Its existing attempt limit, same-run exclusion, uncertainty hold and archive rules remain authoritative. No extra stage name or request budget is introduced.
- A foreign topic ID or unreadable evidence blocks rather than authorizing a replacement call.
- Rejected scope, inadequate facts, overlap and independent-review verdicts are never flipped into approval. Normal source, quality, review and publication gates remain mandatory.
- Original exhausted extraction budgets still stop; existing research/exception queues decide whether the family may receive another topic. No counters are reset and no rejection artifacts are deleted.

Source fetching, local saved-evidence validation and existing-content audit finalization do not instantiate a model client or require model capability admission. They retain their normal stage counters and source/validation checks; this is not an authorization to call a model during a provider hold.

Regression tests cover read-only routing, unchanged raw/counters, scientific rejection, malformed/foreign input, archive retention, the last original extraction attempt, exhausted budgets, unresolved reservations and API-free local stages. A new live execution must separately establish whether the remaining original extraction attempts produce valid research; successful routing is not evidence approval.
