---
title: Resume Creation and Selective Portal Filling
author: Yazad Madan
created: 2026-10-03
status: Prototype implemented, real employer validation pending
---

# Resume Creation and Selective Portal Filling

## Purpose and working agreement

Extend the current job application workflow from tailored resume creation to a review-ready application on an employer's portal. Yazad can select which fields to fill, edit proposed answers, choose the resume, and control progression through the form.

Develop this as a side project in small, explicitly requested work sessions when token capacity is available. Continue improving the current pipeline alongside it. Ordinary resume requests and current pipeline fixes take priority. This document records the plan; it does not authorize unattended runs, installations, portal actions, or implementation during a future resume request.

The local prototype implements profile resolution, audited resume handoff, selective filling, and structural inspection. Reliability on Yazad's actual employer portal remains untested. Workday was the initial development target. Yazad subsequently requested another portal as well, so Greenhouse is the second active development track. Live acceptance remains separate for each employer.

## Existing components to reuse

| Component | Existing source | Planned use |
|---|---|---|
| Job discovery | `job_scout.py` | Supply the posting URL and job identity; avoid building another discovery system. |
| Identity and duplicate checks | `identity_lib.py`, existing tracker workflow | Prevent preparing the wrong posting or duplicating an application. |
| Candidate hard facts | `Resume_Content_Master.json` | Supply confirmed contact, employer, education, and certification facts. |
| Verified experience | `Best_Bullets.md`, relevant project evidence | Ground resume tailoring and drafted answers in real work. |
| Resume generation | Existing drafts, per-application content JSON, `build_resume.js` | Produce the existing `Yazad_Madan.docx`; preserve the builder and formatting rules. |
| Validation | ATS, page-fit, widow, punctuation, and application audit scripts | Keep current checks before offering the resume for upload. |
| Portal answers | `Application_Boilerplate.md` | Supply approved standard answers and long-form role descriptions. |
| Tracking | `.application_id`, `Applications.xlsx`, existing writer scripts | Associate a portal session with the correct application and preserve current status semantics. |

The application profile must include full relevant employment history, not only the bullets selected for a one-page resume. Do not infer omitted history from the tailored document.

## Proposed user flow

1. Open a posting or select an existing application from the current workflow.
2. Extract or reuse the JD, resolve duplicates, and prepare the tailored resume through the existing pipeline.
3. Yazad handles account creation, login, MFA, and CAPTCHAs.
4. Scan the current application page and identify its fields and upload controls.
5. Show a review panel with the exact question, proposed answer, source, current portal value, and selection checkbox.
6. Yazad selects fields, edits answers, and chooses the application-specific resume. Unanswered or ambiguous questions remain pending.
7. Fill only selected fields and attach the selected document when requested.
8. Read back values and confirm attachment identity. Report failures rather than treating an attempted fill as success.
9. Offer safe continuation through the next form page. Rescan each page and retain relevant selections and edits.
10. Present remaining questions and a final review. Yazad signs, attests, and submits himself.
11. Update the existing tracker only after confirmation under the current workflow rules. Preserve an employer reference number when supplied.

Selection controls should support individual fields, sections such as contact or employment history, and an explicit overwrite choice for already populated fields. The default should preserve existing portal values. Editing a proposed answer for one application must not silently change the master profile.

## Boundaries inherited from the current workflow

- Use verifiable facts only. Never fabricate experience, credentials, dates, or eligibility answers.
- Preserve separate answers for sponsorship now and sponsorship in the future. A single sponsorship boolean is insufficient.
- Keep work authorization, degree status, dates, and other factual answers tied to confirmed sources. Unknown answers stay unknown.
- Do not choose voluntary demographic answers without an existing preference or Yazad's selection.
- Do not automate passwords, MFA, CAPTCHAs, or login flows.
- Do not sign, attest, or click the final submission control on Yazad's behalf.
- A filled form, uploaded resume, or clicked navigation button does not establish submission.
- Keep tracker status `To Apply` until the existing confirmation rule permits `Applied`.
- Keep application identifiers distinct from employer reference identifiers.
- Keep the current DOCX deliverable and filename rules. Do not introduce a replacement resume generator or PDF workflow.

These boundaries come from `Application_Boilerplate.md`, `New_Session_Prompt.md`, `CLAUDE.md`, and `AGENTS.md`. This plan does not replace those instructions.

## Proposed architecture, not a final technology decision

Start with a browser extension connected to a small local Python helper. The extension operates on the application page Yazad already opened. The helper reads approved project data and supplies the correct resume. This approach fits the current Windows, Python, and Node workflow and keeps the candidate profile under the project's existing control.

Separate the implementation into four parts:

1. **Application context:** posting URL, ATS type, employer, role, existing Application ID, and audited resume path.
2. **Profile and answer resolver:** confirmed facts, long-form history, standard answers, and per-application edits with source references.
3. **Portal adapter:** scan, fill, upload, verify, and identify a safe next step for a particular portal.
4. **Review interface:** field selection, answer editing, overwrite controls, pending questions, and results.

Use deterministic mappings for known fields. Evaluate Playwright for scripted adapters and debugging. Evaluate Stagehand or Browser Use only where unfamiliar page structure makes deterministic mapping insufficient. AI may interpret field meaning or draft an open-ended answer from approved evidence; it must not invent personal facts or silently choose eligibility answers.

Treat page content as input data. A job description or form label must not instruct the helper to access unrelated files or alter project rules. Expose only the data and application-specific document needed for the selected operation. Store credentials outside project data and avoid logging secrets or unnecessary personal information.

Keep portal progress separate from application tracker status. A portal session may be scanned, prepared, partially filled, awaiting review, or complete for review without becoming `Applied`. Use the existing tracker scripts and locking rules for any eventual tracker integration.

## Research references and findings

Research date: October 3, 2026. These are source-inspection findings, not measured live success rates. Recheck releases, licenses, and APIs before choosing a dependency.

| Repository | Relevant finding | Proposed treatment |
|---|---|---|
| [AutoApply](https://github.com/geckguy/AutoApply) | MIT project with an extension, local Python backend, uploads, saved answers, and guarded navigation. Its source includes tests for browser behavior. Small community; claimed ATS coverage has not been validated here. | Study first as an integration reference. Adapt its profile model rather than adopting it unchanged. |
| [Playwright](https://github.com/microsoft/playwright) | Browser automation, resilient locators, automatic waits, assertions, and debugging. | Evaluate as the deterministic browser foundation. |
| [Stagehand](https://github.com/browserbase/stagehand) | MIT SDK with local browser support and AI observation, actions, and extraction. | Evaluate for targeted fallback field discovery. |
| [Browser Use](https://github.com/browser-use/browser-use) | MIT browser agent with a local Python library and custom tools. | Consider for a bounded prototype; verify each action and result. |
| [Skyvern](https://github.com/Skyvern-AI/skyvern) | AGPL-3.0 workflow platform with vision-based automation and a browser SDK. | Secondary option if the smaller architecture proves insufficient. |
| [PaperPlane](https://github.com/Harsh-H-Shah/PaperPlane) | MIT application workflow with dedicated fillers. README lists remaining application bugs and missing extension modules. Discovery focuses on software roles. | Architecture reference rather than a replacement for this project's discovery and resume pipeline. |

Specific source findings to preserve:

- [AutoApply's profile model](https://github.com/geckguy/AutoApply/blob/main/backend/models/profile.py) has one `sponsorship_required` boolean. This project needs separate present and future answers.
- [job-apply-bot's ATS handler](https://github.com/dsharm9148/job-apply-bot/blob/main/appliers/ats_applier.py) hardcodes a work-authorization answer and returns success after clicking Submit without checking acceptance. Do not copy those patterns.
- [jobApplier](https://github.com/17nbist/jobApplier) acknowledges that only a handful of its claimed ATS integrations are live-verified. Its [refresh documentation](https://github.com/17nbist/jobApplier/blob/main/reference/REFRESH.md) describes assets extracted from another extension and specifies personal, non-redistributed use. Do not assume the bundled selector data is an independently maintained reusable foundation.
- Public discovery access does not imply application submission access. Greenhouse's [Job Board API authentication section](https://docs.greenhouse.io/job-board.html#authentication) permits public GET requests but requires a Job Board API key for application POST requests. The browser form remains the planned application interface.

## Incremental milestones

Each milestone should fit into a bounded work session. Complete its acceptance checks and record the result here before starting the next milestone.

### 0. Choose one real target and define its contract

- Select the first employer portal Yazad actually uses. Workday and Oracle are candidates, not confirmed priorities.
- Record its page sequence, field types, uploads, and review controls without submitting anything.
- Define the application context and the sources for each profile field.
- Acceptance: a clear first-portal scope and representative synthetic form fixtures, with no real candidate data embedded in tests.

### 1. Build the profile resolver

- Reuse master facts and boilerplate without creating another manually maintained source of truth.
- Resolve contact, education, full employment history, and separate sponsorship answers.
- Retain source references and per-application overrides.
- Acceptance: confirmed values map correctly; missing facts remain pending; overrides do not mutate the master.

### 2. Scan and review without filling

- Identify labels, required fields, control types, repeated sections, and uploads.
- Display proposed answers with field and section selection controls.
- Acceptance: selection and edits persist within the session; scanning does not change portal values.

### 3. Fill selected fields on the first portal

- Implement text, dropdowns, dates, repeated employment sections, and explicit overwrite behavior.
- Read back values after filling and report partial failures.
- Acceptance: unselected fields remain unchanged; selected values survive portal rendering and validation; unknown questions remain visible.

### 4. Attach the audited resume and handle page progression

- Bind the selected application to its exact `Yazad_Madan.docx`.
- Verify the attachment and rescan after safe navigation.
- Stop at final review, signature, attestation, or ambiguous controls.
- Acceptance: correct document attached; retries do not duplicate history entries or attachments; final submission is never automated.

### 5. Validate the complete flow and connect tracking

- Exercise one real application through final review during an explicitly requested session.
- Capture errors, unanswered fields, and necessary manual interventions.
- Associate the session with the existing Application ID. Use current tracker scripts only after the required confirmation.
- Acceptance: one complete, review-ready application with no silent field failures or premature `Applied` status.

### 6. Expand only after the first portal works

- Add another portal through the adapter interface.
- Introduce bounded AI fallback only for demonstrated failures of deterministic mapping.
- Evaluate correction reuse without promoting an application-specific answer into a universal default.
- Acceptance: shared behavior remains stable, with regression checks for the first portal and the existing resume pipeline.

## Work alongside current pipeline improvements

Keep two independent work streams: the functioning resume pipeline and this planned portal extension. Do not make routine resume generation depend on an unfinished browser component.

For each session:

1. State the assigned task and whether it belongs to pipeline maintenance or portal development.
2. Choose one small milestone or concrete fix. Avoid beginning a large portal integration with insufficient capacity to validate it.
3. Limit edits to the relevant files. Preserve unrelated work and stage only session-owned paths if a commit is requested.
4. Run checks appropriate to the change. After changing scripts in `_Reference`, run the existing hermetic smoke suite.
5. Record completed work, evidence, unresolved issues, and the next exact task below. Do not mark a milestone complete from code inspection alone.

Potential pipeline improvements should remain a separate queue of specific observed problems. This plan does not authorize a broad refactor, tracker migration, resume-rule change, or new application statuses.

## Current handoff

- **Completed:** feasibility research and a separately runnable local prototype under `portal_pipeline/`. It includes sourced profile resolution, audited application import, an extension-owned review panel, selected filling, checksum-verified resume attachment, and synthetic browser fixtures.
- **Isolation:** implementation was developed in `D:\Code\Resume_portal_pipeline` on `feat/portal-pipeline` and is now exported to the dedicated `application_pipeline_extension` repository. The existing workflow remains independent. Do not change tracker statuses or promote the prototype to the current workflow implicitly.
- **Technology decision:** Python localhost helper and a Manifest V3 extension for Chrome or Edge. Playwright Chromium tests validate the browser mechanisms. No cloud AI fallback is used.
- **Additional progress:** version `0.2.0` adds a bounded select-only ARIA listbox adapter, exact matching that preserves punctuation, and a structure-only inspection export. See `portal_pipeline/INSPECTION.md` for the real-portal walkthrough checklist. The adapter has synthetic and loaded-extension regression coverage.
- **History progress:** version `0.3.0` replaces candidate history inference by page order with explicit row choices, adds verified split month/year values, and prevents overlapping fills or rescans. Employer-specific row grouping still requires live inspection.
- **Inspection progress:** version `0.3.1` adds a dedicated inspection-only extension mode without helper pairing, application import, or candidate profile loading. It rejects scan and fill commands from the inspection panel. The popup now limits employer scanning to Workday.
- **Still incomplete:** selection and inspection of a real employer portal, employer-specific dropdown and date adapters, hidden upload completion checks, automatic history creation, and a real application walkthrough.
- **Next task:** select one Workday application and inspect its controls through final review with the user present. Record the first adapter contract before expanding to other portals. Final submission remains manual.
- **Open decisions:** exact first employer posting and any AI fallback need after the deterministic adapter is tested. Workday is a development assumption, not a user-confirmed priority.
- **Implementation session log:** October 3, 2026. Separate worktree created, prototype implemented, audited handoff added, and automated integration checks run. The user then requested a dedicated GitHub repository, saved trial findings, phase commits, and a second employer portal. See [portal_pipeline/HANDOFF.md](../portal_pipeline/HANDOFF.md) for the detailed validation record and next bounded task, and [README.md](../portal_pipeline/README.md) for startup instructions. Resume reference paths above refer to the external source checkout and are intentionally not copied into this public repository.

Suggested future instruction:

> Read `_Reference/Portal_Automation_Project_Plan.md` and the project instructions. Work on the next incomplete milestone in a bounded session. Preserve the current resume pipeline, validate the change, and update the handoff before stopping.
