---
author: Yazad Madan
---

# Frame inspection and frame fill (iCIMS, PF7)

Status: implemented and tested synthetically. Frame inspection has a loaded-extension test. Frame fill is tested with a mocked Chrome API and fabricated pages; it has not run in a loaded extension and not on a real iCIMS site. The iCIMS adapter has `hosts: []`, so no real frame can reach it.

## Frame inspection

In every mode the review page injects the page bridge into each frame the extension can access. `activeTab` covers same-origin frames only, so cross-origin frames stay uninspected and the existing `iframe_uninspected` note applies. In inspection mode the panel and the export list frame fields under a "Frame" heading and add `frame_reports`, each with `frame: {url, adapter, fill}`.

## Frame fill

A frame serves scan, fill, and mode commands only when the adapter that routes its own URL is marked `frameFill`. Today only the `icims` adapter carries that flag, and it routes no real host, so on production pages every frame serves inspection only. The review page moves work into a frame only when the top page shows no visible fields and exactly one frame reports a `frameFill` adapter with fields. The status line then names the frame.

Guards, all enforced in the frame bridge:

- The frame must be same-origin with the top page, and the command must carry the frame URL seen at selection; a navigated frame is refused until rescan.
- Selected-fields-only fill, overwrite off by default, password and protected controls, and the CAPTCHA gate all come from the shared engine. Submit counters stay at zero in tests.
- Page progression (guarded Next) is refused inside a frame.
- The iCIMS adapter does not require application mode, so no application mode, restriction persistence, or long-form broker call runs from a frame; the background still accepts those only from the top frame. A frame fills without long-form drafts.
- Every top-level command still targets `frameId: 0` or the chosen frame explicitly, never a broadcast.
- No manifest change.

## Not done

Answer sheet export from a frame and per-application CAPTCHA restriction persistence for frame-hosted forms. The iCIMS email capture step before the form is not modelled. Which frame holds the real form, and whether it is same-origin, is UNVERIFIED until a real export exists. Register a real iCIMS host only after that export and a reviewed contract.
