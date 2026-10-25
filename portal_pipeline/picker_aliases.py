"""Ordered name variants for search pickers (school, field of study, ...), with a free-text fallback."""
import argparse
import json
import sys
from pathlib import Path

from question_corpus import normalize_label

# Config
DATA_DIR = Path(__file__).resolve().parent / "data"
ALIASES_FILENAME = "picker_aliases.json"
SCHEMA_VERSION = 1
NAMES_COLUMN = "names"
FALLBACK_COLUMN = "fallback"
MAX_NAMES = 10  # tried on every site, so one list serves all portals
ENTITIES_COLUMN = "entities"


def aliases_path(data_dir=DATA_DIR):
    return Path(data_dir).resolve() / ALIASES_FILENAME


def load_aliases(data_dir=DATA_DIR):
    path = aliases_path(data_dir)
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, ENTITIES_COLUMN: {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get(ENTITIES_COLUMN), dict):
        raise ValueError("Picker aliases have an unsupported schema.")
    return data


def save_aliases(data, data_dir=DATA_DIR):
    path = aliases_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def set_entity(data, kind, canonical, names, fallback=""):
    """Stores the ordered names to try for one entity; the canonical name is always tried first."""
    ordered, seen = [], set()
    for name in [canonical, *names]:
        text = str(name or "").strip()
        key = normalize_label(text)
        if text and key not in seen:
            seen.add(key)
            ordered.append(text)
    if not ordered:
        return False
    ordered = ordered[:MAX_NAMES]
    data[ENTITIES_COLUMN].setdefault(kind, {})[normalize_label(canonical)] = {NAMES_COLUMN: ordered, FALLBACK_COLUMN: str(fallback or "").strip()}
    return True


def profile_pickers(data):
    """Kind to a list of {names, fallback}, the shape the extension reads from profile.pickers."""
    return {kind: [{NAMES_COLUMN: list(entity[NAMES_COLUMN]), FALLBACK_COLUMN: entity[FALLBACK_COLUMN]} for entity in group.values()]
            for kind, group in data[ENTITIES_COLUMN].items()}


def learn_name(data, kind, canonical, picked_label):
    """Adds a label a portal actually offered (user picked it once) so later runs try it; returns True if added."""
    entity = data[ENTITIES_COLUMN].get(kind, {}).get(normalize_label(canonical))
    key = normalize_label(picked_label)
    if not entity or not key or len(entity[NAMES_COLUMN]) >= MAX_NAMES or key in {normalize_label(name) for name in entity[NAMES_COLUMN]}:
        return False
    entity[NAMES_COLUMN].append(str(picked_label).strip())
    return True


def candidates_for(data, kind, value):
    """Returns (names, fallback) for a value, matched on its exact normalized text against any stored name; else ([value], value)."""
    key = normalize_label(value)
    for entity in data[ENTITIES_COLUMN].get(kind, {}).values():
        if key in {normalize_label(name) for name in entity[NAMES_COLUMN]}:
            return list(entity[NAMES_COLUMN]), entity[FALLBACK_COLUMN]
    text = str(value or "").strip()
    return ([text] if text else []), text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add = parser.add_argument
    add("kind")
    add("canonical")
    add("--name", action="append", default=[], help="Another name to try, in order.")
    add("--fallback", default="")
    args = parser.parse_args(argv)
    data = load_aliases()
    if not set_entity(data, args.kind, args.canonical, args.name, args.fallback):
        print("Not stored: no usable name.", file=sys.stderr)
        return 1
    save_aliases(data)
    print(f"Stored {args.kind}: {args.canonical}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
