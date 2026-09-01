"""Extract every plausible test-name string from the v1 test suite:
string literals passed as the first argument to HumanName(...) calls,
plus string elements/keys of list/dict banks. Dev tooling -- over-
collection is fine, the comparator just parses more names. Output is
one JSON object per line, `{"name": ..., "tests": [...]}`, where
`tests` is the sorted v1 test method names (bare) or bank variable
names (prefixed `bank:`) the string appeared in at the pinned ref --
the shape context the original scrape kept the string but threw away.
A `HumanName(...)` call is labelled by its NEAREST enclosing function,
falling back to the source filename for one at module scope.

PROVENANCE: the checked-in tools/differential/corpus.jsonl was built
against commit 2d5d8c2 ("Trim constant-factor waste on the tokenize
hot path"), the last commit before M12 reconciled/edited the v1 test
banks (M12 rewrote expectations and deleted the bucket-A tests, which
would have shrunk the corpus). Reading historical test content is
fine; per the migration rules, no git *operations* are ever run against
the original (non-worktree) checkout -- this script only shells out to
`git show <ref>:<path>` inside the current worktree's own history,
which contains that commit as an ancestor.

Regenerate with:
    uv run python tools/differential/build_corpus.py --ref 2d5d8c2 \\
        > tools/differential/corpus.jsonl
"""
import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

# Obvious non-names the AST heuristic sweeps up along with real names:
# format-string placeholders, decorators/emails, escape sequences.
_NOISE_CHARS = ("{", "@", "\\")


def _is_name_like(value: str) -> bool:
    return not any(ch in value for ch in _NOISE_CHARS)


def _labelled_strings_from(
        tree: ast.Module, module_label: str) -> dict[str, set[str]]:
    """name -> the v1 test methods (or bank variables) it appeared in.
    This is the metadata the original scrape discarded: v1's test
    names say what shape each name exercised
    (test_title_with_conjunction), and #468's whole complaint is that
    nothing recorded it.

    Single recursive walk, tracking the NEAREST enclosing
    FunctionDef/AsyncFunctionDef as the current label (falling back to
    `module_label`, the source filename, for a HumanName(...) call at
    module scope) -- ast.walk's flat iteration cannot express nearest-
    enclosing, and doing two separate module-wide sweeps double-labels
    a call inside a nested function with both the inner and outer
    names. The bank branch is untouched by this label: a list/dict
    assignment is labelled by its own target name (prefixed `bank:` to
    read apart from a test method at a glance) regardless of what
    function, if any, encloses it.
    """
    found: dict[str, set[str]] = {}

    def _add(value: str, label: str) -> None:
        found.setdefault(value, set()).add(label)

    def _walk(node: ast.AST, label: str) -> None:
        if (isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(
                    node.func, "attr", "")) == "HumanName"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            _add(node.args[0].value, label)
        if isinstance(node, ast.Assign) and isinstance(
                node.value, (ast.List, ast.Tuple, ast.Dict)):
            target_name = getattr(node.targets[0], "id", None)
            bank_label = f"bank:{target_name}" if target_name \
                else "bank:<unnamed>"
            for c in ast.walk(node.value):
                if isinstance(c, ast.Constant) and isinstance(c.value, str) \
                        and " " in c.value and "\n" not in c.value:
                    _add(c.value, bank_label)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _walk(child, child.name)
            else:
                _walk(child, label)

    _walk(tree, module_label)
    return {n: labels for n, labels in found.items() if _is_name_like(n)}


def _working_tree_sources() -> dict[str, str]:
    return {path.name: path.read_text()
            for path in sorted(TESTS.glob("test_*.py"))}


def _ref_sources(ref: str) -> dict[str, str]:
    """Read every top-level tests/test_*.py file as it existed at `ref`,
    via `git show`, without touching the working tree or index."""
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", ref,
         "--", "tests"],
        capture_output=True, text=True, check=True).stdout
    paths = sorted(
        p for p in listing.splitlines()
        if p.startswith("tests/") and Path(p).parent == Path("tests")
        and Path(p).name.startswith("test_") and p.endswith(".py"))
    sources = {}
    for path in paths:
        show = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{ref}:{path}"],
            capture_output=True, text=True, check=True)
        sources[Path(path).name] = show.stdout
    return sources


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--ref", default=None,
        help="git ref to read tests/test_*.py from (via `git show`) "
             "instead of the working tree, e.g. 2d5d8c2 (pre-M12).")
    args = ap.parse_args()

    sources = _ref_sources(args.ref) if args.ref else _working_tree_sources()
    names: dict[str, set[str]] = {}
    for filename, text in sources.items():
        try:
            tree = ast.parse(text, filename=filename)
        except SyntaxError as e:
            print(f"skipping {filename}: {e}", file=sys.stderr)
            continue
        for value, labels in _labelled_strings_from(tree, filename).items():
            names.setdefault(value, set()).update(labels)

    for name in sorted(names):
        print(json.dumps({"name": name, "tests": sorted(names[name])},
                         ensure_ascii=False))
    print(f"{len(names)} names", file=sys.stderr)


if __name__ == "__main__":
    main()
