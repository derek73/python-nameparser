"""Split docs/design/rules.md and decisions.md into one file per entry,
and rewrite citations to the new form (#713). A one-shot migration.

    uv run python tools/split_design_docs.py split
    uv run python tools/split_design_docs.py rewrite

`split` writes docs/design/rules/ and docs/design/decisions/, each with
a README.md holding the old file's preamble and an index, and deletes
the two files. It checks first that joining the pieces back gives each
original byte for byte, and writes nothing unless both do. `rewrite`
turns `rules.md#S2` into `rules/S2` and `decisions.md#key` into
`decisions/key` in every tracked .py, .md and .rst file.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.v2.design_docs import SECTION_ORDER, stem_for  # noqa: E402

#: names for the rules no decisions entry names (measured 2026-10-17);
#: every other rule takes its decisions entry's name
RULE_NAMES = {
    "C2": "parts past the second comma",
    "O3": "compound family names written unmarked",
    "P4": "a particle at the front of the name",
    "R1": "fields are views of the parsed words",
    "S1": "a bracketed credential is not a nickname",
    "S3": "credentials written with interior periods",
    "T2": "the katakana middle dot divides like a space",
}
LEDGER = "differential-ledger"
LEDGER_NAME = "the differential ledger's arcs"
INDEX_MARK = "## Index\n\n"

_SECTION_RE = re.compile(r"## (?P<title>.*\((?P<letter>[A-Z])\))\s*$")
_RULE_RE = re.compile(r"(?P<key>[A-Z]\d+)\.\s")
_KEY_RE = re.compile(r"[^\s—,]+")
_FILE_RE = re.compile(r"\]\(([^)/]+\.md)\)")
_CITE_RE = re.compile(r"\b(rules|decisions)\.md#")


def _read(path: Path) -> str:
    # newline="" keeps the bytes; Path.read_text takes it only from 3.13
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _lines(text: str) -> list[str]:
    # newline only: str.splitlines also breaks at U+2028 and friends
    return re.findall(r"[^\n]*\n|[^\n]+$", text)


def _split_readme(readme: str) -> tuple[str, list[str]]:
    assert readme.count(INDEX_MARK) == 1, "README needs one index mark"
    preamble, index = readme.split(INDEX_MARK)
    return preamble, _FILE_RE.findall(index)


def _section_name(title: str) -> str:
    return re.sub(r"\s*\([A-Z]\)$", "", title)


def split_rules(text: str, names: dict[str, str]) -> dict[str, str]:
    preamble: list[str] = []
    chunks: list[tuple[str, str, list[str]]] = []   # (stem, title, lines)
    for line in _lines(text):
        sm, rm = _SECTION_RE.match(line), _RULE_RE.match(line)
        if sm:
            title = sm.group("title")
            chunks.append((stem_for(sm.group("letter"), _section_name(title)),
                           title, [line]))
        elif rm:
            key = rm.group("key")
            title = f"{key} — {names[key]}"
            chunks.append((stem_for(key, names[key]), title,
                           [f"# {title}\n\n", line]))
        elif chunks:
            chunks[-1][2].append(line)
        else:
            preamble.append(line)
    head = "".join(preamble)
    assert INDEX_MARK not in head
    index = []
    for stem, title, _ in chunks:
        if _RULE_RE.match(title.replace(" — ", ". ", 1)):
            index.append(f"- [{title}]({stem}.md)\n")
        else:
            index.append(f"{chr(10) if index else ''}## [{title}]({stem}.md)"
                         "\n\n")
    files = {f"{stem}.md": "".join(body) for stem, _, body in chunks}
    files["README.md"] = head + INDEX_MARK + "".join(index)
    return files


def join_rules(files: dict[str, str]) -> str:
    preamble, order = _split_readme(files["README.md"])
    out = [preamble]
    for name in order:
        body = files[name]
        if re.match(r"[A-Z]\d+-", name):
            heading, rest = body.split("\n\n", 1)
            assert heading.startswith("# "), name
            body = rest
        out.append(body)
    return "".join(out)


def split_decisions(text: str, sections: dict[str, str]
                    ) -> tuple[dict[str, str], list[str]]:
    preamble: list[str] = []
    chunks: list[tuple[str, str, list[str]]] = []   # (key, title, lines)
    for line in _lines(text):
        if line.startswith("### "):
            title = line[4:].rstrip("\n")
            km = _KEY_RE.match(title)
            assert km, line
            chunks.append((km.group(), title, [line]))
        elif chunks:
            chunks[-1][2].append(line)
        else:
            preamble.append(line)
    order = [key for key, _, _ in chunks]
    head = "".join(preamble)
    assert INDEX_MARK not in head
    files: dict[str, str] = {}
    titles: dict[str, tuple[str, str]] = {}          # key -> (title, file)
    for key, title, body in chunks:
        text_body = "".join(body)
        if key == LEDGER:
            name = f"{LEDGER}.md"
            if name not in files:
                files[name] = f"# {LEDGER} — {LEDGER_NAME}\n\n"
                titles[key] = (f"{LEDGER} — {LEDGER_NAME}", name)
            files[name] += "##" + text_body[3:]
            continue
        assert key not in titles, f"decisions key {key} repeats"
        entry_name = title.split(" — ", 1)[1] if " — " in title else ""
        assert entry_name or not re.fullmatch(r"[A-Z]\d+", key), title
        name = f"{stem_for(key, entry_name)}.md"
        files[name] = "#" + text_body[3:]
        titles[key] = (title, name)
    index = []
    rule_keys = [k for k in titles if re.fullmatch(r"[A-Z]\d+", k)]
    for letter in SECTION_ORDER:
        group = sorted((k for k in rule_keys if k[0] == letter),
                       key=lambda k: int(k[1:]))
        if group:
            index.append(f"## {sections[letter]}\n\n")
            index += [f"- [{titles[k][0]}]({titles[k][1]})\n" for k in group]
            index.append("\n")
    index.append("## Named topics\n\n")
    index += [f"- [{titles[k][0]}]({titles[k][1]})\n"
              for k in sorted(titles) if k not in rule_keys]
    files["README.md"] = head + INDEX_MARK + "".join(index)
    return files, order


def join_decisions(files: dict[str, str], order: list[str]) -> str:
    preamble, names = _split_readme(files["README.md"])
    by_key = {}
    for name in names:
        km = _KEY_RE.match(files[name][2:])
        assert km, name
        by_key[km.group()] = name
    ledger = files[by_key[LEDGER]].split("\n\n", 1)[1] if LEDGER in by_key \
        else ""
    arcs = iter(re.split(rf"(?m)^(?=## {LEDGER})", ledger)[1:])
    out = [preamble]
    for key in order:
        out.append("#" + next(arcs) if key == LEDGER
                   else "###" + files[by_key[key]][1:])
    return "".join(out)


def rewrite_citations(text: str) -> str:
    return _CITE_RE.sub(r"\1/", text)


def _decision_names(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(
        r"(?m)^### ([A-Z]\d+) — (.+)$", text)}


def _split(root: Path) -> None:
    design = root / "docs" / "design"
    rules_md, decisions_md = design / "rules.md", design / "decisions.md"
    rules, decisions = _read(rules_md), _read(decisions_md)
    names = {**_decision_names(decisions), **RULE_NAMES}
    sections = {m.group("letter"): m.group("title")
                for line in _lines(rules) if (m := _SECTION_RE.match(line))}
    rule_files = split_rules(rules, names)
    dec_files, order = split_decisions(decisions, sections)
    # every check before any write
    assert join_rules(rule_files) == rules, "rules.md does not round-trip"
    assert join_decisions(dec_files, order) == decisions, (
        "decisions.md does not round-trip")
    for folder in ("rules", "decisions"):
        assert not (design / folder).exists(), f"{folder}/ already exists"
    print("round trip: rules.md and decisions.md both byte-identical")
    for folder, files in (("rules", rule_files), ("decisions", dec_files)):
        (design / folder).mkdir()
        for name, body in files.items():
            (design / folder / name).write_text(body, encoding="utf-8",
                                                newline="")
        print(f"{folder}/: {len(files)} files")
    rules_md.unlink()
    decisions_md.unlink()


def _rewrite(root: Path) -> None:
    skip = {"tools/split_design_docs.py", "tests/v2/test_split_design_docs.py"}
    tracked = subprocess.run(["git", "ls-files"], cwd=root, check=True,
                             capture_output=True, text=True).stdout.split()
    changed = subs = 0
    for rel in tracked:
        if rel in skip or not rel.endswith((".py", ".md", ".rst")):
            continue
        path = root / rel
        if not path.exists():
            continue
        new, n = _CITE_RE.subn(r"\1/", _read(path))
        if n:
            path.write_text(new, encoding="utf-8", newline="")
            changed, subs = changed + 1, subs + n
    print(f"rewrote {subs} citations in {changed} files")


def main(argv: list[str], root: Path = ROOT) -> int:
    if argv == ["split"]:
        _split(root)
    elif argv == ["rewrite"]:
        _rewrite(root)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
