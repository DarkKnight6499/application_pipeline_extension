# Resume to portal prototype

This project adds a local helper and a Chrome or Edge extension to the existing resume workflow. Development now lives in the dedicated `application_pipeline_extension` repository. The original prototype was developed in the isolated `D:\Code\Resume_portal_pipeline` worktree on `feat/portal-pipeline`. The Resume checkout remains usable independently.

The working path is: prepare an application through the current workflow, import its audited resume, review its layout in Word, scan the portal, select fields and answers, fill those fields, and finish the application manually. A separate sandbox builder and a synthetic Workday form support development without opening an employer account.

## Start the helper

For a self-contained dummy application, follow [CONTRIBUTING.md](../CONTRIBUTING.md) and run `python -B portal_pipeline/demo.py` with the configured environment. The production helper below still requires the private Resume checkout. Install `portal_pipeline/requirements.txt` into the Python environment used to start it.

From this repository:

```powershell
.\portal_pipeline\start.ps1 -Source D:\Code\Resume
```

Equivalent command:

```powershell
py -B portal_pipeline\server.py --source D:\Code\Resume --port 8766
```

Open [the local dashboard](http://127.0.0.1:8766). Use this exact loopback address. The existing workflow supplies `python-docx`, `openpyxl`, and the Node `docx` package used by its builder. Importing an already built application does not invoke the Node builder. Sandbox building does.

The source checkout is read-only for the helper. Session copies and generated demonstration files stay under `portal_pipeline/data/`, which Git ignores. The helper does not allocate Application IDs, write tracker rows, change statuses, or modify reference files. No application folders are listed for discovery. You provide one exact path.

## Use an existing application

1. Prepare the application through the current resume workflow. Complete its JD requirements review, audit, and input archival.
2. Paste its exact `Applications` folder into **Audited application folder**. If the tracker link leads to a job board or redirects to a different portal origin, enter the exact employer posting URL in the optional field. This override stays in the session and does not edit the tracker link. The importer requires `.application_id`, `Yazad_Madan.docx`, one `JD_*.docx`, and `_inputs/resume_content.json` plus one archived `Keywords_*.json`.
3. The importer requires an exact, unique tracker ID, matching company and role in the archived requirements, a posting URL, and status `New` or `To Apply`. It runs the existing `audit_application.py` in place and shows the report.
4. Download the copied resume and inspect the latest file in Word, including page count, wrapping, and widows. Confirm the visual review before enabling attachment.
5. Imported resumes are edited through the current workflow and imported again. Their source files and tracker context are checked again before upload. A change invalidates the earlier review.

The audit's eligibility gaps remain visible advisory findings. This prototype does not interpret a completed resume as a submitted application. It does not automatically tailor or invent resume claims.

## Install and pair the extension

1. Open `chrome://extensions` or `edge://extensions`, enable Developer mode, and select **Load unpacked**.
2. Select this repository's `portal_pipeline/extension` folder.
3. Copy the dashboard's pairing token. In the extension popup, enter the helper URL and token, then choose **Pair**. Restarting the helper changes the token.
4. Open the relevant application page and sign in yourself. Select **Scan current page** in the extension. An extension-owned side panel shows the proposed answers and their sources.
5. Confirm the page belongs to the selected posting. Choose individual fields or a section, edit answers as needed, and choose **Fill selected fields**.
6. Existing values are preserved unless you enable that field's **Replace existing** checkbox. Review the result for each selected field. Navigate to the next page manually and choose **Rescan**.
7. For an unsupported control, choose **Export field structure**. The JSON report records labels and control attributes without entered answers, profile proposals, option text, query strings, or protected controls. Review labels and IDs before sharing because an employer may put personal information in those attributes.
8. For each employment or education row, choose its employer and role or its school in **Profile record for ...**. Those fields stay disabled until you choose a record or explicitly choose manual answers. Page order is not used to assign candidate history.

After updating the prototype, reload the unpacked extension in its extensions page and refresh the application tab. Version `0.4.0` adds Greenhouse application-form boundaries and labelled hidden resume inputs. Version `0.3.1` added **Inspect page only**, which does not require helper pairing or an imported application. Version `0.3.0` added explicit history row choices, split month/year fields, and prevention of overlapping fills and rescans.

The extension requests page access on user action using `activeTab`. Its persistent host permission covers only the local helper. The current popup restricts scanning to Workday, Greenhouse, and the paired local fixture. Real employer compatibility remains unverified. The filling panel checks the posting origin and asks you to confirm the exact application.

For a walkthrough, open the Workday or Greenhouse application page and choose **Inspect page only** in the popup. The extension-owned panel lists control labels, types, sections, and manual reasons. It loads no candidate profile, offers no answer selection or fill action, and rejects scan and fill commands from that inspection panel. Export a report, navigate manually, and use **Rescan this page** for the next report. A posting or protected-only login/review page can legitimately show no inspectable fields. Pair and import an audited application later when ready to fill.

Login, MFA, CAPTCHA, demographics, signatures, attestations, and final submission stay manual. Password values are not exposed by scanning. No tokens or profile values are placed in an employer-page review panel. The injected panel appears only on the synthetic local fixture.

## Try the synthetic form

Expand **Develop with a sandbox application**, select **Try sample application**, review its copied content and JD requirements, and build the working document. Use the synthetic form link to test contact details, separate current and future sponsorship answers, repeated employment rows, and resume attachment.

The fixture deliberately includes an existing phone value, unknown questions, an implemented relocation dropdown, an unsupported editable dropdown, and protected final-review controls. The fixture's panel shares the extension's review logic. Sandbox sessions are restricted to the local fixture for portal filling and document attachment. Use audited import for an employer portal.

Its second page contains five employment rows and two education rows. Choose the intended source for each row before selecting fields. Changing a row's source clears that row's old edits, selection, and overwrite choice. Duplicate assignment of the same profile record to visible rows is rejected. Choose distinct records or use explicit manual answers if a portal requires a different structure.

Row choices last only within the current panel. Closing the panel, using Rescan, refreshing the application page, or replacing a row requires choosing again. Existing portal values remain preserved. A reordered live row retains its identity during the active scan, and a replacement row does not inherit an earlier binding.

## Verified behavior and limitations

Automated tests exercise the local backend, source preservation, audited imports, real Chromium form events, and an actual unpacked MV3 extension with its extension-owned review page. They verify selected filling, per-field overwrite, exact dropdown matching, stale-question rejection, collateral-change detection, repeated employment dates, upload checksums, and manual submission boundaries.

Field proposals use exact known question aliases. Unknown or compound questions require a manual answer. An authorization question for another country is not assigned the US authorization answer. Current sponsorship and future sponsorship remain separate facts. Missing street addresses, postcodes, education start dates, and other unknown facts remain pending.

Native text inputs, textareas, selects, radios, explicitly labeled resume file inputs, and a bounded class of custom dropdowns are implemented. The custom adapter requires a select-only combobox, one stable `aria-controls` link, and a single-select `role=listbox` popup. Only the selected combobox and one exact matching option are clicked. Delayed creation of that owned listbox is supported. Scanning and structure export do not open the popup.

The contract is based on the roles and properties in the [W3C Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/#wai-aria-roles-states-and-properties). The adapter deliberately supports a narrower contract: editable autocomplete, controls that publish ownership only after opening, legacy `aria-owns`, grid or dialog popups, ambiguous ownership, and links or submission controls remain manual. Its code lives in `extension/adapters/aria-listbox.js`.

Options are matched by case and whitespace normalization with punctuation retained. `C++`, `C#`, `-1`, and `1` remain distinct. Duplicate or disabled matches, changed questions, changed popup ownership, changed option lists, and side effects on unselected fields stop filling. Existing dropdown answers still require a per-field overwrite choice.

Separate start and end month/year fields can use components of verified `YYYY-MM` facts. Month dropdowns use their visible English full name, English abbreviation, or month number; opaque option values are not treated as month numbers. Missing dates and ambiguous month lists stay pending. A month-only fact never supplies a day for a full-date input. Education start dates remain unknown unless the current facts supply them.

Recognized history rows use only history-specific field aliases. Their Email, City, or Salary expectation questions do not borrow personal contact information or prospective salary answers. Unknown history questions need manual answers.

Greenhouse hosted forms matching the observed contract support a labelled hidden native resume input. Scanning stays inside one unique `form#application-form`, excludes internal ARIA-hidden inputs, and protects the full demographic container. Cover-letter inputs are identified separately; the resume is never used as a cover letter. The public Justworks form supplied the structural evidence. See [GREENHOUSE_CONTRACT.md](../docs/GREENHOUSE_CONTRACT.md). This does not establish remote upload completion or live form compatibility.

Other hidden uploads, cross-origin frames, adding or removing history entries, other portal-specific date controls, and automatic navigation are not implemented. History row discovery is validated only against the explicit synthetic sections; real employer grouping still needs inspection and an adapter. A failed dropdown attempt may leave its listbox open for manual review.

One fill runs at a time per page. The review panel disables editing, row changes, Close, and Rescan until the fill result is ready. Structure export remains available because it does not replace the active scan. Wait for results before manually navigating on the employer page.

A fill reports a verified DOM value after a short settling period. It does not guarantee that the employer saved the value on its server. A file input result does not prove the upload completed remotely. If a portal changes an unselected field, the engine reports the change and stops further writes. It does not silently roll the form back.

No real employer application has been validated yet. Live validation must independently verify Workday and Greenhouse through final review, with the user present and submission remaining manual.

See [INSPECTION.md](INSPECTION.md) for the real-portal inspection checklist and report interpretation.

## Run tests

Install browser test tooling if it is not already present:

```powershell
py -m pip install -r portal_pipeline\requirements-dev.txt
py -m playwright install chromium
```

Run from this worktree with the source checkout named explicitly:

```powershell
$env:PORTAL_SOURCE = 'D:\Code\Resume'
py -B -m unittest discover -s portal_pipeline\tests -v
```

Tests use temporary outputs. Import tests create a synthetic tracker and execute the original audit code in place with that synthetic tracker configured by a test wrapper. They do not copy or edit the production audit script. Browser upload approvals are test-only approvals for the local fixture. No real application status is changed.

See [HANDOFF.md](HANDOFF.md) for implementation progress and the next bounded task. Research and GitHub sources are preserved in [PROJECT_PLAN.md](../docs/PROJECT_PLAN.md).

## Per-field Fill assist

Author: Yazad Madan.

Start from the repository root with the normal Python launcher:
```powershell
py -3 -B portal_pipeline/server.py --assist-only --port 8766
```
Without `py`, use the configured Python executable with the same arguments.
The first start creates `portal_pipeline/data/assist_token.txt`, which is ignored by Git.
In normal Edge, open `edge://extensions`, enable Developer mode, choose Load unpacked, and select `portal_pipeline/extension`.
Assist setup: on that page click the extension's "service worker" link, and in its console run `chrome.storage.local.set({assistToken: "<value from assist_token.txt>"})`. The token never enters source. `ASSIST_PORT` in `extension/background.js` must match the server port.
Then refresh the application page.
Click Fill beside a question. Shift-click explicitly permits overwriting an existing value.
Stored answers precede drafts. A draft is not saved until you click Save this answer beside its field.
Missing answers enter the local learning queue. Eligibility, self-ID, signatures, and attestations remain manual even when stored. Sensitive questions never trigger drafting.
Drafting uses the logged-in `claude` CLI with built-in and MCP tools disabled and a 90 second timeout ([CLI flags](https://code.claude.com/docs/en/cli-reference)). No API key is required.
Configure the read-only knowledge and profile paths in `assist_api.py`; Resume files are never written.
The token stays in the extension worker. Question logs and the learning queue remain under ignored `data/`.
Signatures, attestations, navigation, and submission remain manual. DOM readback does not prove remote saving.

### Save page and sort captured questions

The left dock's **Save page** button, below **Learn page**, saves all visible labelled answers in one click without a review list. Learn page retains its reviewed saving flow. Confirm also appends successfully stored checked rows to the same capture file, preserving each source (legacy clients without a source use typed). Save page captures profile, eligibility, self-ID, signature, attestation, and SSN-labelled answers locally. Password and file inputs are not answers: their values are never read or sent, and the dock counts their exclusions. Save page refuses automation and never navigates or submits.

Captures append to ignored `portal_pipeline/data/page_questions.jsonl`, one JSON object per answer. Read or tail this file directly for chat review. It contains personal answers and must remain local. `assist_questions.jsonl` is the existing, unrelated log of labels asked through `/assist/answer`; it remains unchanged. Raw captures never supply Fill answers.

```powershell
py -3 -B portal_pipeline/questions_sort.py report
py -3 -B portal_pipeline/questions_sort.py report --json
py -3 -B portal_pipeline/questions_sort.py promote
py -3 -B portal_pipeline/questions_sort.py resolve --label "Describe your preferred project" --answer "Synthetic project answer"
```

Successful appends trigger background promotion 30 seconds after the last append. Change `SORT_DEBOUNCE_SECONDS` in `assist_jobs.py` for local tuning. One background sort runs per data directory in each helper process; dumps due during a run coalesce into one follow-up. Drafts and all sorter commands share a process-local limit of three jobs. Dump responses never wait for sorting. Pending timers are not durable; after a helper restart, use `promote` to process any remaining captures.

Every successful sorter command atomically replaces `conflicts.json` with an author, schema version, and `conflicts` list. Each conflict includes label variants, distinct answers, companies, stored scopes, and resolution status. An empty list clears old conflicts. Background errors append only UTC time and exception type to `questions_sort_errors.log`; no answer values or errors reach the dump response.

Put optional `--data <assist-data-directory>` before the command. `AGREE` requires two distinct named companies and no captured or stored contradiction. `SINGLE` saves only into each observed company/host scope. Unnamed hosts cannot establish agreement between companies. Conservative question aliases merge presentation variants; changed meanings remain separate. Sources prefilled, filled, typed, and corrected count equally, once per company. Answer normalization preserves punctuation, ignores case and whitespace, and follows existing Yes/No option equivalents.

`promote` uses the same reviewed-answer writer as Save this answer, with sources `questions-promoted` and `questions-single`. Existing conflicting answers are never replaced automatically. Only unresolved `CONFLICT` groups need a chat choice. `resolve` explicitly sets the shared answer and preserves differing company answers in their scopes. Resolved conflicts remain visible with `resolved: true`; new sightings or changed shared answers reopen them. Multiple different answers within one company, or an existing conflicting company value, require manual company review.

`SENSITIVE (captured, never auto-filled)` lists captured answers and companies separately. Neither promote nor resolve writes these groups into answer stores. There is no sensitive override flag. Server flags use the full question and options before truncation; Fill and existing answer routes retain their blockers.

Limits: 80 pairs and 64 KiB per request; label 300 characters, answer 2000, company 150, type 40, and 40 options of 120 characters. Oversized field values within an accepted request are truncated, with `truncated` and `truncated_fields`; oversized requests fail without partial capture. The file stores author, schema_version, UTC ts, company, host, vendor, label, answer, source, type, options, page_id, sensitive, and truncation flags. Truncated identity fields also get a `pair_digest` so different original values are not deduplicated by their shared prefix. Exact company/label/answer duplicates within seven days are skipped. Counts in the dock and response include saved, duplicate, excluded_by_type, and flagged_sensitive; the last count covers newly saved sensitive rows. No values appear in those responses or errors.

`questions_processed.json` holds fingerprints and resolution state, without answers. Repeated promotion skips unchanged groups. Sorting runs outside write locks. Each promotion re-reads captures and checks stores and resolution state under the final write locks; changed snapshots retry outside the locks. A conflicting or sensitive row received during sorting blocks that promotion. It never edits the capture file. Reports include label variants, answers and companies, distinct-company sightings, raw capture counts, first/last UTC timestamps, stored answers, truncation, and resolution flags. All local data, capture/state filenames, conflicts, and sorter error logs are Git-ignored. See [Save page validation](../docs/TRIAL_ERRORS.md#october-30-2026-save-page-questions) for synthetic evidence and limits.
