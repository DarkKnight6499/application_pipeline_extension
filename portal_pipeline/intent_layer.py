"""Author: Yazad Madan. Map a portal question to a stable intent so one stored answer serves every company.

Patterns live here (public repo). Answers live in answer memory under the key "intent:<id>" (local, gitignored).
Answers are YES, NO, literal alternatives separated by |, or highest/lowest option rules.
YES and NO expand to the wording each portal uses (Yes, Opt In, I agree).
Usage: py -3 intent_layer.py classify "<question>" | learn "<question>" "<answer>" | show
"""
import re
import sys
from datetime import date

import answer_memory

# Config
INTENT_PREFIX = "intent:"
YES, NO = "YES", "NO"
OPTION_RULES = {"highest", "lowest"}
YES_WORDS = ["Yes", "Opt In", "I agree", "I acknowledge", "I consent"]
NO_WORDS = ["No", "Opt Out", "I do not agree"]
OPT_WORDS = re.compile(r"\b(opt|stem|cpt)\b", re.I)
SPONSOR_WORDS = re.compile(r"sponsor", re.I)
# Order matters: first match wins, so narrow patterns come before broad ones.
INTENT_PATTERNS = [
    ("state", r"^state(?:/province)?\s*[?*]*$"),
    ("county", r"^county\s*[?*]*$"),
    ("address_line1", r"^address\s*[?*]*$"),
    ("preferred_first_name", r"^preferred first name"),
    ("preferred_last_name", r"^preferred last name"),
    ("military_status", r"^military status\s*[?*]*$|\b(?:serving|served) in the armed forces\b"),
    ("military_spouse", r"^military spouse(?:/domestic partner)?\s*[?*]*$"),
    ("military_reserve", r"\bcurrently a member of the u\.?s\.? national guard or reserves\b"),
    ("language_preference", r"\blanguage preference for receiving communications\b"),
    ("employee_referral", r"\bare you a referral of a current\b"),
    ("ai_tools_consent", r"\bautomated tools such as ai\b"),
    ("identity_verification", r"\bsubmit verification of both your identity and authorization to work\b"),
    ("related_to_employee", r"\bimmediate family members\b.*\b(?:work|employ)"),
    ("work_authorized_us", r"\blegally eligible to work in (?:the country in which this job is located|the job.s location)"),
    ("salary_expectation", r"^(?:what are your |please (?:provide|indicate) your )?(?:salary expectations|expected salary|desired salary)\s*[?*]*$"),
    ("job_board_source", r"^if internet job board, please specify\s*[:?*]*$"),
    ("current_student", r"\b(?:are you|currently enrolled as) (?:currently )?a (?:full.time |part.time )?student\s*[?*]*$|\bcurrently enrolled (?:in|at) (?:a |an )?(?:college|university|school)\b"),
    ("available_start_date", r"^(?:available date|available start date|earliest start date)\s*[?*]*$|\b(?:what is your|please (?:provide|indicate) your) (?:available |earliest )?start date\b|\bwhen (?:can|could|are) you (?:available to )?(?:start|begin)\b"),
    ("language_preference", r"^(?:preferred language|language preference)\s*[?*]*$|\b(?:what is your|please (?:select|indicate) your) preferred language\b"),
    ("essential_functions", r"\b(?:can|are) you (?:able to )?perform (?:the )?essential functions\b.*\bwith or without (?:reasonable )?accommodation\b"),
    ("basic_qualifications", r"\b(?:do you meet|have you met) (?:all (?:of )?)?(?:the )?(?:basic|minimum|required) qualifications\b"),
    ("preferred_qualifications", r"\b(?:do you meet|have you met) (?:all (?:of )?)?(?:the )?preferred qualifications\b"),
    ("identity_verification", r"\b(?:can|will|are) you (?:able to )?(?:provide|present) (?:proof|verification) of (?:your )?identity\b.*\b(?:upon hire|if hired|on hire)\b"),
    ("military_spouse", r"\bare you (?:a |the )?(?:military spouse|spouse of (?:a |an )?(?:veteran|service member|military member))\s*[?*]*$"),
    ("military_reserve", r"\bare you (?:currently )?(?:a member of|serving in) (?:the )?(?:national guard|(?:armed forces |military )?reserves)\b"),
    ("sms_consent", r"\bopt[ -]?in (?:to|for) (?:sms|text messages)\b|\b(?:consent|agree) to (?:receive |receiving )(?:sms|text messages)\b"),
    ("sms_consent", r"\bopt[ -]?in to receive sms updates about (?:my|your) application\b"),
    ("protected_veteran", r"^are you a protected veteran\s*[?*]*$"),
    ("employee_referral", r"\b(?:were|are) you referred by (?:an? |a current )?employee\b|^employee referral\s*[?*]*$"),
    ("work_type", r"^work type\s*[?*]*$|\b(?:what type of employment are you seeking|are you seeking full[ -]?time (?:work|employment))\b"),
    ("politically_exposed", r"\bare you (?:a |considered a )?politically exposed person\s*[?*]*$"),
    ("securities_registration", r"\bare you currently, were you previously, or have you ever attempted to become, registered in the securities industry\s*[?*]*$"),
    ("middle_name", r"^middle name\s*[?*]*$"),
    ("name_suffix", r"^(?:name )?suffix\s*[?*]*$"),
    ("address_line2", r"^address line 2\s*[?*]*$"),
    ("phone_extension", r"^phone extension\s*[?*]*$"),
    ("country", r"^country\s*[?*]*$"),
    ("country_phone_code", r"^country phone code\s*[?*]*$"),
    ("notice_period", r"^(?:what is your )?notice period\s*[?*]*$"),
    ("email", r"^email(?: address)?\s*[?*]*$"),
    ("linkedin_url", r"\b(?:provide|share) your linkedin (?:profile|url)\b|^linkedin (?:profile|url)\s*[?*]*$"),
    ("related_to_employee", r"related to (any|an)\b.*\b(employee|officer|director)|relative.*(work|employ)"),
    ("current_employee_here", r"currently (working|employed) (at|by|with|for)|are you a current employee"),
    ("prev_worked_here", r"(previously|ever|formerly)\W+(been\W+)?(employed|worked)|worked (at|for) .* (before|previously|either)|former employee"),
    ("prev_worked_here", r"^have you worked (?:at|for)\b"),
    ("non_compete", r"non.?solicit|non.?compet|restrictions in the scope|agreement .* protect confidential"),
    ("outside_activity", r"outside (activity|employment|business)|serving on a board"),
    ("outside_activity", r"\b(?:do you have|will you (?:have|continue)) (?:a |any )?(?:second job|outside business)\b"),
    ("financial_license", r"financial services licen[sc]e|finra|series (7|63|65|66)\b"),
    ("discharged_or_resigned", r"discharged|asked to resign|resigned to avoid|terminated for"),
    ("public_office", r"public office|government entity|government official|elected official"),
    ("under_investigation", r"under investigation"),
    ("age_18", r"at least 18|18 years of age|legal working age|over the age of 18"),
    ("age_18", r"\bare you (?:18 or older|over 18)\s*[?*]*$"),
    ("first_name", r"^first name"),
    ("last_name", r"^last name"),
    ("address_line1", r"^address line 1"),
    ("city", r"^city"),
    ("postal_code", r"^(postal|zip) code"),
    ("postal_code", r"^zip/postal code\s*[?*]*$"),
    ("phone_number", r"^phone number"),
    ("phone_device_type", r"^phone device type"),
    ("current_visa_type", r"what type of visa you are currently on|type of visa .* currently"),
    ("willing_travel", r"willing to travel"),
    ("willing_relocate", r"willing to relocate|open to relocation"),
    ("willing_relocate", r"\bopen to relocating\b"),
    ("california_resident", r"california resident"),
    ("highest_education", r"highest level of education|highest degree"),
    ("work_authorized_us", r"(legally )?(authorized|eligible) to work in the (united states|u\.?s)|legally authorized to work"),
    ("ai_tools_consent", r"artificial intelligence|\bai tools?\b|automated (search|decision)"),
    ("ai_tools_consent", r"\bopt[ -]?in to ai review of your application\b"),
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
    if re.search(r"type of sponsorship", text, re.I):
        return "sponsorship_type_text"
    if SPONSOR_WORDS.search(text) and re.search(r"require|need|assistance|will you", text, re.I):
        return "sponsorship_opt_listed" if OPT_WORDS.search(text) else "sponsorship_h1b_only"
    for name, pattern in COMPILED:
        if pattern.search(text):
            return name
    return None


def key_for(intent):
    return INTENT_PREFIX + intent


def lookup(memory, label):
    """Stored answer or option rule for the label's intent, or None."""
    intent = classify(label)
    entry = memory["answers"].get(answer_memory.normalize_label(key_for(intent))) if intent else None
    return entry["answer"] if entry else None


def learn(memory, label, answer, source="manual"):
    """Store an answer under the label's intent; returns the intent or None when unclassified."""
    intent = classify(label)
    if not intent:
        return None
    text = "|".join(str(value).strip() for value in answer) if isinstance(answer, (list, tuple)) else str(answer).strip()
    text = YES if text.lower() in {w.lower() for w in YES_WORDS} else NO if text.lower() in {w.lower() for w in NO_WORDS} else text
    entry = memory["answers"].setdefault(answer_memory.normalize_label(key_for(intent)), {answer_memory.LABEL_COLUMN: key_for(intent), "first_seen": date.today().isoformat(), "uses": 0})
    entry.update(answer=text, source=source)
    return intent


def expand(answer):
    """Wording candidates to try against a portal's options, best first."""
    candidates = []
    for value in answer if isinstance(answer, (list, tuple)) else [answer]:
        for part in str(value or "").split("|"):
            text = part.strip()
            if text.upper() == YES:
                candidates.extend(YES_WORDS)
            elif text.upper() == NO:
                candidates.extend(NO_WORDS)
            elif text:
                candidates.append(text)
    return candidates


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
