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
    ap.add_argument("--locale", metavar="CODE",
                    help="parse with a locale pack (e.g. 'ru'); see "
                         "nameparser.locales")
    args = ap.parse_args(argv)
    # `is not None`, not truthiness: --locale "" must reach get() and
    # exit 2 listing the codes, not silently fall back to the default
    if args.locale is not None:
        from nameparser import locales, parser_for
        try:
            parser = parser_for(locales.get(args.locale))
        except KeyError as exc:
            ap.error(exc.args[0])  # exits 2, message to stderr
        n = parser.parse(args.name)
    else:
        n = parse(args.name)
    if args.json:
        print(json.dumps(n.as_dict(), ensure_ascii=False))
        return 0
    # Label each section: the two reprs are byte-identical for input
    # that is already correctly cased, so without labels there is no
    # telling which is the parse and which is the capitalized view.
    print("Parsed:")
    print(repr(n))
    print("Capitalized:")
    print(repr(n.capitalized()))
    print("Initials:", n.initials())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
