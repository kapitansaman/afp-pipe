# Current-target evidence for Tajik queue reviews

## Observed infrastructure defect
The immutable family07 Tajik attempt 3 edit returned Cyrillic-only replacements
for IDs 20, 22, and 74. The second reviewer nevertheless repeated the previous
mixed Latin/Cyrillic claim for IDs 22 and 74. The existing review validator bound
an ID to the current target without requiring the reviewer to supply the actual
quote; it could therefore lend apparent source binding to an unsupported claim.
A separate semantic objection remains unapproved. Nothing here resolves it.

## New-review contract
New Tajik queue review and bounded self-correction requests use the versioned
`current-translation-issue-evidence-v1` native schema. Every reported issue needs
exact current full source and target, a nonempty current-target excerpt, and an
explicit evidence code. Mixed-script and Arabic-residue codes are mechanically
corroborated against that literal excerpt. Other language and meaning judgments
remain independent semantic judgments, not inferred from character tests.
Invalid reviewer evidence raises a review validation error; it neither edits the
translation nor turns a negative vote into approval. The existing at-most-one
feedback request path and original call/attempt budgets remain unchanged.

## Preservation and scope
No historical raw response, receipt, candidate, vote, approval, queue counter,
regional document or article is changed. Old cached votes are not reclassified.
Prompt/schema hashing prevents old receipts being rebound to this new contract.
Legacy standalone verification and non-Tajik queue behavior are unchanged.
No new live mode, spending authorization, implicit attempt 4, source fetch,
health refresh, scheduling or publication is introduced. A fresh bounded live
validation would still need its own unused authorization and admission. Approval
of all four translations and production readiness are NOT claimed by this patch.
