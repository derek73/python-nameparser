"""Recorded roster of spellings that have actually shipped wrong in
docs, docstrings, or messages. Add an entry when one is caught; never
remove one without a decisions.md note."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DENYLIST: dict[str, str] = {
    "Policy(segment_scripts=())": (
        "#334/#337: tuple literal fails mypy on this field; "
        "the type-clean spelling is frozenset()"),
    "segment_scripts=()": "#334: same arg-type error, keyword form",
}
SWEEP = ("nameparser", "docs")


def test_no_denylisted_spellings() -> None:
    hits = []
    for d in SWEEP:
        for path in sorted((REPO / d).rglob("*")):
            if path.suffix not in (".py", ".rst", ".md"):
                continue
            if "superpowers" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for bad, why in DENYLIST.items():
                if bad in text:
                    hits.append(f"{path}: {bad!r} ({why})")
    assert not hits, "\n".join(hits)
