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
# failing input -- or a capitalized phrase in quotes or BACKTICKS,
# which is how names appear in prose ("parsing 'Hans "Hansi" Müller'
# gives ...", or `Beethoven, Ludwig van` in a markdown issue).
#
# The backtick branch was missing until #413, and the cost was not
# marginal: this tracker writes names in backticks because issues are
# markdown, so the corpus whose whole purpose is "what users reported"
# was blind to the way this project reports. 105 names over 222
# issues, none of them in the checked-in corpus, and they include the
# headline example of the issue that fixed them -- `Beethoven, Ludwig
# van` (#379), `Berg, Jan vd` (#380), `Ursula von der Leyen geb.
# Albrecht` (#399). That last one sat in its issue's TITLE while #399
# shipped noting the class was invisible to this harness.
_CANDIDATE = re.compile(
    r"""HumanName\(\s*["']([^"']{3,60})["']"""
    r"""|["']([A-Z][^"'\n]{4,60})["']"""
)
# Backticks are scanned SEPARATELY, not as a third alternative, and the
# reason is a name this cost before it was split out. A reporter writes
# the failing input as `HumanName("John  Q  Doe")` -- a call inside a
# code span. Regex scanning takes the leftmost match, so a backtick
# alternative starts one character before the HumanName branch can and
# swallows the whole span, harvesting the CALL and losing the name
# inside it. Two passes over the same text cannot shadow each other.
_BACKTICKED = re.compile(r"""`([A-Z][^`\n]{4,60})`""")
# ... and the same code span is dropped from the backtick pass, or the
# call itself is harvested as a name. The HumanName branch above has
# already taken the argument out of it, which is the part anyone meant.
_A_CALL = re.compile(r"""[A-Za-z_]\w*\(""")
# Structural characters that mean we caught code or markup, not a name.
#
# Extended when the backtick branch landed (#413): backticks wrap code
# far more often than quotes do, so the branch admits code-shaped
# strings a quoted phrase rarely produces -- 'Constants.__init__(self,
# **state)', 'DEVIATION #364', 'SUFFIX_ACRONYMS ∩ SUFFIX_NOT_ACRONYMS'.
# None of '*#~;_' appears in a name. The one existing corpus entry this
# drops, 'St. ___', is a placeholder rather than a name.
_NOT_A_NAME = set('{}<>=/\\|*#~;_')


def _harvest(text: str) -> set[str]:
    found = set()
    values = [(m.group(1) or m.group(2) or "").strip()
              for m in _CANDIDATE.finditer(text)]
    values += [m.group(1).strip() for m in _BACKTICKED.finditer(text)
               if not _A_CALL.match(m.group(1))]
    for value in values:
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
