---
author: Yazad Madan
status: Synthetic only
---

# Workday contract

## Portal and hosts

The adapter retains the existing `myworkdayjobs.com` host pattern. `myworkdaysite.com` remains excluded because no structure export establishes its apply host or controls. No real tenant was inspected after login for this phase.

## Evidence

The hand-built fixtures under `portal_pipeline/fixtures/replay/workday/` and the fabricated cases in `test_public_workday.py` are the only page evidence. Every Workday-specific selector or control shape below is **UNVERIFIED** against a real application. The existing `data-automation-id` row grouping comes from the shared engine and synthetic tests, not a new live observation.

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
