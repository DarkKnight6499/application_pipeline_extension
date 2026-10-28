"""Oracle (JPMC) resume and cover letter slots: remove a wrong file, attach the intended one. Never submits."""
from pathlib import Path

from oracle_history import OracleError, OracleResult, click_control, require_no_dialog

# Config
SLOT_RESUME, SLOT_COVER = "resume", "cover"
REMOVE_LABEL = {SLOT_RESUME: "remove resume", SLOT_COVER: "remove cover letter"}
EMPTY_WORD = {SLOT_RESUME: "resume", SLOT_COVER: "cover letter"}
INDEX_KEY, REMOVE_KEY, NAME_KEY, INPUT_KEY, TEXT_KEY = "index", "remove", "name", "input", "text"
REMOVE_ACTION, ATTACH_ACTION = "remove", "attach"
COMPONENT_SELECTOR = ".attachment-upload-button"
REMOVE_SELECTOR = ".attachment-upload-button__bottom-button"
INPUT_SELECTOR = "input[type=file]"
REMOVE_WAIT_MS, UPLOAD_WAIT_MS, UPLOAD_POLLS = 1500, 500, 20
SLOT_JS = r"""() => [...document.querySelectorAll('.attachment-upload-button')].map((node, index) => {
  const remove = node.querySelector('.attachment-upload-button__bottom-button');
  const name = node.querySelector('.attachment-upload-button__download');
  return {index, remove: remove ? remove.textContent.trim().toLowerCase() : "", name: name ? name.textContent.trim() : "",
          input: !!node.querySelector('input[type=file]'), text: node.innerText.replace(/\s+/g, ' ').trim().slice(0, 120)};
})"""


def plan(existing, resume=None, cover=None, drop_cover=False):
    """Actions to reach the wanted files; existing maps slot to the attached file name or None."""
    actions = []
    for slot, wanted, drop in ((SLOT_RESUME, resume, False), (SLOT_COVER, cover, drop_cover)):
        have = existing.get(slot)
        wanted_name = Path(wanted).name if wanted else None
        if have and wanted_name and have == wanted_name:
            continue
        if have and (wanted_name or drop):
            actions.append((REMOVE_ACTION, slot, None))
        if wanted_name:
            actions.append((ATTACH_ACTION, slot, Path(wanted)))
    return actions


def existing_slots(rows):
    """Map slot to attached file name from scanned attachment components."""
    found = {}
    for row in rows:
        for slot, label in REMOVE_LABEL.items():
            if row[REMOVE_KEY] == label and row[NAME_KEY]:
                if slot in found:
                    raise OracleError("ambiguous_slot", slot)
                found[slot] = row[NAME_KEY]
    return found


def slot_index(rows, slot):
    """Index of the one component holding the slot's remove button; None when absent or ambiguous."""
    hits = [row[INDEX_KEY] for row in rows if row[REMOVE_KEY] == REMOVE_LABEL[slot] and row[NAME_KEY]]
    return hits[0] if len(hits) == 1 else None


def remove(page, slot):
    try:
        require_no_dialog(page)
        if slot not in REMOVE_LABEL:
            return OracleResult(False, "unknown_slot", slot)
        index = slot_index(page.evaluate(SLOT_JS), slot)
        if index is None:
            return OracleResult(False, "ambiguous_slot", slot)
        require_no_dialog(page)
        click_control(page, page.locator(COMPONENT_SELECTOR).nth(index).locator(REMOVE_SELECTOR), slot)
        page.wait_for_timeout(REMOVE_WAIT_MS)
        require_no_dialog(page)
        if slot in existing_slots(page.evaluate(SLOT_JS)):
            return OracleResult(False, "removal_unconfirmed", slot)
        return OracleResult()
    except Exception as error:
        return _failure(error, slot)


def empty_index(rows, slot):
    """Index of the one empty component whose prompt names the slot; None when absent or ambiguous."""
    hits = [row[INDEX_KEY] for row in rows if not row[NAME_KEY] and row[INPUT_KEY] and EMPTY_WORD[slot] in row[TEXT_KEY].lower()]
    return hits[0] if len(hits) == 1 else None


def attach(page, slot, path):
    try:
        require_no_dialog(page)
        if slot not in EMPTY_WORD:
            return OracleResult(False, "unknown_slot", slot)
        if not Path(path).is_file():
            return OracleResult(False, "missing_file", slot)
        index = empty_index(page.evaluate(SLOT_JS), slot)
        if index is None:
            return OracleResult(False, "ambiguous_slot", slot)
        require_no_dialog(page)
        page.locator(COMPONENT_SELECTOR).nth(index).locator(INPUT_SELECTOR).set_input_files(str(path))
        for _ in range(UPLOAD_POLLS):
            page.wait_for_timeout(UPLOAD_WAIT_MS)
            require_no_dialog(page)
            if existing_slots(page.evaluate(SLOT_JS)).get(slot) == Path(path).name:
                return OracleResult()
        return OracleResult(False, "attachment_unconfirmed", slot)
    except Exception as error:
        return _failure(error, slot)


def _failure(error, slot, notes=()):
    return OracleResult(False, error.reason if isinstance(error, OracleError) else "attachment_error",
                        error.field if isinstance(error, OracleError) else slot, notes)


def apply(page, resume=None, cover=None, drop_cover=False) -> OracleResult:
    """Stop on the first failure; callers must inspect ok before proceeding."""
    notes = []
    slot = "attachment"
    try:
        require_no_dialog(page)
        actions = plan(existing_slots(page.evaluate(SLOT_JS)), resume, cover, drop_cover)
        for action, slot, path in actions:
            if action == ATTACH_ACTION and not Path(path).is_file():
                return OracleResult(False, "missing_file", slot, notes)
        for action, slot, path in actions:
            done = remove(page, slot) if action == REMOVE_ACTION else attach(page, slot, path)
            notes.append(f"{action} {slot}: {'ok' if done.ok else 'FAILED'}")
            if not done.ok:
                return OracleResult(False, done.reason, done.field, notes)
        return OracleResult(notes=notes)
    except Exception as error:
        return _failure(error, slot, notes)
