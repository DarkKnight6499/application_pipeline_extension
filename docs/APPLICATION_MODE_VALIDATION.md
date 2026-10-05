---
author: Yazad Madan
date: 2026-10-05
status: Synthetic implementation, final suite evidence recorded in STATUS_AND_NEXT_STEPS.md
---

# Application restriction validation

Version 0.10.0 is based on main 7310dda. All development paths are under D:\Code\application_pipeline. Oracle retains hosts: [], fixed answer_sheet_only capability, and no production injection. Manifest permissions and host permissions are unchanged.

## Changes

An audited Application ID owns a separate restriction sidecar. The authenticated helper route accepts only an answer_sheet_only CAPTCHA downgrade and never offers reset or fill enablement. A process-local lock and atomic replacement protect sidecar writes. Application record and sponsorship updates use separate storage.

The extension broker journals a restriction before helper requests, validates current audited identity before and after reads, and intersects the response with the latest immutable journal. The opt-in application guard checks location, binding, mode, and human gates after awaits. Review loads mode before offering writes. Engine checks occur before a batch, each selected field, and native assignment after asynchronous work. Next checks repeat immediately before the existing guarded click. Custom dropdowns remain manual for adapters requiring this guard.

If a later field is restricted, earlier fill results remain visible and later fields are refused. A late portal length-limit change is checked immediately before assigning text. These controls do not undo completed writes or remote side effects.

## Reproduction and tests

Eight new backend cases cover identity and strict schema, two sessions sharing one application, another application, authenticated routes, helper restart, corrupt storage, injected writer failure, concurrent record updates, and redirected path containment. The containment test uses deterministic resolution redirection and an outside sentinel, so it does not add another Windows symlink skip.

Twenty new browser cases run the actual broker, application guard, engine, bridge, progression, and panel code on fabricated example.invalid pages. Chrome storage, runtime, and helper responses are mocked. Cases cover valid fill, missing guard or identity, stale reads, changed sessions and URLs, per-application isolation, helper outage, simulated reload and helper port change, unreadable storage, failed journal writes, malformed responses, CAPTCHA after awaits, checksum-time restrictions, partial results, late Next refusal, inspection refusal, and read-only sheet review. Shared teardown asserts untouched fields, empty signature, unchecked certification, and zero submission clicks and events.

The first integrated browser run exposed inspection-message precedence, thrown batch errors, and lost partial results before coordinator fixes. A later length-limit regression failed with status filled before the final pre-assignment check; it then passed. Newly authored fixture mistakes and one coordinator optional-chain assignment syntax error were corrected without editing inherited assertions. Focused final browser validation passes 20 tests in 7.223 seconds. The initial full checkpoint passed 424 tests with two skips before four additional cases and the length-limit fix. The final FULL run passes 428 tests in 223.978 seconds, with only the two expected Windows symlink skips. Further acceptance results are recorded in STATUS_AND_NEXT_STEPS.md.

## Review and limits

Final acceptance: FULL 428 in 223.978 seconds and PUBLIC 346 in 174.403 seconds, both OK with two expected Windows symlink skips. JavaScript syntax, Python compilation, manifest permission comparison, and diff checks pass. No inherited tests changed. Replay acceptance is recorded in STATUS_AND_NEXT_STEPS.md.

Backend review accepted the separate sidecar and authenticated downgrade route with the process-local locking limits. The coordinator reviewed browser authority, journal ordering, stale response intersections, per-application latches, asynchronous write boundaries, partial reporting, inspection refusal, and unchanged production routing. The browser subagent stopped before completing its tests; the coordinator finished implementation and validation. No completed independent final browser security clearance is claimed.

Mocks prove these logic paths, not actual Oracle MV3 lifecycle behavior or isolated-world access. Existing loaded-extension regressions run unchanged in full acceptance. A live portal, remote upload completion, remote field persistence, cross-process locking, and recovery after both durable stores lose a restriction remain outside this evidence. See APPLICATION_MODE_SECURITY_NOTES.md.

No live employer page was opened, filled, or submitted. Resume source code, profiles, builders, and trackers are outside this phase's edits. Source fingerprint changes were observed during the session, so whole-source immutability is not claimed. Only the authorized private plan handoff is appended by this phase.

## Next evidence

Obtain Workday structure exports and one exact Oracle apply hostname for a reviewed inspection-only access path. Keep Oracle unrouted until that review. PF1/PF2 real compatibility and the 50 approved pending wordings needed for P9 remain outstanding. Current Resume generation remains independent.
