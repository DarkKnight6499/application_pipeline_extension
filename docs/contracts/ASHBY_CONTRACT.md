---
author: Yazad Madan
---

# Ashby contract

Status: synthetic preparation only. No Ashby Inspect-only export exists in the available checkout and no employer page was opened or filled. Selectors, labels, and page structure in the fixtures are invented and are not assertions about any real Ashby board.

## Hosts and mode

The Ashby adapter has `hosts: []` and is not in a production injection list, so production routing never reaches it. Its fixed mode is `answer_sheet_only` and it requires application mode. Its text and upload writers return `refused`. Only tests clone it onto `ashby-fixture.example.invalid`. No Ashby host permission was added. A real host can be registered only after a structure export establishes the apply host and a reviewed contract supports it.

## Fabricated pages

`fixtures/replay/ashby/page_1.html` has a name, an email, a resume file input, a length-limited textarea, a visible honeypot, and a Submit Application button. `hcaptcha_form.html` has one input and a visible hCaptcha frame. The manifest records the expected gate per page.

## Boundaries shown by synthetic tests

The scan is read-only and drops a visible honeypot. The answer sheet is built without writing to the page. Fill and upload refuse, an existing value is preserved, and a visible CAPTCHA blocks the engine before any writer. Guarded Next stays off by default, and the Submit Application control is never treated as Next. Submit click and event counters stay at zero.

## Open evidence

Ashby may reject automated submissions and deduplicates by email per company, so real use stays answer sheet only with no email aliasing. Required before any live claim: the exact apply host, an Inspect-only export of one application, the real CAPTCHA behavior, field naming for system fields and custom questions, upload behavior, and final review markers. Public posting API reads are a possible later source of question lists. All of this is UNVERIFIED.
