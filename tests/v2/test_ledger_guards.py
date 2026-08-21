"""Pins the differential harness's hand copies to their sources, and
bounds what each ledger rule may claim.

tools/differential/expected_since_*.toml classifies a v1-vs-v2 diff as
an INTENDED change. A rule matching too widely absorbs a real
regression and the run exits 0, so these files carry hand copies of
nameparser constants -- script ranges, honorific and maiden vocabulary
-- that a TOML file could not import if it wanted to. Nothing else
checks them.

Most of what is here reads a rule's SYNTAX -- which spans a character
class declares, which members an alternation offers. Those are exact
where they apply and blind where they do not: five review rounds each
found a widening spelled just outside whichever one had been added
last (#333, #350). The rest read the CORPORA, asking what a rule
actually claims of the names the harness will ever be asked about;
those cannot be dodged by notation, because they do not read notation
-- though a recorded claim can be re-recorded, which is why the syntax
guards stay.

Three tests are neither kind. They keep this file's own inputs honest:
the ledger glob, the roster-versus-filesystem staleness check, and the
pin holding a GENERATED corpus equal to what its generator would
write.

Split from test_regex_sync.py, which shares none of this (#352).
"""
import hashlib
import itertools
import json
import re
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

import pytest

from nameparser import _policy
from nameparser._policy import Script
# The parser's own fold, imported rather than reimplemented: a
# hand-written one here stripped commas, parens, brackets and quotes,
# five character classes neither the lexicon's fold nor config's
# assert_normalized touches -- looser in the dangerous direction, and a
# hand copy of a constant with a source of truth, inside the module
# written to forbid exactly that.
from nameparser._lexicon import _normalize
from nameparser.config.maiden_markers import MAIDEN_MARKERS
from nameparser.config.particles import PARTICLES
from nameparser.config.suffixes import (
    GLUED_HONORIFICS, SUFFIX_ACRONYMS_AMBIGUOUS, SUFFIX_WORDS)

from ._differential_fixtures import (
    _CORPUS_NAMES, _LEDGERS, _TOOLS, _UNCLASSIFIED_NAMES, _claimed,
    _exclusions, _rules, _unclassified_names, load_tool)


# The one sanctioned divergence between the differential rules'
# character classes and _SCRIPT_RANGES: the halfwidth middle dot
# separates tokens without being classified (halfwidth kana stays out
# of the table on purpose). U+00B7 is deliberately NOT here -- its
# flank guard means every name it can change matches through a
# classified flanking character already. Single-sourced: read by the
# span sweep below, and by the membership guard that keeps "sanctioned"
# meaning something -- an extra that becomes classified belongs in the
# table, not in this list.
_SANCTIONED_EXTRAS = frozenset({(0xFF65, 0xFF65)})


def test_the_corpus_population_is_not_degenerate() -> None:
    """The floors themselves live in compare.py and are asserted by
    tests/v2/test_differential.py, which already checks every shipped
    corpus clears one and that every floor names a file that exists.
    Restating that here was a second, independently-drifting copy of a
    guarantee the harness owns.

    What is local to THIS module is the population the guards actually
    measure, which is not the same thing: _CORPUS_NAMES is
    deduplicated, so a corpus rewritten as 486 copies of one line
    clears its floor while the set collapses. And guard A is inert if
    nothing in that set is unclassified.
    """
    assert len(_CORPUS_NAMES) > 700, (
        f"_CORPUS_NAMES holds {len(_CORPUS_NAMES)} distinct names; the "
        f"corpora clear their floors in compare.py but deduplicate to far "
        f"fewer than usual, so every guard here is measuring a smaller "
        f"population than it appears to")
    assert _unclassified_names(), (
        "no corpus name lacks a classified codepoint, so the span rules' "
        "unclassified-reach check has nothing to test against")


def test_ledger_glob_is_not_empty() -> None:
    """A parametrize over an empty list generates a single silent SKIP
    rather than a failure -- the exact silence this module exists to
    break. The swept pins cannot assert this for themselves, since a
    test that is never generated cannot complain, so it lives here."""
    assert _LEDGERS, f"no expected_since_*.toml under {_TOOLS}"


def test_span_bearing_roster_names_exactly_the_ledgers_on_disk() -> None:
    """The roster's per-ledger sweep asserts every ledger has an entry,
    but it runs over _LEDGERS, so it can never visit an entry naming a
    file that is gone. A deleted or renamed ledger would leave its key
    behind indefinitely -- the same staleness the roster's tag-level
    check exists to prevent, one level up."""
    assert set(_SPAN_BEARING_RULES) == {ledger.name for ledger in _LEDGERS}, (
        f"_SPAN_BEARING_RULES names ledgers that do not exist: "
        f"{sorted(set(_SPAN_BEARING_RULES) - {L.name for L in _LEDGERS})}; "
        f"and is missing: "
        f"{sorted({L.name for L in _LEDGERS} - set(_SPAN_BEARING_RULES))}")


_SPAN = re.compile(r"\\u([0-9A-Fa-f]{4})-\\u([0-9A-Fa-f]{4})")


def _declared_spans(name_regex: str) -> set[tuple[int, int]]:
    """The \\uXXXX-\\uXXXX span pairs a rule's character class declares."""
    return {(int(lo, 16), int(hi, 16))
            for lo, hi in _SPAN.findall(name_regex)}


def _unrecognized_class_content(name_regex: str) -> list[str]:
    """Whatever a span-declaring character class holds BESIDES spans.

    _declared_spans reads one notation and is blind to every other, so
    set equality against the table only pins what is written as an
    escaped span. Anything appended in another notation -- a literal
    range, a bare character, a leading "^" negating the whole class --
    is invisible to it and rides along unchecked. That is not
    hypothetical: the ledgers' own convention mixes both spellings (see
    the interpunct note in expected_since_2.0.0.toml), and their
    non-span classes are written literally.

    The consequence is worst in the widening direction the equality is
    supposed to cover. Appending "a-z" to a pinned CJK class passes both
    that equality and compare.validate_rules' sentinel probe, and lets
    the rule claim every Latin diff in the corpus as intended -- exactly
    the regression-absorbing failure the harness exists to prevent.

    So: a class that declares any span must declare NOTHING else.
    Classes carrying no spans (the delimiter sets) are a different
    decision surface and are out of scope here -- as is widening spelled
    OUTSIDE the brackets, which _no_top_level_alternation covers.

    Two known false positives, both deliberate: a single non-range
    escape and a trailing literal "-" are legal regex and would be
    rejected. Write them as a one-codepoint span instead. A class
    metacharacter like \\s has no span spelling at all, so a rule
    genuinely needing one has to move it out of the span-bearing class.

    The bracket scan is a simple findall, not a regex parser: an escaped
    "\\]" inside a class truncates the body early and a nested "[" reads
    as content. Both surface as unrecognized content rather than as
    silence, which is the safe direction, and no ledger rule uses either.
    """
    return [rest
            for body in re.findall(r"\[([^\]]*)\]", name_regex)
            if _SPAN.search(body)
            for rest in [_SPAN.sub("", body)]
            if rest]


def _top_level_alternation(name_regex: str) -> bool:
    """Whether the rule has a "|" at nesting depth 0.

    The sibling of the hole above, three characters to the right of the
    "]". Appending "|[A-Za-z]" to a span-bearing rule widens it exactly
    as appending "a-z" inside the class would, and passes BOTH layers
    that are supposed to stop that: the span equality sees an unchanged
    class, and compare.validate_rules' sentinel probe clears it because
    "Хосе Сантос" fails to match, breaking the matches-everything
    conjunction. A CJK-scoped rule would then claim a Latin name's diff
    as intended.

    No ledger rule has one today, and a rule that genuinely needs an
    alternation can wrap it in "(?:...)", so requiring depth-0 purity
    costs nothing and closes the hatch.
    """
    depth = in_class = 0
    i = 0
    while i < len(name_regex):
        char = name_regex[i]
        if char == "\\":
            i += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = 1
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "|" and depth == 0:
            return True
        i += 1
    return False


#: Codepoints the script table classifies that a ledger rule may still
#: spell literally inside a character class. The nakaguro separators
#: sit in the katakana block by Unicode block assignment while
#: functioning as punctuation, which is exactly why the delimiter rules
#: write them as themselves alongside the corner brackets.
_LITERAL_IN_CLASS_OK = frozenset("・･")

_SPAN_TOKEN = re.compile(r"\\u[0-9A-Fa-f]{4}")


def _literally_spelled_script_chars(name_regex: str) -> list[str]:
    """Classified codepoints a class spells as themselves, not as spans.

    This is the escape hatch every masking attack on the roster below
    actually uses. Respell a rule's class in literal characters and the
    regex means the same thing while the rule vanishes from discovery --
    its hand copy is then unpinned, and _SPAN_BEARING_RULES cannot tell
    a rule that LEFT from a rule that was never there, because a set of
    names cannot see that two different rules answer to one name (the
    1.4 ledger already has two rules tagged feat(#269)).

    Naming rules could never fix that on its own. Closing the hatch can:
    a classified codepoint written literally in a class is refused, so a
    class covering script content has to stay in the notation discovery
    reads.
    """
    return sorted({char
                   for body in re.findall(r"\[([^\]]*)\]", name_regex)
                   for char in _SPAN_TOKEN.sub("", body)
                   if char not in _LITERAL_IN_CLASS_OK
                   and _policy._script_matcher(*_policy._SCRIPT_RANGES)(char)})


def _expected_bmp_spans() -> set[tuple[int, int]]:
    """What a full CJK character class in the toml must declare: the
    table's BMP spans plus the sanctioned extras.

    Han's astral block is the single table entry out of scope, on both
    sides: the ledger rules omit it deliberately because no corpus name
    reaches it -- see the comment on the canonical rule in
    expected_since_1.4.0.toml, which is the only place that reasoning is
    written down -- so the comparisons run over the BMP spans only
    rather than failing forever on a difference everyone agreed to.
    """
    return {span
            for spans in _policy._SCRIPT_RANGES.values()
            for span in spans
            if span[1] <= 0xFFFF} | set(_SANCTIONED_EXTRAS)


def test_script_ranges_membership_is_decided() -> None:
    """The two guards that belong to the script TABLE rather than to any
    one ledger's copy of it.

    Every table entry is in scope for the differential rules. The
    canonical rule covered HAN and HANGUL alone while the kana members
    existed only for classification, but #272 gave HIRAGANA a default
    order entry and made the kana blocks part of the same
    first/middle/last diff shape, so scoping by issue no longer draws a
    real line. Comparing against the whole table is the stronger
    promise: a script added to _SCRIPT_RANGES for ANY reason fails here
    until someone decides, in writing, whether the rules should cover
    it.

    The second assert is what makes _SANCTIONED_EXTRAS mean something.
    That set is the ledgers' licence to be WIDER than the table -- see
    its definition above for why U+FF65 is in it and U+00B7 is not --
    and a licence nobody audits is just a hole. An extra that becomes
    classified belongs in the table, not in the exception list, and
    fails here until it moves.

    There is deliberately no canonical-rule selector here any more. It
    picked rules by the literal '#271'/'#272' substrings and asserted
    uniqueness, which #332 broke: expected_since_2.0.0.toml has two such
    rules. Its equality check was in any case fully subsumed by
    test_every_span_bearing_rule_matches_the_script_ranges, since the
    canonical rule is itself span-bearing. Splitting the two guarantees
    is the point -- the sweep owns "every hand copy equals the table",
    this test owns "the table did not change shape without a decision"
    -- so a selector break can no longer take the decision gate out as
    collateral. Rule authors are correspondingly free to put #271 or
    #272 in a compound slug.
    """
    assert set(_policy._SCRIPT_RANGES) == {
        Script.HAN, Script.HANGUL, Script.HIRAGANA, Script.KATAKANA}, (
        "a Script joined _SCRIPT_RANGES: decide whether the differential "
        "rules in tools/differential/expected_since_*.toml should cover "
        "it, then update this assertion")
    for xlo, xhi in _SANCTIONED_EXTRAS:
        assert not any(lo <= xhi and xlo <= hi
                       for spans in _policy._SCRIPT_RANGES.values()
                       for lo, hi in spans), (
            f"U+{xlo:04X}-U+{xhi:04X} is classified now; drop it "
            "from _SANCTIONED_EXTRAS")


#: Which rules each ledger is known to carry a script-span copy in,
#: named by the leading fix(...)/feat(...) tag of their `issue`.
#:
#: Declared rather than counted. A count is identity-free, so one copy
#: could leave discovery -- rewritten as literal characters, say -- while
#: an unrelated span-bearing rule was added, and the total would hold
#: steady while a hand copy went unpinned (measured). Naming them also
#: buys the staleness direction the count never had, and that this
#: module's other two rosters already have: a tag here that matches no
#: rule fails, so a renamed or deleted rule cannot leave its entry
#: behind.
#:
#: Membership is the forcing function: a new baseline's ledger fails as
#: unrecorded until someone writes its rules down. An empty set is fine
#: and correct for a release that changed nothing CJK.
_SPAN_BEARING_RULES: dict[str, frozenset[str]] = {
    "expected_since_1.4.0.toml": frozenset({
        "fix(#271/#272/#298)",              # the canonical class
        "fix(cjk-delimited-nickname)",      # the four compounds, whose
        "fix(cjk-fullwidth-paren-nickname)",  # lookaheads each carry
        "fix(cjk-comma-compound)",          # their own copy
        "fix(cjk-comma-honorific-peel)",
    }),
    "expected_since_2.0.0.toml": frozenset({
        "fix(#271/#272/#298)",              # the canonical class
        "fix(#298)",                        # the 间隔号 lookahead
    }),
    "expected_since_2.1.0.toml": frozenset(),   # open cycle, no rules yet
}

#: The leading `fix(...)`/`feat(...)` tag of a rule's `issue`, which is
#: what _SPAN_BEARING_RULES names rules by. Unique within each ledger
#: among span-bearing rules (asserted below), and stable across the
#: prose that follows it.
_ISSUE_TAG = re.compile(r"^[a-z]+\([^)]*\)")


def _tag(issue: str) -> str:
    """The leading tag, required only of rules the roster has to name.

    Nothing obliges a ledger rule to carry a tag in general, and one in
    the 1.4 file does not ("ambiguous-surname-acronym data change:
    ..."). That is fine while it declares no script span. If such a rule
    ever gains one it lands here, and the fix is to give it a tag rather
    than to loosen the roster.
    """
    match = _ISSUE_TAG.match(issue)
    assert match, (
        f"a span-bearing rule's issue must open with a fix(...) or "
        f"feat(...) tag so _SPAN_BEARING_RULES can name it; this one "
        f"does not: {issue!r}")
    return match.group(0)


@pytest.mark.parametrize("ledger", _LEDGERS, ids=lambda p: p.name)
def test_every_span_bearing_rule_matches_the_script_ranges(
        ledger: Path) -> None:
    """Auto-discovered pin for every hand copy of the script spans in
    every ledger: any rule whose character class declares spans
    intersecting _SCRIPT_RANGES must declare the whole expected class
    (table BMP spans + sanctioned extras).

    A TOML file cannot import _policy._SCRIPT_RANGES, so these are the
    copies with no possible alternative -- and the ones whose divergence
    is quietest, because the harness is run by hand rather than in CI.

    Both failure directions matter, which is why this compares sets
    rather than checking coverage. A span MISSING from a class turns an
    intended change into an UNEXPLAINED diff (a release blocker for the
    wrong reason); a span that should not be there silently classifies a
    real regression as intended, which is the failure the whole harness
    exists to prevent.

    The compound rules' require-a-classified-codepoint lookaheads exist
    so their trigger sets alone (delimiters; a comma) cannot claim a
    Latin name's regression -- and each such lookahead is a copy nothing
    else checks. Discovery, not enrollment, is what subjects a rule to
    the equality above: a new compound rule's copy is checked because it
    exists, not because an author remembered it. _SPAN_BEARING_RULES
    then holds discovery itself to account, since a copy rewritten in a
    notation discovery cannot see would otherwise just vanish from the
    sweep. Rules whose spans touch OTHER scripts (Cyrillic, say) are out
    of scope and skipped by the intersection test.
    """
    assert ledger.name in _SPAN_BEARING_RULES, (
        f"{ledger.name} is a new ledger whose span-bearing rules are not "
        f"recorded; add it to _SPAN_BEARING_RULES (an empty set is a "
        f"legal answer for a release that changed nothing CJK)")
    table_spans = _expected_bmp_spans()
    tags = []
    for rule in _rules(ledger):
        regex = rule.get("name_regex")
        if not isinstance(regex, str):
            continue
        declared = _declared_spans(regex)
        if not declared & table_spans:
            continue
        tags.append(_tag(rule["issue"]))
        assert declared == table_spans, (
            f"{ledger.name}: {rule['issue']!r} declares "
            f"{sorted(declared)}; expected {sorted(table_spans)}")
        extra = _unrecognized_class_content(regex)
        assert not extra, (
            f"{ledger.name}: {rule['issue']!r} has a span-declaring "
            f"character class holding {extra!r} besides its spans. The "
            f"span equality above cannot see that, so it would widen the "
            f"rule unchecked -- write it as an escaped span or not at all")
        assert not _top_level_alternation(regex), (
            f"{ledger.name}: {rule['issue']!r} has a '|' at depth 0, so "
            f"the whole rule is an alternation and the pinned class "
            f"governs only one branch. Wrap it in '(?:...)'")
        # The property the syntactic check above is only a proxy for.
        # A rule scoped to classified scripts must not reach a name
        # written in none of them -- and unlike a depth test, this does
        # not care how the widening is spelled. "(?:CJK|[A-Za-z])"
        # hides the pipe at depth 1 where the check above stops
        # looking, and claims 644 of the 654 unclassified corpus names;
        # this sees
        # it. Both are kept: the depth test gives the clearer message
        # for the naive spelling, and catches a widening toward a
        # script the corpora happen not to contain.
        unclassified = _UNCLASSIFIED_NAMES.intersection(_claimed(regex))
        assert not unclassified, (
            f"{ledger.name}: {rule['issue']!r} declares the script table's "
            f"spans but claims {len(unclassified)} corpus names carrying "
            f"no classified codepoint at all, e.g. {sorted(unclassified)[:3]}. A rule scoped "
            f"to these scripts cannot explain a diff on those names, so it "
            f"would absorb one instead")
    # Every rule, not just the discovered ones: this is what stops a
    # class being respelled out of discovery in the first place, and it
    # has to reach the rules that are NOT currently span-bearing to do
    # that job.
    for rule in _rules(ledger):
        regex = rule.get("name_regex")
        if not isinstance(regex, str):
            continue
        literal = _literally_spelled_script_chars(regex)
        assert not literal, (
            f"{ledger.name}: {rule['issue']!r} spells the classified "
            f"codepoints {literal} literally inside a character class. "
            f"Write them as \\uXXXX-\\uXXXX spans, or the rule drops out "
            f"of the sweep above while meaning the same thing")
    # two rules sharing a tag would collapse into one set member and
    # read as a disappearance below, which is a confusing way to learn
    # that the naming scheme broke
    assert len(tags) == len(set(tags)), (
        f"{ledger.name}: two span-bearing rules share an issue tag "
        f"({sorted(tags)}); _SPAN_BEARING_RULES cannot name them apart")
    found = set(tags)
    assert found == _SPAN_BEARING_RULES[ledger.name], (
        f"{ledger.name}'s span-bearing rules are not the recorded set. "
        f"Left discovery (a hand copy is now unpinned): "
        f"{sorted(_SPAN_BEARING_RULES[ledger.name] - found)}. "
        f"Newly discovered (pinned now, but record it): "
        f"{sorted(found - _SPAN_BEARING_RULES[ledger.name])}")


#: The delimiter compound's trigger set is its own decision surface,
#: separate from the script spans: these are the characters whose mere
#: presence lets the rule claim a diff. Written once here rather than
#: inline: the check this replaces tested the regex against this set
#: spelled as unicode escapes OR against it spelled as the characters
#: themselves, which in a non-raw literal are the same str -- an `or`
#: whose two operands could never disagree. One spelling, named once.
_NICKNAME_DELIMITERS = "[「」『』・･]"


def test_nickname_delimiter_sets_are_deliberate() -> None:
    """Swept rather than pinned to one file and one rule. The 1.4 ledger
    has exactly one cjk-delimited-nickname rule and the 2.0 ledger has
    none, so a per-file `== 1` is already false and a global one holds
    only by accident of there being a single rule today. What is
    actually invariant is that EVERY such rule carries the sanctioned
    trigger set, and that at least one exists somewhere or this is
    checking nothing.

    Note the scope this does NOT have: it is a decision surface, not a
    sync pin. _NICKNAME_DELIMITERS is a literal because the rule's class
    is not Policy.nickname_delimiters and is not meant to be -- it is
    the two CJK corner-bracket pairs, plus the nakaguro separators,
    which delimit nothing, and minus the nine other pairs the config
    ships. Deriving it would mean deciding all of that in code rather
    than writing it down.

    So a delimiter pair removed from the config does not fail here; it
    fails tests/v2/test_cases.py, on the cjk_white_corner_bracket_
    nickname row (measured -- tests/v2/pipeline/ stays green, which is
    why the pointer is worth being exact about)."""
    found = []
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            if "cjk-delimited-nickname" not in rule["issue"]:
                continue
            found.append(f"{ledger.name}: {rule['issue']}")
            # .get rather than [] on purpose: a rule that dropped its
            # name_regex outright should land on the assertion below,
            # not raise KeyError out of the sweep
            assert _NICKNAME_DELIMITERS in rule.get("name_regex", ""), (
                f"{ledger.name}: the compound rule's delimiter set "
                f"changed, or the rule lost its name_regex; decide "
                f"deliberately, then update _NICKNAME_DELIMITERS")
    assert found, (
        "no cjk-delimited-nickname rule in any ledger; this check is "
        "passing vacuously")


def test_cjk_corpus_matches_the_case_table() -> None:
    """corpus_cjk.jsonl is GENERATED, not curated (#295): every
    distinct case-table text bearing a codepoint the script table
    classifies, sorted -- see build_cjk_corpus.py for why the other
    two corpora cannot carry these names. The checked-in file must
    equal what the generator would write, so a CJK case row added
    without regenerating fails HERE instead of silently narrowing
    the differential gate back toward the blind spot #295 closed.
    Same promise as the toml pin above, aimed at a generated artifact
    instead of a hand copy.
    """
    module = load_tool("build_cjk_corpus")
    checked_in = [json.loads(line) for line in
                  (_TOOLS / "corpus_cjk.jsonl")
                  .read_text(encoding="utf-8").splitlines()]
    assert checked_in == module.selected_names(), (
        "corpus_cjk.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_cjk_corpus.py`")


def test_rules_corpus_matches_the_rules_doc() -> None:
    """corpus_rules.jsonl is GENERATED from docs/design/rules.md's own
    examples (#414), through the doc's parser rather than a second
    regex. Same promise as the CJK pin above: an example added to a
    rule without regenerating fails HERE, instead of leaving the
    normative names outside the differential gate.

    Why the doc's examples need the gate at all, when test_rules_doc
    already executes every one of them: those pin against an
    expectation stored beside them, so a deliberate behaviour change
    edits both in one commit and the test stays green. The corpus
    compares against a RELEASED baseline no commit can edit, which is
    what forces a moved name to be classified in writing.
    """
    module = load_tool("build_rules_corpus")
    checked_in = [json.loads(line) for line in
                  (_TOOLS / "corpus_rules.jsonl")
                  .read_text(encoding="utf-8").splitlines()]
    assert checked_in == module.selected_names(), (
        "corpus_rules.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_rules_corpus.py`")


#: Which vocabulary constant each ledger rule's alternation is a hand
#: copy of. A roster rather than an inference: GLUED_HONORIFICS is a
#: SUBSET of SUFFIX_WORDS (asserted at the bottom of
#: nameparser/config/suffixes.py), so "equals one of the two known sets"
#: would let a spaced rule that silently narrowed to exactly the glued
#: set pass by matching the other member -- a subset check wearing a
#: disguise, and the subset direction is precisely the one that removal
#: drift travels in.
#:
#: Keys are matched as substrings of a rule's `issue` and must select
#: exactly one entry. The full issue lists are the keys, not a bare
#: '#308': both 2.0 rules cite #308 while copying different constants.
_HONORIFIC_SOURCES: dict[str, frozenset[str]] = {
    "cjk-honorific-suffix": SUFFIX_WORDS,               # 1.4, spaced
    "cjk-glued-honorific-peel": GLUED_HONORIFICS,       # 1.4, glued (#372)
    "#307/#308/#320": SUFFIX_WORDS,                     # 2.0, spaced
    "#308/#312/#319/#320": GLUED_HONORIFICS,            # 2.0, glued
}

#: An alternation group with two or more members and no nested
#: parentheses, capturing or not. Together with the classified-member
#: filter in _cjk_alternations it selects exactly the three honorific
#: alternations across both ledgers; on its own it also matches
#: "(?:^| )" from the 1.4 rule and the two Latin maiden/acronym
#: alternations, all of which the filter drops.
#:
#: The "(?:" alternative is spelled out and the plain "(" is guarded by
#: (?!\?) so that lookarounds -- "(?=$|[ ,])", "(?<=[^\s,])" -- do not
#: parse as alternations of their own syntax. Matching plain capturing
#: groups matters: a rule written "(씨|님|先生)" instead of
#: "(?:씨|님|先生)" would otherwise carry a hand copy this pin cannot
#: see, which is the silent-unpinning this module exists to prevent.
#:
#: Shapes it still cannot read correctly. All of them fail, but by two
#: different mechanisms, and the message you get depends on which
#: (every row measured):
#:
#:   STALE half of the roster check -- the group stops matching, so the
#:   rule's key goes unused:
#:     a nested group whose inner members are UNclassified;
#:     a paren inside a character class;
#:     a single-member "group", which is not an alternation at all;
#:     the named and inline-flag forms "(?P<n>a|b)" and "(?i:a|b)".
#:
#:   Declared-vs-expected equality -- the group still matches, but its
#:   members are MISread, since the split is a plain str.split("|"):
#:     "|" inside a character class: "[a|b]" yields "[a" and "b]";
#:     a nested group whose inner members ARE classified: the inner
#:     group is extracted and shows up as a member of the outer one.
_ALTERNATION = re.compile(r"\((?:\?:|(?!\?))((?:[^()|]+\|)+[^()|]+)\)")


def _alternations(name_regex: str) -> list[set[str]]:
    """Every alternation group's members."""
    return [set(body.split("|")) for body in _ALTERNATION.findall(name_regex)]


def _cjk_alternations(name_regex: str) -> list[set[str]]:
    """Every alternation in a rule with a script-classified member."""
    has_classified = _policy._script_matcher(*_policy._SCRIPT_RANGES)
    return [members for members in _alternations(name_regex)
            if any(has_classified(m) for m in members)]


def test_differential_honorific_rules_match_their_vocabulary() -> None:
    """The honorific rules' alternations are hand copies of the CJK
    entries of SUFFIX_WORDS (#307) and of GLUED_HONORIFICS (#308) --
    a toml cannot import them. Each expected set is DERIVED from the
    config by script membership (a classified codepoint anywhere in the
    entry), so adding a CJK honorific without widening the rule, or
    widening a rule with something the vocabulary does not ship, fails
    here.

    Swept over every ledger and every alternation, because the three
    copies are anchored three different ways -- a leading '(?:^| )' in
    1.4, a character class and a lookbehind in 2.0 -- so the old
    startswith/endswith parser could not read two of them. Discovery
    plus a declared source is what replaces it.

    The span-bearing pins skip these rules on purpose: their trigger is
    the alternation, not a character class. Note GLUED_HONORIFICS had no
    pinned copy anywhere in the tree before this.

    Two completeness directions, both required. An alternation matching
    no roster key fails as UNDECLARED, so a new rule's copy is pinned by
    existing rather than by an author remembering to enroll it. A roster
    key matching no rule fails as STALE, catching an entry left behind
    after a rule was renamed or deleted.
    """
    has_classified = _policy._script_matcher(*_policy._SCRIPT_RANGES)
    used: set[str] = set()
    found = 0
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            regex = rule.get("name_regex")
            if not isinstance(regex, str):
                continue
            for declared in _cjk_alternations(regex):
                keys = [k for k in _HONORIFIC_SOURCES if k in rule["issue"]]
                assert len(keys) == 1, (
                    f"{ledger.name}: rule {rule['issue']!r} carries a CJK "
                    f"alternation matching {len(keys)} roster keys "
                    f"({keys}); every such hand copy must name exactly "
                    f"one source in _HONORIFIC_SOURCES")
                used.add(keys[0])
                found += 1
                expected = {entry for entry in _HONORIFIC_SOURCES[keys[0]]
                            if has_classified(entry)}
                assert declared == expected, (
                    f"{ledger.name}: {rule['issue']!r} declares "
                    f"{sorted(declared)}; the config's CJK entries for "
                    f"{keys[0]!r} are {sorted(expected)}")
    assert found, (
        "no CJK honorific alternation found in any ledger; this pin is "
        "passing vacuously")
    assert used == set(_HONORIFIC_SOURCES), (
        f"_HONORIFIC_SOURCES keys matching no rule: "
        f"{sorted(set(_HONORIFIC_SOURCES) - used)}. Either a renamed or "
        f"deleted rule left its entry behind -- drop it -- or that "
        f"rule's alternation stopped matching _ALTERNATION (a nested "
        f"group, a paren inside a character class, or a lone member), "
        f"which is how a still-present hand copy silently leaves this "
        f"pin.")


class _LatinCopy(NamedTuple):
    """A ledger alternation that hand-copies a Latin-script vocabulary.

    Two set-shaped fields that are emphatically not the same kind of
    thing, which is why they are named rather than positional:
    `vocabulary` is the source of truth, `covers` an audited snapshot of
    which of its entries the rule's members reach.
    """
    vocabulary: frozenset[str]
    covers: frozenset[str]


#: Ledger rules whose alternation hand-copies a LATIN vocabulary, keyed
#: by a substring of the rule's `issue`. Kept apart from
#: _HONORIFIC_SOURCES because the relationship is not set equality:
#: these members are regex FRAGMENTS, not entries -- "n[ée]e" covers two
#: markers at once, "geb\.?" and "roz\.?" one each -- so there is no set
#: to compare against.
#:
#: `covers` is recorded rather than equated to the whole vocabulary.
#: Equality would force a rule to grow alternatives for markers it has
#: no reason to claim -- see the note on fix(#274) in the 1.4 ledger for
#: why 旧姓 in particular is not one of them. Recording still catches
#: removal: drop an entry a member covers and the snapshot shrinks.
#:
#: Three nearby counts differ and are easy to conflate, all for
#: fix(#274) specifically: MAIDEN_MARKERS ships 17 entries; that rule's
#: members reach 4 of them; the corpora contain 3 markers in total
#: (geb, née, 旧姓), only 2 of which it covers.
_LATIN_ALTERNATION_SOURCES: dict[str, _LatinCopy] = {
    "fix(#274)": _LatinCopy(
        vocabulary=MAIDEN_MARKERS,
        covers=frozenset({"geb", "nee", "née", "roz"})),
    "ambiguous-surname-acronym": _LatinCopy(
        vocabulary=SUFFIX_ACRONYMS_AMBIGUOUS,
        covers=frozenset({"do", "ma"})),
    # The tussenvoegsel rule copies PARTICLES, and copies it PARTLY on
    # purpose: it needs the words that actually end a Dutch, Iberian or
    # German listing, not all 70. A wider copy would claim comma names
    # whose trailing word is a particle nobody files a name with, which
    # is the reach this roster exists to keep honest.
    "fix(#379)": _LatinCopy(
        vocabulary=PARTICLES,
        covers=frozenset({"de", "del", "den", "der", "di", "do", "dos",
                          "du", "la", "le", "los", "mc", "van", "vd",
                          "von", "zu"})),
    # The same partial copy as fix(#379), and partial for the same
    # reason -- these are the words that actually open a chain in a
    # Latin name. The two rules ask different questions of it (#379
    # wants the word that ENDS a comma listing, #399 the word that
    # opens a chain running into a maiden marker), so the shared
    # snapshot is agreement rather than duplication: a divergence
    # would be a fact about one of the rules.
    "fix(#399)": _LatinCopy(
        vocabulary=PARTICLES,
        covers=frozenset({"de", "del", "den", "der", "di", "do", "dos",
                          "du", "la", "le", "los", "mc", "van", "vd",
                          "von", "zu"})),
}

#: Alternations that copy no vocabulary, so discovery must not demand a
#: source for them. Declared rather than inferred, on the principle
#: test_regex_sync.py's _SOURCES sets with its None entries: an undeclared alternation is a
#: question someone answers in writing, not something to skip past.
_NOT_A_VOCABULARY_COPY = frozenset({
    frozenset({"^", " "}),      # the honorific rule's leading anchor
    # fix(#400)'s two openings: start-of-name or just after a family
    # comma. `abd` joins forward on the given side wherever that side
    # begins, and the alternation is over ANCHORS, not over words --
    # there is no vocabulary here to drift from.
    frozenset({"^", ",\\s*"}),
})

def _unjustified_reach(name_regex: str, members: set[str]) -> list[str]:
    """Corpus names the whole rule claims that none of its own members
    reach.

    The member checks bound what each ALTERNATIVE matches. This bounds
    the rule built around them, which is a different question and the
    one four rounds of syntactic guards kept failing to ask. Nesting a
    rule's own alternation one level down and adding a branch --
    "(?:[(\"'](m\\.?a\\.?|d\\.?o\\.?)[)\"']|[A-Za-z]{4,})" -- leaves every
    member innocent, hides the pipe below the depth test, and hides the
    outer group from _ALTERNATION, which refuses nested parens. It
    claimed 622 of the corpus while every check passed.

    Keyed on the roster rather than on `fields`, which is what makes it
    reach that rule: the acronym copy claims `suffix`/`nickname`, so
    the field-keyed guard below never looks at it.

    A rule claiming nothing scores zero, which is the strongest answer
    rather than a vacuous one -- so the non-vacuity assertion is over
    the union of all rostered rules, not per rule.
    """
    reachable = [re.compile(member, re.IGNORECASE) for member in members]
    return [name for name in _claimed(name_regex)
            if not any(pattern.search(name) for pattern in reachable)]


def _reaches_non_vocabulary(member: str, vocabulary: frozenset[str]) -> list[str]:
    """Corpus text this member matches that is NOT a vocabulary entry.

    fullmatch against the vocabulary bounds what a member matches
    WITHIN those entries and says nothing about what it matches in a
    NAME. That gap was first filled with a tuple of eight hand-picked
    probe strings, and the tuple was defeated by a wider rule than the
    one it was added to stop: every entry this rule needs is three
    characters, so a member must accept some 3-character string and is
    unconstrained everywhere else -- "[acdf-uw-z]{3,}" covers `roz`,
    dodges all eight probes, and reaches 634 of the 751 corpus names
    as a fourth alternative (the rule carrying it claims 542).
    Measured with the IGNORECASE this function applies; the
    case-sensitive figure, 592, is not what runs. Counts here and below are
    against _CORPUS_NAMES, which deduplicates the 783 corpus lines.

    Eight strings could never be more than a spot check. The corpus is
    the whole population the rule will ever be asked about, so ask it
    instead: every fragment a member matches must BE an entry.

    Searched unanchored, which is stricter than the rule's own \\b
    anchoring and so cannot produce a false negative from it.
    Normalized before comparison because the corpus writes "geb." where
    the config stores "geb" -- without that, the shipped member fails.
    Exempting only THIS vocabulary, not the union of all of them, keeps
    a maiden member from being excused by an acronym entry.
    """
    matches = set()
    for name in _CORPUS_NAMES:
        for found in re.finditer(member, name, re.IGNORECASE):
            if found.group() and _normalize(found.group()) not in vocabulary:
                matches.add(found.group())
    return sorted(matches)


def test_latin_alternations_mean_something_the_vocabulary_ships() -> None:
    """The Latin twin of the honorific pin, shaped by what a regex
    alternation over a vocabulary can honestly promise.

    Discovery-first, like its twin: every alternation in every ledger
    must be a declared vocabulary copy or a declared non-copy. Keying
    off the roster and skipping everything else would mean a future rule
    that hand-copies a vocabulary under a new tag is pinned only if its
    author remembers to enroll it -- the failure this module exists to
    prevent, not a shape it should adopt.

    Members are matched against entries as regexes rather than compared
    as strings, because the members ARE regex syntax: "geb\\.?" stands
    for the entry "geb", which the config stores normalized (lowercase,
    no trailing period).

    Two ways a MEMBER can be wrong, checked per member: it can match
    nothing in the vocabulary -- then it cannot describe a real change
    and can only claim other names' diffs, which is how "born" survived
    from the harness's first commit to #350 -- or it can reach corpus
    text that is not vocabulary. A third assertion is about the RULE
    around them, which can widen at depth 0 and leave the pinned
    alternation governing one branch of an unchecked whole. An invalid
    member raises rather than asserts, since nothing else can proceed.
    """
    has_classified = _policy._script_matcher(*_policy._SCRIPT_RANGES)
    used: set[str] = set()
    found = 0
    reach_checked = 0
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            regex = rule.get("name_regex")
            if not isinstance(regex, str):
                continue
            for members in _alternations(regex):
                if any(has_classified(m) for m in members):
                    continue        # the honorific pin owns these
                if frozenset(members) in _NOT_A_VOCABULARY_COPY:
                    continue
                found += 1
                keys = [k for k in _LATIN_ALTERNATION_SOURCES
                        if k in rule["issue"]]
                assert len(keys) == 1, (
                    f"{ledger.name}: {rule['issue']!r} carries the Latin "
                    f"alternation {sorted(members)}, which matches "
                    f"{len(keys)} roster keys ({keys}). Declare the "
                    f"vocabulary it copies in _LATIN_ALTERNATION_SOURCES, "
                    f"or add it to _NOT_A_VOCABULARY_COPY if it copies "
                    f"nothing")
                used.add(keys[0])
                source = _LATIN_ALTERNATION_SOURCES[keys[0]]
                unjustified = _unjustified_reach(regex, members)
                assert not unjustified, (
                    f"{ledger.name}: {rule['issue']!r} claims "
                    f"{len(unjustified)} corpus names that none of its own "
                    f"vocabulary members reach, e.g. {unjustified[:3]}. The "
                    f"members are innocent and the rule around them is not "
                    f"-- whatever it matches beyond them, it claims")
                reach_checked += len(_claimed(regex))
                assert not _top_level_alternation(regex), (
                    f"{ledger.name}: {rule['issue']!r} has a '|' at depth "
                    f"0, so the pinned alternation governs only one branch "
                    f"and the rest of the rule is unchecked. Wrap it in "
                    f"'(?:...)'")
                covered = set()
                for member in members:
                    try:
                        pattern = re.compile(member, re.IGNORECASE)
                    except re.error as exc:
                        raise AssertionError(
                            f"{ledger.name}: {rule['issue']!r} member "
                            f"{member!r} is not a valid regex ({exc}). A "
                            f"mis-split alternation can produce this -- see "
                            f"_ALTERNATION's notes") from None
                    matched = {entry for entry in source.vocabulary
                               if pattern.fullmatch(entry)}
                    loose = _reaches_non_vocabulary(member, source.vocabulary)
                    assert not loose, (
                        f"{ledger.name}: {rule['issue']!r} member "
                        f"{member!r} matches corpus text that is not "
                        f"vocabulary: {loose[:6]}. Spell it literally -- a "
                        f"member broad enough to reach a real name lets the "
                        f"rule claim that name's diff as intended")
                    assert matched, (
                        f"{ledger.name}: {rule['issue']!r} offers the "
                        f"alternative {member!r}, which matches no entry in "
                        f"the vocabulary it copies. It cannot correspond to "
                        f"a real change, so it can only claim other names' "
                        f"diffs as intended -- drop it, or ship it as "
                        f"vocabulary first")
                    covered |= matched
                assert covered == source.covers, (
                    f"{ledger.name}: {rule['issue']!r} covers "
                    f"{sorted(covered)}; recorded {sorted(source.covers)}. "
                    f"Lost: {sorted(source.covers - covered)} (an entry the "
                    f"rule relied on left the vocabulary). Gained: "
                    f"{sorted(covered - source.covers)} (record it)")
    assert found, (
        "no Latin vocabulary alternation found in any ledger; this pin is "
        "passing vacuously")
    assert reach_checked, (
        "no rostered rule claims any corpus name, so the reach check above "
        "measured nothing -- verify the corpora loaded")
    assert used == set(_LATIN_ALTERNATION_SOURCES), (
        f"_LATIN_ALTERNATION_SOURCES keys matching no rule: "
        f"{sorted(set(_LATIN_ALTERNATION_SOURCES) - used)}")


#: A role a rule can claim, mapped to the vocabulary a name must carry
#: for that claim to be possible. Keyed on `fields` rather than on the
#: regex, which is the point: the two pins above discover hand copies
#: by their SYNTAX, so a copy that is not written as an alternation or
#: a character class is not undeclared, it is unseen. A brand-new rule
#: whose name_regex is "(?i)\b[a-z]{3}\b" with maiden fields passed
#: every check in this module while claiming 308 corpus names.
#:
#: `fields` cannot be dodged the same way. A rule that does not claim
#: `maiden` cannot be labelled a maiden change at all, so keying here
#: reaches every spelling -- including fix(cjk-maiden-marker), whose
#: regex is the bare literal "旧姓" and which no roster in this module
#: could see.
#:
#: Only `maiden` today, because only its vocabulary is small and
#: mandatory enough for the implication to hold: a maiden diff needs a
#: marker in the name. `suffix` and `title` are not like that -- most
#: of their diffs come from routing, not from a vocabulary word being
#: present -- so adding them would be false rather than strict.
_FIELD_VOCABULARIES: dict[str, frozenset[str]] = {
    "maiden": MAIDEN_MARKERS,
}


def _carries(name: str, vocabulary: frozenset[str]) -> bool:
    """Whether a name contains a vocabulary entry.

    Whole-token for ASCII entries, substring for the rest, because a
    marker like 旧姓 is written against the name it marks rather than
    spaced off it.

    Note what the isascii() split actually covers: 12 of the 17
    entries, not only the CJK one. `né` is two characters, so the
    substring branch reads `René` as carrying a marker. Every
    over-match here SHRINKS the set of unexplained names and so
    weakens the guard -- the direction this module exists to close --
    but exactly one corpus name reaches that branch today, and it is
    the 旧姓 one. Tighten this before admitting a vocabulary whose
    short non-ASCII entries occur inside ordinary names.
    """
    tokens = {_normalize(token) for token in name.split()}
    return bool(tokens & vocabulary) or any(
        entry in name for entry in vocabulary if not entry.isascii())


def test_rules_claiming_a_vocabulary_role_need_the_vocabulary_present() -> None:
    """The guard that does not care how a rule is spelled.

    Every pin above starts from regex syntax -- an alternation, a
    character class, a span. Each closed the hole it was built for and
    left the next spelling open, four rounds running. This one starts
    from what the rule CLAIMS: if a rule says a diff is a maiden-marker
    change, then every corpus name it claims must actually carry a
    maiden marker. A rule cannot escape that by changing notation,
    because it is not reading the notation.

    Deliberately narrow. It does not say the rule is correct, only that
    it cannot be explaining a marker on a name that has none. That
    covers the maiden widenings review found; the ones claiming
    `nickname` and `suffix` fall outside it, and _CORPUS_CLAIMS is
    what catches those.
    """
    checked = 0
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            regex = rule.get("name_regex")
            if not isinstance(regex, str):
                continue
            for field, vocabulary in _FIELD_VOCABULARIES.items():
                if field not in (rule.get("fields") or []):
                    continue
                checked += 1
                bare = [name for name in _claimed(regex)
                        if not _carries(name, vocabulary)]
                assert not bare, (
                    f"{ledger.name}: {rule['issue']!r} claims {field!r} "
                    f"diffs on {len(bare)} corpus names carrying no {field} "
                    f"vocabulary, e.g. {bare[:3]}. It cannot be explaining a "
                    f"marker that is not there, so on those names it would "
                    f"absorb a regression instead")
    assert checked, (
        "no rule claims a role in _FIELD_VOCABULARIES; this pin is passing "
        "vacuously")


class _Claim(NamedTuple):
    """What a rule claims, in the three dimensions classify() uses.

    A count alone is identity-free -- the weakness this module rejects
    at _SPAN_BEARING_RULES -- and review proved it here twice. Swapping
    feat(#273)'s delimiter class for a single accented letter holds the
    count at 6 while claiming six entirely different names. And
    classify() narrows on `fields` as well as `name_regex`, so widening
    a rule's roles moves nothing a regex-only count can see: the
    comma rule kept its `,` regex and its 236 names while going from
    explaining 6 of the corpus to 242.
    """
    #: corpus names the name_regex reaches; the whole corpus when a
    #: rule has none, which is the most unbounded shape validate_rules
    #: permits and the one most worth writing down
    names: int
    #: the roles it narrows by, sorted; () when it narrows by regex alone
    roles: tuple[str, ...]
    #: sha256[:12] of the claimed names, so a swap that holds the count
    #: still fails. Unreadable by design -- the count above is what a
    #: reviewer reads, and the failure message prints what moved.
    digest: str


def _claim(rule: dict) -> _Claim:
    regex = rule.get("name_regex")
    names = (_claimed(regex) if isinstance(regex, str) else list(_CORPUS_NAMES))
    fields = rule.get("fields")
    return _Claim(
        names=len(names),
        roles=tuple(sorted(fields)) if isinstance(fields, list) else (),
        digest=hashlib.sha256(
            "\n".join(names).encode("utf-8")).hexdigest()[:12])


#: How many corpus names each rule's name_regex matches, per ledger.
#:
#: The backstop the other guards each failed to be. Every one of them
#: is scoped to a CATEGORY -- a span class, an alternation's members, a
#: `maiden` field, a member's reach -- and five review rounds each found
#: a rule outside whichever category the last fix had covered. The
#: categories are the test's, not the ledger's. What every rule shares
#: is what it claims: how much corpus its regex reaches, which roles
#: it narrows by, and WHICH names those are. Scoped to the corpus --
#: and only there -- a widening cannot change what a rule explains
#: without moving one of the three. Restoring 'born' moves none of
#: them, because no corpus name contains it; the member guards catch
#: that, which is why this does not replace them.
#:
#: So this is deliberately dumb: it knows nothing about vocabularies,
#: scripts or roles, and it cannot say whether a number is RIGHT. It
#: says only that it moved, which is the question a widening cannot
#: dodge. The specific guards above stay because they explain WHY a
#: rule may claim what it claims, and their messages are the ones worth
#: reading; this one just refuses to let the number change quietly.
#:
#: Keyed by the full `issue` rather than by tag: the 1.4 ledger has two
#: rules tagged feat(#269), and a tag-keyed roster cannot tell them
#: apart -- the same identity-free weakness recorded at
#: _SPAN_BEARING_RULES.
#:
#: These numbers move when the CORPORA move, not only when a rule does.
#: That is the intended cost: a corpus name added under an existing
#: rule is a real change in what that rule explains, and it should be
#: read once rather than absorbed silently.
_CORPUS_CLAIMS: dict[str, dict[str, _Claim]] = {
    "expected_since_1.4.0.toml": {
        "fix(#271/#272/#298) native-script CJK: family-first order, hangul segmentation, the kana license and the dots":
            _Claim(105, ('family', 'given', 'middle'), "090ac3eef3fb"),
        "fix(#274) maiden markers consumed":
            _Claim(16, ('family', 'maiden', 'middle'), "cc672349b500"),
        "fix(cjk-maiden-marker) maiden marker consumed, compounding with the CJK order flip":
            _Claim(4, ('family', 'given', 'maiden', 'middle'), "27bb9ebc1951"),
        "fix(#379) a tussenvoegsel after a family comma attaches to the family":
            _Claim(8, ('family', 'middle'), "f4d52b062f39"),
        "fix(comma-family) lone post-comma piece routes to suffix/title, not first":
            _Claim(236, ('given', 'suffix', 'title'), "9393109ebf99"),
        "fix(comma-precomma-family) pre-comma run reads as family, not given":
            _Claim(236, ('family', 'given'), "9393109ebf99"),
        "fix(suffix-routing) two-token name with unambiguous trailing suffix stays suffix":
            _Claim(864, ('family', 'given', 'suffix'), "7127402a5078"),
        "fix(suffix-delimiter-rendering) no-space delimiter core token kept whole":
            _Claim(0, ('suffix',), "e3b0c44298fc"),
        "ambiguous-surname-acronym data change: parenthesized (MA)/(DO) now stays nickname":
            _Claim(0, ('nickname', 'suffix'), "e3b0c44298fc"),
        "feat(#269) Arabic بن prefix chains onto family (non-Latin new-recognition)":
            _Claim(2, ('family', 'middle'), "3e2b5c6d1f4d"),
        "feat(#273) typographic nickname delimiters recognized by default":
            _Claim(8, ('middle', 'nickname'), "968bd4162257"),
        "fix(cjk-delimited-nickname) delimiter recognition compounds with the CJK order flip":
            _Claim(6, ('family', 'given', 'nickname'), "ae1dffa01608"),
        "fix(cjk-fullwidth-paren-nickname) fullwidth-parenthesis recognition compounds with the CJK order flip":
            _Claim(1, ('family', 'given', 'middle', 'nickname'), "cf370e856ae7"),
        "fix(cjk-comma-honorific-peel) glued honorific peels off a post-comma given name":
            _Claim(21, ('given', 'suffix'), "fdc02562bd15"),
        "fix(cjk-comma-compound) comma routing compounds with the CJK order flip":
            _Claim(21, ('family', 'given', 'middle', 'suffix', 'title'), "fdc02562bd15"),
        "fix(cjk-glued-honorific-peel) glued honorific peels into suffix":
            _Claim(35, ('family', 'given', 'suffix'), "4da08a0090fe"),
        "fix(cjk-honorific-suffix) postnominal honorifics recognized, compounding with the CJK order flip":
            _Claim(19, ('family', 'given', 'middle', 'suffix'), "aa475ddd4745"),
        "feat(#269) non-Latin titles/conjunctions recognized":
            _Claim(4, ('given', 'middle', 'title'), "e86eeb13eeb2"),
        "fix(leading-credential) a split 'Ph. D.' before the name stays one unit":
            _Claim(1, ('given', 'middle', 'suffix', 'title'), "390e7f814d13"),
        "fix(#367) a title no longer displaces a leading particle out of the leading position":
            _Claim(1, ('family', 'given', 'middle'), "dce0ae6df4be"),
        "fix(#400) abd joins the word after it as one given name":
            _Claim(3, ('given', 'middle'), "6eb6b807523a"),
        "fix(#272/#308) nakaguro division and a glued hangul honorific in one name":
            _Claim(1, ('family', 'given', 'middle', 'suffix'), "2fbf1a94f122"),
        "fix(nickname-typographic-pairs) two typographic quote spans read as one nickname set":
            _Claim(1, ('family', 'given', 'middle', 'nickname'), "3cf566c78800"),
    },
    "expected_since_2.0.0.toml": {
        "fix(#379) a tussenvoegsel after a family comma attaches to the family":
            _Claim(8, ('family', 'middle'), "f4d52b062f39"),
        "fix(#271/#272/#298) native-script CJK: family-first order, hangul segmentation, the kana license and the dots":
            _Claim(105, ('_ambiguities', 'family', 'given', 'middle'), "090ac3eef3fb"),
        "fix(#308/#312/#319/#320) glued CJK honorific peeled off the name into suffix":
            _Claim(35, ('family', 'given', 'suffix'), "4da08a0090fe"),
        "fix(#307/#308/#320) spaced CJK postnominal honorific routed to suffix":
            _Claim(16, ('family', 'given', 'middle', 'suffix'), "6d390e518bd2"),
        "fix(#309) 旧姓 maiden marker consumed, compounding with the CJK order flip":
            _Claim(4, ('family', 'given', 'maiden', 'middle'), "27bb9ebc1951"),
        "fix(#272) nakaguro inside delimited content renders as a space, compounding with the CJK order flip":
            _Claim(1, ('family', 'given', 'nickname'), "d4069d459f23"),
        "fix(#298) 间隔号 division changes the comma reading, sending the credential from title to suffix":
            _Claim(1, ('family', 'given', 'suffix', 'title'), "1d45596e6fdb"),
        "fix(#367) a title no longer displaces a leading particle out of the leading position":
            _Claim(1, ('family', 'given', 'middle'), "dce0ae6df4be"),
        "fix(#380) a trailing vd after a family comma is the tussenvoegsel, not a post-nominal":
            _Claim(1, ('family', 'suffix'), "081ce07f927b"),
        "fix(#399) a maiden marker bounds the particle chain that swallowed it":
            _Claim(6, ('family', 'maiden'), "b40129435671"),
        "fix(#360) mc moved into the never-given particles, so it folds into the family":
            _Claim(1, ('_ambiguities', 'family', 'given'), "ee4339908f4d"),
        "fix(#400) abd joins the word after it as one given name":
            _Claim(3, ('given', 'middle'), "6eb6b807523a"),
        "fix(#367) a title no longer displaces a leading never-given particle":
            _Claim(1, ('family', 'given'), "db724fb9c779"),
        "fix(#272/#308) nakaguro division and a glued hangul honorific in one name":
            _Claim(1, ('family', 'given', 'middle', 'suffix'), "2fbf1a94f122"),
    },
    "expected_since_2.1.0.toml": {
        "fix(#379) a tussenvoegsel after a family comma attaches to the family":
            _Claim(8, ('family', 'middle'), "f4d52b062f39"),
        "fix(#367) a title no longer displaces a leading particle out of the leading position":
            _Claim(1, ('family', 'given', 'middle'), "dce0ae6df4be"),
        "fix(#380) a trailing vd after a family comma is the tussenvoegsel, not a post-nominal":
            _Claim(1, ('family', 'suffix'), "081ce07f927b"),
        "fix(#399) a maiden marker bounds the particle chain that swallowed it":
            _Claim(6, ('family', 'maiden'), "b40129435671"),
        "fix(#360) mc moved into the never-given particles, so it folds into the family":
            _Claim(1, ('_ambiguities', 'family', 'given'), "ee4339908f4d"),
        "fix(#400) abd joins the word after it as one given name":
            _Claim(3, ('given', 'middle'), "6eb6b807523a"),
        "fix(#367) a title no longer displaces a leading never-given particle":
            _Claim(1, ('family', 'given'), "db724fb9c779"),
    },
}


def test_every_rule_claims_the_recorded_share_of_the_corpus() -> None:
    """The guard that knows nothing, and therefore cannot be dodged.

    Five rounds of review defeated five guards, each by moving to a
    rule the last fix did not cover: a span rule, then an alternation's
    members, then a non-maiden role, then a rule whose narrowing lived
    outside its alternation entirely. Every one of those attacks
    changed what the rule claimed -- 6 to 668 names, 0 to 193, and the
    comma rule from 3 roles to 6 while its regex and its 236 names
    stood still -- because that is what widening a rule means WITHIN
    the corpus. A widening reaching only names the corpora lack moves
    nothing here; the guards above are what see those.

    Note which layer is which, because it is the opposite of what it
    looks like. This is a change DETECTOR, not an enforcer: it is
    inert for a brand-new rule, whose author simply records whatever
    number it produces, and its own failure message invites the
    remedy that defeats it -- re-record and the attack lands. The
    member and vocabulary guards above are the walls, because they
    judge a rule wrong at any time INCLUDING at recording time. This
    catches the widenings none of them is scoped to see, and holds
    them still long enough for someone to look.
    """
    for ledger in _LEDGERS:
        assert ledger.name in _CORPUS_CLAIMS, (
            f"{ledger.name} is a new ledger with no recorded corpus claims; "
            f"add it to _CORPUS_CLAIMS (an empty mapping if it has no rules)")
        recorded = _CORPUS_CLAIMS[ledger.name]
        # Keyed on `issue`, so a duplicate silently collapses to the
        # last rule written and the other goes unmeasured -- coverage
        # by file order, which is no coverage. Nothing else asserts
        # this: validate_rules only requires a non-empty string, and
        # the tag-uniqueness check above covers span-bearing rules
        # alone. _LATIN_ALTERNATION_SOURCES and _HONORIFIC_SOURCES key
        # on issue SUBSTRINGS, so they lean on it too.
        issues = [rule["issue"] for rule in _rules(ledger)]
        assert len(set(issues)) == len(issues), (
            f"{ledger.name} has rules sharing an `issue`: "
            f"{sorted({i for i in issues if issues.count(i) > 1})}. Every "
            f"roster here keys on it, so one of them would go unmeasured")
        # A rule with no name_regex narrows by `fields` alone and so
        # reaches EVERY name -- the most unbounded shape validate_rules
        # permits, and the one most worth recording. Counting it as the
        # whole corpus is not a placeholder; it is what it claims.
        actual = {rule["issue"]: _claim(rule)
                  for rule in _rules(ledger)}
        moved = {issue: (recorded.get(issue), count)
                 for issue, count in actual.items()
                 if recorded.get(issue) != count}
        assert actual == recorded, (
            f"{ledger.name}: the corpus each rule claims is not what is "
            f"recorded. Moved (recorded, now): {moved}. Gone: "
            f"{sorted(set(recorded) - set(actual))}. New: "
            f"{sorted(set(actual) - set(recorded))}. A number that GREW "
            f"means the rule claims more of the corpus than it did -- "
            f"check it is not absorbing a regression, then record it")
    assert set(_CORPUS_CLAIMS) == {led.name for led in _LEDGERS}, (
        f"_CORPUS_CLAIMS names ledgers that do not exist: "
        f"{sorted(set(_CORPUS_CLAIMS) - {L.name for L in _LEDGERS})}")


#: Which rule classify() actually picks, for names several rules could
#: claim. Keyed by (name, the diff it produces against that baseline).
#:
#: Every other guard here measures a rule ALONE: _CORPUS_CLAIMS records
#: what a regex reaches, and the gate's total counts names. Neither can
#: see which rule wins a contest, and that is the property #372 is
#: about -- seven of these names spent months on fix(comma-family),
#: whose prose describes none of them, with every guard green and the
#: gate reporting 108/0 throughout.
#:
#: The comma family is recorded because it is where that went wrong.
#: 42 corpus names are reachable by two or more rules in the same tier;
#: these ten are the ones whose boundaries this file argues about, and
#: pinning the argument is cheaper than re-deriving it. Note
#: 'Andrews, M.D.' diffs on the SAME {given, suffix} shape as the seven
#: peels -- only the CJK lookahead separates them, so it is the row
#: that fails if that lookahead is ever dropped.
#:
#: The diff shapes are measured against the 1.4.0 wheel, not guessed.
#: Re-measure rather than adjust them if a parser change moves one:
#: a diff shape that shifted is a finding, not a number to update.
_CROSS_RULE_WINNERS: dict[str, dict[tuple[str, tuple[str, ...]], str]] = {
    "expected_since_1.4.0.toml": {
        ("Andrews, M.D.", ("given", "suffix")): "fix(comma-family)",
        ("田中, 太郎さん", ("given", "suffix")): "fix(cjk-comma-honorific-peel)",
        ("김, 민준씨", ("given", "suffix")): "fix(cjk-comma-honorific-peel)",
        ("김, 민준씨 (Jimmy)", ("given", "suffix")): "fix(cjk-comma-honorific-peel)",
        ("김민준, 씨", ("given", "suffix")): "fix(cjk-comma-honorific-peel)",
        ("김민준, 씨.", ("given", "suffix")): "fix(cjk-comma-honorific-peel)",
        ("선생님, J.씨", ("given", "suffix")): "fix(cjk-comma-honorific-peel)",
        ("이, J.씨", ("given", "suffix")): "fix(cjk-comma-honorific-peel)",
        # the union rows: they move `family`, so the peel rule's fields
        # exclude them and they must stay on the compound rule
        ("Dr 김민준씨, V.", ("family", "given", "suffix")):
            "fix(cjk-comma-compound)",
        ("田中さん, PhD", ("family", "given", "suffix")):
            "fix(cjk-comma-compound)",
        ("田中さん, V.", ("family", "suffix")): "fix(cjk-comma-compound)",
        # #372's suffix-routing split. 'Bob Jones, author' moves NO
        # suffix, which is what disqualifies it from the routing rule;
        # 'Smith Jr.' is the Latin shape that rule is named for; the two
        # glued honorifics are the majority it also legitimately takes,
        # and cannot be given a rule of their own -- '김민준씨' and the
        # given name '김지양' are the same string shape.
        ("Bob Jones, author", ("family", "given")):
            "fix(comma-precomma-family)",
        ("MD, PHD", ("family", "given")): "fix(comma-precomma-family)",
        ("Smith Jr.", ("family", "suffix")): "fix(suffix-routing)",
        # the glued/spaced boundary. 'Andersonさん' and '김민준씨' left
        # suffix-routing for a rule that names them; '김민준 씨.' is
        # spaced and stays on the spaced rule, which #372 taught to
        # tolerate the trailing period.
        #
        # '김지양' is why the glued rule copies GLUED_HONORIFICS and not
        # SUFFIX_WORDS: 양 is absent from the glued set, so no rule
        # NAMED for honorifics can claim a suffix diff on a given name
        # that merely ends in one. The fields-only fix(suffix-routing)
        # still would -- measured -- which is unchanged by #372 and is
        # the residual cost of having a last-resort tier at all. Being
        # absorbed by the catch-all is recoverable; being labelled
        # 'recognized honorific' by a specific rule is not.
        ("Andersonさん", ("given", "suffix")):
            "fix(cjk-glued-honorific-peel)",
        ("김민준씨", ("family", "given", "suffix")):
            "fix(cjk-glued-honorific-peel)",
        ("김민준 씨.", ("family", "given", "suffix")):
            "fix(cjk-honorific-suffix)",
    },
}


def test_the_recorded_rule_still_wins_each_contested_name() -> None:
    """Who explains what, which nothing else here asks.

    Measured: narrowing fix(cjk-comma-compound)'s script class sends
    three of these names to fix(suffix-routing) -- a fields-only
    catch-all whose prose is about two-token Latin names -- and the
    gate still reports 108 intentional / 0 unexplained. Reach is
    per-rule, the total is per-corpus; neither notices a name changing
    hands.

    A failure here is not necessarily a regression: it can equally mean
    a rule was narrowed correctly and its names found a better home. It
    means someone has to look, which is the point.
    """
    compare = load_tool("compare")
    by_name = {led.name: led for led in _LEDGERS}
    checked = 0
    for ledger_name, winners in _CROSS_RULE_WINNERS.items():
        ledger = by_name[ledger_name]
        rules = compare._sorted_rules(_rules(ledger))
        never = _exclusions(ledger)
        for (name, fields), expected in winners.items():
            got = compare.classify(name, set(fields), rules, never)
            assert got is not None and got.startswith(expected), (
                f"{ledger_name}: {name!r} diffing {list(fields)} is now "
                f"explained by {got!r}, not {expected!r}. Check the new "
                f"rule's prose actually describes this name before "
                f"recording it -- a rule claiming a diff it does not "
                f"describe is #372, and it stays green everywhere else")
            checked += 1
    assert checked, "no contested name was checked, so this pin is vacuous"
    assert set(_CROSS_RULE_WINNERS) <= {led.name for led in _LEDGERS}, (
        f"_CROSS_RULE_WINNERS names ledgers that do not exist: "
        f"{sorted(set(_CROSS_RULE_WINNERS) - {L.name for L in _LEDGERS})}")


class _Excluded(NamedTuple):
    """What a [[never]] entry silences, in the two dimensions that can
    change under it."""
    #: corpus names its name_regex captures
    captures: int
    #: sha256[:12] of those names, so a regex swap holding the count
    #: still fails -- the identity-free lesson _CORPUS_CLAIMS records
    digest: str
    #: rules that WOULD claim a protected reading of its examples, with
    #: exclusions switched OFF. This is the #328 event: a rule widened
    #: to reach a protected shape joins this tuple.
    absorbed_by: tuple[str, ...]


#: What each exclusion silences today, keyed by its name_regex.
#:
#: The first version of this guard asked whether a rule claims a
#: protected shape WITH exclusions active. It could not fail: classify()
#: consults exclusions first and returns None, and the guard only asked
#: about subsets the exclusion covers, so the answer was None by
#: construction. Measured: prepending a catch-all rule, and deleting
#: every rule in the ledger, both left it green across all 387 subsets.
#: It was the tenth inert measurement recorded in this tree.
#:
#: So ask with exclusions OFF, and record the answer. Then a rule
#: widened to reach a protected shape changes `absorbed_by` and demands
#: a decision -- which is the event #328 is about, and the one the
#: harness cannot report because the exclusion (correctly) hides it.
#:
#: `captures` and `digest` cover the opposite direction, which nothing
#: else watched: an exclusion widened by name_regex silences real
#: classifications, and BEFORE this record CI stayed green while the
#: release gate broke. Measured then: dropping the Ph. D. entry's
#: Latin anchor left the whole suite passing and took a bare run to
#: unexplained: 1. Measured now: the same edit fails this pin -- the
#: record is keyed by name_regex, so editing one is exactly what it
#: catches -- while the gate still goes to unexplained: 1.
#:
#: One limit worth naming: `absorbed_by` records only the FIRST rule
#: matching each subset, so a rule appended behind one that already
#: answers those subsets is invisible here. A rule reaching a
#: protected READING is caught; a rule shadowed by an existing one on
#: every subset it claims is not.
_EXCLUSION_EFFECT: dict[str, _Excluded] = {
    "(?i)^[\\u0000-\\u024f]*\\bph\\.\\s*d\\.\\s*$":
        _Excluded(3, "5a12a8117651",
                  # fix(comma-precomma-family) JOINED this tuple in #372,
                  # it did not replace anything: it claims the {given,
                  # family} readings, which it legitimately describes for a
                  # Latin comma name, while fix(suffix-routing) still
                  # claims the readings outside its two fields. The
                  # exclusion refuses the name before any of the three is
                  # reached; this records what would happen without it.
                  ("fix(comma-family)", "fix(comma-precomma-family)",
                   "fix(suffix-routing)")),
    '(^|[\\w.]\\s+)[("\'][^)"\']+[)"\'](\\s+\\w|\\s*$)':
        _Excluded(42, "e594ae1a2e73", ()),
}


def _protectable_fields(compare: ModuleType) -> tuple[str, ...]:
    """The universe both exclusion pins quantify over: every field a
    rule's `fields` may name, which is what an exclusion's may name too.

    Not `Role` alone. validate_exclusions accepts `_ambiguities` -- a
    SEGMENTATION-only diff is facade-identical, so it is the one name
    that can classify one -- and a universe of the seven roles never
    builds a subset containing it. Measured: a rule with
    `fields = ["_ambiguities"]` and no `name_regex` claims the
    ambiguity-only reading of every protected shape, which is the #328
    event in that dimension, and only the wider universe grows
    `absorbed_by` and fails.

    It does NOT close the matching hole on the exclusion side: an entry
    narrowing itself to `fields = ["_ambiguities"]` protects nothing
    anyone would notice and passes both pins under either universe,
    because `absorbed_by` is legitimately empty for the honest entry
    too. Taking the universe from compare's own set at least keeps the
    two from drifting apart as `_RULE_FIELDS` grows.
    """
    return tuple(sorted(compare._RULE_FIELDS))


def test_every_exclusion_silences_what_is_recorded() -> None:
    """Both directions an exclusion can drift, recorded rather than
    derived -- because a derivation from the same data always agrees
    with itself, which is how the first version of this guard came to
    be tautological.

    `absorbed_by` is asked with exclusions OFF. That is the only way to
    see the #328 event at all: once an entry is in place the harness
    reports nothing, correctly, so a rule widened to reach a protected
    shape is invisible everywhere else. When this tuple grows, someone
    has to decide whether the new rule is legitimate and the exclusion
    is now doing real work, or whether the rule reached too far.

    `captures`/`digest` are the opposite drift. An over-wide exclusion
    silences classifications a rule should make -- loud at release,
    silent in CI, which is the wrong way round for something a push
    can introduce.
    """
    compare = load_tool("compare")
    roles = _protectable_fields(compare)
    actual: dict[str, _Excluded] = {}
    for ledger in _LEDGERS:
        rules = compare._sorted_rules(_rules(ledger))
        for entry in _exclusions(ledger):
            captured = sorted(name for name in _CORPUS_NAMES
                              if re.search(entry["name_regex"], name))
            covered = entry.get("fields")
            absorbed = set()
            for example in entry["examples"]:
                for size in range(1, len(roles) + 1):
                    for combo in itertools.combinations(roles, size):
                        diff = set(combo)
                        if covered is not None and not diff <= set(covered):
                            continue
                        claimed = compare.classify(example, diff, rules)
                        if claimed:
                            absorbed.add(claimed.split(")")[0] + ")")
            actual[entry["name_regex"]] = _Excluded(
                len(captured),
                hashlib.sha256(
                    "\n".join(captured).encode("utf-8")).hexdigest()[:12],
                tuple(sorted(absorbed)))
    assert actual == _EXCLUSION_EFFECT, (
        f"what an exclusion silences has moved. Recorded "
        f"{_EXCLUSION_EFFECT}, now {actual}. A grown `absorbed_by` means "
        f"a rule now reaches a protected shape -- decide whether that "
        f"rule is right before recording it. A changed captures/digest "
        f"means the exclusion itself moved, which is loud at release "
        f"and silent here until this fails.")
    assert actual, (
        "no ledger declares a [[never]] entry, so this pin is passing "
        "vacuously")


def test_a_fields_narrowing_actually_narrows_something() -> None:
    """The other direction, which nothing else watches.

    test_every_exclusion_silences_what_is_recorded pins an entry's
    reach by NAME -- how much corpus it captures, and which rules would
    claim its examples. It says nothing about whether the `fields`
    narrowing on top of that reach still leaves anything behind, and
    the two failures are not symmetric: an over-wide `fields` silences
    diffs a rule should explain, on names that are not examples and so
    are looked at nowhere else.

    Note where this fails when `fields` is DELETED outright: on the
    vacuity assert at the end, not on the per-entry assert below, since
    a deleted key drops the entry from the loop entirely. That works
    only while one entry carries `fields`. A second one would leave the
    deletion green here -- caught instead by `absorbed_by` in the
    recorded pin, which is then asked about every reading rather than
    the three the key covers, and sees rules claim them. Measured:
    deleting this entry's `fields` grows its `absorbed_by` from () to
    ('fix(suffix-routing)',).

    Measured: deleting `fields = ["nickname", "middle"]` from the
    ASCII-pairs entry passes every other check in this tree. The entry
    then refuses ANY diff on the 34 corpus names it captures --
    including 'Jenny (Johnson) Baker' and 'Lon (Jr.) Williams', whose
    parens are a maiden name and a suffix, both under active
    development. Nothing failed, because none of those names diffs
    today and none of them is an example.

    So: an entry that bothers to name `fields` must leave something
    behind. If no captured corpus name is still classifiable on a
    reading outside them, the narrowing is not narrowing -- either it
    was deleted, or it grew to cover everything the entry reaches.
    """
    compare = load_tool("compare")
    roles = _protectable_fields(compare)
    checked = 0
    for ledger in _LEDGERS:
        rules = compare._sorted_rules(_rules(ledger))
        never = _exclusions(ledger)
        for entry in never:
            covered = entry.get("fields")
            if covered is None:
                continue
            checked += 1
            captured = [name for name in _CORPUS_NAMES
                        if re.search(entry["name_regex"], name)]
            survives = [
                (name, sorted(combo))
                for name in captured
                for size in (1, 2)
                for combo in itertools.combinations(roles, size)
                if not set(combo) <= set(covered)
                and compare.classify(name, set(combo), rules, never)]
            assert survives, (
                f"{ledger.name}: the entry for {entry['name_regex']!r} names "
                f"fields={covered}, but no corpus name it captures is still "
                f"classifiable on any reading outside them. It captures "
                f"{len(captured)} names, so the narrowing has stopped "
                f"narrowing -- check it was not deleted or widened to cover "
                f"the whole entry.")
    assert checked, (
        "no exclusion declares `fields`, so this pin is passing vacuously")


def test_a_rule_reaching_no_corpus_name_says_why_it_is_kept() -> None:
    """The cheap half of #372, asked on every push.

    A rule whose regex reaches nothing explains nothing, and no other
    guard here can tell that from a rule that is merely narrow:
    _CORPUS_CLAIMS records the reach it HAS, whatever that is, so a
    reach of zero is recorded as contentedly as any other number.

    This is deliberately about REACH, not about diffs. Asking whether a
    rule explained a diff needs a baseline wheel and belongs in the
    harness; asking whether it could reach any name at all needs only
    the corpus, so it runs here, on every push, for free.
    """
    silent = []
    checked = 0
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            if "dormant" in rule:
                continue
            # fields-only rules reach every name by construction, so only
            # a name_regex can be statically silent -- see _claim(), which
            # counts them as the whole corpus for the same reason
            regex = rule.get("name_regex")
            if not isinstance(regex, str):
                continue
            checked += 1
            if not _claimed(regex):
                silent.append(f"{ledger.name}: {rule['issue']}")
    assert not silent, (
        f"these rules reach no corpus name, so they explain nothing and "
        f"nothing else would say so: {silent}. Either declare `dormant` "
        f"with the reason the rule is worth keeping, or delete it.")
    assert checked, (
        "no rule was examined, so this guard is passing vacuously -- "
        "every rule either declares `dormant` or narrows by `fields` "
        "alone")
