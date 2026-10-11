---
author: Yazad Madan
---

# Taleo contract

Status: synthetic preparation only. No Taleo Inspect-only export exists in the available checkout and no employer page was opened or filled. Fixture structure is invented.

## Hosts and mode

The adapter has `hosts: []` and is not in a production injection list, so production routing never reaches it. No Taleo host permission was added. Only tests clone it onto `taleo-fixture.example.invalid`.

## Behavior shown by synthetic tests

A visible password field is reported as a `sign_in` human gate, so every write is refused until the person has signed in or created an account. Passwords are never written. `pageKind()` returns `sign_in`, `review`, `form`, or `unknown`; a heading naming review, summary, or confirm marks the final review page and `nextStep()` reports `final_review`. Legacy Next and Submit controls are native submit inputs, which the shared progression denylist never offers as Next. Selected fields fill through the shared engine, existing values are preserved, and submit counters stay at zero.

## Open evidence

Required before any live claim: the career-section host, an Inspect-only export of each page, real legacy markup, account creation flow, upload behavior, and final review markers. All of this is UNVERIFIED.
