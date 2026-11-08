from pathlib import Path

import nameparser
from tests.checkout import HAS_CHECKOUT, ROOT


def test_the_checkout_flag_is_where_nameparser_was_imported_from() -> None:
    # HAS_CHECKOUT decides which tests skip, and a skip passes, so a flag
    # that read False in a checkout would turn every checkout-only test
    # into a skip without failing anything. It must say True exactly
    # where the package imported is this checkout's, and False where it
    # is an installed one (CI's installed-package job).
    imported = Path(nameparser.__file__).resolve().parent
    assert HAS_CHECKOUT == (imported == ROOT / "nameparser"), imported
