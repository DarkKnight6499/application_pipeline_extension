"""Resume and cover letter upload for single page portals (Greenhouse, Lever, Ashby): attach only to empty slots."""
from pathlib import Path

SLOT_RESUME, SLOT_COVER = "resume", "cover"
FILE_NAME_PATTERN = r"[\w .()\-]+\.(pdf|docx?|odt|rtf|txt|md)"
SLOTS_JS = r"""pattern => [...document.querySelectorAll('input[type=file]')].map((input, index) => {
  const block = input.closest('li.application-question, .ashby-application-form-field-entry, .field, .file-upload, fieldset, form') || input.parentElement;
  const own = [...(input.labels || [])].map(l => l.textContent).join(' ') + ' ' + (input.getAttribute('aria-label') || '') + ' ' + input.name + ' ' + input.id;
  const text = (block ? block.innerText : '').replace(/\s+/g, ' ');
  const autofill = !!input.closest('.ashby-application-form-autofill-input-root');
  const attached = [...input.files].map(f => f.name);
  const shown = (text.match(new RegExp(pattern, 'i')) || [])[0] || '';
  return {index, own: own.toLowerCase(), head: text.slice(0, 160).toLowerCase(), autofill, attached, shown};
})"""


def classify(row):
    """Slot name for a scanned file input; None when it is an autofill helper or unrecognised."""
    if row["autofill"]:
        return None
    text = f"{row['own']} {row['head']}"
    if "cover" in text:
        return SLOT_COVER
    if "resume" in text or "cv" in text.split() or "curriculum" in text:
        return SLOT_RESUME
    return None


def upload(page, slot, path):
    """Attach path to the one empty input for the slot; returns a status line or None when nothing was requested."""
    if not path:
        return None
    rows = [row for row in page.evaluate(SLOTS_JS, FILE_NAME_PATTERN) if classify(row) == slot]
    if len(rows) != 1:
        return f"{slot}: expected one upload input, found {len(rows)}; attach it yourself."
    row = rows[0]
    if row["attached"] or row["shown"]:
        return f"{slot}: already uploaded ({(row['attached'] or [row['shown']])[0]}); left alone."
    if not Path(path).is_file():
        return f"{slot}: file not found."
    page.locator("input[type=file]").nth(row["index"]).set_input_files(str(path))
    return f"{slot}: attached {Path(path).name}"
