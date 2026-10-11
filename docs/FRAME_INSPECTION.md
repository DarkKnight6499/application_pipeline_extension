---
author: Yazad Madan
---

# Read-only same-origin frame inspection (iCIMS preparation, PF7)

Status: implemented, tested in a loaded extension on fabricated pages. Not tested on a real iCIMS site.

## What it does

In inspection mode the review page injects a read-only bridge into every frame the extension can access, then asks each frame for the same structure report the top page gives. The panel and the exported JSON list those frame fields under a "Frame" heading and add `frame_reports` to the report. Access comes from `activeTab`, which covers same-origin frames only. A cross-origin frame stays uninspected and the existing `iframe_uninspected` coverage note still applies.

## Boundaries

- `frame-bridge.js` runs only in non-top frames and answers `portal-inspect` from the trusted review page. It has no scan, fill, mode, or progress handler. A loaded-extension test confirms the frame returns no response to those messages.
- Every top-level review command now targets `frameId: 0`, so a frame can never answer a scan, fill, or mode request.
- Frames are injected only in inspection mode, not in popup or fill flows. Application mode, longform checks, and session binding remain top-level only.
- Password, hidden, and protected controls are omitted exactly as for the top page. Entered values are not reported.
- No manifest change.

## Not done

Answer sheet and fill inside a frame are not implemented. They need frame-aware field IDs, session and URL binding, and application mode checks, which change the top-level-only guards. That needs a separate reviewed design after a real iCIMS export shows whether the form frame is same-origin. There is no routed iCIMS adapter and no host registration. Email capture before the form is not modelled.
