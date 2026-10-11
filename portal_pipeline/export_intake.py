"""Intake for Inspect-only exports: validate for leaks, then draft a contract and a synthetic fixture.

Offline and read only. It never contacts a portal and never copies a raw export; keep exports in a private ignored folder.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

# Config
AUTHOR = "Yazad Madan"
SCHEMA_VERSION = 1
TOP_KEYS = {"schema_version", "host", "inspected_at", "portal", "portal_manual_reason", "protected_fields_omitted",
            "coverage", "fields", "handoff", "frame_reports"}
FRAME_KEYS = TOP_KEYS | {"frame_id", "frame"}
FIELD_KEYS = {"label", "type", "required", "disabled", "section", "adapter", "record", "manual_reason", "option_count",
              "dropdown_state", "structure"}
STRUCTURE_KEYS = {"tag", "name", "automation_id", "dom_id", "role", "controls", "popup", "maxlength"}
FORBIDDEN_KEYS = {"value", "proposal", "current", "answer", "password", "token", "cookie", "html", "options", "authorization"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]{0,2}){9,15}(?!\d)")
TOKEN = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")
MAX_STRING = 200
REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = (Path(__file__).resolve().parent / "data", Path(__file__).resolve().parent / "test-results")
TEXT_TYPES = {"text", "email", "tel", "url", "number", "search", "date", "password"}


def _walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")
    else:
        yield path, node


def validate(report):
    """Return {"errors": [...], "warnings": [...]}. Errors mean do not share or draft from this export."""
    errors, warnings = [], []
    if not isinstance(report, dict):
        return {"errors": ["Export is not a JSON object."], "warnings": []}
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version {report.get('schema_version')!r}.")
    if not isinstance(report.get("host"), str) or not report.get("host"):
        errors.append("Missing host.")
    elif re.fullmatch(r"[\d.]+|localhost|.*\.local", report["host"]):
        warnings.append("Host is a loopback, private, or IP address, so this may be a fixture and not a real portal.")
    if not isinstance(report.get("fields"), list):
        errors.append("Missing fields list.")
        return {"errors": errors, "warnings": warnings}

    def check_report(item, label, allowed):
        for key in item:
            if key not in allowed:
                warnings.append(f"{label}: unknown key {key!r}.")
        for index, field in enumerate(item.get("fields", [])):
            where = f"{label}.fields[{index}]"
            if not isinstance(field, dict):
                errors.append(f"{where}: not an object.")
                continue
            for key in field:
                if key not in FIELD_KEYS:
                    warnings.append(f"{where}: unknown key {key!r}.")
            for key in field.get("structure", {}) if isinstance(field.get("structure"), dict) else []:
                if key not in STRUCTURE_KEYS:
                    warnings.append(f"{where}.structure: unknown key {key!r}.")
            if not isinstance(field.get("type"), str):
                errors.append(f"{where}: missing type.")

    check_report(report, "report", TOP_KEYS)
    frames = report.get("frame_reports", [])
    if not isinstance(frames, list):
        errors.append("frame_reports is not a list.")
        frames = []
    for index, frame in enumerate(frames):
        if isinstance(frame, dict) and isinstance(frame.get("fields"), list):
            check_report(frame, f"frame_reports[{index}]", FRAME_KEYS)
        else:
            errors.append(f"frame_reports[{index}]: malformed.")

    for path, value in _walk(report):
        key = path.rsplit(".", 1)[-1].split("[")[0].lower()
        if key in FORBIDDEN_KEYS:
            errors.append(f"{path}: forbidden key {key!r} (entered values, answers, and secrets must not be exported).")
        if isinstance(value, str):
            if EMAIL.search(value):
                errors.append(f"{path}: looks like an email address.")
            if PHONE.search(value):
                errors.append(f"{path}: looks like a phone number.")
            for match in TOKEN.findall(value):
                secret = re.fullmatch(r"[0-9a-fA-F]{32,}", match) or (re.search(r"\d", match) and re.search(r"[a-z]", match) and re.search(r"[A-Z]", match))
                (errors if secret else warnings).append(f"{path}: looks like a {'token' if secret else 'long identifier'}.")
            if "?" in value and re.search(r"https?://", value):
                errors.append(f"{path}: URL with a query string.")
            if len(value) > MAX_STRING:
                warnings.append(f"{path}: unusually long string ({len(value)} characters).")
    if report.get("fields") == [] and not frames:
        warnings.append("No fields recorded. This may be a posting, login page, or unsupported form.")
    return {"errors": errors, "warnings": warnings}


def _reports(report):
    yield "top", report
    for frame in report.get("frame_reports", []) or []:
        yield f"frame {frame.get('frame_id')}", frame


def draft_contract(reports, portal, host_note="UNVERIFIED"):
    """Markdown contract skeleton following docs/contracts/CONTRACT_TEMPLATE.md. Unknowns stay UNVERIFIED."""
    lines = ["---", f"author: {AUTHOR}", "---", "", f"# Portal contract: {portal} (DRAFT)", "",
             "Generated from Inspect-only exports. Review every line against your visit notes before committing. "
             "Unknowns are marked UNVERIFIED.", "", "## Portal and hosts", ""]
    hosts = sorted({report.get("host", "") for report in reports})
    lines += [f"Hostnames seen: {', '.join(hosts) or 'none'}. Host pattern: {host_note}.", "", "## Evidence", "",
              f"{len(reports)} export(s). Export dates: {', '.join(sorted(r.get('inspected_at', '?')[:10] for r in reports))}. "
              "Logged in: UNVERIFIED.", "", "## Page sequence", "",
              "| Page key | Heading text | Controls count | Required count | Upload controls | Navigation labels | Final-review markers |",
              "|---|---|---|---|---|---|---|"]
    families, gates, frames = {}, [], 0
    for number, report in enumerate(reports, 1):
        for scope, item in _reports(report):
            fields = item.get("fields", [])
            uploads = sum(1 for f in fields if f.get("type") == "file")
            lines.append(f"| page {number} {scope} | UNVERIFIED | {len(fields)} | {sum(1 for f in fields if f.get('required'))} | {uploads} | UNVERIFIED | UNVERIFIED |")
            frames += scope != "top"
            for field in fields:
                kind = field.get("adapter") or field.get("type", "unknown")
                families.setdefault(kind, field.get("label") or "unlabelled")
            reasons = (item.get("coverage") or {}).get("reason_codes") or []
            gates += [f"page {number} {scope}: {reason}" for reason in reasons]
    lines += ["", "## Control families", ""]
    lines += [f"- {kind}: example label \"{label}\". Read and write behavior UNVERIFIED." for kind, label in sorted(families.items())] or ["- None recorded."]
    lines += ["", "## Human gates seen", ""]
    lines += [f"- Coverage note {gate}." for gate in gates] or ["- None recorded in exports. Login, MFA, and CAPTCHA placement UNVERIFIED."]
    lines += ["", "## Repeated sections", "", "UNVERIFIED. Exports do not capture add-row behavior.", "", "## Mode", "",
              "`answer_sheet_only` until a reviewed contract supports `fill`." + (f" {frames} frame page(s) were inspected." if frames else ""),
              "", "## Open questions", "", "- Apply host, final review markers, upload behavior, retention after navigation. All UNVERIFIED.", ""]
    return "\n".join(lines)


def draft_fixture(report, keep_labels=False):
    """Synthetic HTML for one export page: neutral labels and invented values only."""
    esc = html.escape
    body = []
    for index, field in enumerate(report.get("fields", []), 1):
        kind = field.get("type", "text")
        label = esc(field.get("label") or f"Field {index}") if keep_labels else f"Field {index}"
        structure = field.get("structure") or {}
        ident = f"f{index}"
        required = " required" if field.get("required") else ""
        disabled = " disabled" if field.get("disabled") else ""
        count = max(int(field.get("option_count") or 0), 0)
        if kind == "textarea":
            maxlength = f' maxlength="{structure["maxlength"]}"' if structure.get("maxlength") else ""
            body.append(f'<label>{label}<textarea id="{ident}" name="{ident}"{maxlength}{required}{disabled}></textarea></label>')
        elif kind in ("select", "select-one"):
            options = "".join(f'<option value="{i}">Option {i}</option>' for i in range(1, count + 1))
            body.append(f'<label>{label}<select id="{ident}" name="{ident}"{required}{disabled}><option value="">Select</option>{options}</select></label>')
        elif kind == "radio":
            radios = "".join(f'<label><input type="radio" name="{ident}" value="Option {i}"{disabled}> Option {i}</label>' for i in range(1, max(count, 2) + 1))
            body.append(f'<fieldset><legend>{label}</legend>{radios}</fieldset>')
        elif kind == "checkbox":
            body.append(f'<label><input type="checkbox" id="{ident}" name="{ident}"{required}{disabled}> {label}</label>')
        elif kind == "file":
            body.append(f'<label>{label}<input type="file" id="{ident}" name="{ident}"{disabled}></label>')
        elif kind == "combobox":
            options = "".join(f'<div role="option">Option {i}</div>' for i in range(1, count + 1))
            body.append(f'<div id="{ident}" role="combobox" tabindex="0" aria-label="{label}" aria-controls="{ident}-list" aria-expanded="false" aria-haspopup="listbox" aria-valuetext="">Select</div>'
                        f'<div id="{ident}-list" role="listbox" style="display:none">{options}</div>')
        else:
            safe = kind if kind in TEXT_TYPES - {"password"} else "text"
            maxlength = f' maxlength="{structure["maxlength"]}"' if structure.get("maxlength") else ""
            body.append(f'<label>{label}<input type="{safe}" id="{ident}" name="{ident}"{maxlength}{required}{disabled}></label>')
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<meta name="author" content="{AUTHOR}"><title>Synthetic fixture</title></head><body>\n<h1>Synthetic page</h1>\n<form novalidate>\n'
            + "\n".join(body) + '\n<button type="button">Next</button>\n</form>\n</body></html>\n')


def out_dir_allowed(out_dir):
    """Drafts may go outside the repository or into an ignored folder; never into a tracked path."""
    resolved = Path(out_dir).resolve()
    inside_repo = resolved == REPO_ROOT or REPO_ROOT in resolved.parents
    return not inside_repo or any(resolved == ignored or ignored in resolved.parents for ignored in IGNORED_DIRS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="Check exports for leaks and schema problems.")
    check.add_argument("exports", nargs="+", type=Path)
    draft = sub.add_parser("draft", help="Write a contract draft and fixtures. Refuses exports that fail validation.")
    draft.add_argument("exports", nargs="+", type=Path)
    draft.add_argument("--portal", required=True)
    draft.add_argument("--out-dir", required=True, type=Path)
    draft.add_argument("--keep-labels", action="store_true", help="Reuse real labels in fixtures. Review them first.")
    args = parser.parse_args(argv)

    reports, failed = [], False
    for path in args.exports:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"{path.name}: cannot read ({error})")
            failed = True
            continue
        result = validate(report)
        for message in result["errors"]:
            print(f"{path.name}: ERROR {message}")
        for message in result["warnings"]:
            print(f"{path.name}: warning {message}")
        failed = failed or bool(result["errors"])
        reports.append(report)
    if failed:
        print("Not safe to share or draft from. Fix or recapture the flagged exports.")
        return 1
    if args.command == "validate":
        print(f"{len(reports)} export(s) passed.")
        return 0
    if not out_dir_allowed(args.out_dir):
        print(f"Refusing to write drafts into a tracked repository path. Use a folder outside the repository or under {IGNORED_DIRS[0]}.")
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", args.portal.lower()).strip("_") or "portal"
    (args.out_dir / f"{slug.upper()}_CONTRACT_DRAFT.md").write_text(draft_contract(reports, args.portal), encoding="utf-8")
    for number, report in enumerate(reports, 1):
        (args.out_dir / f"{slug}_page_{number}.html").write_text(draft_fixture(report, args.keep_labels), encoding="utf-8")
    print(f"Wrote contract draft and {len(reports)} fixture(s) to {args.out_dir}. Review before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
