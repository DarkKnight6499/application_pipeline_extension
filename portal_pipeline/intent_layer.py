"""Author: Yazad Madan. Map a portal question to a stable intent so one stored answer serves every company.

Patterns live here (public repo). Answers live in answer memory under the key "intent:<id>" (local, gitignored).
Answers are YES, NO or literal text. YES and NO expand to the wording each portal uses (Yes, Opt In, I agree).
Usage: py -3 intent_layer.py classify "<question>" | learn "<question>" "<answer>" | show
"""
import re
import sys
from datetime import date

import answer_memory

# Config
INTENT_PREFIX = "intent:"
YES, NO = "YES", "NO"
YES_WORDS = ["Yes", "Opt In", "I agree", "I acknowledge", "I consent"]
NO_WORDS = ["No", "Opt Out", "I do not agree"]
OPT_WORDS = re.compile(r"\b(opt|stem|cpt)\b", re.I)
SPONSOR_WORDS = re.compile(r"sponsor", re.I)
# Order matters: first match wins, so narrow patterns come before broad ones.
INTENT_PATTERNS = [
    ("related_to_employee", r"related to (any|an)\b.*\b(employee|officer|director)|relative.*(work|employ)"),
    ("current_employee_here", r"currently (working|employed) (at|by|with|for)|are you a current employee"),
    ("prev_worked_here", r"(previously|ever|formerly)\W+(been\W+)?(employed|worked)|worked (at|for) .* (before|previously|either)|former employee"),
    ("non_compete", r"non.?solicit|non.?compet|restrictions in the scope|agreement .* protect confidential"),
    ("outside_activity", r"outside (activity|employment|business)|serving on a board"),
    ("financial_license", r"financial services licen[sc]e|finra|series (7|63|65|66)\b"),
    ("discharged_or_resigned", r"discharged|asked to resign|resigned to avoid|terminated for"),
    ("public_office", r"public office|government entity|government official|elected official"),
    ("under_investigation", r"under investigation"),
    ("age_18", r"at least 18|18 years of age|legal working age|over the age of 18"),
    ("willing_travel", r"willing to travel"),
    ("willing_relocate", r"willing to relocate|open to relocation"),
    ("california_resident", r"california resident"),
    ("highest_education", r"highest level of education|highest degree"),
    ("work_authorized_us", r"(legally )?(authorized|eligible) to work in the (united states|u\.?s)|legally authorized to work"),
    ("ai_tools_consent", r"artificial intelligence|\bai tools?\b|automated (search|decision)"),
    ("other_opportunities", r"additional opportunities|other (opportunities|positions|roles)|future opportunities"),
    ("drug_screen", r"drug.free|drug (screen|test)"),
    ("background_check", r"background check|fingerprint|diploma or ged"),
    ("hispanic_latino", r"hispanic or latino"),
    ("veteran_status", r"veteran"),
    ("ethnicity", r"ethnicity|\brace\b"),
    ("gender", r"\bgender\b|\bsex\b"),
    ("disability", r"disabilit"),
    ("lgbtq", r"lgbtq|sexual orientation"),
    ("how_did_you_hear", r"how did you hear|source of (your )?application"),
]
COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in INTENT_PATTERNS]


def classify(label):
    """Intent id for a question label, or None. Sponsorship splits by whether OPT, STEM OPT or CPT is named."""
    text = re.sub(r"\s+", " ", str(label)).strip()
    if SPONSOR_WORDS.search(text) and re.search(r"require|need|assistance|will you", text, re.I):
        return "sponsorship_opt_listed" if OPT_WORDS.search(text) else "sponsorship_h1b_only"
    for name, pattern in COMPILED:
        if pattern.search(text):
            return name
    return None


def key_for(intent):
    return INTENT_PREFIX + intent


def lookup(memory, label):
    """Stored answer (YES, NO or text) for the label's intent, or None."""
    intent = classify(label)
    entry = memory["answers"].get(answer_memory.normalize_label(key_for(intent))) if intent else None
    return entry["answer"] if entry else None


def learn(memory, label, answer, source="manual"):
    """Store an answer under the label's intent; returns the intent or None when unclassified."""
    intent = classify(label)
    if not intent:
        return None
    text = YES if str(answer).strip().lower() in {w.lower() for w in YES_WORDS} else NO if str(answer).strip().lower() in {w.lower() for w in NO_WORDS} else str(answer).strip()
    entry = memory["answers"].setdefault(answer_memory.normalize_label(key_for(intent)), {answer_memory.LABEL_COLUMN: key_for(intent), "first_seen": date.today().isoformat(), "uses": 0})
    entry.update(answer=text, source=source)
    return intent


def expand(answer):
    """Wording candidates to try against a portal's options, best first."""
    if answer == YES:
        return YES_WORDS
    if answer == NO:
        return NO_WORDS
    return [part.strip() for part in str(answer).split("|")]  # "a|b" lists alternative wordings


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "classify":
        print(classify(argv[2]))
    elif argv[1] == "learn":
        found = answer_memory.update_memory(lambda data: learn(data, argv[2], argv[3], source="cli"))
        print("intent:", found)
    elif argv[1] == "show":
        memory = answer_memory.load_memory()
        for key, entry in sorted(memory["answers"].items()):
            if key.startswith(answer_memory.normalize_label(INTENT_PREFIX)):
                print(entry[answer_memory.LABEL_COLUMN], "=", entry["answer"])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
