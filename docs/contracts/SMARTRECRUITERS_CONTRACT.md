---
author: Yazad Madan
---

# SmartRecruiters contract

Status: synthetic preparation only (PF13). No SmartRecruiters Inspect-only export exists in the available checkout and no employer page was opened or filled. Page structure is UNVERIFIED and the fixtures are invented.

## Hosts and mode

The adapter has `hosts: []` and is not in a production injection list, so production routing never reaches it. Its fixed mode is `answer_sheet_only`, it requires application mode, and its text and upload writers return `refused`. No host permission was added. Only tests clone it onto `smartrecruiters-fixture.example.invalid`. A real host can be registered only after a structure export and a reviewed contract. Postings API (GET only) may later supply question lists.

## Behavior shown by synthetic tests

The scan is read only and drops a visible honeypot. The answer sheet is built without writing to the page. Fill and upload refuse, existing values are preserved, and a visible CAPTCHA blocks the engine before any writer. Guarded Next stays off, Submit is never treated as Next, and submit counters stay at zero.

## Open evidence

Required before any live claim: the apply host, an Inspect-only export of one application, real control markup, CAPTCHA behavior, upload behavior, and final review markers. All of this is UNVERIFIED.
