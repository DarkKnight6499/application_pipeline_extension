---
author: Yazad Madan
date: 2026-10-05
---

# Loaded MV3 application mode validation

The new public test `portal_pipeline/tests/test_public_application_mode_mv3.py` loads a temporary copy of the production Manifest V3 extension into an Edge persistent browser context. It exercises actual `chrome.storage.local`, `chrome.scripting.executeScript` in the isolated content-script world, `chrome.runtime.sendMessage`, and the extension service worker. A fabricated HTTP helper exposes only `/api/current` and the audited session's `/fill-mode` route. The target page is served by Playwright at `https://mode-fixture.example.invalid/apply`. No employer site, candidate profile, resume, tracker, or real application is used.

The temporary extension copy adds one test-only host permission and one synthetic adapter for that host. The adapter wraps the generic adapter, requires application mode, and permits fill solely to test the guard. Production manifest permissions, CSP, routing, and Oracle's empty host list remain unchanged. The test copies production `background.js`, `application-mode.js`, `engine.js`, and `progress.js` without editing them in the passing run.

The fabricated helper initially reports an unrestricted audited Application ID 11, then rejects the CAPTCHA downgrade POST. A visible Turnstile-shaped fixture triggers the guard. The real worker writes `application-mode:application:11` to browser storage before the helper rejection. The test then reloads the page, reinjects isolated scripts, and confirms the guard refuses a selected text write and guarded Next. It closes the persistent browser context, reopens the same browser profile, and points pairing storage to a second helper port that still reports unrestricted mode. The reloaded worker intersects that helper response with the stored restriction and again refuses the field and Next. The fixture records zero field input events, Next clicks, Submit clicks, and submit events. Application ID 12 then receives an unrestricted read without inheriting ID 11's restriction. The test does not write a field for ID 12.

This is a real browser context teardown and reopen. It forces a new extension worker instance and proves storage survives that lifecycle. It does not prove a browser initiated idle worker suspension or a live employer portal flow. The helper is a fabricated HTTP implementation, so this test does not independently prove filesystem sidecar persistence. Existing backend tests cover that sidecar boundary.

Coordinator integration caught a missing Path import that was removed after the agent's passing run. Restoring the import and rerunning the exact test resolved the runtime NameError. Syntax-only checks had not caught it. The integrated targeted run passes one test in 15.134 seconds; full acceptance also includes the test.

Run with:

```powershell
$env:PORTAL_TEST_BROWSER='msedge'
py -3 -B -m unittest discover -s portal_pipeline/tests -p test_public_application_mode_mv3.py -v
```

Observed on October 5, 2026: 1 test passed in 9.056 seconds. For a red control, set `PORTAL_MV3_MUTATE_INTERSECTION=1`. The test mutates only its temporary extension copy by removing the durable journal term from the worker's final mode intersection. The same test failed after context reopen with `AssertionError: 'restricted' not found in 'allowed'` at the restored mode check. This red run took 15.001 seconds. Unset the variable for acceptance; it is not a production configuration.
