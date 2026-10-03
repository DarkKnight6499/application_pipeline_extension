# Resume to portal prototype

This project adds a local helper and a Chrome or Edge extension to the existing resume workflow. Development now lives in the dedicated `application_pipeline_extension` repository. The original prototype was developed in the isolated `D:\Code\Resume_portal_pipeline` worktree on `feat/portal-pipeline`. The Resume checkout remains usable independently.

The working path is: prepare an application through the current workflow, import its audited resume, review its layout in Word, scan the portal, select fields and answers, fill those fields, and finish the application manually. A separate sandbox builder and a synthetic Workday form support development without opening an employer account.

## Start the helper

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

After updating the prototype, reload the unpacked extension in its extensions page and refresh the application tab. Version `0.3.1` adds **Inspect page only**, which does not require helper pairing or an imported application. Version `0.3.0` added explicit history row choices, split month/year fields, and prevention of overlapping fills and rescans.

The extension requests page access on user action using `activeTab`. Its persistent host permission covers only the local helper. The current popup restricts scanning to Workday and the paired local fixture, keeping development focused on the first portal. Real Workday compatibility is still unverified. The filling panel checks the posting origin and asks you to confirm the exact application.

For the first walkthrough, open the Workday application page and choose **Inspect page only** in the popup. The extension-owned panel lists control labels, types, sections, and manual reasons. It loads no candidate profile, offers no answer selection or fill action, and rejects scan and fill commands from that inspection panel. Export a report, navigate manually, and use **Rescan this page** for the next report. A posting or protected-only login/review page can legitimately show no inspectable fields. Pair and import an audited application later when ready to fill.

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

Hidden uploads, cross-origin frames, adding or removing history entries, other portal-specific date controls, and automatic navigation are not implemented. History row discovery is validated only against the explicit synthetic sections; real employer grouping still needs inspection and an adapter. A failed dropdown attempt may leave its listbox open for manual review.

One fill runs at a time per page. The review panel disables editing, row changes, Close, and Rescan until the fill result is ready. Structure export remains available because it does not replace the active scan. Wait for results before manually navigating on the employer page.

A fill reports a verified DOM value after a short settling period. It does not guarantee that the employer saved the value on its server. A file input result does not prove the upload completed remotely. If a portal changes an unselected field, the engine reports the change and stops further writes. It does not silently roll the form back.

No real employer application has been validated yet. Live validation should start with one Workday application through its final review page, with the user present and submission remaining manual.

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
