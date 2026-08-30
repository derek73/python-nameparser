"""Pins the pipeline's hand-duplicated regex/table copies to their
nameparser.config.regexes source of truth.

The 2.0 layering rule forbids nameparser._pipeline/_render importing
nameparser.config directly, so several patterns and tables are copied
by hand into the modules that need them, each with a "keep in sync by
hand" comment. Nothing previously enforced that promise: if
config/regexes.py changed, the copies would silently diverge with no
CI signal. Tests may legally import both sides (test_layering.py's own
convention), so this module is where the promise gets checked.

Layering is the usual reason for a copy but not the only one, so the
scope here is the PROMISE rather than that one pair of packages: the
comma-set pin below reads _pipeline._state instead of config.

The differential harness makes the same kind of copy by hand, into
files that could not import a Python constant if they wanted to. Those
are pinned in test_ledger_guards.py, which shares nothing with this
module but the idea (#352).
"""
import pathlib
import re

import pytest

from nameparser.config import regexes as _config
from nameparser._pipeline import (
    _assemble, _assign, _classify, _extract, _group, _pieces,
    _post_rules, _script_segment, _segment, _state, _tokenize, _vocab,
)
import nameparser._pipeline
from nameparser import _render


def test_emoji_ranges_match_config() -> None:
    assert _tokenize._EMOJI_RANGES == _config._EMOJI_RANGES


def test_bidi_pattern_matches_config() -> None:
    assert _tokenize._BIDI.pattern == _config.re_bidi.pattern
    assert _tokenize._BIDI.flags == _config.re_bidi.flags


def test_period_not_at_end_matches_config() -> None:
    source = _config.REGEXES["period_not_at_end"]
    assert _vocab._PERIOD_NOT_AT_END.pattern == source.pattern
    assert _vocab._PERIOD_NOT_AT_END.flags == source.flags


def test_period_abbreviation_matches_config() -> None:
    source = _config.REGEXES["period_abbreviation"]
    assert _pieces._PERIOD_ABBREV.pattern == source.pattern
    assert _pieces._PERIOD_ABBREV.flags == source.flags


def test_roman_numeral_matches_config() -> None:
    source = _config.REGEXES["roman_numeral"]
    assert _vocab._ROMAN.pattern == source.pattern
    assert _vocab._ROMAN.flags == source.flags


def test_patronymic_patterns_match_config() -> None:
    pairs = (
        (_post_rules._EAST_SLAVIC, "east_slavic_patronymic"),
        (_post_rules._EAST_SLAVIC_CYR, "east_slavic_patronymic_cyrillic"),
        (_post_rules._TURKIC, "turkic_patronymic_marker"),
        (_post_rules._TURKIC_CYR, "turkic_patronymic_marker_cyrillic"),
    )
    for copy, key in pairs:
        source = _config.REGEXES[key]
        assert copy.pattern == source.pattern, key
        assert copy.flags == source.flags, key


def test_initial_copy_matches_config_minus_the_empty_alternative() -> None:
    # _vocab._INITIAL is v1's "initial" pattern minus its trailing "?"
    # (documented at the definition: its callers always fullmatch a
    # non-empty token, so the empty-string alternative is dropped on
    # purpose). Assert the exact, documented relationship to the config
    # source, so a future edit to either side that breaks the
    # relationship fails loudly here instead of silently drifting.
    # There was a second copy, in _render, and this test also asserted
    # the two agreed. It went with #458: case repair stopped asking
    # whether a word is initial-shaped -- classify records that, and a
    # view reads the tag -- leaving the constant with no reader. A copy
    # kept alive for its own sync assertion pins nothing about
    # behavior, so it was deleted rather than commented.
    source = _config.REGEXES["initial"]
    # config's pattern is the pipeline copy with an extra "?" spliced in
    # just before the trailing "$", making the whole group optional.
    trimmed = _vocab._INITIAL.pattern
    reconstructed = trimmed[:-1] + "?" + trimmed[-1:]
    assert source.pattern == reconstructed
    assert source.flags == _vocab._INITIAL.flags


# The roster above grew one test at a time, and four hand-copies were
# never added to it -- _render's _SPACES, _SPACE_BEFORE_COMMA, _MAC and
# _WORD. They had not diverged, but nothing would have said so, which
# is the exact promise this module exists to keep. All four mirror a
# config key whose only other reader was v1's parser.py, deleted at the
# M11 swap, so nothing else touches them either.
#
# Declared as a roster rather than one test per copy, with a
# completeness check below: adding a pattern without declaring its
# source now fails here instead of being silently unpinned.
_SOURCES: dict[tuple[str, str], str | None] = {
    ("_pieces", "_PERIOD_ABBREV"): "period_abbreviation",
    ("_group", "_D"): None,
    ("_vocab", "_DOTTED"): None,
    ("_group", "_PH"): None,
    ("_vocab", "_ROMAN"): "roman_numeral",
    ("_post_rules", "_EAST_SLAVIC"): "east_slavic_patronymic",
    ("_post_rules", "_EAST_SLAVIC_CYR"): "east_slavic_patronymic_cyrillic",
    ("_post_rules", "_TURKIC"): "turkic_patronymic_marker",
    ("_post_rules", "_TURKIC_CYR"): "turkic_patronymic_marker_cyrillic",
    ("_render", "_SPACES"): "spaces",
    ("_render", "_SPACE_BEFORE_COMMA"): "space_before_comma",
    ("_render", "_MAC"): "mac",
    ("_render", "_WORD"): "word",
    ("_vocab", "_PERIOD_NOT_AT_END"): "period_not_at_end",
    # Deliberately NOT a straight copy -- pinned by the dedicated tests
    # above, which assert the documented RELATIONSHIP instead:
    ("_vocab", "_INITIAL"): None,       # config's pattern minus one "?"
    ("_tokenize", "_BIDI"): None,       # re_bidi, not a REGEXES key
    # Mirrors _pipeline._state.COMMA_CHARS, not nameparser.config
    ("_render", "_COMMA_CHAR"): None,
}

def test_every_pipeline_module_is_scanned_for_hand_copies() -> None:
    """The twin of test_layering's completeness check, in the file with
    the same shape of registry.

    test_every_hand_copied_pattern_is_declared iterates _MODULES, so a
    module absent from that dict is not scanned loosely -- it is not
    scanned at all, and an undeclared hand copy of a config regex in it
    goes unpinned. Measured on a scratch copy: a new pipeline module
    carrying a wrong copy of the mac pattern passed all 20 tests here.

    Scoped to _pipeline/ for the same reason the layering twin is: it
    is where a new module is a design decision. The directory is
    derived from the imported subpackage and the floor is asserted --
    Path.glob on a missing directory returns empty rather than raising,
    which would make this pass for every possible _MODULES.
    """
    pipeline_dir = pathlib.Path(nameparser._pipeline.__file__).parent
    shipped = {p.stem for p in pipeline_dir.glob("*.py")
               if p.stem != "__init__"}
    assert "_group" in shipped, (
        f"the glob matched no pipeline modules, so this check can no "
        f"longer fail: {sorted(shipped)}")
    missing = sorted(shipped - set(_MODULES))
    assert not missing, (
        f"pipeline modules absent from _MODULES, and therefore never "
        f"scanned for undeclared hand copies of a config regex: "
        f"{missing}. Add each one; a module with no hand copies costs "
        f"nothing to scan"
    )


_MODULES = {"_assemble": _assemble, "_assign": _assign,
            "_classify": _classify, "_extract": _extract,
            "_group": _group, "_pieces": _pieces,
            "_post_rules": _post_rules, "_render": _render,
            "_script_segment": _script_segment, "_segment": _segment,
            "_state": _state, "_tokenize": _tokenize, "_vocab": _vocab}


@pytest.mark.parametrize(
    "where,key", [(w, k) for w, k in _SOURCES.items() if k is not None],
    ids=lambda v: v if isinstance(v, str) else f"{v[0]}.{v[1]}")
def test_declared_copy_matches_its_config_source(
        where: tuple[str, str], key: str) -> None:
    copy = getattr(_MODULES[where[0]], where[1])
    source = _config.REGEXES[key]
    assert copy.pattern == source.pattern, f"{where[1]} vs REGEXES[{key!r}]"
    assert copy.flags == source.flags, f"{where[1]} vs REGEXES[{key!r}]"


def test_every_hand_copied_pattern_is_declared() -> None:
    """The roster must cover every compiled pattern in these modules.

    Without this, the roster is just another list that a new constant
    can be left out of -- which is how the four above went unpinned.
    """
    undeclared = [
        (name, attr)
        for name, mod in _MODULES.items()
        for attr, value in vars(mod).items()
        if attr.startswith("_") and not attr.startswith("__")
        and isinstance(value, re.Pattern)
        and (name, attr) not in _SOURCES
    ]
    assert not undeclared, (
        f"compiled patterns missing from _SOURCES: {undeclared}. Add each "
        f"with its nameparser.config.regexes key, or None if it has no "
        f"config counterpart.")


def test_comma_char_matches_the_pipeline_comma_set() -> None:
    # _render splits on the same comma characters segment does; the set
    # lives in _state, so this one is pinned against that, not config.
    from nameparser._pipeline._state import COMMA_CHARS

    assert set(_render._COMMA_CHAR.pattern.strip("[]")) == set(COMMA_CHARS)
