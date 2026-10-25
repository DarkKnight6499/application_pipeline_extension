"""Oracle (JPMC) resume and cover letter slots: remove a wrong file, attach the intended one. Never submits."""
from pathlib import Path

SLOT_RESUME, SLOT_COVER = "resume", "cover"
REMOVE_LABEL = {SLOT_RESUME: "remove resume", SLOT_COVER: "remove cover letter"}
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
            actions.append(("remove", slot, None))
        if wanted_name:
            actions.append(("attach", slot, Path(wanted)))
    return actions


def existing_slots(rows):
    """Map slot to attached file name from scanned attachment components."""
    found = {}
    for row in rows:
        for slot, label in REMOVE_LABEL.items():
            if row["remove"] == label and row["name"]:
                found[slot] = row["name"]
    return found


def slot_index(rows, slot):
    """Index of the one component holding the slot's remove button; None when absent or ambiguous."""
    hits = [row["index"] for row in rows if row["remove"] == REMOVE_LABEL[slot] and row["name"]]
    return hits[0] if len(hits) == 1 else None


def remove(page, slot):
    index = slot_index(page.evaluate(SLOT_JS), slot)
    if index is None:
        return False
    page.locator(".attachment-upload-button").nth(index).locator(".attachment-upload-button__bottom-button").click()
    page.wait_for_timeout(1500)
    return slot not in existing_slots(page.evaluate(SLOT_JS))


EMPTY_WORD = {SLOT_RESUME: "resume", SLOT_COVER: "cover letter"}


def empty_index(rows, slot):
    """Index of the one empty component whose prompt names the slot; None when absent or ambiguous."""
    hits = [row["index"] for row in rows if not row["name"] and row["input"] and EMPTY_WORD[slot] in row["text"].lower()]
    return hits[0] if len(hits) == 1 else None


def attach(page, slot, path):
    index = empty_index(page.evaluate(SLOT_JS), slot)
    if index is None or not Path(path).is_file():
        return False
    page.locator(".attachment-upload-button").nth(index).locator("input[type=file]").set_input_files(str(path))
    for _ in range(20):
        page.wait_for_timeout(500)
        if existing_slots(page.evaluate(SLOT_JS)).get(slot) == Path(path).name:
            return True
    return False


def apply(page, resume=None, cover=None, drop_cover=False):
    """Run the plan; returns a list of status lines and stops at the first failed action."""
    notes = []
    for action, slot, path in plan(existing_slots(page.evaluate(SLOT_JS)), resume, cover, drop_cover):
        done = remove(page, slot) if action == "remove" else attach(page, slot, path)
        notes.append(f"{action} {slot}: {'ok' if done else 'FAILED'}")
        if not done:
            break
    return notes
