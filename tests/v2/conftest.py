"""Neutralize the v1 suite's autouse dual-run fixture for tests/v2.

tests/conftest.py runs every test twice (empty_attribute_default '' and
None) and deep-copy-snapshots the shared CONSTANTS around each test.
v2 code never reads shared CONSTANTS, so both behaviors are pure
overhead here. Overriding the fixture by name in this conftest replaces
the parametrized parent version for this directory.
"""
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def empty_attribute_default() -> Iterator[None]:
    yield
