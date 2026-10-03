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

## Acceptance still pending

DOM readback does not prove remote saving. A file input's filename does not prove remote upload completion. Neither Workday nor Greenhouse has a real employer application validated through final review. Final submission stays manual.
