---
author: Yazad Madan
updated: 2026-10-04
status: Version 0.8.0 validated: session-profile repair and PF4 synthetic coverage complete; FULL 368 and PUBLIC 286 OK with 2 skips each
---

# Status and next steps

This replaces the earlier probe reports and the two-prototype review. Their findings are folded in below, and the originals remain in Git history. `docs/TRIAL_ERRORS.md`, `portal_pipeline/HANDOFF.md` and `docs/GREENHOUSE_CONTRACT.md` stay as the detailed evidence logs.

## What exists

A Manifest V3 extension and a local Python helper that review and fill only the fields the user selects. The human logs in, navigates and submits. The tool never submits, signs, attests, or handles passwords or CAPTCHAs. Sponsorship now and sponsorship in the future stay separate answers, and unknown answers stay pending.

## Done so far

**Version 0.8.0 reviewed integration (October 4, 2026).** Application review now requires a structurally valid session profile, rejects malformed fact values, keeps unknown empty profiles reviewable, and invalidates cached edits, selection, and overwrite when their sourced proposal or draft changes. Unchanged snapshots preserve human edits. Tailored employment drafts appear separately without automatic insertion or selection. Thirteen new session-profile tests and nine PF4 Greenhouse tests are integrated. Greenhouse control replacements fail closed until an explicit rescan; country and city typeahead stay manual without a verified popup contract. Only the five approved mock setup files changed, without altering inherited assertions. FULL 368 tests in 226.742 seconds and PUBLIC 286 tests in 170.509 seconds pass, each with two Windows symlink-privilege skips. Four replay tests pass in 7.749 seconds; JSCHECK, PYCHECK, and diff checks pass. Manifest version is 0.8.0 with unchanged permissions. Synthetic only; no live employer application was filled or submitted.

**Session-profile review fix (synthetic only, October 4, 2026).** The review panel requires a valid per-session profile before scan or Fill. It rejects malformed facts and keeps an empty values object pending. Per-row snapshots clear stale selected answers after proposal, source, status, sponsorship, or tailored draft changes. Matching employment description drafts show source and review status without filling. Eleven focused regressions and 23 approved mock-dependent tests pass; syntax, compilation, and diff checks pass. No live portal action occurred.

**Approved safety landing (October 4, 2026).** Yazad approved the exact two inherited CSP waits and five session-profile mock setup changes. The two popup waits now use locator assertions preserving their prefix/substring conditions and 30-second timeouts. Production CSP remains unchanged. The previously held manual-field, attestation, and first/repeated resume-upload guards are now validated with this harness repair. FULL 346 tests in 212.146 seconds and PUBLIC 264 tests in 153.942 seconds pass with two symlink-privilege skips each. JavaScript syntax, Python compilation, and diff checks pass. No live portal actions occurred. Session-profile implementation and PF4 synthetic coverage are separately under review.

**PF4 Greenhouse completion, synthetic only.** Nine new browser cases cover adapter routing, read-only scan, selected fill, overwrite preservation, CAPTCHA gating, final-review detection, zero submit events, stale react-select references requiring rescan, and country/city typeahead remaining manual without a verified contract. All nine pass in Edge. No adapter behavior or host permissions changed. Live popup ownership, typeahead selection, remote persistence, and upload completion remain unverified.

**Parallel safety integration held for harness approval (October 4, 2026).** Final validation at code commit dd92b4b: FULL 345 tests in 198.366 seconds has one inherited CSP harness error and two symlink skips. The isolated case failed again after an earlier isolated pass. PUBLIC 264 tests in 148.794 seconds passes with two skips. JSCHECK, PYCHECK and diff checks pass. No production safety rule was weakened, no inherited test was edited, and no live portal actions occurred. The completed code and failure evidence are saved on integration/validated-portal-phases, held off main until the inherited test wait can be repaired with approval and FULL rerun successfully.

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
8. **Phenom (PF5, synthetic only).** The registered adapter routes the two documented career-site hosts, scans a fabricated five-step wizard, reports step and final-review markers through P7 progression, skips the LinkedIn iframe, and blocks every write when synthetic CAPTCHA markup is present. The answer sheet names Phenom on those hosts. Eighteen Phenom tests cover selected fill, preservation, read-only answer-sheet export, all wizard pages, gate behavior, final-control precedence, P7 denylist behavior, and zero submit events. Real apply hosts, page structure, and CAPTCHA placement remain UNVERIFIED. See `docs/contracts/PHENOM_CONTRACT.md`; obtain Inspect-only exports before treating this as live compatibility.

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

Phase order lives in D:\Code\Resume\_Reference\Portal_Phased_Execution_Plan.md. The approved safety, CSP harness, session-profile, and PF4 Greenhouse phases are validated and integrated. Their earlier pending-approval and held-validation entries are historical.

Next: Workday PF1 and Oracle PF2 may continue against synthetic fixtures, but real post-login compatibility requires Yazad's Inspect-only exports. Neither portal's export directory exists in the primary checkout as of October 4, 2026. Keep login, MFA, CAPTCHA, signatures, and submission manual. Country/city typeahead and remote upload completion remain unverified. P9 stays blocked until PF1/PF2 are merged and the corpus includes at least 50 Yazad-approved real pending wordings. No real model calls or live portal probes are authorized by this handoff.

## Rules to keep when working here

- Run tests with the real source checkout configured, since the synthetic-only run hid the regression in item 2.
- Give subagents narrow, measurable jobs. A summarizing probe fabricated field counts and time savings, while scanner-only runs returned usable data.
- Never write real candidate data into this public repository.
- Commit each completed phase separately. The active user instruction authorizes reviewed, validated, non-force pushes directly to main.
