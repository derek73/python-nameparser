"""Command-line debug helper over the 2.0 API (migration spec §6).

    python -m nameparser "Dr. Juan Q. Xavier de la Vega III"
    python -m nameparser --json "Doe, John"
"""
import argparse
import json

from nameparser import parse


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="nameparser", description="Parse a personal name.")
    ap.add_argument("name", help="the name string to parse")
    ap.add_argument("--json", action="store_true",
                    help="print the component dict as JSON")
    args = ap.parse_args(argv)
    n = parse(args.name)
    if args.json:
        print(json.dumps(n.as_dict(), ensure_ascii=False))
        return 0
    print(repr(n))
    print(repr(n.capitalized()))
    print("Initials:", n.initials())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
