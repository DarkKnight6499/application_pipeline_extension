---
author: Yazad Madan
date: 2026-10-05
---

# Answer-sheet guarded Next regression

The `PortalProgress.guardedNext` action classified Next directly and did not enforce an adapter's `answer_sheet_only` mode. With guarded Next explicitly enabled and the required field completed, a fabricated page recorded one actual Next click despite the adapter reporting no next step. A second regression recorded one Next click after the adapter changed from fill mode to answer-sheet mode during the awaited required-field sweep. Neither reproduction submitted a form.

Five new synthetic Edge tests ran before the production change: two failed on actual Next-click counters, one raised the deliberately instrumented callback error, and two passed. The production fix adds an answer-sheet mode refusal after the default-off check and repeats it immediately before incrementing the action count and clicking. The entry check also prevents scan and human-gate callbacks for an adapter already in answer-sheet mode.

After the change, all five new tests passed in 2.418 seconds. All 20 inherited progression tests passed unchanged in 10.470 seconds, including default-off behavior, ordinary fill-mode Next, CAPTCHA, final review, and native-submit refusal. JavaScript syntax, Python parsing, and `git diff --check` passed. Refused answer-sheet cases observed zero Next clicks, zero submit-control clicks, and zero submit events. The fill-mode positive control observed exactly one Next click and zero submissions.

This is a narrow explicit-mode check. It preserves adapters without a mode, as used by inherited safety fixtures. The registry already rejects invalid modes for registered adapters. No broader mode policy, adapter-specific Next classification change, existing test edit, permission change, or live portal action is included. No Resume source file was read or written. No commit or push was made. Combined FULL and PUBLIC integration validation remains the coordinator's task.
