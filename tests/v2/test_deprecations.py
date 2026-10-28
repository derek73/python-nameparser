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

import ast
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


def _pop_parenthesis() -> None:
    # the documented recipe for routing a built-in delimiter between
    # buckets: a pop() and a __setitem__, two mutations on one line
    CONSTANTS.maiden_delimiters["parenthesis"] = (
        CONSTANTS.nickname_delimiters.pop("parenthesis"))


# Every way to mutate the shared singleton, each written in this file so
# the caller's line is here. They reach the warning at different depths
# (a scalar through Constants.__setattr__, a set through add() and
# _changed(), a dict's update() and |= through __setitem__ per key), and
# a fixed stacklevel served only the scalar one until 2.8.0's release
# review: CONSTANTS.titles.add() was attributed inside the shim, so
# Python's default filters hid it. With that fixed stacklevel=3 back,
# 10 of these 11 shapes fail, every one but the scalar (2026-10-28).
_SHARED_MUTATIONS: dict[str, Callable[[], object]] = {
    "scalar": lambda: setattr(CONSTANTS, "string_format", "{last}, {first}"),
    "set add": lambda: CONSTANTS.titles.add("xyzzy"),
    "set remove": lambda: CONSTANTS.titles.remove("dr"),
    "set discard": lambda: CONSTANTS.titles.discard("dr"),
    "set clear": lambda: CONSTANTS.conjunctions.clear(),
    "dict setitem": lambda: CONSTANTS.capitalization_exceptions.__setitem__(
        "xyzzy", "XyZzy"),
    "dict update": lambda: CONSTANTS.capitalization_exceptions.update(
        {"xyzzy": "XyZzy"}),
    "dict |=": lambda: CONSTANTS.capitalization_exceptions.__ior__(
        {"xyzzy": "XyZzy"}),
    "dict setdefault": lambda: CONSTANTS.capitalization_exceptions.setdefault(
        "xyzzy", "XyZzy"),
    "dict pop": lambda: CONSTANTS.capitalization_exceptions.pop("phd"),
    "delimiter recipe": _pop_parenthesis,
}


@pytest.mark.parametrize("shape", sorted(_SHARED_MUTATIONS))
def test_mutating_the_shared_constants_warns_at_the_caller(shape: str) -> None:
    with _record() as caught:
        warnings.simplefilter("always")
        # tests/conftest.py restores the singleton after every test
        _SHARED_MUTATIONS[shape]()
    hits = [w for w in caught if str(w.message).startswith(
        "mutating the shared CONSTANTS singleton")]
    assert hits, [str(w.message) for w in caught]
    for w in hits:
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


class _TaggedName(HumanName):
    # a subclass carrying state of its own through the pickle hooks
    def __getstate__(self) -> dict[str, object]:
        return {**super().__getstate__(), "tag": getattr(self, "tag", None)}

    def __setstate__(self, state: dict[str, object]) -> None:
        super().__setstate__(state)
        self.tag = state["tag"]


class _ExtraConstants(Constants):
    # a subclass whose own __init__ sets state, which a restore ran
    # before 2.8 and runs still
    def __init__(self, extra: str = "default") -> None:
        super().__init__()
        self.extra = extra


def test_a_subclass_copies_and_loads_through_its_own_hooks() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tagged = _TaggedName("John Smith")
        tagged.tag = "T"
        extra = _ExtraConstants("set")
    with _record() as caught:
        warnings.simplefilter("always")
        for fn in (copy.copy, copy.deepcopy):
            assert fn(tagged).tag == "T"
            assert fn(extra).extra == "default"   # its __init__ ran
    assert caught == []
    with _record() as caught:
        warnings.simplefilter("always")
        assert pickle.loads(pickle.dumps(tagged)).tag == "T"
        assert pickle.loads(pickle.dumps(extra)).extra == "default"
    # the load warns, a restore is no construction
    assert sorted(str(w.message).split(" ")[0] for w in caught) == [
        "Constants", "HumanName"]


def test_dir_lists_the_names_getattr_serves() -> None:
    # autodoc collects members from dir(), so a name missing there
    # drops out of the rendered API reference
    import nameparser.config
    import nameparser.util
    assert {"SetManager", "TupleManager", "RegexTupleManager",
            "Constants", "CONSTANTS", "titles"} <= set(dir(nameparser.config))
    assert "lc" in dir(nameparser.util)
    for module in (nameparser.config, nameparser.util):
        with pytest.raises(AttributeError, match="no attribute 'nope'"):
            getattr(module, "nope")


@pytest.mark.parametrize("module,names", [
    ("nameparser.config", {"SetManager", "TupleManager", "RegexTupleManager"}),
    ("nameparser.util", {"lc"}),
])
def test_a_star_import_warns_for_each_removed_name_it_binds(
        module: str, names: set[str]) -> None:
    namespace: dict[str, object] = {}
    with _record() as caught:
        warnings.simplefilter("always")
        exec(f"from {module} import *", namespace)
    assert names <= set(namespace)
    assert len(caught) == len(names)
    assert all(w.category is DeprecationWarning for w in caught)


_REMOVED = {"nameparser.config": {"SetManager", "TupleManager",
                                  "RegexTupleManager"},
            "nameparser.util": {"lc"}}


def _removed_reads(path: Path, package: Path) -> list[str]:
    """Each read of a removed name in one module: ``from`` imports
    (relative ones resolved, star imports included), and attribute or
    ``getattr`` reads through a name bound to either module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts = ["nameparser", *path.relative_to(package).with_suffix("").parts]
    here = parts[:-1]                        # the package a module sits in
    aliases: dict[str, str] = {}             # local name -> module
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in _REMOVED:
                    aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = here[:len(here) - node.level + 1]
                base = ".".join([*anchor, *([base] if base else [])])
            for a in node.names:
                full = f"{base}.{a.name}"
                if full in _REMOVED:         # from nameparser import util
                    aliases[a.asname or a.name] = full
                elif base in _REMOVED and (a.name == "*"
                                           or a.name in _REMOVED[base]):
                    hits.append(f"{node.lineno} from {base} import {a.name}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            owner, name = ast.unparse(node.value), node.attr
        elif (isinstance(node, ast.Call) and ast.unparse(node.func) == "getattr"
              and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)):
            owner, name = ast.unparse(node.args[0]), str(node.args[1].value)
        else:
            continue
        module = aliases.get(owner, owner)
        if name in _REMOVED.get(module, ()):
            hits.append(f"{node.lineno} {module}.{name}")
    return hits


def test_no_internal_code_reads_a_removed_name() -> None:
    # an internal read would warn on the library's behalf, at a line
    # inside nameparser the caller cannot edit; the library reads _lc
    # and _config_shim directly. Read from the AST, so a docstring
    # naming one is not a read
    package = Path(nameparser.__file__).parent
    modules = sorted(package.rglob("*.py"))
    assert len(modules) > 20                 # the scan saw the package
    offenders = [f"{m.relative_to(package)}:{hit}" for m in modules
                 for hit in _removed_reads(m, package)]
    assert offenders == []


@pytest.mark.parametrize("source", [
    "from nameparser.util import lc",
    "from .util import lc",
    "from nameparser.config import *",
    "import nameparser.util as u\nu.lc",
    "from nameparser import config as c\nc.SetManager",
    "import nameparser.config\ngetattr(nameparser.config, 'TupleManager')",
])
def test_the_internal_read_guard_sees_each_shape(source: str,
                                                 tmp_path: Path) -> None:
    package = tmp_path / "nameparser"
    package.mkdir()
    module = package / "probe.py"
    module.write_text(source + "\n", encoding="utf-8")
    assert _removed_reads(module, package)
    module.write_text("self.config.SetManager\n", encoding="utf-8")
    assert not _removed_reads(module, package)


def test_a_copy_leaves_the_once_per_line_registry_alone() -> None:
    # catch_warnings clears every module's registry, so a copy that
    # entered it would re-show the caller's once-per-line warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hn = HumanName("John Smith", constants=Constants())
    with _record() as caught:
        warnings.simplefilter("default")
        for _ in range(3):
            HumanName("Jane Doe"); copy.copy(hn); copy.deepcopy(hn)  # noqa: E702
    assert len(caught) == 1


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
