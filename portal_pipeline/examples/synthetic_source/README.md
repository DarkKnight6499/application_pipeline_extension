---
author: Yazad Madan
updated: 2026-10-22
---

# Dummy source inputs

All candidate facts here are invented. `demo.py` copies them into a temporary directory; it never reads the owner's Resume checkout.

| Private input shape | Public development replacement |
|---|---|
| Identity, contact, employment, education | `_Reference/Resume_Content_Master.json` |
| Confirmed sourced answers and role descriptions | `_Reference/Application_Boilerplate.md` |
| Role-date reference | `_Reference/Builder_Internals.md`; synthetic master dates need no overrides |
| Resume attachment | `demo.py` generates a valid Word file labeled synthetic, with author metadata |
| Application/session data and pairing token | `demo.py` creates temporary sandbox state and a fresh token |
| Tracker, audit, builder, portal exports, browser lifecycle | Existing public tests create fabricated fixtures and mocks; these are not production workflow implementations |
| Credentials, cookies, real application IDs, final submissions | Not needed and not supplied |

Unknown answers intentionally remain pending. These files are not an audited application folder. Do not point the production `server.py --source` or `PORTAL_SOURCE` at this directory. Use the [contributor instructions](../../../CONTRIBUTING.md) to run the demo or public tests instead.
