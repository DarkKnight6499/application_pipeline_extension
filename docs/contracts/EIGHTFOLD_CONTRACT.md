---
author: Yazad Madan
---

# Eightfold contract

Status: synthetic preparation only. No Eightfold Inspect-only export exists in the available checkout and no employer page was opened or filled. The questions endpoint body was never read. Fixture structure is invented.

## Hosts and mode

The Eightfold adapter has `hosts: []` and is not in a production injection list, so production routing never reaches it. No Eightfold host permission was added. Only tests clone it onto `eightfold-fixture.example.invalid`. A real host can be registered only after a structure export establishes the apply host and a reviewed contract supports it. HSBC hands off to SuccessFactors, which this adapter does not cover.

## Behavior shown by synthetic tests

Dropdowns reuse the shared select-only listbox adapter with its existing ownership, visibility, and exact-option checks; an unmatched answer fails without guessing. A visible cookie banner (a cookie or consent container holding accept, reject, or manage controls) is reported as a `cookie_banner` human gate, so the engine refuses every write until the person dismisses it. The adapter never clicks the banner. A hidden banner does not block. CAPTCHA gating is inherited from the generic adapter. Existing values are preserved unless overwrite is selected. Guarded Next stays off and submit counters stay at zero.

## Fabricated pages

`fixtures/replay/eightfold/page_1.html` has a text input, a select-only combobox with an owned listbox, and a Next button. `cookie_banner.html` adds a cookie dialog above a simple form.

## Open evidence

The real fifteen custom dropdowns are not reproduced. Required before any live claim: the apply host, an Inspect-only export, the real combobox markup and popup ownership, the banner markup, step navigation, upload behavior, and final review markers. All of this is UNVERIFIED.
