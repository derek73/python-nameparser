"""The script-property table (_policy._SCRIPT_PROPERTIES, #1256).

Each row's answers are checked through every reader that asks the
question the column holds, on a letter taken from the row's own ranges,
so a row whose ranges are not its script's, or a reader that has
stopped reading the table, fails here. A Latin letter, which no row
holds, is the control: each test asserts the answer the row changes
from it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import nameparser
from nameparser import Lexicon
from nameparser import _match, _render
from nameparser._policy import _SCRIPT_PROPERTIES, _ScriptRow
from nameparser._pipeline import _vocab
from nameparser._pipeline._vocab import (
    ambiguous_lean, is_initial, is_initial_shaped, is_one_case,
    is_title_shaped,
)

_LEX = Lexicon.default()
_ROWS = sorted(_SCRIPT_PROPERTIES.items())


def _letter(row: _ScriptRow, *, cased: bool | None = None) -> str:
    """The first character of the row's ranges that the initial SHAPE
    admits ('X.'), so a False answer is the row's and never the shape's;
    with `cased`, the first whose case Unicode answers that way."""
    for lo, hi in row.ranges:
        for cp in range(lo, hi + 1):
            c = chr(cp)
            if not is_initial_shaped(c + "."):
                continue
            if cased is None or (c.upper() != c.lower()) is cased:
                return c
    raise AssertionError(f"no initial-shaped letter in {row.ranges}")


def test_the_table_holds_rows() -> None:
    # an empty parametrize is a skip, not a failure
    assert len(_ROWS) >= 5


@pytest.mark.parametrize(("key", "row"), _ROWS, ids=[k for k, _ in _ROWS])
def test_every_row_states_its_reason_and_source(key: str,
                                                row: _ScriptRow) -> None:
    assert row.ranges and row.reason and row.source, key
    assert all(lo <= hi for lo, hi in row.ranges), key


def test_rows_do_not_overlap() -> None:
    """A codepoint answered by two rows would take whichever a reader
    selected first."""
    spans = sorted((lo, hi, key) for key, row in _ROWS for lo, hi in row.ranges)
    for (_, hi, a), (lo, _, b) in zip(spans, spans[1:]):
        assert hi < lo, f"rows {a} and {b} overlap"


@pytest.mark.parametrize(("key", "row"), _ROWS, ids=[k for k, _ in _ROWS])
def test_writes_initials_reaches_every_reader(key: str,
                                              row: _ScriptRow) -> None:
    """rules/T5's veto, rules/R7's initials() and the name match read
    the one column; 'J' is the control, an initial in all three."""
    c = _letter(row)
    for letter, writes in ((c, row.writes_initials), ("J", True)):
        assert is_initial(letter + ".") is writes, (key, letter)
        assert (not _render._initialless(letter)) is writes, (key, letter)
        assert (not _match._initialless(letter)) is writes, (key, letter)


@pytest.mark.parametrize(("key", "row"), _ROWS, ids=[k for k, _ in _ROWS])
def test_the_title_shape_reads_its_two_columns(key: str,
                                               row: _ScriptRow) -> None:
    """rules/H2's shape takes a run of two letters with a period only
    where the script writes period abbreviations and the run is not a
    spelled Latin initial; 'Xy.' is the control, a title by shape."""
    c = _letter(row)
    shaped = row.period_abbreviations and not row.spells_initials
    assert is_title_shaped(c + c + ".", _LEX) is shaped, key
    assert is_title_shaped("Xy.", _LEX)
    # rules/S3's joined shape asks the period-abbreviation column alone
    # ('X.Y.Z.' is the control)
    assert (_vocab.period_joined_vocab(f"{c}.{c}.", _LEX) == "shape") \
        is row.period_abbreviations, key
    assert _vocab.period_joined_vocab("X.Q.", _LEX) == "shape"


@pytest.mark.parametrize(("key", "row"), _ROWS, ids=[k for k, _ in _ROWS])
def test_has_case_reaches_every_contrast(key: str, row: _ScriptRow) -> None:
    """rules/S6's contrast is read at three sites, which drop a caseless
    row's letters alike: beside a word in capitals, a letter of a row
    whose case does not count leaves the name in one case. A Latin 'j'
    is the control, a contrast at all three."""
    if row.has_case is not False:
        pytest.skip("Unicode's case properties answer for this row")
    c = _letter(row, cased=True)
    for letter, contrast in ((c, False), ("j", True)):
        assert is_one_case([letter, "MA"]) is not contrast, (key, letter)
        assert _render._in_one_case(f"{letter} MA") is not contrast
        # a capital is a lean in a name of mixed case: a Latin one is
        # the credential's, a Mtavruli one none
        assert (ambiguous_lean(letter.upper(), False) is None) \
            is not contrast, (key, letter)
    # case repair (R4) writes the first letter of a row with no case in
    # its lower case, and title-cases a cased script's
    assert _render._capitalize(c.upper() + c) == c.lower() + c, key
    assert _render._capitalize("jj") == "Jj"


#: A character range written in source: two escapes, a pair of hex
#: literals (a tuple or `range(...)`), a chained comparison, or two
#: non-ASCII characters inside a bracketed class.
_RANGE_IN_SOURCE = re.compile(
    r"\\u([0-9a-fA-F]{4})-\\u([0-9a-fA-F]{4})"
    r"|\\U([0-9a-fA-F]{8})-\\U([0-9a-fA-F]{8})"
    r"|\(0x([0-9a-fA-F]+),\s*0x([0-9a-fA-F]+)\)"
    r"|0x([0-9a-fA-F]+)\s*<=\s*\w+\s*<=\s*0x([0-9a-fA-F]+)"
    r"|\[[^\]]*?([^\x00-\x7f])-([^\x00-\x7f])")

#: Ranges inside a row that answer some other question than the
#: table's, by the name they are bound to, each with its reason.
_OTHER_QUESTIONS = {
    "_THAI_MARKS": "the marks a Thai name writes after a stop (T8)",
    "_AFTER_A_CONSONANT": "the Thai vowel signs written after a "
                          "consonant, which the segmenter reads",
}


def _restated_rows(text: str) -> list[str]:
    """The rows a line of source restates a range of."""
    if any(f"{name} =" in text for name in _OTHER_QUESTIONS):
        return []
    found = []
    for m in _RANGE_IN_SOURCE.finditer(text):
        lo, hi = (int(x, 16) if len(x) > 1 else ord(x)
                  for x in [g for g in m.groups() if g][:2])
        found += [key for key, row in _ROWS
                  if any(lo <= b and a <= hi for a, b in row.ranges)]
    return found


@pytest.mark.parametrize(("planted", "rows"), [
    # the recorded control: what the scan sees and what it lets pass
    ("_X = re.compile('[\\u0e01-\\u0e5b]')", ["thai"]),
    ("_X = re.compile('[ก-๛]')", ["thai"]),
    ("_X = '[\\u10a0-\\u10ff]'", ["georgian"]),
    ("_X = ((0x0E00, 0x0E7F),)", ["thai"]),
    ("if 0x1000 <= cp <= 0x109f:", ["myanmar"]),
    ("_X = '[\\U00020000-\\U000323af]'", ["han"]),
    ("_X = '[\\u0300-\\u036f]'", []),         # outside every row
    ("_X = frozenset({'\\u30fb', '\\uff65'})", []),  # lone codepoints
    ("_THAI_MARKS = '[\\u0e31\\u0e34-\\u0e3a]'", []),  # named other question
])
def test_the_source_scan_sees_a_restated_range(planted: str,
                                               rows: list[str]) -> None:
    assert _restated_rows(planted) == rows


def test_a_reader_never_restates_a_row() -> None:
    """The questions the table answers are asked through it alone: no
    module but _policy names the constants the table replaced or writes
    a character range overlapping a row, which is how a second copy of
    a row would start (#1256), save the ranges `_OTHER_QUESTIONS` names.
    A lone codepoint is not a range: the halfwidth nakaguro U+FF65,
    which opens the katakana row, is a word separator in tokenize and
    render. A copy spelled some other way (a reader rebuilt from
    `_script_matcher`) is the behavior tests' to catch."""
    root = Path(nameparser.__file__).parent
    stale = re.compile(r"\b_NO_INITIALS\b|\b_INDIC_BRAHMIC\b")
    found = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "_policy.py" or path.parent.name == "config":
            continue
        for n, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if stale.search(line) or _restated_rows(line):
                found.append(f"{path.relative_to(root).as_posix()}:{n}")
    assert not found, found


def test_the_initial_reader_and_the_matcher_agree_on_every_letter() -> None:
    """_vocab's contains-any matcher and the whole-word matchers of
    _render and _match are built from the same spans."""
    for _, row in _ROWS:
        for lo, hi in row.ranges:
            for cp in (lo, hi, (lo + hi) // 2):
                c = chr(cp)
                assert (_vocab._has_initialless_char(c)
                        is _render._initialless(c)
                        is _match._initialless(c)
                        is (not row.writes_initials))


@pytest.mark.parametrize(("text", "field", "value"), [
    ("ดร. สมชาย ใจดี", "title", "ดร."),          # listed
    ("ร.ต.อ.สมชาย ใจดี", "title", "ร.ต.อ."),     # listed, glued
    ("กข. สมชาย ใจดี", "title", "กข."),          # unlisted, by H2's shape
    ("สมชาย ใจดี พ.บ.", "suffix", "พ.บ."),       # unlisted, by S3's shape
])
def test_a_script_with_no_initials_may_still_write_abbreviations(
        text: str, field: str, value: str) -> None:
    """Thai writes no initials but writes titles and degrees short with
    periods, so its two columns part (#1256): a reader that asked the
    initials column for an abbreviation question would move these."""
    from nameparser import parse
    name = parse(text)
    assert getattr(name, field) == value, (text, name)
    assert name.initials() == ""


#: Georgian beside its Arabic twin: a script the table gives no case
#: reads as a script Unicode gives none, at every name-level case
#: question that reads the name's case (#1222). Master (161ebd28) reads
#: eleven of these sixteen rows apart; the other five agreed there too
#: (MA, ჯეკ; the MD and III rows; ნინო SMITH; the Latin control). Not
#: an oracle where the two scripts differ in another column: Georgian
#: writes initials and Arabic's dotted runs read otherwise, so a
#: dotted run is held by its own test below, not by its twin.
_GEORGIAN = {"ჯეკ": "محمد", "ბერიძე": "علي", "ნინო": "حسن",
             "ᲑᲣᲠᲯᲐᲜᲐᲫᲔ": "فاطمة"}
_TWIN_SHAPES = (
    "ჯეკ MA", "ჯეკ, MA", ", ჯეკ MA", "MA, ჯეკ", "ჯეკ ბერიძე MA",
    "ბერიძე, ჯეკ MA", "ჯეკ DO",
    "ჯეკ ბერიძე Jr. ნინო", "ჯეკ ბერიძე MD ნინო", "ჯეკ ბერიძე III ნინო",
    "ჯეკ ბერიძე MA ნინო", "ჯეკ ბერიძე Phd ნინო",   # S8's name behind
    "ნინო SMITH", "ნინო ᲑᲣᲠᲯᲐᲜᲐᲫᲔ MA", "ჯეკ, ნინო MA",
    "ნინო Smith MA",                       # control: Latin case speaks
)


def _shape(text: str, order: tuple[object, ...]) -> tuple[object, ...]:
    from nameparser import Parser, Policy
    name = Parser(policy=Policy(name_order=order)).parse(text)  # type: ignore[arg-type]
    return (tuple(len(getattr(name, f).split()) for f in
                  ("title", "given", "middle", "family", "suffix")),
            tuple(a.kind for a in name.ambiguities),
            len(name.initials().split()))


@pytest.mark.parametrize("text", _TWIN_SHAPES)
def test_georgian_reads_as_its_arabic_twin(text: str) -> None:
    from nameparser import FAMILY_FIRST, GIVEN_FIRST
    twin = text
    for ka, ar in _GEORGIAN.items():
        twin = twin.replace(ka, ar)
    for order in (GIVEN_FIRST, FAMILY_FIRST):
        assert _shape(text, order) == _shape(twin, order), (text, twin)


#: The twin test's recorded negative control (AGENTS.md's guard tests):
#: how many of `_TWIN_SHAPES` read apart from their Arabic twin under
#: either order with the caseless table emptied, which is master's
#: answer at every site that reads it. Re-take it when a shape is added.
_UNGUARDED_EFFECT = 11


def test_the_twin_test_fails_with_the_table_off() -> None:
    from nameparser import FAMILY_FIRST, GIVEN_FIRST
    from nameparser import _policy
    saved = dict(_policy._CASELESS_LETTERS)
    _policy._CASELESS_LETTERS.clear()    # the readers hold this object
    try:
        apart = 0
        for text in _TWIN_SHAPES:
            twin = text
            for ka, ar in _GEORGIAN.items():
                twin = twin.replace(ka, ar)
            apart += any(_shape(text, o) != _shape(twin, o)
                         for o in (GIVEN_FIRST, FAMILY_FIRST))
    finally:
        _policy._CASELESS_LETTERS.update(saved)
    assert apart == _UNGUARDED_EFFECT


def test_a_reader_selecting_no_span_is_refused() -> None:
    """A column no row holds the selected value of compiles to an empty
    class, which would match nothing in silence."""
    from nameparser._policy import _ranges_pattern, _ranges_where
    assert _ranges_where("has_case", True) == ()
    with pytest.raises(ValueError, match="at least one range"):
        _ranges_pattern(_ranges_where("has_case", True))


@pytest.mark.parametrize(("text", "given", "middle", "initials"), [
    # a Georgian dotted run is initials, as on master: the run asks
    # Unicode's case, Georgian writing initials in its one case (#1256)
    ("ნ.ბ. ბერიძე", "ნ.", "ბ.", "ნ. ბ. ბ."),
    ("ბერიძე, ა.ბ.", "ა.", "ბ.", "ა. ბ. ბ."),
    ("ა.ბ. ბერიძე ნინო", "ა.", "ბ. ბერიძე", "ა. ბ. ბ. ნ."),
    ("j.r. ბერიძე", "j.", "r.", "j. r. ბ."),
])
def test_a_georgian_run_of_initials_reads_as_initials(
        text: str, given: str, middle: str, initials: str) -> None:
    from nameparser import parse
    name = parse(text)
    assert (name.given, name.middle, name.initials()) == (
        given, middle, initials), text
    # its letters in R3's run of initials, as initials() reads them
    assert parse("ნინო ბერიძე ა.ბ.").initials() == "ნ. ბ. ა. ბ."
