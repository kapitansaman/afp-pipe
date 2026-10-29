"""Mixed knowledge contract: useful model knowledge is not fabricated source evidence."""
VERSION = 'mixed-knowledge-supervision-v1'
RULES = (
 'Use three complementary knowledge bases: the model\'s established general knowledge and reasoning; credible loaded external sources (extension guidance, technical manuals, reviews and research, not only field trials); and actual field measurements when a claim genuinely needs them. '
 'The writer may use well-established qualitative background, definitions, conceptual explanations, practical non-prescriptive guidance, comparisons and explicitly limited editorial synthesis from model knowledge. It need not merely paraphrase fetched passages. '
 'Do not require a field experiment or external citation for every general explanatory sentence. Absence from the fetched excerpts alone is NOT a defect in permitted model background. '
 'Model confidence is not verification: the independent supervisor must still check plausibility, contradictions, uncertainty, actual reader intent and potential harm. Doubtful or disputed background must be qualified, omitted or routed for targeted verification, not silently approved. '
 'Source-specific findings, attributed statements, quantities and calculations must retain verified evidence and exact units/scope. Current prices, regulations and claims of real observations need current verification. Local operational rates/dates, cultivar recommendations, safety-critical inputs and brand performance guarantees need suitable applicability evidence, not model memory alone. '
 'Do not fabricate a citation, quote, author, field trial, measurement, local experience or human approval. Never attach a supplied institutional citation to a claim it does not support. Model background may remain uncited; cite actual loaded sources only on the claims they support. '
 'Model knowledge does not override a contradicted source, license a new unsupported causal mechanism or prove an actual field condition. Distinguish well-established explanatory concepts from speculative causal explanations and novel recommendations. '
 'Source-extraction fields remain literal evidence only: use model knowledge to understand, synthesize and identify gaps, never to manufacture an evidence ID or quotation. Translation is fidelity-only: do not add knowledge or localization. '
 'No change to numeric gates, security, attempt budgets, existing holds or publication authorization follows from this policy.'
)


def contract(role=None):
 mode = ('fidelity_only' if role in ('translator','translation-reviewer') else
         'source_extraction_with_model_reasoning' if role=='researcher' else
         'independent_mixed_knowledge_audit' if role=='evidence-reviewer' else
         'mixed_knowledge_writing')
 return {'version':VERSION,'mode':mode,'model_background_allowed':mode not in ('fidelity_only','source_extraction_with_model_reasoning'),
         'field_trial_required_for_every_claim':False,'model_memory_is_verified_source':False,
         'invented_citations_allowed':False,'numeric_authority_unchanged':True,
         'publication_authorized':False,'rules':RULES}
