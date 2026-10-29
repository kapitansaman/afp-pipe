# Claim-level research and review contract

Version: `claim-context-research-v1`.

## Scope and source admission

Publisher credibility, support for the exact claim, and applicability to the reader are separate checks. National, provincial and municipal public bodies, official extension/research centres, universities and specialist scientific publications can supply evidence within their competence. A municipal water-restriction notice supports that dated restriction, not automatically a crop irrigation rate. Official news is context, not technical agronomic support. Commercial specifications are not independent agronomic corroboration.

This change does **not** admit arbitrary country domains, `.org` or commercial websites. Restricted government namespaces for Turkey, France, Spain, Mexico, Brazil, Japan, South Korea and China are added for international fallback; existing HTTPS, URL, public-DNS and redirect checks remain. Municipalities or research institutes outside admitted namespaces need a separately verified exact-host registry entry. No guessed municipal domains were added. The existing university-single-source / two-independent-institutions sufficiency rule is unchanged and is never sufficient proof of a claim.

## New extraction

Every new scoped extraction must return the exact policy version, a conflict array, and a complete per-fact study context: publisher, publication date, species, cultivar, actual geography, climate, season, soil, water quality, irrigation method and trial conditions. Each known value is bound to a literal passage supporting that same fact. Unreported fields are explicitly `{value:null,quote:null}`. Context metadata is not additional claim or numeric authority.

Claims distinguish general principles from bounded source observations. The current extraction workflow still prohibits unsupported local operational prescriptions. Numeric observations cannot be relabelled as universal principles. A reviewer checks semantic meaning and publisher competence separately; a mechanically valid substring is not scientific approval.

Conflicting results identify the original fact indices and are explained, unresolved, or not comparable. An explained cause needs a literal supporting passage and independent semantic review. Missing causes remain unknown. New conflict indices are never silently remapped by dropping or rewriting facts; invalid new outputs remain blocked. Historical conservative salvage remains available only under its original rules, without being upgraded to this policy.

## Reviews and reader-facing writing

The same policy reaches the researcher, Persian writer, evidence reviewer, translator and translation reviewer. New source reviews must independently check each original fact's context, claim class and publisher expertise, and confirm that differences were assessed. Existing source/route/crop/numeric checks and honest negative decisions remain mandatory.

New regional reviews use schema 2. They distinguish a general principle, a geographically labelled observation and a local recommendation. Every negative root flag or unsupported fact requires actual affected fact IDs, an exact quotation from the current article/excerpt/FAQ, and a specific reason. An unbound negative stays blocked; it is never changed to approval. An accurately labelled foreign observation does not require a study in every target country. A disclaimer does not excuse an unsupported instruction in a table, excerpt or FAQ.

Public prose attributes institutional findings naturally and distinguishes editorial synthesis without AI/model boilerplate. Private claim-source links remain for auditing; the existing presentation layer moves approved scientific source links to the final source list. This change does not remove source bindings or alter the end-source renderer.

## History, execution and deployment safety

- Previously saved candidates, reviews and briefs are not relabelled or automatically approved.
- New briefs retain policy, contexts and conflict records, and replay verification revalidates them.
- Original article/image/translation bytes, queues, retry counters, budgets and receipts are untouched.
- No workflow, scheduler, production-enable flag, WordPress post or image-hosting setting is changed.
- Offline mock tests are not independent scientific re-review of the blocked alfalfa article.
- Existing one-shot revision receipts remain fenced; this patch is not authorization to replay consumed calls. A fresh bounded authorization and a new source-bound review are required before any same-post replacement.

## Validation

Run `python -m unittest discover -s tests/agri_v2` and `git diff --check`.
The baseline before this change passed 1,369 offline tests. New tests cover source-bound versus invented context, missing conditions, numeric observation classification, unresolved/explained conflicts, exact negative quotations, official namespace lookalikes, new-extraction contract propagation, full new-brief replay, legacy preservation, and unchanged publication/budget gates.

Validated result: **1,396 tests passed**, including 27 new policy tests; baseline: 1,369 passed. Full tests used local fixtures/mocks, with zero live model/search/WordPress calls. `git diff --check` passed. Production workflows, queue/state data, articles, receipts, images, retry budgets and publication flags were not changed.
