"""Enforce the conventions doc's contracts mechanically: import
layering, public exports, and the pickle layout guards."""
import ast
import importlib
import pathlib

import pytest

from tests.checkout import ROOT

import nameparser
import nameparser._pipeline

PKG = pathlib.Path(nameparser.__file__).parent

# ALLOWED keys whose module must exist on disk -- the exists() skip in
# test_layering_contract is for entries that precede their module within
# a plan, and without this list a renamed existing module would silently
# drop out of enforcement. Later tasks add each stage file as it lands.
_MUST_EXIST = {"_types.py", "_lexicon.py", "_policy.py", "_locale.py",
               "_reading_index.py",
               "_render.py", "_pipeline/_state.py", "_pipeline/__init__.py",
               "_pipeline/_extract.py", "_pipeline/_tokenize.py",
               "_pipeline/_vocab.py", "_pipeline/_script_segment.py",
               "_pipeline/_segment.py", "_pipeline/_comma.py",
               "_pipeline/_classify.py", "_pipeline/_group.py",
               "_pipeline/_pieces.py",
               "_pipeline/_assign.py", "_pipeline/_post_rules.py",
               "_pipeline/_assemble.py", "_parser.py",
               "locales/__init__.py", "locales/ja.py",
               "locales/ru.py", "locales/tr_az.py", "locales/zh.py",
               "locales/_es_given_names.py"}

_PIPELINE_STAGE_ALLOWED = (
    "nameparser._types", "nameparser._lexicon", "nameparser._policy",
    # stages share _state plus in-package helpers (_vocab and
    # _pieces); the prefix still forbids _render/_locale/_parser
    "nameparser._pipeline.",
)

# a locale pack: pure data over the base types, no pipeline or config
# access (mechanisms.md#LOCALE-PACKS-PURE-DATA) -- one contract
# shared by every pack, like
# _PIPELINE_STAGE_ALLOWED above, so tightening it is a one-line edit.
# _types joined the three in #272: the ja pack's segmenter factory
# constructs a Segmentation, and _types is the bottom of the graph
# (Locale itself imports it), so this widens the base types, not the
# reach.
_LOCALE_PACK_ALLOWED = (
    "nameparser._lexicon", "nameparser._locale", "nameparser._policy",
    "nameparser._types",
)

# module -> prefixes it may import from within nameparser
ALLOWED = {
    # call-time imports only (inside the rendering-delegate method
    # bodies); module level stays import-free. TYPE_CHECKING imports
    # are skipped by _nameparser_imports and need no entry.
    "_types.py": ("nameparser._render", "nameparser._parser"),
    # intent: DATA modules only -- mechanically this admits any config
    # submodule, and since 3.0 the package holds nothing else; and the
    # reading index's reader and compiler, at call time only, since
    # tools/vocab/build.py loads this file by path (3.0's 4i-b: a
    # Lexicon compiles its readings)
    "_lexicon.py": ("nameparser.config.", "nameparser._reading_index"),
    "_policy.py": ("nameparser._types",),
    # name matching: the types, the lexicon's listed spellings, the
    # scripts that write no initials (as _render reads them) and the
    # pipeline's hyphens (_pipeline/_vocab._HYPHEN_CHARS, rules/O6's
    # set, which the match reads every hyphen as, #1264); _parser at
    # call time only, in Matching's constructor, which requires a
    # Parser, and its repr, which tells a Parser from a subclass (Parser
    # imports this module at call time, in Parser.matching)
    "_match.py": ("nameparser._types", "nameparser._lexicon",
                  "nameparser._policy", "nameparser._parser",
                  "nameparser._pipeline._vocab"),
    # the group suggester: types, policy, the lexicon's particles and
    # titles, the pipeline's patronymic, title, suffix and numeral
    # predicates and its private word tables;
    # _parser at call time only, in Suggestion.__post_init__, to check
    # that the base is a Parser (Parser imports this module at call
    # time, in Parser.suggest)
    "_suggest.py": ("nameparser._types", "nameparser._policy",
                    "nameparser._lexicon", "nameparser._pipeline",
                    "nameparser.config.", "nameparser._parser"),
    # the shared compiler and the reading index's reader (#753, 3a): the
    # index, a config DATA module, and nothing else. That the import is
    # at call time only, nothing internal at module level, since
    # tools/vocab/build.py loads this file by path as it loads
    # _lexicon.py, is held by test_reading_index.py's
    # test_the_module_imports_nothing_internal_at_module_level, which
    # this prefix match cannot see
    "_reading_index.py": ("nameparser.config.",),
    # _types is a downward import (bottom of the graph): Locale shares
    # the _guarded_getstate/_guarded_setstate pickle functions; the
    # compiled [rules] tables, a config DATA module, at call time, in
    # rules_patch (#754, 4f), which the shipped packs call
    "_locale.py": ("nameparser._types", "nameparser._lexicon",
                   "nameparser._policy", "nameparser.config._rules"),
    # _lexicon is needed at runtime: capitalized(lexicon=None) resolves
    # to Lexicon.default(); _policy for the scripts that write no
    # initials (_SCRIPT_PROPERTIES), which initials() skips (#754)
    "_render.py": ("nameparser._types", "nameparser._lexicon",
                   "nameparser._policy"),
    # every stage module: state + the three config/type modules
    "_pipeline/_state.py": ("nameparser._types", "nameparser._lexicon",
                            "nameparser._policy"),
    "_pipeline/__init__.py": ("nameparser._pipeline.",),
    # Tighter than the stage allowance on purpose: _vocab takes
    # normalized-or-raw text explicitly, no state, with named
    # departures (its own docstring) -- tag_marker_runs is one, and it
    # reads WorkToken.role/span and comma_bucket, never a whole
    # ParseState. Widening this past _state is the tell that a text-
    # level predicate has grown a dependency on a stage.
    # _reading_index joined in 3.0's 4b for a listed suffix word's
    # kind and left in 4i-b, the lexicon compiling the kind into sets
    # of its own (Lexicon._sets.generation_words and its siblings).
    "_pipeline/_vocab.py": ("nameparser._lexicon", "nameparser._policy",
                            "nameparser._pipeline._state"),
    "_pipeline/_extract.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_tokenize.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_script_segment.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_segment.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_classify.py": _PIPELINE_STAGE_ALLOWED,
    # Piece-level predicates shared by four stages -- segment,
    # classify, group and assign
    # (mechanisms.md#ONE-PREDICATE-PER-QUESTION). Segment joined with
    # #289/#516's own-words span, and "both stages" below was written
    # when there were two. Tighter than the
    # stage allowance on purpose: it is a leaf those stages sit on, so
    # it may read the token type and the vocabulary layer and NOTHING
    # else -- not even _lexicon, which is the likeliest next reach (a
    # title predicate wanting _title_key) and so the one this entry
    # most needs to refuse. Carrying the stage allowance's other
    # prefixes here would pre-authorise the very widening the entry
    # exists to make visible. Widening it is the tell that a piece
    # predicate has grown a dependency on a stage.
    "_pipeline/_pieces.py": ("nameparser._pipeline._state",
                             "nameparser._pipeline._vocab"),
    "_pipeline/_group.py": _PIPELINE_STAGE_ALLOWED,
    # not a stage: C1's decision, which group calls at its head (#613)
    "_pipeline/_comma.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_assign.py": _PIPELINE_STAGE_ALLOWED,
    "_pipeline/_post_rules.py": _PIPELINE_STAGE_ALLOWED,
    # not a stage: it alone reads the reading index, for
    # Reading.languages (4a's follow-up); no stage that decides a
    # role may, since the index is the files' record, not the lexicon
    "_pipeline/_assemble.py": _PIPELINE_STAGE_ALLOWED + (
        "nameparser._reading_index",),
    # Parser sits on everything except _render; the reading index at
    # call time only, where a choice of languages is applied (3b); _match
    # at call time only, in Parser.matching(); _suggest at call time
    # only, in Parser.suggest()
    "_parser.py": ("nameparser._types", "nameparser._lexicon",
                   "nameparser._policy", "nameparser._locale",
                   "nameparser._pipeline", "nameparser._reading_index",
                   "nameparser._match", "nameparser._suggest"),
    # PEP 562 lazy loader: the only static import is _locale (for the
    # Locale return type); pack modules load via importlib.import_module
    # (a runtime string, invisible to the AST walker) -- the
    # "nameparser.locales." prefix documents that reach for humans even
    # though the walker never exercises it.
    "locales/__init__.py": ("nameparser._locale", "nameparser.locales."),
    "locales/ja.py": _LOCALE_PACK_ALLOWED,
    "locales/ru.py": _LOCALE_PACK_ALLOWED,
    "locales/tr_az.py": _LOCALE_PACK_ALLOWED,
    "locales/zh.py": _LOCALE_PACK_ALLOWED,
    # a pack's data, no pack itself: rules/O6's given-name list (#959),
    # which the es pack will carry as a lexicon fragment
    "locales/_es_given_names.py": (),
    # the data modules' package: a docstring, no imports
    "config/__init__.py": (),
    # CLI: imports only the public package, same as
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


def test_every_pipeline_module_is_keyed_in_allowed() -> None:
    """ALLOWED is a hand-maintained list, and test_layering_contract
    iterates ITS keys -- so a module absent from it is not checked
    loosely, it is not checked AT ALL. Nothing else notices: the suite
    stays green, and the new module may import whatever it likes.

    Scoped to _pipeline/ because that is what this contract governs.
    Unkeyed by choice: the config/ DATA modules (config/__init__.py is
    keyed, being code) and _version.py. nameparser/__init__.py is unkeyed
    too and is none of those -- it is the export surface, held by
    test_public_exports instead.

    Measured when this was added: all 13 _pipeline modules were keyed,
    so the gap was latent rather than active. #439's _pieces.py would
    have been the first to slip through, which is why closing it then
    cost nothing to clean up.

    The directory comes from the imported subpackage rather than a path
    literal, so a typo is an AttributeError; and the floor below is not
    ceremony. Path.glob on a missing directory returns EMPTY rather than
    raising, so a mistyped pattern would leave this asserting `set() -
    keyed`, which passes for every possible ALLOWED -- a completeness
    check measuring nothing, which is the shape of the bug it exists
    to prevent.
    """
    keyed = set(ALLOWED)
    pipeline_dir = pathlib.Path(nameparser._pipeline.__file__).parent
    shipped = {f"_pipeline/{p.name}" for p in pipeline_dir.glob("*.py")}
    assert "_pipeline/_group.py" in shipped, (
        f"the glob matched no pipeline modules, so this check can no "
        f"longer fail: {sorted(shipped)}")
    missing = sorted(shipped - keyed)
    assert not missing, (
        f"pipeline modules absent from ALLOWED, and therefore exempt "
        f"from the layering contract entirely: {missing}. Add each with "
        f"the narrowest prefix tuple that admits what it actually "
        f"imports -- _PIPELINE_STAGE_ALLOWED for a stage, something "
        f"tighter for a leaf several stages sit on (see _pipeline/_pieces.py)"
    )


def test_lexicon_never_imports_config_package_root_or_parser() -> None:
    for imported in _nameparser_imports(PKG / "_lexicon.py"):
        assert imported != "nameparser.config"
        assert not imported.startswith("nameparser.parser")


def test_public_exports() -> None:
    expected = {
        "Span", "Role", "Token", "Ambiguity", "AmbiguityKind", "ParsedName",
        "Segmentation", "Segmenter",
        "Lexicon", "Policy", "PolicyPatch", "PatronymicRule", "Script", "UNSET",
        "GIVEN_FIRST", "FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST",
        "DEFAULT_NICKNAME_DELIMITERS", "DEFAULT_SCRIPT_ORDERS", "Locale",
        "Parser", "parse", "parser_for",
    }
    assert expected <= set(nameparser.__all__)
    for name in expected:
        assert getattr(nameparser, name) is not None


@pytest.mark.parametrize("module,name", [
    ("nameparser", "HumanName"),
    ("nameparser.config", "Constants"),
    ("nameparser.config", "CONSTANTS"),
    ("nameparser.config", "SetManager"),
    ("nameparser.config", "TupleManager"),
    ("nameparser.config", "RegexTupleManager"),
])
def test_the_1x_compatibility_names_are_gone(module: str, name: str) -> None:
    # 3.0 removed the 1.x layer 2.8 warned about (#357); a name that
    # came back would be a public surface nothing documents
    imported = importlib.import_module(module)
    assert not hasattr(imported, name)
    assert name not in getattr(imported, "__all__", ())


@pytest.mark.parametrize("module", [
    "nameparser.parser", "nameparser.util", "nameparser.config.prefixes",
    "nameparser.config.bound_first_names",
])
def test_the_1x_compatibility_modules_are_gone(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


@pytest.mark.parametrize("module", [
    "nameparser.config.titles", "nameparser.config.suffixes",
    "nameparser.config.particles", "nameparser.config.conjunctions",
    "nameparser.config.bound_given_names", "nameparser.config.given_names",
    "nameparser.config.maiden_markers", "nameparser.config.capitalization",
    "nameparser.config.surnames",
])
def test_the_vocabulary_modules_are_gone(module: str) -> None:
    # 3.0 removed the modules that re-exported the compiled sets, which
    # 2.8.1 warned of (#1007): Lexicon.words(kind=...) lists a kind's
    # words. It made surnames private too, which 2.8.2 warned of:
    # Lexicon.default().surnames holds its words, and nameparser.config
    # has no public module left
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_the_config_package_holds_no_public_module() -> None:
    # the public surface is nameparser and nameparser.locales; a module
    # added here without a leading underscore would be a public import
    # path nothing documents (surnames was the last, private since 3.0)
    import pathlib

    import nameparser.config
    root = pathlib.Path(nameparser.config.__file__).parent
    modules = sorted(p.stem for p in root.glob("*.py"))
    assert "_ko_surnames" in modules
    assert [m for m in modules if not m.startswith("_")] == []


@pytest.mark.parametrize("statement,error", [
    ("from nameparser.config.prefixes import PREFIXES", ModuleNotFoundError),
    ("from nameparser.config.titles import FIRST_NAME_TITLES", ImportError),
    ("from nameparser.config.suffixes import SUFFIX_NOT_ACRONYMS", ImportError),
    ("from nameparser.config.titles import TITLES", ModuleNotFoundError),
    ("from nameparser import HumanName", ImportError),
])
def test_the_1x_imports_fail(statement: str, error: type[Exception]) -> None:
    # #357's acceptance, as written: the 1.x spellings fail at the
    # import, with no DeprecationWarning bridge left to serve them
    with pytest.raises(error):
        exec(statement, {})  # noqa: S102


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
    import nameparser._match
    import nameparser._parser
    import nameparser._policy
    import nameparser._suggest
    import nameparser._types
    from nameparser._types import _guarded_getstate, _guarded_setstate

    # _pipeline internals (ParseState, WorkToken, ...) are exempt: they
    # are never pickled and are not public API.
    modules = (nameparser._types, nameparser._lexicon,
               nameparser._policy, nameparser._locale, nameparser._parser,
               nameparser._match, nameparser._suggest)
    for module in modules:
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if not dataclasses.is_dataclass(cls):
                continue
            if cls.__name__ == "_LexiconSets":
                # never pickled: a Lexicon pickles its fields and
                # rebuilds this from them at load (#754, 4i-a)
                continue
            if cls.__name__ in ("Lexicon", "LexiconReading"):
                # each keeps a copy of the guard, layering keeping
                # _lexicon import-free of _types (LexiconReading, 4i-b)
                assert "__getstate__" in cls.__dict__
                assert "__setstate__" in cls.__dict__
                continue
            assert cls.__dict__.get("__getstate__") is _guarded_getstate, cls
            assert cls.__dict__.get("__setstate__") is _guarded_setstate, cls


# -- the compiled sets are read through Lexicon._sets (#754, 4i-a) --------

#: The checkout these tests sit in, for tools/: not PKG.parent, which
#: is site-packages when the suite runs against the installed package
#: (tests/checkout.py).
_REPO = ROOT

#: Where a parse reads vocabulary: every library module but `_lexicon`,
#: which owns the fields and fills `_sets` from them. A vocabulary
#: field read here must go through `<lexicon>._sets`, so that 4i-b can
#: make the compiled fields internal without touching a reader.
_LIBRARY_READERS = sorted(
    p for p in [*PKG.glob("*.py"), *PKG.glob("_pipeline/*.py"),
                *PKG.glob("locales/*.py")]
    if p.name != "_lexicon.py")

#: Every tool. Their own counters and records reuse the field names
#: (`local_corpora`'s `found.titles`), so a tool is checked by what a
#: read is taken OFF -- a lexicon, by its spelling or by a name bound
#: to one -- rather than by the library's rule that only `_sets` may
#: be read.
_TOOL_READERS = sorted((_REPO / "tools").rglob("*.py"))

#: Names that hold no lexicon though they carry an attribute of a
#: vocabulary field's name: `read` is a `TailRead`, whose `titles` is
#: the title words of a segment's trailing run (_assign, _group).
_NOT_A_LEXICON = frozenset({"read"})


def _lexiconish(node: ast.expr | None, aliases: frozenset[str]) -> bool:
    """`lexicon`, `lex`, `<x>.lexicon`, `Lexicon.default()` or
    `Lexicon.empty()`, or a name bound to one of those (`aliases`)."""
    if isinstance(node, ast.Name):
        return node.id in ("lexicon", "lex") or node.id in aliases
    if isinstance(node, ast.Attribute):
        return node.attr == "lexicon"
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("default", "empty")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "Lexicon")


def _from_sets(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "_sets"


def _bindings(tree: ast.AST) -> list[tuple[str, int, ast.expr | None,
                                           ast.expr | None]]:
    """(name, line, value, annotation) for every binding of a plain
    name: an assignment, annotated or augmented, a walrus, a for or
    comprehension target, a parameter, a with or except target. The
    value is None where the form gives a name no single value of its
    own (a parameter, a loop target, one name of an unpacking)."""
    out: list[tuple[str, int, ast.expr | None, ast.expr | None]] = []

    def target(t: ast.expr, value: ast.expr | None) -> None:
        if isinstance(t, ast.Name):
            out.append((t.id, t.lineno, value, None))
        elif isinstance(t, (ast.Tuple, ast.List)):
            for elt in t.elts:
                target(elt, None)
        elif isinstance(t, ast.Starred):
            target(t.value, None)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                target(t, node.value)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(node.target, ast.Name) and (
                    isinstance(node, ast.AugAssign) or node.value is not None):
                out.append((node.target.id, node.lineno, node.value,
                            getattr(node, "annotation", None)))
        elif isinstance(node, ast.NamedExpr):
            target(node.target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            target(node.target, None)
        elif isinstance(node, ast.withitem) and node.optional_vars:
            target(node.optional_vars, None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.append((node.name, node.lineno, None, None))
        elif isinstance(node, ast.arguments):
            for arg in [*node.posonlyargs, *node.args, *node.kwonlyargs,
                        *filter(None, (node.vararg, node.kwarg))]:
                out.append((arg.arg, arg.lineno, None, arg.annotation))
    return out


def _lexicon_aliases(
        bindings: list[tuple[str, int, ast.expr | None, ast.expr | None]],
) -> frozenset[str]:
    """The names some binding gives a lexicon: by its value's spelling,
    by another such name, or by a `Lexicon` annotation."""
    aliases: frozenset[str] = frozenset()
    while True:
        grown = aliases | {
            name for name, _, value, annotation in bindings
            if _lexiconish(value, aliases) or (
                annotation is not None
                and "Lexicon" in ast.unparse(annotation))}
        if grown == aliases:
            return aliases
        aliases = frozenset(grown)


def _direct_reads(source: str, library: bool) -> list[tuple[int, str]]:
    """(line, field) for every vocabulary field `source` reads off a
    lexicon rather than through its `_sets`: an attribute load; a
    `getattr` of a lexicon, by its spelling or through a name bound to
    one, or, in the library, of a field named as a constant off
    anything but a `_sets`; and a name `sets` bound by any form but an
    assignment from a `_sets` (which would make the attribute rule's
    `sets` a lexicon), reported as `sets =`.

    Its limits, each a reach no reader has today: a lexicon handed
    through a container, a call's return or an attribute other than
    `.lexicon` (`self.lex.titles` in a tool) is not followed, and an
    alias is per module, not per scope, so a name that holds a lexicon
    in one function counts as one in every other."""
    from nameparser._lexicon import _VOCAB_FIELDS
    tree = ast.parse(source)
    bindings = _bindings(tree)
    aliases = _lexicon_aliases(bindings)
    found = [(line, "sets =") for name, line, value, _ in bindings
             if name == "sets" and not _from_sets(value)]
    sets_ok = not found
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and node.attr in _VOCAB_FIELDS
                and isinstance(node.ctx, ast.Load)):
            base = node.value
            if library:
                if not (_from_sets(base)
                        or (isinstance(base, ast.Name) and (
                            (base.id == "sets" and sets_ok)
                            or base.id in _NOT_A_LEXICON))):
                    found.append((node.lineno, node.attr))
            elif _lexiconish(base, aliases):
                found.append((node.lineno, node.attr))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "getattr" and node.args):
            obj = node.args[0]
            named = (len(node.args) > 1
                     and isinstance(node.args[1], ast.Constant)
                     and node.args[1].value in _VOCAB_FIELDS)
            if _lexiconish(obj, aliases) or (
                    library and named and not _from_sets(obj)
                    and not (isinstance(obj, ast.Name) and obj.id == "sets"
                             and sets_ok)):
                found.append((node.lineno, "getattr"))
    return sorted(found)


def _readers() -> list[tuple[pathlib.Path, bool]]:
    return ([(p, True) for p in _LIBRARY_READERS]
            + [(p, False) for p in _TOOL_READERS])


def test_the_reader_lists_name_files_that_exist() -> None:
    # a renamed tool or stage would otherwise drop out of the check
    # below in silence, an empty scope passing it
    assert len(_LIBRARY_READERS) > 20
    for path, _ in _readers():
        assert path.is_file(), path


def _vocab_field_ids() -> list[str]:
    from nameparser._lexicon import _VOCAB_FIELDS
    return list(_VOCAB_FIELDS)


@pytest.mark.parametrize("field", _vocab_field_ids())
def test_no_reader_takes_a_vocabulary_field_off_a_lexicon(field: str) -> None:
    # 4i-a: the parse, the renderer, the parser and the tools read the
    # vocabulary sets through Lexicon._sets (_lexicon._LexiconSets),
    # never the public fields 4i-b makes internal. Per field, so that
    # the field a stray read names is the failing test's id.
    stray = [f"{path.relative_to(PKG.parent if library else _REPO)}:{line}"
             for path, library in _readers()
             for line, name in _direct_reads(path.read_text(), library)
             if name in (field, "getattr", "sets =")]
    assert not stray, stray


@pytest.mark.parametrize("field", _vocab_field_ids())
@pytest.mark.parametrize("spelling,library", [
    ("lexicon.{f}", True), ("state.lexicon.{f}", True), ("lex.{f}", True),
    ("self.lexicon.{f}", True), ("Lexicon.default().{f}", True),
    ("lexicon.{f}", False), ("lex.{f}", False), ("parser.lexicon.{f}", False),
    ("Lexicon.default().{f}", False),
])
def test_the_check_finds_a_direct_read(field: str, spelling: str,
                                       library: bool) -> None:
    # the negative control, per field and spelling: a read the check
    # above must refuse
    source = f"x = 'w' in {spelling.format(f=field)}\n"
    assert _direct_reads(source, library) == [(1, field)]
    through = f"x = 'w' in {spelling.format(f='_sets.' + field)}\n"
    assert _direct_reads(through, library) == []


@pytest.mark.parametrize("source,expected", [
    ("getattr(lexicon, name)\n", [(1, "getattr")]),
    ("getattr(lexicon._sets, name)\n", []),
    ("sets = lexicon\nsets.titles\n", [(1, "sets ="), (2, "titles")]),
    ("sets = lexicon._sets\nsets.titles\n", []),
    ("sets = lexicon._sets\ngetattr(sets, name)\n", []),
    ("read.titles\n", []),
    ("found.titles\n", [(1, "titles")]),
    # getattr through an alias, or of a field named as a constant
    ("lx = state.lexicon\ngetattr(lx, name)\n", [(2, "getattr")]),
    ("def f(lx: Lexicon):\n    getattr(lx, name)\n", [(2, "getattr")]),
    ("getattr(obj, 'titles')\n", [(1, "getattr")]),
    ("getattr(obj, name)\n", []),
    # every form that binds `sets` but an assignment from a `_sets`
    ("sets: object = lexicon\nsets.titles\n", [(1, "sets ="), (2, "titles")]),
    ("(sets := lexicon)\nsets.titles\n", [(1, "sets ="), (2, "titles")]),
    ("sets, other = lexicon._sets, 1\nsets.titles\n",
     [(1, "sets ="), (2, "titles")]),
    ("for sets in lexicons:\n    sets.titles\n", [(1, "sets ="), (2, "titles")]),
    ("def f(sets):\n    return sets.titles\n", [(1, "sets ="), (2, "titles")]),
    ("with open() as sets:\n    sets.titles\n", [(1, "sets ="), (2, "titles")]),
])
def test_the_check_finds_a_roster_read_and_an_alias(
        source: str, expected: list[tuple[int, str]]) -> None:
    assert _direct_reads(source, True) == expected


@pytest.mark.parametrize("source,expected", [
    # the AGENTS.md recipe's own spelling, and an alias of an alias
    ("L = Parser().lexicon\nL.titles - L.suffix_words\n",
     [(2, "suffix_words"), (2, "titles")]),
    ("a = Lexicon.default()\nb = a\nb.particles\n", [(3, "particles")]),
    ("def f(lx: Lexicon):\n    return lx.titles\n", [(2, "titles")]),
    ("def f(lx: 'Lexicon | None'):\n    return lx.titles\n", [(2, "titles")]),
    ("L = Parser().lexicon\ngetattr(L, name)\n", [(2, "getattr")]),
    # what a tool's own records may spell
    ("found.titles\nname.given_names\n", []),
    ("getattr(found, 'titles')\n", []),
])
def test_the_check_finds_a_tool_read_through_an_alias(
        source: str, expected: list[tuple[int, str]]) -> None:
    assert _direct_reads(source, False) == expected


#: The reads 4i-a moved, as the check counts them on today's sources
#: with `._sets` taken out again: the recorded negative control over
#: the real tree, so the check above cannot pass because its walk
#: reaches nothing. The library's 134 on #1138's tree (140 since
#: #1006's, below) were 125 attribute loads, 3 roster
#: `getattr`s, all through `sets`, which the undone `sets = lexicon`
#: makes a lexicon, and the 6 `sets =` bindings (#1000's Ph./D. gate
#: added one binding and four of the loads; #999's gate
#: one load, its `titles_ambiguous` half, and its article partner two,
#: `title_styles` and `conjunctions`, `title_abbreviations` being no
#: 2.x field the check counts; #1039 moved two `agnomens` loads to
#: `title_case_name_words`, no 2.x field either; #694's phrase gate
#: one load, `bound_given_names`; #792's set-apart clause two `sets =`
#: bindings and nine loads in `_vocab` and two loads in `_post_rules`,
#: taking extract's four suffix-set loads out, 119 -> 128; #1088's
#: set-apart word asking `suffix_as_written`, three loads out of
#: `_vocab` and both of `_post_rules`' copies of the dotted member
#: test, 128 -> 123; its parity fix moving the initials test into
#: `_vocab.reads_as_initials` and the dotted test into
#: `_vocab.dotted_member`, 123 -> 124, and its simplify pass asking
#: two suffix sets inline ahead of `suffix_as_written`, 124 -> 126, and
#: `reads_as_initials` leaving a credential listed whole unsplit, two
#: more, 126 -> 128; #1103's cut of a joined credential reading the
#: longest listed run of each suffix set, two more, 128 -> 130;
#: #1138's member test for a chunk, the two ambiguous suffix sets,
#: and the tests of a credential that settles one, 130 -> 134;
#: #1131's every-chunk reading of a word the periods join, the
#: honorific tail, the titles and the acronyms its set-apart word
#: asks first, its S11 guard and the initials test of a word the
#: periods join, 134 -> 139; #1006's name matching dropping a hyphen
#: half that is a listed particle, the particles, 139 -> 140;
#: #1241's apostrophe opening a listed particle, the particles,
#: 140 -> 141; case repair's opening `ter` and `der`, the particles
#: before one, 141 -> 142; #490's C4 count asking for a title behind
#: a dotted run, the titles, 142 -> 143; classify's gate on that
#: run's fold, the contested titles and the modifiers, 143 -> 145;
#: #1296's run of initials listed whole, its `sets =` binding and the
#: roster `getattr` through it, 145 -> 147; #1230/#1235's glued word,
#: the chunks read alone, the titles a chunk chains, the word after
#: the stop and the end-of-name report's suffix and title tests,
#: 147 -> 169; #1071's glued saint particle, the saint particles,
#: 169 -> 170, and the maiden marker ending a part's own words, 170 ->
#: 171; its review's suffix-word refusal after the stop, 171 -> 179;
#: its fix-diff review's own name test for the saint division (titles
#: of every kind, connectives), 179 -> 185; `_suggest`'s particle
#: read, 185 -> 186; its leading title read, which reads a name's
#: evidence past its titles, 186 -> 187; #317's front peel, the glued
#: titles its gate and the peel read and the titles a site steps past,
#: 187 -> 190, and its review dropping the peel's own titles test,
#: 190 -> 188, its `sets =` binding and the titles read through it;
#: #1319's dotted titles, T8's and the peel's titles, the peel's
#: `sets =` binding and its modifiers, 188 -> 192, and its fix-commit
#: review's dotted-chunk and modifier-head reads, 192 -> 194; #1323's
#: review, the chunk test of a joined word behind the pair reading the
#: generation and gated-word sets, 194 -> 196; #659's capitals peel,
#: its `sets =` binding and the four suffix sets it reads, 196 -> 201,
#: its review's conjunctions read for a run, 201 -> 202, and the
#: ambiguous suffix halves dropped from the peel as subsets, 202 -> 200;
#: #1369's capitals vote asking the base parse where a family word is
#: a listed title, its `sets =` binding and the two title sets it
#: reads, 200 -> 203);
#: the tools' first 20 are 18
#: attribute loads, every tool scanned, and config_diff.py's
#: `sets =` binding and the roster `getattr` through it (its
#: `changed_words`, which compares two lexicons set by set), which
#: with one of the loads moved the count from 16; the 18th load is
#: tools/vocab/order_names.py reading `locales.ZH.lexicon._sets.surnames`
#: (group suggestions); order_names.py's `listed_titles` adds four,
#: its `sets =` binding and the three title sets it reads through it
#: (the given names refusing a listed title, 2026-11-12), 20 -> 24;
#: and tools/vocab/familiar_candidates.py reading the default's
#: titles, to drop a title from a name before it pairs a familiar
#: form, 24 -> 25. 4i-a's own count was 114 (on
#: that tree's sources), two of them `getattr`s in
#: `_parser._apply_choice`, which read the sets through
#: `_lexicon._fields_of` from 4i-b until 4i-c retired it.
#: A reader added through `_sets` moves these, and they are re-taken
#: then: they count what the check would refuse with the move undone.
_UNGUARDED_READS = {"library": 203, "tools": 25}


def test_the_check_refuses_every_read_4i_a_moved() -> None:
    counts = {"library": 0, "tools": 0}
    for path, library in _readers():
        undone = path.read_text().replace("._sets", "")
        counts["library" if library else "tools"] += len(
            _direct_reads(undone, library))
    assert counts == _UNGUARDED_READS
