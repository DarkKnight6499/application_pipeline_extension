---
author: Yazad Madan
updated: 2026-10-03
---

# Trial failures and remaining work

This log distinguishes observed failures from untested compatibility. Keep historical findings even after a fix so future sessions do not repeat the same experiments.

## Earlier Greenhouse CLI trial

The original report is preserved in [LEGACY_GREENHOUSE_TRIAL.md](trials/LEGACY_GREENHOUSE_TRIAL.md). It describes a separate Python and Playwright prototype, not this extension's code.

| Finding | Evidence and response | Current status |
| --- | --- | --- |
| Public BTIG form stopped before scanning | The trial emitted a combined login, MFA, CAPTCHA, or bot-protection reason. The original run did not record which signal matched. Later code separated signal types. | Specific live barrier remains unverified. No live filling or upload occurred. |
| Conservative barrier may reject optional sign-in or passive CAPTCHA frames | This is a hypothesis from code review, not a measured diagnosis of the BTIG run. | Needs an observed signal before changing behavior. Do not bypass a challenge. |
| Synthetic input reverted its value | Eight selected rows produced seven verified results and one intentional mismatch. Fourteen unselected controls retained their original values. | Demonstrates reporting, not employer persistence. |
| Current workflow smoke suite had one inherited documentation failure | The earlier recorded run passed 183/184 tests. Directory_Map lacked two names already missing at baseline. | Historical failure outside this repository; not a current extension test failure. |
| No demonstrated live time saving | The safety stop prevented live writes. Human time was not measured. | Observed live saving remains zero; comparison with Simplify remains unknown. |

## Extension prototype

| Finding | Fix or evidence | Remaining limit |
| --- | --- | --- |
| Review-state race when Close or Rescan interrupted filling | Lock review controls and Rescan until the fill result. Version 0.3.0 regression tests pass. | Manual navigation can still replace the employer page during a fill. |
| History assigned from DOM order could use the wrong employer | Explicit per-row employer or school selection, stable DOM identity, duplicate binding rejection, and tests. | Real employer wrappers still need validation. |
| Opaque month values could be mistaken for calendar numbers | Match visible month labels against verified month/year facts. | Unknown start dates and full-date day components stay manual. |
| Inspection was buried in the filling flow | Version 0.3.1 provides inspection-only mode without helper pairing, import, or candidate profile loading. Its bridge rejects scan and fill commands. | User must navigate the real form and export reports. |
| Live browser unavailable during the latest session | Edge selection failed; inventory contained no browsers; automatic browser selection returned `No browser is available`. | No live DOM walkthrough occurred in this session. |
| Test popup did not receive activeTab permission | Opening popup.html in a test tab does not reproduce clicking the browser extension action. The routed-host test uses an explicit temporary test-only host permission. | Production activeTab flow still needs a connected real browser. |
| Shadow host inner_text returned an empty string | Browser assertions now read the panel element inside the shadow root. | This was a test assertion issue, not a missing review panel. |

Latest completed validation before Greenhouse development: 76 tests passed in 46.206 seconds, with JavaScript syntax checks passing. Backend tests confirmed source trackers and references were unchanged.

## Greenhouse phase, version 0.4.0

- An initially discovered Antora posting redirected to a board marked inactive. It was rejected as the adapter reference. The public Justworks application provided an intact form instead.
- Generic scanning would include auxiliary required inputs, miss whole-section demographic protection, and label the resume upload as Attach. The dedicated adapter now scopes the form, excludes ARIA-hidden controls, protects the survey container, and resolves the hidden resume input through its exact labelled group.
- Editable comboboxes remain unsupported because the public response does not establish their live popup and selection contract. Compound sponsorship stays pending. These are visible limits rather than successful fills.
- Five new browser regressions and the extended loaded-extension inspection test pass. The full suite passed 81 tests in 50.944 seconds. JavaScript syntax checks passed.
- Public HTML inspection and synthetic verification do not establish live persistence or upload completion. Detailed evidence and the next task are in [GREENHOUSE_CONTRACT.md](GREENHOUSE_CONTRACT.md).

## Acceptance still pending

DOM readback does not prove remote saving. A file input's filename does not prove remote upload completion. Neither Workday nor Greenhouse has a real employer application validated through final review. Final submission stays manual.

## Independent synthetic probe, October 3, 2026

Baseline: `de2e51b5e424634d2be66a32bcfa5627f5e1fbef`. Full evidence, reproductions, earlier-review status, and ranked proposed fixes are in [PROBE_REPORT_2026-10-03.md](PROBE_REPORT_2026-10-03.md). No production fix has been applied at this checkpoint.

| Failure | Evidence | Fix and validation status | Remaining limit |
| --- | --- | --- | --- |
| Cross-form radio writes protected attestation | Synthetic same-name radios in separate forms; ordinary selected Yes checked protected second-form radio and reported filled. | Open, personally reproduced by coordinator. Proposed form/member binding regression and fix. | Selected-only and protected-field invariant violated. |
| Protected collateral missed | Selected text input side effect checked unselected agreement; next selected write continued. | Open, personally reproduced. Proposed protected-state monitoring without disclosure. | No automatic rollback assumed safe. |
| Unconfirmed answer promoted | Synthetic `Yes [CONFIRM]` became Yes and filled authorization select. | Open, personally reproduced. Proposed uncertainty-preserving parser and regression. | Unknown facts must remain pending. |
| Upload guard stale across checksum await | Queued synthetic label change to protected question was observed at file assignment; result still filled. | Open, personally reproduced. Proposed immediate post-await guard revalidation. | A checksum validates bytes, not current question identity. |
| ARIA-state and dropdown visibility gaps | Stale ARIA read-only input filled; ARIA-hidden option clicked. | Open, lane reproductions recorded. | Current native/ARIA availability needs consistent checks. |
| Parsing fragility | Blank boilerplate consumed next line; contact length/reordering caused crash or wrong mapping. | Open, synthetic reproductions recorded. | Private actual source parsing was deliberately not checked. |
| Public suite unavailable | Three module import errors, zero actual tests executed; inventory is 81 methods. | SKIPPED-BY-ENVIRONMENT, not passing. Proposed independent synthetic test setup. | External real audit/build and default Chromium unavailable. |
| Unsupported surfaces omitted | Synthetic iframe, shadow-root, and spinbutton controls absent from inspection with no incomplete-surface reason. | Open, synthetic reproduction recorded. | Does not authorize new portal families or live probes. |

Low findings cover Rescan host-policy inconsistency, caller-supplied sandbox placement, probable session reparse-point containment, and weak test cardinality assertions. No critical issue or employer-page-readable extension PII channel was established. Historical live limits and validation records above remain unchanged. Await the user's ranked-item selection before production fixes.

## Selected-fix validation, October 3, 2026

The user selected recommended items 1-5. E-01 regressions initially failed in three cases: merged cross-form groups, selecting another form's attestation, and a protected member inside an ordinary group. Radio grouping now uses form ownership and validates every member's protection. All four independent synthetic radio tests pass, including a moved-member refusal. Untouched controls and submission counters remain unchanged. Real portal compatibility remains unverified.

E-02 produced two failing regressions before repair: consent side effects continued into the next selected write, and changed password state was ignored. The baseline now includes registered protected controls and redacts their labels and values from error reports. All seven engine tests pass. A portal side effect can already have happened when detected; it is reported and later writes stop, without automatic rollback. Unscanned controls and delayed remote changes remain unverified.

E-04 regressions demonstrated protected-label, disabled-control, detached-node, and changed-form writes during checksum awaiting. The detached-node case previously reported failure after it had already received a file. Live guards now run after the await and before assignment, preventing all four writes. All 13 engine tests pass; checksum mismatch still leaves the input empty and valid synthetic bytes still attach. Native and ARIA editability checks share this guard. No remote employer upload or real document validation was performed.

C3-01 fabricated profile tests failed on 13 subcases and raised one whitespace exception before repair. Unknown or unconfirmed text is now omitted, and only exact Yes/No values become eligibility booleans. All three profile tests and the browser pending-answer regression pass. Confirmed present/future sponsorship remains separate. Annotated eligibility requires manual clarification; the private source was not inspected. Contact-schema and general multiline parsing fixes remain outside the selected batch.

L6-01's source-missing regression initially raised an import-time RuntimeError. Independent profile, HTTP boundary, engine, and loaded-extension trial tests now run on fabricated data. Explicitly configured bad sources still error; absent sources skip external integration. Combined result: 27 passed, 0 failed/errors, 81 skipped, 108 total in 25.677 seconds. This does not reproduce the historical 81 integration passes.

The requested visible Edge browser trial passed two tests in 13.962 seconds: loaded-extension pairing/review/selected fill/custom dropdown/synthetic attachment/final protected review/inspection refusal, and synthetic Greenhouse filling/hidden upload/editable-dropdown refusal. Unselected fields, cover letters, protected survey, signatures, and attestation remained untouched. Submission counters stayed zero. The helper's session and attachment methods are explicitly fabricated stubs; genuine resume audit/build and remote upload acceptance were not tested.

New trial harness failures and corrections are preserved here: Playwright string waiting violated extension CSP, fixed with a locator wait; its network filter accidentally blocked extension scripts, narrowed to allow only the test's localhost and extension origins; appended boundary controls duplicated fixture IDs, fixed with distinct guard IDs; and an isolation assertion initially saw the local fixture's own engine, fixed by removing page-owned engine/panel scripts from the routed test response. Production guards and manifest permissions were unchanged for these harness corrections. Screenshots remain local and ignored.

The selected batch is published as [open PR 1](https://github.com/DarkKnight6499/application_pipeline_extension/pull/1). It is not merged. All four selected high findings are repaired; remaining probe findings and unverified external/live acceptance limits are retained above.

## Follow-up extension validation, October 3, 2026

Author: Yazad Madan. User authorization covers extending this extension and additional subagent probes, within Workday and Greenhouse.

C5-01 remained reproducible: ARIA-hidden options and hidden ancestors overridden by CSS were clicked. Six new regressions failed before repair. Semantic visibility and final target checks now reject these cases; all 12 listbox tests pass in isolated Edge. Lazy creation and closed-popup inventory remain passing. Structural description does not click or expose answer values. Remote ATS behavior remains unverified.

B-01 was reproduced with an unchanged loaded extension inspecting unpaired localhost. The old review failed the new rejection regression because inspection succeeded. Shared host validation now precedes injection on initialization and every Rescan. Both tests pass, including 18 URL cases and navigation refusal. A test harness argument error was corrected before meaningful red evidence. Actual browser-action permission acquisition remains unverified.

Profile regressions produced 14 failed subcases and three errors before repairs. Blank answers consumed later labels; malformed contact crashed or misrouted facts; contradictory duplicates selected the last answer; uncertain master facts and reversed dates were proposed. Single-line parsing, conflict detection, guarded contact validation, shared uncertainty checks, and chronology rejection resolve those cases. Review additionally reproduced partial surname leakage from `[CONFIRM] Jane` and `Unknown Person`; the whole uncertain name is now suppressed. All 14 tests pass. No new pending-reason schema was introduced. External source compatibility is unverified.

Native and coverage regressions initially produced five failed subcases and two missing-metadata errors. Effective disabled state, actual radio target availability, and optgroup availability now govern proposals and writes. Independent review caught duplicate select values selecting the opposite label while readback falsely passed; root also reproduced duplicate radio values. Both are now refused before writing. All nine native/inspection tests pass. Structural coverage warnings expose omitted surfaces without their contents or protected labels. Hidden/future pages and closed shadows remain uninspected.

Root corrected two test assertions: panel text resides in its shadow root; the omitted-protection count is three because it includes the password and both boundary controls. Final result: 61 passed, 81 environment skips, 142 total, zero failures/errors in 46.816 seconds. Both visible Edge trials passed in 15.173 seconds; submission counters remained zero. Screenshots were inspected and remain local. Syntax/diff checks passed. See [follow-up evidence and deferred findings](PROBE_FOLLOWUP_2026-10-03.md).

Follow-up is published as [open PR 2](https://github.com/DarkKnight6499/application_pipeline_extension/pull/2), stacked on PR 1. Neither is merged; main and employer applications remain unchanged.

## Continued gap validation, October 3, 2026

Author: Yazad Madan. Four dynamic protected-side-effect cases were reproduced after the follow-up batch. Cached protection exempted a newly protected selected value, stale radio members hid replacement state, and new/revealed consent controls were absent from monitoring. Five root regressions failed before repair, including a newly introduced control before filling. Live protection and visible/radio membership checks now stop subsequent writes and redact protected collateral. Five new tests and 16 existing engine tests pass. Reordering remains allowed; topology changes need Rescan. Already-triggered portal side effects are reported without rollback. No live forms or submissions were used.
