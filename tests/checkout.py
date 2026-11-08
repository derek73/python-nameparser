"""Whether these tests sit in a checkout, beside the source package and
the user docs.

A downstream packager runs the suite against the INSTALLED package,
with tests/, tools/ and a few files copied beside it and no nameparser/
source package (Debian's autopkgtest; CI's installed-package job runs
the same layout). Its build-time run is a third layout: the built
package beside the tests, and still no user docs (docs/design/ is
copied, docs/*.rst is not). So there are two questions, each with its
flag:

- `HAS_CHECKOUT`: is the source package here? A test reads the package
  through the module it imports, `Path(module.__file__)`, so that it
  works either way; a test whose subject is the source tree -- the
  vocabulary build, which reads the TOML and writes the generated
  modules beside it; the differential harness, which refuses a
  nameparser imported from anywhere else; the citation comments in the
  source -- skips without it, through `require_checkout` for a module
  or `needs_checkout` for a test.
- `HAS_DOCS`: are the user docs here? A test reading docs/*.rst skips
  without them, through `needs_docs`.

tests/test_checkout.py holds both flags to what a whole tree has (a git
checkout, or an export of one), so neither can turn tests into skips
there without failing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The source package's own file, not its folder: the installed-package
# layout keeps nameparser/vocab/README.md beside the tests, so the folder
# exists there with no package in it.
HAS_CHECKOUT = (ROOT / "nameparser" / "__init__.py").is_file()

# The Sphinx configuration, which no packager's test layout copies.
HAS_DOCS = (ROOT / "docs" / "conf.py").is_file()

REASON = ("reads the nameparser source tree, which a run against the "
          "installed package does not have")
DOCS_REASON = "reads the user docs (docs/*.rst), which this layout does not have"

needs_checkout = pytest.mark.skipif(not HAS_CHECKOUT, reason=REASON)
needs_docs = pytest.mark.skipif(not HAS_DOCS, reason=DOCS_REASON)


def require_checkout() -> None:
    """Skip the calling test module outside a checkout."""
    if not HAS_CHECKOUT:
        pytest.skip(REASON, allow_module_level=True)
