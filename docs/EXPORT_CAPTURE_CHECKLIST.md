---
author: Yazad Madan
---

# Manual portal structure capture

Use this procedure to collect form structure for a manually visited application page. Inspection mode needs no helper pairing, candidate profile, or application import. It does not enter answers or submit forms.

## Capture each page

1. Open the employer application page yourself in the browser. Handle login, MFA, and CAPTCHA yourself.
2. Open the extension popup and choose **Inspect page only**. Confirm the side panel says inspection only and shows no answer-selection or fill controls.
3. Record employer, role, page name, and page order in a separate human note. Do not put candidate answers, credentials, or personal values in the note.
4. In the side panel, choose **Export field structure**. Rename the downloaded file locally with a sequence and page label, for example `01-contact.json`. Keep exports in a private, ignored local folder. Do not add raw exports to Git.
5. Navigate the employer page manually to its next page. In the side panel choose **Rescan this page**, then export a separate report. Repeat for each page you can reach without entering or submitting answers.
6. If a control is not understood, record its visible label, page, reported type and manual reason. Describe how it behaves only if you observed it yourself. Leave answers blank and do not select options for the purpose of inspection.
7. Stop at any review, signature, attestation, or submit step. Do not submit the application.

If the report has no fields, record that observation. The current page may be a posting, login page, protected-only page, or unsupported form. Continue only after you manually reach another page.

## What the JSON captures

The export uses schema version 1. It records the current hostname and capture time; detected portal family and any portal-level manual reason; current-page coverage counts; number of omitted protected controls; and each visible, unprotected control's label, type, required and disabled state, section, adapter name, record wrapper identity when detected, manual reason, option count, dropdown state, and structure attributes.

Structure attributes include tag, name, automation ID, DOM ID, role, `aria-controls`, and `aria-haspopup`. Option labels and values are not exported. The report omits entered values, proposed answers, protected controls, HTML, cookies, passwords, pairing tokens, and URL query strings. Labels and identifiers can still contain employer-specific or personal information. Review them before sharing. Browser downloads go to the browser's configured download location; the extension does not upload the report.

An export is evidence of controls detected in one snapshot. It does not prove that an answer was filled, retained after navigation, saved by the employer, or that an uploaded file completed remotely.

## Record these observations separately

- Employer host, role, page name, and page order.
- Which page transitions you performed manually and which pages you could not reach without answering or submitting.
- Fields that the report marks unsupported, including visible control behavior and option labels observed manually, if needed.
- Date formats, split month/year widgets, repeated history rows, and whether adding rows requires a manual action.
- Resume upload label and any employer completion indicator you observe yourself.
- Whether values remain after ordinary manual navigation, if you later test this in an authorized application session.
- Final review, signature, attestation, and submission controls. Record their presence without activating them.

Do not infer missing dates or personal facts from defaults. Do not record credentials, CAPTCHA contents, or entered candidate answers in the annotations.

## Coverage limits and portal policy

The current report covers visible controls in the current page's light DOM. It counts visible iframes, detectable open shadow hosts, and unsupported spinbuttons, but does not read those contents. It does not capture future pages until you navigate to them manually. Hidden sections, closed shadow roots, frames, and controls rendered only after interaction may be missed. Inspection does not open dropdowns, trigger typeahead, expand sections, or add repeated rows. Manually observe these structures and annotate them without entering candidate answers.

Popup policy currently permits Workday hosts under `myworkdayjobs.com`, Greenhouse hosts under `greenhouse.io`, Phenom hosts under `careers.marsh.com` and `careers.franklintempleton.com`, and the paired local fixture. Phenom host recognition is enabled by a synthetic-only adapter: its selectors and behavior remain unverified against a real portal. The extension has only a persistent localhost host permission; employer page access is requested through the user-triggered browser action. Oracle is not supported by the current adapter registry or allowlist and will be rejected by the popup before inspection. Treat Oracle as a blocker for contract review and future implementation planning. Do not change browser permissions or bypass this policy as part of capture.

The top-level `portal` value in the export reports only `greenhouse` or `generic`. It does not identify Workday or Phenom as the portal family. A field's `adapter` value describes custom dropdown support for that field, such as `aria-listbox` or `greenhouse-select`; it is not the portal family. Use the hostname and your own visit notes to identify the employer system. Current host support is not proof of compatibility with a live application. The existing handoff records that Workday and Greenhouse have no real employer flow validated through final review; Phenom has synthetic-only fixtures. An export alone cannot establish field semantics, retention, remote persistence, or upload completion.

## Existing implementation references

- `portal_pipeline/extension/popup.html` and `popup.js`: **Inspect page only** action and user-triggered page access.
- `portal_pipeline/extension/host-policy.js` and `adapters/generic.js`: Workday, Greenhouse, and paired local fixture host checks.
- `portal_pipeline/extension/engine.js`, `inspect()`: schema fields, protected-field omission, and coverage limits.
- `portal_pipeline/extension/panel.js`: **Export field structure**, download behavior, and inspection-only panel.
- `portal_pipeline/extension/page-bridge.js`: inspection mode rejects scan and fill commands.
- `portal_pipeline/INSPECTION.md` and `docs/LIVE_TEST_RUNBOOK.md`: current human workflow and existing runbook constraints.
- `portal_pipeline/HANDOFF.md`: live compatibility status and remaining limits.
