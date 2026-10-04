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

Public synthetic tests run without the source checkout:

```powershell
py -3 -m pip install -r portal_pipeline\requirements-dev.txt
py -3 -m playwright install chromium
py -3 -B -m unittest discover -s portal_pipeline\tests -v
```

To use installed Edge instead of packaged Chromium, set `$env:PORTAL_TEST_BROWSER = 'msedge'`. For a visible synthetic browser trial, also set `$env:PORTAL_TEST_HEADFUL = '1'` and run `py -3 -B -m unittest discover -s portal_pipeline\tests -p test_public_trial.py -v`. Trial screenshots are saved in the ignored `portal_pipeline/test-results/` folder. The synthetic helper uses an explicitly fabricated session and attachment stub; this does not validate resume building or auditing.

Without `PORTAL_SOURCE`, external workflow tests report explicit environment skips. An invalid explicitly configured source remains a configuration error. Full external integration requires the existing source checkout and Playwright Chromium:

```powershell
$env:PORTAL_SOURCE = 'D:\Code\Resume'
py -3 -B -m unittest discover -s portal_pipeline\tests -v
```

The production helper still depends on that external source checkout. It is not a standalone replacement for the resume workflow. Integration tests read its master profile and copy it into temporary local fixtures. Do not commit source data or generated integration artifacts to satisfy those dependencies.

## Development status

Version `0.8.0` includes application-specific profile review with stale-cache invalidation and separately displayed tailored drafts, selected-field review, the per-application sponsorship toggle, guarded Next with its switch off by default, checksum-verified resume attachment, and a synthetic-only Phenom adapter alongside Workday and Greenhouse. Phenom applies only to the two documented career-site hosts; actual apply hosts and markup remain unverified. See [current validation and remaining work](docs/STATUS_AND_NEXT_STEPS.md). No real employer application has been validated through final review.

The extension's persistent host permission covers only the local helper. Real application page access is requested by user action. The routed-host inspection test uses a temporary extension copy with test-only host permissions because opening a popup as a test tab does not grant `activeTab`; it does not establish the real browser permission flow.

- [Research and project plan](docs/PROJECT_PLAN.md)
- [Development handoff](portal_pipeline/HANDOFF.md)
- [Status and next steps](docs/STATUS_AND_NEXT_STEPS.md)
- [Failures and limitations](docs/TRIAL_ERRORS.md)
- [Greenhouse contract and evidence](docs/GREENHOUSE_CONTRACT.md)
- [Original Greenhouse trial report](docs/trials/LEGACY_GREENHOUSE_TRIAL.md)

The legacy report records a separate earlier prototype. Its test counts and safety stop are historical evidence, not current extension results.

## Credits

Ideas, not code, are adapted from two MIT-licensed projects.

- [career-ops-hq/career-ops](https://github.com/career-ops-hq/career-ops) (MIT): source precedence, preflight gates, never inventing legal or demographic answers, character-limit counting, the pre-action field sweep, and a table of ATS quirks.
- [GodsScion/Auto_job_applier_linkedIn](https://github.com/GodsScion/Auto_job_applier_linkedIn) (MIT): keyword label classification, whole-word matching, work-authorization question ordering, Yes or No option matching that refuses to guess, and stall detection. Random answering, auto-submit, stealth drivers and bulk applying are not adopted.
