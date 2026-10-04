# Application-filling extension follow-up probe

Author: Yazad Madan. Date: October 3, 2026.

The user requested further subagent probes and confirmed extending the existing application-filling extension. Three independent read-only lanes inspected baseline `a35cc5e14e3025c2770fecddab7beda76ff0aa37`. Repairs use branch `feat/followup-inspection-safety`, stacked on the unmerged selected-fix branch. Only Workday, Greenhouse, and fabricated local fixtures are in scope.

## Verified findings and repairs

All reproductions used fabricated sources or isolated Edge pages. Findings have high confidence for synthetic implementation behavior. They do not establish live employer compatibility.

| Finding | Severity | Evidence | Repair |
|---|---|---|---|
| C5-01: hidden listbox choices clicked | Medium | ARIA-hidden option, popup ancestor, and CSS-overridden hidden ancestor each returned filled and clicked a choice. | Semantic ancestor visibility and final matched-node checks in `adapters/aria-listbox.js`. Closed and lazy popups remain supported. |
| Effective native availability ignored | Medium | A fieldset disabled after scan accepted text. A non-leading ARIA-disabled radio checked. A disabled optgroup selected. | Shared effective native/ARIA checks in scan, fingerprint, and live writers in `engine.js`. Native first-legend exception remains editable. |
| Duplicate native values selected opposite labels | Medium | Disabled select option No and enabled Yes shared a value. Filling Yes selected No and reported success. Root reproduced analogous radio behavior. | Duplicate native select/radio values are refused before writing. |
| C3-02: blank text consumes next line | Medium | Empty Start date followed by Source produced availability equal to the next bullet. | Single-line parsing in `portal_profile.py`; blank facts stay pending. |
| C3-03: malformed contact crashes or misroutes | Medium | Two segments crashed; reordered phone/email became wrong facts. | Validate the complete legacy triplet before exposing named facts. Invalid triplets remain pending without guessed locations. |
| Conflicting facts and uncertainty leaks | Medium | Contradictory sponsorship chose the last answer. Unknown master facts were proposed. Mixed uncertain names leaked surnames. | Reject conflicts; apply uncertainty checks to all proposals and the whole name before splitting. Exact confirmed sponsorship now/future remain separate. |
| Reversed date chronology | Low | January 2026 to December 2025 yielded reversed employment dates. | Omit both normalized dates when chronology is reversed. Unsupported separators remain pending. |
| C5-02: incomplete inspection appeared complete | Medium | Iframe, open-shadow, and custom spinbutton controls were absent with no notice. | Counts, fixed reason codes, current-page scope, and panel warnings in `engine.js` and `panel.js`. No traversal or filling added. |
| Unopened dropdown inspection ambiguous | Low | Lazy combobox exposed zero options without explanation. | Export popup presence, expansion, and observed-choice state. Panel directs manual opening and Rescan. Inspection never opens controls. |
| B-01: Rescan bypasses page policy | Low | Unchanged loaded extension inspected unpaired localhost outside `/fixture`. | Shared popup/review host policy before injection, including every Rescan. |

## Regression evidence

- Listbox: six failures before repairs, then 12 tests passed. Inventory, lazy creation, stale option replacement, final hiding/closing/disabling, and inspection without clicks are covered.
- Host policy: old review inspected the unsupported page and failed the refusal regression. Two tests pass, covering 18 URL boundaries and loaded MV3 initial refusal, paired fixture acceptance, and navigation followed by Rescan refusal. Rejected pages receive no bridge.
- Profile: initially 14 failed subcases and three errors. Mixed-name review additionally reproduced partial surnames. All 14 tests pass. Confirmed contact and history dates remain preserved.
- Native/coverage gate: original seven tests produced five failed subcases and two missing-metadata errors before repairs. Duplicate select and radio regressions separately failed before guards. Nine final tests cover effective availability, ambiguity, privacy, coverage, and panel notices.

Two root harness assertions were corrected: shadow panel text requires reading its shadow root; omitted protected fields count includes the synthetic password plus both boundary controls. These corrections did not weaken production checks. A host test argument error was corrected before meaningful red evidence.

Final discovery with `PORTAL_TEST_BROWSER=msedge` and no `PORTAL_SOURCE`: 142 tests in 46.816 seconds, 61 passed, 81 SKIPPED-BY-ENVIRONMENT, zero failures/errors. Both visible Edge browser trials passed in 15.173 seconds. All extension JavaScript syntax checks and diff checks passed. Root inspected review and new coverage screenshots; PNG author metadata is Yazad Madan. Screenshots remain ignored local artifacts.

## Boundaries and deferred work

No private profile, tracker, source workflow, real resume, credentials, or employer account was used. No application submission occurred. Manifest permissions and ATS family scope remain unchanged. Coverage contains counts and fixed reason codes, excluding frame URLs/content, shadow content, entered answers, and protected labels. Closed shadows cannot be discovered; hidden and future sections require manual navigation and fresh inspection.

Remaining earlier findings are outside this batch: sandbox destination policy, session reparse-point containment, and legacy test-cardinality weaknesses. Editable custom dropdowns, genuine workflow audit/build, remote persistence, upload completion, production browser-action permission acquisition, and live employer compatibility remain unverified. Uncertainty recognition is conservative and phrase-based; malformed contact triplets are rejected wholesale.
