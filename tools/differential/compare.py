"""Differential harness (migration spec S5): 1.4-on-PyPI vs the working
tree over the corpus. Every diff must classify against
expected_changes.toml or the run fails.

    uv run python tools/differential/compare.py [--corpus corpus.jsonl]
"""
import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ("title", "first", "middle", "last", "suffix", "nickname",
          "maiden")


def classify(name: str, diff_fields: set[str],
             rules: list[dict[str, object]]) -> str | None:
    for rule in rules:
        name_regex = rule.get("name_regex")
        if isinstance(name_regex, str) and not re.search(name_regex, name):
            continue
        fields = rule.get("fields")
        if isinstance(fields, list) and not diff_fields <= set(fields):
            continue
        issue = rule["issue"]
        assert isinstance(issue, str)
        return issue
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(HERE / "corpus.jsonl"))
    args = ap.parse_args()
    rules = tomllib.loads(
        (HERE / "expected_changes.toml").read_text()).get("change", [])
    corpus = [json.loads(line) for line in
              Path(args.corpus).read_text().splitlines() if line.strip()]

    proc = subprocess.Popen(
        ["uv", "run", "--no-project", str(HERE / "worker_v1.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    v1_input = "".join(json.dumps(n, ensure_ascii=False) + "\n"
                        for n in corpus)
    v1_lines, _ = proc.communicate(v1_input)
    v1_results = [json.loads(line) for line in v1_lines.splitlines()]
    assert len(v1_results) == len(corpus), "worker line count mismatch"

    from nameparser import HumanName  # the working tree (2.0 facade)
    by_issue: dict[str, list[str]] = {}
    unexplained: list[tuple[str, dict[str, str], dict[str, str]]] = []
    for name, old in zip(corpus, v1_results):
        new = {k: v or "" for k, v in HumanName(name).as_dict().items()}
        diff = {f for f in FIELDS if old.get(f, "") != new.get(f, "")}
        if not diff:
            continue
        issue = classify(name, diff, rules)
        if issue is None:
            unexplained.append((name, old, new))
        else:
            by_issue.setdefault(issue, []).append(name)

    print(f"corpus: {len(corpus)} names; "
          f"intentional diffs: {sum(map(len, by_issue.values()))}; "
          f"unexplained: {len(unexplained)}\n")
    for issue, names in sorted(by_issue.items()):
        print(f"## {issue} ({len(names)})")
        for n in names[:10]:
            print(f"  {n!r}")
        print()
    for name, old, new in unexplained:
        print(f"UNEXPLAINED {name!r}")
        for f in FIELDS:
            if old.get(f, "") != new.get(f, ""):
                print(f"    {f}: {old.get(f, '')!r} -> {new.get(f, '')!r}")
    return 1 if unexplained else 0


if __name__ == "__main__":
    raise SystemExit(main())
