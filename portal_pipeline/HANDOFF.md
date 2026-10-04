# Portal development handoff

Date: October 3, 2026.

Current repository: `D:\Code\application_pipeline_extension`, remote `https://github.com/DarkKnight6499/application_pipeline_extension.git`, branch `main`. The user requested publication to this repository and commits after each completed phase. The initial export contains only portal code, research, and trial reports. It does not contain the private Resume Git history or candidate data.

Provenance: the original prototype worktree is `D:\Code\Resume_portal_pipeline`, branch `feat/portal-pipeline`, baseline `1b7827d`. Leave that worktree, the independent `Resume_portal_trial` worktree, and unrelated files intact. Use `D:\Code\Resume` as an explicitly configured, read-only workflow source.

## Implemented

- Read-only profile resolution from the master, application boilerplate, and authoritative employment date references. Every proposed fact carries its source. Separate sponsorship answers and Axis sub-role dates are preserved.
- A localhost dashboard with a paired API, sandbox JD intake, manually reviewed content editing, existing resume builder reuse, ATS and page-fit checks, metadata checks, and a Word visual-review gate.
- Import of a single explicitly selected application folder through the existing full audit. The importer verifies the exact Application ID and copies the resume without writing the source or tracker. Source fingerprints and tracker context are checked again before attachment.
- An optional employer posting URL override supports tracker links that redirect to another portal origin. The original tracker link stays unchanged and is still checked for drift.
- A Manifest V3 extension with a user-triggered scanner and an extension-owned side panel. Individual field and section selections, edited answers, and per-field overwrite choices persist for that session and page.
- Native form filling with exact option matching, question fingerprints, DOM readback, validation feedback, collateral-change detection, and checksum-verified resume attachment.
- Version `0.2.0` adds a bounded select-only ARIA listbox adapter with stable popup ownership, exact option matching, lazy popup support, and protection against submission controls. It does not establish a Workday-specific adapter contract.
- Version `0.3.0` replaces history assignment by DOM order with explicit per-row employer/role or school choices. A manual-answer mode is available. Duplicate source assignments, replacement rows, and changed row identities are rejected. Changing a row choice clears its old edits and selection.
- Verified month/year date components can populate separate history controls. English month labels and numeric month labels are matched against the actual options without interpreting opaque values as calendar numbers. Missing education start dates and day components are not invented.
- A page permits only one active fill. Review controls and Rescan wait for its result, while structure export remains available. History-scoped questions no longer borrow personal contact or prospective salary answers.
- A structure-only inspection export supports the next real-portal walkthrough. It omits entered answers, profile proposals, option text, protected fields, and URL query strings. Inspecting does not reset an active scan or open dropdowns.
- Version `0.3.1` adds a dedicated **Inspect page only** popup action. Its panel works without helper pairing, candidate profile loading, or application import. It lists structural controls and exports each manually navigated page. The page bridge rejects candidate scans and fills originating from this inspection panel. Employer scanning in the popup is now restricted to Workday.
- Version `0.4.0` adds Greenhouse to the popup and injects its dedicated adapter. The adapter scopes one unique hosted application form, excludes ARIA-hidden internal inputs, protects the whole demographic container, and recognizes the labelled hidden resume input. Native selected filling and checksum-verified resume attachment pass synthetic tests. Editable dropdowns and remote upload completion remain manual.
- A three-page synthetic Workday fixture containing five employment rows and deliberately unsupported or protected controls. Navigation and submission remain manual.
- Backend, import, and browser integration tests, including an actual loaded extension in Chromium. All production tracker and reference writes remain outside the prototype.

## Acceptance status

The prototype proves the local profile, review, selected-fill, and audited-resume handoff mechanisms. It does not establish a complete real employer application on either Workday or Greenhouse. The user explicitly requested the second portal track. The Greenhouse contract was inspected from the public Justworks form and its supported structures were verified on synthetic fixtures. Lever and Oracle remain outside scope.

The initial portal priority remains unconfirmed. Workday is the development assumption because the synthetic fixture exercises its likely field categories. No account login, live employer form filling, or application submission occurred.

## Next exact task

Connect a real browser and continue one employer-specific walkthrough at a time. Workday still needs a selected employer URL and real form inspection. Greenhouse has the public Justworks structural reference, but its editable dropdown and upload completion contracts need rendered browser observations. Use **Export field structure** and follow [INSPECTION.md](INSPECTION.md). Record real page behavior and final-review persistence without submitting. See [GREENHOUSE_CONTRACT.md](../docs/GREENHOUSE_CONTRACT.md) for that track's next exact control.

The latest session attempted a public Workday reference inspection through the browser tools. Edge was unavailable and the browser inventory returned no connected browsers. A public posting fetched through web search exposed no form content, so it does not provide a verified adapter contract. Do not replace live inspection with assumptions or another generic feature cycle. The new inspection-only mode removes the import and pairing prerequisites for Yazad's first walkthrough in his own browser.

Implement the next demonstrated unsupported control behind the current engine, with a representative fixture and checks for unselected fields and submission boundaries. Keep each completed phase independently validated, documented, and committed. Maintain separate live acceptance evidence for Workday and Greenhouse.

Continue preparing real resumes through the current pipeline and use audited import for browser handoff. The sandbox builder remains a development tool. Do not make current resume generation depend on this unfinished extension.

## Known limits

- Editable or otherwise unsupported custom dropdowns, hidden uploads outside the exact Greenhouse contract, iframe discovery, automatic history creation, and portal-specific date widgets are pending. The select-only ARIA listbox adapter is verified on fixtures and through the loaded extension only.
- History grouping uses recognized wrappers from the synthetic fixtures. Candidate records require explicit choices instead of DOM-order inference. Row choices are deliberately not persisted across panel closure, Rescan, page refresh, or replacement DOM nodes. Real employer grouping still needs validation.
- Word page count and widows require manual review. Programmatic word and bullet checks are not a visual page-count guarantee.
- Readback proves the DOM retained the selected value, not that a remote employer saved it. File input verification is not remote upload completion.
- An unexpected unselected field change stops subsequent writes and reports the change. The prototype does not undo portal side effects automatically.
- Session data and selection overrides are local files or local extension storage and may contain personal data. They are Git-ignored. No cloud service or AI fallback is used.
- The source checkout must supply the existing builder dependencies for sandbox build tests. Tests use explicit `PORTAL_SOURCE`; they do not silently switch to another checkout.

## Validation record

Validation on October 3, 2026: the complete combined suite passed 76 tests in 46.206 seconds, comprising 13 backend tests, 10 audited-import tests, and 53 browser tests. Tests use the explicitly configured source `D:\Code\Resume` and temporary output folders.

Version `0.3.1` adds a three-page loaded-extension inspection regression. It checks no API calls, no candidate values in reports or the panel, no fill controls, rejected scan/fill messages, manual page progression, and protected-only review behavior. The routed synthetic employer host uses test-only host permissions in a temporary extension copy. Opening popup.html as a test tab does not grant activeTab, so this is not proof of the production browser-action permission flow.

The dedicated repository export was validated independently: the same 76 tests passed in 46.676 seconds using explicit `PORTAL_SOURCE`. Export inspection found only 36 text files, with no candidate document artifacts or detected credential patterns. No source repository history was copied.

Version `0.4.0`: the combined suite passed 81 tests in 50.944 seconds, comprising 13 backend, 10 import, and 58 browser tests. Five new Greenhouse regressions passed, and the existing loaded-extension inspection test now exercises the Greenhouse adapter and its hidden upload structure. JavaScript syntax checks passed. No live candidate data was sent to either portal.

New browser coverage includes exact custom dropdown selection, preservation and explicit overwrite, lazy popup creation, duplicate and disabled options, changed popup ownership, changed questions and options during opening, value reversion, collateral changes before option selection, submission controls and nested submission buttons, punctuation-sensitive matching, protected password inputs with a misleading ARIA role, and structure export. The loaded MV3 extension fills the custom dropdown and exports the structure through its real page messaging bridge.

The version `0.3.0` tests cover unbound history rows, reordering and replacement, duplicate binding rejection, wrapper identity changes, explicit manual rows, clearing edits on source changes, missing start dates, ambiguous month options, Axis date components, no invented day, scoped history aliases, and concurrent fill/rescan rejection. The loaded extension test now chooses both employment and education records and fills graduation month/year through its real page bridge. Close and Rescan now wait for completion, fixing a review-state race exposed by these tests.

JavaScript syntax and Python compilation checks passed. Desktop and mobile screenshots were inspected, and the mobile page had no horizontal overflow. Generated screenshots remain in the ignored `portal_pipeline/test-results/` folder. The local helper was started at `http://127.0.0.1:8766` for preview; restart it using the README if that process has stopped.

The version `0.3.0` row chooser was inspected visually using synthetic profile facts. Its preview screenshot is `portal_pipeline/test-results/history-review-v03.png`. The running preview serves the new JavaScript and fixtures without altering the source checkout or the user's session data.

The existing `_Reference` scripts have not been modified. Only this worktree's research Markdown was updated to reflect progress. Any later change to those scripts must run the existing workflow smoke suite as required by `CLAUDE.md`. Unrelated concurrent files and changes in other worktrees were preserved.

## Independent probe checkpoint, October 3, 2026

Author: Yazad Madan.

Six read-only lanes inspected baseline `de2e51b5e424634d2be66a32bcfa5627f5e1fbef` using synthetic data only. The coordinator personally reproduced four high findings: cross-form radio writes into protected attestation, omitted protected collateral monitoring, uncertainty stripped from profile answers, and stale upload protection after checksum await. Medium and low findings and all 14 earlier-review statuses are consolidated in [PROBE_REPORT_2026-10-03.md](../docs/PROBE_REPORT_2026-10-03.md).

Current public-checkout discovery produced three import errors and zero actual tests executed. All 81 test methods are blocked by the missing external workflow, recorded as SKIPPED-BY-ENVIRONMENT rather than passing. Default Playwright Chromium is missing; independent synthetic probes used fresh headless Edge contexts. Existing historical 81-pass results are retained and were not reproduced here. Real source data was not read or copied.

Only probe documentation changed on `probe/2026-10-03`. Production code remains unchanged and every finding remains open. The next task is user selection from the report's ranked fix list. The supplied Phase B checkpoint requires that selection before production edits. After selection, write failing synthetic regressions first, make separate serial engine fixes, run available tests with honest integration skips, update these notes, and open an unmerged pull request. No live employer forms, accounts, submissions, or automatic push are authorized by this checkpoint.

## Selected fixes, October 3, 2026

The user selected recommended items 1-5 and requested a trial. Implementation is on `fix/probe-safety-1-5`; the trial uses synthetic data and isolated browser contexts only.

E-01 is fixed: radio membership and deduplication use form ownership, every member is checked for protection, and changed membership is rejected before writing. Three new regressions failed before the fix; all four radio tests now pass using explicit `PORTAL_TEST_BROWSER=msedge`. Each test checks an untouched field, signature, certification, and zero submission clicks/events. The independent browser harness has no private workflow dependency. Live employer behavior and the full workflow suite remain unverified.

E-02 is fixed: collateral monitoring includes registered protected controls and reports them without their values or labels. A protected ID in a forged selection cannot exempt it from monitoring. Two regressions failed before the fix; all seven engine tests now pass, including ordinary collateral detection. Detection stops later writes and does not roll back portal side effects. Hidden or unsupported controls absent from the scan and changes after the observation window remain limits.

E-04 is fixed: live identity, protection, editability, visibility, history, and form ownership are checked after checksum verification and immediately before file assignment. The same live checks run at settled readback; custom listboxes retain their separate lazy-option contract. Four upload regressions failed before the relevant fixes, including file assignment to a detached node. All 13 engine tests now pass and JavaScript syntax checks pass. ARIA editability is also enforced by the shared guard, covering the E-03 mechanism; broader ARIA adapters remain outside this batch. Synthetic attachment bytes are deliberately not a valid resume document. Remote upload completion remains manual.

C3-01 is fixed: unresolved markers and unknown text are omitted; eligibility booleans require exact Yes or No. Annotated or conditional eligibility prose remains pending for manual clarification rather than losing its qualifier. The fabricated profile tests initially produced 13 failed subcases and one whitespace exception. All three profile tests now pass, and an Edge regression confirms unconfirmed authorization and availability remain pending while a selected confirmed name fills. Synthetic profile files are clearly labelled and contain no real candidate facts. Private profile compatibility and other parsing findings remain unverified or open.

L6-01 is fixed: public tests use fabricated profile fixtures and isolated HTTP/browser harnesses. External integration requires explicit `PORTAL_SOURCE`; absence skips its 81 methods and an invalid explicit path remains an error. The source-missing regression failed before this change. Requirements now include public-discovery imports and screenshot metadata support; README documents independent, integration, and visible Edge trial commands.

Final combined discovery: 108 tests, 27 passed, 0 failed, 0 errors, and 81 SKIPPED-BY-ENVIRONMENT in 25.677 seconds. JavaScript and Python syntax checks passed. A separate visible Edge run passed both browser trials in 13.962 seconds. The loaded unchanged manifest, pairing, extension-owned review, selected filling, separate sponsorship, existing-value preservation, manually chosen custom dropdown, synthetic upload, final protected review, and inspection rejection were exercised. Greenhouse selected native filling and hidden native upload passed; editable dropdowns refused and survey/cover-letter/internal controls remained untouched. Submission counters stayed zero.

The loaded-extension trial uses an explicitly fabricated helper session and attachment stub, not the real workflow audit/build/review gates. Its routed localhost fixture removes page-owned engine/panel scripts to prove isolated extension behavior. No extra manifest permissions were added. It opens extension review as a test tab, so actual browser-action activeTab behavior remains unverified. Screenshots have Yazad Madan author metadata and remain in ignored `portal_pipeline/test-results/`.

Trial harness failures were corrected without weakening production guards: string-based Playwright waiting hit extension CSP, an overbroad network filter blocked extension scripts, appended fixture controls duplicated IDs, and a page-world assertion initially observed the fixture's deliberately loaded engine. Earlier failure screenshots are retained locally. Remaining probe items are deferred outside selected items 1-5. Real external audit/build and live employer compatibility remain unverified. Publish the reviewed branch as an unmerged PR; do not merge or submit an application.

Publication complete: [PR 1](https://github.com/DarkKnight6499/application_pipeline_extension/pull/1) is open from `fix/probe-safety-1-5` to `main`. Only the fix branch was pushed; main remains at inspected baseline `de2e51b5e424634d2be66a32bcfa5627f5e1fbef`. The next task is human PR review. No merge, employer action, or application submission occurred.
