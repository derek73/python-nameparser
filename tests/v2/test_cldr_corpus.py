"""Offline checks on tools/differential/build_cldr_corpus.py.

The build script is the only part of the CLDR corpus that touches the
network, so its parsing of CLDR's personNameTest format is pinned here on
a hand-written sample in that format. tools/ is not a package, so the
module is loaded by path, as _differential_fixtures.py loads compare.py.
"""
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_PATH = Path(__file__).parents[2] / "tools" / "differential" / "build_cldr_corpus.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_cldr_corpus", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = _load()

_SAMPLE = """# Test data for Person Name Data
#  SPDX-License-Identifier: Unicode-3.0
enum ; field ; title, given, surname

# nativeGS
name ; given; Iris
name ; surname; Falke
name ; locale; de_AQ

expectedResult; Iris Falke

parameters; givenFirst; long; referring; formal
parameters; givenFirst; medium; referring; formal

expectedResult; Falke, Iris

parameters; surnameFirst; long; referring; formal
parameters; sorting; long; referring; formal

endName

# nativeG
name ; given; Lena
name ; locale; de_AQ

expectedResult; Lena

parameters; givenFirst; long; referring; formal
parameters; surnameFirst; long; referring; formal

expectedResult; Lena Lena

parameters; sorting; long; referring; informal

endName
"""


def test_parse_test_file_keeps_only_the_long_referring_formal_renderings() -> None:
    rows = build.parse_test_file(_SAMPLE, "de")
    assert [(r["label"], r["order"], r["text"]) for r in rows] == [
        ("nativeGS", "givenFirst", "Iris Falke"),
        ("nativeGS", "surnameFirst", "Falke, Iris"),
        ("nativeGS", "sorting", "Falke, Iris"),
        ("nativeG", "givenFirst", "Lena"),
        ("nativeG", "surnameFirst", "Lena"),
    ]  # the medium and the informal parameters are not selected
    assert rows[0]["fields"] == {"given": "Iris", "surname": "Falke", "locale": "de_AQ"}
    assert rows[0]["file"] == "de"


@pytest.mark.parametrize(("order", "text", "shape"), [
    ("givenFirst", "Iris Falke", None),
    ("surnameFirst", "Falke, Iris", 4),   # declared surname-first, comma or not
    ("surnameFirst", "Lena", 4),
    ("sorting", "Falke, Iris", None),     # the comma carries the order
    ("sorting", "Adler Irene", 4),        # a comma-less sorting form is surname-first
])
def test_shape_for_tags_surname_first_renderings(order: str, text: str, shape: int | None) -> None:
    assert build.shape_for(order, text) == shape


def test_parse_test_file_refuses_a_name_with_no_label() -> None:
    with pytest.raises(ValueError, match="no label"):
        build.parse_test_file("name ; given; X\nexpectedResult; X\n"
                              "parameters; givenFirst; long; referring; formal\nendName\n", "xx")


def test_parse_test_file_refuses_an_unknown_line_kind() -> None:
    with pytest.raises(ValueError, match="unknown line kind"):
        build.parse_test_file("# nativeG\nnmae ; given; X\n", "xx")


def test_corpus_lines_dedupe_on_text_and_shape() -> None:
    lines = build.corpus_lines(build.parse_test_file(_SAMPLE, "de"))
    entries = [json.loads(line) for line in lines]
    assert entries == [
        "Falke, Iris",
        {"name": "Falke, Iris", "shape": 4},
        "Iris Falke",
        "Lena",
        {"name": "Lena", "shape": 4},
    ]


def test_fields_lines_refuse_a_duplicate_rendering_key() -> None:
    rows = build.parse_test_file(_SAMPLE, "de")
    with pytest.raises(ValueError, match="duplicate rendering"):
        build.fields_lines(rows + rows[:1])
