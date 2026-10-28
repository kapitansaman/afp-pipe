# Real, bounded source search for evidence repair

## Purpose and acceptance boundary

The model diagnoses missing evidence and proposes search queries. Tavily Search retrieves discovery URLs, and the existing guarded downloader retrieves the actual HTML/PDF. Search snippets, result titles, model-supplied claims and coverage triage are never scientific evidence or publication permission. Original extraction, review, overlap and publication gates still decide whether the evidence is sufficient.

This implementation extends the existing repair lifecycle, rather than resetting titles, counters or failures. Pending version-1 URL plans remain usable without a search connection; version-2 plans use real search. Exhausted original planner attempts are not silently reopened. Research-only rollout, scheduler-disabled state and uncertainty reconciliation remain unchanged.

## Connection required

Add the repository Actions secret `AFP_SOURCE_SEARCH_API_KEY` with an existing Tavily API key. It is separate from the 97 AGNES model keys and does not change their fixed family ownership. No account, subscription or paid plan is automatically created. Service availability, allowance and any charges depend on the search account's terms; this implementation does not assume that search is free.

The Actions workflow passes this secret only as an environment variable. The adapter sends it in `Authorization: Bearer` to the fixed HTTPS endpoint. Neither the secret nor raw provider error bodies are saved in checkpoints or logs. A missing connection produces a capability hold before a model call or stage attempt is spent. Never place this key in repository files, issue bodies, query strings or chat.

Official API reference: https://docs.tavily.com/api-reference/endpoint/search

Use Tavily’s free Researcher plan; do not enable Pay-As-You-Go or any paid plan. The code cannot inspect or change account billing settings. Explicit `search_depth: basic` and `auto_parameters: false` prevent automatic advanced search. No answer generation or raw-content extraction is requested from Tavily.

## Bounds

- At most two adaptive search rounds per admitted repair.
- Up to two distinct queries per round and six discovery results per query.
- Up to six source fetches per round, twelve total per repair.
- One shared search request at a time, at least one second between admissions, and at most eighty reserved requests per coordinator run across all families. Reservations are conservative and can include a cache hit after queue admission.
- A conservative local 1,000-reservation calendar-month budget is checkpointed across runs. It counts failed/uncertain requests too, never infers unused account credit, and cannot account for use outside this repository. HTTP 432/433 exhaustion pauses search only; it never triggers paid fallback or a new account.
- Six-hour shared query-result cache, restored from checkpoint without extending its original timestamp. Only actually fetched text enters the evidence packet; the existing packet archive and reuse/idempotence protections remain in place.
- Round-one coverage triage uses fetched text with bound document IDs. Missing requirements lead to targeted round-two queries. Coverage is not final scientific approval.
- The admitted source registry covers `.gov`, selected academic suffixes and explicit public-research/journal hosts. It does not allow arbitrary `.org`/`.com` sites or all international government domains. A registry match alone does not make an article relevant or a claim valid.
- Existing HTTPS, public-DNS, redirect, size and document validation remain enforced. Search/navigation pages are not counted as extracted evidence.

The shared search guard is separate from model-account guards: search authentication, rate limit and temporary provider failures do not cool down all model families. Unknown transport outcomes retain a reservation and enter the existing reconciliation fence; no blind immediate retry. Search requests are bounded service calls, not guaranteed successful searches.

## Failure and checkpoint behavior

Two rounds with no usable evidence record repair exhaustion while preserving the original packet and original attempt history. Temporary page/network failures defer rather than masquerading as scientific absence. Actual exhausted titles continue through the existing finite retry and research/exception backlog policy, not an unbounded repair loop.

Cache/hold state is checkpointed under `artifacts/agri-v2/parallel/source-search/state.json`. Per-title search provenance and fetched-text/coverage reports are in the existing lifecycle evidence tree under `real-search/`. The archive/replacement receipt and coordinator merge proof are unchanged. No current-run workflow admission or publication approval is implied by this code merge.

## Verification

The network-blocked offline suite passes 1,092 tests, including 43 dedicated real-search adapter and adaptive-repair tests. These exercise mocked provider responses, strict schema, admission, cache timestamps, source filtering, coverage binding, temporary failures, legacy compatibility and preserved counters/gates.

The `source-search-check` workflow mode executes at most one fixed basic query and at most two guarded source reads. It makes zero model calls, never changes title attempts or publication state, and does not require model-health renewal because it is not generation. A provider cache hit is labelled explicitly and is not a fresh credential check. Its sanitized report is saved under `parallel/source-search/connection-check.json`.

Old Brave cache/holds are not reused as Tavily results; existing packets and original repair attempts remain untouched.

Offline tests do **not** verify a real Tavily credential or production search availability. Live acceptance remains pending until the secret is configured and a bounded authorized check succeeds. Any subsequent generator dispatch must also satisfy fresh model-health and current lifecycle admission requirements; a search connection is not a waiver for stale health or a closed gate.
