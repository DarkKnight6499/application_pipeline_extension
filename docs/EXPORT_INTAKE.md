---
author: Yazad Madan
---

# Export intake tool

`portal_pipeline/export_intake.py` turns Inspect-only exports into a draft contract and synthetic fixtures. It runs offline, reads only the files you name, contacts no portal, and does not copy raw exports anywhere.

## Commands

Run from `portal_pipeline`:

- `python export_intake.py validate 01-contact.json 02-experience.json` checks each export and exits 1 if any fails.
- `python export_intake.py draft 01-contact.json 02-experience.json --portal "Example ATS" --out-dir <private folder>` validates first, refuses to write if any export fails, then writes `EXAMPLE_ATS_CONTRACT_DRAFT.md` and one `example_ats_page_N.html` per export.

## What validation rejects

Errors: wrong schema version, missing host or fields, any `value`, `proposal`, `current`, `answer`, `password`, `token`, `cookie`, `html`, or `options` key anywhere in the report (frame reports included), and strings that look like an email address, phone number, secret token or hex identifier, or a URL with a query string. Warnings: unknown keys, very long strings, loopback or IP hosts, and long identifiers that could be ordinary DOM ids. Warnings do not block drafting. Labels and ids can still hold employer or personal text, so read the draft before sharing.

## What the drafts contain

The contract draft follows `docs/contracts/CONTRACT_TEMPLATE.md`: hosts, export count and dates, one page-sequence row per page and per inspected frame (control, required, and upload counts), control families with an example label, coverage notes, and mode `answer_sheet_only`. Everything the export cannot show is marked UNVERIFIED, including headings, navigation labels, final review markers, repeated sections, and gates.

Fixtures use neutral labels ("Field 1") and invented option names unless you pass `--keep-labels`. Each control type is rebuilt from the export (text, textarea, select, radio group, checkbox, file, select-only combobox). A browser round trip test confirms the fixture scans back to the same control types and counts. Passwords become plain text inputs, and no values are ever generated.

## Limits

Exports describe one snapshot of visible controls, so the draft cannot establish field semantics, retention, upload completion, or live compatibility. Keep raw exports in a private ignored folder, never in Git. Review the drafts, then follow `docs/contracts/FIXTURE_POLICY.md` before adding them to the repository.
