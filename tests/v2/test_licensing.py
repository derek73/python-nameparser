"""The package's licence metadata names every licence file the checkout
carries (decisions/shipped-data-licences): a third-party dataset whose
licence asks its text or notice to travel with copies has a
``LICENSE-<source>`` file at the root, and that file has to reach the
wheel (``license-files``), the licence expression (``license``) and the
README's License section, the PyPI page. A new file without a row in
``_THIRD_PARTY`` fails here, naming the three places to update. A list
the project measured on a dataset names no licence in the expression;
``_CREDITED`` holds its credit in its module and the README instead."""
import tomllib
from pathlib import Path

import pytest
from packaging.licenses import canonicalize_license_expression

from tests.checkout import ROOT, needs_checkout

#: Each third-party licence file and the SPDX identifier it stands for.
_THIRD_PARTY = {
    "LICENSE-nicknames": "Apache-2.0",
}

#: Each source the project measured its own list on, credited as a
#: courtesy rather than named in the expression (decisions/
#: shipped-data-licences, FACTS WE MEASURE): its SPDX identifier, the
#: modules crediting it and the words of the licence's name they credit
#: it by.
_CREDITED = {
    "CC-BY-4.0": (("nameparser/locales/_es_given_names.py",
                   "nameparser/locales/_es_ar_given_names.py"),
                  "Creative Commons Attribution 4.0"),
    "OGDL-Taiwan-1.0": (("nameparser/locales/zh.py",),
                        "Open Government Data License, version 1"),
}


def _project() -> dict:
    return tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


@needs_checkout
def test_every_third_party_licence_file_has_a_row() -> None:
    found = {p.name for p in ROOT.glob("LICENSE-*")}
    assert found == set(_THIRD_PARTY), (
        f"root licence files {sorted(found)} differ from _THIRD_PARTY's "
        f"{sorted(_THIRD_PARTY)}: give a new file a row with its SPDX "
        "identifier, and add it to pyproject's license and license-files "
        "and to README.rst's License section")


@needs_checkout
def test_license_files_lists_every_licence_file_and_nothing_missing() -> None:
    listed = _project()["license-files"]
    for name in listed:
        assert (ROOT / name).is_file(), f"license-files names missing {name}"
    assert {"LICENSE", *_THIRD_PARTY} <= set(listed), (
        f"license-files {listed} leaves out a licence file")


@needs_checkout
@pytest.mark.parametrize("name", sorted(_THIRD_PARTY))
def test_licence_expression_names_each_file_s_licence(name: str) -> None:
    expression = _project()["license"]
    assert canonicalize_license_expression(expression) == expression
    assert _THIRD_PARTY[name] in expression.split(" AND "), (
        f"{name}'s {_THIRD_PARTY[name]} is not in license = {expression!r}")


@needs_checkout
def test_licence_expression_names_nothing_without_a_row() -> None:
    terms = _project()["license"].split(" AND ")
    assert terms[0] == "LGPL-2.1-or-later"
    assert set(terms[1:]) == set(_THIRD_PARTY.values()), (
        f"license = {' AND '.join(terms)!r} and _THIRD_PARTY differ: a list "
        "copied whole names its licence in both, with a licence file; a "
        "list the project measured is credited in _CREDITED instead")


@needs_checkout
@pytest.mark.parametrize("spdx", sorted(_CREDITED))
def test_each_measured_source_is_credited(spdx: str) -> None:
    modules, credit = _CREDITED[spdx]
    readme = (ROOT / "README.rst").read_text(encoding="utf-8")
    for module in modules:
        text = (ROOT / module).read_text(encoding="utf-8")
        assert " ".join(credit.split()) in " ".join(text.split()), (
            f"{module} does not credit its data under {credit}")
        assert f"``{module}``" in readme or f"``{Path(module).name}``" in readme, (
            f"README.rst's License section does not name {module}")


@needs_checkout
@pytest.mark.parametrize("name", sorted(_THIRD_PARTY))
def test_readme_names_each_licence_file(name: str) -> None:
    readme = (ROOT / "README.rst").read_text(encoding="utf-8")
    section = readme.split("\nLicense\n-------\n", 1)[1].split("\n.. |", 1)[0]
    assert f"``{name}``" in section
    assert _project()["license"] in section
