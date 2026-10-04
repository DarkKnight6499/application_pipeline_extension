"""Local log of question wording so classifier rules grow from real portal language after review."""
import json
import re
from datetime import date
from pathlib import Path

# Config
CORPUS_FILENAME = "question_corpus.json"
SCHEMA_VERSION = 1
MAX_LABEL = 300
MAX_OPTIONS = 50
MAX_OPTION = 200
PROTECTED_TERMS = re.compile(r"\b(password|passcode|captcha|one.?time|otp|ssn|social security|credit card|bank account|routing number|signature|attest|certify|certification of|consent|agree|accept terms|privacy policy|declaration|gender|race|ethnicity|veteran|disability|sexual orientation)\b", re.I)
PROTECTED_TYPES = {"password", "file", "signature"}


def normalize_label(value):
    text = str(value or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#\s-]+", " ", text)).strip()


def empty_corpus():
    return {"schema_version": SCHEMA_VERSION, "questions": {}}


def corpus_path(data_dir):
    return Path(data_dir).resolve() / CORPUS_FILENAME


def load_corpus(data_dir):
    path = corpus_path(data_dir)
    if not path.is_file():
        return empty_corpus()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("questions"), dict):
        raise ValueError("Question corpus has an unsupported schema.")
    return data


def _option_labels(options):
    labels = []
    for option in options if isinstance(options, list) else []:
        label = option.get("label") if isinstance(option, dict) else option
        if isinstance(label, str) and label.strip():
            labels.append(label.strip()[:MAX_OPTION])
    return labels[:MAX_OPTIONS]


def is_protected(entry):
    return (bool(entry.get("protected")) or str(entry.get("type", "")).lower() in PROTECTED_TYPES
            or bool(PROTECTED_TERMS.search(str(entry.get("label", "")))))


def append_question(data, entry, now=None):
    """Adds or counts one question; returns False when skipped as protected or empty."""
    label = str(entry.get("label") or "").strip()[:MAX_LABEL]
    key = normalize_label(label)
    if not key or is_protected(entry):
        return False
    today = now or date.today().isoformat()
    record = data["questions"].get(key)
    if record:
        record["count"] += 1
        record["last_seen"] = today
        if entry.get("classified_as") and not record["classified_as"]:
            record["classified_as"] = str(entry["classified_as"])
        return True
    data["questions"][key] = {"label": label, "portal": str(entry.get("portal") or "")[:60], "type": str(entry.get("type") or "")[:30],
                              "options": _option_labels(entry.get("options")), "first_seen": today, "last_seen": today, "count": 1,
                              "classified_as": str(entry["classified_as"]) if entry.get("classified_as") else None, "reviewed": False}
    return True


def log_question(data_dir, entries, write):
    """Appends entries and saves via the supplied atomic writer; returns (logged, skipped)."""
    entries = [entries] if isinstance(entries, dict) else entries
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise ValueError("Questions must be a list of objects.")
    data = load_corpus(data_dir)
    logged = sum(append_question(data, item) for item in entries)
    if logged:
        write(corpus_path(data_dir), data)
    return logged, len(entries) - logged


def promote(data, label):
    """Returns a test case line for review; never edits the corpus or any test file."""
    record = data["questions"].get(normalize_label(label))
    if not record:
        return None
    return json.dumps([record["label"], record["classified_as"]])


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Print a CLASSIFICATION_CORPUS line for one logged question.")
    parser.add_argument("label")
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parent / "data")
    args = parser.parse_args()
    line = promote(load_corpus(args.data), args.label)
    print(line or "Not found.")


if __name__ == "__main__":
    main()
