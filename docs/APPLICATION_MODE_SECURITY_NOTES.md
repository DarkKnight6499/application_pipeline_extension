---
author: Yazad Madan
status: Security acceptance notes for synthetic implementation
---

# Application mode security boundary

The persistent mode is a restriction overlay. A helper response of fill means no stored restriction was found, not that a portal has a verified fill contract. The effective permission is the intersection of the adapter's capability, the helper restriction, the extension journal, and the existing field protections. Oracle stays unrouted and its adapter stays answer_sheet_only.

## Extension authority

Chrome documents that scripting.executeScript uses ISOLATED by default and that content-script variables are not exposed to the host page. The production injection must remain in that world. Tests that inject scripts directly into a fabricated page prove guard logic; they do not alone prove Chrome world isolation. See the ScriptInjection.world property in the [Chrome scripting API](https://developer.chrome.com/docs/extensions/reference/api/scripting) and [Work in isolated worlds](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts#work_in_isolated_worlds).

Chrome supplies sender identity, frame, tab, and URL information through MessageSender. The mode broker must require the same extension and a top-level content-script sender. Page-bridge configuration must come from the exact extension review page for the target tab, without accepting a page-supplied mode or permission. See [runtime MessageSender](https://developer.chrome.com/docs/extensions/reference/api/runtime#type-MessageSender).

## Durable restrictions

The helper writes a separate contained sidecar keyed to a positive audited Application ID. Ordinary portal-record and sponsorship updates cannot erase this sidecar. The route accepts a CAPTCHA downgrade only, with no reset or fill-enabling operation. Malformed or inaccessible state blocks writes.

The browser records an immutable restriction flag for each audited Application ID before attempting the helper downgrade. A failed helper request must not lose the restriction on a page reload, extension worker restart, helper restart, or helper port change. This project uses one Resume workflow; an application-ID-only browser key conservatively restricts a same-ID application on another helper rather than risking restoration after a port change. Multiple independent workflows would need a reviewed stable scope identifier.

A read must intersect with the latest durable restriction after awaiting helper responses. Identity and page checks must also repeat after awaits. A stale response or new binding must never restore a previously restricted application. An application change may invalidate pending writes; it must not copy the first application's restriction to a different ID.

The helper lock is process-local. Cross-process serialization, malicious filesystem replacement, hardlinks, and operator deletion of stored restrictions are not covered. If both browser storage and helper persistence fail, current processes still refuse writes; after all process memory is lost, a restriction that reached neither durable store cannot be recovered. No durable guarantee is claimed for that combined failure.

## Write boundaries

Enforce mode before a fill batch, before each selected field, after asynchronous attachment or dropdown work, and immediately before Next. Detecting a CAPTCHA must latch locally before awaiting persistence. Observing a CAPTCHA after an awaited mode response also requires the latch, even if the page subsequently removes the challenge.

These checks stop further writes. They do not roll back an already completed field or portal side effect. Remote persistence and a globally atomic transaction across tabs are not established by synthetic guard tests. Login, email codes, CAPTCHA handling, signatures, attestations, and Submit remain human actions.

## Required evidence

Keep new regressions independent of inherited assertions. Cover missing identity, malformed helper responses, helper and journal failures, restart, changed helper port, stale session responses, URL changes, two sessions for one application, isolation of another application, and gates appearing during asynchronous operations. Observe actual field, Next, and submit-event counters. A passing synthetic suite does not authorize a new real host or establish live compatibility.

The new browser suite loads the production broker and guards into fabricated example.invalid pages with mocked Chrome APIs and helper responses. Reload and port-change tests simulate those lifecycle changes; they are not a real Oracle MV3 lifecycle trial. Backend tests use fabricated audited identities and temporary storage. No inherited test assertions changed in this phase.
