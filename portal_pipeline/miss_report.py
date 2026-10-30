"""Author: Yazad Madan. Report unanswered questions or resolve a label across hosts.

Usage: python portal_pipeline/miss_report.py [--data DIRECTORY] [--json] [--resolve "Question label"]
Counts measure sightings, including server misses and extension notifications, not fill attempts.
Resolve hides a label across all hosts. A later sighting reopens it with its historical count.
"""
import argparse
import json
from pathlib import Path

import miss_log

# Config
DEFAULT_DATA = Path(__file__).resolve().parent / "data"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Directory containing the assist token and miss log")
    parser.add_argument("--json", action="store_true", help="Print report rows as JSON")
    parser.add_argument("--resolve", metavar="LABEL", help="Hide this normalized label across all hosts")
    args = parser.parse_args(argv)
    try:
        if args.resolve is not None:
            miss_log.resolve(args.data, args.resolve)
        rows = miss_log.report(args.data)
    except (OSError, ValueError, KeyError, TimeoutError) as error:
        parser.exit(1, f"Cannot read or update unanswered queue: {error}\n")
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=True))
    elif not rows:
        print("No unanswered questions.")
    else:
        for row in rows:
            print(f"{row[miss_log.COUNT_COLUMN]} sightings: {row[miss_log.LABEL_COLUMN]}")
            print("  Hosts: " + ", ".join(row[miss_log.HOSTS_COLUMN]))
            print("  Companies: " + (", ".join(row[miss_log.COMPANIES_COLUMN]) or "(unknown)"))
            for sample in row[miss_log.SAMPLES_COLUMN]:
                print("  Options: " + " | ".join(sample))
            print(f"  First: {row[miss_log.FIRST_COLUMN]}; last: {row[miss_log.LAST_COLUMN]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
