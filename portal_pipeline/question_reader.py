"""Browser-free question reader: turns a saved posting API response into an export-shaped report.

Offline only. It reads a local JSON file, has no network code, and never contacts a portal. The response shapes below follow the
published Greenhouse Job Board API from memory and are UNVERIFIED against a live response. Save a response yourself, then run it here.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Config
SCHEMA_VERSION = 1
MAX_BYTES = 2_000_000
MAX_QUESTIONS = 300
MAX_LABEL = 200
SUPPORTED = ("greenhouse",)
HOSTS = {"greenhouse": "boards-api.greenhouse.io"}
# Greenhouse field types mapped to the type names an Inspect export uses.
GREENHOUSE_TYPES = {"input_text": "text", "textarea": "textarea", "input_file": "file",
                    "multi_value_single_select": "select-one", "multi_value_multi_select": "select-multiple"}
SKIPPED_TYPES = {"input_hidden"}
# Question blocks that hold voluntary demographic or compliance answers are counted and never listed.
PROTECTED_BLOCKS = ("demographic_questions", "compliance")
LISTED_BLOCKS = ("questions", "location_questions")
TAGS = re.compile(r"<[^>]*>")


def _clean(text):
    text = TAGS.sub(" ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _structure(name, maxlength=None):
    return {"tag": "input", "name": name, "automation_id": "", "dom_id": "", "role": "", "controls": "", "popup": "", "maxlength": maxlength}


def _greenhouse_fields(payload):
    fields, omitted, notes = [], 0, []
    for block in PROTECTED_BLOCKS:
        entries = payload.get(block)
        if isinstance(entries, list):
            omitted += len(entries)
        elif isinstance(entries, dict):
            omitted += sum(len(v) for v in entries.values() if isinstance(v, list)) or 1
    for block in LISTED_BLOCKS:
        entries = payload.get(block)
        if entries is None:
            continue
        if not isinstance(entries, list):
            notes.append(f"{block} is not a list and was ignored.")
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("fields"), list):
                notes.append(f"A {block} entry has no fields list and was ignored.")
                continue
            label = _clean(entry.get("label"))
            if len(label) > MAX_LABEL:
                label = label[:MAX_LABEL]
                notes.append("A label was truncated.")
            for field in entry["fields"]:
                if not isinstance(field, dict):
                    continue
                kind = field.get("type")
                if kind in SKIPPED_TYPES:
                    continue
                mapped = GREENHOUSE_TYPES.get(kind)
                values = field.get("values") if isinstance(field.get("values"), list) else []
                fields.append({
                    "label": label, "type": mapped or "text", "required": bool(entry.get("required")), "disabled": False,
                    "section": "posting_questions" if block == "questions" else "location", "adapter": None, "record": None,
                    "manual_reason": "" if mapped and mapped != "select-multiple" else
                                     ("Multiple-choice questions need manual review." if mapped else f"Unrecognized field type {_clean(kind)!r}; treated as text."),
                    "option_count": len(values), "dropdown_state": None,
                    "structure": _structure(_clean(field.get("name")))})
                if len(fields) >= MAX_QUESTIONS:
                    notes.append("Question limit reached; the rest were ignored.")
                    return fields, omitted, notes
    return fields, omitted, notes


def read_questions(payload, portal):
    """Return an export-shaped report from a parsed posting response. Raises ValueError for unsupported input."""
    if portal not in SUPPORTED:
        raise ValueError(f"Unsupported portal {portal!r}. Supported: {', '.join(SUPPORTED)}.")
    if not isinstance(payload, dict):
        raise ValueError("The response is not a JSON object.")
    fields, omitted, notes = _greenhouse_fields(payload)
    return {"schema_version": SCHEMA_VERSION, "host": HOSTS[portal], "inspected_at": "1970-01-01T00:00:00.000Z",
            "portal": portal, "portal_manual_reason": " ".join(notes), "protected_fields_omitted": omitted,
            "coverage": {"scope": "posting_api_response", "visible_iframes": 0, "visible_open_shadow_hosts": 0,
                         "unsupported_spinbuttons": 0, "reason_codes": ["posting_api_not_live_dom"]},
            "fields": fields}


def read_file(path, portal):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("The response file is too large.")
    return read_questions(json.loads(path.read_text(encoding="utf-8")), portal)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response", type=Path, help="Saved posting API response (JSON).")
    parser.add_argument("--portal", required=True, choices=SUPPORTED)
    parser.add_argument("--out", type=Path, help="Write the report here instead of stdout.")
    args = parser.parse_args(argv)
    try:
        report = read_file(args.response, args.portal)
    except (OSError, ValueError) as error:
        print(f"Cannot read questions: {error}", file=sys.stderr)
        return 1
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
