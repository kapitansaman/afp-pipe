# Independent-account backpressure in parallel generation

The owner reports that the 97 free keys belong to separate accounts. A 402/429 response from one leased account does not establish a common quota or a paid balance for the other accounts.

## Admission

- A parallel request makes one provider attempt. There is no immediate retry, overflow borrowing, or fallback to another family/central group after an error.
- HTTP 402/429 holds only the leased slot for at least one hour, retaining a longer Retry-After. Both text and image requests use the same account hold.
- HTTP 401/403 disables only that slot. Disabling persists until separately reviewed; a new run or fresh health file does not silently re-enable it.
- Existing conservative global service/network-error cooldown remains for network failures and HTTP 5xx. The explicit global defer function, repository-wide image lease, serial shared-evidence guard and image single-flight limit are unchanged. This change does not claim to distinguish all provider-wide errors.
- No key value or credential fingerprint is persisted.

## Durable checkpoint

The existing `parallel/key-routing.json` now atomically records request counters with slot-disabled flags, per-slot expiry times and the existing shared cooldown expiry. Unknown/malformed/non-finite hold data fails closed. Old count-only ledgers remain supported. Holds for temporarily ineligible slots are retained, and expiry times never decrease during merges.

The production lifecycle, independent-language queue and legacy parallel coordinator restore this evidence into each fresh SQLite lease pool. Other bounded diagnostic entrypoints retain their existing initialization behavior; they are not advertised as migrated by this change.

A confirmed provider rejection still consumes the original stage attempt. Unknown request outcomes still require reconciliation. No failed scientific assessment, title, content, publication authorization or attempt limit is changed.

## Verification

Regression tests cover local text/image account holds, no immediate hopping, independent families, persistent auth/Retry-After/shared holds, old ledgers, corrupt evidence, concurrency, fixed family boundaries and restoration at generator entrypoints. Live acceptance must distinguish successful admission/coordination from actual quality acceptance and newly verified publication; a rejected research candidate is not a provider-account failure.
