---
author: Yazad Madan
---

# Lever contract

Status: synthetic preparation only. No Lever Inspect-only export exists in the available checkout and no employer page was opened or filled. Fixture structure is invented and is not an assertion about any real Lever posting.

## Hosts and mode

The Lever adapter has `hosts: []` and is not in a production injection list, so production routing never reaches it. No Lever host permission was added. Only tests clone it onto `lever-fixture.example.invalid`. A real host can be registered only after a structure export establishes the apply host and a reviewed contract supports it.

## Behavior shown by synthetic tests

Fill is limited to text, textarea, email, tel, and url fields the user selected. Checkbox, radio, select, and file fields scan as `manual_only` with no proposal, and their writers return `refused` without touching the page. Uploads are refused. A label held outside the field (a sibling `.application-label` in the question block) replaces an identifier-only label so the person sees the question; the engine's own identity check is unchanged. A visible hCaptcha blocks the engine before any writer. Existing values are preserved unless overwrite is selected. Guarded Next stays off, Submit is never treated as Next, and submit counters stay at zero.

## Fabricated pages

`fixtures/replay/lever/page_1.html` has name and email inputs, a textarea whose label sits outside it, a radio group, a checkbox, a resume input, and a Submit button. `hcaptcha_form.html` has one input and a visible hCaptcha frame.

## Open evidence

Required before any live claim: the apply host, an Inspect-only export, real label markup, whether hCaptcha appears at submission or earlier, upload behavior, and final review markers. The postings API (GET only) may later supply question lists. All of this is UNVERIFIED.
