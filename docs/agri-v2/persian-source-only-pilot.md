# One approved Persian source pilot

User-authorized one-source publication test, not production activation. Uses the original WordPress.publish and verify implementations through a narrowly bounded source-only subclass; locale fan-out is disabled only for this operation. Article/evidence, image selection, ownership, live inventory, saved publication validation and public HTTP/title/featured-media checks remain mandatory. No text/image API calls, no health probes, no changes to provider cooldown.

Scope: existing carrot article, retained positively reviewed role 1, one source post, at most one media upload and five total WordPress mutations. Existing failed role 2 is never uploaded. Existing stage attempts, all language queues, source experiment and 20 owner assignments are preserved. Durable one-shot and publish-stage reservations prevent duplicate billed/publication replay. Automatic scheduling stays off.

The waiting language-only workflow 40463036595 was cancelled before its provider deadline to free the single-writer concurrency slot. Its paid-call count remains zero; remaining translations stay in their durable queue.

812 offline tests passed before live publication. This is not a claim of live success; see the operation prepare.json and original WordPress receipt after the run finishes. Full production calibration remains separate.
