"""Exercise the doctest examples embedded in Constants attribute docstrings.

nameparser.config.Constants documents several scalar attributes (e.g.
patronymic_name_order, middle_name_as_last) with a bare string literal placed
right after the class-attribute assignment -- Sphinx's "attribute docstring"
convention, picked up by autodoc's source-level analysis for the built docs.

That convention is invisible to Python at runtime: only module/class/function/
method docstrings become a real __doc__, so a bare string following
`attr = value` is evaluated and discarded. doctest.DocTestFinder walks __doc__
attributes, so pytest's --doctest-modules (see pyproject.toml addopts) never
finds the `.. doctest::` examples inside them -- they can go stale silently.

This module parses the source with `ast` to recover those literals (the same
information Sphinx's static analysis relies on) and runs any doctest examples
found inside them explicitly, so a stale example fails the suite.
"""
import ast
import doctest
import io
from pathlib import Path

import pytest

import nameparser.config as config_module
from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants

CONFIG_SOURCE_PATH = Path(config_module.__file__)


def _constants_attribute_docstrings() -> dict[str, str]:
    """Map attribute name -> bare-string-literal docstring, Constants class body only."""
    tree = ast.parse(CONFIG_SOURCE_PATH.read_text(), filename=str(CONFIG_SOURCE_PATH))
    (class_node,) = (
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == 'Constants'
    )
    docstrings = {}
    body = class_node.body
    for stmt, following in zip(body, body[1:]):
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)):
            continue
        if isinstance(following, ast.Expr) and isinstance(following.value, ast.Constant) \
                and isinstance(following.value.value, str):
            docstrings[stmt.targets[0].id] = following.value.value
    return docstrings


ATTRIBUTE_DOCSTRINGS = _constants_attribute_docstrings()

DOCTEST_GLOBS = {'HumanName': HumanName, 'CONSTANTS': CONSTANTS, 'Constants': Constants}


def _attrs_with_doctest_examples() -> list[str]:
    parser = doctest.DocTestParser()
    return sorted(
        attr for attr, docstring in ATTRIBUTE_DOCSTRINGS.items()
        if parser.get_examples(docstring)
    )


@pytest.mark.parametrize("attr", _attrs_with_doctest_examples())
def test_constants_attribute_docstring_examples(attr: str) -> None:
    docstring = ATTRIBUTE_DOCSTRINGS[attr]
    test = doctest.DocTestParser().get_doctest(
        docstring, DOCTEST_GLOBS, attr, str(CONFIG_SOURCE_PATH), 0,
    )
    output = io.StringIO()
    failures, _ = doctest.DocTestRunner().run(test, out=output.write)
    assert failures == 0, output.getvalue()


def test_found_expected_attributes_with_doctest_examples() -> None:
    """Guard the discovery mechanism itself: if this drops to zero, the AST
    walk above stopped matching Constants's attribute-docstring pattern and
    every parametrized case above is silently skipped rather than run."""
    assert _attrs_with_doctest_examples()
