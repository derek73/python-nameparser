"""2.8's warnings for everything 3.0 removes (decisions/3-0-reevaluations,
2026-10-28).

One test per warning, each asserting its category, its message, that
it is attributed to the CALLER's file (the stacklevel) and that the
code it offers runs. The offered code is also written below as real
functions, so ``uv run mypy`` type-checks it, and each test asserts the
message quotes that function's source (AGENTS.md: code a message hands
the reader has to survive a type checker, and then run).
"""
from __future__ import annotations

import copy
import inspect
import pickle
import subprocess
import sys
import tomllib
import warnings
from collections.abc import Callable
from pathlib import Path

import pytest

import nameparser
from nameparser import HumanName, Lexicon, ParsedName, Parser, parse
from nameparser._config_shim import CONSTANTS, Constants
from nameparser.util import _lc
from tests.removals import REMOVAL_MESSAGES


# -- the code the messages offer, type-checked by mypy ------------------------

def _offered_parse(text: str) -> ParsedName:
    return nameparser.parse(text)


def _offered_store(text: str) -> dict[str, str]:
    return parse(text).as_dict()


def _offered_parser() -> Parser:
    return Parser(lexicon=Lexicon.default().add(titles={'dean'}))


def _offered_lexicon() -> Lexicon:
    return Lexicon.default().add(titles={'dean'})


def _offered_lc(value: str) -> str:
    return value.lower().strip('.')


def _quoted(fn: Callable[..., object]) -> str:
    """The expression ``fn`` returns, as its source spells it."""
    source = inspect.getsource(fn)
    return source.split("return ", 1)[1].strip()


def _one(caught: list[warnings.WarningMessage], start: str
         ) -> warnings.WarningMessage:
    hits = [w for w in caught if str(w.message).startswith(start)]
    assert len(hits) == 1, [str(w.message) for w in caught]
    return hits[0]


def _assert_removal(w: warnings.WarningMessage, offered: Callable[..., object]
                    ) -> None:
    assert w.category is DeprecationWarning
    assert "3.0" in str(w.message)
    assert _quoted(offered) in str(w.message), (_quoted(offered), w.message)
    assert w.filename == __file__, w.filename   # the caller's line


def _record() -> warnings.catch_warnings[list[warnings.WarningMessage]]:
    return warnings.catch_warnings(record=True)


def _from_import(name: str) -> None:
    # spelled out rather than exec()'d, so the warning's filename is
    # this file's
    if name == "SetManager":
        from nameparser.config import SetManager  # noqa: F401
    elif name == "TupleManager":
        from nameparser.config import TupleManager  # noqa: F401
    else:
        from nameparser.config import RegexTupleManager  # noqa: F401


# -- the warnings ------------------------------------------------------------

def test_constructing_a_humanname_warns_at_the_caller() -> None:
    with _record() as caught:
        warnings.simplefilter("always")
        HumanName("John Smith")
    w = _one(caught, "HumanName is deprecated")
    _assert_removal(w, _offered_parse)
    assert "given and family" in str(w.message)
    assert _offered_parse("John Smith").given == "John"


def test_every_construction_warns_not_once_per_process() -> None:
    with _record() as caught:
        warnings.simplefilter("always")
        HumanName("John Smith")
        HumanName("Jane Doe")
    assert sum(str(w.message).startswith("HumanName is deprecated")
               for w in caught) == 2


def test_a_subclass_warns_at_its_own_super_call() -> None:
    class Sub(HumanName):
        def __init__(self, text: str) -> None:
            super().__init__(text)

    with _record() as caught:
        warnings.simplefilter("always")
        Sub("John Smith")
    assert _one(caught, "HumanName is deprecated").filename == __file__


def test_loading_a_humanname_pickle_warns_at_the_load() -> None:
    blob = pickle.dumps(HumanName("John Smith"))
    with _record() as caught:
        warnings.simplefilter("always")
        pickle.loads(blob)
    w = _one(caught, "HumanName pickles stop loading in 3.0")
    _assert_removal(w, _offered_store)
    assert _offered_store("John Smith")["family"] == "Smith"


def test_constructing_a_constants_warns_at_the_caller() -> None:
    with _record() as caught:
        warnings.simplefilter("always")
        Constants()
    w = _one(caught, "Constants is deprecated")
    _assert_removal(w, _offered_parser)
    assert _offered_parser().parse("Dean John Smith").title == "Dean"


def test_copying_a_constants_warns_as_construction_does() -> None:
    # CONSTANTS.copy() is a private Constants built past __init__
    with _record() as caught:
        warnings.simplefilter("always")
        CONSTANTS.copy()
    _assert_removal(_one(caught, "Constants is deprecated"), _offered_parser)


def test_loading_a_constants_pickle_warns_at_the_load() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        blob = pickle.dumps(Constants())
    with _record() as caught:
        warnings.simplefilter("always")
        pickle.loads(blob)
    w = _one(caught, "Constants pickles stop loading in 3.0")
    _assert_removal(w, _offered_parser)
    # what it offers pickles, which is the point of offering it
    assert pickle.loads(pickle.dumps(_offered_parser())).parse(
        "Dean John Smith").title == "Dean"


def test_mutating_the_shared_constants_names_a_runnable_parser() -> None:
    # the scalar path is the one attributed to the caller; the manager
    # path lands in the shim (the _bump comment says why)
    with _record() as caught:
        warnings.simplefilter("always")
        # tests/conftest.py restores the singleton after every test
        CONSTANTS.string_format = "{last}, {first}"
    w = _one(caught, "mutating the shared CONSTANTS singleton")
    _assert_removal(w, _offered_parser)
    assert "private Constants" not in str(w.message)


@pytest.mark.parametrize("name", ["SetManager", "TupleManager",
                                  "RegexTupleManager"])
def test_reading_a_manager_from_nameparser_config_warns_once(name: str) -> None:
    with _record() as caught:
        warnings.simplefilter("always")
        _from_import(name)
    w = _one(caught, f"nameparser.config.{name} is deprecated")
    assert w.filename == __file__
    _assert_removal(w, _offered_lexicon)
    assert "dean" in _offered_lexicon().titles

    import nameparser.config
    with _record() as caught:
        warnings.simplefilter("always")
        getattr(nameparser.config, name)
    assert _one(caught, f"nameparser.config.{name}").filename == __file__


def test_reading_lc_from_nameparser_util_warns() -> None:
    import nameparser.util
    with _record() as caught:
        warnings.simplefilter("always")
        lc = nameparser.util.lc
    w = _one(caught, "nameparser.util.lc is deprecated")
    _assert_removal(w, _offered_lc)
    for value in ("M.D.", ".Dr", "", "Smith"):
        assert _offered_lc(value) == lc(value) == _lc(value)


def test_the_hook_override_warning_says_humanname_goes_in_3_0() -> None:
    class Custom(HumanName):
        def is_title(self, value: object) -> bool:
            return False

    with _record() as caught:
        warnings.simplefilter("always")
        Custom("John Smith")
    w = _one(caught, "Custom overrides v1 parsing hooks")
    assert w.category is DeprecationWarning
    assert "HumanName is removed in 3.0" in str(w.message)
    assert w.filename == __file__


# -- what stays quiet --------------------------------------------------------

def test_copying_an_instance_is_not_a_pickle_load() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hn = HumanName("Dr. John Smith", constants=Constants())
    with _record() as caught:
        warnings.simplefilter("always")
        for fn in (copy.copy, copy.deepcopy):
            clone = fn(hn)
            assert clone.as_dict() == hn.as_dict()
            assert fn(hn.C).titles == hn.C.titles
    assert caught == []
    # deepcopy copies the config, copy shares it, as before 2.8
    assert copy.copy(hn).C is hn.C
    assert copy.deepcopy(hn).C is not hn.C


@pytest.mark.parametrize("code", [
    "import nameparser",
    "import nameparser.config, nameparser.parser, nameparser.util",
    "from nameparser import *",
    "from nameparser import HumanName",
    "from nameparser.parser import HumanName",
    "from nameparser.config import CONSTANTS, Constants",
    "from nameparser.config.titles import TITLES",
    "from nameparser import parse; parse('John Smith')",
])
def test_imports_and_the_core_stay_quiet(code: str) -> None:
    # a fresh interpreter, since this one has imported everything
    result = subprocess.run(
        [sys.executable, "-W", "error", "-c", code],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_the_suite_ignores_exactly_these_messages() -> None:
    # pyproject's filterwarnings and tests/removals.py's tuple are one
    # list in two places; a message changed in one goes unignored (or
    # unasserted) in the other
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    ignored = [f.split(":")[1] for f
               in config["tool"]["pytest"]["ini_options"]["filterwarnings"]
               if f.startswith("ignore:") and f.endswith(":DeprecationWarning")]
    assert tuple(ignored) == REMOVAL_MESSAGES
