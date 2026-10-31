"""Command-line debug helper over the 2.0 API.

    python -m nameparser "Dr. Juan Q. Xavier de la Vega III"
    python -m nameparser --json "Doe, John"
    python -m nameparser --order family-first "Kovács János Péter"
"""
import argparse
import dataclasses
import json

from nameparser import (
    FAMILY_FIRST,
    FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST,
    Parser,
)

# The CLI spelling of each Policy.name_order constant.
_ORDERS = {
    "given-first": GIVEN_FIRST,
    "family-first": FAMILY_FIRST,
    "family-first-given-last": FAMILY_FIRST_GIVEN_LAST,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="nameparser", description="Parse a personal name.")
    ap.add_argument("name", help="the name string to parse")
    ap.add_argument("--json", action="store_true",
                    help="print the component dict as JSON")
    ap.add_argument("--locale", metavar="CODE",
                    help="parse with a locale pack (e.g. 'ru'); see "
                         "nameparser.locales")
    ap.add_argument("--order", choices=_ORDERS,
                    help="the order to read the name's words in "
                         "(default: given-first); applied after --locale, "
                         "so it wins over a pack's order")
    args = ap.parse_args(argv)
    # `is not None`, not truthiness: --locale "" must reach get() and
    # exit 2 listing the codes, not silently fall back to the default
    if args.locale is not None:
        from nameparser import locales, parser_for
        try:
            parser = parser_for(locales.get(args.locale))
        except KeyError as exc:
            ap.error(exc.args[0])  # exits 2, message to stderr
    else:
        parser = Parser()
    # Applied after the pack, so the explicit flag wins over its order
    if args.order is not None:
        parser = dataclasses.replace(parser, policy=dataclasses.replace(
            parser.policy, name_order=_ORDERS[args.order]))
    n = parser.parse(args.name)
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
