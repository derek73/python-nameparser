"""tools/stage_reads.py, the trace of what each pipeline stage reads.

The tool exists to show the reads a grep of a stage module cannot: a
read made through a helper in ``_vocab`` or ``_pieces``. One test pins a
read of that kind, one the stage's own module never spells; the others
pin where a read is charged, that a policy read follows the row's
policy, and that the traced fold reads every row as ``Parser.parse``
does, so the trace watches the real parse rather than another one.

tools/ is not a package, so the module is loaded by path.
"""
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from nameparser import Parser, Policy
from tests.checkout import needs_checkout

from ._differential_fixtures import load_by_path

_PATH = Path(__file__).parents[2] / "tools" / "stage_reads.py"


@dataclass(frozen=True)
class _Case:
    text: str
    policy: Any = None
    locale: str | None = None


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return load_by_path("stage_reads", _PATH)


@needs_checkout
def test_it_sees_a_read_made_through_a_helper(tool: ModuleType) -> None:
    # assign's given-part walk reads the suffix sets through
    # _vocab.is_suffix_lenient; _assign.py spells none of them
    source = (_PATH.parents[1] / "nameparser" / "_pipeline"
              / "_assign.py").read_text()
    assert "_sets.suffix_words" not in source
    reads = tool.trace([_Case("Salem, Abdul Rahman Ahmed")])
    assert reads["assign"]["L.suffix_words"] == "Salem, Abdul Rahman Ahmed"


@needs_checkout
def test_it_charges_a_read_to_the_stage_and_the_decision_apart(
        tool: ModuleType) -> None:
    reads = tool.trace([_Case("John Smith, PhD")])
    assert "group/_comma.decide" in reads
    assert not any(stage.endswith("_comma.decide/_comma.decide")
                   for stage in reads)
    assert "L.titles" in reads["classify"]


@needs_checkout
def test_it_records_policy_reads_under_the_case_s_policy(
        tool: ModuleType) -> None:
    # post_rules asks the order only once two_family_names is on: a read
    # the row's policy causes, where tokenize's P.strip_bidi is read for
    # any row at all
    plain = tool.trace([_Case("Juan Pérez García")])
    switched = tool.trace([_Case("Juan Pérez García",
                                 policy=Policy(two_family_names=True))])
    assert "P.name_order" not in plain["post_rules"]
    assert switched["post_rules"]["P.name_order"] == "Juan Pérez García"


@needs_checkout
def test_tracing_restores_the_decision_it_wraps(tool: ModuleType) -> None:
    from nameparser._pipeline import _comma
    before = _comma.decide
    tool.trace([_Case("John Smith, PhD")])
    assert _comma.decide is before


_ROWS = (
    _Case("John Smith, PhD"),
    _Case("Salem, Abdul Rahman Ahmed"),
    _Case("Juan Pérez García", policy=Policy(two_family_names=True)),
    _Case("Dr. Juan Q. Xavier de la Vega III (Doc)"),
    _Case("김민준"),
    _Case("Ivan Petrovich Sidorov", locale="ru"),
)


@needs_checkout
@pytest.mark.parametrize("case", _ROWS, ids=lambda c: c.text)
def test_the_traced_fold_reads_as_parser_parse_does(
        tool: ModuleType, case: _Case) -> None:
    from nameparser import locales, parser_for
    parser = (parser_for(getattr(locales, case.locale.upper()))
              if case.locale else Parser(policy=case.policy or Policy()))
    seen: list[Any] = []
    tool.trace([case], assembled=seen.append)
    assert seen == [parser.parse(case.text)]


@needs_checkout
def test_an_unknown_stage_is_an_error(tool: ModuleType,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        tool.main(["--stage", "no_such_stage"])
    assert exit_.value.code == 2
    assert "classify" in capsys.readouterr().err
