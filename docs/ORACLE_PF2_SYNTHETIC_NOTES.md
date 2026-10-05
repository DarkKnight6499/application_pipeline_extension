---
author: Yazad Madan
---

# PF2 Oracle synthetic preparation

Branch `feat/pf2-oracle-synthetic` is based on `47bc4a1`. Tests were added first. The initial targeted run had seven errors because `oracle.js` did not yet exist. After implementation, targeted runs exposed a fixture URL that did not contain `hcaptcha`, a scan assertion that counted the shared guard controls, and an email-code row still present in the Oracle scan. Those were corrected. All examples use fabricated values and `example.invalid` test routing.

The adapter remains unrouted and in `answer_sheet_only`. Human gates stop engine writes before the adapter writer. The pure mode transition proves a monotonic downgrade but is not persisted; unknown state fails closed. The engine does not enforce `adapter.mode` globally, so Oracle's own text and upload writers explicitly refuse. The base version did not enforce adapter mode in enabled `PortalProgress.guardedNext`. Coordinator integration now refuses explicit answer_sheet_only mode on entry and immediately before clicking; its global default remains off. See ANSWER_SHEET_NEXT_GUARD.md. This guard does not implement persisted application state. No helper route, record schema, host policy, manifest permission, or production injection list changed.

Final targeted Edge validation: 13 tests passed in 3.907 seconds. JavaScript syntax, Python compilation, and `git diff --check` passed. The three replay cases passed within the targeted suite. No inherited test was edited. No live Oracle export or application was used. Full discovery and integration remain for the coordinator.
