# Workday field notes (learned 2026-10-29: Provident, Regions, KeyBank, BBH)

Author: Yazad Madan. Operational facts only. Update in place when a new portal behaves differently.

## Before touching a page
- Simplify runs in the same Edge profile and keeps filling after the page looks done. Read only after form values stay unchanged for 5 s (`step_pass.wait_until_quiet`). A read during its fill looks like missing data and a write collides with it.
- Simplify overwrites answers, adds junk rows (certifications become education rows, e.g. CFA Institute, ICAI), and puts a stale date in date fields (12/29/2010 on BBH).
- One process per tab. Never run `apply.py`, `step_pass.py` and a hand script on the same tab together. Two runs on one tab hang with an empty log.
- Output is buffered. Launch with `py -3 -u` and a log file. A launcher "completed" notice is not completion. A log that stays empty for minutes means a hung run: kill that one PID and relaunch.

## Page structure
- Steps differ per tenant. Regions and KeyBank: 5 steps. BBH: 6 steps (adds Self Identify with the CC-305 disability form).
- Next button text differs ("Save and Continue", "Next"). Select by `data-automation-id` `pageFooterNextButton` or `bottom-navigation-next-button`.
- Go back with the Back button. The progress bar items do not navigate.
- Header "Sign In" can show while an application is open. Check the step title, not the header.
- BBH job page has two Apply links and the first click can time out. Open `<job url>/apply` directly.

## Fields
- Dropdowns are `button[aria-haspopup=listbox]`; options are `[role=option]`. Match the option text exactly or by prefix.
- Option wording differs per tenant. Veteran, ethnicity and similar self-ID options are worded differently per tenant ("not a protected veteran" vs "not a veteran"; ethnicity with or without "(Not Hispanic or Latino)"). Store alternatives as "a|b" in the intent answer. Pass a list of alternatives and take the first that exists.
- The question text is the first line of the field. Do not build a label from the whole field text: it includes the selected value ("<option> (Not Hispanic or Latino)") and trips keyword rules. That bug reset ethnicity to "Not Specified".
- Skills is a closed vocabulary (search returns Accounting, Finance only). Do not fill it. It is not required.
- Education school is a plain text box on BBH. Fields: schoolName, degree, fieldOfStudy, gradeAverage, firstYearAttended, lastYearAttended.
- Radio groups (Yes/No) exist, for example "previously worked at BBH". Read with `input[type=radio]`, set with `get_by_label(answer, exact=True).check()`.
- Date widgets are three inputs (month, day, year). A plain `fill` does not stick. Type digits with `Tab` between. Never press Enter in a date field. Never retry a click on an off-screen box: the retry loop scrolls the page up and down and locks the user out.
- Name fields follow the passport: never split the first name or invent a middle name (details in the local answer memory).
- Minimum or desired pay: low end of the JD range.
- Required marker is an asterisk in the label. Optional blank text fields (Phone Extension) are not unknowns.

## Attachments
- The slot reader can call KeyBank's only Resume/CV control "Attachments" and treat it as the cover slot. `workday_attachments.py` now maps it to resume when no cover letter is expected and no resume input is found.
- Upload by `set_input_files` on the right input, then check the "KB" size shown against the file. A stale copy from an earlier application can sit beside the new one: delete the stale one first.
- Expected resume size shows as a rounded binary KB (11,744 bytes shows 11.47 KB).

## Answers that repeat across companies
- Sponsorship by wording: Yes when the question lists CPT, STEM OPT or OPT. No when it names only H-1B (or H-1B, TN, E-3). Check the exact words each time.
- Acknowledgement and "I have read and consent" dropdowns and boxes: auto-select. Arbitration agreement: auto-tick for KeyBank only (approved).
- Work, education and language history on "use my last application" pages: match carried rows first (legal suffix and trailing asterisk stripped, school matched on first significant word). Never add a row when one exists.
- Company-specific one-time items (for example a completed tax credit survey and its confirmation number) live in the local company KB, not in this repo.

## Intent layer (built 2026-10-29)
- `intent_layer.py` maps a question to an intent id (`prev_worked_here`, `sponsorship_h1b_only`, `sponsorship_opt_listed`, `non_compete`, and 20 more). One stored answer per intent serves every company. Answers sit in answer memory under `intent:<id>` (local, gitignored); only the patterns are in the repo.
- Lookup order in `step_pass.resolve`: exact text in answer memory, company KB, then intent. A stored answer never replaces a different filled value (logged as CONFLICT) unless `--overwrite` is passed. Answers YES and NO expand to the portal's own wording (Yes, Opt In, I agree).
- New question: answer it once, then `py -3 intent_layer.py learn "<question text>" "<answer>"`. Unclassified questions stay exact-text only. Add a pattern to `INTENT_PATTERNS` and a case to `tests/test_public_intent_layer.py` when a repeating question is not classified.
- `answer_memory.update_memory(fn)` saves only when `fn` returns a truthy value. A function that returns nothing silently saves nothing.

## Process lessons
- Never run `git stash push <file>` then `git stash pop` in one chain. When the push fails, the pop applies an older stash. Check `git stash list` first.
- Do not kill processes by a broad pattern. List by script name first, then stop by PID.
- Open items: two failing tests in `tests/test_public_workday_upload.py` (`same_file_already_attached_does_not_dispatch_again`), not yet compared against HEAD; BBH step 4 multiselect ethnicity not matched by `step_pass`. `step_pass` now also uploads the resume (`--resume`), fills blank history rows (`--history-file`), writes a run report (`--report-path`) and full unknowns (`--unknowns-out`).

## Learned 2026-10-29 (Tyson, Visa, Capital One, RBC)
- Prefill differs per tenant. Visa and Capital One carried work rows and dates from Simplify. Tyson was blank: type title, company, location, role description, then dates.
- Date widgets: focus the month box, then per part `ControlOrMeta+A`, type digits, `Tab`. A typing delay produced a wrong month ("05" read as 2). `step_pass` now skips date fields that already hold values.
- Search-type fields (school, field of study): type the text, press Enter, wait, click the `promptOption`. Typing alone shows "No Items". Rutgers appears as Rutgers University-Newark.
- Education degree list is per tenant (Tyson: M.S.). Resume must be uploaded by `set_input_files` and checked against the shown KB size (11,822 bytes shows 11.54 KB).
- Unclassified questions are not saved by `intent_layer.py learn` (it returns None and stores nothing). Store exact-text answers with `answer_memory.remember`. Classified intents still need the right stored answer: `sponsorship_opt_listed` held No and overwrote a correct Yes until fixed.
- Sponsorship by wording: OPT/F-1/CPT listed means Yes (Visa, Capital One). Generic "sponsor or renewal of work authorization" means No (Tyson). RBC "now or in the future" left No by Yazad.
- Salary dropdown with no JD range: lowest band. Work type: full time.
- "I accept" voluntary-disclosure checkbox is auto-ticked (`ACK_LABEL` now includes `^i accept`).
- "Are you a protected Veteran?" with Yes/No/I do not wish to answer: answer No. The generic veteran rule does not match it.
- Visa: Opt-In for SMS, Opt-In for AI review tool. Going back from Review uses `pageFooterBackButton`; the pass re-sets answers from memory on the way forward, so fix memory first.
