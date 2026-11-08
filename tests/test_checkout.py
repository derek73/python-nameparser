from pathlib import Path

import nameparser
from tests.checkout import HAS_CHECKOUT, HAS_DOCS, ROOT


def test_the_checkout_flag_is_where_nameparser_was_imported_from() -> None:
    # HAS_CHECKOUT decides which tests skip, and a skip passes, so a flag
    # that read False in a checkout would turn every checkout-only test
    # into a skip without failing anything. It must say True exactly
    # where the package imported is this checkout's, and False where it
    # is an installed one (CI's installed-package job).
    imported = Path(nameparser.__file__).resolve().parent
    here = ROOT / "nameparser"
    if HAS_CHECKOUT:
        assert imported == here, (
            f"nameparser was imported from {imported}, not from this "
            f"checkout's {here}: the environment's install points at another "
            "tree (an editable install from a different worktree, or a "
            "PYTHONPATH). Run `uv sync` in this checkout, or unset PYTHONPATH.")
    else:
        assert imported != here, imported


def test_a_git_checkout_has_the_source_and_the_docs() -> None:
    # The converse guard: a git checkout always holds both, so a flag
    # computed from the wrong path fails here rather than skipping the
    # tests it gates. An export with no repository (CI's source-tree
    # job, a packager's layout) has nothing to compare with.
    if (ROOT / ".git").exists():
        assert HAS_CHECKOUT and HAS_DOCS, (HAS_CHECKOUT, HAS_DOCS)
