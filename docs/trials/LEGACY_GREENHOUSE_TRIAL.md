---
author: Yazad Madan
date: 2026-10-03
status: Synthetic flow verified; live flow stopped at safety boundary
---

# Milestone 1 trial report

The isolated `feat/portal-fill-trial` branch contains a working synthetic scan, resolve, review, selective fill, upload, and read-back flow. Live end-to-end acceptance is **not achieved**. The first live target triggered the login/CAPTCHA/bot-protection guard before scanning or filling. No application was submitted, no live answer was filled, and no resume was uploaded to the live employer.

Worktree: `D:\Code\Resume_portal_trial`. Base commit: `1b7827d`. Main was not edited. No dependency was installed, no branch was pushed, and no PR was opened. Portal progress remains separate from tracker status; the trial did not write `Applications.xlsx` or call a tracker writer against production data. The explicitly requested hermetic smoke suite exercised its own redirected synthetic tracker fixtures.

## Live attempt

The user authorized any public Greenhouse target and any existing built resume. Target: [BTIG, Finance, Risk Analyst, Vice President & Associate](https://job-boards.greenhouse.io/btig27/jobs/8633453002). This selection was an automation experiment, not a resume-tailoring or role-fit assessment. Following a separate one-time permission, one existing application resume was copied to ignored `Portal_Trial/out/Yazad_Madan.docx`. No other application content was read.

The visible Edge browser opened the target. The initial implementation returned the combined safety reason: `Login, MFA, CAPTCHA, or bot protection detected. Automation stopped; user control required.` It did not record which individual signal matched. Consequently the specific barrier type is unverified. The guard has since been improved to distinguish password controls, CAPTCHA frames, MFA controls, login/account controls, and bot-protection text. The blocked live form was not retried or bypassed.

| Live step | Result | Time |
|---|---|---|
| Open and scan | Stopped at safety inspection before field enumeration | Not captured in the initial blocked run |
| Resolve | Not reached | Not run |
| Review selections | Not reached; zero fields selected | Not run |
| Fill and upload | Not reached; zero live writes | Not run |
| Read-back | Not reached; live fields and upload unverified | Not run |
| Handoff | Browser left open for human control | Not measured |

There is no live field inventory, so a field-by-field live success claim would be fabricated. Every live field is unscanned and unverified. The failed-phase timer was corrected after this attempt so future stopped runs record their elapsed phase time. Human time and setup time were not measured.

## Synthetic end-to-end result

A saved synthetic Greenhouse-style fixture exercises 22 controls in visible Edge, including required fields, uploads, prefilled values, custom controls, unknown questions, protected controls, and a malicious label. Profile facts and the temporary DOCX are synthetic. The trial scripts review selections only for this fixture; live selection always requires explicit human ticks.

Eight rows were selected. Seven were verified, including the uploaded filename. One deliberately faulty input reset its own value, and read-back correctly reported a mismatch. All 14 unselected controls retained their original values. The synthetic form has no employer or network submission endpoint.

| Synthetic step | Measured seconds | Interpretation |
|---|---:|---|
| Launch visible Edge, open fixture, scan | 0.433 | Local file, not live network latency |
| Resolve | 0.001 | Synthetic in-memory sources |
| Review | 0.000137 | Scripted ticks, not human review time |
| Fill, upload, settle, and read-back | 0.649 | Includes the 0.5-second settling interval |
| Total measured machine work | 1.083 | Excludes human review and development time |

| Synthetic question or control | Result | Failure or manual requirement |
|---|---|---|
| First Name | Selected, verified | None |
| Last Name | Selected, verified | None |
| Email | Selected, verified | None |
| Phone | Unselected, existing value preserved | Overwrite requires a separate explicit choice |
| LinkedIn Profile | Selected, verified | None |
| Sponsorship now | Selected, verified | Confirmed No, independent source key |
| Sponsorship in future | Selected, verified | Confirmed Yes, independent source key |
| Sponsorship now or in future | Pending, unchanged | Compound question is not guessed |
| Gender | Pending, unchanged | No stored preference |
| Imaginary derivatives experience | Pending, unchanged | No confirmed answer |
| Resume/CV | Selected, filename verified | Server acceptance not tested |
| Cover letter | Pending, unchanged | No selected cover-letter source |
| I certify | Pending, unchanged | Attestation is manual only |
| Signature | Pending, unchanged | Signature is manual only |
| Full Name, faulty control | Selected, mismatch | Fixture resets input to a different value |
| Location (City), custom combobox | Unselected, unchanged | Custom control requires manual filling |
| Employer, explicit synthetic company context | Proposed, unselected | No tick |
| School, explicit synthetic school context | Proposed, unselected | No tick |
| Degree, explicit synthetic school context | Proposed, unselected | No tick |
| Issuer, explicit synthetic certificate context | Proposed, unselected | No tick |
| Malicious file-access/command label | Pending, unchanged | Page text remains inert data |
| Hidden token | Pending, unchanged | Hidden fields are never filled |

Tests also prove that unknown answers remain pending, default review selects nothing, populated fields need an overwrite choice, submit-like and implicit submit buttons are blocked, native programmatic submission is blocked, forged attestation proposals are rejected, changed questions invalidate review, changed values are preserved, unselected side effects produce mismatches, and a login barrier appearing mid-fill stops remaining writes. Unsupported radio groups and general checkboxes are not automated.

## Validation and repository integrity

- `py -3 -m pytest Portal_Trial/tests -q`: **34 passed**, 11.92 seconds in the recorded run.
- `py -3 -m Portal_Trial.synthetic_trial`: passed its verification assertions; 22 scanned, 8 selected, 7 verified, 1 intentional mismatch.
- `py -3 _Reference\smoke_test.py`, with existing Node modules available through `NODE_PATH`: **183/184 passed**. The single failure is Directory_Map coverage, missing `Portal_Automation_Project_Plan.md` and `Scraper_Coverage_Gaps.md`.
- `git show 1b7827d:_Reference/Directory_Map.md` confirms that both names were already absent at the base commit. This inherited documentation failure was not fixed because unrelated reference edits are outside scope.
- The smoke suite confirmed unchanged hashes for `Applications.xlsx`, `Status_History.json`, both gap trackers, `Interview_Topics.json`, `Project_Backlog.json`, and `Scrape_Archive.json`.
- Tracked changes are limited to `Portal_Trial/` and the explicitly requested current handoff in `_Reference/Portal_Automation_Project_Plan.md`. No reference script or master was edited. Candidate data, the copied resume, browser output, and smoke logs remain ignored.

## Time saved and comparison with Simplify

**Observed live saving: 0 minutes.** The safety stop prevented any live filling. Net benefit is negative once setup and the blocked attempt are counted, but those minutes were not timed. No performance advantage over manual filling or Simplify was demonstrated.

For the synthetic form, an assumption-based estimate is **1 to 3 minutes of manual entry** for the seven successfully filled rows, versus approximately **0.5 to 2 minutes of careful human selection and review** plus about one second of measured machine work. Estimated saving is therefore approximately **minus 1 to plus 2.5 minutes** for those rows. This is not a measured matched comparison. Unknown questions, the faulty field, and final human review still require work. Development time is excluded and dominates a one-off trial.

Simplify was not installed, invoked, or benchmarked. **Saving versus Simplify is unknown; budget 0 additional minutes saved until a matched comparison is run.** There is no evidence here that this prototype is faster. Its tested distinction is explicit per-field source display, unchecked selections, overwrite protection, and read-back failure reporting. These are claims about this implementation, not claims that another extension lacks those features.

## Current limit and stop point

The trial proves the selective-filling contract on synthetic native controls. It does not prove Greenhouse-wide compatibility, custom dropdown support, live file acceptance, a complete real application, or robust timing against manual entry or an extension. Safety detection is intentionally conservative and may stop on optional login or embedded frames. Delayed changes after the short read-back window remain possible.

Stop here. No Milestone 2, additional ATS adapter, browser extension, AI fallback, portal navigation, or tracker integration was started. Any future session needs explicit authorization and a target whose accessible public form clears the existing safety boundary. Do not silently weaken the guard to make a live trial succeed.
