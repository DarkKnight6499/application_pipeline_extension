---
author: Yazad Madan
date: 2026-10-05
status: Template only, no live validation recorded
---

# One-application validation record

Copy this template into the ignored portal_pipeline/data/exports/<portal>/ folder. Keep completed records private. Record observations and pass/fail results without candidate answers, credentials, cookies, full document contents, or URL query strings. A blank or missing observation remains unverified.

| Context | Observation |
| --- | --- |
| Employer hostname and role | |
| Portal family | |
| Audited Application ID | |
| Extension version, expected 0.11.0 | |
| Date and human observer | |
| Page sequence and export filenames | |

| Check | Observed result | Evidence or stop reason |
| --- | --- | --- |
| One explicitly selected contact field | | |
| Existing values preserved unless overwrite selected | | |
| Unselected and protected controls unchanged | | |
| Required field and validation feedback reviewed | | |
| Supported dropdown exact selection retained | | |
| Unsupported dropdown left manual | | |
| Long-form draft checked, reviewed, and selected manually | | |
| Selected resume passes local audited checksum | | |
| Employer reports upload completion | | |
| Attachment remains after manual navigation | | |
| Reviewed field values remain after manual navigation | | |
| Attachment filename or preview visible at final review | | |
| Login, MFA, and CAPTCHA handled by the human | | |
| No automated signatures, attestations, or submission | | |

DOM readback and file-input assignment prove local state only. Upload completion needs an employer indicator, and persistence needs observation after manual navigation. Stop at final review. Actual submission and tracker confirmation belong to the human and existing Resume workflow. Keep Employer Reference ID separate from the audited Application ID.
