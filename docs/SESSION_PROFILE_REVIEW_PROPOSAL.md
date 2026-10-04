---
author: Yazad Madan
updated: 2026-10-04
---

# Session profile review implementation

The approved setup changes and production repair were applied on `feat/session-profile-review-fix`. This document retains the original red-case evidence and exact approved mock scope below.

## Result

The panel loads the current session, then requires its session profile. Invalid or failed profile loading stops before scan and Fill controls. A valid empty `values` object keeps unknown answers pending. Each cached row records its proposal, source, status, sponsorship truth and mode, and matching tailored draft. Changed or legacy snapshots clear cached review choices; unchanged snapshots preserve human edits. A tailored employment description draft appears with its source and status for separate review. It is never inserted or selected automatically.

The original six cases showed two passes and four red test methods before repair. Eleven session-profile tests now pass, including added cache, draft, and missing-profile checks. The five approved inherited mock files pass 23 targeted tests. JavaScript syntax, Python compilation, and diff checks pass. All evidence is synthetic. No live portal action occurred.

Follow-up review found object and array fact values were still accepted. A separate synthetic regression first failed for both shapes, then passed after limiting fact values to strings, booleans, and finite numbers. Another new test confirms a changed proposal clears the edited answer, selection, and overwrite choice together. Both follow-up tests pass, with syntax, compilation, and diff checks clean.

## Evidence

Branch `fix/session-profile-review` starts at `996a674`. Targeted tests use fabricated profiles and a synthetic page. Six new tests were run against the current implementation. Two pass and four remain red:

- Scoped profile proposals are used: pass.
- A structurally valid scoped `{values: {}}` is accepted, leaving a blank answer available for manual review: pass.
- Scoped profile failure does not fall back to global proposals: fails. The panel does not show the scoped profile error.
- Missing `values`, null or array `values`, and malformed fact entries are rejected: fails. The panel falls back to the global profile.
- A cached review value is cleared when a newer backend proposal arrives: fails. The scoped profile contains the new override, but the panel restores its old cached value and selection.
- Tailored `description_draft` is visible with review status and source while unselected: errors because the panel does not render the draft.

No broad suite was run.

## Proposed production scope

1. Load `/api/current`, then require `/api/sessions/<id>/profile`. Remove the `/api/profile` fallback from the application review path. Validate the response as an object with a non-array `values` object. Accept `{values: {}}` as a valid empty profile so fields remain pending and available for manual review. Reject a missing `values` property, null or array `values`, and malformed fact entries. On failure or an invalid response, show a clear profile-load error and do not scan fields or expose Fill controls.
2. Store a compact profile snapshot beside each cached row. Include proposal value, source, status, and any corresponding tailored draft value, source, and status. On reopen, discard that row's cached value, selection, and overwrite choice if the snapshot differs. Keep unchanged rows and their user edits.
3. For an employment description field with a matching `employment.N.description_draft`, render the draft separately with its source and `draft_needs_review` status. Do not put the draft in the answer control or select the field automatically. A future explicit use action needs separate review before implementation.

The server already resolves session profiles and tailored draft values. `background.js` already allows the session-profile GET route. No eligibility resolver changes or new permissions are proposed.

## Existing synthetic mock edits requiring approval

Two inherited panel mocks need an explicit session-profile response after the panel stops calling `/api/profile`:

1. `portal_pipeline/tests/test_public_answer_sheet.py`, lines 170 to 176. Its local `api` returns a profile only for `/api/profile`. Add an exact `/api/sessions/${session.id}/profile` branch returning the same fabricated first-name value used by this test. Keep existing answer-sheet, corpus, and pending assertions unchanged. Make `/api/profile` a failing or stale sentinel branch so an accidental global call cannot pass silently.
2. `portal_pipeline/tests/test_public_trial.py`, lines 53 to 55. Its fabricated `SimpleNamespace` pipeline has no `folder` method. The session-profile request currently raises `AttributeError`; the panel silently falls back. Add an isolated synthetic folder and accessor beside the existing `current` fixture:

```python
session_folder = root / "sandbox" / SESSION_ID
session_folder.mkdir(parents=True)
(session_folder / "session.json").write_text(json.dumps({"id": SESSION_ID}), encoding="utf-8")

def folder(session_id):
    if session_id != SESSION_ID:
        raise ValueError("Session not found.")
    return session_folder

pipeline = SimpleNamespace(source=root, lock=threading.RLock(), templates=lambda: [],
                           current=lambda: current, folder=folder,
                           resume=lambda session_id, for_upload=False: ATTACHMENT_BYTES)
```

3. `portal_pipeline/tests/test_public_sponsorship_panel.py`, lines 26 to 30, already returns a non-empty fabricated profile for a path ending in `/profile`, so it can serve the session route without new data. Narrow its predicate to the exact `/api/sessions/${session.id}/profile` route and make any `/api/profile` request fail, so the mock cannot conflate global and session profiles. This is a contract-clarifying edit, not required setup to return the session profile.
4. `portal_pipeline/tests/test_public_answer_sheet_placeholder.py` in `fix/answer-sheet-placeholder`, lines 16 to 24 in `test_unanswered_select_exports_empty_pending_value`, responds only to `/api/profile`. Add an exact session-profile response returning `{values: {}}`, which must now remain valid, and make global profile access fail. Preserve all export assertions.
5. The same file, lines 46 to 54 in `test_selected_native_select_fills_only_selection_without_submit`, accepts both global and any session profile via a broad suffix check. Restrict this to the exact session path and use a global sentinel that fails. Keep native-fill and zero-submit assertions unchanged.
6. `portal_pipeline/tests/test_public_manual_boundary.py` in `fix/preflight-manual-boundary`, lines 56 to 60 in `test_panel_passes_preflight_manual_ids_to_fill_transport`, returns the same profile for both global and session routes. Restrict the profile branch to the exact `/api/sessions/${session.id}/profile` route and make the global route fail. Keep all manual-boundary assertions unchanged.

Other `/api/profile` tests exercise backend global-profile behavior directly, not the panel, so they need no setup change. The new `test_public_session_profile_panel.py` has six test methods. Its two passing cases cover a valid scoped profile and valid empty values. Its four red cases cover scoped failure, malformed response shapes, stale cached review, and tailored draft display.

These proposed edits change only fabricated helper dependencies and response routing. They preserve existing assertions and use no candidate data. No inherited test file has been changed in this branch.
