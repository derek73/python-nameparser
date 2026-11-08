from pathlib import Path

import nameparser
from tests.checkout import HAS_CHECKOUT, HAS_DOCS, ROOT


def test_the_checkout_flag_is_where_nameparser_was_imported_from() -> None:
    # HAS_CHECKOUT decides which tests run, so where it says True the
    # package under test must be this checkout's: a run that imports
    # another tree's would test that tree. (Where it says False there is
    # no package here to import, so that side needs no check.)
    imported = Path(nameparser.__file__).resolve().parent
    here = ROOT / "nameparser"
    if HAS_CHECKOUT:
        assert imported == here, (
            f"nameparser was imported from {imported}, not from this "
            f"checkout's {here}: the environment's install points at another "
            "tree (an editable install from a different worktree, or a "
            "PYTHONPATH). Run `uv sync` in this checkout, or unset PYTHONPATH.")


def test_a_whole_tree_has_the_source_and_the_docs() -> None:
    # A skip passes, so a flag computed from the wrong path would turn
    # the tests it gates into skips without failing anything. A whole
    # tree -- a git checkout, or an export of one like CI's source-tree
    # job -- holds the README beside tools/, and always the source and
    # the docs; a packager's layout copies tools/ without the README,
    # and an sdist the README without tools/, and either may lack both.
    if (ROOT / "README.rst").is_file() and (ROOT / "tools").is_dir():
        assert HAS_CHECKOUT and HAS_DOCS, (HAS_CHECKOUT, HAS_DOCS)
