---
author: Yazad Madan
updated: 2026-10-04
status: Greenhouse dropdowns verified live on one public form, Workday and Oracle blocked on post-login structure
---

# Status and next steps

This replaces the earlier probe reports and the two-prototype review. Their findings are folded in below, and the originals remain in Git history. `docs/TRIAL_ERRORS.md`, `portal_pipeline/HANDOFF.md` and `docs/GREENHOUSE_CONTRACT.md` stay as the detailed evidence logs.

## What exists

A Manifest V3 extension and a local Python helper that review and fill only the fields the user selects. The human logs in, navigates and submits. The tool never submits, signs, attests, or handles passwords or CAPTCHAs. Sponsorship now and sponsorship in the future stay separate answers, and unknown answers stay pending.

## Done so far

1. **Safety work from the external contributor, merged to main (commit 765e17b).** Radio groups are bound to their own form, protected collateral changes stop a fill, upload targets are revalidated, unconfirmed profile answers stay pending, helper session paths are contained, and inspection coverage is reported with host checks on every rescan.
2. **Real-source compatibility (pull request 4, open).** The merged suite failed 5 tests and errored 1 when run against the real workflow checkout, although it had passed with synthetic fixtures. The strict profile parser dropped answers such as "No (on F-1 OPT)", two tests were stale, and a popup handler could be attached too late under load. All fixed.
3. **Greenhouse dropdown adapter (pull request 5, open, stacked on 4).**
   - Fills the react-select dropdowns on Greenhouse job-boards forms and reads each value back. It follows the structure observed on a live public posting and refuses anything that does not match it.
   - Verified on the real Robinhood form in a headless browser: the work authorization and sponsorship dropdowns filled and read back, five EEO dropdowns were refused, and no application request was sent.
   - Classifies work authorization and sponsorship questions from about 16 verbatim real wordings. It does not invert "Do you require work authorization?", skips place-dependent questions and ones phrased "without sponsorship". The combined "now or in the future" question is answered from the two separate confirmed answers.
   - Blocks bot-trap inputs found on Oracle and Workday sign-in screens, and protects survey options by their container, because Lever lists choices such as "White" and "Asian" whose own labels carry no demographic word.
4. **Suite status.** 178 tests pass against the real source checkout, with 2 skipped for lack of symlink privilege.

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

## Way ahead, in order

1. **Review and merge pull requests 4 and 5.** Rerun the suite against the real source first. Delete the stale `review/stacked-pr-trial` worktree only after checking whether the other session still needs it.
2. **Phenom adapter.** Highest volume that is reachable without login. Allow the host, handle the LinkedIn iframe, handle the multi-step wizard, and expect plain native selects with predictable `cntryFields.*` and `phoneWidget.*` ids.
3. **Real post-login structure for Workday and Oracle.** Use **Inspect page only**, then **Export field structure**, on each step of a logged-in Workday application and a JPMorgan Oracle application, saved without entering answers. This replaces guessing. Then build, per system, a dropdown adapter, repeated-section handling and a date handler. Reuse offeros logic with its license header and a NOTICE entry.
4. **Settle the en-dash question.** Try "Autofill with Resume" on one Workday tenant with a throwaway account. If dates drop, change the master resume date ranges to a plain hyphen, after asking before touching any built resume.
5. **Eightfold form for New York Life.** Same dropdown technique as Greenhouse, with the cookie banner dismissed first.
6. **Frame support for iCIMS and Lever, and host allow-list additions.** Only if the volume justifies it.
7. **Liveness check before filling.** Skip postings whose Apply control is missing.
8. **Add the Lever question-label resolver**, so authorization and sponsorship wording is read from the question block and not the radio labels.

## Rules to keep when working here

- Run tests with the real source checkout configured, since the synthetic-only run hid the regression in item 2.
- Give subagents narrow, measurable jobs. A summarizing probe fabricated field counts and time savings, while scanner-only runs returned usable data.
- Never write real candidate data into this public repository.
- Commit each phase on its own branch and open a pull request instead of pushing to main.
