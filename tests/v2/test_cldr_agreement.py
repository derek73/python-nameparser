"""The CLDR agreement ratchet, and the comparison rules it rests on.

tools/differential/cldr_agreement.py decides, for each CLDR rendering and
each role, whether nameparser agrees with CLDR's stated fields. The rules
are pinned here first, each with the wrong answer the plausible
alternative gives recorded beside it; the ratchet test at the end then
holds the whole corpus to the recorded disagreements in
tools/differential/cldr_agreement.json.

tools/ is not a package, so the module is loaded by path, as
_differential_fixtures.py loads compare.py.
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from nameparser import parse

_TOOLS = Path(__file__).parents[2] / "tools" / "differential"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "cldr_agreement", _TOOLS / "cldr_agreement.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


agreement = _load()


@pytest.mark.parametrize(("value", "text", "result"), [
    ("Falke", "Falke, Iris", True),          # commas stripped from the tokens
    ("Anna Cornelia", "Prof. Anna Cornelia Wolf", True),
    # Token containment, not substring: the substring rule says True here
    # and would expect a surname the rendering dropped.
    ("Wolf", "Wolfgang Smith", False),
    ("佐藤", "佐藤グレース恵子", True),        # unspaced: substring
    ("中村", "中村　敬子", True),          # ideographic space is a space
    # A no-break space is a space too. Treated as "no space", the text
    # falls to substring rules and finds `Ann` inside `Anna`.
    ("Ann", "Anna Smith", False),
    ("", "Iris Falke", False),               # an empty field is never present
])
def test_occurs(value: str, text: str, result: bool) -> None:
    assert agreement.occurs(value, text) is result


def test_expected_roles_drop_fields_the_rendering_omits() -> None:
    # Spanish given-first omits the second surname and the title stays.
    fields = {"title": "Sr.", "given": "Miguel Ángel", "given2": "Juan Antonio",
              "surname-core": "Pablo", "surname2": "Pérez", "generation": "II"}
    roles = agreement.expected_roles(fields, "Sr. Miguel Ángel Juan Antonio Pablo II")
    assert roles == {"title": "Sr.", "given_names": "Miguel Ángel Juan Antonio",
                     "family": "Pablo", "suffix": "II",
                     "family_particles": "", "family_base": "Pablo"}


def test_expected_roles_compare_particles_only_where_cldr_splits_them() -> None:
    plain = agreement.expected_roles({"given": "Iris", "surname": "Falke"}, "Iris Falke")
    assert set(plain) == {"title", "given_names", "family", "suffix"}
    split = agreement.expected_roles(
        {"given": "Paul", "surname-prefix": "von", "surname-core": "Fischer"},
        "Paul von Fischer")
    assert (split["family"], split["family_particles"], split["family_base"]) == (
        "von Fischer", "von", "Fischer")


def test_expected_roles_count_a_word_shared_by_two_fields_in_both() -> None:
    roles = agreement.expected_roles(
        {"given": "Syed Sadiq", "surname": "Syed Hassan"}, "Syed Sadiq Syed Hassan")
    assert (roles["given_names"], roles["family"]) == ("Syed Sadiq", "Syed Hassan")


@pytest.mark.parametrize(("expected", "got", "text", "result"), [
    ("Pablo Pérez", "Pérez Pablo", "Pablo Pérez Miguel", True),  # order-free
    ("Pablo", "Pablo Pérez", "Pablo Pérez Miguel", False),       # a word too many
    ("", "", "Iris Falke", True),          # absent on both sides agrees
    ("", "Dr.", "Dr. Iris Falke", False),  # an invented title disagrees
    ("jr. MdB", "jr., MdB", "Paul Fischer jr., MdB", True),     # commas ignored
    ("민규 헨리", "민규헨리", "김민규헨리", True),                  # unspaced text
])
def test_same(expected: str, got: str, text: str, result: bool) -> None:
    assert agreement.same(expected, got, text) is result


def test_got_roles_reads_the_six_views() -> None:
    roles = agreement.got_roles(parse("Dr. Paul von Fischer Jr."))
    assert roles == {"title": "Dr.", "given_names": "Paul", "family": "von Fischer",
                     "suffix": "Jr.", "family_particles": "von",
                     "family_base": "Fischer"}
    assert tuple(roles) == agreement.ROLES
