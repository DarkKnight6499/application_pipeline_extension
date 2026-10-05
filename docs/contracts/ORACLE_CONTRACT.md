---
author: Yazad Madan
---

# Oracle Recruiting Cloud contract

Status: synthetic preparation only. No Oracle post-login Inspect-only export exists in the available checkout. No employer page was opened or filled for this work. The probe findings in `docs/STATUS_AND_NEXT_STEPS.md` document an email gate, hCaptcha, and a honeypot. They do not establish a host pattern or a post-gate form structure.

## Hosts and mode

October 5, 2026: the opt-in application mode guard and helper sidecar now provide synthetic restriction persistence independently of the pure nextMode helper. See ../APPLICATION_MODE_SECURITY_NOTES.md and ../ORACLE_MODE_PERSISTENCE_PROPOSAL.md. A helper fill overlay never enables this adapter. Oracle keeps its fixed answer-sheet capability and no real hosts.

The Oracle adapter has `hosts: []` and is not in a production injection list. Production routing does not reach it. Its fixed mode is `answer_sheet_only`; its text and upload writers return `refused`. Only tests clone it onto `oracle-fixture.example.invalid`. No Oracle host permission was added. A real host can be registered only after a structure export establishes the exact apply host and a reviewed contract supports it.

## Fabricated page sequence

The fixtures under `portal_pipeline/fixtures/replay/oracle/` are invented. `page_1.html` has three ordinary inputs, a visible honeypot, and a Next button. `email_gate.html` has a visible email verification heading, a code field, and one ordinary input. `hcaptcha_form.html` has one ordinary input and a visible hCaptcha frame. The labels, control counts, order, selectors, and navigation are not assertions about any real Oracle tenant. The fixture manifest records expected field and gate counts.

## Boundaries shown by synthetic tests

The adapter composes the generic visible CAPTCHA gate. It identifies an email-code gate only when a visible email verification heading and a visible code input coexist. Both gates are checked by the engine before its adapter writer. A visible honeypot and the code field are filtered from Oracle scan output. Shared engine protection also blocks a honeypot writer. The adapter never interacts with a CAPTCHA or code input and never clicks Next or Submit. P7 guarded Next stays off by default.

`nextMode(previousMode, gate)` remains a pure, nonpersistent design proof: a CAPTCHA changes `fill` to `answer_sheet_only`, and that mode does not revert when the challenge disappears. An unknown previous mode fails closed to `answer_sheet_only`. It does not itself enforce application lifetime persistence. The separate application_mode backend and extension guard now supply that restriction overlay, with mocked browser lifecycle evidence and the limits in `../APPLICATION_MODE_SECURITY_NOTES.md`.

Oracle's own text and upload writers refuse. The engine also refuses adapter answer-sheet mode for adapters requiring application mode. Shared guarded Next checks answer-sheet mode and the opt-in persistence guard; it remains off by default. These guards do not authorize Oracle production injection or establish a verified Next contract.

## Open evidence

The current extension rejects Oracle inspection because Oracle has no verified host policy. First establish the exact apply host and review an Inspect-only access path without bypassing permissions. Then Yazad can capture each page of one application after handling login and email verification himself, following `../EXPORT_CAPTURE_CHECKLIST.md`. Exports must establish the exact host, gate placement, page sequence, controls, repeated rows, upload behavior, and final review markers. If hCaptcha appears inside the application, the application remains in `answer_sheet_only`. Remote persistence, upload completion, and live compatibility remain unverified.
