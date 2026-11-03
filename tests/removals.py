"""2.8's and 2.8.1's 3.0-removal warnings, for tests that install their own filters.

pyproject's ``filterwarnings`` ignores each of these by message, but a
``warnings.catch_warnings()`` block that calls ``simplefilter`` replaces
those filters, so a test recording or erroring on warnings around the
facade calls :func:`ignore_removals` after its ``simplefilter`` to keep
asserting what it asserted before 2.8. tests/v2/test_deprecations.py
holds this tuple to pyproject's list and asserts every warning in it.
"""
import warnings

REMOVAL_MESSAGES = (
    "HumanName is deprecated and will be removed in 3.0",
    "HumanName pickles stop loading in 3.0",
    "Constants is deprecated and will be removed in 3.0",
    "Constants pickles stop loading in 3.0",
    "nameparser.config.(Set|Tuple|RegexTuple)Manager is deprecated",
    "nameparser.util.lc is deprecated",
    # 2.8.1's: the Lexicon set fields (#754) and the constants of the
    # nameparser.config modules 3.0 deletes (#1007, #1008)
    "Lexicon's set fields are deprecated",
    r"nameparser\.config\.\w+\.\w+ is deprecated and will be removed in "
    r"3\.0 \(#100[78]\)",
)


def ignore_removals() -> None:
    """Ignore the removal warnings by message, ahead of the filters in place."""
    for message in REMOVAL_MESSAGES:
        warnings.filterwarnings("ignore", message=message,
                                category=DeprecationWarning)
