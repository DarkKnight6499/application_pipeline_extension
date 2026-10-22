---
author: Yazad Madan
updated: 2026-10-22
---

# Contributor start

Start from `main`. You can develop, inspect pages, run the public tests, and try the local dummy application without the owner's private Resume repository or accounts.

## Install

Use Git, Python 3.13, and Node.js 24 for JavaScript syntax checks. The owner's tested versions are Python 3.13.5 and Node.js 24.16.0. The extension is plain JavaScript with no npm build or package installation. Chrome or Edge can load it unpacked.

Clone the repository on the new computer, then enter it:

```text
git clone https://github.com/DarkKnight6499/application_pipeline_extension.git
cd application_pipeline_extension
```

On the owner's machine, keep checkouts and worktrees under `D:\Code\application_pipeline` instead.

From the cloned repository root on Windows:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r portal_pipeline\requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pip check
```

On Linux, use Python 3.13 and Node.js 24:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r portal_pipeline/requirements-dev.txt
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python -m pip check
```

`requirements.txt` declares helper runtime packages; `requirements-dev.txt` includes them and adds Playwright and screenshot tooling. Pip installs their transitive dependencies. Browser binaries are installed separately by Playwright. Commit manifests, not environments, browser binaries, or `node_modules`. CI runs the public suite on Linux; the commands in this handoff are locally checked on Windows.

## Run with dummy data

```powershell
.\.venv\Scripts\python.exe -B portal_pipeline\demo.py
```

Open the printed `/fixture` URL, normally `http://127.0.0.1:8767/fixture`. Click **Review this page's fields**, select individual fields, confirm the page, and fill. Click the fixture's Next button yourself, then review the new page. Choose a source record for employment and education rows. The fixture contains more rows than the dummy profile, so leave unmatched rows unselected or enter explicit manual answers.

The demo uses invented identity, two employment records, two education records, separate sponsorship answers, and a generated Word attachment labeled synthetic. Its author metadata is Yazad Madan, the document author, not a candidate fact. Unknown salary, relocation, address, and education start dates stay pending. Each run uses a temporary directory and a new pairing token. Ctrl+C stops the server and removes its dummy session files.

To use the actual extension, open `chrome://extensions` or `edge://extensions`, enable Developer mode, and Load unpacked from `portal_pipeline/extension`. Pair using the printed helper URL and token, then scan the local fixture. Reload the extension and refresh the page after code changes. The fixture also has a built-in panel, so use one panel at a time when diagnosing extension behavior.

The attachment is preapproved solely to exercise local upload plumbing. No real builder, tracker, eligibility check, audit, or visual resume acceptance is simulated as genuine evidence. Missing duplicate/JD checks remain visible warnings. Demo imports, new application creation, tracker records, and resume building are unavailable. The helper attachment endpoint refuses a changed application origin; the extension also checks the selected posting origin. Never use dummy answers on employer pages.

See [dummy input files](portal_pipeline/examples/synthetic_source/README.md). Existing public tests also fabricate trackers, session records, portal pages, helper responses, and attachment bytes. They need no credentials or private files.

## Validate

Run the public suite without a private source:

```powershell
Remove-Item Env:PORTAL_SOURCE -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -B -m unittest discover -s portal_pipeline/tests -p "test_public_*.py" -v
Get-ChildItem portal_pipeline/extension -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName; if ($LASTEXITCODE -ne 0) { throw 'JavaScript syntax check failed.' } }
git diff --check
```

On Linux, use `.venv/bin/python` and `unset PORTAL_SOURCE`; the unittest arguments are identical. To use installed Edge on Windows instead of downloaded Chromium, set `$env:PORTAL_TEST_BROWSER = 'msedge'`. Clear it with `Remove-Item Env:PORTAL_TEST_BROWSER` to return to Chromium. Browser tests must execute, not all skip. The public suite currently has 17 explicit private-source preflight skips; Windows may also skip two physical file-symlink tests. Report actual counts and reasons rather than copying old acceptance totals.

For a short check, replace the test pattern with `test_public_demo.py`. `test_public_trial.py` exercises a loaded unpacked extension with fabricated inputs. A passing fixture is synthetic evidence, not live compatibility.

## Next work, in order

Read `AGENTS.md`, [current status](docs/STATUS_AND_NEXT_STEPS.md), [live Workday handoff](docs/LIVE_WORKDAY_HANDOFF.md), and [trial failures](docs/TRIAL_ERRORS.md). Historical notes are dated; later acceptance supersedes earlier holds. The owner prioritizes other portals before Greenhouse.

| Order | Work | Acceptance |
|---|---|---|
| 1 | Fix export intake's token false positive for long Workday structural IDs. Start in `portal_pipeline/export_intake.py` and `tests/test_public_export_intake.py`. | Add a fabricated failing ID case first. Accept the narrow structural pattern while genuine secret-like data and forbidden answer keys remain rejected. Never relax the entire token detector. |
| 2 | Capture Workday button menus and searchable dialog contracts. Start in `extension/adapters/workday.js`, `engine.js`, and `docs/contracts/WORKDAY_CONTRACT.md`. | Anonymized fixtures cover Country, State, phone device type, school/field selectors, degree menus, popup ownership, and stale controls. Unsupported controls remain manual. |
| 3 | Repair omitted resume input, date semantics, and repeated-row attribution. | Tests cover month/year spin controls, correct explicit record binding, stale rows, unselected-field preservation, and zero final-submit events. A null record or missing picker cannot be called supported. |
| 4 | Validate through the loaded extension with the owner. | Recheck the browser state, source approved real answers locally, navigate manually, then verify persistence after navigation and upload completion separately. Native UI entry is not extension acceptance. |
| 5 | Continue Oracle only after the owner supplies an exact reviewed apply hostname. Keep Greenhouse last. | Oracle remains unrouted and answer-sheet only. No new host permissions or automated fill without an observed, reviewed contract. |

P9 remains gated by completed PF1/PF2 prerequisites and at least 50 owner-approved real pending question wordings. Do not add model calls, bulk applying, new production hosts, or automatic submission as a shortcut. Additional portal fixtures already in the repository remain synthetic evidence only.

One phase per branch. Add a regression before a behavior fix, keep existing safety assertions, run relevant tests and PUBLIC, and record failures and limits in the handoff. Changes to existing tests, host policy, or popup acceptance need the project's existing owner review and source-enabled FULL validation. Commit exact owned paths. Push without force; do not reset or clean other worktrees.

## Optional private integration

The production helper still requires the separate existing Resume checkout. It supplies its profile, reference modules, builder, audit, tracker, and application files. Dummy demo files are not a replacement for those modules and cannot satisfy FULL integration prerequisites.

With authorized access, install `requirements.txt` into the selected Python environment, use that checkout's own dependency instructions for its Node `docx` builder, and run:

```powershell
$env:PORTAL_SOURCE = 'C:\path\to\authorized\Resume'
.\.venv\Scripts\python.exe -B -m unittest discover -s portal_pipeline/tests -v
.\.venv\Scripts\python.exe -B portal_pipeline/server.py --source $env:PORTAL_SOURCE --port 8766
```

Use the environment's Python directly. `start.ps1` uses the Windows `py` launcher and may select a different environment. The private phased plan, if provided by the owner, supplies broader phase details; the public queue above is enough to start current synthetic work. Do not copy that private repository, real profiles, raw live exports, resumes, trackers, credentials, cookies, or tokens into Git. Login, CAPTCHA, voluntary disclosures, signatures, attestations, and final submission remain manual.
