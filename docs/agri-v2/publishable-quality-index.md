# Publishable quality, not perfection

The owner requested an automatic quality index instead of manually inspecting and repeatedly perfecting every article. Minor wording, organization, repetition, translation naturalness and visual composition imperfections are acceptable.

## Article index

The existing final-review request now returns points, not a demand that every idealized flag be true. Software sums the points:

| Dimension | Maximum |
|---|---:|
| Useful answer to the reader | 25 |
| Fidelity to approved sources | 30 |
| Readability | 20 |
| Natural commercial fit, without forcing advertising | 10 |
| Language and factual units | 15 |

At least 70/100, at least 15/30 source fidelity, and no material critical issue is sufficient. A perfect score is neither expected nor requested. No extra scoring call is added to successful reviews. This filter is not a guarantee of factual perfection.

Critical issues are limited to invented sources, wrong crop/product, unsafe advice, materially unsupported quantities, invented human approval, reversed meaning, and unsupported marketing guarantees. A critical objection must quote text actually present in the current article. Grammar, synonyms and preferred heading styles are not critical issues.

A failed index triggers at most ONE automatic editorial repair and ONE independent recheck. After that the topic remains in its separate quality queue; other topics continue. Original article/review artifacts, attempt histories and existing shared call limits survive. Provider failures, missing credentials, unknown/unbound assessments and unsafe HTML cannot become an approval. No history or exhausted budget is reset.

The durable article-quality-index.json is bound to exact article and brief hashes. The total and acceptance are recomputed on reads. quality-review-queue.json records accepted, automatic-repair-pending or review-queue status. The dashboard snapshot exposes these scores and queue states. Existing legacy approvals are not silently re-scored or rewritten.

## Image index

A deterministic 0–100 index is derived from the existing checks: 85 points across substantive checks and 15 across composition preferences. The model's aesthetic score cannot veto an otherwise usable image, nor approve a wrong crop or unsafe assembly. Existing three-correction/single-approved-image fallback remains unchanged; this article-policy update does not reset image counters or introduce more image requests.

## Deployment scope

This policy is enabled for subsequent article reviews. It does not automatically activate recurring generation or publish existing rejected articles. Existing unit-display rules, source bindings, ownership checks, WordPress mutation limits and provider cooldown remain in force. Languages still run independently in their existing queues; this change does not claim to replace translation-fidelity review.
