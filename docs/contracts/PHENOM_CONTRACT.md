---
author: Yazad Madan
---

# Portal contract: Phenom

Synthetic only. No Inspect-only export of a real Phenom application exists, so nothing below was confirmed against a live page. Every item is UNVERIFIED unless it names a repository document as its source. Replace this file's UNVERIFIED items from an export before any live use (see Open questions).

## Portal and hosts

- Portal family: Phenom People career sites with a five-step application wizard (source: `docs/PORTAL_COVERAGE.md` row 6 and the probe table in `docs/STATUS_AND_NEXT_STEPS.md`).
- Registered host patterns (all UNVERIFIED as apply hosts; they are the career-site hosts the job-scrap scout polls, read from its local config):
  - `/(^|\.)careers\.marsh\.com$/`
  - `/(^|\.)careers\.franklintempleton\.com$/`
- Not registered: `phenompeople.com` and any other Phenom or employer host. Add a host only from a real export, one pattern per host.
- Marsh queue links redirect to the home page (source: `docs/STATUS_AND_NEXT_STEPS.md`), so whether a given posting is live is Yazad's check.

## Evidence

- Export files: none. Export date: none. Tenant: none. Logged in: not applicable.
- Documented, not exported: step 1 of the wizard is visible without login, the wizard has five steps, Marsh shows reCAPTCHA, a LinkedIn iframe is present, and native selects use ids prefixed `cntryFields.` and `phoneWidget.` (source: `docs/STATUS_AND_NEXT_STEPS.md` probe table and `docs/PORTAL_COVERAGE.md`; the probes were public pages only).
- Synthetic fixtures: `portal_pipeline/fixtures/replay/phenom/` (page_1 to page_5, gate_recaptcha, manifest.json). They reproduce the documented facts above and nothing else. The suffixes after `cntryFields.` and `phoneWidget.` (country, city, countryCode, phoneNumber), every `name.*`, `contact.*`, `linkedin.*`, `q.*` and `vd.*` id, the progress markup and the button labels are invented and UNVERIFIED.

## Page sequence

Page keys are the host and path plus the step heading (`answer_sheet.page_key`). The answer sheet classifies only the two registered career-site hosts as Phenom. Whether the real URL changes per step is UNVERIFIED, so the adapter reads the heading from the progress indicator (`stepInfo`).

| Page key (synthetic) | Heading text | Controls count | Required count | Upload controls | Navigation labels | Final-review markers |
|---|---|---|---|---|---|---|
| host/path#my information | My Information | 7 | 4 | 0 | Next | none |
| host/path#my experience | My Experience | 2 | 0 | 1 (file) | Back, Save and Continue | none |
| host/path#application questions | Application Questions | 3 | 3 | 0 | Back, Next | none |
| host/path#voluntary disclosures | Voluntary Disclosures | 3 (all protected) | 0 | 0 | Back, Next | none |
| host/path#review | Review | 0 | 0 | 0 | Back, Submit | Step 5 of 5, Review heading, Submit control |

All five rows are synthetic and UNVERIFIED. The real step names, order, control counts and navigation labels are UNVERIFIED. The wizard length of five is documented.

## Control families

- Native text input: first name, last name, email, phone number, city. Read and written with the native value setter plus events, then read back. UNVERIFIED on real pages.
- Native select with `cntryFields.*` and `phoneWidget.*` ids (documented): country, phone country code. Country and phone country code have no profile key, so they stay pending. Whether the real selects are native elements throughout is documented; option text is UNVERIFIED.
- Native select for work authorization and sponsorship questions: the shared classifier and exact option matcher apply. UNVERIFIED.
- File input for the resume: filled through the generic upload path with the audited attachment. UNVERIFIED whether the real control is a hidden input or a button.
- Voluntary self-identification selects and the consent checkbox: protected by the engine, never written (R15).
- Listbox, react-select, typeahead, date widget, radio group: none assumed. UNVERIFIED whether any appear.
- LinkedIn import iframe (documented): never entered. The engine scans only the top document, and the adapter adds no frame access. Nothing is typed into or read from it.

## Human gates seen

- reCAPTCHA on Marsh (documented; the step where it appears is UNVERIFIED). The adapter's `humanGate` composes the generic hCaptcha, reCAPTCHA and Turnstile checks, then checks a reCAPTCHA frame title, `.g-recaptcha`, and `data-sitekey`. The engine then writes nothing and reports `blocked_by_human_gate` for every selection (R3, R19). The additional selectors are synthetic guesses at common reCAPTCHA markup.
- Login, MFA, email code: none documented. Step 1 is visible without login (documented). UNVERIFIED after step 1.
- If a real export shows a CAPTCHA inside the form on every tenant, switch the mode to `answer_sheet_only` (R19) and ask Yazad.

## Repeated sections

UNVERIFIED. The synthetic wizard has none. Work history and education pages, their "Add" labels and row containers are unknown. The adapter does not click Add (plan 7.0 standard do-not).

## Mode

`fill`, as the plan sets for Phenom (rank 6). A CAPTCHA gate degrades a gated page to no writes. The adapter never clicks Next, Back or Submit; `nextStep` and `detectFinalReview` only report. Submit, Apply, Finish and Review and Submit take precedence over Next in the synthetic controls. Fill strategy is `native_setter`.

## Open questions

- Which hosts actually serve the apply wizard for Marsh and Franklin Templeton (the career-site hosts above may differ from the apply hosts).
- Real step names, order, URL behavior per step, progress indicator markup, and button labels.
- Exact `cntryFields.*` and `phoneWidget.*` id suffixes, required markers, and whether the selects carry real labels.
- Where the reCAPTCHA appears (which step, visible or invisible) and its markup.
- Whether the LinkedIn control is an iframe on every step or only step 2.
- Work history, education, and resume upload structure.
- Whether the wizard re-renders controls between steps in a way that invalidates the engine's registered surface.
- Next step: Yazad runs Inspect page only and Export field structure on every page of one real Phenom application, logged in himself, entering no answers, and saves the exports to `portal_pipeline\data\exports\phenom\`.
