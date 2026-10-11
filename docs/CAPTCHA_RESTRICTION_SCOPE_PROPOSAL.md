---
author: Yazad Madan
status: Proposal only, not implemented
---

# CAPTCHA restriction scope and clearing (proposal)

## Problem

The persistent, per-Application-ID CAPTCHA restriction applies only to adapters with `requiresApplicationMode`, which today are Oracle and the fallback. Workday, Greenhouse, and Phenom check for a visible challenge on each scan and fill but do not remember that one appeared, so a challenge that is dismissed and later returns mid-application is not treated as a lasting restriction. A restriction also cannot be cleared, so one false positive locks that application to answer sheet for good.

## Proposed scope

1. Decide per adapter whether it joins application mode. Recommendation: Greenhouse and Workday join once a live trial shows a challenge can appear mid-flow. Until then the per-scan gate stays, because adding persistence without evidence only adds lock-in.
2. Frame fill must read the same restriction. Today a frame form cannot, because application mode is top-level only. Keep frame fill unrouted until it does.

## Proposed clearing

- Clearing is human-only: a button on the helper's local dashboard, not in the extension panel and not reachable from any page or frame message.
- The helper writes a log entry (application ID, time, previous reason) and the sidecar returns to `fill` only for that application.
- The extension journal entry is removed on the next mode read, and a rescan is required.
- The extension never offers the clear action itself, and no automated path (model, test hook, message) may call it.

## Tests that would be needed

Restriction survives reload and helper port change for the newly joined adapters; clear route rejects any request without the dashboard token and origin; a cleared application re-restricts on the next visible challenge; frame fill refuses while restricted.

## Not decided

Which routed adapters join, and whether a restriction should expire. These need Yazad's decision after live evidence.
