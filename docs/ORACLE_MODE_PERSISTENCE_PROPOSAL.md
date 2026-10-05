---
author: Yazad Madan
status: Implemented for synthetic enforcement, real hosts disabled
---

# Oracle application mode persistence proposal

## October 5 implementation

The proposal below is retained as design history. The current implementation uses a separate restriction sidecar at data/application_modes/<application_id>.json rather than adding a fill_mode field to portal records. GET /api/sessions/<id>/fill-mode reads the overlay; POST accepts only a CAPTCHA downgrade. Sessions require a positive audited Application ID. Corrupt or inaccessible state returns answer_sheet_only. Per-application helper locks and atomic replacement protect updates within one helper process; ordinary record or sponsorship writes cannot erase the sidecar.

The extension journals a restriction by Application ID before requesting the helper downgrade. The mode broker checks audited session identity before and after reads and intersects responses with the latest journal. The application guard checks page identity and human gates after awaits. Review hydrates mode before offering writes, and engine and progression boundaries independently refuse restricted writes. The mechanism is opt-in through requiresApplicationMode. Oracle is the only production adapter declaring this flag, and it remains unrouted, outside production injection, and answer_sheet_only.

New browser tests run actual guard and broker code with mocked Chrome storage, runtime, and helper responses. They establish synthetic behavior, not actual Oracle extension isolation, remote persistence, or live compatibility. Existing loaded-extension regressions remain in the full suite. See APPLICATION_MODE_SECURITY_NOTES.md for authority boundaries and persistence limits. The pure nextMode helper remains nonpersistent by itself.

## Original proposal boundary

Oracle preparation is synthetic only. The production adapter has no routed hosts and defaults to answer_sheet_only. Its pure mode transition helper demonstrates a CAPTCHA downgrade using caller-supplied state. It does not persist application state across navigation, extension reloads, helper restarts, or another imported session.

The existing helper stores sessions in session.json and audited application records under data/records/<application_id>.json. server.py record_for rejects sessions without an audited Application ID. portal_record.py does not currently store an enforced portal fill mode. Sponsorship answer mode is a separate property and must remain separate.

## Original proposed enforcement

Before enabling any Oracle host, obtain verified structure exports and implement an application-scoped monotonic mode restriction. Record the restriction against the audited Application ID rather than a tab or session ID. All sessions for that application must observe the same restriction. A new session, browser restart, CAPTCHA removal, or successful human gate completion must not restore fill mode after a mid-form CAPTCHA.

Use a proposed fill_mode field with values fill and answer_sheet_only, plus a bounded reason code. This is a proposed schema extension, not an existing API. Legacy records need an explicit conservative migration policy. Oracle sessions without an audited identity must remain answer_sheet_only.

The extension-owned review page must load the effective mode before offering Fill, upload, or guarded Next. A failed or malformed mode response must leave writes disabled. Scan and answer-sheet export may remain available without interacting with a gate. An engine boundary must also enforce the restriction, so hiding a panel button alone is insufficient.

A detected mid-form CAPTCHA must stop writes immediately and report the downgrade to the helper before another write is possible. Failed persistence must keep the current page blocked. The helper needs serialized read-modify-write updates per application because atomic file replacement alone does not prevent a concurrent stale update from restoring fill mode. Unrelated record updates must preserve the restriction.

Initial email verification remains a human gate. Do not infer that clearing an initial gate authorizes a later CAPTCHA bypass. No code should solve, click, or inspect CAPTCHA frame contents.

## Tests required before enabling fill

1. Two sessions for one fabricated audited application observe the same downgrade.
2. Navigation, panel closure, browser reload, and helper restart preserve the restriction.
3. Removing the CAPTCHA does not restore fill, upload, or guarded Next.
4. Direct page-bridge fill requests are blocked after downgrade even if panel state is stale.
5. Missing identity, malformed responses, and persistence failure all block writes.
6. Concurrent page-record updates cannot erase or reduce the restriction.
7. A different application does not inherit the first application's state.
8. Scan and answer-sheet export remain read-only; passwords, honeypots, signatures, and attestations remain protected.
9. Actual submit click and submit event counters stay zero.

Do not implement this persistence by reusing sponsorship_answer_mode, trusting a page-owned variable, or adding a reset route. This proposal requires coordinator review and meaningful tests before backend or write-boundary changes. It does not establish live compatibility.

## Source references

- portal_pipeline/server.py: Pipeline.read, record_for, and session record routes.
- portal_pipeline/portal_record.py: record schema, load_record, record_page, and atomic replacement.
- portal_pipeline/extension/engine.js: fillSelected and human-gate checks.
- portal_pipeline/extension/page-bridge.js: inspection and fill message boundaries.
- Private phased execution plan: PF2 application-lifetime downgrade requirement.
