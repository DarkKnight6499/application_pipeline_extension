# Review of the two portal-filling prototypes, for Codex

Reviewed 2026-10-03. Read-only review: nothing in either folder was changed. Codex leads this project; treat everything here as suggestions.

Reference plan: `Resume\_Reference\Portal_Automation_Project_Plan.md` (milestones 0 to 6, extension plus local Python helper, human logs in and submits).

Two prototypes exist, both branched from base commit `1b7827d`:

| Folder | Branch | Approach | State |
|---|---|---|---|
| `D:\Code\Resume_portal_trial\Portal_Trial` | `feat/portal-fill-trial` | Python + Playwright driving a visible Edge, CLI checkbox review, Greenhouse only | 2 commits, 34 tests pass, live run blocked by own safety guard |
| `D:\Code\Resume_portal_pipeline\portal_pipeline` | `feat/portal-pipeline` | MV3 extension + loopback Python server + web dashboard that also builds the resume | Entirely untracked, no commit, no JS tests, only a self-written Workday fixture |

## Verdict

Partly on track. The pipeline folder has the right architecture. The trial folder has the right discipline. Neither has done milestone 0 (a real portal Yazad actually uses) and neither has a single live success. Merge the two strengths rather than choosing one.

## What is right

Trial:
- Fail-closed design. Submit, signature, attestation and navigation are blocked in code (`safety.py` `guarded_click`, `SUBMISSION_LOCK`).
- Strict resolver (`resolver.py`). Exact label aliases, unique record context, compound sponsorship question stays pending, no first-record guessing.
- Per-row tick and per-row `OVERWRITE`, field fingerprint re-check before each write (`_fresh`), 500 ms settle, then read-back of the whole form including unselected controls (catches side effects). This is the best verification logic in either folder.
- Honest `TRIAL_REPORT.md`: states 0 minutes live saving and that the barrier type was never recorded.
- Hostile-input tests: malicious label, forged attestation, mid-fill barrier.

Pipeline:
- Matches the plan's architecture: extension in the user's own browser, loopback helper, human handles login and MFA.
- Server hardening: exact Host check, origin allowlist, pairing token, path allowlist in `background.js`, 2 MB body cap, session id regex, sandbox data dir that refuses `_Reference` and `Applications`.
- Resume attachment is bound to a SHA-256, reviewed flag and built state (`Pipeline.resume`), and the engine re-hashes before upload.
- `hard_fact_errors` rejects drift from the master. Separate present and future sponsorship keys. Non-overlapping Axis role dates sourced from `Builder_Internals.md`.
- Engine handles multi-section employment and education, radios, selects and a 3-step fixture, and persists selections per posting.

## Problems, most important first

1. **Trial cannot hold a login.** `browser.new_context()` starts a fresh profile, so any portal that needs an account (Workday, Oracle) cannot work. Either attach to the user's real Edge over CDP or use the extension. Keep the Playwright code as a test and regression harness, not the product.
2. **Trial's live block is undiagnosed.** `assert_no_barrier` trips on any frame URL containing `captcha`, any `iframe` whose src matches captcha, and any visible button named "Sign in" or "Create account". Greenhouse job boards commonly load an invisible reCAPTCHA frame, so this may fire on every board. This is a hypothesis; the first run did not record which signal matched. Re-run `--scan-only` once on a public board and read the signal before changing anything. Distinguish a visible challenge from a passive script frame.
3. **Pipeline built a second resume builder.** The dashboard (`web/app.js`, `server.py` `create` and `build`) lets the user edit resume JSON and build `Yazad_Madan.docx`. The plan says reuse the existing pipeline, no replacement generator, and routine resume work must not depend on the browser component. It also skips `audit_application.py`, widow checks, `.application_id`, the tracker row and the `_inputs` archive, and says so in its own advisory text. Replace it with a read-only lookup: given an Application ID or folder, return the already audited `Yazad_Madan.docx`, hash it, and require the audit to have passed.
4. **Pipeline skipped milestone 0.** It is validated only against a fixture the same session wrote. Real Workday mostly uses custom listbox dropdowns, date spinners and "Add" buttons for repeated sections. The engine rejects `role=combobox` and checkboxes and cannot add sections, so most real fields would fail. Unverified expectation, but the fixture proves nothing about it. Pick the real portal from `Applications.xlsx` links (count ATS types actually used) and capture a synthetic copy of its structure.
5. **Pipeline classifier is regex guesswork with inversion risk.** `classify()` in `engine.js` maps any text containing "authoriz", "work" and "united states" to `authorized_us`. "Do you require work authorization in the United States?" would be answered "Yes", the opposite meaning. Other loose rules: any "location" becomes the contact location (job location, preferred location), any "company" or "employer" becomes an employment field (e.g. "current employer"), "start" or "from" becomes employment start. Port the trial's exact-alias plus explicit-context approach and move resolution server-side so there is one resolver.
6. **Two resolvers will drift.** `Portal_Trial/resolver.py` and `portal_pipeline/profile.py` parse the same master and boilerplate with different regexes. The master `contact` split on ` | ` with a length-3 assumption is fragile in both. Make one shared module with tests that also guard against `smoke_tests/t_facts.py` style drift.
7. **Pipeline verification is thin.** 120 ms wait, same-element value compare, no whole-form re-read, no detection of collateral changes, no fingerprint check that the question text is unchanged at fill time. Port trial `_fresh` and the post-settle full read-back into `engine.js`.
8. **Review panel is exposed to the page.** `panel.js` uses `attachShadow({mode: "open"})` injected into the employer page, so page script can read the rendered PII and proposed answers. Use a closed shadow root or an extension-owned side panel. Also replace the manual "This page belongs to the selected posting" checkbox with an automatic origin match against `session.url`, and restrict injection to known ATS hosts.
9. **Overwrite is global in the pipeline.** One checkbox applies to all selected fields. The plan and the trial use per-field overwrite. Make it per row.
10. **No JS tests for the engine.** Only `test_backend.py` (server and builder). Add Playwright tests against the fixtures, and port the trial's hostile cases (malicious label, forged protected field, detached control, field replaced mid-fill).
11. **Name shadowing.** `portal_pipeline/profile.py` is imported as `from profile import ...`, which collides with the standard library `profile` module (also imported by `cProfile`). Rename, for example `portal_profile.py`.
12. **Test portability.** `test_backend.py` falls back to `SOURCE.parent / "Resume"` when the worktree has no `node_modules`, so tests silently read the main checkout. Set `NODE_PATH` explicitly as the trial does.
13. **Voluntary demographics.** The pipeline blocks veteran and disability outright; the trial can propose stored preferences for exact questions. Decide one policy, matching the plan (use stored preference only, otherwise pending).
14. **Housekeeping.** Pipeline work is entirely untracked, so commit it on its branch before any rewrite. Trial README and report are untracked. The 183/184 smoke result fails on `Directory_Map` missing `Portal_Automation_Project_Plan.md` and `Scraper_Coverage_Gaps.md`, which predates both branches; a one-line fix on main would restore a green suite.

## Suggested path

1. Commit both branches as they stand. Decide the real first portal from tracker data (milestone 0). Record it in the plan.
2. Run the trial scanner once on a public board and log which barrier signal fired. Fix only the false positive; do not weaken the guard for real login or CAPTCHA.
3. Converge on the extension plus local helper. Delete the dashboard's resume builder; serve audited resumes by Application ID, read-only, with hash and audit-passed check.
4. Single shared resolver, trial-style strictness, server-side, with tests.
5. Port trial verification (fingerprint, settle, whole-form read-back) and per-row overwrite into `engine.js`.
6. Build a synthetic fixture copied from the real portal's structure, add Playwright tests for the extension, then add custom dropdown support only for that portal.
7. One real run to final review (milestone 5), with measured human time against manual entry, before any second portal.

## Unchanged invariants to keep

Never click submit, sign or attest. Separate sponsorship now and future. No password, MFA or CAPTCHA automation. Portal progress never changes tracker status. Filled does not mean submitted.
