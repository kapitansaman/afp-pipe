# Combine verified feedback before the single translation correction

Post-hold run 40845818699 retained a genuine negative Tajik recheck. Structural inspection (not manual article editing) showed three initial mechanical language issues, followed by three semantic issues found only after the mechanical correction. The existing orchestration skipped initial semantic review whenever a mechanical issue was present. That could consume the only correction round before meaning defects were reviewed.

## Change

Both the production language-review queue and the isolated language primitive now run independent semantic review on the first structurally valid indexed candidate even if mechanical checks found defects. The reviewer receives those verified mechanical findings as data. Source-bound validators still validate the semantic verdict. Every distinct verified detail for each ID is combined, rather than one defect overwriting another for the same ID.

Only those defective IDs reach the one correction. The independent final recheck remains mandatory for approval. A positive semantic verdict cannot override a mechanical failure, and a negative final verdict cannot trigger another correction or forced approval. An unrepaired final mechanical failure can stop without another paid review.

The four-call ceiling remains draft → review → one targeted correction → recheck. First-pass success still needs only draft/review. Existing production per-item/per-attempt budgets, provider holds, source bindings and unknown-response fences remain unchanged. If earlier research or reviewer self-correction consumes the remaining budget, the queue defers rather than expanding it.

## Evidence boundaries

No consumed diagnostic request is rewritten, replayed or assigned a replacement ID. No article/translation is manually edited. The old Tajik negative, Russian invalid output and unknown Arabic receipt remain unchanged. This is prevention for future eligible work, not retrospective quality approval and not a claim that a new live translation test passed. Publication, scheduling and rollout promotion are not part of this change.
