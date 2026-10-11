---
author: Yazad Madan
---

# Handoff resolution (PF14)

Status: implemented and tested synthetically, including one loaded-extension test. Host patterns other than the routed ones are UNVERIFIED.

## What it does

Career-site front ends such as Jibe, TalentBrew, Avature, and HRMDirect usually send the applicant to another ATS. In inspection mode, `handoff.js` reads visible links whose text says apply or start application, resolves each link's host to an ATS id and a support level, and the panel and exported report list them under "Apply links on this page (not followed)". The person then opens the link, and inspects or works on that page with the adapter it maps to.

Support levels: `routed` (adapter on real hosts: Workday, Greenhouse, the Phenom hosts), `prepared` (synthetic unrouted adapter: Lever, Ashby, Oracle, Taleo, SuccessFactors, SmartRecruiters, BrassRing, Eightfold; answer sheet fallback applies), `inspect_only` (iCIMS frames), and `fallback` (answer sheet fallback only). Unrecognized hosts are reported as `unknown`.

## Boundaries

- Read only. Links are never clicked, followed, prefetched, or fetched. A loaded-extension test confirms the page URL is unchanged and no outside request is made.
- Only https links without embedded credentials are listed. http, javascript, mailto, file, and malformed targets are ignored, as are hidden links and the extension panel.
- Host matching is anchored to the domain, so lookalikes such as `greenhouse.io.evil.invalid` resolve to `unknown`.
- Tracker and shortener links resolve to their own host and stay `unknown`; redirects are not followed.
- Top frame only. Results are capped at 20 and de-duplicated by host and label.
- No manifest change and no change to what any adapter may write. "Prepared" does not mean a host is routed; those adapters stay unrouted until an export supports a reviewed host.

## Not done

Apply buttons that navigate by script rather than an anchor href cannot be resolved. Hosts for Jibe, TalentBrew, Avature, HRMDirect, Workable, and Dayforce are listed only as general fallback. Automatic adapter selection from a link is deliberately not implemented, since the person navigates and each destination page is routed by its own host.
