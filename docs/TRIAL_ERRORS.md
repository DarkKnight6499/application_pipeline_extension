---
author: Yazad Madan
updated: 2026-10-30
---

# Trial failures and remaining work

This log distinguishes observed failures from untested compatibility. Keep historical findings even after a fix so future sessions do not repeat the same experiments.

## October 30, 2026: Learn page

Author: Yazad Madan. Learn page reviews current answers in the dock, flags changed answers through a dry run, and stores only checked rows after Confirm. Confirm rechecks the page and answers; a locked server comparison refuses stale KB changes. Limits: 80 pairs, 300 characters per label, 2000 per answer, and the existing 64 KB body cap. Server filtering reuses the draft block patterns and protected-field checks.

Untouched-field rule: snapshot each DOM field on its first scan. A current answer must match its last trusted input/change event and differ from that snapshot, or match a verified Fill write. Prefills and site-only writes are excluded. Replaced nodes start with a new snapshot. Custom widgets without trusted input/change events require a verified Fill.

The old accept route used global answer memory. Page-context accept and Learn now share a writer and local store at `data/company_kb/<hash of host and company>/answer_memory.json`, preceding the read-only reference matcher. With no company hint, scope is the host. Context-free legacy accept stays global. No global promotion or Resume checkout write was added.

Verified: Node content/worker harness, 2 suites; three assist unittest files, 28 tests passed. Coverage includes selection, stale review, provenance, automation, scope isolation, reference preservation, protected questions, bounds, sender validation, and HTTP guards. Python/JavaScript syntax and Git whitespace checks pass. Full pytest could not start: the specified runtime has no pytest module. No import failure required PYTHONPATH.

Unverified: live rendering/events, custom widget edits, real company-module integration, employer compatibility, remote persistence, and full-suite acceptance. No browser was opened. Sources: local code and fabricated fixtures; no external fetch. Manifest permissions are unchanged. No branch, commit, or push was created.

## Sponsorship toggle landing, October 4, 2026

Rebase conflicts in server routes, the background allowlist, and the status line were resolved by retaining both P8 record functionality and sponsorship functionality. No permission or host expansion occurred.

New browser tests first exposed stale selected sponsorship answers after a mode change and an enabled toggle during a pending fill. A further test exposed stale sponsorship reviews when reopening a page after changing the mode elsewhere. Mode changes now reset only future and combined sponsorship review entries. Cached entries carry their mode and are ignored when it differs from the session mode. The toggle is locked during filling, and Fill waits for mode saving. A failed mode save preserves the prior review.

Final validation: FULL 284 tests in 159.378 seconds, OK with two skips; PUBLIC 203 tests in 105.618 seconds, OK with two skips. Both skips require Windows file-symlink privileges. Five new browser cases and the original nine mode cases pass. Existing tests were not edited. Syntax, compilation, and diff checks pass. Resume working-tree status remained unchanged by validation.

The existing loaded-extension test stub lacks `folder` for the newly allowed session-profile request. Its helper prints an AttributeError and the panel uses its existing global-profile fallback; the test passes. This does not verify session-profile failure handling, which remains part of the queued profile-route review. Synthetic results do not establish live filling or remote persistence.

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
| Popup status wait failed under extension CSP | Replaced two inherited `wait_for_function` calls with locator text assertions after explicit approval. The synthetic pairing proof and both affected browser methods pass. | Test synchronization changed only. Production CSP and pairing behavior are unchanged. |

Latest completed validation before Greenhouse development: 76 tests passed in 46.206 seconds, with JavaScript syntax checks passing. Backend tests confirmed source trackers and references were unchanged.

## Greenhouse phase, version 0.4.0

- An initially discovered Antora posting redirected to a board marked inactive. It was rejected as the adapter reference. The public Justworks application provided an intact form instead.
- Generic scanning would include auxiliary required inputs, miss whole-section demographic protection, and label the resume upload as Attach. The dedicated adapter now scopes the form, excludes ARIA-hidden controls, protects the survey container, and resolves the hidden resume input through its exact labelled group.
- Editable comboboxes remain unsupported because the public response does not establish their live popup and selection contract. Compound sponsorship stays pending. These are visible limits rather than successful fills.
- Five new browser regressions and the extended loaded-extension inspection test pass. The full suite passed 81 tests in 50.944 seconds. JavaScript syntax checks passed.
- Public HTML inspection and synthetic verification do not establish live persistence or upload completion. Detailed evidence and the next task are in [GREENHOUSE_CONTRACT.md](GREENHOUSE_CONTRACT.md).

## Session-profile review repair, October 4, 2026

The panel previously fell back to a global profile when session loading failed, accepted malformed response shapes, and reused stale cached answers after a new application proposal. Synthetic regressions reproduced these failures. The panel now requires a valid session profile before scanning, invalidates cached rows when their sourced proposal or matching draft changes, and displays tailored employment drafts for human review without selecting them. Eleven focused regressions and 23 approved inherited mock cases pass. Live portal behavior remains unverified.

## PF4 Greenhouse completion, October 4, 2026

Nine new synthetic Edge browser tests pass. A control replaced after scanning is refused as stale. An explicit rescan registers the replacement and permits selected filling. Country and city role=combobox controls without verified popup ownership stay manual. The remaining seven cases check routing, read-only scan, selected-only fill, overwrite-off preservation, CAPTCHA gating, final-review detection, and zero submit events. No production code, inherited test, live portal, or Resume workflow file changed. Live typeahead behavior, react-select popup behavior, remote persistence, and upload completion remain unverified.

## Acceptance still pending

The independent review of stacked PRs #1 through #3 found a source-format compatibility regression and two stale integration assertions. At the reviewed PR #3 head, 168 tests produced 160 passes, 5 failures, 1 error, and 2 skips. No PR was merged. See [the detailed review](PR_STACK_REVIEW_2026-10-03.md). These results concern the proposed stack, not the production version 0.4.0 live-trial browser.

DOM readback does not prove remote saving. A file input's filename does not prove remote upload completion. Neither Workday nor Greenhouse has a real employer application validated through final review. Final submission stays manual.

## Independent synthetic probe, October 3, 2026

Baseline: `de2e51b5e424634d2be66a32bcfa5627f5e1fbef`. Full evidence, reproductions, earlier-review status, and ranked proposed fixes are in PROBE_REPORT_2026-10-03.md (original kept in Git history). No production fix has been applied at this checkpoint.

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

Root corrected two test assertions: panel text resides in its shadow root; the omitted-protection count is three because it includes the password and both boundary controls. Final result: 61 passed, 81 environment skips, 142 total, zero failures/errors in 46.816 seconds. Both visible Edge trials passed in 15.173 seconds; submission counters remained zero. Screenshots were inspected and remain local. Syntax/diff checks passed. See follow-up evidence and deferred findings (original kept in Git history).

Follow-up is published as [open PR 2](https://github.com/DarkKnight6499/application_pipeline_extension/pull/2), stacked on PR 1. Neither is merged; main and employer applications remain unchanged.

## Continued gap validation, October 3, 2026

Author: Yazad Madan. Four dynamic protected-side-effect cases were reproduced after the follow-up batch. Cached protection exempted a newly protected selected value, stale radio members hid replacement state, and new/revealed consent controls were absent from monitoring. Five root regressions failed before repair, including a newly introduced control before filling. Live protection and visible/radio membership checks now stop subsequent writes and redact protected collateral. Five new tests and 16 existing engine tests pass. Reordering remains allowed; topology changes need Rescan. Already-triggered portal side effects are reported without rollback. No live forms or submissions were used.

Independent review found a new filter regression: native button type was checked before its supported combobox role. A scan-count regression failed, then passed after role-first filtering was restored. All six dynamic tests pass. Twelve listbox tests and bound-row reorder/identity probes remain passing. Unsafe action dropdowns remain governed by the existing bounded adapter contract.

L6-02/L6-03 mutation tests confirmed all three weaknesses: empty protected scans, history scans containing only two asserted dates, and truncated history results survived old assertions. New exact field/result coverage rejects each mutant; the unmutated synthetic fixture passes. Four standalone Edge tests pass in 23.943 seconds. Target methods are extracted without executing integration imports or private-source setup. This verifies those assertions, not the skipped external workflow suite.

Duplicate required tracker headers overwrote company/role/link context and allowed first Status Applied to be replaced by second Status New. Conflicting ID columns also selected by one position while reporting a different mapped identity. Five duplicate-header subcases failed before required-header uniqueness checks; empty-workbook handling initially raised StopIteration. Named row selection and clear missing-header errors now pass all five public tests. Reordering and exact-ID selection remain sound. Only temporary fabricated workbooks were used.

L2-01 was reproduced by writing a fabricated JD/session into a source Projects descendant. L2-02 is now verified rather than probable: a temporary Windows junction redirected actual session reads, resume bytes, and approval writes outside the sandbox. The junction itself was removed nonrecursively and its target survived. Six initial regression failures preceded path guards. Review reproduced a source nested under sandbox overlap; both ancestor directions are now rejected. Eight tests pass and two physical file-symlink tests skip for missing privilege. Portable resolve mocks verify per-artifact guard branches. Existing HTTP tests pass. Normal create/import/build tests use explicit fabricated workflow stubs; they do not validate genuine audits or builders. Hardlinks and concurrent local filesystem replacement remain outside this guarantee.

Final continued discovery passed 84 tests and skipped 83, 167 total, no failures/errors in 75.783 seconds. Two skips require file-symlink privilege; the other 81 require external workflow. Visible Edge trial passed both tests in 16.963 seconds with no submissions. Syntax/diff checks passed. Continued report (original kept in Git history) maps original findings to current repairs and preserves live/filesystem limits.

Final instruction audit found that unrelated reference/tracker-looking paths still passed the overlap policy. Three fabricated `_Reference`, `Applications`, and `Applications.xlsx` destination cases failed before reserved path components were refused case-insensitively before mkdir. Nine path tests pass, two physical symlink tests skip, and four HTTP tests pass. This completes the named-directory portion of L2-01; ordinary external sandboxes remain supported.

Post-audit suite: 168 total, 85 passed, 83 skips, zero failures/errors, 75.249 seconds. Review verified six mixed-case reserved destinations refused and four ordinary or similarly prefixed names remained usable. [PR 3](https://github.com/DarkKnight6499/application_pipeline_extension/pull/3) is open and unmerged, stacked on PR 2. No source/main/tracker changes or employer submissions occurred.

## P7 progression and upload safety, October 4, 2026

The P7 branch was rebased onto `80490bf` without conflicts. Review then found two unsafe cases: a native submit control labelled Next could be clicked, and a second upload with the same filename skipped checksum validation. New synthetic regressions failed on both cases. Guarded Next now excludes native submit controls and rechecks the human gate and final-review state immediately before clicking. Same-name upload skip now verifies incoming bytes, attached bytes, and current control structure before reporting success. A detached upload control fails after the asynchronous checksum step. Six new tests pass; no existing test was edited.

Acceptance: FULL 304 tests, OK with two Windows symlink-privilege skips; PUBLIC 223 tests, OK with the same two skips; JSCHECK, PYCHECK, and `git diff --check` pass. `rg -n submit portal_pipeline/extension/progress.js` returns the denylist plus explicit native-submit checks required by safety review. The older plan check expected only denylist strings, so this stronger fail-closed guard changes that search output. Synthetic tests record zero submit events. No employer page or application submission was used.

Both full and public discovery also log a handled request-thread exception in the loaded-extension sponsorship panel fixture. Its `SimpleNamespace` pipeline stub lacks the `folder` method used by the session-profile GET route. The panel catches that request failure and falls back to the global fabricated profile; both browser tests pass. The stub mismatch remains a test-harness limitation. It does not establish live behavior for the per-session profile route.

## PF5 synthetic regressions, October 4, 2026

Three PF5 tests exposed phase gaps before repair. A Phenom page with hCaptcha or Turnstile returned no human gate, a Next button beside Submit, Apply, Finish, or Review and Submit was not reported as final review, and a Phenom answer sheet was labeled generic. The adapter now composes generic gate detection, gives final controls precedence in reporting, and maps only the two registered hosts in answer-sheet classification. After the P7 rebase, a new progression test failed because the adapter still reported Next beside Certify. It now delegates denylist and Next classification to P7 while retaining Phenom final-control markers. All 18 targeted Phenom tests passed in Edge. Final FULL 322 and PUBLIC 241 passed with two Windows symlink-privilege skips each. Five replay tests, JavaScript syntax, Python syntax, and diff checks passed. The loaded-extension test still logs a handled session-profile stub exception as described above. These checks use fabricated pages only. Real apply hosts and markup remain UNVERIFIED.

## Manual-field, attestation, and existing-upload regressions, October 4, 2026

Author: Yazad Madan.

The user authorized isolated parallel lower-tier agents and coordinator integration. PF5 uses fabricated Phenom pages only; its exact registered career-site hosts remain unverified apply hosts. Placeholder export now keeps unanswered selects empty and pending. A new native-select panel test writes only the explicitly selected field and instruments actual submit clicks and events, both zero.

Five engine regressions proved that preflight manual IDs must be passed through the fill boundary, refused before adapter calls, and included in collateral monitoring even when forged into selections. Six attestation regressions proved selects, radios, text inputs, and signature heading regions need the same manual protection as checkboxes. No existing assertions were edited.

Three upload regressions reproduced matching-file success on a cover-letter target, a multiple-file target, and a file replaced during asynchronous hashing. Two further regressions reproduced a late multiple attribute change and an already attached file rejected by portal validation. The skip path now revalidates the target, exact attached file identity, and portal validation before reporting that the reviewed local file is already attached. This does not verify remote upload completion.

Session-profile review is prepared separately on fix/session-profile-review at c49d86c. Two valid-profile cases pass; four new regression cases remain red on the current implementation. Existing synthetic mock routing and setup edits require Yazad approval under the handoff working-method rule. The panel still silently falls back to the global profile on scoped-profile failure, cached review values can mask saved application overrides, and tailored drafts are not shown. Do not claim that review item is fixed.

Independent synthetic review then reproduced signature headings above nested fieldsets and ordinary legends hiding inherited signature context. Three new ancestry tests cover both blocked signature cases and an ordinary contact field after a later semantic heading. Relevant ancestor headings now protect nested signature fields; an ordinary legend cannot erase that protection. A later Contact heading still ends the signature region. No inherited tests were changed.

The first combined stack passed FULL 338 tests in 210.069 seconds and PUBLIC 257 tests in 152.473 seconds, each with two symlink skips. After the ancestry and upload review additions, FULL 343 in 209.672 seconds and PUBLIC 262 in 155.194 seconds each failed one inherited hCaptcha replay case. Its ordinary First name field lost its profile key because a body-level heading containing captcha was included in all protected-word matching. This is a production regression, not a stale assertion. The repair keeps heading-based context specific to attestation protection and preserves the existing CAPTCHA write gate. The replay assertion remains unchanged. Final post-repair validation is recorded below.

The heading-specific repair passed PUBLIC 263 tests in 153.651 seconds with two skips. FULL 344 tests in 207.057 seconds had one error in the existing loaded-extension pairing test: Page.wait_for_function hit the extension Content Security Policy unsafe-eval restriction. The unchanged test passed alone in 6.837 seconds. No inherited test was edited to hide that known intermittent harness issue.

A final new regression also exposed the multiple-file race during a first upload, when no file was attached yet: the helper could write after the portal enabled multiple during the checksum wait. A second multiple check immediately before assigning files now refuses the write, leaving the target empty. The new test failed first and then passed with ten related upload checks. Final full and public discovery run sequentially to avoid adding concurrent browser load.

Final code at dd92b4b: FULL 345 tests in 198.366 seconds still has one CSP harness error and two symlink skips. Unlike the earlier isolated pass, the latest isolated rerun also fails at test_browser.py line 863. The wait predicate itself is compiled through eval in a chrome-extension page; its unsafe-eval prohibition must not be loosened in production. Escalated review prepares a test-only locator wait replacement for approval. Do not describe the final FULL run as green. The safety batch is held off main pending validated harness resolution.

Final validation at code commit dd92b4b: FULL 345 tests in 198.366 seconds has one inherited CSP harness error and two symlink skips. The isolated case failed again after an earlier isolated pass. PUBLIC 264 tests in 148.794 seconds passes with two skips. JSCHECK, PYCHECK and diff checks pass. No production safety rule was weakened, no inherited test was edited, and no live portal actions occurred. The completed code and failure evidence are saved on integration/validated-portal-phases, held off main until the inherited test wait can be repaired with approval and FULL rerun successfully.

Escalated harness review saved a passing synthetic real-extension pairing proof at b39cb5f on test/csp-safe-popup-wait. The exact proposal is https://github.com/DarkKnight6499/application_pipeline_extension/blob/test/csp-safe-popup-wait/docs/CSP_POPUP_WAIT_PROPOSAL.md. It replaces only two existing popup waits in test_browser.py with locator assertions, retaining the Paired. prefix and limited to Workday substring conditions plus a 30-second timeout. The proposal also adds imports for re and expect. No production or inherited tests were edited; approval is pending under handoff working method step 3.

## Approved CSP repair and safety validation, October 4, 2026

Author: Yazad Madan. Yazad explicitly approved both prepared test changes. The two popup waits retain their original text conditions and 30000 ms timeout through locator assertions. Production CSP is unchanged. The final safety stack now passes FULL 346 tests in 212.146 seconds and PUBLIC 264 tests in 153.942 seconds, each with two expected Windows symlink skips. JSCHECK, PYCHECK, and diff checks pass. This supersedes the earlier held-safety status. The session-profile mock edits are also approved, but that implementation awaits separate coordinator integration and validation. No live portal actions occurred.

## Version 0.8.0 session-profile and PF4 integration, October 4, 2026

Author: Yazad Madan. Three isolated parallel tasks completed: approved CSP test-only repairs, session-profile review persistence, and PF4 Greenhouse synthetic completion. Coordinator review added malformed scalar-value refusal and verified that a changed proposal resets edited answers, selection, and overwrite together. No inherited assertion was altered by the five approved mock setup repairs. Changed and legacy snapshots reset review choices; unchanged sourced proposals preserve human edits. Tailored drafts are displayed for review without automatic insertion or selection. Greenhouse stale controls remain refused until rescan; unsupported country/city typeahead stays manual.

Final code at c3f8487 passed FULL 368 in 226.742 seconds and PUBLIC 286 in 170.509 seconds, each with two expected Windows file-symlink privilege skips. Replay 4 passed in 7.749 seconds; JSCHECK, PYCHECK, and diff checks pass. The old missing-folder mock exception no longer appears after the approved synthetic session-folder setup. Manifest 0.8.0 adds no permissions or hosts. Workday and Oracle export directories are absent in the primary checkout, so real post-login compatibility remains unverified. No live portal action, application submission, candidate-data publication, or Resume workflow mutation occurred. This supersedes earlier pending approvals and held-validation notes.

## Local version 0.9.0 preparation, October 5, 2026

Author: Yazad Madan. Branch integration/pf1-pf2-preparation in D:\Code\application_pipeline\worktrees\integration_next contains uncommitted preparation based on 47bc4a1. Workday registration moved to its dedicated file without host or behavior changes, with 14 new tests. Oracle remains outside production injection and routing, defaults to answer_sheet_only, refuses text and upload writes, and has 13 new tests plus three invented replay pages. Its pure mode transition is nonpersistent. The application-lifetime downgrade design is documented, not implemented.

Five new tests reproduced actual Next clicks in answer-sheet mode, including a mode change during the awaited sweep. Entry and immediate pre-click mode checks now refuse those actions. Twenty inherited progression tests passed unchanged. Only the shared harness script-name list changed in an existing test support file; inherited assertions stayed unchanged.

FULL 400 in 221.495 seconds and PUBLIC 318 in 165.735 seconds pass, each with two expected Windows symlink-privilege skips. Replay 4 in 7.226 seconds passes. JSCHECK, PYCHECK, and diff checks pass. Manifest 0.9.0 changes version only, with unchanged permissions. New fixture metadata names Yazad Madan. No live employer page was opened, filled, or submitted. Current work remains uncommitted and unpushed at Yazad's request.

The Resume status fingerprint changed during validation as additional application artifacts appeared; the existing reference change flags stayed the same. This run does not claim an unchanged whole source checkout. Phase code and test additions are confined to the extension workspace; the private plan receives only the authorized section 9 handoff entry. Current resume generation remains independent.

Next: commit and push only when requested. Obtain Workday page exports and establish a reviewed Oracle inspection path before collecting Oracle exports. Complete application-scoped CAPTCHA downgrade persistence before enabling Oracle fill. P9 still requires merged PF1/PF2 and 50 approved real pending wordings.

## October 5, 2026: application-scoped restriction persistence

Author: Yazad Madan.

The version 0.9.0 checkpoint was pushed to main as 7310dda before this phase. Version 0.10.0 adds an audited-application restriction sidecar, an immutable extension journal, and opt-in engine and Next checks. Oracle remains unrouted, outside production injection, and answer-sheet only. No manifest permission or inherited test changed.

The initial browser integration tests exposed thrown initial refusals, loss of earlier results when a later mode check denied a field, and inspection-message precedence. Coordinator fixes return structured refusals, preserve earlier results, and keep the inspection denial before the new tab check. Newly authored fixture mistakes were corrected in the new file only. One coordinator optional-chain assignment caused syntax errors and was corrected. A late text-length test reproduced an actual write after maxLength changed during the mode await; the final pre-assignment check now prevents that write. Twenty focused browser tests pass in 7.223 seconds. Backend has eight new tests with no new skips.

Final FULL passes 428 tests in 223.978 seconds with two expected Windows symlink skips. PUBLIC and replay results are recorded in the final handoff and STATUS_AND_NEXT_STEPS.md. The new browser persistence tests mock Chrome APIs and helper responses on fabricated pages. They simulate worker reload and helper port changes; they do not establish actual Oracle MV3 lifecycle behavior. Existing loaded-extension tests remain unchanged in acceptance.

Storage failures block current writes. If both durable stores fail and process memory is later lost, no recovery of an unpersisted restriction is claimed. Helper locking is process-local. Remote field persistence, remote upload completion, malicious filesystem replacement, and real portal compatibility remain unverified. See APPLICATION_MODE_SECURITY_NOTES.md and APPLICATION_MODE_VALIDATION.md.

Source fingerprints changed during this session, so whole-source immutability is not claimed. This phase changes no source profile, builder, tracker, or application artifact; it appends only the authorized private plan handoff. No live employer page was opened, filled, or submitted. Next evidence: Workday structure exports and one Oracle hostname for reviewed inspection access. P9 prerequisites remain unmet.

Final PUBLIC passes 346 tests in 174.403 seconds with the same two expected skips. Replay passes four tests in 5.890 seconds. JavaScript syntax, Python compilation, manifest permission comparison, and diff checks pass.

## October 5, 2026: parallel long-form and actual MV3 lifecycle work

Author: Yazad Madan.

Long-form module tests first failed because the module was absent. Coordinator tests then reproduced nonexistent helper routes and direct engine writes without draft validation. Review found scaled and leading-decimal numbers accepted as bare digits, and helper-supported prompt wording missed by engine enforcement. Numeric parsing and prompt matching were corrected; a regression now compares every helper trigger word with the engine matcher. A stale portal-limit regression later reproduced a write after validation awaited; the engine now checks the same live limit and canonical UTF-16 count before assignment. One newly authored checkbox locator timed out and was corrected without changing inherited tests. Thirteen route, engine, and panel cases pass in 5.450 seconds; five backend and six broker/report cases also pass.

The new loaded MV3 test uses actual Chrome storage and messaging on an invented example.invalid application. It preserves the restriction after helper POST failure, page reload, persistent browser context reopen, and helper port change; another application does not inherit it. It records zero field writes, Next clicks, Submit clicks, and submit events. A temporary-copy mutation removing durable journal intersection failed after reopen. Integration caught a missing Path import removed after the agent's earlier successful run. Restoring it and rerunning the exact test passed, including the coordinator run in 15.134 seconds. The helper HTTP behavior is fabricated; idle worker suspension, remote storage, and real portal compatibility remain outside this test.

An incorrect Git line-ending override produced a false whole-file trailing-whitespace report. The repository's normal settings pass diff check. No line-ending rewrite was made. Initial combined FULL passed 452 tests with two expected skips before the new stale-limit case; final acceptance reruns after that fix. Manifest 0.11.0 changes version only. No inherited tests, real portal hosts, production Oracle routing, or source workflow files changed. No model calls or live portal actions occurred.

These checks screen numeric expressions and length, not truth or role attribution. Human review remains required. Cover letters stay in the existing Resume builder; current Resume generation remains independent. Next: structure exports, reviewed Oracle inspection access, actual upload/remote field evidence, and the 50 approved pending question wordings required before P9.

Final combined acceptance: FULL 453 in 249.239 seconds and PUBLIC 371 in 188.060 seconds, each OK with only the two expected Windows symlink skips; replay 4 in 5.988 seconds OK. JSCHECK, PYCHECK, and normal Git diff check pass. Four monitored tracker/reference hashes match their pre-validation values.

## October 18, 2026: live Citi Workday inspection gaps

Author: Yazad Madan. Contributor handoff published October 20, 2026.

- Contact export omits required Country, State, and Phone Device Type button menus. Referral source and phone country code search dialogs appear as ordinary text inputs with no adapter.
- Added employment/education export records 55 controls, including 24 date components represented as text and no attributed records. Required degree menus and the visible resume picker are absent. Zero unsupported-spinbutton warnings do not establish date support.
- Intake rejects long mixed-case structural IDs as token-like. Raw exports stay private; no validator weakening or production fix was made.
- Native coordinate selection chose a neighboring country during correction. Fresh exact accessibility selection and readback corrected country and dependent phone code before saving. One earlier unexpected country change has no established cause.
- Native UI entry advanced contact and experience pages, but the extension stayed Inspect-only. No extension live-fill, upload, or final-review acceptance is claimed.

See [the contributor handoff](LIVE_WORKDAY_HANDOFF.md) for evidence counts, source precedence, private artifact locations, pending questions, and ordered next work. Earlier trial entries remain historical.

## October 20, 2026: branch consolidation validation

Author: Yazad Madan. The historical handoff merge conflicted; resolution preserved the current handoff and retained the old review separately. Patch-equivalent or superseded branch ancestry was consolidated without reverting runtime behavior. FULL 573 and PUBLIC 491 finish with zero failures or errors, with two and 19 documented skips respectively. Export-intake rejection messages are expected negative-test output. No live scanner gap was repaired by this merge. See [branch consolidation](BRANCH_CONSOLIDATION_2026-10-20.md).

## October 22, 2026: contributor demo validation

Author: Yazad Madan. The new demo test initially failed at import, then at the inherited browser harness network block, and then at a nonexistent rescan control after fixture navigation. Corrections are confined to the new test: include the helper import path, allow only the demo loopback origin, await the fill report, and reopen the built-in panel. All four targeted checks pass. A fresh-environment actual MV3 exercise also paired, filled one selected dummy field, attached the synthetic DOCX, and observed zero submits. No audit, tracker, real resume, or employer compatibility claim follows from this demo. Dependency installation and pip check succeed. Fresh acceptance: FULL 577 in 339.595 seconds with two expected skips; clean-environment PUBLIC 495 in 165.848 seconds with 19 expected skips. No failures or errors. Export-intake error messages are expected negative-test output. See [contributor instructions](../CONTRIBUTING.md) and current status for reproduction.

## October 30, 2026: per-field assist, browser-free validation

Author: Yazad Madan.

- Added a separate assist route and isolated content script under the owner's current request. Existing adapters and navigation behavior remain independent. The manifest invariant now permits exactly the new assist script; a separate structural test checks its complete host allowlist.
- Initial eager service startup broke synthetic pipelines without a data property and added unexpected token files to existing test outputs. Lazy initialization for existing server callers fixed both regressions. Production startup explicitly initializes assist and stores its token locally.
- Rejected unread HTTP bodies caused intermittent Windows socket resets. Bounded rejected bodies are drained without parsing; the oversize test sends only declared length and confirms rejection before a body is sent. No oversized body is parsed.
- Pytest works through the supplied private dependency path. Its default temporary directory was inaccessible to the sandbox account; a fresh external TemporaryDirectory fixes that environment error without changing tests.
- Focused assist API, manifest, and Node-only control checks cover resolution, blocked labels and options, queue preservation, authentication, readback, duplicate buttons, stale fields, explicit overwrite, draft acceptance, popup ownership, native setters, and worker isolation. Broader pytest execution reports 546 passed, 613 skipped, one failure, and two collection errors. The remaining failure and both collection errors require missing Playwright. Full-suite green status is unverified.
- Primary source contracts were read without copying personal values: company_kb exposes find_answer; profile name is header.name, with education, certifications, and experience company fields separately allowlisted. The official Claude CLI reference confirms built-in tool restrictions and a separate MCP deny flag. Windows npm shims are bypassed through Node to avoid shell interpretation.
- No Git, Edge, employer page, or real Claude draft call was used. Normal-profile injection, real React/Workday behavior, CLI login, and remote persistence remain unverified. Drafts remain local proposals until explicitly saved; signatures, attestations, and final actions remain manual.

## October 30, 2026: one Fill per page

- A segmented date field (month, day, year inputs) got three Fill buttons that overlapped the digits. Segment inputs inside one form group are now one field, filled together from an MM/DD/YYYY answer; an answer without the matching number of parts is left unfilled.
- Per-field Fill moved outside the field's right edge and shows only for the focused field. A docked "Fill page" button fills every empty field in page order, never overwrites, never clicks Next or Submit, and reports filled, left alone and not filled.
- Verified only with the browser-free harness. The real Workday date widget, focus placement and live fills are unverified.

## October 30, 2026: unanswered queue

Author: Yazad Madan.

- Added `miss_log.py` and `miss_report.py`, with small hooks in assist API, worker, and content script. Unanswered server results and fire-and-forget extension notifications append metadata-only snapshots to `assist_misses.jsonl` beside the assist token. Each normalized label and host has a cumulative count and first/last UTC timestamps. The report combines hosts and companies, sorts by count, and includes bounded sample option lists.
- Caps: label 300 characters, 40 dropdown options, 120 characters per option, company hint 150 characters, host 253 characters. The worker derives the host from the sender and forwards only the five allowed metadata fields. No field values, answer values, page URLs, or tokens enter the new log. Server filtering checks labels and supplied options before truncation, excluding credentials, signatures, attestations, SSN, eligibility, and self-ID questions. Existing question logging and the existing learning queue are unchanged.
- Run `python portal_pipeline/miss_report.py` for text, add `--json` for JSON, or `--data DIRECTORY` for another assist data directory. `--resolve "Question label"` appends a resolution event and hides that label across all hosts. A later sighting reopens it with historical counts. Counts measure reports, not distinct fill attempts: one failed fill can produce both a server sighting and an extension notification.
- Initial new tests failed because the new module was absent. Browser-free harnesses then exposed CRLF-sensitive source injection. Both harnesses now normalize source newlines before instrumentation. Queue write failures preserve the answer outcome; malformed log contents remain an explicit report error rather than silently discarding evidence.
- Verified synthetically: deduplication, caps, sensitive labels and options, concurrent counts, restart persistence, cross-host report ordering, resolution, endpoint token/Origin/Host/body-size boundaries, metadata allowlisting, no-answer and no-match notifications, pending or failed logging without blocking fills, and successful fills without miss notifications. The original Node harness and new miss harness pass. Focused unittest acceptance passes 32 tests across all three existing assist files and the new miss file. Full pytest with the supplied private dependency path stops at two existing collection errors because Playwright is missing; full-suite acceptance remains unverified.
- Source contracts were read from the local `company_kb.py` and `kb_fill.py`: assist calls the read-only `find_answer` matcher and reads company JSON questions and portal hosts. No private values were copied. No live browser, employer page, real draft CLI, source workflow write, commit, push, or branch creation occurred. Live delivery, portal wording coverage, and crash recovery of a partially written JSONL line remain unverified.

## October 30, 2026: per-track essays

Author: Yazad Madan.

- Added conservative classification for alm, capital, fpa, model_risk, quant, and treasury_ops. Multiple family signals return no family. Company names and URL queries are not classification evidence; the URL path is a fallback when heading context has no signal.
- User-approved templates take precedence over generic answers for matching free-text motivation, about_yourself, and good_fit questions. Only {company} and {role} are substituted. Missing placeholders, absent or invalid templates, unknown kinds, and ambiguous tracks retain existing KB, memory, and draft fallback behavior. Eligibility, self-ID, other blocked labels, and protected fields cannot use essay templates; existing reviewed-answer rules remain unchanged.
- The new CLI creates essay_templates.json in the assist data directory only when used. No personal content or starter essays are included. Add requires explicit user approval; returned essays always have draft status and retain the existing Save this answer link. Example syntax: `python portal_pipeline/essay_templates_cli.py add alm motivation --text-file <approved-utf8-file> --approved`. Use `list [family]` or `remove <family> <kind>`; put optional `--data <directory>` before the command.
- Heading context excludes native and editable form controls. Job titles are capped at 300 characters and page snippets at 1500; the server rejects oversized or non-string context. Template text and expanded answers are capped at 2000 characters; template-store reads are capped at 256 KiB. The worker already forwards optional context, so background.js and server.py need no edits.
- Verified: Node content and worker harness passes. Focused pytest passes 30 tests and 66 subtests; unittest fallback passes all 30 tests across the three assist files and the new essay file. Coverage includes six families, ambiguous classification, question kinds, literal placeholder substitution, missing and malformed stores, approval, CLI add/list/replace/remove, persistence, fallback, HTTP context rejection, size caps, blocked labels, heading sanitization, draft saving, and worker forwarding. Python syntax, JavaScript syntax, and Git whitespace checks pass.
- Initial harness execution failed because its LF-only instrumentation marker did not match this CRLF checkout. Normalize line endings when reading the fixture source; assertions remain intact. The specified Python lacks pytest by default; the supplied _pylibs path loads it. Full pytest stops with two collection errors because test_browser.py and test_csp_popup_wait.py import missing Playwright. Full-suite acceptance remains unverified.
- Read-only local contracts confirmed: bb.py FAMILIES contains the six family keys, resume draft files use the existing content schema, and assist_api calls company_kb.find_answer without using its writers. No private values were copied. No external data, browser, real model call, submission, branch creation, commit, or push occurred. Live heading discovery, employer persistence, and the concurrent Learn page merge remain unverified.

## October 30, 2026: reviewed question aliases

Author: Yazad Madan.

- Learn review shows `similar to: <stored question>` and an unticked alias checkbox only for an unambiguous matching answer. Confirmation recomputes the candidate on the server under company and global memory locks. Conflicting answers, forged matches, stale reviews, and existing alias replacements are refused. Unticked rows retain ordinary learning behavior.
- Similarity uses Unicode normalization and conservative presentation-prefix removal, with a 0.85 threshold. Content words must remain identical and in order; changing authorization, polarity, time, numbers, minimum/maximum, or first/last cannot create an alias. Eligibility, self-ID, credentials, signatures, attestations, and sensitive options remain excluded at the server.
- Alias records contain wording, target keys, and answer fingerprints, without answer values. Company aliases live beside that company's answer memory in `question_aliases.json`; global aliases require an existing global target and never promote company answers. Changed or missing target answers disable lookup. Existing direct answers retain precedence. Removing an alias leaves its target answer intact.
- CLI: `python portal_pipeline/question_alias.py --data <assist-data> list`. Remove with `python portal_pipeline/question_alias.py --data <assist-data> --scope <global-or-company-hash-from-list> remove "Question wording"`. Listing includes company scope hashes and no answer values.
- Baseline inspection found two contradictions with the requested safety rules: accept could silently replace answers, and stored self-ID answers were fillable. Accept now requires a matching `previous_answer` for replacements; stored eligibility and self-ID answers remain manual. The affected legacy test and two explicit replacement fixtures were updated. New reviewed global intent saves retain `question_label`, because existing intent records otherwise contain only opaque IDs. Old intent records without question wording do not produce alias suggestions. Company JSON reference questions support aliases without modifying the reference store; custom matcher results without stored question wording are excluded.
- Initial new tests failed because the module was absent. An expanded intent-target test then exposed the missing original wording; retaining `question_label` fixed it. A reference fixture accidentally exercised the existing overlap matcher before alias resolution; using a distinct wrapper tests the alias path directly. The specified Python has no pytest module by default. The supplied `_pylibs` path works; pytest uses an external temporary directory and disables its repository cache.
- Verified: the required four assist test files, new alias tests, and existing essay tests pass together: 66 tests and 135 subtests. The existing content/worker harness and miss harness pass. Alias tests cover opt-in and unticked behavior, similarity positives and negatives, scope isolation, global intent targets, read-only reference targets, restart persistence, conflict refusal, stale targets, blocked stored answers/options, explicit replacement checks, CLI listing/removal, and worker forwarding. No field values enter logs.
- Unverified: live DOM rendering, employer compatibility, remote persistence, full-suite acceptance, and integration with the other concurrent jobs. No browser, real model call, external data fetch, private workflow write, navigation click, branch, commit, or push occurred. Sources that worked: local source code and fabricated fixtures. No external source was attempted. Background worker, server routing, manifest permissions, and answer-memory module remain unchanged.

## October 30, 2026: corrections after Assist Fill

Author: Yazad Madan.

- Added `corrections.py` and small hooks in assist API, worker, and content script. A trusted edit after a retained Fill sends one correction 180 ms after trusted blur. Repeated input, change, and blur events share that correction. Refocusing cancels the timer. Later edit sessions can record a changed choice; a new retained Fill resets the baseline. Scripted events, unchanged or empty answers, stale labels, navigation, automation, and changed readback produce no correction.
- Learn page puts corrected fields first, flags them `corrected`, and checks them by default. Existing review and previous-answer checks remain in place. Recording corrections never writes answer memory or the read-only reference. Wrong and user values stay in the local `assist_corrections.json` store; the worker allowlists correction fields and derives host from the sender. No values enter question logs or report output.
- Counts use exact normalized question, host, and normalized company hint. Two corrections to the latest user value return a draft with `reason: corrected`, before KB and essay lookup. Different wrong values contribute to that user-value count. A newer user choice with only one correction suppresses the older suggestion. Draft saving still requires explicit user action.
- Eligibility, self-ID, sensitive labels, protected types, and blocked question options cannot be recorded. The inherited API explicitly allowed stored self-ID filling; this conflicted with the current task rule. Server lookup and acceptance now reject eligibility and self-ID even when stored, and the conflicting regression now verifies rejection. Other existing reviewed-answer behavior remains unchanged.
- Report: `python portal_pipeline/corrections.py --data <assist-data-directory>` lists questions by count, with host and company. Add `--json` for metadata-only JSON. Atomic writes and shared locks preserve concurrent counts and restart persistence. Invalid stores fail explicitly with a generic error, without printing values.
- Verified synthetically: all three Node harnesses pass, including the new `assist_correction_harness.js`. Focused pytest across the four requested files and new correction tests passes 48 tests and 96 subtests. Python and JavaScript syntax and whitespace checks pass. Coverage includes debounce, trusted events, scripted writes, Learn ordering, stale context, worker boundaries, blocked labels/options/types, count isolation and concurrency, the two-correction rule, unchanged answer memory, CLI privacy, and HTTP token/Origin/Host/method/body limits. Python lacks pytest by default; the supplied `_pylibs` path works. Initial checks caught a corrected flag reset after a duplicate event, an overbroad blocked-label test, and a Windows socket reset from sending a GET body. The flag and tests were corrected.
- Unverified: live browser events, real portal widgets, loaded MV3 delivery, employer persistence, and helper-offline recovery. Failed notifications are not retried automatically; the current corrected answer remains available in Learn page. The full repository suite was not run. No external data, live browser, real draft CLI, source workflow write, submission, branch, commit, or push was used.
