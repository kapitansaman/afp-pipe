# Bounded language probe: output contract and retained hold

## Observed evidence

- Text continuation run 40835869236 passed writer and independent review in two calls (score 90); no artificial repair was introduced.
- Read-only authenticated WordPress readiness run 40836208187 verified publishing capability and the language bridge without post mutations.
- Capability refresh run 40836584707 made 18 successful image requests, leaving fresh actual image capability evidence for all 20 families. Capability evidence is not article visual-quality approval and expires after 24 hours.
- Language infrastructure run 40837334239 stopped after four text calls: the Russian draft failed canonical row validation; Arabic's independent review timed out with no response saved. Tajik and English were not attempted. The report preserves zero site, image and search calls and unchanged originals.
- Offline structural inspection of the retained Russian response found 46 rows rather than the expected 63, including a string where an object was required. No missing translations were synthesized and no response was discarded to manufacture approval.

## Production hardening

Application-owned translator draft prompts with contiguous indexed source segments now request a strict JSON schema: exactly the source row count, object rows with integer IDs and string text, and no extra root/row fields. Canonical validation still checks exact unique ID coverage, and semantic review remains mandatory. A schema does not prove semantic quality or provider reliability.

New receipts bind the response schema hash before transport. Historical prompt/raw-bound responses remain inspectable without replay; unresolved receipts remain blocked. The consumed language probe request retains its original code hash and is intentionally invalid under changed code. It is not rewritten or replaced with a new run ID.

Static translation failure categories are allowlisted for actionable diagnostics without storing arbitrary exception/provider text.

## Verification and remaining release gates

All 1,525 offline tests pass, including strict wire shape, cache reuse, unknown-response non-replay and diagnostic redaction regressions. No additional live provider test is claimed for this hardening.

Readiness evaluated against checkpoint f523dea28187afe317dc7144daa681f16de86092 remains blocked by `provider_circuits_clear`: the shared text circuit is open after the Arabic timeout. Do not erase the circuit, reset counters or repeat the unknown request. Other read-only readiness gates passed at inspection time, not indefinitely.

The staged cohort remains limited to one family with manual acceptance and no automatic promotion. Language fidelity/regional applicability, complete staged end-to-end acceptance, and separate publication/schedule authorization remain necessary. No publication or schedule activation is part of this change.
