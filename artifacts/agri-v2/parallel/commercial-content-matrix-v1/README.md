# Search-to-product content matrix: implementation v1

This implements the owner's clarified business goal: attract real agricultural search needs, answer the actual question, and connect naturally to relevant drip-irrigation products. It is not a recovered transcription of the three historical X examples, which were not located in the supplied chat texts.

## Runtime integration

- `content_matrix.contract` keeps the canonical question, crop and intent, practical reader sections, irrigation relationship, actual approved bridge fact IDs, allowed CTA and product-claim limits.
- Irrigation topics may carry a neutral equipment-selection invitation. Adjacent agricultural topics need actual irrigation-related approved facts before receiving a product bridge. Storage/feed-safety and other distant intents receive no forced product CTA. Keyword matching is a planning hint, not proof of agronomic or commercial suitability.
- Extraction, grounded and legacy writer prompts receive this editorial context. The answer must serve the searcher first, not become a list of experiments or an advertisement instead of an answer. The model cannot invent product URLs, specifications, stock, prices, discounts, water-saving percentages or yield promises.
- Server attaches the matrix to newly generated articles; article validation recomputes it against the topic and approved brief. Historical accepted articles and briefs are not rewritten by this migration.
- New classified matrix articles require independent final source review AND positive flags for answer-before-promotion, no invented product claims and supported-or-omitted irrigation bridges. This also applies to newly generated articles from older non-scoped briefs. Existing scientific, numerical, overlap, image and publication gates remain.
- Persian publication uses only the already reviewed same-site drip-tape landing/category targets, checked again at publication. Distant/unsupported CTAs do not force those links. Translations retain the same-language-only map and omit equipment links when the source article has no CTA. Source citations, media and FAQs remain intact.

## Search Console evidence

The supplied archive contains a limited 1000-query export with a `Last 6 months` filter. Exact calendar boundaries and a query-to-page cross-table were not supplied. Only normalized exact matches against a full canonical title or its leading clause are admitted to `search-demand-map.json`. No synonym/substring match is presented as confirmed intent. Nonmatches remain UNKNOWN, not zero demand. Presence in the queue is not proof of demand; performance alone does not prove a content gap. Actual existing-article review remains necessary.

Raw query rows, clicks, impressions, CTR, positions and page-level analytics remain local under `/data/raw`; they are not copied into the repository. The committed map contains source provenance and matched existing topic IDs only. The source map is an explicit snapshot, not an automatic ongoing sync. CTR percentage strings were validated as percentages and were not used to infer opportunity or priority.

## Delivery and limits

`topic-content-matrix.csv` maps all 2905 immutable titles. It is a planning overlay: conditional bridge IDs/CTAs are recomputed from approved facts at writing time. It does not delete, rewrite, automatically deprioritize or reassign queue topics. No scheduler order, paid attempt budget or historical rejection is changed. It does not modify already published posts or enable the general schedule.

The product target check is a real read-only HTTP check of the configured landing/category pages, NOT verification of individual SKU specifications or live stock. Offline tests validate integration and guards; no new paid article/image/translation/publication run is claimed by this implementation.
