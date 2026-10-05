---
author: Yazad Madan
updated: 2026-10-05
---

# Long-form evidence and validation

`portal_pipeline/longform.py` is a read-only helper for human-authored portal answers. It does not draft text, call a model, fill a field, or select an answer. Cover letters remain in the private Resume workflow.

`evidence_for(question, root)` reads only `_Reference/Application_Boilerplate.md` below the supplied workflow root. It returns `{text, source}` lines from `Role Descriptions` for project or experience questions and `Why Us` for employer motivation questions. A question that matches both categories can receive both sections. The source has the form `Application_Boilerplate.md#Role Descriptions:L12`. Missing files, unrelated questions, and unresolved placeholder lines yield no evidence. A source path that resolves outside the root is rejected. The file read is limited to 1 MB. No private source text is stored in this repository.

`count_chars(text)` counts UTF-16 code units after treating CRLF, LF, and lone CR as canonical CRLF newlines. Each newline therefore counts as two units. A supplementary Unicode character counts as two units. `fit(draft, limit)` returns `{ok, count, limit}` and requires a positive integer limit. A draft fits when its count is equal to or below that limit.

`check_numbers(draft, evidence)` returns distinct unsupported numeric expressions in draft order. It accepts exact digits and decimal precision, plus comma grouping as an equivalent spelling. `8.5%` and `8.5 percent` are equivalent. Signs, percentages, fractions, scientific notation, attached letters, scale words, and date digits retain their meaning. For example, evidence for `5` does not support `5k`, `5M`, `5 million`, or `.5%`; evidence for `999` does not support `v999`; and evidence for `2024` does not support `2025`. Ambiguous expressions require the same quantitative spelling in the evidence. The check is a narrow numeric gate, not a factual or semantic verifier. A reviewer must still check that each statement uses the evidence accurately and does not disclose a skills gap in cover-letter prose.

A caller should show returned lines and source references beside a human-authored draft, mark it `draft_needs_review`, and block selection when `fit` is false or `check_numbers` is nonempty. No evidence means pending, even for a draft with no figures. The caller must not accept evidence supplied by a portal page or client request as a trusted source.

Synthetic tests were written first. The initial targeted run failed because `longform` did not exist. After implementation, `py -3 -B -m unittest discover -s portal_pipeline/tests -p test_public_longform.py -v` passed five tests. These cover UTF-16 and newline counts, strict limits, source section boundaries, missing evidence, and numeric differences. No live portal or candidate data was used. The tests establish local behavior only, not live portal compatibility.

## Integrated review and filling

The authenticated POST /api/sessions/<id>/longform route accepts only question, draft, and a positive bounded portal limit. It applies to the current session, reads its own workflow evidence, and never trusts client-supplied evidence. No evidence stays pending; supported numeric expressions and a fitting draft still have status draft_needs_review. The helper neither generates nor stores a draft.

The review panel offers Check draft for supported non-history textarea prompts. It shows source evidence, exact count, and unsupported numbers. A successful check enables manual selection, without selecting anything. Edits invalidate approval and selection. Select suggested excludes these drafts. Draft checks and filling cannot run concurrently, and their controls lock during a fill.

The engine independently requires explicit review and fresh validation before adapter dispatch. It checks the live portal limit and refuses a missing validator, unsupported number, missing evidence, malformed report, or failed fit. The extension bridge supplies its own validator, and the background broker verifies sender, origin, and current session before and after the request. Caller-supplied functions are excluded from browser transport. Other selected-field, overwrite, manual-field, and human-gate controls remain in place.

Coordinator integration initially reproduced missing routes and unguarded direct engine writes. Review then reproduced scaled/leading-decimal numeric bypasses and prompt vocabulary gaps before their fixes. A vocabulary regression checks every backend trigger word against the engine matcher. A further regression reproduced a write after the portal limit changed during an awaited validation; the engine now refuses a stale limit and repeats the canonical UTF-16 count before assignment. Thirteen new route, engine, and panel tests pass in 5.450 seconds; six new broker and malformed-report tests pass. No inherited tests changed. One newly authored locator was corrected after a timeout.

These checks establish numeric screening and length fit, not factual accuracy. Spelled-out quantities, attribution of a number to a particular role, nonnumeric claims, and wording still need human review. A missing verified portal limit leaves filling manual. No model calls or source workflow writes occur. Cover letters continue through the existing private builder.

Combined final FULL acceptance passes 453 tests in 249.239 seconds with two expected Windows symlink skips. JavaScript syntax, Python compilation, and normal Git diff check pass. The four monitored tracker/reference hashes are unchanged. PUBLIC and replay acceptance are recorded in STATUS_AND_NEXT_STEPS.md.
