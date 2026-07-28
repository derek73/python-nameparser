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


def validate_rules(rules: list[dict[str, object]]) -> None:
    """Reject malformed allowlist rules LOUDLY at startup. A rule with
    neither name_regex nor fields would match every diff and shadow
    every later rule -- the harness would report false confidence,
    the exact failure it exists to prevent."""
    for i, rule in enumerate(rules):
        issue = rule.get("issue")
        if not isinstance(issue, str) or not issue:
            raise SystemExit(
                f"expected_changes.toml rule #{i + 1} has no string "
                f"'issue': {rule!r}")
        if not isinstance(rule.get("name_regex"), str) \
                and not isinstance(rule.get("fields"), list):
            raise SystemExit(
                f"expected_changes.toml rule #{i + 1} ({issue!r}) has "
                f"neither 'name_regex' nor 'fields' -- it would match "
                f"every diff and shadow every later rule")


def classify(name: str, diff_fields: set[str],
             rules: list[dict[str, object]]) -> str | None:
    for rule in rules:
        name_regex = rule.get("name_regex")
        if isinstance(name_regex, str) and not re.search(name_regex, name):
            continue
        fields = rule.get("fields")
        if isinstance(fields, list) and not diff_fields <= set(fields):
            continue
        return rule["issue"]  # type: ignore[return-value]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    # Both corpora by default: they have different blind spots (see
    # build_issues_corpus.py), and one that has to be asked for by name
    # is one that stops being run.
    ap.add_argument("--corpus", action="append", metavar="PATH",
                    help="corpus file; repeatable. Defaults to every "
                         "corpus*.jsonl beside this script.")
    args = ap.parse_args()
    paths = ([Path(p) for p in args.corpus] if args.corpus
             else sorted(HERE.glob("corpus*.jsonl")))
    rules = tomllib.loads(
        (HERE / "expected_changes.toml").read_text()).get("change", [])
    validate_rules(rules)
    # Most-specific-first: a name_regex rule outranks a fields-only rule
    # wherever both match, so file order stops being load-bearing. The
    # sort is stable, so rules within a tier keep the order they were
    # written in.
    rules.sort(key=lambda r: not isinstance(r.get("name_regex"), str))
    # A glob that matches nothing must not read as "everything passed".
    # Comparing zero names would print 0 unexplained and exit 0 -- the
    # harness's own stated nightmare (see validate_rules), and a
    # regression from the single hard-coded path this replaced, which
    # raised FileNotFoundError.
    if not paths:
        raise SystemExit(
            f"no corpus files found in {HERE}: expected corpus*.jsonl")
    per_file = {}
    corpus = []
    for path in paths:
        names = [json.loads(line)
                 for line in path.read_text().splitlines() if line.strip()]
        if not names:
            raise SystemExit(f"{path.name} is empty; comparison aborted")
        per_file[path.name] = len(names)
        corpus.extend(names)
    # dedupe across files, keeping first-seen order stable for output
    corpus = list(dict.fromkeys(corpus))
    # per-file counts, not just the total: a corpus that shrinks or
    # vanishes is only visible if its own number is printed
    print("corpora: " + ", ".join(f"{name} ({n})"
                                  for name, n in per_file.items()))

    proc = subprocess.Popen(
        ["uv", "run", "--no-project", str(HERE / "worker_v1.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    v1_input = "".join(json.dumps(n, ensure_ascii=False) + "\n"
                        for n in corpus)
    v1_lines, _ = proc.communicate(v1_input)
    v1_results = [json.loads(line) for line in v1_lines.splitlines()]
    # hard checks, not asserts: -O must not turn a crashed worker into
    # a truncated-but-green comparison
    if proc.returncode != 0:
        raise SystemExit(
            f"worker_v1.py exited {proc.returncode}; comparison aborted")
    if len(v1_results) != len(corpus):
        raise SystemExit(
            f"worker returned {len(v1_results)} results for "
            f"{len(corpus)} corpus names; comparison aborted")

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
