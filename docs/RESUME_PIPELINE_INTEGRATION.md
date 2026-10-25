---
author: Yazad Madan
date: 2026-10-25
---

# Integrating the application pipeline into the Resume pipeline

Local only. Nothing here submits, signs, or allocates Application IDs. The user clicks Submit.

## Entry point

```
py apply.py <job link> --folder <application folder> [--no-open]
```

Python: `import apply; apply.run(url, folder)` (from `portal_pipeline/`).

Inputs:
- Job link, or `apply.json` in the folder: `{"url": "...", "resume": "path", "cover": "path"}` (resume and cover optional).
- Folder files by default: `Yazad_Madan.docx` (else `.pdf`) and the first `CoverLetter_*.docx` or `.pdf`.
- `PORTAL_SOURCE` env var: the Resume checkout, read only (default `D:\Code\Resume`). Profile, boilerplate and tailored text are read from `_Reference`.
- Edge running with `--remote-debugging-port=9223 --user-data-dir=D:\Code\application_pipeline\browser_profile`.

Output: driver log on screen and a JSON report in `portal_pipeline/data/runs/` (git-ignored).

## What the Resume pipeline should do

1. After the resume and cover letter exist, write `apply.json` in the application folder (link, resume, cover).
2. Call `apply.run(url, folder)` or the command above.
3. Keep exactly one browser tab per board open (the driver stops if there are several).

## Flow

link -> board by host (`apply.HOST_PORTALS`) -> open link, click Apply (Workday, Oracle only) -> `workday_run.py --portal <board>` -> per page: scan, propose from stored answers or profile, fill, attach files, learn what the user typed, click Next -> stop at Review or Submit.

Boards: workday, oracle, icims, lever, ashby, smartrecruiters, eightfold, taleo, greenhouse (greenhouse skipped by the user: autofill exists).

## State per board (2026-10-25)

| Board | State |
|---|---|
| Workday (Citi) | Wired; proven on synthetic pages and read-only on a filled form. Fresh empty application not yet run. |
| Oracle (JPMC) | Live run through sections 1 to 4 to the Submit page. History sections are cards plus inline forms (`oracle_history.py`, unproven live). Files via `oracle_attach.py`. |
| iCIMS (Schwab) | Live run to the last page (Submit only). Frame targeting, address override checkbox, Update Profile as Next. History rows not bound to profile records. |
| Lever, Ashby, Eightfold | Live dry scans work (real question text, upload slots). No fill run yet. |
| SmartRecruiters | Live dry scan works after shadow-DOM scanning. Multi-step Next flow not built. |
| Taleo, SuccessFactors, BrassRing, Phenom | Not proven. Need a logged-in posting (Taleo) or a real link. |

## Rules enforced in code

- Sponsorship: every sponsorship value is No (`workday_run.build_profile`), overwriting portal prefill. Immigration, OPT, STEM, visa and sponsorship answers are never learned (`IMMIGRATION_LABEL`). OPT follow-ups under "No sponsorship" are set to N/A (user can change).
- Exact-match answers only; answer memory is `portal_pipeline/data/answer_memory.json` (ignored). Learning skips history rows, duplicate labels, checkboxes, password fields, bare option ids and account labels (`UNLEARNABLE_LABELS`).
- Consent boxes only after the user ticked once for that host and label. Signature and Full Name fields are manual.
- Existing portal values are preserved unless the answer is sponsorship related.
- iCIMS "Use this address anyway? Yes" is ticked automatically (user decision).
- Dialogs (except empty ones and cookie banners) stop the driver. Next is clicked only when its label is Next, Save and Continue, or Update Profile.

## Known gaps and next steps

1. Fresh-application live runs for Workday and Oracle (login, email code entry stay manual; Gmail reader deferred).
2. Apply-button clicks for iCIMS, Lever, Ashby and others (`apply.APPLY_CLICK`); login fill from Credential Manager.
3. Bind iCIMS Education rows and Oracle history cards to profile records; check the JPMC Master's card has no school name.
4. Codex review items still open: Next validated by label only; live Oracle adapter lacks the application-mode CAPTCHA restriction; explicit record identity mapping; CAPTCHA gates around Add, upload and Next.
5. SmartRecruiters multi-step flow (Add experience and education, Next).
6. Profile gaps: SBM role description, GPA, education start years, field of study for the second education row.
7. Free-text "why us" drafts are shown to the user first, never auto-submitted.

## Lessons

- Workday pickers: typing plus Enter selects the first result at once; verify the pill and delete a mismatch.
- Oracle comboboxes use `aria-haspopup=grid` with one gridcell per row; hidden dialogs exist in the DOM.
- Script injection uses CDP `Runtime.evaluate` on pages (CSP safe) and plain frame evaluate inside iframes.
- Back on Workday My Experience opens a Discard dialog: press Continue only.
- Editing `engine.js` (CRLF): write with `newline=""` and avoid non-ASCII in Python heredocs; `\b` in shell-passed Python strings can turn into a backspace character.
