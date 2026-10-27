# Read-only reconciliation of uncertain outcomes

## Commands

Local evidence only (no network):

```bash
python -m automation.agri_v2.reconciliation
```

Explicit authenticated read-only observation on the approved WordPress origin and current GitHub fence:

```bash
python -m automation.agri_v2.reconciliation --wordpress-read-only --remote-fence-read-only
```

The second command requires the existing destination GitHub/WordPress environment credentials. It only invokes GitHub GET and fixed WordPress GET routes; it never invokes a model, `publish`, `verify`, a WordPress mutation, a Git push or a fence PUT. Do not print credentials or include raw provider/WordPress exception text in reports.

Only the diagnostic artifact `artifacts/agri-v2/parallel/recovery/reconciliation/latest.json` is written. The command does not modify stage states, language states, receipts, attempt counters, family assignments, briefs, policy or the lifecycle fence.

## What a dossier proves

- Its local evidence scope includes all selected family files (including raw outputs, receipts and rejected attempts), their briefs, the lifecycle fence, admission and coordinator report. File paths and SHA-256 digests are recorded, not article text, model responses or exception bodies.
- Current in-flight topics and independent held language/stage families are included. Unknown or malformed fence identities fail closed, rather than guessing another family.
- Remote fence observation verifies the returned Git blob hash and exact agreement with the local fence. Missing, foreign, changed or unreadable remote evidence cannot authorize recovery.
- WordPress observation authenticates by GET, searches exact source/locale slugs across public/draft/pending/future/private statuses and checks marker, owner, post ID, language/source binding, and approved public origin. Media are checked by exact slug, owner, source-post association and existing receipt IDs/URLs when available.
- Multiple matches, incomplete collections, missing matches, ownership conflicts, media conflicts and read failures retain holds. A missing match is NOT proof that the request was unbilled/unprocessed and never permits a recreate.
- Finding an owned post is an observation, not content-quality approval or public verification. It does not adopt the post or overwrite any receipt. Author visibility is limited to what that account can read; absence cannot prove no other private draft exists.
- The dossier is hash-bound and detects evidence changes during inspection. `verify_report` checks the local dossier integrity, a 15-minute freshness bound and unchanged local evidence. It does NOT revalidate the live remote state and grants no permission to mutate.

## Review sequence

1. Confirm the current authoritative fence still matches the intended run; do not delete it or expire it by time.
2. Compare the immutable local evidence against provider-side call/billing evidence and retained Actions artifacts. Existence of a raw response is not a domain-validation pass.
3. For publication, inspect the exact owned existing post and media. Re-run the normal deterministic/domain/public checks before any explicitly reviewed adoption. Never resend a POST simply because its response was lost.
4. Keep any outcome whose evidence is missing or conflicting held. A subsequent adoption must be a separate reviewed, counter-preserving state change. This tool intentionally has no automatic unlock/apply/reset switch.

This implements the evidence-collection and decision-dossier part of recovery, not a generic automatic adjudicator for unknown provider billing. Hard-lost output cannot be reconstructed from a missing receipt. No exactly-once provider billing claim is made.
