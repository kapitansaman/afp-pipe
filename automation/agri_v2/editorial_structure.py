"""Reader-first structure; a reusable editorial guide, never factual authority."""
VERSION='reader-first-organized-v1'
RULES=('Organize a useful Persian article rather than a research memo: answer the canonical reader question in the opening, then develop relevant factors and practical explanations with clear h2/h3 hierarchy, a genuinely useful comparison/decision table, a natural irrigation/product bridge only when relevant, and a concise conclusion. '
 'Source listing and the final FAQ are assembled by the existing renderer; do not duplicate the page title, table heading, bibliography, table of contents or FAQ in the body. Use semantic headings so the theme can build navigation; no embedded scripts or handmade layout. '
 'Use short readable paragraphs and purposeful lists, not repetitive keyword stuffing or repeated caveats. Limitations belong next to the affected claim and once in a concise summary, not in every paragraph. '
 'The supplied editorial example guides organization only, not its factual values or claims. Adapt the outline to actual intent: a narrow question does not need every section of a long comprehensive guide. There is no fixed heading count, paragraph count or minimum size per section. Do not pad, invent measurements or manufacture product benefits to fill a template. '
 'In review assess flow, useful coverage, coherent heading hierarchy, non-repetitive explanation and a clear ending under the existing readability/usefulness rubric. Organization is not scientific proof and minor style differences are not critical failures.')

def contract():return {'version':VERSION,'fixed_section_count':False,'example_is_factual_evidence':False,'theme_owns_navigation':True,'renderer_owns_sources_and_faq':True,'rules':RULES}
