---
author: Yazad Madan
---

# Portal coverage matrix

Snapshot dated 2026-10-04. Execution order and phase ids (PF1 and later) live in `D:\Code\Resume\_Reference\Portal_Phased_Execution_Plan.md`.

## Method

Counts come from a read-only pass over the private application tracker (Link and Status columns, read by header name) and the job-scrap queue mapped to ATS. "Applied-like" means Status in Applied, Screening, or Rejected. The queue is not filtered for fit or location, so it measures supply, not intent. Tracker host classification is a regex heuristic. LinkedIn and Indeed tracker links are discovery links; the real apply portal behind most of them is unknown (UNVERIFIED). Rows with no link have no known portal and are out of scope. No candidate data is stored here.

Rank is by applied-like rows, then queue volume. Mode is `fill` (selected-field fill) or `answer_sheet_only` (scan and propose, write an answer sheet plus the resume file path, Yazad fills manually). "Public API" notes whether a public endpoint exists and confirms it is read-only for this project.

## Ranked matrix

| Rank | Portal | Applied-like / queue | Phase | Mode | Known quirks | Automation risk | Public API | Fill strategy and upload |
|---|---|---|---|---|---|---|---|---|
| 1 | Workday | 138 / 3,654 | PF1 | fill | Create Account or Sign In is step 1 on every tenant probed; React inputs may need real keystrokes; hidden per-block required fields; Yes or No order varies; listbox buttons; repeated sections need "Add"; honeypot on sign-in; Autofill-with-Resume may drop en-dash dates (UNVERIFIED) | Medium: honeypot on sign-in; no in-form CAPTCHA observed (UNVERIFIED post-login) | CXS jobs JSON used by `job_scout.py` is GET only; no public apply API | Native setter plus events, readback after blur; keystroke fallback per D4; file input upload with checksum; never click "Autofill with Resume" automatically |
| 2 | LinkedIn Easy Apply | 47 linked / n.a. | TA | answer_sheet_only by default | Multi-step modal; question pages vary; User Agreement 8.2 item 13 | High: account restriction risk | None used | Opt-in fill per job only; resume chosen from LinkedIn's stored list by Yazad |
| 3 | Oracle Recruiting Cloud (JPMorgan and others) | 18 / 451 | PF2 | fill after Yazad clears the gate | Email gate first; hCaptcha; honeypot input | High at the gate | `recruitingCEJobRequisitions` REST is GET only (used by `job_scout.py`) | Native setter; stop on any CAPTCHA (R3); upload via file input UNVERIFIED until export |
| 4 | Custom bank portals (Goldman higher.gs.com, Scotiabank, AQR, UBS, Macquarie, Fitch, M&T) | 18 / 199 | PF3 | answer_sheet_only until one host has an export | Structure unknown per host (UNVERIFIED); several hand off to another ATS | Unknown | None | Resolve to underlying ATS first; build a host adapter only for a host with 5 or more queued roles and an export |
| 5 | Greenhouse | 11 / 523 | PF4 | fill | react-select re-renders invalidate refs; country and city typeahead; MyGreenhouse autofills when logged in, so value is low | Low to medium; some boards use reCAPTCHA on submit (UNVERIFIED) | Job Board API GET is public; application POST needs an employer API key | Existing react-select adapter with readback; type-ahead manual; hidden labelled resume input with checksum |
| 6 | Phenom (Marsh, Franklin Templeton) | 6 / 110 | PF5 | fill | Five-step wizard; reCAPTCHA on Marsh; LinkedIn iframe; native selects with `cntryFields.*` and `phoneWidget.*` ids | Medium (reCAPTCHA) | None verified | Native setter; skip iframe; stop at reCAPTCHA |
| 7 | Ashby | 2 / 69 | PF6 | answer_sheet_only | Automation can trigger rejection at submission; dedups by email per company | High | Public posting API GET only | No writes; answer sheet plus resume path. Never use email aliases to get around dedup |
| 8 | iCIMS | 1 / 98 | PF7 | fill (after frame support) | Email capture first; whole form inside an iframe the scanner does not enter | Medium | None verified | Needs `all_frames` injection on the same-origin form frame; native setter |
| 9 | Lever | 1 / 34 | PF8 | fill for text only | hCaptcha blocks checkbox and radio clicks; labels held outside the field | High for clicks | Postings API GET only | Text and textarea fill only; checkbox and radio listed for manual completion |
| 10 | SuccessFactors | 0 / 133 | PF9 | fill | Resume parse can silently diverge from stored profile; ten custom picklists; most behind sign-in; HSBC handoff from Eightfold | Medium | None verified | Native setter; after upload, list profile-preview fields for Yazad to compare; picklists via listbox adapter if contract matches |
| 11 | Taleo | 0 / 180 | PF10 | fill | Login first; legacy multi-page forms | Medium | None verified | Native setter; strict page detection |
| 12 | BrassRing (Kenexa) | 0 / 151 | PF11 | answer_sheet_only until export | Structure UNVERIFIED | Unknown | None verified | Decide after export |
| 13 | Eightfold (New York Life, Millennium, HSBC) | 0 / 94 | PF12 | fill | About 15 custom dropdowns; cookie banner first; HSBC hands off to SuccessFactors | Medium | Questions endpoint exists, body not read (UNVERIFIED) | Listbox-style adapter like Greenhouse; Yazad dismisses the cookie banner |
| 14 | SmartRecruiters | 0 / 86 | PF13 | answer_sheet_only until export | Structure UNVERIFIED | Unknown | Postings API GET only | Decide after export |
| 15 | Jibe, TalentBrew, Avature, HRMDirect, D. E. Shaw custom, Indeed apply | 0 / 198 combined | PF14 | answer_sheet_only | Jibe and TalentBrew are career-site front ends that usually hand off to another ATS (UNVERIFIED) | Unknown | None used | Resolve to the underlying ATS and use its phase; otherwise answer sheet |
