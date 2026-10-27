# Stable key ownership for twenty families

## Allocation

`data/agri-v2/family-key-allocation.json` is the tracked, revisioned ownership map. It partitions all 97 destination **slot names** into twenty disjoint four-slot family groups and one seventeen-slot central group. It contains no secret values or fingerprints of secrets.

Initial map:

| Family | Secret slot numbers |
| --- | --- |
| family-01 | 1–4 |
| family-02 | 5–8 |
| family-03 | 9–12 |
| family-04 | 13–16 |
| family-05 | 17–20 |
| family-06 | 21–24 |
| family-07 | 25–28 |
| family-08 | 29–32 |
| family-09 | 33–36 |
| family-10 | 37–40 |
| family-11 | 41–44 |
| family-12 | 45–48 |
| family-13 | 49–52 |
| family-14 | 53–56 |
| family-15 | 57–60 |
| family-16 | 61–64 |
| family-17 | 65–68 |
| family-18 | 69–72 |
| family-19 | 73–76 |
| family-20 | 77–80 |
| Central / reserve | 81–97 |

Slot 1 is `AGNES_API_KEY` in the process environment; slots 2–97 are `AGNES_API_KEY2` through `AGNES_API_KEY97`. These refer to the existing workflow's `AGNES_API_KEY_1` through `AGNES_API_KEY_97` secrets; this change does not read, rotate or replace secret values.

The family ID owns its group across topic changes, checkpoints and executions. It is not derived from queue position or a random/circular global cursor. Within its own verified group, the existing process-safe pool deterministically chooses the least-used free slot, then slot ordinal. Durable usage counts are preserved; no immediate retry/failover is added.

## Central scope, not family overflow

The seventeen central slots are reserved **from production family ownership**. Existing independent language-backlog work and explicitly admitted non-family diagnostics use this fixed central group. This preserves those workflows without letting them consume any family's four keys. They retain their own admission/budget/health requirements.

A family never automatically borrows central slots or another family's slots. A missing/disabled/busy/unverified family group cannot fall through to a globally healthy key. Central keys can be reassigned to a family only through a separately reviewed revision of the tracked disjoint map; no error handler, timer, failover or automatic promotion changes ownership. This map itself creates no new model budget or operation admission.

## Enforcement

- The required-policy flag rejects a missing allocation map instead of silently reverting to a global pool.
- The map must have exactly twenty recognized family IDs, four slots each, seventeen central slots, no duplicates/unknown slots and all 97 slots represented once. Unknown worker identities fail closed.
- Before subprocess launch, in-memory comparison rejects duplicate configured secret values across slots. The worker environment is stripped of every AGNES key outside its owned group. WordPress secrets remain stripped as before.
- The parallel client independently intersects the assigned group with the fresh health report for each capability (text/image). It never interprets text success as image proof. Its request boundary rejects a foreign candidate before a lease or provider call.
- The assignment hash and slot names are attached to family context and runtime proof, not secret values. A new topic in the same family keeps the same key group.
- A missing assigned capability returns a safe `capability_required` worker result with zero new stage attempts, rather than falsely reporting a successful generation or forcing an unknown crashed-worker fence.
- Shared cooldown, billing/quota holds, total/per-worker call budgets, maximum twenty text leases and single-flight images are unchanged. Separate API keys do not prove separate provider accounts/quotas, and are never used to evade provider limits.

## Readiness

A structural map is not a capability audit. Readiness now checks fresh text availability and **actual fresh image proof inside every family's own group**, not just a global count or one global image key. The initial numerical partition does not claim these capabilities have been demonstrated for all twenty groups. Fresh evidence may show that an explicit reviewed repartition is needed before full production.

No paid audit, generation, image request, WordPress write, schedule change, production activation or actual topic reassignment is part of this patch. Existing global configuration gates stay intact.
