"""Author: Yazad Madan. List or remove local vendor dropdown mappings."""
import argparse
import json
from pathlib import Path

import answer_memory
import dropdown_mappings

# Config
DEFAULT_DATA = answer_memory.DATA_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("vendor", nargs="?", choices=dropdown_mappings.VENDOR_DOMAINS)
    remove = commands.add_parser("remove")
    remove.add_argument("vendor", choices=dropdown_mappings.VENDOR_DOMAINS)
    remove.add_argument("question")
    remove.add_argument("answer")
    args = parser.parse_args(argv)
    try:
        store = dropdown_mappings.load(args.data)
        if args.command == "list":
            print(json.dumps([row for row in store[dropdown_mappings.ROWS]
                              if not args.vendor or row[dropdown_mappings.VENDOR] == args.vendor], indent=2))
        else:
            previous = dropdown_mappings.lookup(store, args.vendor, args.question, args.answer)
            if previous is None:
                parser.error("Mapping not found.")
            if not dropdown_mappings.update(args.data, args.vendor, args.question, args.answer, None, previous):
                parser.error("Mapping changed. List mappings and retry.")
            print("Removed mapping.")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
