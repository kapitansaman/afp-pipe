# Generator foundation: bounded continuation and staged acceptance

## What changes
- The 20 stable family/key allocations remain intact. `advance` now runs only due work within a persistent staged cohort, initially **one family**, not all 20.
- `rollout-plan` is a zero-model, zero-WordPress-write diagnostic: shows the current limit, next stages, waits, exhausted budgets and reconciliation requirements. It does not select a cohort or publish.
- `rollout-verify` is a manual read/verification operation. Promotion is **1 → 3 → 20**, never automatic and never driven by an environment-variable override or an old pilot flag. No schedule is enabled.

## Source retrieval
The model plans targeted searches and judges coverage against actual fetched text. Search snippets and suggested URLs are not evidence. The system persists each confirmed search, the bounded URL set, fetched documents and coverage receipts under the topic's `lifecycle-evidence/real-search/` directory. Progress is bound to the immutable topic, source/candidate hashes and plan.

Across deferrals, the operation admits at most two search rounds, two queries per round, six distinct URLs per round and twelve total. Retries fetch only failed/due URLs; confirmed searches are not repeated. A failed GET waits 15 minutes, then 30 minutes; after three unsuccessful transport attempts for a URL it requires retrieval review. This is **not scientific evidence of absence** and does not reset or spend an invalid model-output attempt. The stored original sources and rejection are never replaced until original coverage/policy gates pass. New fetched text expires under the existing six-hour cache policy; stale bytes cannot silently satisfy a new triage.

Uncertain model/search requests remain fenced by their original lifecycle state. A timestamp cannot release them. Corrupt/mismatched progress stops before network/model work.

## Due work and independent image continuation
`parallel/families/due-work.json` and `image-work.json` show admission reasons. Held, blocked, complete, exhausted, malformed or unconfirmed work does not get a worker/model allowance. Temporary source waits do not reassign the topic or borrow keys. Approved text remains untouched when an image needs correction or review. The existing four-generation/four-review maximum, SHA-bound critique, immutable rejected evidence, single image concurrency and all visual checks remain mandatory. No generated stock image is implicitly approved.

A staged source family retains its assignment through translation handoff until required translations complete. Due translation reviews stay within the existing eight-call coordinator review allowance and the selected cohort; other families' backlog is not published as a side effect of a one-family canary. A verified source does not receive a fresh source-publish budget.

## Promotion acceptance
The entire current cohort must finish source and required translations under the original gates. Acceptance rechecks brief/article/image bindings, current remote ownership and markers, exact raw content hashes recorded at publication, public availability, translation language/source association and uniqueness of each slug across publication states. At least two distinct, merged, non-uncertain checkpoint reports are required per topic to demonstrate continuation; offline tests alone cannot promote a stage. Legacy receipts without an original publication-content hash cannot be silently backfilled into a stage acceptance. Proofs and acceptance-chain hashes are persisted. If evidence is missing, contradictory or unavailable, the limit does not change.

Run sequence: `rollout-plan` → `advance` as due → `rollout-verify` after end-to-end completion → next stage. Existing terminal topics keep their exception/research history; no attempt reset or automatic re-entry is introduced. The phased cohort is sticky during temporary waits; a terminally released topic may be replaced with a logged non-acceptance event.

## Not claimed
A green offline suite does not prove provider/source availability or successful live 20-family publication. This implementation does not erase old failures, replay unknown requests, change accepted articles, weaken scientific/overlap/vision gates, or enable unattended schedules.
