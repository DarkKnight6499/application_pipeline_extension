# Portal development handoff

## October 4, 2026: sponsorship toggle landing

Author: Yazad Madan.

Worktree `D:\Code\application_pipeline_extension_spon`, branch `feat/sponsorship-toggle`, rebased onto main `2904ded`. Both sponsorship routes and P8 record routes are preserved. The mode defaults to truthful, affects only future and combined sponsorship proposals, carries the true answer beside the proposal, and never auto-selects a field. The eligibility override refusal remains unchanged.

Five new synthetic browser tests cover default state and truth display, selective review reset, cached reviews from another mode, a toggle locked during filling, and failed mode-save preservation. The new regression cases failed before their corresponding fixes. Existing tests were not changed. FULL 284 tests and PUBLIC 203 tests end OK with two known symlink skips each. JavaScript syntax, Python compilation, and diff checks pass. Validation did not change the Resume working-tree status.

No live portal work occurred. The next task is P7 landing from `feat/p7-progression`; retain these toggle locks and mode-aware review resets when resolving panel conflicts. PF5 and the remaining review items were not started.

Date: October 3, 2026.

Current repository: `D:\Code\application_pipeline_extension`, remote `https://github.com/DarkKnight6499/application_pipeline_extension.git`, branch `docs/p0-contracts` (docs only, cut from `origin/main` at `765e17b`; PRs 4 and 5 not yet merged). The user requested publication to this repository and commits after each completed phase. The initial export contains only portal code, research, and trial reports. It does not contain the private Resume Git history or candidate data.

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

Phase order lives in `D:\Code\Resume\_Reference\Portal_Phased_Execution_Plan.md`. Next task: finish P0 (merge PRs 4 and 5, rerun the full suite on `main`, merge `docs/p0-contracts`), then P1 (adapter interface and registry). The walkthrough guidance below remains valid input for contracts under `docs/contracts/`.

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

## PF5 Phenom, October 4, 2026

Phenom support uses synthetic fixtures only. The two registered career-site hosts, five wizard pages, native controls, LinkedIn iframe, and reCAPTCHA gate are documented in `docs/contracts/PHENOM_CONTRACT.md`; live apply hosts, page markup, and CAPTCHA placement remain UNVERIFIED. The adapter fills selected fields through the shared engine, preserves existing values, never enters the iframe, and only reports Next and final review. A visible CAPTCHA blocks all writes. The answer sheet identifies the two hosts as Phenom. Seventeen isolated Edge tests passed before integration with P7. No real portal was opened, no application was submitted, and no tracker or Resume file was changed.

Six read-only lanes inspected baseline `de2e51b5e424634d2be66a32bcfa5627f5e1fbef` using synthetic data only. The coordinator personally reproduced four high findings: cross-form radio writes into protected attestation, omitted protected collateral monitoring, uncertainty stripped from profile answers, and stale upload protection after checksum await. Medium and low findings and all 14 earlier-review statuses are consolidated in PROBE_REPORT_2026-10-03.md (original kept in Git history).

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

## Follow-up extension phases, October 3, 2026

Author: Yazad Madan. The user requested further probes with subagents and confirmed extension of the existing application-filling extension. Three independent lanes reproduced gaps on `a35cc5e14e3025c2770fecddab7beda76ff0aa37`. Work continues on stacked branch `feat/followup-inspection-safety`, preserving the unmerged first PR.

C5-01 is repaired: listbox visibility respects semantic hidden ancestors, and the actual chosen node is revalidated immediately before clicking. Closed-popup inventory and lazy creation remain supported. Twelve synthetic Edge listbox tests pass, after six failing regressions. Inspection description now includes popup presence, expanded state, and whether choices were observed, without opening a popup. Existing 16 engine tests also pass. No live ATS compatibility is established.

B-01 is repaired: popup and review use a shared host policy before injection, including every Rescan. The policy retains Workday, Greenhouse, and the exact paired local origin with `/fixture`. Two tests pass, covering 18 URL boundaries and loaded MV3 rejection before pairing and after navigation away from the fixture. Rejected pages receive no bridge. The manifest has no new permissions.

C3-02 and C3-03 are repaired: answers are parsed one line at a time, conflicting duplicates remain pending, and the legacy contact triplet is validated before named facts are exposed. Uncertain master facts and mixed uncertain names remain pending. Reversed employment chronology is omitted. All 14 fabricated profile tests pass. No private profile was inspected. Invalid triplets are rejected wholesale; ASCII date separators remain unsupported. Uncertainty detection remains phrase-based.

C5-02 now reports visible iframe, open-shadow-host, and unsupported spinbutton counts with fixed reason codes. Inspection presents a current-page snapshot and warns when dropdown choices remain unobserved. No unsupported surface traversal or writes were added. Native writers now respect disabled fieldsets, ARIA availability of actual radio targets, and disabled optgroups. Duplicate select/radio values are refused because value-based assignment can select the opposite label. Review reproduced both ambiguity regressions before repair.

Final follow-up discovery: 142 total, 61 passed, 81 SKIPPED-BY-ENVIRONMENT, zero failures/errors in 46.816 seconds. Two visible Edge trials passed in 15.173 seconds with zero submissions. Nine native/inspection tests pass; extension syntax and diff checks pass. New coverage screenshot was inspected and remains ignored with author metadata. Full evidence and deferred limits are in PROBE_FOLLOWUP_2026-10-03.md (original kept in Git history). No private workflow or live employer acceptance was tested.

Published as [PR 2](https://github.com/DarkKnight6499/application_pipeline_extension/pull/2), stacked onto `fix/probe-safety-1-5`. PR 1 and PR 2 are open and unmerged; main remains unchanged. Human review is next. Remaining work is explicitly deferred in the follow-up report.

## Continued verified-gap phases, October 3, 2026

Author: Yazad Madan. The user requested continued unattended work. Work remains synthetic, within existing portal scope, on `fix/remaining-probe-boundaries` stacked onto the unmerged follow-up branch.

Further probes reproduced dynamic collateral omissions: a selected field newly labelled as certification remained exempt from collateral monitoring; replacing a non-leading protected radio member, adding consent, or revealing hidden consent did not stop later selected writes. Five regressions failed before repair. Live protection now governs collateral exemption and redaction. The registered visible control membership and native radio membership must remain stable; new, revealed, or replaced controls require Rescan, while reordering remains permitted. All five regressions and 16 existing engine tests pass. Detection reports existing portal side effects and stops later writes; it does not roll them back. Unobserved hidden/unsupported surfaces and changes after the settling window remain limits.

Review caught a regression introduced by the shared visible-control filter: supported `button[type=button][role=combobox]` controls were omitted. Root reproduced a failing scan-count test and restored role-first filtering. All six dynamic tests pass; the 12 listbox tests pass, and independent reordering/changed-row identity checks remained sound.

L6-02 and L6-03 are repaired: existing browser assertions now require exact requested-key/result-ID coverage, all 20 expected employment results, and exactly the protected attestation/signature fields. A standalone public harness executes the actual target assertions against the existing fixture with fabricated facts, without private integration setup. Empty protected scan, partial history scan, and truncated-result mutants were accepted before repair; all three are now rejected and the unmutated fixture passes. Four public Edge tests pass. The original external suite remains environment-skipped.

Synthetic tracker review found duplicate required headers could overwrite context or bypass Applied-status rejection. Five duplicate-header subcases failed before the importer rejected ambiguous headers. Empty trackers also now return the intended missing-header error instead of StopIteration. Row selection uses named column constants and the exact Application ID. Five public workbook tests pass, including reordered rows/columns, duplicate IDs, missing columns, and unchanged inactive-status refusal. Every workbook is fabricated and has Yazad Madan metadata; no tracker was changed.

L2-01 and L2-02 are repaired. A caller-supplied source descendant previously accepted synthetic session/JD writes. A real temporary Windows junction redirected session reads, downloads, and upload approval writes outside the sandbox. Source/output roots now cannot overlap in either direction, and resolved session directories and artifacts must remain contained before access. Initial regressions produced six failures; review caught and reproduced the ancestor-root overlap before correction. Eight path tests and four existing HTTP tests pass; two file-symlink tests skip because Windows privileges are unavailable. Portable resolve-escape tests cover artifact guards without claiming physical symlink proof. Fabricated create/import/build preservation tests pass; genuine workflow integration, hardlinks, and filesystem replacement races remain unverified.

Final continued-batch result: 167 total, 84 passed, 83 skipped, zero failures/errors in 75.783 seconds. Skips are 81 external workflow methods and two physical file-symlink cases. Two visible Edge trials passed in 16.963 seconds with zero submissions. Syntax and diff checks pass. All original 15 mechanisms have repairs or explicit coverage reporting, with acceptance limits retained. See continued evidence (original kept in Git history). Further live contracts require user-present inspection; genuine workflow integration remains deferred.

Final instruction audit reproduced the remaining L2-01 naming case: unrelated paths containing `_Reference`, `Applications`, or `Applications.xlsx` were still accepted as output destinations. Three subcases failed before a case-insensitive reserved-component check was added before directory creation. Nine path tests now pass with two privilege skips; four HTTP tests pass. Valid independent sandbox paths remain supported.

Final post-audit discovery: 168 tests, 85 passed, 83 explicit skips, zero failures/errors in 75.249 seconds. Independent review rejected six case variants and preserved four valid destinations, including similarly prefixed names. Published as [PR 3](https://github.com/DarkKnight6499/application_pipeline_extension/pull/3), stacked on PR 2. All three PRs remain open and unmerged; main is unchanged. Live final review and genuine workflow integration remain deferred.

## P7 progression handoff, October 4, 2026

P7 is complete on `feat/p7-progression`, rebased over `80490bf`. The phase commit is ready for coordinator review. Guarded Next defaults off. Required-field sweep, two-pass stall detection, final-review detection, a 15-action limit, and repeated-row identity remain in place. New review regressions also reject native submit controls labelled Next, stop if a human gate or final review appears during the sweep, and validate both incoming and already attached file bytes before skipping a same-name resume. Current upload identity and collateral state are rechecked after checksum awaits. P8 record routes, sponsorship toggle locks and mode-aware review invalidation, and the session-profile allowlist remain present.

Validation: FULL 304 OK, two symlink skips; PUBLIC 223 OK, two symlink skips; JSCHECK, PYCHECK, and diff checks pass. Synthetic tests assert zero submit events. The `rg submit` acceptance search now shows both the denylist and explicit native-submit guards because the safety review requires that check. A loaded-extension panel test logs a handled session-profile request error because its fake pipeline stub has no `folder` method; the panel falls back to the global synthetic profile and the test passes. No live portal behavior was tested. Next queue item: PF5 Phenom.
