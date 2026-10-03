"""Resolve portal values from the existing read-only resume references."""
from __future__ import annotations

import json
import re
from pathlib import Path


def plain(value: str) -> str:
    return value.replace("**", "").replace("\u2014", ",").strip()


def month(value: str) -> str | None:
    import datetime
    for pattern in ("%B %Y", "%b %Y"):
        try:
            return datetime.datetime.strptime(value.strip(), pattern).strftime("%Y-%m")
        except ValueError:
            pass
    return None


def resolve_profile(root: Path) -> dict:
    reference = root / "_Reference"
    master = json.loads((reference / "Resume_Content_Master.json").read_text(encoding="utf-8"))
    boiler = (reference / "Application_Boilerplate.md").read_text(encoding="utf-8")
    internals = (reference / "Builder_Internals.md").read_text(encoding="utf-8")
    values = {}

    def add(key, value, source):
        if value is not None and value != "":
            values[key] = {"value": value, "source": source}

    header = master["header"]
    name = header["name"].split(",")[0].strip().title().split()
    contact = header["contact"].split("|")
    source = "Resume_Content_Master.json: header"
    add("first_name", name[0], source)
    add("last_name", " ".join(name[1:]), source)
    add("full_name", " ".join(name), source)
    add("email", contact[0].strip(), source)
    add("phone", contact[1].strip(), source)
    add("location", contact[2].strip(), source)
    add("city", contact[2].split(",")[0].strip(), source)
    add("linkedin", header.get("linkedin"), source)
    add("github", header.get("github"), source)

    answers = dict(re.findall(r"^- ([^:\n]+):\s*(.+)$", boiler, re.M))
    answer_map = {
        "Work authorized in US": "authorized_us",
        "Require sponsorship now": "sponsorship_now",
        "Require sponsorship in future": "sponsorship_future",
        "Visa type": "visa_type",
        "Open to relocation": "relocation",
        "Salary expectation": "salary",
        "Start date": "available_from",
        "Source": "job_source",
        "Country of citizenship": "citizenship",
    }
    for label, key in answer_map.items():
        raw = answers.get(label)
        if raw:
            value = plain(raw)
            if key in {"authorized_us", "sponsorship_now", "sponsorship_future", "relocation"}:
                value = value.split()[0]
            add(key, value, f"Application_Boilerplate.md: {label}")

    descriptions = re.findall(r"^### (.+)\n(.+?)(?=\n---|\n##|\Z)", boiler, re.M | re.S)
    employment = []
    for employer in master["experience"]:
        date_parts = re.split(r"\s+[\u2013\u2014]\s+|\s+to\s+", employer["dateRange"])
        for role in employer["roles"]:
            index = len(employment)
            prefix = f"employment.{index}."
            add(prefix + "company", employer["company"], "Resume_Content_Master.json: experience")
            add(prefix + "title", plain(role["title"]), "Resume_Content_Master.json: experience")
            add(prefix + "location", employer["location"], "Resume_Content_Master.json: experience")
            start = end = None
            date_source = "Resume_Content_Master.json: experience"
            if len(employer["roles"]) == 1 and len(date_parts) == 2:
                start, end = map(month, date_parts)
            elif employer["company"] == "Axis Bank Limited":
                key = ("Deputy Manager, Wholesale Banking FP&A" if "Deputy Manager" in role["title"]
                       else "Manager, Basel III Capital Reporting and Credit Risk" if "Basel III" in role["title"]
                       else "Manager, ALM (Liquidity Risk and Treasury)" if "Asset Liability" in role["title"]
                       else None)
                if key:
                    found = re.search(re.escape(key) + r":\s*([A-Za-z]+ \d{4}) to ([A-Za-z]+ \d{4})", internals)
                    if found:
                        start, end = map(month, found.groups())
                        date_source = "Builder_Internals.md: non-overlapping application role dates"
            add(prefix + "start_date", start, date_source)
            add(prefix + "end_date", end, date_source)
            for heading, paragraph in descriptions:
                normalized = plain(heading)
                if employer["company"] in normalized and plain(role["title"]) in normalized:
                    add(prefix + "description", plain(paragraph), "Application_Boilerplate.md: role descriptions")
                    break
            employment.append({"company": employer["company"], "title": plain(role["title"])})

    for index, education in enumerate(master["education"]):
        for key, value in {"school": education["school"], "degree": education["degree"],
                           "location": education["location"], "end_date": month(education["date"])}.items():
            add(f"education.{index}.{key}", value, "Resume_Content_Master.json: education")
    return {"values": values, "employment": employment, "education": master["education"],
            "note": "No street address, postal code, education start date, or voluntary demographic default is inferred."}


def hard_fact_errors(content: dict, master: dict) -> list[str]:
    """Allow tailoring while rejecting changed identity, dates, and credentials."""
    errors = []
    for key in ("header", "education", "certifications"):
        if content.get(key) != master.get(key):
            errors.append(f"{key} must match the master. Change facts in the existing workflow first.")
    facts = {item["company"]: item for item in master["experience"]}
    for item in content.get("experience", []):
        original = facts.get(item.get("company"))
        if not original:
            errors.append("An employer is not present in the master.")
            continue
        for key in ("location", "dateRange"):
            if item.get(key) != original[key]:
                errors.append(f"{item['company']}: {key} differs from the master.")
        titles = {role["title"] for role in original["roles"]}
        if any(role.get("title") not in titles for role in item.get("roles", [])):
            errors.append(f"{item['company']}: a role title differs from the master.")
    return errors
