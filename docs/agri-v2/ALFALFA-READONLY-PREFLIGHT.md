# Alfalfa read-only prepublication audit

Owner requested beginning the next prepublication gate, not publication. Manual mode `alfalfa-prepublication-audit` uses only fixed-origin WordPress GET requests, no generic method or body parameter, no model/translation/image generation and no publisher client. Existing credentials stay in Actions; no credentials or users/me body are saved.

The source is the exact accepted final revised article/brief, hash-bound to its ready-for-publication-review report. This is not publication authorization. For post 524204 the audit checks authenticated owner, ID, slug, language, URL, featured media, job marker and exact saved publication bytes. Drift stops the audit before further work.

Fresh inventory covers all public posts (not other users' private drafts). All 25 historical related IDs plus a broad multilingual crop-title shortlist are fetched in full up to the existing 60,000-character document limit; truncation/unavailable records stay explicit and cannot pass. The owned source is excluded after its identity has been confirmed. Added, missing and content-changed IDs are reported. Collecting a fresh scope does NOT grant revision-specific semantic overlap approval.

Both existing WordPress image attachments must keep their IDs, same-host URLs, MIME type and exact saved image bytes. Existing visual verdicts do NOT become approval for the revised article. Their crop identity and revised-article use still require fresh visual binding; no regeneration, upload or hosting change occurs.

Old Arabic/English translations and missing Russian/Tajik translations are checked against the NEW source hash. A faithful translation of the old article cannot be promoted. All languages remain blocked until new source-bound translation, fidelity and regional review are present. Existing review queues/attempt counts and translation files are not reset.

At most 350 authenticated GET/asset requests, 200 inventory pages, 100 related IDs, 4 MB per response, no redirects. Protected originals, images, translation/attempt state and all research/review outputs are hashed before/after. Output is isolated under `artifacts/agri-v2/prepublication-audits/alfalfa-readonly-prepublication-v1/<run-id>/`. A duplicate same-run report is not replayed; a new manual run may refresh read-only observations.

The expected outcome is an honest readiness report with outstanding gates, never `safe_to_publish:true`. Site update still needs explicit same-post authorization and a fresh identity/byte recheck immediately before mutation.

Validation: 1,437 network-blocked offline tests passed, including seven new audit tests. `git diff --check` passed.
