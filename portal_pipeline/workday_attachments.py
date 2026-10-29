"""Author: Yazad Madan. Verify Workday attachment names and rounded binary KB sizes."""
import hashlib
import mimetypes
import re
import time
from decimal import Decimal
from pathlib import Path

# Config
SLOTS = ("resume", "cover")
CHECK_KEY = "attachment_check"
FAILURE_KEY = "failure_telemetry"
ITEM_SELECTOR = '[data-automation-id="file-upload-item"]'
INPUT_SELECTOR = 'input[type="file"]'
DELETE_SELECTOR = '[data-automation-id="delete-file"]'
KB_BASE = Decimal(1024)
ROUNDING_HALF = Decimal("0.005")
SIZE_PATTERN = re.compile(r"(?<![\d.])(\d+\.\d{2})\s*KB\b", re.I)
ATTACHMENT_STEP = re.compile(r"\b(my experience|resume|attachments?)\b", re.I)
CONFIRM_SECONDS = 15
POLL_SECONDS = 0.1
READ_JS = r"""() => {
  const itemSelector = '[data-automation-id="file-upload-item"]';
  const inputSelector = 'input[type="file"]';
  const deleteSelector = '[data-automation-id="delete-file"]';
  const visible = node => !node.closest('[hidden],[aria-hidden="true"]') && node.getClientRects().length > 0;
  const inputs = [...document.querySelectorAll(inputSelector)];
  const items = [...document.querySelectorAll(itemSelector)];
  const label = node => {
    const clone = node.cloneNode(true);
    clone.querySelectorAll(itemSelector + ',input,button,[role="button"],script,style').forEach(child => child.remove());
    return [node.getAttribute('aria-label'), clone.textContent].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  };
  const owner = node => {
    let fallback = null;
    for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
      if (parent.querySelectorAll(inputSelector).length > 1) break;
      const identity = parent.getAttribute('data-automation-id') || '';
      const text = label(parent);
      if (/^formField-(coverLetter|attachments)$/i.test(identity) || /\bcover\s*letter\b/i.test(text) || /^attachments\b/i.test(text)) return {slot: 'cover', node: parent};
      if (/^formField-resume$/i.test(identity) || /\b(resume|cv)\b/i.test(text)) return {slot: 'resume', node: parent};
      if (!fallback && /\bupload a file\b/i.test(text)) fallback = {slot: 'resume', node: parent};
    }
    return fallback;
  };
  const slots = {resume: {inputs: [], items: []}, cover: {inputs: [], items: []}};
  const unknown_inputs = [];
  inputs.forEach((input, index) => {
    const found = owner(input);
    if (found) slots[found.slot].inputs.push(index);
    else unknown_inputs.push(index);
  });
  const listed = [];
  items.forEach((item, index) => {
    if (!visible(item)) return;
    const clone = item.cloneNode(true);
    clone.querySelectorAll(deleteSelector).forEach(child => child.remove());
    const text = (item.innerText || clone.textContent || '').replace(/\s+/g, ' ').trim();
    const named = item.querySelector('[data-automation-id="fileName"],[data-automation-id="file-upload-file-name"]');
    const name = named ? named.textContent.trim() : (text.match(/^(.+?\.(?:pdf|docx?|rtf|txt|odt))(?=\s|\d+\.\d{2}\s*KB|$)/i)?.[1] || '');
    const record = {index, name, text, identity_text: (item.textContent || '').replace(/\s+/g, ' ').trim()};
    listed.push(record);
    const found = owner(item);
    if (found) slots[found.slot].items.push(record);
  });
  return {slots, items: listed, unknown_inputs};
}"""
DELETE_JS = r"""([item, index, expected]) => {
  BOUNDARY();
  if (!item || !item.isConnected || item !== document.querySelectorAll('[data-automation-id="file-upload-item"]')[index]
      || (item.textContent || '').replace(/\s+/g, ' ').trim() !== expected) throw new Error('Attachment identity changed.');
  const buttons = [...item.querySelectorAll('[data-automation-id="delete-file"]')];
  const button = buttons[0];
  if (buttons.length !== 1 || !button.isConnected || button.disabled || button.getAttribute('aria-disabled') === 'true'
      || button.closest('[hidden],[aria-hidden="true"]') || !button.getClientRects().length
      || button.type === 'submit' || button.type === 'image'
      || !button.matches('button,[role="button"],input[type="button"]')) throw new Error('Attachment deletion is ambiguous.');
  BOUNDARY();
  button.click();
}"""
INPUT_UNAVAILABLE_JS = """(node, slot) => {
  const state = (READ)().slots[slot];
  return !node.isConnected || node.disabled || node.getAttribute('aria-disabled') === 'true'
    || state.items.length > 1
    || state.inputs.length !== 1 || document.querySelectorAll('input[type="file"]')[state.inputs[0]] !== node;
}""".replace("READ", READ_JS)


class AttachmentMismatch(RuntimeError):
    pass


def expected_files(args):
    manifest = getattr(args, "attachment_manifest", None)
    values = manifest if manifest is not None else {slot: getattr(args, slot, None) for slot in SLOTS}
    return {slot: Path(values[slot]) if values.get(slot) else None for slot in SLOTS}


def compare(path, items):
    expected_bytes = path.stat().st_size if path and path.is_file() else None
    result = {"expected_bytes": expected_bytes, "seen_kb": None, "status": "missing"}
    if path is None:
        result["status"] = "unexpected" if items else "not_requested"
        return result
    if len(items) != 1:
        result["status"] = "ambiguous" if items else "missing"
        return result
    size = SIZE_PATTERN.search(items[0].get("text", ""))
    result["seen_kb"] = size.group(1) if size else None
    if expected_bytes is None:
        result["status"] = "source_missing"
    elif items[0].get("name") != path.name:
        result["status"] = "name_mismatch"
    elif not size:
        result["status"] = "size_missing"
    else:
        shown = Decimal(size.group(1))
        actual = Decimal(expected_bytes) / KB_BASE
        result["status"] = "matched" if shown - ROUNDING_HALF <= actual < shown + ROUNDING_HALF else "size_mismatch"
    return result


def mismatch_message(failure):
    seen = f"{failure['seen_kb']} KB" if failure.get("seen_kb") is not None else "missing/unknown"
    return f"Attachment mismatch: {failure['file']}, expected {failure['expected_bytes']} bytes, seen {seen} ({failure['status']})."


def stop(report, event, slot, path, result, phase):
    report.data.setdefault(CHECK_KEY, {})[slot] = result
    if event is not None:
        event.setdefault(CHECK_KEY, {})[slot] = dict(result)
        for record in event.get("uploads", []):
            if record.get("subtype") == slot:
                record.update(status="unconfirmed", reason="attachment_mismatch", **{key: result[key] for key in ("expected_bytes", "seen_kb")})
    name = path.name if path else slot
    failure = {"kind": "attachment_mismatch", "slot": slot, "file": name, "phase": phase, **result}
    report.data.setdefault(FAILURE_KEY, []).append(failure)
    raise AttachmentMismatch(mismatch_message(failure))


def verify(page, args, report, event=None, review=False, guard=None, boundary_js=None):
    paths = expected_files(args)
    phase = "review" if review else "upload"
    checks = report.data.setdefault(CHECK_KEY, {})
    for slot, path in paths.items():
        checks.setdefault(slot, {"expected_bytes": path.stat().st_size if path and path.is_file() else None,
                                 "seen_kb": None, "status": "not_checked" if path else "not_requested"})
        checks[slot]["expected_bytes"] = path.stat().st_size if path and path.is_file() else None
    if review:
        names = [path.name for path in paths.values() if path]
        report.data["review_attachments"] = {"expected": names, "found": [], "missing": names,
                                              "unexpected": [], "ok": False}
    try:
        snapshot = page.evaluate(READ_JS)
    except Exception:
        stop(report, event, "resume", paths["resume"], {**checks["resume"], "status": "unreadable"}, phase)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("slots"), dict):
        stop(report, event, "resume", paths["resume"], {**checks["resume"], "status": "unreadable"}, phase)
    slots = snapshot["slots"]
    # KeyBank labels its only Resume/CV control "Attachments", which reads as the cover slot.
    if paths["resume"] and not paths["cover"] and not slots["resume"]["inputs"] and slots["cover"]["inputs"]:
        slots["resume"], slots["cover"] = slots["cover"], {"inputs": [], "items": []}
    present = any(state["inputs"] or state["items"] for state in snapshot["slots"].values())
    if not review and not present and not snapshot["unknown_inputs"] and not ATTACHMENT_STEP.search(event["title"]):
        return
    if review:
        expected = [path.name for path in paths.values() if path]
        found = [item["name"] for item in snapshot["items"]]
        report.data["review_attachments"] = {"expected": expected, "found": found,
            "missing": [name for name in expected if name not in found],
            "unexpected": [name for name in found if name not in expected], "ok": False}
    for slot, path in paths.items():
        state = snapshot["slots"][slot]
        items = [item for item in snapshot["items"] if path and item["name"] == path.name] if review else state["items"]
        result = compare(path, items)
        checks[slot] = result
        if event is not None:
            event.setdefault(CHECK_KEY, {})[slot] = dict(result)
        payload = path.read_bytes() if path and path.is_file() else None
        digest = hashlib.sha256(payload).hexdigest() if payload is not None else None
        manifest = getattr(args, "attachment_manifest", None) or {}
        if path and slot == "resume" and manifest.get("resume_sha256") and digest != manifest["resume_sha256"]:
            stop(report, event, slot, path, {**result, "status": "sha256_mismatch"}, phase)
        if not review and path:
            record = {"file": path.name, "sha256": None, "status": "unconfirmed", "subtype": slot,
                      "reason": "attachment_mismatch", "expected_bytes": result["expected_bytes"], "seen_kb": result["seen_kb"]}
            event["uploads"].append(record)
            record["sha256"] = digest
            if result["status"] != "matched":
                if not path.is_file() or len(state["inputs"]) != 1 or len(items) > 1:
                    stop(report, event, slot, path, result, phase)
                try:
                    guard()
                    if items:
                        item = page.locator(ITEM_SELECTOR).nth(items[0]["index"]).element_handle()
                        page.evaluate(DELETE_JS.replace("BOUNDARY()", "(" + boundary_js + ")()"),
                                      [item, items[0]["index"], items[0].get("identity_text", items[0]["text"])])
                        deadline = time.monotonic() + CONFIRM_SECONDS
                        while True:
                            guard()
                            live = page.evaluate(READ_JS)["slots"][slot]
                            if not live["items"] and len(live["inputs"]) == 1:
                                break
                            if time.monotonic() >= deadline:
                                stop(report, event, slot, path, {**result, "status": "delete_unconfirmed"}, phase)
                            time.sleep(POLL_SECONDS)
                    live = page.evaluate(READ_JS)["slots"][slot]
                    if live["items"] or len(live["inputs"]) != 1:
                        stop(report, event, slot, path, {**result, "status": "input_ambiguous"}, phase)
                    target = page.locator(INPUT_SELECTOR).nth(live["inputs"][0]).element_handle()
                    if target is None or target.evaluate(INPUT_UNAVAILABLE_JS, slot):
                        stop(report, event, slot, path, {**result, "status": "input_unavailable"}, phase)
                    guard()
                    target.set_input_files({"name": path.name, "mimeType": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                                            "buffer": payload})
                    deadline = time.monotonic() + CONFIRM_SECONDS
                    while True:
                        guard()
                        snapshot = page.evaluate(READ_JS)
                        result = compare(path, snapshot["slots"][slot]["items"])
                        if result["status"] == "matched" or time.monotonic() >= deadline:
                            break
                        time.sleep(POLL_SECONDS)
                except AttachmentMismatch:
                    raise
                except Exception:
                    stop(report, event, slot, path, {**result, "status": "replacement_failed"}, phase)
                checks[slot] = result
                event[CHECK_KEY][slot] = dict(result)
            record.update(expected_bytes=result["expected_bytes"], seen_kb=result["seen_kb"])
            if result["status"] == "matched":
                record.update(status="verified", reason="attachment_verified")
        if result["status"] not in {"matched", "not_requested"}:
            stop(report, event, slot, path, result, phase)
    if not review:
        owned = {item["index"] for state in snapshot["slots"].values() for item in state["items"]}
        if any(item["index"] not in owned for item in snapshot["items"]):
            stop(report, event, "resume", paths["resume"], {**checks["resume"], "status": "unexpected"}, phase)
    if review:
        result = report.data["review_attachments"]
        if result["unexpected"] or len(snapshot["items"]) != len(result["expected"]):
            slot = "cover" if paths["cover"] is None else "resume"
            stop(report, event, slot, paths[slot], {**checks[slot], "status": "unexpected"}, phase)
        result.update(ok=True, attachment_check={slot: dict(value) for slot, value in checks.items()})
