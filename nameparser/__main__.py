"""Command-line debug helper over the 2.0 API.

    python -m nameparser "Dr. Juan Q. Xavier de la Vega III"
    python -m nameparser --json "Doe, John"
    python -m nameparser --order family-first "Kovács János Péter"
    python -m nameparser --locale ja "山田太郎"
"""
import argparse
import dataclasses
import json

from nameparser import (
    FAMILY_FIRST,
    FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST,
    Lexicon,
    Locale,
    PolicyPatch,
    Segmenter,
    parser_for,
)

# The vocabulary [rules] tables' spelling of each name_order constant,
# copied because __main__ imports only the public package;
# tests/v2/test_cli.py holds it equal to _locale's.
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
                         "nameparser.locales. 'ja' divides unspaced names "
                         "when nameparser[ja] is installed")
    ap.add_argument("--order", choices=_ORDERS,
                    help="the order to read a name's words in "
                         "(default: given-first); a Han, Hangul or kana "
                         "name keeps its script's order, and a family "
                         "comma fixes the order")
    args = ap.parse_args(argv)
    pack = None
    segmenter: Segmenter | None = None
    # `is not None`, not truthiness: --locale "" must reach get() and
    # exit 2 listing the codes, not silently fall back to the default
    if args.locale is not None:
        from nameparser import locales
        try:
            pack = locales.get(args.locale)
        except KeyError as exc:
            ap.error(exc.args[0])  # exits 2, message to stderr
        # The pack only activates division; the installed extra divides.
        # Without it the parser warns, naming the install (rules/D1).
        if pack.code == "ja":
            try:
                segmenter = locales.ja_segmenter()
            except ImportError:
                pass
    # The order is written into the pack's own patch, so it replaces a
    # pack's order without a two-pack conflict warning, and the parser
    # is built once, parser_for re-emitting its warnings (#337)
    if args.order is not None:
        order = _ORDERS[args.order]
        if pack is None:
            pack = Locale(code="cli_order", lexicon=Lexicon.empty(),
                          policy=PolicyPatch(name_order=order))
        else:
            pack = dataclasses.replace(pack, policy=dataclasses.replace(
                pack.policy, name_order=order))
    packs = () if pack is None else (pack,)
    n = parser_for(*packs, segmenter=segmenter).parse(args.name)
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
