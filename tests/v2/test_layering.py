"""Enforce the conventions doc's import layering mechanically."""
import ast
import pathlib

import nameparser

PKG = pathlib.Path(nameparser.__file__).parent

# module -> prefixes it may import from within nameparser
ALLOWED = {
    "_types.py": (),
    "_lexicon.py": ("nameparser.config.",),  # DATA modules only, during 2.x
    "_policy.py": ("nameparser._types",),
    "_locale.py": ("nameparser._lexicon", "nameparser._policy"),
}


def _nameparser_imports(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
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
        for imported in _nameparser_imports(PKG / mod):
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
        "Lexicon", "Policy", "PolicyPatch", "PatronymicRule", "UNSET",
        "GIVEN_FIRST", "FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST", "Locale",
    }
    assert expected <= set(nameparser.__all__)
    for name in expected:
        assert getattr(nameparser, name) is not None
