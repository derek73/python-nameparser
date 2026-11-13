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


def test_the_twin_test_fails_with_the_table_off(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Each reader's own binding of the caseless-letter map is replaced
    by an empty one for this test alone (monkeypatch restores them
    whatever happens), the shared map being read-only."""
    from nameparser import FAMILY_FIRST, GIVEN_FIRST
    from nameparser._pipeline import _pieces
    for module in (_vocab, _pieces, _render):
        assert hasattr(module, "_CASELESS_LETTERS"), module
        monkeypatch.setattr(module, "_CASELESS_LETTERS", {})
    apart = 0
    for text in _TWIN_SHAPES:
        twin = text
        for ka, ar in _GEORGIAN.items():
            twin = twin.replace(ka, ar)
        apart += any(_shape(text, o) != _shape(twin, o)
                     for o in (GIVEN_FIRST, FAMILY_FIRST))
    assert apart == _UNGUARDED_EFFECT


def test_every_reader_of_the_caseless_map_is_patched_above() -> None:
    """The control above empties the map in the modules it names, so a
    new module reading it must join them, or the control would measure
    a table only partly off."""
    root = Path(nameparser.__file__).parent
    readers = sorted(p.relative_to(root).as_posix()
                     for p in root.rglob("*.py")
                     if "_CASELESS_LETTERS" in p.read_text(encoding="utf-8")
                     and p.name != "_policy.py")
    assert readers == ["_pipeline/_pieces.py", "_pipeline/_vocab.py",
                       "_render.py"], readers


def test_a_column_with_no_row_fails_the_import_by_name() -> None:
    from nameparser._policy import _read_spans
    with pytest.raises(ValueError, match="has_case=True.*add the row"):
        _read_spans("has_case", True)


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


# Each row's values pinned by a reading, so a wrong value fails here and
# not only a reader that stopped reading the row (the per-column tests
# above compare a reader with the row's own value, which a wrong value
# passes).
@pytest.mark.parametrize(("text", "field", "value"), [
    # brahmic writes period abbreviations: S3's joined shape reads a
    # dotted run of bare letters as a credential, as on master
    ("राम शर्मा क.ख.", "suffix", "क.ख."),
    # myanmar writes period abbreviations, not decided otherwise: H2's
    # shape reads an unlisted run of consonants with a period as a title
    ("ကက. ဌေး", "title", "ကက."),
    # georgian has no case for the contrast (#1222)
    ("ჯეკ MA", "family", "MA"),
    # thai and myanmar write no initials (#1256's amendment)
    ("สมชาย ใจดี", "initials", ""),
    ("ကြည် ကြည် ဌေး", "initials", ""),
])
def test_each_row_is_pinned_by_a_reading(text: str, field: str,
                                         value: str) -> None:
    from nameparser import parse
    name = parse(text)
    got = name.initials() if field == "initials" else getattr(name, field)
    assert got == value, (text, name)


def _letters(row: _ScriptRow) -> list[str]:
    """The first and last initial-shaped letter of every span of the
    row, so a span dropped or cut short fails."""
    out = []
    for lo, hi in row.ranges:
        shaped = [chr(cp) for cp in range(lo, hi + 1)
                  if is_initial_shaped(chr(cp) + ".")]
        out += shaped[:1] + shaped[-1:]
    return out


@pytest.mark.parametrize(("key", "row"), _ROWS, ids=[k for k, _ in _ROWS])
def test_every_span_of_a_row_answers_at_both_ends(key: str,
                                                  row: _ScriptRow) -> None:
    for c in _letters(row):
        assert is_initial(c + ".") is row.writes_initials, (key, hex(ord(c)))


def test_every_mtavruli_letter_repairs_to_mkhedruli() -> None:
    """rules/R4 over the whole Mtavruli block: every one of its letters
    that Unicode cases opens a word written in Mkhedruli (#1223)."""
    letters = [chr(cp) for cp in range(0x1C90, 0x1CC0)
               if chr(cp).upper() != chr(cp).lower()]
    assert len(letters) == 46
    for c in letters:
        assert _render._capitalize(c + "ა") == c.lower() + "ა", hex(ord(c))


#: Script members whose spans no row holds, each answering every
#: column by default (has case where Unicode gives it, writes initials
#: and period abbreviations), with the reason that is right.
_SCRIPTS_WITH_NO_ROW = {
    "cyrillic": "Cyrillic names abbreviate: А. С. Пушкин",
}


def test_every_script_member_has_a_row_or_a_stated_default() -> None:
    """A Script member must not inherit the table's answers in silence:
    its spans fall in a row, or it is named above with its reason. The
    rows are keyed privately, so this binds the enum to the table by
    span, as the test this replaced bound it to _NO_INITIALS (#1256)."""
    from nameparser import Script
    from nameparser._policy import _SCRIPT_RANGES
    covered = [span for _, row in _ROWS for span in row.ranges]
    for script in Script:
        inside = all(any(a <= lo and hi <= b for a, b in covered)
                     for lo, hi in _SCRIPT_RANGES[script])
        assert inside or script.value in _SCRIPTS_WITH_NO_ROW, (
            f"{script} has no row in _policy._SCRIPT_PROPERTIES: decide "
            "its answers and add a row, or name it in "
            "_SCRIPTS_WITH_NO_ROW with the reason the defaults are right")
    # the Cyrillic control: a default script's letter is an initial
    assert is_initial("А.") and is_initial("Й.")


#: Each row's script by the Unicode character names of its letters,
#: independent of the row's own spans, so a span dropped or cut short
#: leaves a letter of the script outside the row.
_ROW_LETTER_NAMES = {
    "myanmar": ("MYANMAR LETTER",),
    "thai": ("THAI CHARACTER",),
    "georgian": ("GEORGIAN LETTER", "GEORGIAN MTAVRULI CAPITAL LETTER"),
    "brahmic": tuple(f"{s} LETTER" for s in (
        "DEVANAGARI", "BENGALI", "GURMUKHI", "GUJARATI", "ORIYA", "TAMIL",
        "TELUGU", "KANNADA", "MALAYALAM", "SINHALA")),
}


#: Letters of a row's script its spans leave out, each with its reason.
_OUTSIDE_A_ROW = {
    0xA8FE: "DEVANAGARI LETTER AY, in Devanagari Extended, outside the ten "
            "main blocks rules/H2's Except names (#1191)",
}


@pytest.mark.parametrize("key", sorted(_ROW_LETTER_NAMES))
def test_every_letter_of_a_row_script_is_in_the_row(key: str) -> None:
    import sys
    import unicodedata
    row = _SCRIPT_PROPERTIES[key]
    letters = [cp for cp in range(sys.maxunicode + 1)
               if unicodedata.name(chr(cp), "").startswith(
                   _ROW_LETTER_NAMES[key])
               and unicodedata.category(chr(cp)).startswith("L")]
    assert letters
    outside = [hex(cp) for cp in letters
               if not any(lo <= cp <= hi for lo, hi in row.ranges)
               and cp not in _OUTSIDE_A_ROW]
    assert not outside, (key, outside[:5])
