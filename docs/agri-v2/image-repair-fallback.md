# Three corrective image rounds and one-approved-image fallback

Policy: prefer two distinct images, require at least one positively reviewed image. Each slot has its initial candidate plus at most three corrective generations (four total), each independently reviewed. Existing generation/review counters and rejected bytes survive. Three earlier generations leave ONE generation, not three new ones. Unknown/malformed reviews never become approval. Admission deferrals do not consume a defective-output attempt. Provider backpressure remains shared and does not authorize key hopping.

The active family lifecycle uses `image_workflow.advance`: retain healthy images; feed exact SHA-bound rejected-candidate feedback into only the failed slot; archive each replaced candidate and verdict. Same-run retries are allowed only for image/vision stages. Every call still consumes the existing shared family/model budget; work checkpoints if it cannot finish in one invocation. Legacy exhausted generation budgets still block advancement.

After all correction opportunities are exhausted for a missing/rejected slot, one approved role can be selected. Role 2 alone can be featured. Selection is bound to article, image and exact review; failed images remain in the archive and are not uploaded. Identical bytes cannot fill two slots. Zero approved images leave only that family waiting. No automatic approval by score or attempt count.

The original single WordPress publisher uploads only selected roles, verifies the selected featured image and any actual inline image, and persists the layout. A one-image article has a featured image without a duplicate inline copy. All four languages reuse precisely the selected source media with zero extra uploads. Published media selections cannot silently change. Article, scientific, translation, ownership and live public-verification gates remain intact.

The nonpublishing live test `ops-image-three-corrections-single-fallback-test-v1` is pinned to the current carrot source and its three-attempt image-2 checkpoint. It permits at most one remaining image generation, one visual review and four bounded language attempts: at most 17 text calls and one image call total. WordPress access is GET/OPTIONS only; publication, uploads, scheduling and production activation are forbidden. It records actual image/translation readiness, not a claim that the unperformed 20-family calibration or live publication has succeeded.

## Recorded verification result

Run `40461248497` completed the image fallback check, but NOT the full generator test: the fourth total role-2 candidate was generated and its visual review timed out. Only already-approved role 1 was selected; no unapproved image was accepted. There was one image call and one text/visual call; all four languages were queued without any new translation call. WordPress mutations and publications were zero; production and schedule stayed off.

786 offline unit tests passed using `python tests/agri_v2/run_offline.py`. The runner isolates the live circuit store only; it never clears or shortens the real provider hold. Generic discovery during the real cooldown had 10 failures and 1 error caused by the live hold, so it is not reported as passing. Circuit-specific tests retain their explicit fixtures.

Provider-only language deferral now preserves attempts/calls and follows the provider deadline instead of creating a new 6/24-hour editorial delay. Existing later editorial backoff remains intact. The four test queues were reconciled to the recorded provider deadline with their former dates retained in history. Imported experimental rows are hidden from the dashboard only when a canonical row with the same source hash exists; original experiment files are untouched.

Full language verification, real publishing and 20-family timing calibration remain unperformed. This result is not permission to activate production.

## Language-only bounded continuation

`ops-image-fallback-language-only-after-cooldown-v1` may wait at most 3600 seconds for the existing provider deadline, without clearing it. Then it may use the remaining 16 text calls from the original 17-text-call test budget (one was spent on visual review), one attempt per language, no image calls, no uploads and no publishing. Existing language attempts and per-item caps remain binding, including Tajik's already spent 2 attempts / 7 calls. Fourth-image generation cannot replay. Existing images, source, original experiment, prior test report and family assignments are protected.

A mixed `text_or_image` circuit was incorrectly omitted by one text-only cooldown helper; it now blocks that route as well. The owner workflow uses the isolated offline runner instead of inheriting the live circuit in unit tests. Its bounded job timeout allows the existing provider wait plus the language-only check; it is not a recurring schedule. 801 offline tests pass; this is not a live-language success claim.
