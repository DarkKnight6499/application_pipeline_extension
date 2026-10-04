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
