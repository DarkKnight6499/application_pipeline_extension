---
author: Yazad Madan
---

# Review of the stacked portal pull requests

Reviewed October 3, 2026. Recommendation: hold merging until profile compatibility and source-enabled integration assertions are corrected. No PR was merged, and no review message was posted externally.

## Reviewed revisions

The changes are stacked and should be evaluated in this order:

1. [PR #1: selected-field safety and independent synthetic trials](https://github.com/DarkKnight6499/application_pipeline_extension/pull/1), head `a35cc5e14e3025c2770fecddab7beda76ff0aa37`, based on main.
2. [PR #2: inspection coverage and follow-up safety](https://github.com/DarkKnight6499/application_pipeline_extension/pull/2), head `4123211954f9cbfd3daa4021882ed28cfe24e369`, based on PR #1.
3. [PR #3: dynamic protection and helper path containment](https://github.com/DarkKnight6499/application_pipeline_extension/pull/3), head `bd1a31fc4d826bebd571f64dc8397c7a4a6e052a`, based on PR #2.

The combined stack was tested in a separate detached worktree. The production checkout and its visible live-trial browser remain on version 0.4.0. PR validation and live production inspection are separate evidence.

## Findings

### P2: confirmed annotated boolean answers no longer resolve

[portal_profile.py, lines 104 to 106](https://github.com/DarkKnight6499/application_pipeline_extension/blob/bd1a31fc4d826bebd571f64dc8397c7a4a6e052a/portal_pipeline/portal_profile.py#L104) now accepts only an entire `Yes` or `No` value for boolean answers. The existing source uses a confirmed sponsorship-now answer with explanatory text. The parser omits that fact, so previously available proposals become pending.

A synthetic reproduction uses `Require sponsorship now: No (current permit)`. The resolved values omit `sponsorship_now`. This reproduction contains no candidate facts. The real source-enabled backend test raises `KeyError: 'sponsorship_now'`, and three browser integration tests fail because the proposal or selected answer is absent.

Preserve unknown, conflicting, and confirmation-required guards. Reconcile the established confirmed-answer format through narrowly defined parsing or an explicit structured migration. Do not edit the private source merely to make this PR's tests pass. Add a public regression for the supported annotated format and rerun source-enabled integration tests.

### P2: source-enabled integration assertions are stale

Two additional browser failures are assertion mismatches:

- [test_browser.py, line 498](https://github.com/DarkKnight6499/application_pipeline_extension/blob/bd1a31fc4d826bebd571f64dc8397c7a4a6e052a/portal_pipeline/tests/test_browser.py#L498) expects `question changed while opening`. The guard correctly refuses the write with `Question or control identity changed. Rescan before filling.` Update the assertion while retaining checks that no option was selected.
- [test_browser.py, lines 570 to 572](https://github.com/DarkKnight6499/application_pipeline_extension/blob/bd1a31fc4d826bebd571f64dc8397c7a4a6e052a/portal_pipeline/tests/test_browser.py#L570) rejects the substring `current` anywhere in serialized inspection JSON. The new structural coverage value `visible_light_dom_current_page` contains that word. This failure does not demonstrate a private-answer leak. Check forbidden answer keys and private fixture values structurally instead.

The public-only run skips these source-dependent tests, which concealed the failures. Validate both public fixtures and the configured private-source integration path before merging.

## Independent validation

At PR #3's reviewed head, the full suite ran with explicit read-only source configuration:

```powershell
$env:PORTAL_SOURCE = 'D:\Code\Resume'
py -B -m unittest discover -s portal_pipeline\tests -v
```

Result: 168 tests in 101.236 seconds. 160 passed, 5 failed, 1 errored, and 2 skipped. The two skips require Windows file-symlink privileges. The Windows directory-junction regression passed. JavaScript syntax checks passed.

Failure breakdown: four failures or errors stem from the missing sponsorship-now fact; two failures are the stale browser assertions described above. Public safety regressions passed, including the tested dynamic protection and containment cases. Source-preservation checks passed. These results do not establish safety for every possible employer page or live compatibility.

## Follow-up

Correct the two findings in the other agent's branches, rerun the complete source-enabled suite, and review the updated heads. Merge order, if later authorized, is #1, then #2, then #3 with their bases reconciled. Continue live Workday and Greenhouse acceptance separately; no application has reached verified remote final-review persistence.
