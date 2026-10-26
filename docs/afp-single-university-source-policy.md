# Single-university source sufficiency

Owner-approved on 2026-10-26: one actually fetched and directly relevant university source can be sufficient. A second independent institution is preferred, not mandatory in this case.

- This exception applies to university `.edu` hosts already admitted by the secure institutional URL validator; it does not expand domain trust or bypass HTTPS, public-address, redirect, cache or content validation.
- With no admitted university source, two independent institutional publications remain required.
- Only sources used by approved facts count. An unused university citation cannot unlock unrelated claims.
- Relevance, crop/product/intent, literal quotations, numeric/unit/geographic limits, independent fact review, complete overlap audit, article review, image review and translation checks remain mandatory.
- Scoped reviews return `source_policy_version: university-single-source-v1` and `source_policy_satisfied`. `independent_sources` remains an honest descriptive flag: a single independent publication must use `false`; it is not fabricated corroboration.
- Single-university reliance is disclosed in the new brief's source limitations. Rejected historical reviews are not relabelled or turned into passes.
- No historical attempts, accepted outputs, family assignments, service cooldowns or publication holds are reset. General scheduling and scoped-rollout release are unchanged.

Implemented in scouting, qualitative evidence, scoped evidence, reviewer prompts/validators and final brief readback. Offline validation: 559 tests passed. This is not a live generation or publication result.

Remaining work is separate: evidence discovery/backlog/replacement for blocked families, exhausted-budget handling with explicit bounded authorization, successful pilot, then a measured 20-family run and adaptive scheduling.
