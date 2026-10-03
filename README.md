---
author: Yazad Madan
---

# Application pipeline extension

A local Python helper and Chrome or Edge extension for reviewing and filling selected job application fields. Resume preparation stays in the existing private Resume workflow. This repository contains the portal prototype, research, and trial findings, not candidate profiles, resumes, trackers, or that workflow's Git history.

The prototype imports one audited application, displays sourced answers, preserves existing values unless explicitly selected for overwrite, verifies selected writes, and attaches the reviewed resume. Login, navigation, signatures, attestations, and final submission remain manual. Inspection-only mode works without pairing or importing an application.

## Run locally

The existing Resume checkout supplies the master profile, reference scripts, resume builder, and installed dependencies. Configure its path explicitly:

```powershell
.\portal_pipeline\start.ps1 -Source D:\Code\Resume
```

Load `portal_pipeline/extension` as an unpacked extension. See [setup and usage](portal_pipeline/README.md) and the [inspection checklist](portal_pipeline/INSPECTION.md).

Tests require the existing source checkout and Playwright Chromium:

```powershell
$env:PORTAL_SOURCE = 'D:\Code\Resume'
py -B -m unittest discover -s portal_pipeline\tests -v
```

The code currently depends on that external source checkout. It is not a standalone replacement for the resume workflow. Do not commit source data to satisfy those dependencies.

## Development status

Version `0.3.1` passes 76 automated tests on synthetic fixtures, including a loaded MV3 extension. No real employer application has been validated through final review. Workday is the initial target. Greenhouse is the next requested development phase.

The extension's persistent host permission covers only the local helper. Real application page access is requested by user action. The routed-host inspection test uses a temporary extension copy with test-only host permissions because opening a popup as a test tab does not grant `activeTab`; it does not establish the real browser permission flow.

- [Research and project plan](docs/PROJECT_PLAN.md)
- [Development handoff](portal_pipeline/HANDOFF.md)
- [Failures and limitations](docs/TRIAL_ERRORS.md)
- [Original Greenhouse trial report](docs/trials/LEGACY_GREENHOUSE_TRIAL.md)

The legacy report records a separate earlier prototype. Its test counts and safety stop are historical evidence, not current extension results.
