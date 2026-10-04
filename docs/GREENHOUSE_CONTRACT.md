---
author: Yazad Madan
observed: 2026-10-03
status: Public structure inspected, synthetic behavior verified, live filling pending
---

# Greenhouse hosted-form contract

The second portal track uses the public [Justworks Financial Analyst application](https://job-boards.greenhouse.io/justworks/jobs/7980174) as a development reference. Its response was fetched directly and parsed for form attributes, labels, and ancestor structure. No account was used, no candidate facts were sent, and no application was created or submitted. This is structural inspection of a public document, not a rendered browser walkthrough or a role recommendation.

## Observed structure and implementation

| Public structure | Implemented behavior |
| --- | --- |
| A `form#application-form` contains the application controls. | Scan only one unique matching form on Greenhouse hosts. Exclude page search, newsletter, and other forms. Missing or duplicate forms yield a manual inspection reason. |
| Native contact inputs expose labels, IDs, maximum lengths, and ARIA required flags. | Reuse sourced, selected native filling and readback. Required stars do not change exact field classification. Unknown questions remain pending. |
| Country, location, and several employer questions are editable `input[role=combobox]` controls with `aria-autocomplete=list`. Closed markup does not establish popup ownership or selected-value behavior. | Keep these controls manual. Do not infer a dropdown contract from server-rendered markup or type a value as though an option had been selected. |
| Companion required inputs have `aria-hidden=true` and `tabindex=-1`. | Exclude ARIA-hidden controls and hidden ancestors. These internal validation inputs are not candidate questions. |
| Upload inputs have IDs `resume` and `cover_letter`, visually hidden styling, and immediate labels saying Attach. Their enclosing `.file-upload[role=group]` names the document using `aria-labelledby=upload-label-...`. | Recognize an upload only when the form, unique input ID, group, unique label, and exact document label agree. A visible resume group can expose its hidden native input for selected checksum-verified attachment. Cover letters are identified separately and are not supplied with the resume. |
| The upload group's ARIA required flag applies to the resume. | Show the inherited required state. Verify the native file input and require manual confirmation of remote upload completion. |
| `#demographic-section.demographic--container` encloses the voluntary survey, including questions whose wording may not contain standard demographic keywords. | Protect every input in that container. Recheck the container before and after filling so a moved field cannot retain an earlier unprotected classification. |
| A submit-type button ends the application form. | Do not enumerate or click the submission control. The fixture counts attempted submission and asserts zero attempts. |

The adapter checks the form's live object identity before and after writing. A field moved outside that form, moved into the survey, or attached to a replaced form requires a new scan. Changed upload labels and duplicate identity attributes invalidate the upload contract.

## Evidence and limits

`portal_pipeline/fixtures/greenhouse.html` reproduces only the relevant structures using synthetic values and no employer endpoint. Five new browser tests cover native selected filling, preserved existing values, hidden resume attachment, untouched cover-letter input, excluded internal and survey fields, rejected editable dropdown filling, ambiguous forms, changed upload labels, and reparented controls. The loaded extension also scans and exports the routed synthetic Greenhouse form without pairing or API calls.

The loaded-extension test uses temporary test-only host permissions because a popup opened as a test tab does not acquire `activeTab`. Production retains only the loopback helper host permission. A real extension-action click remains part of live validation.

The full suite passed 81 tests in 50.944 seconds on October 3, 2026. No remote saving, upload completion, reactive dropdown selection, browser-rendered validation, or final-review persistence has been demonstrated on Justworks. Workday and Greenhouse therefore remain separately unvalidated end-to-end integrations. Do not copy the candidate's resume into the public fixture or repository.

PF4 synthetic completion coverage adds nine new cases. Seven cover Greenhouse routing, read-only scanning, selected-only fill, overwrite-off preservation, CAPTCHA gating, final-review detection, and zero submission events. One verifies a stale react-select field reference fails closed after a synthetic rerender, then succeeds after an explicit rescan. One confirms country and city typeahead stay manual without an observed popup contract. The focused suite passes in Edge. These cases use fabricated values and do not expand the public contract or establish live compatibility.

## Next demonstrated gap

Connect a real browser and inspect one editable country or city dropdown after the user opens it. Record its stable popup ownership, exact option labels, current selection representation, event behavior, and asynchronous validation before enabling automatic choice. Separately observe the real resume upload completion indicator. Keep signatures, attestations, and submission manual.
