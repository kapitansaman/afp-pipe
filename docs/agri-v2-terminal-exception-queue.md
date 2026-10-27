# Finite terminal exception queue

## Purpose

Twenty family slots advance through the immutable 2,905-title new-topic queue. An exhausted unpublished topic may leave a slot for explicit exception review; it is not completed, approved, deleted, retried, or published by this transition.

## Admission and execution boundary

- The exact `queue-exception-policy.json` enables recording in the general family lifecycle only. It does not enable production, a schedule, model calls or a new owner operation.
- The coordinator records a terminal checkpoint only after a worker result passes identity checks and its files merge successfully. Counters alone are insufficient.
- `allocate(..., allow_deferral=True)` verifies the checkpoint against actual exhausted stage counters, topic/evidence/brief/policy bindings and publication safeguards. Diagnostic allocation does not release slots.
- The original topic, exception record, history event and next slot owner are committed in the same atomic assignments document. A failed assignments write leaves the original ownership in place.
- Each run still processes only its originally selected topics, up to 20. Assigning a replacement at the end never launches an extra worker or enlarges the run's budget.
- Matrix and single-family white-bean pilots do not record general exception checkpoints. Existing research-repair and per-language queues retain their separate contracts.

## Supported terminal outcomes

- Real failed research, overlap batch, text or source-evidence-review stages at their original limit (three attempts).
- Article quality repair/recheck at their original one-attempt limit, including the bound final quality-review hold.
- Legacy research or generation budgets at their original two attempts.
- Both image-role budgets exhausted with no approved usable image. A valid retained image is not quarantined merely because a second role failed.

Provider deferrals, worker crashes/timeouts, available attempts, validated stages, language-local failures, unknown stages and publication attempts do not qualify by themselves. Explicit holds, any WordPress receipt, a saved publication payload or a source-publish stage record prevent release and require reconciliation through the original publication path.

## Durability and review

The per-topic marker is `queue-terminal-checkpoint.json`. Queue membership is `exception_backlog` inside `artifacts/agri-v2/parallel/families/assignments.json`, with counts and original family/history. Artifacts, stage histories and counters are retained byte-for-byte. Every entry denies automatic retry, attempt reset and publication authorization.

A queued topic is rejected by the shared lifecycle stage gate, including the publisher. Catalog changes do not put it back automatically. Explicit review/reentry must reconcile ownership atomically, retain all prior attempts and meet original quality gates; any additional paid budget needs separate authorization. This change does not implement a budget extension or automatic reentry.

A pending marker whose topic/evidence/brief/policy binding changed is not used to release a slot. An already queued topic stays queued until explicitly reconciled.

## Validation scope

Offline tests cover twenty simultaneous terminal topics, mixed successful/terminal traversal of the actual 2,905-title manifest, concurrent allocation, interrupted assignments writes, counter/evidence preservation, stale-marker rejection, publication guards, provider deferrals, language independence, image fallback and bounded quality repair. They simulate outcomes; they are not a live generation throughput, model-quality or WordPress publication test.
