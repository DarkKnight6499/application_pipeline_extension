---
author: Yazad Madan
updated: 2026-10-20
status: Live inspection and native UI observations; extension filling remains unverified
---

# Workday contributor handoff

## Start here

Use this branch, based on `154d6e0`, rather than `origin/main`. Main still points to `bcdea7f` and lacks the October 11 preparation. This publication adds documentation only. The code baseline is `f183c90`; `154d6e0` records its laptop validation.

The owner requested other portals before Greenhouse. Workday is the current live target. Continue one employer at a time. Read `AGENTS.md` and the existing phased plan before development.

## What was actually exercised

On October 18, 2026, the owner selected Citi Workday requisition `26995518` on `citi.wd5.myworkdayjobs.com`. Native Windows computer use accessed the existing Edge window. The browser connector returned an empty inventory. The local helper returned HTTP 200. The installed extension opened Inspect-only mode and exported structures without pairing or importing an application.

The owner completed authentication manually. At the owner's later request, native UI actions filled confirmed contact facts, five sourced employment records, and two education records. Both Save and Continue actions advanced successfully. These were native UI writes, not extension-engine writes. Inspection continued in the extension side panel. The source Resume checkout was read only; no tracker, master profile, builder, or application artifacts were written.

Last observed page: **Application Questions 1 of 2, step 3 of 6**. One sourced authorization answer was selected and revealed a document-verification question. Other required answers were not completed. The owner subsequently supplied five missing responses; those are private, and their entry remains pending. The browser has not been rechecked on October 20, so do not assume its session or unsaved state survives.

No resume was prepared, imported, or uploaded. No signature, attestation, final submission, Application ID allocation, or tracker status change occurred. Questions page 2, voluntary disclosures, final review, and remote attachment persistence remain unverified.

## Observations and scanner gaps

| Surface | Observed live | Extension export or remaining limit |
|---|---|---|
| Posting entry modal | Apply Manually led to the same Workday tenant. | Zero fields; one iframe and one open shadow host reported. |
| Account gate | Authentication preceded the application. | One email control and three protected controls omitted. Owner handled credentials. |
| My Information | Contact form plus required Country, State, and Phone Device Type button menus. | Eleven controls captured. All three button menus omitted. |
| Referral source | Search dialog with categories; searching yielded distinct LinkedIn and LinkedIn Job Board options. | Exported as ordinary text, zero options, no adapter. |
| Phone country code | Search dialog, selectable options, and a removable selected token. | Exported as ordinary text, zero options, no adapter. |
| Employment creation | Add and Add Another created five distinct rows. | Row IDs changed as rows were created. No automatic row creation is implemented by this trial. |
| Employment dates | Separate editable month/year spin controls accepted sourced values. | Exported as text; unsupported-spinbutton count remained zero. This does not prove date-widget coverage. |
| Employment and education export | Fifty-five controls: 45 text, five checkboxes, five textareas. Twenty-four date components were present. | Every exported record was null. Correct repeated-row attribution remains unverified. |
| School and study pickers | Search dialogs selected school and field tokens. A unique search result could be committed by Enter. | Search-input detection is not verification of the associated picker. |
| Degree menus | Required button menus; some actual degree names were absent. | Degree buttons omitted. Keep actual source degrees separate from owner-approved portal categories. |
| Resume/CV | Visible drop zone and Select files; page stated 5 MB maximum. | No file field appeared in the 55-control export. Upload was not exercised. |
| Conditional questions | Authorization selection revealed another required question. | Rescan after each answer that changes structure. Questions are not all available from the initial snapshot. |
| Routing label | Exports reported portal generic. | `engine.js` currently labels non-Greenhouse inspection generic. This alone does not prove routing failed. |

Open shadow content was not inspected and its ownership was not established. Third-party Simplify UI was also present. Do not attribute every iframe or shadow host to Workday.

## Failures and practical lessons

- A country selection changed unexpectedly during the trial; the cause was not established. A later coordinate correction selected a neighboring country. Exact option selection and readback corrected the country and dependent phone code before saving. Record and recheck dependent controls after country changes.
- Menu animations, asynchronous search results, resizing, and overlapping side panels made immediate observations stale. Wait for settled state, use fresh accessibility targets, and verify the selected label. Offscreen option clicks were refused; scrolling or dragging the visible scrollbar was required.
- One resize produced a blank posting body. Refreshing the unfilled posting restored it. Do not refresh a partially filled page without checking what would be lost.
- Raw added-row export failed intake validation. `TOKEN` in `export_intake.py` matches long mixed-case identifiers containing digits, including `workExperience-23--startDate-dateSectionMonth-input`. This is a demonstrated structural-ID false positive, not a reason to disable secret checks. Keep the raw export private until a narrow fix or reviewed redaction exists.
- The empty My Experience export captured no controls before rows were added, despite a visible resume picker. Empty export does not mean complete page coverage or no required work.
- Reusable answers reduce lookup time. Native UI entry still needs individual checks. No measured speedup or unattended compatibility is claimed.

## Private continuation data

These paths are Git-ignored and intentionally absent from the publication:

- `portal_pipeline/data/exports/workday/`: five raw exports, chronological evidence, and an incomplete generated contract/fixture draft.
- `portal_pipeline/data/reusable_answers.json`: confirmed facts, provenance, sourced employment/education, owner-approved portal mappings, and employer-scoped answers. This is a local JSON artifact, not an implemented extension input route.
- `portal_pipeline/data/simplify_saved_answers_review.json`: read-only review of saved-answer cards. Numeric salary entries disagreed; some text was employer-specific; visa wording required context; an invalid title placeholder and saved attestations were present. Do not promote these wholesale into generic defaults. No Simplify answer or setting was edited.

A contributor without these files must obtain approved local inputs from the owner. Never commit candidate answers, profile snapshots, raw browser exports, document contents, pairing tokens, signed URLs, cookies, or browser profiles. Private notes contain earlier intermediate states; this handoff describes the final observed checkpoint.

Source precedence matters: authoritative non-overlapping role dates came from `Builder_Internals.md`; role descriptions came from `Application_Boilerplate.md`; identity and education came from `Resume_Content_Master.json` through the existing resolver. Optional unknown GPA, education start years, and language proficiency were not invented.

## Next work

1. Recheck the selected browser and saved application state with the owner. Complete the five confirmed pending questions from private inputs. Keep login, CAPTCHA, attestations, and submission manual. Defer resume upload until the existing Resume workflow supplies one audited folder.
2. Add a narrow regression for the intake structural-ID false positive while retaining rejection of genuine secret-like strings. Do not weaken existing assertions without the project's required approval.
3. Capture the Workday button-menu and search-dialog contracts, including stable popup ownership and rerender behavior. Build anonymized fixtures from reviewed observations, rather than treating the incomplete generated fixture as a complete DOM reproduction.
4. Cover omitted degree/upload controls, date semantics, and repeated-row attribution. Verify through the actual loaded extension, with unselected-field preservation and zero final submission events.
5. Revisit field persistence after navigation and resume completion indicators separately. Native UI success does not satisfy extension live acceptance. Keep Greenhouse last unless the owner changes priority.

## Validation and sources

Prior laptop acceptance recorded in `154d6e0`: FULL 573 tests in 213.1 seconds, two skips; PUBLIC 491 in 155.9 seconds, 19 skips. These are inherited October 11 results, not tests rerun for this documentation publication.

Publication checks passed: exactly five documentation paths, author attribution, added-text privacy and punctuation checks, eight relative links, evidence counts, ignored private artifacts, and Git whitespace checks. No runtime suite was rerun because this publication changes no code.

Live sources that worked: Citi's rendered Workday UI, Inspect-only exports, the local helper dashboard, native Windows computer use, and the existing read-only profile resolver. The browser connector was unavailable. The first four raw exports passed intake validation, with empty-page or long-label warnings where applicable; the fifth failed on structural IDs. Neither external job-data APIs nor search were needed. Live employer state after October 18 has not been revalidated.
