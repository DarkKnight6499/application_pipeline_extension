---
author: Yazad Madan
---

# Oracle Recruiting Cloud contract

Status: synthetic preparation only. No Oracle post-login Inspect-only export exists in the available checkout. No employer page was opened or filled for this work. The probe findings in `docs/STATUS_AND_NEXT_STEPS.md` document an email gate, hCaptcha, and a honeypot. They do not establish a host pattern or a post-gate form structure.

## Hosts and mode

October 5, 2026: the opt-in application mode guard and helper sidecar now provide synthetic restriction persistence independently of the pure nextMode helper. See ../APPLICATION_MODE_SECURITY_NOTES.md and ../ORACLE_MODE_PERSISTENCE_PROPOSAL.md. A helper fill overlay never enables this adapter. Oracle keeps its fixed answer-sheet capability and no real hosts.

The Oracle adapter has `hosts: []` and is not in a production injection list. Production routing does not reach it. Its fixed mode is `answer_sheet_only`; its text and upload writers return `refused`. Only tests clone it onto `oracle-fixture.example.invalid`. No Oracle host permission was added. A real host can be registered only after a structure export establishes the exact apply host and a reviewed contract supports it.

## Fabricated page sequence

The fixtures under `portal_pipeline/fixtures/replay/oracle/` are invented. `page_1.html` has three ordinary inputs, a visible honeypot, and a Next button. `email_gate.html` has a visible email verification heading, a code field, and one ordinary input. `hcaptcha_form.html` has one ordinary input and a visible hCaptcha frame. The labels, control counts, order, selectors, and navigation are not assertions about any real Oracle tenant. The fixture manifest records expected field and gate counts.

## Boundaries shown by synthetic tests

The adapter composes the generic visible CAPTCHA gate. It identifies an email-code gate only when a visible email verification heading and a visible code input coexist. Both gates are checked by the engine before its adapter writer. A visible honeypot and the code field are filtered from Oracle scan output. Shared engine protection also blocks a honeypot writer. The adapter never interacts with a CAPTCHA or code input and never clicks Next or Submit. P7 guarded Next stays off by default.

`nextMode(previousMode, gate)` remains a pure, nonpersistent design proof: a CAPTCHA changes `fill` to `answer_sheet_only`, and that mode does not revert when the challenge disappears. An unknown previous mode fails closed to `answer_sheet_only`. It does not itself enforce application lifetime persistence. The separate application_mode backend and extension guard now supply that restriction overlay, with mocked browser lifecycle evidence and the limits in `../APPLICATION_MODE_SECURITY_NOTES.md`.

Oracle's own text and upload writers refuse. The engine also refuses adapter answer-sheet mode for adapters requiring application mode. Shared guarded Next checks answer-sheet mode and the opt-in persistence guard; it remains off by default. These guards do not authorize Oracle production injection or establish a verified Next contract.

## Open evidence

The current extension rejects Oracle inspection because Oracle has no verified host policy. First establish the exact apply host and review an Inspect-only access path without bypassing permissions. Then Yazad can capture each page of one application after handling login and email verification himself, following `../EXPORT_CAPTURE_CHECKLIST.md`. Exports must establish the exact host, gate placement, page sequence, controls, repeated rows, upload behavior, and final review markers. If hCaptcha appears inside the application, the application remains in `answer_sheet_only`. Remote persistence, upload completion, and live compatibility remain unverified.

## JPMC contact information page (October 25, 2026 live Inspect export)

Source: one Inspect-only export of `jpmc.fa.oraclecloud.com` (signed in, nothing entered). Raw file stays in the ignored exports folder. Native fill is **UNVERIFIED**.

| Item | Observed structure |
|---|---|
| Text fields | Plain inputs with generated numeric suffixes in ids, for example `firstName-24`, `lastName-26`, `addressLine1-31`. The `name` attribute is stable (`firstName`, `middleNames`, `lastName`, `addressLine1`), so match on name, never on id. |
| Email | `email`, disabled (prefilled from the account). |
| Comboboxes | Country, City, County, State, Postal Code, Preferred Location, and the phone country code are `input role="combobox"` with `aria-controls="<id>-listbox"`. Country, City, County, State, Postal Code and the phone code report `aria-haspopup="grid"`, not `listbox`, so the existing aria-listbox adapter refuses them. Preferred Location reports `listbox`. Options are not captured. |
| Labels | Required comboboxes carry the label text with embedded whitespace and a trailing `*`. |
| Phone | A separate tel input with `maxlength` 30 beside the code combobox. |
| Resume | One visible `input type="file"`, `accept=".doc,.docx,.odt,.pdf,.txt,.rtf,.htm,.html"`, not multiple, labelled "Import your profile from resume". |
| Coverage gaps | One visible iframe and four open shadow hosts are not inspected. |

Next capture needed: one combobox open (for example State) to see whether options render as `role="option"` in a grid or a listbox.

## JPMC application flow and State popup, live (October 25, 2026)

Source: a live read-only walk of `jpmc.fa.oraclecloud.com`, job 210778739 (Risk Reporting - Associate), with the user's account. Fill stays **UNVERIFIED**.

| Item | Observed |
|---|---|
| Entry | Job page has an `Apply Now` button. It leads to `.../job/<id>/apply/email`: an email input (`name=primary-email`), a `honey-pot` text input (never fill), a legal checkbox (`name=legal-disclaimer-checkbox`, "I agree with the terms and conditions"), Cancel, Next, and a privacy `Accept`/`Decline` banner. |
| Verification | After Next the page shows "Confirm Your Identity" with six single-digit inputs (`pin-code-1` to `pin-code-6`); the code arrives by email. |
| Contact page | `.../apply/section/1`. 17 inspectable fields: resume import file input, First/Middle/Last name, Email, phone code combobox plus tel input, Country, Address Lines 1 to 3, City, Tax District, County, State, Postal Code, Preferred Location. Inspection still reports `iframe_uninspected` and `open_shadow_uninspected`. |
| Comboboxes | `input role="combobox"` with `aria-haspopup="grid"` (Preferred Location uses `listbox`), names `country`, `city`, `region1`, `region2`, `postalCode`, `phoneNumber`. Values may be prefilled from the account (State showed `NJ`). |
| State popup | Opens on click. `div role="grid"` named by `aria-controls` (`region2-37-listbox`, generated per page), `aria-label="State"`, `aria-busy`. 60 `div role="row"`, each with one `div role="gridcell" id="<popup>-listitem-N" aria-selected`. The label is the cell text (`NJ`). The selected cell has `aria-selected="true"`. |
| Closing | Escape closes the popup and leaves the value unchanged. |
