"""Command-line debug helper over the 2.0 API.

    python -m nameparser "Dr. Juan Q. Xavier de la Vega III"
    python -m nameparser --json "Doe, John"
    python -m nameparser --order family-first "Kovács János Péter"
    python -m nameparser --locale ja "山田太郎"
    python -m nameparser --locale ko --strict "Kim Do Hyun"
    python -m nameparser --locale vi --strict "Do Van Minh"
    python -m nameparser --two-given-names "Juan Carlos García"
    python -m nameparser --lone-name-word family "Nguyen"
    python -m nameparser --locale es --no-two-family-names "Maestra Ana García López"
"""
import argparse
import dataclasses
import importlib.util
import json
import sys
import warnings
from typing import Any

from nameparser import (
    FAMILY_FIRST,
    CapsSuffixes,
    FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST,
    Lexicon,
    Locale,
    PolicyPatch,
    Role,
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

# The Policy fields a rule is tested by, one flag each, spelled as the
# field; tests/v2/test_cli.py holds every Policy field to these two
# tables, --order or _NOT_ON_THE_COMMAND_LINE.
_SWITCHES = {
    "two_given_names": "join a middle name to the given name",
    "two_family_names": "read two name words as the family (two "
                        "family names): the last two, or the first two "
                        "under a family-first --order",
    "middle_as_family": "fold the middle names into the family",
    "lenient_comma_suffixes": "read a lone V or I after a comma as a "
                              "numeral suffix (John Smith, V)",
    "unlisted_dotted_suffixes": "read an unlisted X.Y.Z. ending a name "
                                "as a suffix",
}
# each an enum field, with the help its flag offers
_CHOICES = {
    "unlisted_caps_suffixes": (CapsSuffixes,
                               "where an unlisted all-caps word reads as "
                               "a credential: nowhere, after a comma (the "
                               "default), or ending a name too"),
}
# the two fields Policy.lone_name_word accepts, a flag of their own as
# --order is, since a choice of every Role would offer the ones it refuses
_LONE_NAME_WORD = {"given": Role.GIVEN, "family": Role.FAMILY}
_NOT_ON_THE_COMMAND_LINE = {
    # each needs a mapping, a set of scripts or rules, bracket pairs or
    # separator strings
    "script_orders", "segment_scripts", "patronymic_rules",
    "nickname_delimiters", "maiden_delimiters", "extra_suffix_delimiters",
    # input clean-up, not a reading of the name
    "strip_emoji", "strip_bidi",
}

_NO_JA_EXTRA = (
    "nameparser: --locale ja divides unspaced names only with "
    "namedivider-python installed: pip install 'nameparser[ja]'")


def _ja_extra_installed() -> bool:
    # only the package's absence falls back: a broken install fails
    # with its own error rather than a note saying to install it
    return importlib.util.find_spec("namedivider") is not None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="nameparser", description="Parse a personal name.")
    ap.add_argument("name", help="the name string to parse")
    ap.add_argument("--json", action="store_true",
                    help="print the component dict as JSON")
    ap.add_argument("--locale", metavar="CODE",
                    help="parse with a locale pack (e.g. 'ru'); see "
                         "nameparser.locales. 'ja' divides unspaced names "
                         "when nameparser[ja] is installed. A code no "
                         "pack has but a vocabulary file does (e.g. 'ko') "
                         "chooses that language alone; a file holding no "
                         "reading yet (e.g. 'hu') needs --strict")
    ap.add_argument("--strict", action="store_true",
                    help="read only the --locale language's vocabulary "
                         "file, the shared words (Dr, PhD, the numerals) "
                         "and native-script words, dropping every other "
                         "language's (for single-origin names); a "
                         "pack choosing no language chooses its code")
    ap.add_argument("--order", choices=_ORDERS,
                    help="the order to read a name's words in "
                         "(default: given-first); a Han, Hangul or kana "
                         "name keeps its script's order, and a family "
                         "comma fixes the order")
    ap.add_argument("--lone-name-word", choices=_LONE_NAME_WORD,
                    help="the field a name of one name word reads as, "
                         "under every order (default: given); a title, "
                         "a nickname, a maiden name, a family comma or "
                         "a script's own order still decides first")
    rules = ap.add_argument_group(
        "Policy switches",
        "each sets the Policy field of its name, replacing a pack's "
        "setting; one left out keeps the pack's or the default")
    for field, what in _SWITCHES.items():
        rules.add_argument("--" + field.replace("_", "-"),
                           action=argparse.BooleanOptionalAction,
                           help=what)
    for field, (enum, what) in _CHOICES.items():
        rules.add_argument("--" + field.replace("_", "-"),
                           choices=[member.value for member in enum],
                           help=what)
    args = ap.parse_args(argv)
    if args.strict and args.locale is None:
        ap.error("--strict needs --locale: it keeps only the chosen "
                 "language's vocabulary and the shared words")
    pack = None
    unknown = None
    segmenter: Segmenter | None = None
    noted = False
    # `is not None`, not truthiness: --locale "" must reach get() and
    # exit 2 listing the codes, not silently fall back to the default
    if args.locale is not None:
        from nameparser import locales
        # a tag spelled for a pack's code is that pack (pt-BR is pt_br);
        # a pack's language with a region or script subtag (zh-CN,
        # zh-Hant, es-MX, ja-JP) is refused
        # naming the pack, never chosen bare: a bare choice would drop
        # the pack's list, policy and segmenter in silence
        code = args.locale.replace("-", "_").casefold()
        language = code.split("_")[0]
        try:
            pack = locales.get(code if code in locales.available()
                               else args.locale)
        except KeyError as exc:
            unknown = exc.args[0]
            if language != code and language in locales.available():
                ap.error(f"{unknown}; {args.locale!r} names the language "
                         f"of the pack {language!r} with a subtag: use "
                         f"--locale {language}")
            # not a pack: a language tag chooses that language alone,
            # which parser_for checks below; if it is neither, the error
            # lists the codes and the tags
            try:
                pack = Locale(code="cli_language", lexicon=Lexicon.empty(),
                              languages=frozenset({args.locale}))
            except (TypeError, ValueError):
                ap.error(unknown)  # exits 2, message to stderr
        # a strict call needs a language: a pack choosing none (zh, ja,
        # ru) chooses its own code, which parser_for checks below
        if args.strict and not pack.languages:
            try:
                pack = dataclasses.replace(
                    pack, languages=frozenset({pack.code}))
            except ValueError:
                ap.error(f"--strict needs a language to keep: the pack "
                         f"{pack.code!r} chooses none, and its code is not "
                         f"a language tag; give a tag instead (e.g. "
                         f"--locale {pack.code.split('_')[0]} --strict)")
        # The pack only activates division; the installed extra divides.
        # Without it a note says so in the command line's terms, in
        # place of the parser's warning (rules/D1), whose other remedies
        # are code; a print also shows where warnings are filtered out.
        if pack.code == "ja":
            if _ja_extra_installed():
                segmenter = locales.ja_segmenter()
            else:
                print(_NO_JA_EXTRA, file=sys.stderr)
                noted = True
    # The order and the switches are written into the pack's own patch,
    # so each replaces a pack's setting without a two-pack conflict
    # warning, and the parser is built once, parser_for re-emitting its
    # warnings (#337)
    chosen = vars(args)
    updates: dict[str, Any] = {
        field: chosen[field] for field in _SWITCHES
        if chosen[field] is not None}
    updates.update({
        field: enum(chosen[field]) for field, (enum, _) in _CHOICES.items()
        if chosen[field] is not None})
    if args.order is not None:
        updates["name_order"] = _ORDERS[args.order]
    if args.lone_name_word is not None:
        updates["lone_name_word"] = _LONE_NAME_WORD[args.lone_name_word]
    if updates:
        if pack is None:
            pack = Locale(code="cli_policy", lexicon=Lexicon.empty(),
                          policy=PolicyPatch(**updates))
        else:
            pack = dataclasses.replace(pack, policy=dataclasses.replace(
                pack.policy, **updates))
    packs = () if pack is None else (pack,)
    with warnings.catch_warnings():
        if noted:
            warnings.filterwarnings(
                "ignore", message="Policy.segment_scripts activates")
        try:
            parser = parser_for(*packs, segmenter=segmenter,
                                strict=args.strict)
        except ValueError as exc:
            # the choice's own refusal, without the pack wrapper naming
            # the CLI's stand-in code
            why = str(exc.__cause__ or exc).replace("strict=True", "--strict")
            ap.error(f"{unknown}; nor a language: {why}" if unknown else why)
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
