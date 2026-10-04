"""Read-only answer sheet: a per-page list of proposals with sources, required flags and character counts."""
import datetime
import hashlib
import html
import re
from pathlib import Path
from urllib.parse import urlsplit

import question_corpus

# Config
SCHEMA_VERSION = 1
MODE = "answer_sheet_only"
AUTHOR = "Yazad Madan"
SHEET_PREFIX = "answer_sheet_"
MAX_FIELDS = 500
MAX_HEADING = 80
MAX_SLUG = 60
KNOWN_STATUSES = {"prepared", "pending", "manual_only", "draft_needs_review"}
PORTAL_HOSTS = {"myworkdayjobs.com": "workday", "greenhouse.io": "greenhouse",
                "careers.marsh.com": "phenom", "careers.franklintempleton.com": "phenom"}
RESUME_LABEL = re.compile(r"\b(resume|cv)\b", re.I)
RESUME_FILE_NAME = "Yazad_Madan.docx"
TEXT_TYPES = {"text", "textarea", "email", "tel", "url", "search", "number"}
CSS = ("body{font:14px system-ui,sans-serif;margin:24px;color:#18273d}table{border-collapse:collapse;width:100%}"
       "th,td{border:1px solid #cad5e2;padding:6px 8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}"
       "th{background:#eef3fa}.pending td,.manual_only td{background:#fff9ee}.meta{color:#56677d;font-size:12px}")


def char_count(text):
    """UTF-16 code units as JavaScript counts them, with every newline counted as 2."""
    text = str(text or "").replace("\r\n", "\n")
    return len(text.encode("utf-16-le")) // 2 + text.count("\n")


def portal_for(host):
    host = (host or "").lower()
    return next((name for suffix, name in PORTAL_HOSTS.items() if host == suffix or host.endswith("." + suffix)), "generic")


def page_key(url, heading):
    parts = urlsplit(url or "")
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("The page URL must use HTTP or HTTPS.")
    text = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f]", " ", str(heading or ""))).strip().lower()[:MAX_HEADING]
    return f"{parts.hostname}{parts.path}#{text}"


def _excluded(entry):
    probe = {"label": entry.get("label", ""), "type": "" if entry.get("type") == "file" else entry.get("type", "")}
    return (bool(entry.get("blocked")) and not entry.get("forced_manual")) or question_corpus.is_protected(probe)


def _limit(entry):
    value = entry.get("char_limit", (entry.get("structure") or {}).get("maxlength"))
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _row(entry):
    label = re.sub(r"\s+", " ", str(entry.get("label") or "")).strip()[:question_corpus.MAX_LABEL]
    kind = str(entry.get("type") or "")[:30]
    proposal, source = str(entry.get("proposal") or ""), str(entry.get("source") or "").strip()
    status = entry.get("status") if entry.get("status") in KNOWN_STATUSES else "pending"
    if kind == "file":
        proposal, source, status = (RESUME_FILE_NAME, "Session resume copy", "prepared") if RESUME_LABEL.search(label) else ("", "", "pending")
    if entry.get("forced_manual") or status == "manual_only":
        proposal, source, status = "", "", "manual_only"
    elif status == "pending" or not proposal.strip() or not source:
        proposal, source, status = "", "", "pending"
    counted = bool(proposal) and kind in TEXT_TYPES
    options = entry.get("options")
    return {"label": label, "required": entry.get("required") is True, "type": kind, "proposal": proposal, "source": source,
            "status": status, "char_limit": _limit(entry), "char_count": char_count(proposal) if counted else None,
            "options_seen": len([o for o in options if o]) if isinstance(options, list) else 0}


def build_answer_sheet(session, fields, url="", heading="", now=None):
    if not isinstance(fields, list) or len(fields) > MAX_FIELDS or any(not isinstance(item, dict) for item in fields):
        raise ValueError("Fields must be a list of at most 500 objects.")
    host = urlsplit(url or "").hostname
    return {"schema_version": SCHEMA_VERSION, "application_id": session.get("application_id"), "company": session.get("company", ""),
            "role": session.get("role", ""), "portal": portal_for(host), "mode": MODE, "page_key": page_key(url, heading),
            "generated_at": now or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "resume": {"path": str(session.get("resume_path", "")), "sha256": session.get("resume_sha256", "")},
            "rows": [_row(item) for item in fields if not _excluded(item)]}


def render_html(sheet):
    esc = lambda value: html.escape(str(value), quote=True)
    head = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="author" content="{AUTHOR}">'
            f"<title>Answer sheet</title><style>{CSS}</style></head><body>")
    meta = (f'<h1>Answer sheet: {esc(sheet["company"])}, {esc(sheet["role"])}</h1><p class="meta">Portal {esc(sheet["portal"])}. '
            f'Page {esc(sheet["page_key"])}. Generated {esc(sheet["generated_at"])}. Resume file {esc(sheet["resume"]["path"])} '
            f'(SHA-256 {esc(sheet["resume"]["sha256"])}). Fill manually and submit yourself. Pending and manual rows have no proposed value.</p>')
    rows = "".join(
        f'<tr class="{esc(r["status"])}"><td>{esc(r["label"])}</td><td>{"Yes" if r["required"] else "No"}</td><td>{esc(r["type"])}</td>'
        f'<td>{esc(r["proposal"])}</td><td>{esc(r["source"])}</td><td>{esc(r["status"])}</td>'
        f'<td>{"" if r["char_count"] is None else r["char_count"]}{"" if r["char_limit"] is None else " of " + str(r["char_limit"])}</td></tr>'
        for r in sheet["rows"])
    table = ("<table><thead><tr><th>Question</th><th>Required</th><th>Type</th><th>Proposed answer</th><th>Source</th><th>Status</th>"
             f"<th>Characters</th></tr></thead><tbody>{rows}</tbody></table>")
    return head + meta + table + "</body></html>"


def sheet_paths(session_folder, key):
    slug = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")[:MAX_SLUG] or "page"
    stem = f"{SHEET_PREFIX}{slug}_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:8]}"
    folder = Path(session_folder).resolve()
    paths = folder / f"{stem}.json", folder / f"{stem}.html"
    if any(path.parent != folder for path in paths):
        raise ValueError("Answer sheet path escapes the session directory.")
    return paths


def save_sheet(session_folder, sheet, write):
    """Writes the JSON and HTML next to each other inside the session directory; returns (json_path, html_path, html)."""
    json_path, html_path = sheet_paths(session_folder, sheet["page_key"])
    markup = render_html(sheet)
    write(json_path, sheet)
    html_path.write_text(markup, encoding="utf-8")
    return json_path, html_path, markup
