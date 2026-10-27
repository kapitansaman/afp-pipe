# Checkpoint recovery without paid replay

## Scope

The general 20-family lifecycle now uses a repository-backed write-ahead run fence, conservative stage/locale uncertainty holds, and a transactional Git checkpoint. This does not activate production, enlarge any budget, start a workflow or create a model/WordPress request. Matrix and white-bean one-shot pilots retain their existing admissions and do not acquire the new general lifecycle fence. Other legacy one-shot operations are not certified by this change.

## Run fence

After healthy capability and read-only inventory/input preparation, but BEFORE launching any workers or publishing, the coordinator compare-and-swaps `data/agri-v2/status/lifecycle-flight.json` on the destination feature branch. One record contains the exact run and up to 20 topic/family identities. Only a confirmed write admits work. Missing credentials, a failed/uncertain write, an unfinished prior run or a replay of the same completed run stop new work. There is no time-based lease expiry or automatic unlock.

A single remote fence is conservative: a completely unknown prior runner outcome stops the next general run until reconciliation. It is not treated as permission to discard topics or reset counters. Initial read-only preparation failures do not reserve this fence.

The fence may close only when every selected topic has an identity-checked, successfully merged worker result, the coordinator report is terminal and has no coordinator-level failure, and all checkpoints plus the closing fence are in ONE pushed Git commit. Worker timeout/crash/missing output does not qualify. Merely returning success in memory or uploading an artifact cannot close the fence.

## Stage and language uncertainty

A previously reserved stage or a transport-unknown/5xx provider outcome is `reconciliation_required`; a new run cannot blindly archive it and submit another model request. The original spent/reserved attempt remains counted. Admission-only deferrals still do not spend an attempt. Known invalid completed content follows existing finite retry budgets; no quality verdict is inferred from attempt count.

Unknown WordPress transport/5xx outcomes also hold the source publish stage or the affected locale publication until actual post/media reconciliation. A lost mutation response is not an automatic re-POST authorization. Interrupted or transport-uncertain language attempts similarly stop automatic retry for that language. Valid sibling languages and source-family handling stay independent. Existing approved, source-bound language outputs may still be recovered without a model call.

## Git checkpoint transaction

`persist-agri-v2.sh` now calls `automation.agri_v2.checkpoint_persistence`. It builds a scoped commit with an isolated Git index; it never resets/stashes the worktree or mutates the ordinary index. Real deletions and newly archived outputs are committed together, avoiding resurrection from an additive copy overlay.

Concurrent agriculture-state changes fail closed; unrelated remote code/files survive. Failed pushes retain local outputs and deletions. A push whose acknowledgement was lost is recognized from the actual remote tree and checkpoint digest; it does not cause work to be replayed. The closing fence and report/artifacts are indivisible at the repository commit boundary. A local checkpoint ref supports a second persistence pass without duplicate commits.

The general parallel workflow retains sanitized outputs/briefs/flight evidence as an always-run artifact with seven-day retention. A hard runner loss may prevent artifact upload and lose uncommitted local output; the remote fence still blocks silent repeat billing. This is safe stopping and evidence-based recovery, NOT a guarantee that a lost provider response or uncommitted output can be reconstructed.

## Reconciliation contract

Do not delete the fence, reset a stage counter, rename a request or start another run to bypass an uncertain outcome. Inspect Git checkpoints, sanitized artifacts, reserved call receipts, model/provider evidence and marker-owned WordPress posts as applicable. Publication recovery must reconcile actual owned posts/media before any mutation. Unknown results require an explicit reviewed decision; no automatic uncertainty-clear or new paid budget is provided here.

## Offline validation

Tests inject crashes after stage reservation, network/5xx uncertainty, missing workers, unconfirmed fence writes, copy/push failure, concurrent state changes and a crash after remote commit but before local acknowledgement. Local bare Git repositories prove deletion/archive consistency, ordinary worktree/index preservation, no-op/idempotent second persistence, remote fence/checkpoint atomicity and recovery of an already pushed result. These are fault simulations, not a live provider-billing or WordPress publication test.
