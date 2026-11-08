"""Whether these tests sit in a checkout, beside the source package.

A downstream packager runs the suite against the INSTALLED package,
with tests/, tools/ and a few files copied beside it and no nameparser/
source package (Debian's autopkgtest; CI's installed-package job runs
the same layout). A test reads the package through the module it
imports, `Path(module.__file__)`, so that it works in both layouts. A
test whose subject is the checkout itself -- the vocabulary build,
which reads the TOML and writes the generated modules beside it; the
differential harness, which refuses a nameparser imported from
anywhere else; prose under docs/ -- skips there instead, through
`require_checkout` for a module or `needs_checkout` for a test.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The source package's own file, not its folder: the installed-package
# layout keeps nameparser/vocab/README.md beside the tests, so the folder
# exists there with no package in it.
HAS_CHECKOUT = (ROOT / "nameparser" / "__init__.py").is_file()

REASON = ("reads the checkout (the nameparser source package or docs/), "
          "which a run against the installed package does not have")

needs_checkout = pytest.mark.skipif(not HAS_CHECKOUT, reason=REASON)


def require_checkout() -> None:
    """Skip the calling test module outside a checkout."""
    if not HAS_CHECKOUT:
        pytest.skip(REASON, allow_module_level=True)
