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


def test_a_reader_never_restates_a_row() -> None:
    """The questions the table answers are asked through it alone: no
    module but _policy names the constants the table replaced or opens a
    character range at a row's first codepoint, which is how a second
    copy of a row would start (#1256). A lone codepoint is not a range:
    the halfwidth nakaguro U+FF65, which opens the katakana row, is a
    word separator in tokenize and render."""
    root = Path(nameparser.__file__).parent
    starts = {lo for _, row in _ROWS for lo, _ in row.ranges}
    escapes = re.compile("|".join(
        rf"\\u{lo:04x}-|\\U{lo:08x}-|\(0x{lo:04x},"
        for lo in sorted(starts)), re.IGNORECASE)
    stale = re.compile(r"\b_NO_INITIALS\b|\b_INDIC_BRAHMIC\b")
    found = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "_policy.py" or path.parent.name == "config":
            continue
        text = path.read_text(encoding="utf-8")
        if stale.search(text) or escapes.search(text):
            found.append(path.relative_to(root).as_posix())
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
