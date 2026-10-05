# Live Greenhouse Test Runbook

Author: Yazad Madan.

Updated October 5, 2026 for validated version 0.11.0. Use the same selected-field and upload evidence checks for a selected Workday application. Oracle stays unrouted until its exact hostname and inspection contract are reviewed.

Run on Windows with Microsoft Edge. Never let the tool click Submit; you click Submit yourself. All navigation, login, MFA, CAPTCHA, and signatures are manual.

## 1. Start the helper

From D:\Code\application_pipeline\worktrees\live_prep:

```powershell
.\portal_pipeline\start.ps1 -Source D:\Code\Resume
```

Or directly:

```powershell
py -B portal_pipeline\server.py --source D:\Code\Resume --port 8766
```

Open http://127.0.0.1:8766 in Edge. Use this exact loopback address.

## 2. Load the unpacked extension

1. Open `edge://extensions` in Edge.
2. Enable Developer mode (toggle, top right).
3. Select Load unpacked.
4. Browse to D:\Code\application_pipeline\worktrees\live_prep\portal_pipeline\extension.
5. Extension loads as "Resume Portal Prototype". Confirm version 0.11.0. Reload an existing installation after updating this checkout.

## 3. Inspect the page without pairing (optional first look)

1. Open the Greenhouse application page in Edge, logged in or not.
2. Click the extension icon (Resume Portal Prototype).
3. Popup appears. Select Inspect page only.
4. Extension-owned side panel opens. Lists structural controls, labels, and types.
5. Select Export field structure if you want a JSON report of the form layout.
6. No candidate data is loaded. No pairing or import required.
7. Navigate manually on the employer page and click Rescan for the next page.

## 4. Pair the extension (to enable fill and resume upload)

1. Back at http://127.0.0.1:8766, copy the pairing token from the dashboard (green box, top right).
2. Click the extension icon again.
3. Paste the helper URL: http://127.0.0.1:8766
4. Paste the pairing token.
5. Select Pair.
6. Status changes to "Paired". If it fails, restart the helper (Ctrl+C in PowerShell, then re-run the start command).

## 5. Import an application

1. Prepare the application through the existing Resume workflow. Confirm JD requirements review, audit completion, and `_inputs` archival.
2. Back at http://127.0.0.1:8766, select Audited application folder.
3. Browse to D:\Code\Resume\Applications\<ApplicationID_Company_Role>.
4. The folder must contain: `.application_id`, `Yazad_Madan.docx`, one `JD_*.docx`, `_inputs/resume_content.json`, and one archived `Keywords_*.json`.
5. If the tracker link goes to a job board and redirects elsewhere, paste the exact Greenhouse posting URL in the override field.
6. Select Import.
7. The importer runs `audit_application.py` in place and shows the report. Watch for errors.
8. Download the copied resume and inspect it in Word: page count, wrapping, widow lines.
9. Confirm visual review complete before enabling attachment.

## 6. Open a real Greenhouse application page and scan

1. In Edge, open the Greenhouse application page and sign in yourself (handle MFA/CAPTCHA).
2. Click the extension icon.
3. Select Scan current page (not "Inspect page only" this time).
4. Confirm the employer name and role match your selected posting.
5. Extension-owned side panel opens with proposed answers and sources.

## 7. Select fields to fill

1. Review the proposals in the side panel.
2. Choose individual fields or sections to fill.
3. Edit answer text directly in the panel if needed.
4. For each field, check or uncheck Replace existing to preserve or overwrite.
5. For employment or education rows, choose the employer/role or school from the Profile record dropdown.
6. Select Export field structure anytime for a JSON report (useful if something looks wrong).

## 8. Fill selected fields

1. Select Fill selected fields.
2. Panel disables editing while fill is in progress.
3. Wait for completion message.
4. Review each filled field on the page by eye.
5. Check that existing values were preserved (unless you enabled Replace existing).

## 9. Upload resume (if present on this page)

1. Look for a resume file input field labeled "Resume" or similar.
2. Select that field in the panel.
3. Check Replace existing if the field already has a file.
4. Select Fill selected fields.
5. The tool reads the audited imported resume, verifies its checksum, and assigns the selected file input. This alone does not prove employer upload completion.
6. Check the filename and the employer's completion indicator. Record uploading, processing, and errors as unverified or failed.
7. Navigate manually to a later page and back. Check that the attachment remains. Check its filename or preview again at final review. Record these observations privately without candidate answers or document contents.

## 10. Navigate and rescan

1. Manually navigate to the next page in Greenhouse.
2. In the extension panel, select Rescan (or close the panel and open the extension again).
3. The panel loads the new page's fields.
4. Repeat steps 7-9 for the next page.

## 11. What to check by eye

1. Each filled text field shows the correct value on the page.
2. Dropdown selections show the expected option text.
3. Existing values remain unless you enabled Replace existing.
4. Resume filename appears next to the upload field if supported.
5. No fields were changed that you did not select.
6. No validation errors appear on the page.

## 12. Stop rules

1. Never click Submit or any button labeled Submit, Continue, or Next. You handle final submission.
2. If you see a CAPTCHA or login prompt, handle it manually.
3. If you see MFA, complete it yourself.
4. If a field shows unexpected values after fill, stop and export the field structure for debugging.
5. If an unselected field changes during fill, the tool stops and reports the change. Do not retry; review the export and decide next steps.

## 13. Export field structure if something looks wrong

1. Select Export field structure in the side panel anytime.
2. Browser downloads a JSON file (e.g., `01-contact.json`).
3. Save to D:\Code\application_pipeline\worktrees\live_prep\portal_pipeline\data\exports\greenhouse\, or exports\workday\ for Workday. These local folders are Git-ignored.
4. Include the filename and the observation in your notes.

## 14. After you submit

1. After you submit yourself, keep the existing audited Application ID unchanged. Record an employer confirmation number separately as Employer Reference ID.
2. Return to http://127.0.0.1:8766.
3. In the extension's Application record, enter any employer reference and choose I submitted this myself. The extension prints the tracker command and does not update the tracker.
4. Run that command through the existing Resume workflow only after confirming submission. It uses --id for Application ID and --employer-ref for the employer reference when supplied.

## Unverified items

- Sponsorship toggle and the extension's printed tracker command are implemented and synthetically tested. Employer retention of the reviewed fields remains unverified.
- Remote upload completion confirmation from Greenhouse (UNVERIFIED; checksum verified locally only).
- History row grouping on real Greenhouse forms (UNVERIFIED; tested on synthetic fixture only).
- Editable dropdown manual reason and unsupported control handling (UNVERIFIED on live Greenhouse).
