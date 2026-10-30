# Regional catalog v3 — explicit source metadata, not inferred applicability

## Live diagnosis (no article prose edited)

The one-shot v2 diagnostic in Actions run `40993263400` completed at
2026-10-30T02:45:37Z: exactly three text calls (one scoped health + AR + EN),
three fresh logical original-source fetches, zero searches/site/image calls,
zero article/translation edits/publications/schedules/promotions. Originals and
expired global capacity health bytes remained unchanged.

The English review passed all existing server gates but was NOT promoted.
Arabic selected literal numeric-eligible source passages and complete facts,
but explicitly returned `country:null` for all five known US institution
sources. The unchanged server correctly rejected `regional_country_scope_required`.
One foreign-source local gap was also 29 characters, below the existing 30-char
server minimum. That secondary issue was found structurally, not by editing
article/fact prose. All raw responses, receipts, canonical hashes, failed
outcomes and spent budgets remain immutable.

## Forward-only contract

New requests default to `regional-quote-catalog-v3`. Explicit v1/v2/keyed
requests remain frozen, including the consumed isolated v2 executor/admission.
No new paid admission, workflow, retry, queue reset or live call is added here.

- A hashed `source_context_policy` records the EXISTING institution-host-country
  classification and local technical-host eligibility for each actual document,
  bound to complete document hashes and the exact current audience policy.
- Institution country is metadata, NOT trial/study geography, experimental
  relevance or a source of local prescriptions. Actual study location and
  soil/climate/water/cultivar/system limitations remain independently reviewed
  in `scope`. Unknown institutional country is NOT guessed from a language.
- Each supported fact's native `anyOf` branches couple the selected numeric-
  eligible quote IDs with the corresponding known institution-country label.
  The MODEL must explicitly return it. The decoder NEVER fills missing/null
  country or copies a URL label into an old answer.
- For foreign supported evidence the native branch requires the already
  mandatory `international_fallback:true`, meaningful local gap 30..480 chars,
  and `transfer_limits_retained:true`. Technical source-kind bounds match the
  existing positive server validator. Existing scope 30..480 bounds remain.
- Honest unsupported fact and negative-root branches remain available. Required
  metadata cannot compel approval. Whitespace padding still fails the unchanged
  server's stripped-length checks. Numeric eligibility still proves no semantics.
- Complete literal quotes/article-objections, duplicate-key rejection, all
  scientific/numeric/geographic/negative validators, runtime payload ceiling,
  immutable schema/catalog/response receipts and no-replay rules remain intact.

The v3 snapshot includes the unchanged v2 consistency/catalog snapshot plus the
context policy. Raw labels/gaps/decisions are validated then copied without
inference or rewriting. Changing sources, profile or metadata invalidates the
contract before transport. Old receipts cannot be relabelled as v3.

## Limits of verification

This change is tested OFFLINE only. The retained v2 Arabic result remains failed;
the retained English result remains isolated and unpromoted. Offline checking of
archived raw responses is regression testing, never a freshness renewal, new
scientific assessment or production acceptance. Further live validation needs a
new explicit bounded authorization. Global capability renewal, RU/TG acceptance,
fresh site readiness and staged 1 → 3 → 20 gates still precede activation;
publication and recurring schedules require their own authorization.
