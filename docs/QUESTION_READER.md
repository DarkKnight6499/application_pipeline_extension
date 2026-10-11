---
author: Yazad Madan
---

# Browser-free question reader

Status: implemented against a fabricated response only. The Greenhouse response shape is written from memory of the published Job Board API and is UNVERIFIED against a live response. No other portal is supported.

## What it does

`portal_pipeline/question_reader.py` reads one saved posting API response (a local JSON file) and writes an export-shaped report: the same schema version 1 an Inspect export uses, with `coverage.scope` set to `posting_api_response` and the reason code `posting_api_not_live_dom`. The report passes `export_intake.py validate` and can feed `export_intake.py draft` to produce a contract skeleton and fixture, so question lists can be reviewed before any page is opened.

Run from `portal_pipeline`: `python question_reader.py response.json --portal greenhouse --out report.json`.

## Boundaries

- Offline. The module has no network code, and a test fails if networking imports appear. You save the response yourself. No live call is authorized by this tool or by this phase.
- Application questions and location questions are listed. Compliance and demographic blocks are counted in `protected_fields_omitted` and never listed.
- HTML is stripped from labels, labels are capped at 200 characters, at most 300 fields are read, and files over 2 MB are refused. Hidden fields are skipped. Multiple-choice and unrecognized field types are listed with a manual reason.
- The report holds no answers. It supplies structure only, so it cannot establish how a rendered page behaves, field semantics, retention, or upload completion.

## Not done

Lever, Ashby, SmartRecruiters, and Eightfold are not implemented because their public question endpoints and response shapes are UNVERIFIED and are not invented here. Mapping questions to profile answers still happens in the extension at review time. A live fetch needs a separate, explicit approval and a reviewed request design.
