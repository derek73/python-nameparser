"""tools/stage_reads.py, the trace of what each pipeline stage reads.

The tool exists to show the reads a grep of a stage module cannot: a
read made through a helper in ``_vocab`` or ``_pieces``. So each test
pins a read of that kind, one the stage's own module never spells, and
holds that tracing leaves the parse as it was.

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
    reads = tool.trace([_Case("Juan Pérez García",
                              policy=Policy(two_family_names=True))])
    assert any(read.startswith("P.") for stage in reads.values()
               for read in stage)


@needs_checkout
def test_tracing_restores_the_decision_it_wraps(tool: ModuleType) -> None:
    from nameparser._pipeline import _comma
    before = _comma.decide
    tool.trace([_Case("John Smith, PhD")])
    assert _comma.decide is before
    # and the parse it watched reads as an untraced one does
    assert str(Parser().parse("John Smith, PhD")) == "John Smith, PhD"


@needs_checkout
def test_an_unknown_stage_is_an_error(tool: ModuleType,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_:
        tool.main(["--stage", "no_such_stage"])
    assert exit_.value.code == 2
    assert "classify" in capsys.readouterr().err
