"""Enforce the conventions doc's contracts mechanically: import
layering, public exports, and the pickle layout guards."""
import ast
import pathlib

import nameparser

PKG = pathlib.Path(nameparser.__file__).parent

# ALLOWED keys whose module must exist on disk -- the exists() skip in
# test_layering_contract is for entries that precede their module within
# a plan, and without this list a renamed existing module would silently
# drop out of enforcement. Later tasks add each stage file as it lands.
_MUST_EXIST = {"_types.py", "_lexicon.py", "_policy.py", "_locale.py",
               "_render.py", "_pipeline/_state.py", "_pipeline/__init__.py",
               "_pipeline/_extract.py", "_pipeline/_tokenize.py",
               "_pipeline/_vocab.py", "_pipeline/_segment.py",
               "_pipeline/_classify.py", "_pipeline/_group.py",
               "_pipeline/_assign.py", "_pipeline/_post_rules.py",
               "_pipeline/_assemble.py", "_parser.py", "_facade.py",
               "_config_shim.py", "locales/__init__.py", "locales/ru.py",
               "locales/tr_az.py"}

_PIPELINE_STAGE_ALLOWED = (
    "nameparser._types", "nameparser._lexicon", "nameparser._policy",
    # stages share _state plus in-package helpers (_vocab, _group's
    # piece predicates); the prefix still forbids _render/_locale/_parser
    "nameparser._pipeline.",
)

# a locale pack: pure data over the three base types, no pipeline or
# config access (locales spec §2) -- one contract shared by every pack,
# like _PIPELINE_STAGE_ALLOWED above, so tightening it is a one-line edit
_LOCALE_PACK_ALLOWED = (
    "nameparser._lexicon", "nameparser._locale", "nameparser._policy",
)

# module -> prefixes it may import from within nameparser
ALLOWED = {
    # call-time imports only (inside the rendering-delegate method
    # bodies); module level stays import-free. TYPE_CHECKING imports
    # are skipped by _nameparser_imports and need no entry.
    "_types.py": ("nameparser._render", "nameparser._parser"),
    # intent: DATA modules only, during 2.x -- mechanically this admits
    # any config submodule; "data only" holds by convention/review
    "_lexicon.py": ("nameparser.config.",),
    "_policy.py": ("nameparser._types",),
    # _types is a downward import (bottom of the graph): Locale shares
    # the _guarded_getstate/_guarded_setstate pickle functions
    "_locale.py": ("nameparser._types", "nameparser._lexicon",
                   "nameparser._policy"),
    # _lexicon is needed at runtime: capitalized(lexicon=None) resolves
    # to Lexicon.default()
    "_render.py": ("nameparser._types", "nameparser._lexicon"),
    # every stage module: state + the three config/type modules
    "_pipeline/_state.py": ("nameparser._types", "nameparser._lexicon",
                            "nameparser._policy"),
    "_pipeline/__init__.py": ("nameparser._pipeline.",),
    "_pipeline/_vocab.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_extract.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_tokenize.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_segment.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_classify.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_group.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_assign.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_post_rules.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_assemble.py": _PIPELINE_STAGE_ALLOWED,
    # Parser sits on everything except _render and the facade
    "_parser.py": ("nameparser._types", "nameparser._lexicon",
                   "nameparser._policy", "nameparser._locale",
                   "nameparser._pipeline"),
    # facade layer (migration spec §2/§3): may import anything public
    # plus _render (unused yet) and each other. _facade delegates
    # parsing to the core Parser resolved from the bound Constants shim.
    # The bare "nameparser.config" import (not just its submodules) is
    # deliberate -- it resolves an import cycle, see _facade.py's comment.
    "_facade.py": ("nameparser._config_shim", "nameparser._lexicon",
                   "nameparser._parser", "nameparser._types",
                   "nameparser._render", "nameparser.util",
                   "nameparser.config"),
    # the Constants/SetManager/TupleManager shim: config DATA modules
    # stay the single vocabulary source through 2.x (nameparser.config.*)
    "_config_shim.py": ("nameparser._lexicon", "nameparser._parser",
                        "nameparser._policy", "nameparser.util",
                        "nameparser.config"),
    # PEP 562 lazy loader: the only static import is _locale (for the
    # Locale return type); pack modules load via importlib.import_module
    # (a runtime string, invisible to the AST walker) -- the
    # "nameparser.locales." prefix documents that reach for humans even
    # though the walker never exercises it.
    "locales/__init__.py": ("nameparser._locale", "nameparser.locales."),
    "locales/ru.py": _LOCALE_PACK_ALLOWED,
    "locales/tr_az.py": _LOCALE_PACK_ALLOWED,
    # v1 import-path preservation: thin re-exports of the facade/shim
    "parser.py": ("nameparser._facade",),
    "config/__init__.py": ("nameparser._config_shim",),
    # CLI (migration spec §6): imports only the public package, same as
    # any other consumer -- no access to internal modules.
    "__main__.py": ("nameparser",),
}


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


def _nameparser_imports(path: pathlib.Path) -> list[str]:
    """All nameparser-internal imports in the module, at any nesting
    depth, EXCEPT those under `if TYPE_CHECKING:` -- annotation-only
    imports are not runtime dependencies."""
    found: list[str] = []

    def _record(node: ast.AST) -> None:
        # guard checked on EVERY node uniformly, so `elif TYPE_CHECKING:`
        # (a nested If in orelse) is skipped exactly like the plain form
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            for stmt in node.orelse:
                _record(stmt)
            return
        if isinstance(node, ast.Import):
            found.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
        for child in ast.iter_child_nodes(node):
            _record(child)

    _record(ast.parse(path.read_text()))
    return [m for m in found if m.startswith("nameparser")]


def _permitted(imported: str, allowed: tuple[str, ...]) -> bool:
    # An entry ending in "." is a pure prefix (subpackage contents only);
    # any other entry means that exact module or its submodules -- a bare
    # startswith would also admit siblings like nameparser._types_helpers.
    for entry in allowed:
        if entry.endswith("."):
            if imported.startswith(entry):
                return True
        elif imported == entry or imported.startswith(entry + "."):
            return True
    return False


def test_layering_contract() -> None:
    for mod, allowed in ALLOWED.items():
        path = PKG / mod
        if not path.exists():
            assert mod not in _MUST_EXIST, (
                f"{mod} keyed in ALLOWED but file is missing")
            continue  # entries may precede their module within a plan
        for imported in _nameparser_imports(path):
            assert _permitted(imported, allowed), (
                f"{mod} imports {imported}, which the layering contract "
                f"forbids (allowed prefixes: {allowed or 'none'})"
            )


def test_lexicon_never_imports_config_package_root_or_parser() -> None:
    for imported in _nameparser_imports(PKG / "_lexicon.py"):
        assert imported != "nameparser.config"
        assert not imported.startswith("nameparser.parser")


def test_public_exports() -> None:
    expected = {
        "Span", "Role", "Token", "Ambiguity", "AmbiguityKind", "ParsedName",
        "Lexicon", "Policy", "PolicyPatch", "PatronymicRule", "Script", "UNSET",
        "GIVEN_FIRST", "FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST",
        "DEFAULT_NICKNAME_DELIMITERS", "DEFAULT_SCRIPT_ORDERS", "Locale",
        "Parser", "parse", "parser_for",
    }
    assert expected <= set(nameparser.__all__)
    for name in expected:
        assert getattr(nameparser, name) is not None


def test_type_checking_imports_do_not_count(tmp_path: pathlib.Path) -> None:
    mod = tmp_path / "snippet.py"
    mod.write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from nameparser._lexicon import Lexicon\n"
        "elif TYPE_CHECKING:\n"
        "    import nameparser.never_runtime\n"
        "else:\n"
        "    import nameparser.util\n"
        "def f():\n"
        "    from nameparser import _render\n"
    )
    assert _nameparser_imports(mod) == ["nameparser.util", "nameparser"]


def test_every_frozen_dataclass_carries_the_pickle_guards() -> None:
    # Forgetting the two class-body assignments is SILENT --
    # @dataclass(slots=True) installs its own working pickle methods
    # without skew detection. Lexicon keeps a private copy of the guard
    # (layering keeps _lexicon import-free of _types).
    import dataclasses
    import inspect

    import nameparser._lexicon
    import nameparser._locale
    import nameparser._parser
    import nameparser._policy
    import nameparser._types
    from nameparser._types import _guarded_getstate, _guarded_setstate

    # _pipeline internals (ParseState, WorkToken, ...) are exempt: they
    # are never pickled and are not public API.
    modules = (nameparser._types, nameparser._lexicon,
               nameparser._policy, nameparser._locale, nameparser._parser)
    for module in modules:
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if not dataclasses.is_dataclass(cls):
                continue
            if cls.__name__ == "Lexicon":
                assert "__getstate__" in cls.__dict__
                assert "__setstate__" in cls.__dict__
                continue
            assert cls.__dict__.get("__getstate__") is _guarded_getstate, cls
            assert cls.__dict__.get("__setstate__") is _guarded_setstate, cls
