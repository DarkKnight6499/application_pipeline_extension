---
author: Yazad Madan
---

# Answer-sheet fallback for unrouted hosts

Status: implemented and tested synthetically. Not exercised in a loaded extension on a real unrouted site.

## What it does

Any public https host with no registered adapter can now be scanned and reviewed in answer-sheet mode. The popup and review panel call `PortalHostPolicy.assertAllowed`. A native host (Workday, Greenhouse, the Phenom hosts, the paired fixture) keeps its existing routing. An eligible unrouted host also gets `adapters/fallback.js` injected, which registers an adapter with `mode: "answer_sheet_only"`, `requiresApplicationMode: true`, and refusing fill and upload writers, then sets `PortalFallbackActive`. The registry returns that adapter only on a page where it was injected. Inspect mode also works on these hosts, so exports can be captured for new adapters.

## Boundaries

- Rejected unchanged: http, loopback, localhost and `.local`, `.internal`, dotless and IP hosts, URLs with credentials, and the unpaired loopback fixture. The original policy error and `supported()` results are untouched.
- No manifest change. Host access still comes from `activeTab` after the person clicks the popup, and `host_permissions` stays `http://127.0.0.1/*`.
- Fill, upload, and guarded Next are refused by the adapter, the engine's answer-sheet check, and the progression guard. A visible CAPTCHA still gates first. Submit counters stay at zero.
- Native adapters are unaffected because the fallback is chosen only when no host pattern matches.

## Limits

No loaded-extension test covers the fallback path: the headless test harness cannot grant `activeTab`, so tab URLs are hidden from the extension for an https site. Policy, injection lists, routing, and adapter behavior are covered by `test_public_fallback.py`. Real compatibility on an unrouted site, including the helper flow and application mode for an unaudited Application ID, is UNVERIFIED.
