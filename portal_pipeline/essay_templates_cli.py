"""Author: Yazad Madan. Add, list, or remove user-approved local essay templates."""
import argparse
import json
from pathlib import Path

import answer_memory
import essay_tracks

# Config
DEFAULT_DATA = answer_memory.DATA_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Assist data directory")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Store text written or approved by the user")
    add.add_argument("family", choices=essay_tracks.FAMILIES)
    add.add_argument("kind", choices=essay_tracks.KINDS)
    content = add.add_mutually_exclusive_group(required=True)
    content.add_argument("--text")
    content.add_argument("--text-file", type=Path, help="UTF-8 template file")
    add.add_argument("--approved", action="store_true", required=True,
                     help="Confirm the user wrote or approved this text")
    listing = commands.add_parser("list")
    listing.add_argument("family", nargs="?", choices=essay_tracks.FAMILIES)
    remove = commands.add_parser("remove")
    remove.add_argument("family", choices=essay_tracks.FAMILIES)
    remove.add_argument("kind", choices=essay_tracks.KINDS)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            rows = essay_tracks.load_templates(args.data)[essay_tracks.TEMPLATES_KEY]
            print(json.dumps({args.family: rows.get(args.family, {})} if args.family else rows, indent=2))
        elif args.command == "remove":
            essay_tracks.update_template(args.data, args.family, args.kind)
            print("Removed template.")
        else:
            text = args.text
            if args.text_file:
                with args.text_file.open(encoding="utf-8-sig") as handle:
                    text = handle.read(answer_memory.MAX_ANSWER + 1)
            essay_tracks.update_template(args.data, args.family, args.kind, text, approved=args.approved)
            print("Stored approved template. Assist answers remain drafts.")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
