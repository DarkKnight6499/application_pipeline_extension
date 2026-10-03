# Inspect the first real portal

Use this checklist when Yazad selects an employer posting. The local fixtures prove mechanisms but do not establish compatibility with that employer's portal.

## Preparation

1. Reload extension version `0.4.0` and refresh the application tab. Workday and Greenhouse are the current portal tracks.
2. Start with **Inspect page only** in the extension popup. Inspection does not require the local helper, pairing, a candidate profile, or an application import. It displays structural control details and exports reports without offering filling. Navigate manually and use Rescan for each page.
3. Let Yazad sign in and handle MFA or CAPTCHA. Keep navigation and submission manual.
4. When ready to validate filling, prepare the resume through the existing workflow and import its audited application folder. If its tracker URL is a job board link, supply the exact employer posting URL during import. Pair the extension, reopen it with **Scan current page**, and confirm the selected employer and role before any filling.

## Record each page

Choose **Export field structure** before filling. Name each downloaded report for the page, such as `01-contact.json` or `02-experience.json`. The report contains the host, control labels, DOM names and IDs, automation IDs, roles, ownership attributes, required and disabled flags, adapter availability, and option counts.

The export omits entered and proposed answers, option text, protected controls, and URL query strings. It does not include HTML, cookies, passwords, or the pairing token. Review labels and identifiers before sharing because the employer can embed personal information there. Reports stay wherever the browser saves downloads; nothing is uploaded by this feature.

For each page, record:

| Item | Observation |
| --- | --- |
| Employer host and role | |
| Page name and position | |
| Text and native selects | |
| Select-only dropdowns with adapter available | |
| Unsupported dropdowns and their manual reason | |
| Date input format and separate month/year controls | |
| Employment and education rows already present | |
| Whether new rows must be added manually | |
| Resume upload label and completion indicator | |
| Fields retained after manual navigation | |
| Final review, signatures, and attestations | |

Do not infer missing employment dates or personal facts from a widget's default. Inspect unknown controls without selecting an answer automatically.

## Validate one control at a time

Start with one contact field. Confirm the engine's readback against the visible portal value and confirm that the portal retains it after manual navigation. Then try one supported dropdown and one resume upload, checking the employer's actual completion indicator.

If a dropdown is unsupported, record its stable role and ownership attributes, whether its options exist before opening, and how the chosen value appears after manual selection. Record option labels manually only where needed to reproduce the behavior in an anonymized fixture. Do not save raw page HTML or candidate answer dumps.

For repeated history, choose the source employer and role or school for each visible row in the panel before filling. No candidate record is assigned from page order. Verify that the employer's real record wrappers are recognized correctly, especially with partial, collapsed, or reordered history. Reopening the panel or replacing a row requires choosing again.

For split dates, check the visible month option labels and required year format. The prototype can split known month/year facts, but it does not invent missing start dates or a day for full-date controls. Leave those fields manual when the current sources do not establish the answer.

Stop at final review. This inspection does not authorize the extension or an agent to sign, attest, or submit. A built or filled application does not change its tracker status.

## Implement the next demonstrated gap

Create an anonymized fixture that reproduces one unsupported control. Add an adapter only after its contract is explicit. Include regression checks for exact choice, existing-value preservation, stale identity, unavailable options, unselected-field side effects, and submission boundaries. Keep all changes in this separate worktree.

Mark live compatibility established only after the real employer flow retains the reviewed answers and the audited attachment through its final review page. DOM readback alone is not remote persistence or upload completion.
