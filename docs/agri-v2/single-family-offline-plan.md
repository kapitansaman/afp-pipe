# Single-family preparation — no paid execution

Run `python -m automation.agri_v2.single_family_plan` to print a local, offline proposal. It reads the existing signed stage-one cohort, validated model ownership and saved readiness report; it does not select another topic, write artifacts, access credentials, reserve work or send requests. The report is deliberately **not an executable admission**. Existing dispatch modes, production gates and global health remain unchanged.

## Prepared scope

The current cohort is family-07 / agri-6fc1032cdf42. A proposed separate capability-only execution would use at most:

- Three tiny text probes, once each, on the family's three text slots (25, 26, 27).
- One image probe, once, on its pinned image slot (28).
- One run, one request at a time, no retry, no borrowing or fallback.
- Zero search requests, source fetches, site calls, article/translation edits, publication, promotion or schedule activation.

These are **upper bounds for a future authorized implementation**, not calls made by this planner. Image capability is not visual approval. A failed probe must stop remaining calls; an unknown request must be reconciled, never replayed. Provider cooldown, input/ownership changes and consumed reservations must also stop execution. Separate owner approval is required before any paid call.

## Findings that must not be bypassed

1. Existing text refresh targets 77 slots; image refresh supports batches of 4 or 20, not one selected family. Do not dispatch those modes as a substitute. The dedicated `single-family-capability` executor now provides this bounded diagnostic; it requires its own bound, explicitly approved admission.
2. Global readiness requires fresh capacity across families. A single-family diagnostic must not rewrite global health or be presented as production readiness. No change to that safety contract is made here.
3. The saved selected family's current stage has three spent attempts and is exhausted. Its state is retained; fresh capability does not authorize another attempt or reset it. Resolve completion/continuation through the existing validated workflow with a separately scoped admission, not a counter reset.
4. Isolated Arabic/English positive diagnostics are not production language acceptance. Russian/Tajik and legitimate adoption of diagnostic evidence remain separate work. Do not quote an ungrounded total end-to-end model budget.
5. The source already has a WordPress receipt; do not publish it again as a new pilot. Keep article details with the automated author/reviewer rather than manually changing prose.

## Phases

1. **Now:** offline preparation and tests only (no paid requests).
2. **After explicit budget approval:** use the tested isolated 3-text/1-image capability executor; check changed bindings before transport; use a new create-only admission and preserve all original artifacts. Only then perform one bounded live check.
3. **After reviewing real capability results:** calculate a separate budget for missing language/output acceptance, without replaying unknown requests or exhausted admissions. A ready-to-publish result must be independently validated, not inferred from capacity.
4. **Separately authorized later:** controlled publication and manual 1 → 3 → 20 acceptance. Recurring schedules remain off.

## Integrity

The printed report includes SHA-256 bindings of routing, allocation, saved readiness, staged state and existing article/publication receipt when present. It summarizes lifecycle status/attempt counters with hashes, never copies article prose or raw model replies. These hashes document the inspected snapshot; they do not grant freshness or execution permission. A future executor must revalidate every binding and enforce its own admission and transport limits.
