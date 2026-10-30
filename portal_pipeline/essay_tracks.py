"""Author: Yazad Madan. Conservative essay tracks and user-approved local templates."""
import json
import re
from pathlib import Path
from string import Formatter
from urllib.parse import unquote, urlsplit

from answer_memory import MAX_ANSWER
from shared_storage import atomic_json, file_lock

# Config
TEMPLATE_FILENAME = "essay_templates.json"
SCHEMA_VERSION = 1
MAX_JOB_TITLE = 300
MAX_PAGE_SNIPPET = 1500
MAX_STORE_BYTES = 256 * 1024
FAMILIES = ("alm", "capital", "fpa", "model_risk", "quant", "treasury_ops")
KINDS = ("motivation", "about_yourself", "good_fit")
TITLE_KEY, SNIPPET_KEY = "job_title", "page_snippet"
FAMILY_KEY, KIND_KEY, TEXT_KEY, APPROVED_KEY = "family", "kind", "text", "approved"
TEMPLATES_KEY, SCHEMA_KEY, AUTHOR_KEY = "templates", "schema_version", "author"
PLACEHOLDERS = {"company", "role"}
FREE_TEXT_TYPES = {"text", "textarea", "search"}
FAMILY_PATTERNS = {
    "alm": r"\balm\b|\birrbb\b|\basset[\s/-]+liability\b|\bliquidity (?:risk|management)\b|\bbalance sheet management\b",
    "capital": r"\bbasel(?:\s+(?:iii?|iv|[234]))?\b|\b(?:regulatory|economic) capital\b|\bcapital (?:risk|adequacy|management|planning)\b",
    "fpa": r"\bfp\s*&\s*a\b|\bfp[ /-]?a\b|\bfinancial planning(?: and analysis)?\b",
    "model_risk": r"\bmodel (?:risk|validation|governance)\b|\bvalidation of models\b",
    "quant": r"\bquant(?:itative)? (?:research\w*|analyst|analysis|trading|developer|strateg\w*)\b|\bsystematic (?:research|trading|strateg\w*)\b|\binvestment research\b",
    "treasury_ops": r"\btreasury (?:operations?|services)\b|\bcash management\b|\bpayments? operations?\b",
}
KIND_PATTERNS = {
    "motivation": r"\bwhy\b.{0,100}\b(?:interest\w*|join|work|apply\w*|company|role|position)\b|\b(?:what|tell)\b.{0,60}\b(?:interest\w*|attract\w*|motivat\w*)\b",
    "about_yourself": r"\btell (?:us|me) (?:a (?:bit|little) )?about yourself\b|\bintroduce yourself\b",
    "good_fit": r"\b(?:good|great|strong|ideal|suitable|best) (?:fit|candidate)\b|\bwhy\b.{0,60}\b(?:hire|choose) you\b|\bwhat\b.{0,60}\bqualifies you\b",
}


def validate_context(body):
    for key, limit in ((TITLE_KEY, MAX_JOB_TITLE), (SNIPPET_KEY, MAX_PAGE_SNIPPET)):
        value = body.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("Essay context must be bounded strings.")


def classify_job(job_title="", page_snippet="", url=""):
    """Require one family signal; company names and URL queries are not job evidence."""
    validate_context({TITLE_KEY: job_title, SNIPPET_KEY: page_snippet})
    context = job_title + " " + page_snippet
    matches = {family for family, pattern in FAMILY_PATTERNS.items() if re.search(pattern, context, re.I)}
    if not matches:
        try:
            path = unquote(urlsplit(url).path).replace("_", " ").replace("-", " ")
        except ValueError:
            return None
        matches = {family for family, pattern in FAMILY_PATTERNS.items() if re.search(pattern, path, re.I)}
    return next(iter(matches)) if len(matches) == 1 else None


def question_kind(label):
    matches = [kind for kind, pattern in KIND_PATTERNS.items() if re.search(pattern, label, re.I)]
    return matches[0] if len(matches) == 1 else None


def validate_template(text):
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_ANSWER:
        raise ValueError("Template must be a nonempty bounded string.")
    if "\u2014" in text or "--" in text:
        raise ValueError("Rewrite dash punctuation before saving a template.")
    for _, name, spec, conversion in Formatter().parse(text):
        if name is not None and (name not in PLACEHOLDERS or spec or conversion):
            raise ValueError("Only {company} and {role} placeholders are allowed.")


def render_template(text, company="", role=""):
    validate_template(text)
    values = {"company": company.strip(), "role": role.strip()}
    for _, name, _, _ in Formatter().parse(text):
        if name is not None and not values[name]:
            return None
    answer = text.format(**values).strip()
    return answer if len(answer) <= MAX_ANSWER else None


def load_templates(data):
    path = Path(data) / TEMPLATE_FILENAME
    if not path.exists():
        return {SCHEMA_KEY: SCHEMA_VERSION, AUTHOR_KEY: "Yazad Madan", TEMPLATES_KEY: {}}
    with path.open("rb") as handle:
        raw = handle.read(MAX_STORE_BYTES + 1)
    if len(raw) > MAX_STORE_BYTES:
        raise ValueError("Essay template store is too large.")
    store = json.loads(raw)
    if (not isinstance(store, dict) or store.get(SCHEMA_KEY) != SCHEMA_VERSION
            or not isinstance(store.get(TEMPLATES_KEY), dict)):
        raise ValueError("Unsupported essay template store.")
    return store


def update_template(data, family, kind, text=None, approved=False):
    """Adding or replacing text requires explicit approval; None removes one template."""
    if family not in FAMILIES or kind not in KINDS:
        raise ValueError("Select a known family and question kind.")
    if text is not None:
        validate_template(text)
        if approved is not True:
            raise ValueError("Explicit approval is required to store template text.")
    path = Path(data) / TEMPLATE_FILENAME
    with file_lock(path):
        store = load_templates(data)
        rows = store[TEMPLATES_KEY].setdefault(family, {})
        if not isinstance(rows, dict):
            raise ValueError("Invalid family template records.")
        if text is None:
            rows.pop(kind, None)
            if not rows:
                store[TEMPLATES_KEY].pop(family, None)
        else:
            rows[kind] = {TEXT_KEY: text, APPROVED_KEY: True}
        store[AUTHOR_KEY] = "Yazad Madan"
        atomic_json(path, store)


def answer(data, body):
    """Called only after the assist service's blocked-label and protection checks."""
    if body.get("options") or body.get("type", "text") not in FREE_TEXT_TYPES:
        return None
    family = classify_job(body.get(TITLE_KEY, ""), body.get(SNIPPET_KEY, ""), body.get("url", ""))
    kind = question_kind(body["label"])
    if not family or not kind:
        return None
    try:
        rows = load_templates(data)[TEMPLATES_KEY].get(family, {})
        row = rows.get(kind) if isinstance(rows, dict) else None
        if not isinstance(row, dict) or row.get(APPROVED_KEY) is not True:
            return None
        value = render_template(row.get(TEXT_KEY), body.get("company_hint", ""), body.get(TITLE_KEY, ""))
    except (OSError, ValueError, TypeError):
        return None
    if not value:
        return None
    return {"status": "draft", "source": "essay_templates", "answer": value, "candidates": [value],
            FAMILY_KEY: family, KIND_KEY: kind}
