---
author: Yazad Madan
---

# SuccessFactors contract

Status: synthetic preparation only. No SuccessFactors Inspect-only export exists in the available checkout and no employer page was opened or filled. Fixture structure is invented.

## Hosts and mode

The adapter has `hosts: []` and is not in a production injection list, so production routing never reaches it. No SuccessFactors host permission was added. Only tests clone it onto `successfactors-fixture.example.invalid`. HSBC reaches SuccessFactors from Eightfold; that handoff is not modelled.

## Behavior shown by synthetic tests

Selected text, native select, and select-only listbox fields fill through the shared engine. Existing values are preserved unless overwrite is selected, and unselected fields are untouched. `profilePreview()` lists label and value pairs from a visible section whose heading names a profile, preview, or parsed result, so the person can compare a resume parse against the stored profile. It is read only and omits passwords, hidden, file, checkbox, and radio controls. A password field is never written or listed. Guarded Next stays off and submit counters stay at zero.

## Open evidence

Required before any live claim: the apply host, an Inspect-only export, the real picklist markup (about ten custom picklists are reported), the real parse preview structure, sign-in handling, upload behavior, and final review markers. All of this is UNVERIFIED.
