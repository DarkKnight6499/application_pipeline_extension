---
author: Yazad Madan
updated: 2026-10-04
status: placeholder answer sheet fix on fix/answer-sheet-placeholder, rebased onto 996a674; FULL 306 and PUBLIC 225 OK with 2 skips each
---

# Status and next steps

This replaces the earlier probe reports and the two-prototype review. Their findings are folded in below, and the originals remain in Git history. `docs/TRIAL_ERRORS.md`, `portal_pipeline/HANDOFF.md` and `docs/GREENHOUSE_CONTRACT.md` stay as the detailed evidence logs.

## What exists

A Manifest V3 extension and a local Python helper that review and fill only the fields the user selects. The human logs in, navigates and submits. The tool never submits, signs, attests, or handles passwords or CAPTCHAs. Sponsorship now and sponsorship in the future stay separate answers, and unknown answers stay pending.

## Done so far

**Pending select answer sheet export fix (synthetic only, October 4, 2026).** The panel now exports an unanswered select as an empty proposal, preserving its pending status instead of exporting the placeholder label as an edited draft. `answer_sheet.py` already clears empty proposals and normalizes them to pending, so no backend change was needed. Two new synthetic browser regression tests pass. The second fills only the selected native select, preserves other controls, and observes zero submit clicks or events. FULL 306 and PUBLIC 225 pass with two symlink-privilege skips each. JSCHECK, PYCHECK, and diff checks pass. Rebased onto P7 commit `996a674`; no live portal interaction occurred.

**Sponsorship toggle landing (synthetic only, October 4, 2026).** Rebased over main `2904ded`, preserving P8 record routes and the session-profile allowlist. The per-application toggle defaults to truthful, changes only future and combined sponsorship proposals, displays the boilerplate answer beside the proposal, and never selects fields automatically. Mode changes clear affected answers, selections, and overwrite choices while preserving unrelated edits. Cached sponsorship reviews from another mode are discarded. The toggle is disabled during filling, and Fill is disabled during mode saving. The original nine backend tests and five new browser tests pass; FULL 284 tests and PUBLIC 203 tests both end OK with two symlink-privilege skips. JavaScript syntax, Python compilation, and diff checks pass. Existing tests were not edited. No live portal validation occurred.

**P7 progression guards (synthetic only, October 4, 2026).** Rebased onto `80490bf`, preserving sponsorship-mode locks and invalidation, the per-session profile allowlist, and P8 record routes. The page check sweeps required fields, detects repeated missing sets, classifies one safe Next control, stops at final review or a human gate, and keeps guarded Next disabled by default. Native submit controls remain ineligible even when labelled Next. A second resume upload is skipped only after both incoming and attached bytes match the reviewed checksum; changed or detached controls fail. Six new regressions passed without editing existing tests. FULL 304 and PUBLIC 223 passed, each with two symlink-privilege skips. JSCHECK, PYCHECK, and diff checks pass. The `rg submit` acceptance output includes the denylist and explicit native-submit guards required by the safety review. Synthetic only; no live portal interaction occurred. Next queued phase: PF5 Phenom.

**P6 selective fill hardening (synthetic only).** Each fill is read back after the blur and settle wait. A value that reverts is reported failed with reason "reverted after blur" (failure_kind reverted); an aria-invalid flag or error text inside the field's own container is captured in validation_error (failure_kind validation_error). The trusted_keystrokes strategy throws "not enabled" before any write. Overwrite semantics unchanged and now tested per control type. Manifest version 0.6.0, no new permissions. Never verified on a live portal.

1. **Safety work from the external contributor, merged to main (commit 765e17b).** Radio groups are bound to their own form, protected collateral changes stop a fill, upload targets are revalidated, unconfirmed profile answers stay pending, helper session paths are contained, and inspection coverage is reported with host checks on every rescan.
2. **Real-source compatibility (pull request 4, open).** The merged suite failed 5 tests and errored 1 when run against the real workflow checkout, although it had passed with synthetic fixtures. The strict profile parser dropped answers such as "No (on F-1 OPT)", two tests were stale, and a popup handler could be attached too late under load. All fixed.
3. **Greenhouse dropdown adapter (pull request 5, open, stacked on 4).**
   - Fills the react-select dropdowns on Greenhouse job-boards forms and reads each value back. It follows the structure observed on a live public posting and refuses anything that does not match it.
   - Verified on the real Robinhood form in a headless browser: the work authorization and sponsorship dropdowns filled and read back, five EEO dropdowns were refused, and no application request was sent.
   - Classifies work authorization and sponsorship questions from about 16 verbatim real wordings. It does not invert "Do you require work authorization?", skips place-dependent questions and ones phrased "without sponsorship". The combined "now or in the future" question is answered from the two separate confirmed answers.
   - Blocks bot-trap inputs found on Oracle and Workday sign-in screens, and protects survey options by their container, because Lever lists choices such as "White" and "Asian" whose own labels carry no demographic word.
4. **Suite status.** 178 tests pass against the real source checkout, with 2 skipped for lack of symlink privilege.
5. **Preflight gates (P4, synthetic only).** `portal_pipeline/preflight.py` reads the tracker read-only and the JD document, and the panel lists the results before any fill. Duplicate postings, a Blocked, Skipped or Expired tracker status, and a no-sponsorship JD block until acknowledged; knock-out questions need acknowledgement; status and sensitive questions are forced manual. A gate that cannot run is shown as a warning, and a failed preflight request keeps Fill disabled.
6. **Answer sheet (P5, synthetic only).** `portal_pipeline/answer_sheet.py` and `POST /api/sessions/<id>/answer-sheet` turn a read-only scan into a per-page JSON and offline HTML sheet under the session folder, with sources, required flags, UTF-16 character counts and limits (`maxlength` is now in the scan structure). Protected fields never appear, pending and manual rows carry no value. The panel also lists required and pending fields, saves an edited answer through the override route, and logs pending questions to the corpus.
7. **Portal record (P8, synthetic only).** `portal_pipeline/portal_record.py` keeps one record per tracker Application ID under ignored `portal_pipeline/data/records/`, with each page's proposed, selected, filled and read-back answers, the resume hash and an optional `sponsorship_answer_mode` (defaults to truthful). Routes: `GET/POST /api/sessions/<id>/record` and `POST /api/sessions/<id>/reported-submitted`. The helper never writes the tracker: after the user reports a submission it only prints the `mark_application_status.py` command, with the employer reference kept separate from the Application ID.

## What the probes established

Public pages only, nothing typed or submitted.

| System | Share of the job queue | Form visible without login | Main blockers |
|---|---|---|---|
| Oracle Cloud (JPMorgan) | 143 | No | Email gate, hCaptcha, honeypot input |
| Workday | 125 | No | Create Account or Sign In is step 1 on every tenant tested |
| Phenom (Marsh, Franklin Templeton) | about 110 | Yes, step 1 | Five-step wizard, reCAPTCHA on Marsh, LinkedIn iframe |
| Eightfold (New York Life, Millennium, HSBC) | about 94 | Yes for New York Life | 15 custom dropdowns; HSBC hands off to SuccessFactors |
| iCIMS | few | Email capture first | Whole form inside an iframe the scanner does not enter |
| SuccessFactors | few | Fitch only | Ten custom picklists; others sit behind a sign-in |
| Taleo | few | No | Login first |
| Lever, Ashby, Workable, Dayforce | few | Mostly | Per-system dropdowns, labels held outside the field, hosts not yet allowed |
| Greenhouse | handful | Yes | Done for Yes/No dropdowns; country and city typeahead stay manual |

Also found:
- The extension only allows Greenhouse and Workday hosts today.
- Some queue links are dead: 6 of 18 sampled Workday tenants showed a missing posting, and the Marsh links redirect to the home page.
- No public source holds a recorded post-login Workday page or any Oracle apply-flow automation. Workday selectors found in open-source code are from hand-written or live-run code and are unverified here.
- Greenhouse, Lever and Workable publish their question lists through public endpoints, which could remove DOM guessing for those systems. Eightfold's questions endpoint exists, but its body was not read.
- The open-source extension offeros (Apache-2.0) has reusable logic for Workday listbox buttons, repeated sections and option matching. Its automatic "Save and Continue" click must be left out. Date pickers have no permissively licensed reference.
- One unverified risk: a framework README reports a real Workday resume import dropping dates joined by an en dash. The master resume uses en dashes in its date ranges. Untested here.

## Way ahead

Phase order now lives in D:\Code\Resume\_Reference\Portal_Phased_Execution_Plan.md. The current handoff queue is sponsorship toggle landing, P7 landing, PF5 Phenom, and the remaining review fixes. The sponsorship task is complete; landing details are recorded in section 9 of the plan. Next task: rebase `feat/p7-progression`, preserve the sponsorship review guards, rerun the required checks, and push to main. One task per session.

The earlier ordered list is kept in Git history. Items still open from it: Phenom adapter, post-login Workday and Oracle exports, the en-dash autofill check, Eightfold, iframe support for iCIMS and Lever, a liveness check before filling, and the Lever question-label resolver. They map to phases PF1 to PF14 in the plan.

## Rules to keep when working here

- Run tests with the real source checkout configured, since the synthetic-only run hid the regression in item 2.
- Give subagents narrow, measurable jobs. A summarizing probe fabricated field counts and time savings, while scanner-only runs returned usable data.
- Never write real candidate data into this public repository.
- Commit each phase on its own branch and open a pull request instead of pushing to main.
