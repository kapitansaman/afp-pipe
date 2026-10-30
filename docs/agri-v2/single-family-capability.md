# Authorized family-07 capability check

Manual mode: `single-family-capability`. Admission: `single-family-capability-request.json`. Request identity: `authorized-family07-capability-four-call-v1`.

The owner approved at most **three tiny text calls and one actual image call**, only for family-07. This is a new, independent capability diagnostic, not replay or admission of any exhausted article/translation request. It cannot publish, edit article/translation bytes, reset attempts, promote proofs, change global health, or enable schedules.

## Transport and preservation

- Exact existing stage-one cohort, topic, roles (text slots 25/26/27; image slot 28), code, credential-set labels, original reference-image bytes and historical artifact hashes are bound before admission. No credentials or credential fingerprints are saved.
- Exact manual repository/branch identity plus create-only remote reservation. An existing local report, including an interrupted/unknown one, or conflicting remote reservation means zero new requests. No rerun or retry of this admission.
- One request at a time, one attempt per slot, a pool ceiling of four, and one receipt per slot. Text is `Reply with OK only.`, at most 256 output tokens and 70-second timeout. Non-OK, truncation and wrong model fail closed.
- Before text is spent, read-only shared image admission is checked. Existing provider holds and per-slot backpressure deny work. Ownership is pinned; neither central slots nor another family can be substituted. The image call uses existing repository-wide queue/lease admission, rechecks shared evidence and has the existing 180-second provider timeout.
- An independent diagnostic ID is included in the image prompt to distinguish this approved test from prior requests. Original AFP reference identity is preserved. Existing render checks and landscape decoding apply; final dimensions must be at least 768×432, landscape, and at most 20 megapixels. No image is installed into a production article.
- Any failed/unknown probe stops remaining calls. Timeout is spent and reconciliation-required, never replayed. Authentication rejection disables that slot; quota/rate failures preserve slot and shared cooldown. Shared routing counters only increase.
- Historical inputs are checked before every transport and at finalization. All old reports/raw replies/queues/attempts, global health and language approvals remain unchanged. Only new diagnostic artifacts, monotonic routing/backpressure and a provider hold when needed may change. GitHub coordination operations are not site writes.
- Success writes a scoped proof only under this new diagnostic's directory. It explicitly is **not global production health, production readiness, language approval or publication visual approval**. The existing global gates remain enforced.

## After execution

Report actual spend and outcome, not the approved ceiling as if it were actual usage. Never run broad `health-refresh` or `image-refresh*` as a substitute. A positive result is only family capability evidence; missing language acceptance, exhausted-stage continuation and end-to-end output validation need separately bounded work. Publication and scheduling still require distinct owner approval.
