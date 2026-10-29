# Regional review: unique fact keys and compact output

## Observed failures, retained without alteration

The separately authorized two-call schema recheck (Actions 40856635768) ended blocked: Arabic hit the existing output limit; English supplied five checks but only four distinct fact IDs. One fact was omitted and one repeated. Schema-v2 metadata was present, but an array of fixed length with enum IDs does not guarantee coverage. Both outcomes remain unapproved and immutable.

## Forward-only offline correction

The shared production regional review prompt opts into `regional-keyed-facts-v1`:

- `fact_checks` is a strict object with one required property per actual source fact ID, no unknown properties, no redundant inner `fact_id`. Native schema requires every fact's own check. A legacy array, omitted key or unexpected key fails closed.
- Duplicate JSON keys (including escaped-equivalent keys) are rejected before parsing can silently retain the last value. Keyed requests accept only a complete JSON object, not repaired/truncated/wrapped output. Other legacy clients retain their old parsing behavior.
- Raw parsed wire responses stay unchanged. A deterministic projection copies each explicitly keyed check into the existing canonical array in source-fact order. Only the fact identity is moved from its explicit key into `fact_id`; no missing fact, quote, reason, flag or approval is generated. Receipt binds schema, adapter version, raw hash and canonical hash. Invalid received responses are retained; unknown and incompletely converted requests are never billed again.
- Every existing server validator remains: actual document identity, literal quote, numeric support, study conditions, transfer limits and article-bound negative reasons. Wire correctness is not scientific approval. Negative flags are preserved.
- Prompt asks for JSON only, concise scope/objections, no article/source echo or analysis. Quotes are bounded to 1200 characters, scope/local gap to 480, article objections to 800 and reasons to 600. Text is **never clipped after generation**: the model must choose a genuine adequate contiguous quote or reject insufficient evidence. Full article, facts and actual source texts are preserved in the input.
- The same maximum 14,000 output tokens, 180-second timeout, one transport attempt and all original run/item budgets remain. No undocumented provider reasoning parameters, token-budget increases or automatic retries. Smaller requested prose reduces avoidable verbosity; it does **not** prove that a provider will stop hitting the output limit.

Legacy manually constructed prompts without the wire marker retain their original array schema. Existing cached receipts are not migrated or supplemented. Changed prompts/contracts cannot reinterpret an old response or trigger a paid retry under its reservation.

## Status and boundary

This change is tested offline only. No new admission, run ID, budget, workflow dispatch, search, source fetch, article/translation edit, publication, production promotion or schedule activation is created. Previously consumed admissions intentionally stay code-hash stale and consumed. A future live compatibility check needs a separately explicit bounded authorization and must not reuse the exhausted operations. Russian, Tajik and the earlier unknown Arabic diagnostic remain unchanged.
