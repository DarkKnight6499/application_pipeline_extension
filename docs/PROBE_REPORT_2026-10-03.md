---
author: Yazad Madan
date: 2026-10-03
status: Selected fixes 1-5 complete, live acceptance pending
---

# Local safety and portability probe

The inspected baseline is `de2e51b5e424634d2be66a32bcfa5627f5e1fbef` from the public `DarkKnight6499/application_pipeline_extension` repository. Six read-only lanes inspected the same baseline. The coordinator consolidated their results and personally reproduced every high-severity finding below. No production code was changed.

Only fabricated profiles, temporary files, synthetic browser pages, and synthetic localhost requests were used. No private candidate checkout, resume, tracker, browser credentials, live employer form, account, or submission was used. Browser probes used fresh headless Edge contexts, version `154.0.4258.53`. Synthetic results establish these mechanisms only, not employer compatibility.

## Existing suite result

Command: `py -3 -B -m unittest discover -s portal_pipeline\tests -v`.

| Measure | Current result |
| --- | --- |
| Actual suite tests passed | 0 |
| Actual test assertion failures | 0, because test methods never ran |
| Discovery errors | 3, one each for backend, browser, and import modules |
| Tests blocked by environment | 81: 13 backend, 58 browser, 10 import |
| Runner elapsed time | 0.003 seconds, excluding module import work |
| Command wall time | 2.155 seconds |

All 81 are **SKIPPED-BY-ENVIRONMENT** in this report's accounting. Unittest itself emitted import errors, not 81 skip events. Each module calls `workflow_source()` during import. The public checkout lacks the private builder and its Node dependencies, so discovery exits before any actual test runs. No silent alternate checkout was used. The historical 81-pass record remains historical evidence, not a result reproduced here.

The installed Playwright default Chromium executable is also missing. Independent probes explicitly selected installed Edge. Those probes were separate from the existing suite and are not counted as suite passes.

## Consolidated findings

Line references refer to the inspected baseline. Severity describes the demonstrated failure and its prerequisites. Verified means the behavior was reproduced or the stated assertion weakness was directly inspected. Probable means the code supports it but the complete exploit or mutation was not executed.

| ID | Severity | File:line | Finding | Evidence | Confidence |
| --- | --- | --- | --- | --- | --- |
| E-01 | High | `portal_pipeline/extension/engine.js:177-183`, `309-313` | Same-name radios from different forms are merged; selecting an ordinary answer can directly check a protected attestation in another form. | Independent lane and coordinator synthetic browser reproductions checked the other form's radio and reported `filled`. | Verified |
| E-02 | High | `portal_pipeline/extension/engine.js:255-258` | Protected controls are excluded from collateral monitoring, so an unselected consent change is missed and filling continues. | Independent lane and coordinator reproductions checked an agreement through an input side effect; both selected text writes reported `filled`. | Verified |
| C3-01 | High | `portal_pipeline/portal_profile.py:60-66`, `portal_pipeline/extension/engine.js:205-213` | Unknown and unconfirmed answers become sourced proposals; `Yes [CONFIRM]` loses its qualifier and can fill a Yes/No authorization field. | Synthetic resolver and browser traces; coordinator personally confirmed qualifier removal and successful exact Yes selection. | Verified |
| E-04 | High | `portal_pipeline/extension/engine.js:280-301`, `330-337` | Resume upload does not revalidate question identity or generic protection after awaiting the checksum, allowing attachment to a newly protected question. | Coordinator queued a synthetic label change during the digest await; the change handler observed `I attest and certify` at upload, and result was `filled`. | Verified |
| E-03 | Medium | `portal_pipeline/extension/engine.js:128-139`, `284` | Current ARIA disabled/read-only state is not checked at native write time. | After scan, `aria-readonly=true` still allowed a selected text write and `filled`. | Verified |
| C3-02 | Medium | `portal_pipeline/portal_profile.py:48`, `65` | Blank boilerplate answers can consume the next bullet; whitespace-only boolean answers crash. | Blank authorization resolved as `-`; whitespace-only authorization raised `IndexError`. | Verified |
| C3-03 | Medium | `portal_pipeline/portal_profile.py:36`, `41-44` | Unchecked contact positions and segment counts can crash or silently swap email and phone facts. | Two contact segments raised `IndexError`; reversed segments produced swapped values. | Verified |
| C5-01 | Medium | `portal_pipeline/extension/adapters/aria-listbox.js:5`, `28-30`, `73-79` | ARIA-hidden options can remain selectable and receive a click. | A synthetic option with `aria-hidden=true` was clicked and its combobox reported `filled`. | Verified |
| C5-02 | Medium | `portal_pipeline/extension/engine.js:172`, `222-230` | Inspection silently omits iframe, shadow-root, and custom spinbutton controls without an incomplete-surface warning. | Synthetic inspection reported ordinary input and combobox only, with empty portal-manual reason. | Verified |
| L6-01 | Medium | `portal_pipeline/tests/test_support.py:8-10`, `test_backend.py:18`, `test_browser.py:18`, `test_import.py:15` | All public tests require the external workflow even when their subject could be tested independently. | Suite discovery result above and module imports. | Verified |
| B-01 | Low | `portal_pipeline/extension/review.js:20-23` | Rescan does not repeat the popup's supported-host or paired-fixture restriction. | Loaded MV3 extension inspected an unpaired localhost path with empty storage through persistent localhost permission. | Verified |
| L2-01 | Low | `portal_pipeline/server.py:35-38` | A caller-supplied sandbox path can write within other source directories or unrelated reference/tracker-like directory names. | Fabricated source with in-memory helper stubs accepted source `Projects`, source `_Backup`, and unrelated `_Reference` and `Applications` paths. | Verified |
| L2-02 | Low | `portal_pipeline/server.py:51-57` | A local session-directory reparse point could redirect reads or writes outside the sandbox. | Session path is not resolved and constrained; Windows symlink creation was unavailable, so exploit was not executed. | Probable |
| L6-02 | Low | `portal_pipeline/tests/test_browser.py:349-358` | Protected-control test lacks a nonempty-scan assertion and could pass with an empty scan. | `all(...)` accepts empty collections and remaining checks only require unchanged fixture values; mutation not executed. | Verified weakness, probable mutant survival |
| L6-03 | Low | `portal_pipeline/tests/test_browser.py:145-152` | Five-role fill test does not assert all requested fields or result cardinality. | Helper filters discovered fields; test checks universal statuses and two dates only; mutation not executed. | Verified weakness, probable mutant survival |

No critical finding or page-readable extension PII channel was established. E-01 directly violates selected-only and protected-field boundaries. E-02 observes a portal side effect rather than a direct consent write by the engine; the defect is failure to detect it and stop. E-04 attaches a file to a changed protected question; it does not demonstrate an actual signature or submission.

## Minimal reproductions

### E-01: cross-form radio binding

On a fresh synthetic page load the unchanged engine and this markup:

```html
<form><fieldset>
  <legend>Are you authorized to work in the United States?</legend>
  <label><input type="radio" name="auth" value="no">No</label>
</fieldset></form>
<form><fieldset>
  <legend>I certify this application</legend>
  <label><input id="attest" type="radio" name="auth" value="yes">Yes</label>
</fieldset></form>
```

Scan with fabricated `authorized_us=Yes`, then fill only the first returned field ID with `Yes`. The second form's `#attest` becomes checked and the result is `filled`. Scan membership ignores form ownership, while fingerprint construction filters by form. Correct behavior is separate groups with independent protection and target validation.

### E-02: protected collateral

Use a First name input whose input handler sets a separate `I agree` checkbox to true, plus a Last name input. Scan and select only First name and Last name. Both writes succeed and the agreement changes unnoticed. Correct behavior is to monitor protected state without exposing its value in the panel or report, report the side effect, and stop subsequent writes. Automatic rollback is not assumed safe.

### C3-01: unknowns promoted to facts

Create a temporary fabricated master with `header.name`, three synthetic contact segments, empty `experience`, and empty `education`. Supply empty `Builder_Internals.md` and boilerplate `- Work authorized in US: Yes [CONFIRM]`. `resolve_profile()` emits `authorized_us.value=Yes`. Scan a labelled native authorization Yes/No select and fill that proposal: result is `filled`. Literal `[CONFIRM]` and `Unknown` also become prepared proposals and can fill text controls. Correct behavior is to omit unresolved facts and keep questions pending, preserving uncertainty.

### E-04: upload question changes during checksum await

Use a locally fulfilled secure synthetic page, a visible labelled Resume file input, and fabricated bytes `[1, 2, 3]`. Compute their valid SHA-256 and scan the input. Before invoking fill, queue a microtask that changes the label's text node to `I attest and certify`. Fill only the scanned upload with the valid fabricated attachment. The engine's digest await lets the mutation run before file assignment. A `change` listener records `I attest and certify` at assignment; the input has one file and reports `filled`. Revalidate identity, visibility, protection, form ownership, and editability immediately after asynchronous boundaries and before assignment.

### Other verified or probable findings

- **E-03:** Scan a normal text input, set `aria-readonly=true`, and fill its previously selected ID. It still receives the value. Initial ARIA-disabled controls are blocked by panel selection, but the direct engine writer also ignores that state.
- **C3-02:** Boilerplate `- Work authorized in US:` followed on the next line by `- Require sponsorship now: No` resolves authorization as `-`. Three spaces as the answer cause an `IndexError` at boolean token extraction.
- **C3-03:** Use two contact segments to reproduce the index error. Reverse synthetic phone and email segments to reproduce silent misrouting.
- **C5-01:** Use an owned select-only listbox with one visible-layout option labelled Yes and `aria-hidden=true`. Its click handler updates `aria-valuetext`. Selecting the combobox clicks that option and reports success.
- **C5-02:** Add an iframe input, an open shadow-root input, and `div[role=spinbutton]` beside an ordinary input. Inspect. Only supported top-level controls appear and no incomplete-surface reason is reported.
- **L6-01:** Run the discovery command above in the public checkout without private source dependencies.
- **B-01:** Load unchanged MV3 extension in a fresh test profile. Route a synthetic page at an unpaired `http://127.0.0.1:<port>/not-the-paired-fixture`. Open extension `review.html?tab=<target-id>&mode=inspect` with empty storage. Inspection succeeds although popup validation would reject that target. This establishes localhost scope bypass only.
- **L2-01:** With fabricated source and explicit in-memory workflow stubs, construct `Pipeline(source, source / "Projects")` and create a synthetic session. Session files appear inside the source. Startup currently chooses the normal default path; this is a caller/configuration risk, not a demonstrated unauthenticated web attack.
- **L2-02:** Proposed local reproduction is a junction at `<data>/<32 lowercase hex characters>` targeting an outside directory containing `session.json`. Session lookup would follow it. Symlink execution was blocked by Windows privilege error 1314; this remains probable.
- **L6-02:** Proposed test mutation: scanner returns `[]` on protected review page. Universal assertions and unchanged fixture checks still accept it. Mutation execution remains pending.
- **L6-03:** Proposed test mutation: omit most requested history fields while preserving the two asserted date fields. No exact expected-field/result assertion detects the omission. Mutation execution remains pending.

## Status of all 14 earlier review items

These statuses refer to `docs/Codex_Review_Portal_Projects.md`. External legacy trial code and private workflow files are absent; their behavior was not inferred from current extension code.

| Item | Status | Current evidence and limit |
| --- | --- | --- |
| 1. Trial cannot hold login | CHANGED | Product is MV3 extension in the user's browser, `portal_pipeline/extension/manifest.json:1-10`; legacy Playwright login prototype is absent. Actual production login continuity remains untested. |
| 2. Undiagnosed trial barrier | STILL OPEN | Historical signal remains unidentified, `docs/TRIAL_ERRORS.md:16-17`. No live rerun is permitted in this probe. |
| 3. Second resume builder | CHANGED | Existing builder reused at `portal_pipeline/server.py:157`; audited import at `74-95`; imported sessions cannot rebuild at `127-128`; sandbox uploads restricted to local fixture at `210-213`. Sandbox dashboard remains intentionally present. |
| 4. Real target milestone | STILL OPEN | No real employer final-review acceptance, `portal_pipeline/HANDOFF.md:29-35`. Synthetic custom controls and Greenhouse structural contract are progress, not live proof. |
| 5. Regex classifier inversion | FIXED | Exact scoped aliases, `portal_pipeline/extension/engine.js:88-125`. Required authorization, compound sponsorship, preferred/job location, and unscoped employers stay pending in synthetic traces. New resolver uncertainty bug C3-01 is separate. |
| 6. Two fragile resolvers | CHANGED | One Python resolver is present, `portal_pipeline/portal_profile.py:23`; legacy resolver absent. Unchecked contact splitting persists at `36-44` and is C3-03. No cross-repository convergence was verified. |
| 7. Thin verification | CHANGED | Fingerprints at `portal_pipeline/extension/engine.js:280`, collateral at `255-263`, 500 ms settle at `330`, detached checks at `278,336`. E-01, E-02, E-04, and E-03 show remaining gaps. |
| 8. Page-exposed panel | FIXED | Extension-owned review page opened by `portal_pipeline/extension/popup.js:22-23`; posting-origin check at `panel.js:69`; trusted bridge at `page-bridge.js:5-10`. Loaded-extension synthetic test found no page-world engine, bridge, or panel. B-01 is a narrower host-policy inconsistency. |
| 9. Global overwrite | FIXED | Individual checkbox and payload at `portal_pipeline/extension/panel.js:138-143,178`; writer checks individual flag at `engine.js:287`. Legacy engine-wide option remains callable, but production panel sends per-field choices. |
| 10. No JS tests | FIXED | 58 browser test methods in `portal_pipeline/tests/test_browser.py`, including stale labels, re-rendered rows, collateral changes, and submit controls. Public portability remains L6-01; current probe reproductions need regression integration after selection. |
| 11. Standard-library name collision | FIXED | `portal_pipeline/portal_profile.py` and `server.py:20` use the renamed module; no `profile.py` exists in this checkout. |
| 12. Silent source fallback | FIXED | `portal_pipeline/tests/test_support.py:8-10` selects explicit environment path or public root, then fails instead of silently switching to sibling Resume. All three test modules use it. |
| 13. Demographic policy | CHANGED | Conservative manual-only policy at `portal_pipeline/extension/engine.js:5,190`; whole Greenhouse container protected at `adapters/greenhouse.js:28`. No stored demographic defaults are resolved. Supporting optional preferences is a product decision, not required for this probe. |
| 14. Untracked work and external smoke failure | CHANGED | Current baseline contains tracked implementation and tests. External 183/184 failure remains historical at `docs/TRIAL_ERRORS.md:19`. Its missing private files were not copied or edited. Probe documentation is committed on a separate branch. |

## Semantics and unsupported surfaces

Synthetic source answers were authorization Yes, sponsorship now No, and future sponsorship Yes. Exact authorization wording proposes Yes. Requiring work authorization remains pending; no opposite answer is proposed. Compound now-or-future sponsorship remains pending. Job location, preferred location, current employer, previous employer, and posting-company wording remain pending rather than borrowing residence or the first employment record. Current location uses residence. Explicitly bound employment company/location/start dates use only the chosen record. Available-from uses candidate availability outside history and remains pending inside history. Graduation dates use the bound school; absent education start dates stay pending. Voluntary identity fields remain manual.

| Surface | Current outcome | Remaining limit |
| --- | --- | --- |
| Owned select-only listbox | Exact single enabled option or clean refusal for ambiguity/action controls | C5-01 allows ARIA-hidden options. |
| Editable combobox | Explicit manual reason and clean refusal | No portal-specific editable-dropdown contract. |
| Lazy listbox | Polling up to 1,200 ms | Slower popup fails with manual reason; does not prove employer behavior. |
| Employment/education rows | Explicit per-row source choice; replacement and duplicate bindings rejected | Only recognized wrappers; no automatic row creation. |
| Add another button | Not scanned or clicked | Human creates missing rows. |
| Native split month/year | Sourced components and visible option labels | No invented day or missing education start. |
| Custom date spinbutton | Silent omission | C5-02 needs incomplete-surface reporting. |
| Iframe/shadow-root form | Silent omission | C5-02; no traversal or extra iframe injection implemented. |
| Lazy sections | Newly created controls need a new scan | No automatic discovery after asynchronous insertion. |
| Reactive re-render | Detached target fails; ordinary collateral detachment stops subsequent writes | Current selected node and history identity checks do not close all async gaps. |
| Greenhouse hosted form | One unique application form; auxiliary/internal inputs excluded | Unsupported/duplicate form produces explicit manual reason. |
| Greenhouse survey | Entire known survey container manual-only | New arbitrary demographic structures remain unverified. |
| Greenhouse hidden resume | Exact labelled upload-group recognition | Native attachment proves file input only; remote completion manual. |
| Autosave and later validation | DOM readback after 500 ms | Later reversion or remote saving is outside the observed window. |

## Checked and found sound

- Actual loaded-extension synthetic checks found no page-readable review panel or engine global. Review content lives on the extension origin; the panel's open shadow root there is not employer DOM.
- Inspection mode rejected candidate scans and fills, omitted a synthetic password, and did not load candidate data.
- Manifest grants persistent access only to loopback. No external messaging or public extension resources are declared. Popup rejects unsupported hosts. Production browser-action permission behavior remains unverified.
- Background restricts API paths and loopback configuration. Bridge validates extension identity and review sender. Payload-schema validation is incomplete, but no employer-page channel reaching it was demonstrated.
- Synthetic HTTP requests rejected foreign Host and Origin with 403 and wrong token with 401. Correct synthetic token and origin-free localhost request succeeded with 200. Body cap, malformed/nonobject JSON, static traversal, and invalid session identifiers were checked by lane 2. Binding is loopback only. No browser-driven CSRF or DNS-rebinding exploit was run.
- Synthetic importer-mechanism checks with an explicitly fabricated audit stub rejected outside folders, duplicate IDs, Applied status, changed tracker context, and changed marker. This does not validate the real external audit.
- Ordinary selected writes preserve existing values unless overwrite is selected. Question changes and detached targets fail. Ordinary unselected collateral stops later writes. Concurrent fill and registered rescan reject. Correct and incorrect synthetic upload checksums behaved as expected.
- No current code path examined changes tracker status, allocates a real Application ID, automates account credentials, or clicks a native submission button. The protected-radio counterexample shows that guarding action types alone is insufficient.

## Documentation and test limits

README's present-tense 81-pass claim at `README.md:32` lacks the environment qualification that appears in HANDOFF's historical validation record. The inventory is correct, but it cannot be reproduced from this public checkout. HANDOFF's older Workday-only popup statement at line 22 is superseded by Greenhouse support in the next line; `docs/PROJECT_PLAN.md` retains a similar older progress statement. These are historical/superseded claims, not evidence of removed Greenhouse support.

Existing test fixtures use synthetic employer/tracker labels but `audited_fixture()` copies the real master from the configured private source at `portal_pipeline/tests/test_support.py:20`. They are not wholly synthetic candidate fixtures. Do not configure these tests against a real candidate checkout for this task.

Minimal proposed test stand-in: keep a clearly fabricated master and boilerplate under `tests/fixtures`, and separate engine, inspection, HTTP boundary, and profile tests from external audit/build integration. Use an explicitly labelled audit stub only for importer-mechanism tests. Real audit and builder tests remain opt-in and must emit an explicit environment skip when absent. Do not fabricate private builder implementation or claim a stub validates it. This stand-in has not been implemented before the user's fix selection.

Unavailable: real external audit/build integration; default Playwright Chromium; production browser-action permission flow; legacy trial source and exact barrier signal; runtime reparse-point exploit; live Workday/Greenhouse structure and final review; real remote saving/upload completion; any measured human time saving. No live employer probes should follow automatically from this report.

## Ranked fix order for user selection

Effort estimates are approximate focused implementation and regression time, excluding live portal validation and dependency installation. Engine fixes must be serial; preserve all invariants and keep each selected fix in a separate commit.

| Order | Items | Proposed change | Estimate |
| --- | --- | --- | --- |
| 1 | E-01 | Bind radio groups by form ownership and validated members; protect every candidate target. Add cross-form and protected-member regression. | 2-4 hours |
| 2 | E-02 | Monitor all relevant unselected state, including protected controls, without returning protected values; stop on change. | 2-4 hours |
| 3 | E-04 | Revalidate target identity/protection/editability after async waits and before upload assignment; check retained question identity too. | 1-3 hours |
| 4 | C3-01 | Preserve uncertainty; reject unresolved/qualified eligibility facts instead of truncating into Yes/No. | 1-3 hours |
| 5 | L6-01 | Isolate public synthetic tests from private workflow and use explicit integration skips. Build minimal fabricated fixtures. | 3-6 hours |
| 6 | E-03, C5-01 | Recheck ARIA availability at write time; exclude ARIA-hidden dropdown nodes and ancestors. Separate commits. | 1-2 hours each |
| 7 | C3-02, C3-03 | Bound boilerplate parsing to one line; validate contact schema before exposing facts. Separate commits. | 1-3 hours each |
| 8 | C5-02 | Report incomplete inspection for unsupported surfaces without expanding portal/control families. | 1-3 hours |
| 9 | B-01, L2-01, L2-02 | Repeat host restriction; tighten output and resolved session containment. Separate commits. | 1-2 hours each |
| 10 | L6-02, L6-03, doc drift | Require nonempty scans and exact result coverage; qualify historical/environment-bound claims. | 1-2 hours |

Proposed first batch is orders 1-5, with the minimal regression harness needed to prove each fix built before its production change. All findings remain open at this checkpoint. Await user selection before production edits, fixes, pushing, or opening the Phase C pull request.

## Selected-fix follow-up

The user selected recommended items 1-5 and requested a browser trial. On `fix/probe-safety-1-5`, E-01, E-02, E-04, C3-01, and L6-01 are repaired with synthetic regressions. Each production fix was preceded by observed failing regression cases and committed separately. The E-04 shared live guard also addresses the E-03 native ARIA editability mechanism. Remaining findings are deliberately deferred outside the selected batch. The baseline tables and earlier status analysis above are retained as historical evidence.

Final combined suite: **27 passed, 0 failed, 0 errors, 81 SKIPPED-BY-ENVIRONMENT**, 108 total in 25.677 seconds. The former discovery import errors are now explicit external-integration skips. Source resolution requires explicit configuration and rejects invalid configured paths. Python/JavaScript syntax and diff checks passed. Public tests contain a labelled fabricated profile, not copied private candidate facts.

A separate visible Edge browser run passed two trials in 13.962 seconds. The loaded MV3 extension exercised pairing, extension-owned review, selected native and custom dropdown filling, preserved existing values, separate sponsorship, synthetic attachment, final protected review, and inspection-mode scan/fill rejection. The Greenhouse trial exercised selected native fields, exact hidden resume recognition, checksum attachment, protected survey exclusion, and editable-dropdown refusal. Zero submission events/clicks occurred. Screenshots were inspected and have explicit Yazad Madan author metadata; they remain ignored local artifacts.

The trial helper's session and attachment are fabricated stubs and do not validate production audit/build/review gates. The localhost fixture's page-owned engine/panel scripts were removed in the test response to verify extension isolation. The production manifest was unchanged; actual browser-action activeTab permission remains unverified because review opens as an extension test tab. Private workflow integration, real employer saving/upload completion, live final review, and measured time saving remain unverified. HANDOFF and TRIAL_ERRORS preserve the regression failures and corrected harness errors.
