---
author: Yazad Madan
status: Synthetic preparation
---

# PF1 Workday phase notes

The dedicated Workday adapter preserves the previous inline registration and `myworkdayjobs.com` host pattern. It delegates to the shared generic engine. No additional host, page selector, permission, fill strategy, or navigation action was added. The synthetic contract is in `contracts/WORKDAY_CONTRACT.md`.

Fourteen new browser tests cover routing, read-only scan and answer-sheet export, selected fill, overwrite preservation, human gating, final-review reporting, zero submission actions, required-field reveal, reversed Yes or No options, Add and resume-autofill controls, split date binding, and setter reversion. The initial run stopped because the new adapter file did not exist. After extraction, the shared implementation passed all cases. This proves synthetic behavior only.

Existing tests were not edited except the `ENGINE_SCRIPTS` injection list in `portal_pipeline/tests/browser_test_support.py`. Popup and review script lists now load `workday.js` after `generic.js`. The manifest remains unchanged for coordinator integration.

Outstanding live work: obtain Inspect-only exports after human login, confirm page and control shapes, and check remote readback up to review without submission. The en-dash date import question remains for a human-operated throwaway account.
