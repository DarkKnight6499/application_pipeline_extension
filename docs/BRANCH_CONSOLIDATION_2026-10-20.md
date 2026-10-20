---
author: Yazad Madan
updated: 2026-10-20
---

# Branch consolidation

The owner requested merging all fixes and branches to main. Consolidation starts from `fb6dd1d`, including the October 11 runtime checkpoint and October 20 live Workday handoff.

## Resolution

- Merge `1bc7288` retains the historical stacked-PR review and the previously uncommitted backend audit. The HANDOFF conflict preserves the current handoff; the historical review now points to current acceptance.
- Merge `3d6b055` records superseded branch ancestry with the `ours` strategy. It intentionally changes no runtime, tests, fixtures, permissions, or current safety behavior. Every local branch and fetched origin branch at audit time is an ancestor afterward.
- The old Greenhouse test file matches the current file. Session-profile and placeholder runtime patches match their integrated counterparts. Old P7 and sponsorship branches are superseded by the reviewed integration and its additional guards. The remaining safety branches have no unique patches after patch-equivalence comparison.
- Dirty worktrees remain intact. Normalized blob history confirms most files were already integrated. Remaining mode-browser differences are later refusal, collateral, identity, and length guards in the integrated version. Remaining Oracle fixture changes add author metadata. Old long-form, MV3, and Oracle notes omit later integration evidence. The unique backend audit is retained above.
- Branch names and worktrees are preserved. Candidate answers, raw exports, Resume data, credentials, and ignored local artifacts are excluded.

## Validation

FULL with `PORTAL_SOURCE=D:/Code/Resume` and Edge passes 573 tests in 497.933 seconds, with two expected Windows file-symlink privilege skips. PUBLIC without `PORTAL_SOURCE` passes 491 tests in 367.451 seconds, with 17 explicit source-environment skips and the same two symlink skips. Both suites have zero failures or errors. All 28 extension JavaScript files pass `node --check`; all 80 Python files compile with bytecode outside the repository. Documentation links, attribution, and Git whitespace checks pass. Export-intake rejection messages are expected synthetic negative-test output. These checks do not establish live employer compatibility. The October 18 Workday gaps and pending native UI answers remain as documented in LIVE_WORKDAY_HANDOFF.md.

## Audited refs

These hashes identify the audit snapshot before the final documentation commit and main update.

```text
codex/backend-audit bcdea7fb7a1de900cb0b18a1afdfd4726f32bc46
docs/live-test-runbook b32a986dff9bf51a1a2836ee04ad2f3e03a16d1e
docs/live-validation-preparation bcdea7fb7a1de900cb0b18a1afdfd4726f32bc46
docs/live-workday-handoff-2026-10-20 fb6dd1d755df27cf671484825d929454d7f7e182
docs/p0-contracts 4c785169ceb8193eb8e3d8f8e48267dd9587f2b4
docs/portal-export-readiness 47bc4a12304ddb4ac8fe1f12f3ed666508282cbc
feat/application-mode-backend 7310dda104ae0dd7e79e6a428ad2b672b6c56766
feat/application-mode-browser 7310dda104ae0dd7e79e6a428ad2b672b6c56766
feat/greenhouse-combobox b2c036c800a6f6b4b6e8f1eec8cc4f1d8ece3464
feat/p1-adapter-interface dd6cb59bfc1cde92a3949c2114412287bd07ae5f
feat/p2-resolver-v2 a88688a7c875fc091bb98abe95898a4d925d456f
feat/p3-classifier 7b9935416613520992eb51ffc8371555c963f1f0
feat/p4-preflight 46c7f92b1876d9f52af1db124f75dc73463df80a
feat/p5-answer-sheet fcf4843883b03b75afc154100db7bdddcb0214b0
feat/p6-fill-hardening 3b6778e783052e8637f663d7624cf3f51bb44c99
feat/p7-progression 996a674b1798af95f412b528de13bebf0bac2871
feat/p8-portal-record 6b4f187e70e3e522a9b09927783007999cb032b0
feat/pf1-workday-synthetic 47bc4a12304ddb4ac8fe1f12f3ed666508282cbc
feat/pf2-oracle-synthetic 47bc4a12304ddb4ac8fe1f12f3ed666508282cbc
feat/pf4-greenhouse-completion 2d6de1e27cb660a5353018a482b9e724d6460d4f
feat/pf5-phenom 5db0ba3f5a066be0823257c137d60e7f121ab574
feat/session-profile-review-fix b863d07043331c62c3479018dbb3d15c35b58223
feat/sponsorship-toggle 80490bfa21b59a29d0e34e8dddbade708a80b1b4
feat/tb-longform e90113810a06c10bdb70d185e9db00f5b20dbcc7
feat/te-question-corpus 81bf7c908ec5b5b35f91a56bde7089db85d26d88
feat/tf-replay-harness c380557fbabe51860c685d486401aaa00dac80d4
fix/answer-sheet-next-guard 47bc4a12304ddb4ac8fe1f12f3ed666508282cbc
fix/answer-sheet-placeholder c205affcdb0c840eea3b8fe3f0747425d21dad60
fix/attestation-controls 6bd3e47974747dbed4569524a696ae8639cd6ce1
fix/attestation-heading-ancestry 258d812d2084cecf05d490f7d58cb940ded7c8d2
fix/csp-approved-waits 7315239286e1dda8e4d9bc709fe44a1c636064d5
fix/existing-upload-multiple-race 22bdd28671771fcf78b96f0587cdb25aa3e8a659
fix/first-upload-multiple-race 212ce52db5022b0ce528d63b62bb8b37304f119d
fix/p1-visible-captcha-gate 001e6b741811145df47186b96837ded0bd27578d
fix/p3-classifier-review 2904ded4a0891033b6f9fc20a1a00bd0c66c0b17
fix/preflight-manual-boundary db91f0f79c753defd5ed87170796ee4d6a9714ee
fix/real-source-compat 07d691a52d49269ba5d6458d196ab7b14829bd62
fix/session-profile-review c49d86cdd1f67d1f8678a795fdb61dddb0a0a046
integration/all-branches-2026-10-20 3d6b055876c7e38b2f79b2e312935a41f90fe20c
integration/application-mode-persistence e90113810a06c10bdb70d185e9db00f5b20dbcc7
integration/approved-portal-updates 47bc4a12304ddb4ac8fe1f12f3ed666508282cbc
integration/longform-and-mode-tests 9c5ed08e94d7d50150c2c6246e67f4ee9b4c6da0
integration/parallel-portal-phases 88dd40c59db6458a40c459a1299c48386f466f81
integration/pf1-pf2-preparation 7310dda104ae0dd7e79e6a428ad2b672b6c56766
integration/validated-portal-phases a1f215f2ba6a03b7bb859c3d16a60f2a02524cfb
main bcdea7fb7a1de900cb0b18a1afdfd4726f32bc46
review/stacked-pr-trial 857e365093f9a461525fbb9bdf3068465509ca36
test/application-mode-mv3 e90113810a06c10bdb70d185e9db00f5b20dbcc7
test/csp-safe-popup-wait b39cb5f8388efa9316db2f363d260b860d56fbfe
today/validate 154d6e05e0f8657cfa11d44b150576f722c6d2b4
origin/ccr-67ea04e8-ss3ld3 154d6e05e0f8657cfa11d44b150576f722c6d2b4
origin/docs/live-validation-preparation bcdea7fb7a1de900cb0b18a1afdfd4726f32bc46
origin/docs/live-workday-handoff-2026-10-20 fb6dd1d755df27cf671484825d929454d7f7e182
origin/feat/followup-inspection-safety 4123211954f9cbfd3daa4021882ed28cfe24e369
origin/feat/greenhouse-combobox b2c036c800a6f6b4b6e8f1eec8cc4f1d8ece3464
origin/feat/p7-progression f9f6b4d0cd614528014206299faa0630277390e8
origin/feat/pf4-greenhouse-completion 2d6de1e27cb660a5353018a482b9e724d6460d4f
origin/feat/session-profile-review-fix b863d07043331c62c3479018dbb3d15c35b58223
origin/feat/sponsorship-toggle ef1790569ac3c187d3341e905ebb7621044c3872
origin/fix/answer-sheet-placeholder c205affcdb0c840eea3b8fe3f0747425d21dad60
origin/fix/attestation-controls 6bd3e47974747dbed4569524a696ae8639cd6ce1
origin/fix/attestation-heading-ancestry 258d812d2084cecf05d490f7d58cb940ded7c8d2
origin/fix/csp-approved-waits 7315239286e1dda8e4d9bc709fe44a1c636064d5
origin/fix/existing-upload-multiple-race 22bdd28671771fcf78b96f0587cdb25aa3e8a659
origin/fix/first-upload-multiple-race 212ce52db5022b0ce528d63b62bb8b37304f119d
origin/fix/p1-visible-captcha-gate 001e6b741811145df47186b96837ded0bd27578d
origin/fix/p3-classifier-review 7880cc0c3baf2f4c4a0ce98352b72f45af1559b2
origin/fix/preflight-manual-boundary db91f0f79c753defd5ed87170796ee4d6a9714ee
origin/fix/probe-safety-1-5 a35cc5e14e3025c2770fecddab7beda76ff0aa37
origin/fix/real-source-compat 07d691a52d49269ba5d6458d196ab7b14829bd62
origin/fix/remaining-probe-boundaries bd1a31fc4d826bebd571f64dc8397c7a4a6e052a
origin/fix/session-profile-review c49d86cdd1f67d1f8678a795fdb61dddb0a0a046
origin/integration/application-mode-persistence e90113810a06c10bdb70d185e9db00f5b20dbcc7
origin/integration/approved-portal-updates 47bc4a12304ddb4ac8fe1f12f3ed666508282cbc
origin/integration/longform-and-mode-tests 9c5ed08e94d7d50150c2c6246e67f4ee9b4c6da0
origin/integration/parallel-portal-phases 88dd40c59db6458a40c459a1299c48386f466f81
origin/integration/pf1-pf2-preparation 7310dda104ae0dd7e79e6a428ad2b672b6c56766
origin/integration/validated-portal-phases a1f215f2ba6a03b7bb859c3d16a60f2a02524cfb
origin/main bcdea7fb7a1de900cb0b18a1afdfd4726f32bc46
origin/pr-1 a35cc5e14e3025c2770fecddab7beda76ff0aa37
origin/pr-2 4123211954f9cbfd3daa4021882ed28cfe24e369
origin/pr-3 bd1a31fc4d826bebd571f64dc8397c7a4a6e052a
origin/review/stacked-pr-trial 857e365093f9a461525fbb9bdf3068465509ca36
origin/test/csp-safe-popup-wait b39cb5f8388efa9316db2f363d260b860d56fbfe
```
