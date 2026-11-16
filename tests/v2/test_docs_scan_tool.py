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

_LONG = " ".join(["word"] * 30)

_PAGE = f"""\
Title
=====

A short paragraph of a few words.

{_LONG}
{_LONG}

- a short item
- {_LONG}
  {_LONG}
- another short item, measured on 2026-11-15

.. doctest::

    >>> "{_LONG} {_LONG}"
    '...'
    2026-01-01

.. list-table::
   :header-rows: 1

   * - Code
     - Turns on
   * - ``xx``
     - {_LONG}
   * - ``yy``
     - short

Second
------

.. _a-label:

{_LONG}
"""


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return load_by_path("docs_scan", _PATH)


@needs_checkout
def test_each_kind_is_found_and_its_short_twin_is_not(
        tool: ModuleType) -> None:
    found = tool.scan(_PAGE, paragraph=50, cell=25, section=3)
    assert [(f.line, f.kind) for f in found] == [
        (1, "SECTION"),   # six lines of prose under the title
        (6, "PARA"),      # the sixty-word paragraph, not the short one
        (10, "ITEM"),     # the long bullet alone
        (12, "DATE"),     # in a list item
        (20, "CELL"),     # the long cell; the doctest's text is unread
    ]
    assert "60 words" in found[1].detail
    assert "2026-11-15" in found[3].detail


@needs_checkout
def test_nothing_is_flagged_under_the_limits(tool: ModuleType) -> None:
    quiet = "Title\n=====\n\nA short paragraph.\n\n- one\n- two\n"
    assert tool.scan(quiet) == []
    # the same long text passes once every limit is above it
    assert [f.kind for f in tool.scan(_PAGE, paragraph=500, cell=500,
                                      section=500)] == ["DATE"]


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
    assert "docs/long.rst:6: PARA" in out
    with pytest.raises(SystemExit):
        tool.main(["missing.rst", "--docs", str(tmp_path)])
    assert "no such page to scan: missing.rst" in capsys.readouterr().err
