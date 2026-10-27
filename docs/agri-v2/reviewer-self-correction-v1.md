# Feedback for the reviewer itself

A review is untrusted model output, not ground truth. Before any edit, the server
checks issue IDs, full quotations, verdict consistency and the source-bound Tajik
carrot glossary. It sends concrete validation feedback back to the reviewer and
allows **one** corrected judgment, paid from the existing total allowance. Both
judgments and the feedback are retained. A corrected judgment may still reject
the translation: the server never silently turns a false flag into true.

The correction does not edit translations. Editing remains a separate step and
requires enough remaining allowance for both the edit and its recheck. If budget
or review validity is unresolved, only this family is held; global source, image,
ownership, provider cooldown, publication and scheduling gates are unchanged.

## Alternative reviewer test

The previous five-call authorization spent three requests. The new one-shot
operation is limited to the **remaining two**, not a fresh five-call budget.
It may perform one authenticated `/models` GET in Actions, choose one actually
advertised alternative text-model ID (never an image/audio/embedding model), and
review the saved Tajik correction candidate with the previous review's verified
quotation errors supplied as feedback. One reviewer self-correction is allowed
within those same two calls. There is no model hopping after a provider error.

The selected model must identify itself in the response; otherwise its identity
is unconfirmed. No diagnostic success is written into the default model's health
record, and no production model or translation is replaced. If the catalog has
no other text model, the operation stops without guessing a model name or making
a model-generation call. A valid negative review is useful diagnostic evidence,
not a failed demand to approve the text. No publication is authorized.
