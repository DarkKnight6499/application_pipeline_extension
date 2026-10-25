---
author: Yazad Madan
status: Synthetic adapter evidence; October 18 live inspection gaps recorded separately
---

# Workday contract

## Portal and hosts

The adapter retains the existing `myworkdayjobs.com` host pattern. `myworkdaysite.com` remains excluded because no structure export establishes its apply host or controls. No real tenant was inspected after login for this phase.

## Evidence

The hand-built fixtures under `portal_pipeline/fixtures/replay/workday/` and the fabricated cases in `test_public_workday.py` remain the automated adapter evidence. [October 18 live observations](../LIVE_WORKDAY_HANDOFF.md) now establish a real tenant's visible controls and native UI behavior, with concrete scanner omissions. They do not validate extension-selected filling, popup ownership, repeated-row attribution, or upload completion. The existing `data-automation-id` row grouping still comes from the shared engine and synthetic tests.

## Page sequence

| Page key | Heading | Controls | Required | Upload | Navigation | Final review |
|---|---|---:|---:|---|---|---|
| `workday/page_1.html` | Synthetic Workday application | 5 | 3 | None | Next | No |

Later pages, actual sequence, and remote persistence are **UNVERIFIED**. Other test cases construct individual control shapes without claiming a real page sequence.

## Control families

| Family | Synthetic behavior | Live status |
|---|---|---|
| Native text and select | Shared scanner and selected-field writer preserve unselected values and refuse overwrite by default. | UNVERIFIED |
| Yes or No select | Shared option matcher selects the requested label even when No precedes Yes. | UNVERIFIED |
| Required field revealed after initial scan | Shared bounded sweep rescans and reports the newly visible empty field. | UNVERIFIED |
| Existing employment row | Shared row identity requires explicit profile-record binding. The adapter never creates a row. | UNVERIFIED |
| Split month and year | Shared `datePartFact` derives components from a sourced `YYYY-MM` fact after manual row binding. Other date widgets remain manual. | UNVERIFIED |
| ARIA listbox | Existing bounded `aria-listbox.js` contract applies only when its own checks pass. | UNVERIFIED |
| File upload | Shared checksum and selected-upload rules apply. No Workday-specific upload shape is established. | UNVERIFIED |

## Human gates

Visible hCaptcha, reCAPTCHA, and Turnstile use the shared page gate. Password controls are protected per control. MFA and email-code progression remain manual. Their actual Workday placement is **UNVERIFIED**.

## Repeated sections

The shared engine recognizes existing `data-automation-id` values beginning with `workExperience` or `education`. Those selectors and row containers are **UNVERIFIED** against a real export. Add-row controls are never clicked. Existing rows require explicit binding.

## Mode

`fill` for selected supported controls on the existing host. Answer-sheet export remains read only. No live compatibility claim follows from synthetic tests.

## Open questions

- Collect Inspect-only structure exports for each page after the human completes login. Confirm all selectors, required markers, listbox ownership, row grouping, upload shape, navigation labels, and final review.
- Check whether actual Workday pages revert native setter writes. The synthetic reversion case reports failure. Any live reversion needs human review before changing fill strategy.
- Check en-dash date import only through a human-operated throwaway account. No master date change belongs to this phase.

## Date range parsing (October 11, 2026)

The profile builder now splits an employment date range on an en or em dash with or without spaces, a spaced hyphen, or "to", and reads Sept and abbreviated months with periods. An unspaced hyphen is not a separator, so ISO dates are never split. An unreadable side such as Present stays pending while a readable side keeps its own fact, a reversed range clears both, and nothing is guessed. This covers only our own parsing of the master resume. Whether the Workday resume import drops dates joined by an en dash is still UNVERIFIED and needs the throwaway-account check above. Tests: `test_public_date_ranges.py`.

## Button menus and search pickers (October 25, 2026 live Inspect exports)

Source: four Inspect-only exports of the Citi My Information page (tenant `citi.wd5.myworkdayjobs.com`), with no answers entered and no menu option selected. Raw files stay in the ignored exports folder. Native fill through the extension remains **UNVERIFIED**.

| Control | Observed structure |
|---|---|
| Country, State, Phone Device Type | `button` with `aria-haspopup="listbox"`, ids `country--country`, `address--countryRegion`, `phoneNumber--phoneType`, label ends with `*`. Closed: no `aria-expanded`, no `aria-controls`. Open: `aria-expanded="true"` and `aria-controls` set. |
| Open menu popup (Country, State) | One `ul role="listbox"` with a generated id (`t4hix`, `t4hiz`), no automation id, container or label, and 250 and 61 `role="option"` items. Generated ids change between captures, so a selector must come from the button's `aria-controls` and never from a fixed id. |
| Page chrome | `utilityMenuButton` buttons (`languageSelectorButton`, `settingsSelectorButton`, `accountSettingsButton`) are not application controls and are excluded from the unsupported menu count. |
| How Did You Hear About Us, Country Phone Code | Export as text inputs (`source--source`, `phoneNumber--countryPhoneCode`) with no popup attributes. Each sits beside a `ul role="listbox"` with `data-automation-id="selectedItemList"` inside `multiselectInputContainer`. Search dialog contents are not captured. |

Still **UNVERIFIED**: that `aria-controls` names the popup (the export records only that it is set; later exports record its value), how an option is committed, and whether unselected options render off screen. The October 18 notes record that off-screen options could not be clicked and that Country once changed unexpectedly, so any adapter must scroll an exact option into view, select only one exact label match, and read the button text back.

## My Experience and Application Questions (October 25, 2026 live Inspect exports)

Source: Inspect-only exports of the Citi My Experience and Application Questions pages, nothing entered. Native fill stays **UNVERIFIED**.

| Item | Observed structure |
|---|---|
| Repeated rows | Control ids carry a row prefix, `workExperience-N--` and `education-N--` (N is a generated number such as 78 or 83), with no container automation id the scanner could use. Rows are now grouped by this prefix. |
| Date parts | `input role="spinbutton"`, ids `<row>--startDate-dateSectionMonth-input`, `...-dateSectionYear-input`, `endDate`, and for education only `firstYearAttended` and `lastYearAttended` (year only). Every label is just "Month" or "Year", so the date part comes from the id. |
| Employment row | `jobTitle`, `companyName`, `location`, `currentlyWorkHere` checkbox, `roleDescription` textarea. |
| Education row | `school` and `fieldOfStudy` text inputs backed by search pickers, `gradeAverage` input, and a `degree` button menu (`education-N--degree`, `aria-haspopup="listbox"`, 23 options once open, popup reachable through `aria-controls`). |
| Resume/CV | A "Drop files here / Select files" zone is visible, but no file input or upload control appears in the export. **UNVERIFIED** and not yet captured. |
| Application Questions | Six `button` menus with ids `primaryQuestionnaire--<32 hex>`, all labelled "Select One Required", so question text is not captured. The 32 hex ids trip the export validator, so these files stay private. |
