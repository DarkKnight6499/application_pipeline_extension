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
- A three-page synthetic Workday fixture containing five employment rows and deliberately unsupported or protected controls. Navigation and submission remain manual.
- Backend, import, and browser integration tests, including an actual loaded extension in Chromium. All production tracker and reference writes remain outside the prototype.

## Acceptance status

The prototype proves the local profile, review, selected-fill, and audited-resume handoff mechanisms. It does not establish compatibility with a real Workday tenant. The research plan's real-portal milestones remain incomplete. Greenhouse, Lever, and Oracle are outside the current popup scope and have no completed integrations.

The initial portal priority remains unconfirmed. Workday is the development assumption because the synthetic fixture exercises its likely field categories. No account login, live employer form filling, or application submission occurred.

## Next exact task

Choose one Workday application and inspect its real form during a user-authorized application session. A question requesting the employer URL was sent during this development pass and remains unanswered. Use **Export field structure** at each page, and follow [INSPECTION.md](INSPECTION.md). Record the employer host, page sequence, label and automation IDs, date widgets, custom dropdowns, upload completion indicator, and repeated history behavior. Do not submit the application.

The latest session attempted a public Workday reference inspection through the browser tools. Edge was unavailable and the browser inventory returned no connected browsers. A public posting fetched through web search exposed no form content, so it does not provide a verified adapter contract. Do not replace live inspection with assumptions or another generic feature cycle. The new inspection-only mode removes the import and pairing prerequisites for Yazad's first walkthrough in his own browser.

Then implement one portal-specific adapter behind the current engine. Start with the most common demonstrated unsupported control, add a representative fixture for it, and verify that unselected fields and submission controls remain unchanged. Do not begin several portal adapters in the same session.

Continue preparing real resumes through the current pipeline and use audited import for browser handoff. The sandbox builder remains a development tool. Do not make current resume generation depend on this unfinished extension.

## Known limits

- Editable or otherwise unsupported custom dropdowns, hidden uploads, iframe discovery, automatic history creation, and portal-specific date widgets are pending. The select-only ARIA listbox adapter is verified on fixtures and through the loaded extension only.
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

New browser coverage includes exact custom dropdown selection, preservation and explicit overwrite, lazy popup creation, duplicate and disabled options, changed popup ownership, changed questions and options during opening, value reversion, collateral changes before option selection, submission controls and nested submission buttons, punctuation-sensitive matching, protected password inputs with a misleading ARIA role, and structure export. The loaded MV3 extension fills the custom dropdown and exports the structure through its real page messaging bridge.

The version `0.3.0` tests cover unbound history rows, reordering and replacement, duplicate binding rejection, wrapper identity changes, explicit manual rows, clearing edits on source changes, missing start dates, ambiguous month options, Axis date components, no invented day, scoped history aliases, and concurrent fill/rescan rejection. The loaded extension test now chooses both employment and education records and fills graduation month/year through its real page bridge. Close and Rescan now wait for completion, fixing a review-state race exposed by these tests.

JavaScript syntax and Python compilation checks passed. Desktop and mobile screenshots were inspected, and the mobile page had no horizontal overflow. Generated screenshots remain in the ignored `portal_pipeline/test-results/` folder. The local helper was started at `http://127.0.0.1:8766` for preview; restart it using the README if that process has stopped.

The version `0.3.0` row chooser was inspected visually using synthetic profile facts. Its preview screenshot is `portal_pipeline/test-results/history-review-v03.png`. The running preview serves the new JavaScript and fixtures without altering the source checkout or the user's session data.

The existing `_Reference` scripts have not been modified. Only this worktree's research Markdown was updated to reflect progress. Any later change to those scripts must run the existing workflow smoke suite as required by `CLAUDE.md`. Unrelated concurrent files and changes in other worktrees were preserved.
