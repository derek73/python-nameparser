"""tools/docs_scan.py, the readability scan of docs/*.rst.

The scan lists candidates, so the failure that matters is a miss: a
long paragraph, cell or section it walks past, which reads as a clean
page. Each kind has a row that must be found and a short twin that must
not, and the directive bodies it does not read are held unread.

tools/ is not a package, so the module is loaded by path.
"""
from pathlib import Path
from types import ModuleType

import pytest

from tests.checkout import needs_checkout

from ._differential_fixtures import load_by_path

_PATH = Path(__file__).parents[2] / "tools" / "docs_scan.py"

_LONG = " ".join(["word"] * 30)          # thirty words
_SIXTY = f"{_LONG}\n{_LONG}"

_PAGE = f"""\
=====
Title
=====

A short paragraph of a few words.

{_SIXTY}

- a short item
- {_LONG}
  {_LONG}
- another short item, measured on 2026-11-15

  A second paragraph of the item, which is long:
  {_LONG}
  {_LONG}

  - a nested item that is long too
    {_LONG}
    {_LONG}

.. doctest::

    >>> "{_LONG} {_LONG}"
    '...'
    2026-01-01

A command::

    {_LONG}
    {_LONG} 2026-02-02

.. list-table::
   :header-rows: 1

   * - Code
     - Turns on
   * - ``xx``
     - {_LONG}

       - a bullet inside the cell
       - and another, dated 2026-03-03
   * - ``yy``
     - short

.. warning::

   {_LONG}
   {_LONG}

Second
------

.. _a-label:

{_LONG}

.. a comment that is long {_LONG}
   {_LONG}
"""


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return load_by_path("docs_scan", _PATH)


@needs_checkout
def test_each_kind_is_found_and_its_short_twin_is_not(
        tool: ModuleType) -> None:
    found = tool.scan(_PAGE, paragraph=50, cell=25, section=12)
    assert [(f.line, f.kind) for f in found] == [
        (2, "SECTION"),   # the title, under its overline
        (7, "PARA"),      # the sixty-word paragraph, not the short one
        (11, "ITEM"),     # the long bullet alone
        (13, "DATE"),     # in a list item
        (15, "ITEM"),     # an item's second paragraph
        (19, "ITEM"),     # a nested item
        (40, "CELL"),     # one cell, its nested bullets inside it
        (40, "DATE"),     # a date in that cell
        (49, "ITEM"),     # a warning's body is prose
    ]
    by_line = {(f.line, f.kind): f.detail for f in found}
    assert by_line[7, "PARA"].startswith("60 words")
    assert by_line[40, "CELL"].startswith("41 words")
    assert "2026-11-15" in by_line[13, "DATE"]
    # unread: the doctest and its date, the literal block after `::` and
    # its date, the comment, and the label
    assert not {23, 25, 26, 27, 29, 31, 32, 55, 59, 60} & {
        f.line for f in found}


@needs_checkout
def test_a_limit_is_exceeded_not_met(tool: ModuleType) -> None:
    page = (f"Title\n=====\n\n{_LONG}\n\n"
            f".. list-table::\n\n   * - {_LONG}\n")
    assert tool.scan(page, paragraph=30, cell=30, section=1) == []
    assert [f.kind for f in tool.scan(page, paragraph=29, cell=29,
                                      section=0)] == [
        "SECTION", "PARA", "CELL"]


@needs_checkout
def test_an_item_ends_at_the_next_marker_at_any_indent(
        tool: ModuleType) -> None:
    ten = " ".join(["word"] * 10)
    # a nested bullet, then numbered steps at the margin with no blank
    # line between: one block, four items of about ten words each
    page = (f"#. {ten}\n\n   - {ten}\n   - {ten}\n#. {ten}\n#. {ten}\n")
    assert tool.scan(page, paragraph=12) == []
    # and a long one among them is found at its own line, alone
    long_step = page.replace(f"#. {ten}\n#. {ten}\n",
                             f"#. {ten} {ten}\n#. {ten}\n")
    assert [(f.line, f.kind) for f in tool.scan(long_step, paragraph=12)
            ] == [(5, "ITEM")]
    # a parent item and the bullets nested under it with no blank line
    # are measured apart too
    nested = f"- {ten}\n  - {ten}\n  - {ten}\n"
    assert tool.scan(nested, paragraph=12) == []


@needs_checkout
def test_a_table_is_read_cell_by_cell(tool: ModuleType) -> None:
    half = " ".join(["word"] * 20)
    page = f".. list-table::\n\n   * - {half}\n     - {half}\n"
    # forty words in the row, twenty in each cell
    assert tool.scan(page, cell=25) == []
    assert [(f.line, f.kind) for f in tool.scan(page, cell=19)] == [
        (3, "CELL"), (4, "CELL")]


@needs_checkout
@pytest.mark.parametrize("text, dated", [
    ("Counted 2026-11-15.", True),
    ("Issue 1203-11-15 and 12026-11-150 are no dates.", False),
], ids=["a-date", "not-dates"])
def test_only_an_iso_date_of_this_century_is_a_date(
        tool: ModuleType, text: str, dated: bool) -> None:
    assert bool(tool.scan(text)) is dated


@needs_checkout
def test_nothing_is_flagged_under_the_limits(tool: ModuleType) -> None:
    quiet = "Title\n=====\n\nA short paragraph.\n\n- one\n- two\n"
    assert tool.scan(quiet) == []
    # the same long text passes once every limit is above it, and reads
    # alike with Windows line ends
    high = dict(paragraph=500, cell=500, section=500)
    assert {f.kind for f in tool.scan(_PAGE, **high)} == {"DATE"}
    assert tool.scan(_PAGE.replace("\n", "\r\n"), paragraph=50, cell=25,
                     section=12) == tool.scan(_PAGE, paragraph=50, cell=25,
                                              section=12)


@needs_checkout
def test_the_command_counts_every_page_and_lists_the_ones_named(
        tool: ModuleType, tmp_path: Path,
        capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "long.rst").write_text(_PAGE, encoding="utf-8")
    (tmp_path / "short.rst").write_text("T\n=\n\nShort.\n", encoding="utf-8")
    (tmp_path / "release_log.rst").write_text(_PAGE, encoding="utf-8")
    assert tool.main(["long.rst", "--docs", str(tmp_path),
                      "--paragraph", "50", "--cell", "25"]) == 0
    out = capsys.readouterr().out
    assert "long.rst" in out and "short.rst" in out
    assert "release_log.rst" not in out          # a list by nature
    assert "docs/long.rst:7: PARA" in out
    for name, message in [
            ("missing.rst", "no such page to scan: missing.rst"),
            ("release_log.rst", "release_log.rst is not scanned")]:
        with pytest.raises(SystemExit):
            tool.main([name, "--docs", str(tmp_path)])
        assert message in capsys.readouterr().err
    # a folder with nothing to scan is an error, never a clean result
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit):
        tool.main(["--docs", str(empty)])
    assert "no page to scan" in capsys.readouterr().err
