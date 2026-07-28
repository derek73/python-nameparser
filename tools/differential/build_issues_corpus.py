"""Harvest name-like strings from this project's GitHub issue tracker.

Companion to build_corpus.py, and deliberately a SEPARATE corpus with a
separate builder. The two have different provenance and different
blind spots:

- corpus.jsonl comes from v1's own test suite at a pinned git ref. It
  is reproducible forever, and it is structurally blind to anything
  2.0 added -- v1's authors had no reason to write a test for a
  typographic nickname delimiter or a Cyrillic title.
- corpus_issues.jsonl comes from what USERS REPORTED, which is the
  adversarial half: names that broke the parser in the field, in the
  reporter's own words. On its first run it surfaced five intended-
  but-unclassified 2.0 behaviors and one shape (a LEADING "Ph. D.")
  that no test had considered.

Reproducibility differs, and that is why these are not merged. A git
ref is immutable; an issue tracker is not. Re-running this later can
only ADD names as new issues arrive, so the checked-in file is the
snapshot under test and regeneration is an explicit, reviewable act.

Over-collection is fine, same as build_corpus.py: the comparator just
parses more names. Junk like 'Bridge (1.4)' costs one parse and
produces no diff.

Regenerate with (requires `gh` authenticated to the repo):
    uv run python tools/differential/build_issues_corpus.py \\
        > tools/differential/corpus_issues.jsonl
"""
import json
import re
import subprocess
import sys

# Either an explicit HumanName("...") call -- the reporter showing the
# failing input -- or a quoted, capitalized phrase, which is how names
# appear in prose ("parsing 'Hans "Hansi" Müller' gives ...").
_CANDIDATE = re.compile(
    r"""HumanName\(\s*["']([^"']{3,60})["']"""
    r"""|["']([A-Z][^"'\n]{4,60})["']"""
)
# Structural characters that mean we caught code or markup, not a name.
_NOT_A_NAME = set('{}<>=/\\|')


def _harvest(text: str) -> set[str]:
    found = set()
    for match in _CANDIDATE.finditer(text):
        value = (match.group(1) or match.group(2) or "").strip()
        # Require an internal space: a single word is a surname at best
        # and carries no structure to disagree about.
        if value and " " in value and not (_NOT_A_NAME & set(value)):
            found.add(value)
    return found


def main() -> None:
    raw = subprocess.run(
        ["gh", "issue", "list", "--state", "all", "--limit", "1000",
         "--json", "number,title,body"],
        capture_output=True, text=True, check=True).stdout
    issues = json.loads(raw)
    names: set[str] = set()
    for issue in issues:
        names |= _harvest(
            f"{issue.get('title') or ''}\n{issue.get('body') or ''}")
    for name in sorted(names):
        print(json.dumps(name, ensure_ascii=False))
    print(f"{len(names)} names from {len(issues)} issues", file=sys.stderr)


if __name__ == "__main__":
    main()
