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

from nameparser import DEFAULT_NICKNAME_DELIMITERS, _policy
from nameparser._policy import Script
# The parser's own fold, imported rather than reimplemented: a
# hand-written one here stripped commas, parens, brackets and quotes,
# five character classes neither the lexicon's fold nor config's
# assert_normalized touches -- looser in the dangerous direction, and a
# hand copy of a constant with a source of truth, inside the module
# written to forbid exactly that.
from nameparser._lexicon import _PHRASE_FIELDS, _normalize
from nameparser.config.bound_given_names import BOUND_GIVEN_NAMES
from nameparser.config.conjunctions import CONJUNCTIONS
from nameparser.config.maiden_markers import MAIDEN_MARKERS
from nameparser.config.particles import PARTICLES
from nameparser.config.titles import GIVEN_NAME_TITLES, TITLES
from nameparser.config.suffixes import (
    GLUED_HONORIFICS, SUFFIX_ACRONYMS, SUFFIX_ACRONYMS_AMBIGUOUS,
    SUFFIX_WORDS)

from ._differential_fixtures import (
    _CORPUS_NAMES, _LEDGERS, _TOOLS, _UNCLASSIFIED_NAMES, _claimed,
    _entry_name, _exclusions, _rules, _unclassified_names, load_tool)


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


@pytest.mark.parametrize("field", _PHRASE_FIELDS)
def test_a_shipped_phrase_entry_is_stored_as_written(field: str) -> None:
    """The half of a phrase entry's storage rule config's own
    assert_normalized cannot see.

    It checks the single-spaced lowercase form; the per-WORD period
    strip is _lexicon._title_key's, and a data module asserting with
    the parser's fold would make a constant's hygiene depend on the
    parser. The question that actually matters is asked here instead,
    and it is stronger than the fold: does Lexicon store the shipped
    constant UNCHANGED? An entry written 'z. domu' passes import-time
    hygiene and is silently rewritten to 'z domu' -- inert as a lookup
    key nobody wrote, and invisible everywhere until now.

    Over _PHRASE_FIELDS rather than over maiden_markers, so the
    given_name_titles half is covered by the same assertion and a third
    phrase field arrives already pinned. Nothing else in the suite pins
    this equality for any field.
    """
    from nameparser import Lexicon
    shipped = {"maiden_markers": MAIDEN_MARKERS,
               "given_name_titles": GIVEN_NAME_TITLES}[field]
    assert getattr(Lexicon.default(), field) == frozenset(shipped), (
        f"{field}: Lexicon rewrote the shipped constant, so the entries "
        f"it stores are not the ones the data module wrote -- "
        f"{sorted(frozenset(shipped) - getattr(Lexicon.default(), field))} "
        f"were folded away or changed")


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
    "expected_since_2.1.0.toml": frozenset(),   # 2.2 cycle: no span-bearing rule
    # open cycle: its one rule, fix(#462), is a Latin letter shape and
    # copies no script range
    "expected_since_2.2.0.toml": frozenset(),
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
        # looking, and its Latin half claims all but a handful of
        # _UNCLASSIFIED_NAMES -- the whole population this assertion is
        # over, whatever that population's size that day; this sees it.
        # Both are kept: the depth test gives the clearer message
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


def test_the_emoji_boundary_rule_copies_the_dividing_ranges() -> None:
    """The emoji rule's character class is a HAND COPY of the ranges
    the tokenizer actually divides on, and this is what keeps the two
    in step.

    The rule promises "an emoji inside a token divides it". Only
    _EMOJI_RANGES decides that, so a class wider than those ranges
    makes the promise false for every codepoint in the gap -- and the
    rule would then claim a {given, family} diff whose cause is
    something else entirely. The first draft had exactly that bug: one
    \\U0001F300-\\U0001FAFF span, covering U+1F650-U+1F67F and
    U+1F700-U+1FAFF, where the parser leaves the token whole.

    Only the ASTRAL half is copied. The BMP half (U+2600-U+26FF,
    U+2700-U+27BF) is out because no corpus name reaches it through
    the rule's \\S...\\S anchor, and a rule should be no wider than the
    diffs it must explain -- so this asserts a SUBSET relationship in
    that direction, not equality. What it refuses is the other
    direction: a class reaching a codepoint the tokenizer does not
    divide on.
    """
    from nameparser._pipeline._tokenize import _EMOJI_RANGES

    divides = {c for lo, hi in _EMOJI_RANGES for c in range(lo, hi + 1)}
    found = 0
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            if "emoji-boundary" not in rule["issue"]:
                continue
            found += 1
            pattern = rule["name_regex"]
            # EVERY codepoint, not just the astral plane. Scanned
            # 0x1F000-0x20000 until the #453 review measured what that
            # missed: a bare '-' or a \u2B00-\u2BFF span appended to
            # the class left this guard GREEN while the rule stood
            # ready to explain a {given, family} regression on 22
            # hyphenated corpus names. The docstring promises to
            # refuse a class reaching a codepoint the tokenizer does
            # not divide on; a scan narrower than that promise is the
            # #451 shape one level down. Costs 0.3s.
            claimed = {c for c in range(0x20, 0x110000)
                       if re.search(pattern, f"a{chr(c)}b")}
            stray = sorted(claimed - divides)
            assert not stray, (
                f"{ledger.name}: {rule['issue']!r} claims "
                f"{len(stray)} codepoint(s) the tokenizer does not "
                f"divide on, e.g. {[hex(c) for c in stray[:3]]}. Its "
                f"prose says an emoji inside a token divides it, which "
                f"is false for those -- so a diff with another cause "
                f"would classify here as intended. Copy from "
                f"_EMOJI_RANGES rather than widening the span.")
            assert claimed, (
                f"{ledger.name}: {rule['issue']!r} claims no codepoint "
                f"at all; the class or the anchor is broken and the "
                f"rule can explain nothing")
    assert found, (
        "no emoji-boundary rule in any ledger; this pin is passing "
        "vacuously")


def test_cjk_corpus_matches_the_case_table() -> None:
    """corpus_cjk.jsonl is GENERATED, not curated (#295): every
    distinct case-table text bearing a codepoint the script table
    classifies -- minus the rows that declare `tolerated` (the
    2026-09-01 demotion; they are the twin test below) -- sorted.
    See build_cjk_corpus.py for why the other two corpora cannot
    carry these names. The checked-in file must equal what the
    generator would write, so a CJK case row added without
    regenerating fails HERE instead of silently narrowing the
    differential gate back toward the blind spot #295 closed. Same
    promise as the toml pin above, aimed at a generated artifact
    instead of a hand copy.
    """
    module = load_tool("build_cjk_corpus")
    checked_in = [json.loads(line) for line in
                  (_TOOLS / "corpus_cjk.jsonl")
                  .read_text(encoding="utf-8").splitlines()]
    assert checked_in == module.selected_names(), (
        "corpus_cjk.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_cjk_corpus.py`")


def test_tolerated_cjk_corpus_matches_the_case_table() -> None:
    """The radar half of the same generated projection: the texts
    whose case rows declare `tolerated`. Pinned for the same reason
    as the contract half one function up -- one command writes both
    files, so a row marked without regenerating leaves the demoted
    name in NEITHER file and its diffs invisible at every baseline,
    which is the failure the radar tier exists to prevent."""
    module = load_tool("build_cjk_corpus")
    checked_in = [json.loads(line) for line in
                  (_TOOLS / "corpus_cjk_tolerated.jsonl")
                  .read_text(encoding="utf-8").splitlines()]
    assert checked_in == module.tolerated_names(), (
        "corpus_cjk_tolerated.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_cjk_corpus.py`")


def test_a_text_tolerated_on_one_row_only_is_a_hard_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The two pins above compare files to a selection; neither can
    see the one input that has no right answer. A corpus carries name
    STRINGS, so a text on two rows -- a default row and a
    policy/locale fork of it, which several CJK texts have -- is one
    line in one file, and marking one of those rows and not the other
    declares both tiers for it.

    What makes the raise load-bearing rather than tidy is the
    consequence with it removed, which the negative control below
    measures instead of asserting in prose: the two halves select
    `flags == {False}` and `flags == {True}`, so a split text matches
    NEITHER and would be dropped from both files -- gone from the
    harness, watched at no baseline, and invisible to every guard
    here (the pins would agree with the degraded selection, and the
    floors bound the loss to a few names). The message must name the
    offending text for the same reason: an author who has to go
    hunting for which row is split is an author who marks the other
    one at random.
    """
    from tests.v2.cases import Case
    module = load_tool("build_cjk_corpus")
    split = [
        Case(id="split_a", text="田中さん, PhD", expect={"family": "田中"},
             tolerated=True),
        Case(id="split_b", text="田中さん, PhD", expect={"family": "田中"}),
        Case(id="pure", text="김민준", expect={"family": "김"}),
    ]
    monkeypatch.setattr(module, "CASES", split)
    with pytest.raises(SystemExit, match=r"'田中さん, PhD' on \['split_a', "
                                          r"'split_b'\]"):
        module._partition()

    # The negative control: the same selections the generator runs,
    # with the raise conceptually deleted. The split text is in
    # neither half -- which is the dropped-name failure the docstring
    # above describes, reproduced rather than asserted from reading.
    by_text: dict[str, set[bool]] = {}
    for case in split:
        by_text.setdefault(case.text, set()).add(case.tolerated)
    contract = {t for t, f in by_text.items() if f == {False}}
    tolerated = {t for t, f in by_text.items() if f == {True}}
    assert "田中さん, PhD" not in contract | tolerated
    assert contract | tolerated == {"김민준"}


def test_shapes_corpus_matches_the_case_table() -> None:
    """corpus_shapes.jsonl is GENERATED from the shape-tagged case
    rows -- the same promise test_cjk_corpus_matches_the_case_table
    makes above, for the tag predicate instead of the
    codepoint one: a row tagged without regenerating fails HERE
    instead of silently keeping the contract tier narrower than the
    table says it is."""
    module = load_tool("build_shapes_corpus")
    checked_in = [json.loads(line) for line in
                  (_TOOLS / "corpus_shapes.jsonl")
                  .read_text(encoding="utf-8").splitlines() if line.strip()]
    assert checked_in == module.selected(), (
        "corpus_shapes.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_shapes_corpus.py`")


def test_case_shape_ids_exist_in_the_inventory() -> None:
    """cases.py cannot import tools/, so Case.__post_init__ validates
    every shape tag against its own hand copy of the inventory's id
    set (cases._SHAPE_IDS). This is the cross-file half, in two parts.
    The equality holds the copy itself honest: a shape added to or
    removed from shapes.py without updating cases._SHAPE_IDS fails
    here, whichever side changed. The subset check catches a
    different drift -- a row tagged under a stale _SHAPE_IDS before
    this test last ran -- so it stays even though __post_init__ would
    refuse the same tag today."""
    from tests.v2 import cases
    shapes = load_tool("shapes")
    tagged = {c.shape for c in cases.CASES if c.shape is not None}
    assert tagged <= set(shapes.SHAPES), (
        f"tests/v2/cases.py tags shape id(s) "
        f"{sorted(tagged - set(shapes.SHAPES))} that are not in "
        f"tools/differential/shapes.py's SHAPES; add the shape there "
        f"or fix the tag in cases.py")
    assert cases._SHAPE_IDS == set(shapes.SHAPES), (
        f"cases._SHAPE_IDS {sorted(cases._SHAPE_IDS)} != shapes.py's "
        f"{sorted(shapes.SHAPES)}; they are hand copies of one "
        f"inventory -- update whichever side is stale")


#: Names each rule MUST NOT match, keyed by a substring of its `issue`.
#:
#: A wall, not a change detector, and that is the point. _CORPUS_CLAIMS
#: catches a widening that changes corpus reach or roles -- but a rule
#: whose regex is literal-anchored and claims exactly ONE corpus name
#: can be widened with the count unmoved, because the names it newly
#: reaches are not in the corpora. Such widenings were demonstrated on
#: this file's own rules with the whole suite green: `^mc\s+\S+$`
#: to `^mc` (every leading Mc*), the vd rule to a bare `\bvd\b`,
#: `^sir\s+de\b` without its anchor, and the nakaguro rule to `·.*씨`.
#: Each of those then stood ready to explain exactly what its own
#: comment promises will arrive UNEXPLAINED. The list is the evidence;
#: a count here said six over four items and was the only part anyone
#: could get wrong, since the widenings themselves are named.
#:
#: The probes are taken from the names those comments already argue
#: about, so this roster records an answer someone already wrote in
#: prose. Being a wall rather than a snapshot, it is wrong at recording
#: time too -- a probe that matches when it is added fails immediately
#: rather than being blessed as the new normal.
#:
#: A probe must be a name the rule has no business claiming, NOT merely
#: one that does not move today: rules deliberately claim some static
#: names (fix(#399) claims 'Jane van der Berg nee PhD', fix(#400)
#: claims 'abd Allah'), and those are recorded in the rules' comments
#: instead.
_MUST_NOT_MATCH: dict[str, tuple[str, ...]] = {
    "fix(#380)": ("vd Berg, Jan", "Jan vd Berg", "Smith vd",
                  "Berg, Jan mc"),
    "fix(#399)": ("Jane van der Berg née", "Jane van der Berg née y Jones",
                  "van der Berg, abdul née Jones", "Jane Smith née Jones"),
    # Keyed on the full issue text, not "fix(#360)": that substring now
    # matches two rules, and each one's boundary is the other's claim.
    "fix(#360) mc moved into the never-given particles, so it folds into the family":
        ("McDonald, Ronald", "Mcintyre Smith Jr.", "Ste Marie",
         "Los Santos"),
    "fix(#360) ste moved into the never-given particles with mc":
        ("Steve Marie", "Ste", "Mc Donald", "Los Santos",
         "Ste Marie Jones", "Ste. Marie Dupont"),
    "fix(#400)": ("Jane Smith ABD", "Jane Smith A.B.D.", "Abdul Salam"),
    "fix(#400/#274)": ("abd Berg née Jones", "abd Allah Smith",
                       "Jane Smith née Jones"),
    # The literal-anchored rules #413 added. Each claims exactly one
    # corpus name -- _CORPUS_CLAIMS carries that reach for both, so the
    # number is pinned there rather than asserted here -- and a reach
    # that small is one _CORPUS_CLAIMS cannot use: a widening reaching
    # only names the corpora lack leaves it unmoved. These probes are
    # the only wall.
    "fix(#399) a maiden marker bounds the particle chain: the geb. spelling":
        ("Berg, Ursula von der geb. Albrecht",),
    "fix(credential-pair-order) a split credential and a suffix render in written order":
        ("田中さん, Jr. Ph. D.", "Smith, Jr. Ph. D. MD"),
    "fix(#411)": ("abdul née Jones", "Smith, abdul Rahman",
                  "Jane Smith ABD", "van der Berg, abd née Jones"),
    "fix(#411/S2)": ("van der Berg, abdul née Jones", "Berg, abd Rahman",
                     "Jane Smith ABD"),
    "fix(#367) a title no longer displaces a leading never-given particle":
        ("John Sir de Mesnil", "Smith, Sir de Vaux", "Sir Smith"),
    "fix(#272/#308)": ("田中·太郎 김씨", "A·B 씨", "山田·花子"),
    "fix(nickname-typographic-pairs)": ("Hans „Hansi“ Müller",
                                        "John “Jack” Kennedy"),
    "fix(#274)": ("Jones née", "née Jones", "Jane van der Berg née",
                  "Jane Smith (Nee)"),
    # #399's and #274's names: a marker followed by a NAME word was
    # never the connective join's to reach. A connective BEFORE the
    # marker ('Jane Smith and née Jones') IS the rule's shape, reached
    # from the other side, and is deliberately not a probe: the regex
    # is scoped to marker-then-connective because that is what the
    # corpora carry -- a snapshot, not a boundary.
    "fix(#412)": ("Jane van der Berg née Jones", "Jane Smith née Jones",
                  "Jane van der Berg née", "Jane née Andrews Smith"),
    # the carve-out is a THREE-word rule: four name words join with or
    # without the clause, a name with no clause has nothing to lose,
    # and the #412 pair is the other rule's
    "fix(#418)": ("Juan y Eva Garcia née Jones", "Juan y Garcia",
                  "Jane van der Berg née y Jones", "Juan y Garcia née"),
    # literal-anchored to its one example: the suffix-then-connective
    # class has no other corpus name, and a name with either half
    # missing is fix(#399)'s or fix(#412)'s
    "fix(#418) accepted": ("Jane née Jr Jones", "Jane née y Jones",
                           "Jane van der Berg née Jr Jones"),
    # decisions.md#H1's own nickname-plus-title-plus-name shape, kept
    # out on purpose: this rule is anchored to a trailing suffix word,
    # not a title, and a two-token name (with or without the suffix)
    # has no third token for the regex to require.
    "fix(N3) a nickname-led name with a trailing suffix keeps the suffix in `suffix`":
        ("'Smitty' Jones", "Jones Jr.", "'Smitty' Dr. Jones"),
    # #451's two NOT-WANTED rules, literal-anchored to one corpus name
    # apiece: a three-token name with a rootname before or after is a
    # different diff shape (or, for 'Carod i Rovira' and 'Lluis Carod
    # i', no diff at all -- #397's still-open enhancement, not a
    # 1.4-to-2.x regression), and 'Rai'/'Jane Rai Smith' have no
    # 'aishwarya' to anchor on.
    "fix(#342)": ("Aishwarya Rai Bachchan", "Rai", "Jane Rai Smith"),
    "fix(#397)": ("Carod i Rovira", "Josep Carod i Rovira", "Lluis Carod i"),
    # #451's four replacements for the fields-only catch-all. Each is
    # anchored to a two-token name, so the probes are a third token and
    # each other's vocabulary: the four exist BECAUSE one rule could not
    # carry all six names, and a rule that quietly grew to reach a
    # sibling's name would put the split back where it started.
    #
    # 'Carod i' and '田中さん II' are deliberately NOT probes for the
    # numeral rule: its regex really does reach both, and rules above it
    # win them -- 'Carod i' on file order, '田中さん II' on the subset
    # test, its diff moving {family, given, suffix} where the numeral
    # rule declares {family, suffix} and so cannot admit the `given`
    # move. _CROSS_RULE_WINNERS pins both instead;
    # this roster tests the regex, not classify().
    "fix(suffix-routing) a two-token name ending in a roman numeral keeps it in `suffix`":
        ("Mohamad X Surname", "Smith Jr.", "Donald mc", "Aishwarya Rai"),
    "fix(suffix-routing) a two-token name ending in the suffix word jr keeps it in `suffix`":
        ("John Smith Jr.", "Smith Jr. PhD", "John V", "Jack Ma"),
    # 'Mc Donald' is the leading-particle shape fix(#360) claims and
    # 'Berg, Jan vd' the comma shape P6 gives to fix(#380); this rule is
    # the third corner, trailing and comma-less, and must not reach
    # either of the others.
    "fix(suffix-routing) a two-token name ending in a credential acronym keeps it in `suffix`":
        ("Mc Donald", "Berg, Jan vd", "John Smith MP", "Jack Ma"),
    # decisions.md#ma-do turns on the BARE spelling keeping its surname
    # while the dotted one reads as a credential, so both spellings of
    # the bare one are probes here -- and 'Jack Ma' is a probe for the
    # acronym rule above as well, since 'ma' is acronym vocabulary too.
    "fix(suffix-routing) the dotted M.A. spelling reads as a credential (ma-do)":
        ("Jack Ma", "Jack MA", "John Smith M.A."),
    # #484: the connective rule is case-sensitive on the single letters
    # so that the #462 shapes -- a capital or dotted E that is an
    # INITIAL the facade drops -- are never claimed as the per-word
    # grouping change. Since the facade fix these names AGREE with
    # 1.4.0 and diff only against the 2.x baselines, where fix(#462)
    # claims them, so a #462 REGRESSION is the only way they can diff
    # at this baseline again -- and it must surface as UNEXPLAINED
    # rather than be absorbed as per-word grouping. That is what the
    # case-sensitivity buys, and it is why this roster keeps probing
    # for it after the bug is gone.
    "a connective run initials": ("Jose E Maria Santos",
                                  "JOSE E MARIA SANTOS",
                                  "Scott E. Werner", "Amy E Maid"),
    # fix(#462)'s boundary: lowercase bare e/y is the connective;
    # 'E.T.' is a run of initials the rule has no view on; a bare I
    # is not conjunction vocabulary at all.
    "fix(#462)": ("john e smith", "maria y lopez", "E.T. Smith",
                  "Maier, Amy I, Jr."),
}


def test_no_rule_matches_a_name_it_has_no_business_claiming() -> None:
    """The wall _CORPUS_CLAIMS cannot be.

    A claim count moves only when corpus reach moves, so a rule that
    claims one corpus name can be widened arbitrarily as long as the
    names it newly reaches are outside the corpora -- and every rule
    added by #414 is literal-anchored and claims exactly one. This
    asserts the boundaries those rules' comments argue for, against
    names chosen to sit just outside them.
    """
    checked = 0
    hits_by_key: dict[str, int] = {k: 0 for k in _MUST_NOT_MATCH}
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            regex = rule.get("name_regex")
            if not isinstance(regex, str):
                continue
            for key, probes in _MUST_NOT_MATCH.items():
                if key not in rule["issue"]:
                    continue
                hits_by_key[key] += 1
                for probe in probes:
                    checked += 1
                    assert not re.search(regex, probe), (
                        f"{ledger.name}: {rule['issue']!r} matches "
                        f"{probe!r}, a name its own comment says should "
                        f"arrive UNEXPLAINED. Either the rule widened "
                        f"or the boundary moved -- if the latter, the "
                        f"comment and this roster both need editing")
    # Per KEY, not in aggregate. The old spelling summed one counter
    # over every key, so renaming a single key to a string no rule
    # contains left the suite green -- which is exactly the edit the
    # message below warns about.
    empty = sorted(k for k, n in hits_by_key.items() if not n)
    assert not empty, (
        f"_MUST_NOT_MATCH keys matching no rule: {empty}. The keys are "
        f"`issue` substrings, so a renamed or deleted rule silently "
        f"empties its pin while every other key keeps this test green")
    assert checked


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

    # The equality above cannot see a generator that silently selects
    # LESS: someone regenerates, the file agrees with the degraded
    # selection, and both are wrong together. _CORPUS_FLOORS bounds
    # that to a few names; these two bound the shapes it cannot.
    #
    # A rule whose ID line stops matching, or that gains a heading
    # mid-block, loses its examples to the previous rule or to
    # nothing. Both are loud today only by luck of a neighbouring
    # invariant -- every rule carries `implemented:` and is cited from
    # code, so test_doc_citations fails on the unknown ID. That is a
    # different file's guarantee and could stop holding.
    from .rules_doc import parse_rules_doc
    rules = parse_rules_doc(
        (_TOOLS.parents[1] / "docs" / "design" / "rules.md")
        .read_text(encoding="utf-8"))
    assert len(rules) >= 38, (
        f"rules.md parsed to {len(rules)} rules, fewer than the 38 this "
        f"corpus was built from. A rule block that stops parsing hands "
        f"its examples to its neighbour and shrinks the corpus "
        f"silently. Ratchet this floor up when rules are added")
    empty = [r.rule_id for r in rules
             if not any(e.text for e in r.examples)]
    assert empty == ["D1", "D2"], (
        f"rules with no example NAME: {empty}. D1 and D2 are the "
        f"expected two -- their examples name a policy rather than a "
        f"name string. Any other rule contributing nothing means its "
        f"examples stopped being recognized as examples, which the "
        f"file-equality check above cannot distinguish from a rule "
        f"that never had any")


def _tolerated_only_texts(rules: list) -> set[str]:
    """Example texts a `tolerated:` rule carries and no normative rule
    does -- the subtraction the demotion guards below both scope by.

    Shared rather than written twice because the two guards must agree
    on WHICH texts a demotion is about: one asserts they left the
    contract corpus, the other that they are still watched somewhere,
    and a pair disagreeing about the set would leave a text neither
    enforced nor watched while both stayed green. An example some
    normative rule also carries is in the contract on that rule's
    account -- demoting one rule cannot take another's name away.
    """
    normative = {e.text for r in rules if r.tolerated is None
                 for e in r.examples if e.text}
    return {e.text for r in rules if r.tolerated is not None
            for e in r.examples if e.text} - normative


def test_a_tolerated_rule_puts_no_name_in_the_rules_corpus() -> None:
    """A rule marked `tolerated:` in rules.md contributes no example
    to the CONTRACT corpus (2026-09-01, the CJK comma demotion).

    The equality above would pass with the skip deleted -- regenerate
    and the file agrees with whatever the generator now selects. This
    reads the doc's marker directly and asks the file. Scoped to the
    marked rule's OWN texts: an example some normative rule also
    carries is in the corpus on that rule's account, and demoting one
    rule cannot take another's name away, so the check subtracts them
    rather than failing on them.

    What it does NOT check: that the demoted names are still watched
    somewhere. That is the opposite promise and it has its own guard,
    the next one down -- this pair is a floor and a ceiling on the
    same set of texts, and each is vacuous without the other. Deleting
    an example satisfies this one; adding an unwatched one satisfies
    that one; only together do they say what a demotion is.
    """
    from .rules_doc import parse_rules_doc
    rules = parse_rules_doc(
        (_TOOLS.parents[1] / "docs" / "design" / "rules.md")
        .read_text(encoding="utf-8"))
    tolerated = [r for r in rules if r.tolerated is not None]
    assert tolerated, (
        "no rule in rules.md carries a `tolerated:` marker; W3 has "
        "carried one since 2026-09-01. If a demotion was reversed, "
        "delete this guard in that commit rather than leaving it "
        "asserting nothing")
    in_corpus = {json.loads(line) for line in
                 (_TOOLS / "corpus_rules.jsonl")
                 .read_text(encoding="utf-8").splitlines()}
    leaked = sorted(_tolerated_only_texts(rules) & in_corpus)
    assert not leaked, (
        f"corpus_rules.jsonl carries example texts belonging only to "
        f"tolerated rules {[r.rule_id for r in tolerated]}: {leaked}. "
        f"A tolerated rule's examples illustrate current behavior; "
        f"enforcing them against released baselines is the promise "
        f"the marker withdrew")


def test_a_tolerated_rules_examples_are_still_watched_somewhere() -> None:
    """Every text a tolerated rule alone carries is in SOME corpus the
    harness loads, so it is still compared at every released baseline
    -- the half of the demotion the marker did not withdraw.

    The failure this closes, verified by injection rather than
    reasoned about (the negative control below runs it): a sixth comma
    example added to W3 with no `tolerated` row in tests/v2/cases.py.
    Nothing in the suite notices. The doc parses, test_rules_doc.py
    executes the example and it passes, build_rules_corpus.py skips
    the whole rule so the contract pin above stays equal, and
    build_cjk_corpus.py projects the CASE TABLE -- it never sees a
    name nobody wrote a row for. The text is executed at HEAD and
    compared at no baseline, with every suite green. That is exactly
    the state the demotion was written to avoid: "we still watch it,
    we no longer enforce it" costs the watching, or it costs nothing
    and means nothing.

    Membership is asked of the UNION of the corpora rather than of
    corpus_cjk_tolerated.jsonl by name, because the union is what this
    can honestly promise: the requirement is that the name reaches the
    comparison, and which file carries it is the projection's business
    (a future tolerated rule outside the CJK sections would have no
    business in a CJK file at all). Today every one of them arrives
    through corpus_cjk_tolerated.jsonl -- W3's four comma texts, its
    fifth example being W1's normative one and subtracted here -- and
    that file's equality with the case table is pinned separately by
    test_tolerated_cjk_corpus_matches_the_case_table.
    """
    from .rules_doc import parse_rules_doc
    doc = (_TOOLS.parents[1] / "docs" / "design" / "rules.md").read_text(
        encoding="utf-8")
    rules = parse_rules_doc(doc)
    demoted = _tolerated_only_texts(rules)
    # Anti-vacuity, the same shape the guard above carries: with no
    # marked rule, or with the subtraction eating everything, the
    # assertion below is a truth about the empty set.
    assert demoted, (
        "no rule in rules.md carries a `tolerated:` marker with an "
        "example text of its own; W3 has carried four since "
        "2026-09-01. If a demotion was reversed, delete this guard in "
        "that commit rather than leaving it asserting nothing")
    unwatched = sorted(demoted - set(_CORPUS_NAMES))
    assert not unwatched, (
        f"tolerated rules in rules.md carry example texts no corpus "
        f"holds: {unwatched}. Each is executed at HEAD and compared "
        f"at no baseline. Give it a `tolerated=True` row in "
        f"tests/v2/cases.py and regenerate "
        f"(`uv run python tools/differential/build_cjk_corpus.py`), or "
        f"take the example out of the doc")

    # The negative control, run rather than described: the doc with
    # one extra example on the tolerated rule -- a text no case row
    # produces -- and the same question asked again. It must find it.
    # Without this, a subtraction that quietly emptied `demoted` would
    # leave the assertion above green forever.
    probe = "조, 은우"
    assert probe not in _CORPUS_NAMES, (
        f"{probe!r} was chosen because no corpus holds it; a row was "
        f"added for it, so pick another string for the injection")
    lines = doc.splitlines()
    # Anchored on the marker line, not on one of the rule's example
    # texts: W3's first example is a text W1 also carries, so a search
    # by text lands in W1's block and injects a NORMATIVE example --
    # which the subtraction then removes, and the control passes by
    # doing nothing. The marker is in the tolerated rule's block by
    # definition.
    at = next(i for i, line in enumerate(lines)
              if re.match(r"^\s*tolerated:", line))
    lines.insert(at, f'      "{probe}"  →  family="조"')
    injected = _tolerated_only_texts(parse_rules_doc("\n".join(lines)))
    assert sorted(injected - set(_CORPUS_NAMES)) == [probe]


def _corpus_texts(filename: str) -> set[str]:
    """One corpus file's names, in whichever line format it uses."""
    return {_entry_name(json.loads(line)) for line in
            (_TOOLS / filename).read_text(encoding="utf-8").splitlines()
            if line.strip()}


def test_the_tolerated_corpus_is_disjoint_from_the_contract_ones() -> None:
    """No text is in corpus_cjk_tolerated.jsonl and in a CONTRACT
    corpus at the same time.

    Overlap does not error anywhere -- it reads as a demotion that did
    not happen. compare.py's dedup loads contract files first and
    keeps the contract reading, so a text both tiers hold is still
    enforced: an unmatched diff on it fails the run, exactly as before
    the flag was set. Meanwhile everything that describes it says
    otherwise -- the case row says `tolerated`, README's tier table
    says radar, the release notes group it as watched-not-enforced.
    The name is enforced and documented as demoted, which is the one
    combination nobody is reading for.

    _CORPUS_TIERS's own comment states the rule this asserts: a file
    entry demotes the file, and a text some contract corpus also holds
    reads contract no matter what the entry says. Five texts did on
    the day the file was created; the same day's rules.md edits took
    all five out of corpus_rules.jsonl. This keeps that true instead
    of leaving it a fact about one afternoon.

    Either resolution is deliberate and neither is this test's to
    pick: clear the `tolerated` flag (the name was never demoted), or
    take the text out of the contract corpus that still holds it (it
    was). The tier list is read from compare.py rather than copied,
    so a new contract corpus is covered by existing here, not by
    someone remembering to add it.
    """
    tiers = load_tool("compare")._CORPUS_TIERS
    contract = sorted(name for name, tier in tiers.items()
                      if tier == "contract")
    assert len(contract) >= 3, (
        f"_CORPUS_TIERS lists {contract} as contract; corpus_cjk, "
        f"corpus_rules and corpus_shapes have been contract since the "
        f"#468 tier split. A shorter list means this guard is asking "
        f"about fewer files than it reads as")
    demoted = _corpus_texts("corpus_cjk_tolerated.jsonl")
    assert demoted, "corpus_cjk_tolerated.jsonl is empty"
    for filename in contract:
        overlap = sorted(demoted & _corpus_texts(filename))
        assert not overlap, (
            f"{filename} (contract) and corpus_cjk_tolerated.jsonl "
            f"(radar) both hold {overlap}. compare.py's dedup keeps "
            f"the contract reading, so these names are still enforced "
            f"at released baselines while their case rows, the README "
            f"tier table and the release notes all call them demoted. "
            f"Clear the `tolerated` flag, or take the text out of "
            f"{filename}")


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
#: markers at once and "geb\.?" one -- so there is no set to compare
#: against.
#:
#: `covers` is recorded rather than equated to the whole vocabulary.
#: Equality would force a rule to grow alternatives for markers it has
#: no reason to claim -- see the note on fix(#274) in the 1.4 ledger for
#: why 旧姓 in particular is not one of them. Recording still catches
#: removal: drop an entry a member covers and the snapshot shrinks.
#:
#: Three nearby counts differ and are easy to conflate, all for
#: fix(#274) specifically, and every one of them moved in 2.2 -- twice,
#: so recount rather than adjust them: MAIDEN_MARKERS ships 17 entries
#: (roz left the vocabulary, z domu joined it); that rule's members
#: reach 3 of them; the corpora contain 5 markers in total (geb, nee,
#: née, z domu, 旧姓 -- nee arrived with #414's rules corpus and z domu
#: with #434's examples), 3 of which it covers. Counting z domu at all
#: needs the RUN reading _carries uses: it is two tokens, and a
#: per-token count cannot see it.
_LATIN_ALTERNATION_SOURCES: dict[str, _LatinCopy] = {
    "fix(#274)": _LatinCopy(
        vocabulary=MAIDEN_MARKERS,
        covers=frozenset({"geb", "nee", "née"})),
    "ambiguous-surname-acronym": _LatinCopy(
        vocabulary=SUFFIX_ACRONYMS_AMBIGUOUS,
        covers=frozenset({"do", "ma"})),
    # fix(#412) copies CONJUNCTIONS partly on purpose: the two
    # connectives the corpus names carry beside a marker. The rule
    # names the join-swallow shape, not the vocabulary.
    "fix(#412)": _LatinCopy(
        vocabulary=CONJUNCTIONS,
        covers=frozenset({"and", "y"})),
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
    # The title half of the #367 rule, widened when three more titled
    # names arrived (#413). Partial on purpose: these are the spellings
    # that appear before `van` in the corpora, not every title that
    # could -- the other titles before a particle in the corpora either
    # have rules of their own or do not diff. 'jr' was a member until #296's audit took
    # it out of TITLES (a postnominal only); 'Jr. Van Johnson' reads the
    # same by the period-abbreviation inference and has its literal.
    "fix(#367) a title no longer displaces a leading particle out of the leading position":
        _LatinCopy(vocabulary=TITLES,
                   covers=frozenset({"mr", "dr", "sir"})),
    "fix(#399)": _LatinCopy(
        vocabulary=PARTICLES,
        covers=frozenset({"de", "del", "den", "der", "di", "do", "dos",
                          "du", "la", "le", "los", "mc", "van", "vd",
                          "von", "zu"})),
    "fix(N3) a nickname-led name with a trailing suffix keeps the suffix in `suffix`":
        _LatinCopy(vocabulary=SUFFIX_WORDS,
                   covers=frozenset({"jr", "sr", "ii", "iii", "iv", "v"})),
    # #451's credential-acronym rule, one of the four that replaced the
    # fields-only fix(suffix-routing) catch-all. Two members, because
    # 'Donald mc' and 'QC MP' are the two corpus names in that shape;
    # partial for fix(#379)'s reason, SUFFIX_ACRONYMS running to
    # hundreds of entries that nobody writes after a bare name word.
    #
    # This is the roster entry behind one of #451's three splits, and
    # it forces that split only GIVEN THE ROSTER AS WRITTEN: the
    # sibling rule's `jr` is a SUFFIX_WORDS entry, _LatinCopy carries
    # exactly one `vocabulary`, and the test below asserts exactly one
    # roster key per alternation -- so an alternation spanning both
    # vocabularies cannot be pinned against either AS DECLARED HERE.
    # `vocabulary` is a hand-supplied frozenset, though: declaring
    # SUFFIX_WORDS | SUFFIX_ACRONYMS would let `(jr\.?|v|mp|mc)` pass
    # the member checks, measured. Declining to write a union is a
    # judgement -- an alternation should name one wordlist a reader can
    # go and check -- and decisions.md records it as one rather than as
    # a constraint. An earlier version of this comment said FORCED
    # flatly and was walked back (#452 review).
    "fix(suffix-routing) a two-token name ending in a credential acronym keeps it in `suffix`":
        _LatinCopy(vocabulary=SUFFIX_ACRONYMS,
                   covers=frozenset({"mc", "mp"})),
    # #484's per-word rules copy one vocabulary EACH, which is why the
    # 98 names take three rules: the roster keys a rule to a single
    # source. B1 is case-sensitive on purpose (its comment says why),
    # so both spellings of `and` are members and cover one entry.
    "a connective run initials": _LatinCopy(
        vocabulary=CONJUNCTIONS,
        covers=frozenset({"y", "e", "&", "and", "of", "the"})),
    "a bound-given run initials": _LatinCopy(
        vocabulary=BOUND_GIVEN_NAMES,
        covers=frozenset({"abdul", "abu"})),
    # Three entries, not the five the chain names: this roster keys ONE
    # vocabulary per rule, and the rule's first draft carried a second
    # alternation (`(?:\s+(?:der|la))?`) that this test would have had
    # to pin against the same entry. It could not: `covers` is one set,
    # and the two alternations cover disjoint halves of it. The draft
    # group was inert -- same 107 names, same digest, with and without
    # it -- so the ledger dropped it rather than the roster growing a
    # second shape. The rule's comment records the measurement.
    "a particle chain inside": _LatinCopy(
        vocabulary=PARTICLES,
        covers=frozenset({"van", "von", "de"})),
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
    # fix(#371)'s alternation holds the TAILS of the four corpus names
    # that carry a leading 'Ph. D.' -- three tails plus the bare stem
    # on the `?`. A list of names, not a copy of any wordlist. And the
    # pair the rule turns on is not vocabulary at all: _vocab.PH and
    # _vocab.D are fixed regexes, so there is no wordlist here for the
    # alternation to drift from.
    frozenset({" John Smith", " Van Johnson", ", Jr\\."}),
    # fix(#445)'s movers, one corpus name per alternative -- a list of
    # names, not a copy of any wordlist, so there is no vocabulary for
    # it to drift from. Two sets because the ledgers group the nine
    # movers differently. At 1.4.0 seven of them move the same four
    # fields and share the first set; the eighth ('John née Jones
    # Smith Ma') moves those plus `suffix`, and the ninth ('Smith
    # (née Jones)') keeps the rule it already had. At 2.0.0/2.1.0 the
    # second set holds the ones that move two fields: the first set
    # less the two compounds it drops -- with #412 and with #424, each
    # with a rule of its own -- plus that acronym name, whose acronym
    # is no part of the diff at those baselines. Read the composition
    # off the two literals below rather than off a count here.
    #
    # Spelled out rather than written as the shape -- one word, then a
    # marker -- because that shape also matches rules.md#M4's two
    # carve-outs, 'abd née Jones' and 'J. née Jones Smith V'. A rule
    # covering those two while declaring `given` would stand ready to
    # explain the very given -> family move they exist to prevent,
    # which is the absorption these rosters exist to catch.
    frozenset({"Janey n[ée]e Jones", "Jane n[ée]e Jones J\\. V",
               "Jane n[ée]e Jones Smith", "Jane n[ée]e and Jones Smith",
               "John n[ée]e Jones Smith V", "Smith n[ée]e Jones",
               "Smith n[ée]e Jones PhD"}),
    frozenset({"Janey n[ée]e Jones", "Jane n[ée]e Jones J\\. V",
               "Jane n[ée]e Jones Smith", "John n[ée]e Jones Smith Ma",
               "Smith n[ée]e Jones", "Smith n[ée]e Jones PhD"}),
    # #451's roman-numeral rule copies _ROMAN -- the pattern in
    # nameparser/_pipeline/_vocab.py that _vocab.is_trailing_numeral_suffix
    # matches a final piece against -- and NOT a wordlist. There is no
    # vocabulary here to drift from: 'x' is in none of SUFFIX_WORDS,
    # SUFFIX_ACRONYMS or their ambiguous subsets, and 'Mohamad X' moves
    # to `suffix` all the same, which is the whole reason the rule
    # cannot be an entry in _LATIN_ALTERNATION_SOURCES.
    #
    # The members are _ROMAN's body with the EMPTY alternative removed
    # (I{0,3} -> I{1,3}, plus the bare V that would otherwise be lost).
    # Measured over every string of length 1..4 from IVXivx, the two
    # accept the same strings apart from the empty one. Nothing pins
    # the ledger's copy against _ROMAN: test_regex_sync pins _ROMAN
    # against _config.REGEXES["roman_numeral"], which is the parser's
    # two copies of it, and a hand copy in a toml is outside that pair.
    # What holds this one is _CORPUS_CLAIMS' reach and digest plus the
    # _MUST_NOT_MATCH probes, the same wall every other literal rule
    # here stands behind. This roster records only that a wordlist is
    # not what is copied.
    frozenset({"X", "IX", "IV", "V?I{1,3}", "V"}),
    # #484: the anchor groups of the `_initials` rules -- start-of-name
    # or whitespace, start-of-name or whitespace-or-comma. Anchors, not
    # words; the same reason as fix(#400)'s pair above.
    frozenset({"^", "\\s"}),
    frozenset({"^", "[\\s,]"}),
    # fix(#385/#402)'s 24 spellings: the 27 corpus names whose
    # all-particle part moved, listed because "a part of nothing but
    # particles" is not a property a regex over the raw string can
    # state. A list of names, the fix(#445) precedent -- that rule and
    # fix(#410) and fix(#335) are the 1.4.0 ledger's literal lists.
    frozenset({"anh do", "smith van der", "yin le", "yin a le", "vai la",
               "jong van der", "jong, van der", "juan van der",
               "mesnil garcia de", "mesnil garcia van", "mesnil de",
               "sander van", "van ma van", "anh van do",
               "beethoven ludwig van", "berg jan de jr\\.", "john van mc",
               "jong anke de", "juan de", "ménil christophe de",
               "ménil de", "nguyen thi van", "nguyen, van le",
               "van berg jan de"}),
    # fix(#462)'s letter shape: a bare capital E/Y or a dotted E./Y.
    # It is the initial SHAPE (v1's `initial` regex, _render._INITIAL)
    # intersected with the single-letter conjunctions, not a copy of
    # CONJUNCTIONS -- "e." is no entry, and matching it against the
    # vocabulary would be a false claim of correspondence.
    frozenset({"[EY]", "[EeYy]\\."}),
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
    probe strings, and the tuple WAS DEFEATED by a wider rule than the
    one it was added to stop: every entry fix(#274) needs is three
    characters (`geb`, `nee`, `née`), so a member must accept some
    3-character string and is unconstrained everywhere else --
    "[acdf-uw-z]{3,}" covers `roz`, dodged all eight probes, and as a
    fourth alternative reached most of the corpus, far past what the
    rule carrying it claimed. The figures that stood here were taken
    against a corpus of 751 names and are not restated: the corpus has
    since grown by half, the eight-string tuple this replaced is gone,
    and the finding is the SHAPE -- a member unconstrained outside one
    3-character window walks past every probe anyone hand-picks --
    which is what the paragraph below acts on and which no count
    strengthens. If a number is wanted, drive the member over
    _CORPUS_NAMES with the IGNORECASE this function applies; the
    case-sensitive figure is smaller and is not what runs. Counts here
    and below are against _CORPUS_NAMES, which deduplicates the corpus
    lines rather than counting them.

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

    Note what the isascii() split actually covers: EVERY non-ASCII
    entry, not only the CJK one -- the great majority of
    MAIDEN_MARKERS, and the predicate below is the enumeration, so
    read it there rather than from a count here, which said 12 of 16
    while the vocabulary shipped 17. `né` is two characters, so the
    substring branch reads `René` as carrying a marker. Every
    over-match here SHRINKS the set of unexplained names and so
    weakens the guard -- the direction this module exists to close --
    but only two corpus names DEPEND on that branch today, meaning the
    token test below says no and the substring test says yes, and both
    are 旧姓 ones: the fullwidth-bracketed clause and the
    fullwidth-colon spelling. Eight depended on it before the
    delimiter strip below arrived (2026-08-26); that strip moved the
    parenthesized née names onto the token branch, where the answer
    does not rest on a substring. Both figures quantify over the
    corpus and go stale on any row added to it, so recount rather than
    adjust:
    The body must sit flush left: `python -c` compiles it as a module,
    so an indented first line raises IndentationError on paste.

uv run python -c "
import glob, json
from nameparser import DEFAULT_NICKNAME_DELIMITERS as D
from nameparser.config.maiden_markers import MAIDEN_MARKERS as V
from nameparser._lexicon import _normalize
def _n(x): return x if isinstance(x, str) else x['name']
names = {_n(json.loads(l)) for f in glob.glob('tools/differential/corpus*.jsonl') for l in open(f, encoding='utf-8') if l.strip()}
strip = ''.join({c for p in D for c in p})
sub = lambda n: any(e in n for e in V if not e.isascii())
print(sum(not {_normalize(t.strip(strip)) for t in n.split()} & V and sub(n) for n in names),
      sum(not {_normalize(t) for t in n.split()} & V and sub(n) for n in names))"
    Tighten this before admitting a vocabulary whose short non-ASCII
    entries occur inside ordinary names.

    Delimiter characters come off the token before the membership
    test, because a marker glued to a bracket is still a marker to the
    parser: rules.md#M3 reads '(geb. Schmidt)' as a maiden clause on
    the strength of that very word, and _normalize strips the
    abbreviating period but not the paren, so 'Anna Müller (geb.
    Schmidt)' read as carrying no maiden vocabulary at all. This
    direction is the safe one -- an unstripped token cannot be a
    vocabulary entry, so the strip only ever finds markers that are
    really there, and the names it rescues are exactly the ones a
    maiden rule may legitimately claim.
    """
    delimiters = "".join({ch for pair in DEFAULT_NICKNAME_DELIMITERS
                          for ch in pair})
    tokens = [_normalize(token.strip(delimiters)) for token in name.split()]
    # A vocabulary may hold PHRASE entries ('z domu'), which no set of
    # single tokens can contain: 'Maria Kowalska z domu Nowak' carries
    # a marker and not one of its words is one. So the membership test
    # runs over every consecutive token RUN up to the longest entry --
    # which is the single tokens themselves when no entry is a phrase,
    # leaving every count above unchanged. Still textual and still
    # wider than the parser (no longest-first, no fold-away rule):
    # tools/differential/README.md says that is this helper's job.
    longest = max((entry.count(" ") + 1 for entry in vocabulary), default=1)
    runs = {" ".join(tokens[i:i + n])
            for n in range(1, longest + 1)
            for i in range(len(tokens) - n + 1)}
    return bool(runs & vocabulary) or any(
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
    #: corpus names the name_regex reaches. The whole corpus when a
    #: rule has none -- a shape validate_rules REJECTED in #451, so no
    #: ledger can carry one now; the fallback stays because this
    #: module reads ledgers without validating them first
    names: int
    #: the roles it narrows by, sorted; () when it narrows by regex alone
    roles: tuple[str, ...]
    #: sha256[:12] of the claimed names, so a swap that holds the count
    #: still fails. Unreadable by design -- the count above is what a
    #: reviewer reads, and the failure message prints what moved.
    digest: str
    #: the comparison orders it narrows by, sorted; None when it carries
    #: no `orders` key at all. The three above are all blind to the
    #: third narrowing: deleting `orders` from a shipped rule widens it
    #: to every order while its regex reaches the same names, narrows by
    #: the same roles, and digests identically. No default, so a new
    #: entry has to state which one it is.
    orders: tuple[str, ...] | None


def _claim(rule: dict) -> _Claim:
    regex = rule.get("name_regex")
    names = (_claimed(regex) if isinstance(regex, str) else list(_CORPUS_NAMES))
    fields = rule.get("fields")
    orders = rule.get("orders")
    return _Claim(
        names=len(names),
        roles=tuple(sorted(fields)) if isinstance(fields, list) else (),
        digest=hashlib.sha256(
            "\n".join(names).encode("utf-8")).hexdigest()[:12],
        orders=tuple(sorted(orders)) if isinstance(orders, list) else None)


#: How many corpus names each rule's name_regex matches, per ledger.
#:
#: The backstop the other guards each failed to be. Every one of them
#: is scoped to a CATEGORY -- a span class, an alternation's members, a
#: `maiden` field, a member's reach -- and five review rounds each found
#: a rule outside whichever category the last fix had covered. The
#: categories are the test's, not the ledger's. What every rule shares
#: is what it claims: how much corpus its regex reaches, which roles
#: it narrows by, which comparison ORDERS it admits, and WHICH names
#: those are. The orders entry closes a widening none of the other
#: three can see: deleting `orders` from a shipped rule returns it to
#: claiming every order while its reach, its roles and its digest all
#: stand still. Scoped to the corpus --
#: and only there -- a widening cannot change what a rule explains
#: without moving one of the four. Restoring 'born' moves none of
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
#: Seventeen of these moved at once when corpus_rules.jsonl landed
#: (#414) and fourteen more were added, which is a lot of re-recording
#: to review. The figure read "Twenty" until #452 measured it: parse
#: this roster out of `7a10689^` and `7a10689` with ast and diff the
#: per-entry dumps -- 30 entries before, 44 after, 17 changed. The same
#: three ways (that commit, the whole of PR #415, the backtick-harvest
#: commit after it) all give 17. The jumps are all
#: one cause -- 113 names arriving -- and the ones worth naming are
#: the broad rules: the fields-only catch-alls grew to the whole
#: corpus (751 -> 864), the comma rules 215 -> 236, fix(#274) 4 -> 11
#: and fix(#379) 2 -> 8. What made each jump reviewable was not this
#: record but the two guards beside it: the vocabulary-presence guard
#: rejected fix(#274)'s first grown reach outright, and the
#: member-reach guard rejected the acronym rule's. A jump that passes
#: both is growth into names the rule genuinely describes.
_CORPUS_CLAIMS: dict[str, dict[str, _Claim]] = {
    "expected_since_1.4.0.toml": {
        "fix(A2) content-free input names nobody, so every role empties":
            _Claim(5, ('given',), "1af8d718688b", None),
        "fix(#335) a marker-led clause leaves the one name word its bare reading":
            _Claim(1, ('maiden', 'nickname'), "c09cc7dba88b", None),
        "fix(#434) a multi-word maiden marker takes the maiden name":
            _Claim(1, ('family', 'maiden', 'middle'), "c428798fc6ef", None),
        "fix(#434) a multi-word marker leads a bracketed clause to the maiden name":
            _Claim(1, ('maiden', 'nickname'), "0b3ef183f283", None),
        "fix(#335) a marker-led bracketed clause reads as the maiden name whatever pair encloses it":
            _Claim(5, ('maiden', 'nickname'), "a419f74143e3", None),
        "fix(#410) a title and one name word name the family, whatever annotation stands beside it":
            _Claim(3, ('family', 'given'), "24d6223e472f", None),
        "fix(#410) the maiden flavor, where 1.4.0 read the marker as a middle name":
            _Claim(1, ('family', 'given', 'maiden', 'middle'), "309e39fc2475", None),
        "fix(#432) a dotted numeral behind a name is a middle initial, not the generation":
            _Claim(1, ('middle', 'suffix'), "e9f282da0d0f", None),
        "fix(#271/#272/#298) native-script CJK: family-first order, hangul segmentation, the kana license and the dots":
            _Claim(108, ('family', 'given', 'middle'), "9a814f70c2dc", None),
        "fix(#274) maiden markers consumed":
            _Claim(32, ('family', 'maiden', 'middle'), "06d199ceb249", None),
        "fix(cjk-maiden-marker) maiden marker consumed, compounding with the CJK order flip":
            _Claim(5, ('family', 'given', 'maiden', 'middle'), "bc0e10dd7ec8", None),
        "fix(#379) a tussenvoegsel after a family comma attaches to the family":
            _Claim(13, ('family', 'middle'), "973617235cda", None),
        "fix(#380) a trailing vd after a family comma is the tussenvoegsel, not a post-nominal":
            _Claim(2, ('family', 'suffix'), "ec0d45289dc1", None),
        # 279 -> 280 with #371, and the growth is corpus, not behavior:
        # that PR added `Ph. D., John` as a rules.md example, so the
        # regex matches one more corpus name. The name does not diff at
        # this baseline (v1 and HEAD both read first 'John', last
        # 'Ph. D.'), so nothing was absorbed.
        #
        # 284 -> 286 with the shape 1-3 variation matrix (#486), and
        # the growth is corpus again: 'Smith, John Jr.' and
        # 'Smith, John, Extra, Jr.' were case-table rows in no corpus
        # until their shape tags put them in corpus_shapes.jsonl. Both
        # are parity rows, so neither diffs at this baseline and this
        # rule absorbs nothing new -- the same reach-not-behavior
        # growth the paragraph above records, from the other source.
        # It moves this rule and fix(comma-precomma-family) below by
        # the same two names, both matching on the bare comma. 286 ->
        # 288 in the commit after it, for the two comma-bearing rows
        # #486 had to AUTHOR -- 'John Smith Jr., PhD' and
        # 'Kennedy, John (Jack)' -- and neither diffs at this baseline
        # either, so all four names are reach without absorption.
        "fix(comma-family) lone post-comma piece routes to suffix/title, not first":
            _Claim(288, ('given', 'suffix', 'title'), "10c78dd0f2d2", None),
        "fix(comma-family) a comma followed only by titles keeps the given/family split":
            _Claim(2, ('family', 'given'), "5bd9c6d96c38", None),
        "fix(comma-family) a comma followed only by titles keeps the given/family split, the C1 example":
            _Claim(2, ('family', 'given', 'suffix'), "a3cfff4e78f4", None),
        "fix(#296) a dropped prenominal takes the name position it occupies":
            _Claim(3, ('given', 'middle', 'title'), "263d5957cfc1", None),
        "fix(#296) dr is not postnominal vocabulary, so a trailing Dr. is a name word":
            _Claim(11, ('family', 'middle', 'suffix'), "b9cfc0d88bf6", None),
        "fix(#296) a credential-only comma string reads a name and its postnominal":
            _Claim(2, ('family', 'given', 'suffix', 'title'), "3f983ff71dee", None),
        "fix(#296) a lone post-comma credential is a suffix":
            _Claim(18, ('family', 'given', 'suffix', 'title'), "1f79efa10444", None),
        "fix(#325) a split credential followed by another suffix after a one-word family comma reads as suffixes":
            _Claim(6, ('given', 'suffix', 'title'), "7911e0158337", None),
        "fix(#325) a credential run across a second comma reads as suffixes":
            _Claim(1, ('suffix', 'title'), "f025c5f70a4e", None),
        "fix(#367) an inferred title no longer displaces a leading particle either":
            _Claim(1, ('family', 'given'), "d8ee9cd5da5f", None),
        "fix(comma-precomma-family) pre-comma run reads as family, not given":
            _Claim(288, ('family', 'given'), "10c78dd0f2d2", None),
        "fix(#342) NOT WANTED: a bare trailing 'Rai' is read as a post-nominal suffix and the family is lost":
            _Claim(1, ('family', 'suffix'), "694fd06a2e9a", None),
        "fix(#397) NOT WANTED: a trailing Catalan/Polish linking 'i' is read as a generation marker and the family is lost":
            _Claim(1, ('family', 'suffix'), "498602f3cfd0", None),
        "fix(suffix-delimiter-rendering) no-space delimiter core token kept whole":
            _Claim(0, ('suffix',), "e3b0c44298fc", None),
        "ambiguous-surname-acronym data change: parenthesized (MA)/(DO) now stays nickname":
            _Claim(0, ('nickname', 'suffix'), "e3b0c44298fc", None),
        "feat(#269) Arabic بن prefix chains onto family (non-Latin new-recognition)":
            _Claim(2, ('family', 'middle'), "3e2b5c6d1f4d", None),
        "feat(#273) typographic nickname delimiters recognized by default":
            _Claim(8, ('middle', 'nickname'), "968bd4162257", None),
        "fix(cjk-delimited-nickname) delimiter recognition compounds with the CJK order flip":
            _Claim(6, ('family', 'given', 'nickname'), "ae1dffa01608", None),
        "fix(cjk-fullwidth-paren-nickname) fullwidth-parenthesis recognition compounds with the CJK order flip":
            _Claim(1, ('family', 'given', 'middle', 'nickname'), "cf370e856ae7", None),
        "fix(cjk-comma-honorific-peel) glued honorific peels off a post-comma given name":
            _Claim(23, ('given', 'suffix'), "344de804e2c6", None),
        "fix(cjk-comma-compound) comma routing compounds with the CJK order flip":
            _Claim(23, ('family', 'given', 'suffix', 'title'), "344de804e2c6", None),
        "fix(cjk-glued-honorific-peel) glued honorific peels into suffix":
            _Claim(37, ('family', 'given', 'suffix'), "719c31233502", None),
        "fix(cjk-honorific-suffix) postnominal honorifics recognized, compounding with the CJK order flip":
            _Claim(19, ('family', 'given', 'middle', 'suffix'), "aa475ddd4745", None),
        "feat(#269) non-Latin titles/conjunctions recognized":
            _Claim(4, ('given', 'middle', 'title'), "e86eeb13eeb2", None),
        "fix(#424) an unlisted abbreviation is as transparent as a listed title to the leading particle":
            _Claim(1, ('family', 'given'), "ca7b37af6cf8", None),
        "fix(#367) a title no longer displaces a leading particle out of the leading position":
            _Claim(3, ('family', 'given'), "724967a4a117", None),
        "fix(#400) abd joins the word after it as one given name":
            _Claim(11, ('given', 'middle'), "1eaed91fc574", None),
        "fix(#272/#308) nakaguro division and a glued hangul honorific in one name":
            _Claim(1, ('family', 'given', 'middle', 'suffix'), "2fbf1a94f122", None),
        "fix(emoji-boundary) an emoji inside a token divides it":
            _Claim(1, ('family', 'given'), "efa60ca42d4a", None),
        "fix(nickname-typographic-pairs) two typographic quote spans read as one nickname set":
            _Claim(1, ('family', 'given', 'middle', 'nickname'), "3cf566c78800", None),
        "fix(#411) the bound-given reserve stops counting words the maiden name takes":
            _Claim(1, ('given', 'maiden', 'middle'), "7515923c9613", None),
        "fix(#400/#274) bound-given join and maiden consumption in one name":
            _Claim(1, ('family', 'given', 'maiden', 'middle'), "6bed6d349342", None),
        "fix(#411/S2) a declining bound-given join leaves the suffix reading after a family comma":
            _Claim(1, ('given', 'maiden', 'middle', 'suffix'), "0f8ed9db0a32", None),
        "fix(#418) the connective carve-out counts the name the maiden clause leaves behind":
            _Claim(1, ('family', 'given', 'maiden', 'middle'), "7923e6d3c5a7", None),
        "fix(credential-pair-order) a split credential and a suffix render in written order":
            _Claim(1, ('suffix',), "6f6eef764248", None),
        "fix(#369) a given-name title licenses the bound given-name join with one word to spare":
            _Claim(3, ('family', 'given'), "724be3e6b926", None),
        "fix(#401) the bound-given reserve counts the trailing numeral assign reads as the suffix":
            _Claim(2, ('family', 'given', 'suffix'), "5713d4c0bd68", None),
        "fix(#421) the bound-given join never absorbs a suffix piece":
            _Claim(1, ('given', 'middle'), "9523e518e6ec", None),
        "fix(#421) the bound-given join never absorbs a split credential":
            _Claim(1, ('given', 'middle'), "228abe0f32ef", None),
        "fix(#425) accepted: a bare ambiguous acronym the peel does not take joins as a name word":
            _Claim(1, ('given', 'middle'), "2010cc79a34d", None),
        "fix(#424) the particle chain stops before the trailing numeral":
            _Claim(1, ('family', 'suffix'), "2c99162bc9cf", None),
        "fix(#424/#445) accepted: the maiden walk keeps a bare acronym, and the lone name word is the family":
            _Claim(1, ('family', 'given', 'maiden', 'middle', 'suffix'), "f2c6cd2e3001", None),
        "fix(#424) an unlisted abbreviation is as transparent as a listed title to the leading particle, the P4 example":
            _Claim(1, ('family', 'given'), "42b69cf1b320", None),
        "fix(#424) accepted: the maiden walk keeps the numeral an initial before the marker vetoes":
            _Claim(1, ('family', 'maiden', 'middle', 'suffix'), "08c0158c8d3f", None),
        "fix(#424) accepted: the chain keeps an acronym assign will not peel behind a title-and-particle word":
            _Claim(1, ('family', 'given'), "faa4bedda537", None),
        "fix(#424) a title-led chain before the numeral is the one name piece":
            _Claim(1, ('family', 'suffix'), "5b3a743f9e35", None),
        "fix(#424) accepted: a particle of the suffix vocabulary opening the trailing run is a suffix piece":
            _Claim(1, ('family', 'middle', 'suffix'), "a564b97f7162", None),
        "fix(#360) ste moved into the never-given particles with mc":
            _Claim(1, ('family', 'given'), "e62caedec864", None),
        "fix(#360) mc moved into the never-given particles, so it folds into the family":
            _Claim(1, ('family', 'given'), "ee4339908f4d", None),
        "fix(#367) a title no longer displaces a leading never-given particle":
            _Claim(1, ('family', 'given'), "db724fb9c779", None),
        "fix(#445) a maiden marker makes the lone name word the family":
            _Claim(7, ('family', 'given', 'maiden', 'middle'), "3de9ef12b4a8", None),
        "fix(N3) a nickname-led name with a trailing suffix keeps the suffix in `suffix`":
            _Claim(1, ('family', 'suffix'), "570f265a2f46", None),
        # #451's four replacements for the fields-only catch-all, whose
        # own entry recorded the whole 1090-name corpus -- a rule with no
        # name_regex reaches everything, so its reach could never move and
        # this roster could not see names arrive on it. The numeral and jr
        # rules reach more names than they explain, and rules above them
        # take the surplus, which is why the four are last in the file;
        # the acronym and M.A. rules reach exactly what they explain.
        "fix(suffix-routing) a two-token name ending in a roman numeral keeps it in `suffix`":
            _Claim(4, ('family', 'suffix'), "fc52089dfa8e", None),
        "fix(suffix-routing) a two-token name ending in the suffix word jr keeps it in `suffix`":
            _Claim(5, ('family', 'suffix'), "602e2d83a23b", None),
        "fix(suffix-routing) a two-token name ending in a credential acronym keeps it in `suffix`":
            _Claim(2, ('family', 'suffix'), "ed72c9672214", None),
        "fix(suffix-routing) the dotted M.A. spelling reads as a credential (ma-do)":
            _Claim(1, ('family', 'suffix'), "17379620526b", None),
        # #484's six `_initials` rules. Four of them reach far more
        # than they explain, and the gap is the pseudo-field's own
        # doing rather than a widening: `_initials` enters a diff ONLY
        # when the seven roles and the ambiguity kinds all agree, so a
        # name whose regex the rule matches contributes nothing unless
        # its parse is otherwise identical across the two surfaces.
        # Reach against explained, measured 2026-09-02 at baseline
        # 1.4.0 -- a snapshot of that run, not a standing count:
        # 27/27, 1/1, 96/66, 41/19, 107/11, 18/2. The reach half is
        # what this roster holds; the explained half moves with the
        # corpus and is re-read from the gate. The phd rule's 18 is the widest
        # gap and the most literal regex -- `\bph\. d\.` matches every
        # spelling of the fragment the corpora carry, and the trailing
        # ones are protected by the [[never]] entry above, which is
        # what _EXCLUSION_EFFECT's grown `absorbed_by` records.
        "fix(#385/#402) an all-particle name part initials its words (R2)":
            _Claim(27, ('_initials',), "6b242c287db8", ('DEFAULT',)),
        "fix(#360) los joined the particles, so it no longer initials":
            _Claim(1, ('_initials',), "cd721215f463", ('DEFAULT',)),
        "fix(initials-per-word) a connective run initials each word (facade, since 2.0.0)":
            _Claim(96, ('_initials',), "fa69850d2cd4", ('DEFAULT',)),
        "fix(initials-per-word) a bound-given run initials each word (facade, since 2.0.0)":
            _Claim(41, ('_initials',), "e99f56c955d5", ('DEFAULT',)),
        "fix(initials-per-word) a particle chain inside a name part initials each word (facade, since 2.0.0)":
            _Claim(107, ('_initials',), "bdc4da864f59", ('DEFAULT',)),
        "fix(initials-per-word) the Ph. D. merge initials each word (facade, since 2.0.0)":
            _Claim(18, ('_initials',), "f67d8ebddd56", ('DEFAULT',)),
    },
    "expected_since_2.0.0.toml": {
        "fix(#335) a marker-led clause leaves the one name word its bare reading":
            _Claim(1, ('maiden', 'nickname'), "c09cc7dba88b", None),
        "fix(#434) a multi-word maiden marker takes the maiden name":
            _Claim(1, ('family', 'maiden', 'middle'), "c428798fc6ef", None),
        "fix(#434) a multi-word marker leads a bracketed clause to the maiden name":
            _Claim(1, ('maiden', 'nickname'), "0b3ef183f283", None),
        "fix(#335) a marker-led bracketed clause reads as the maiden name whatever pair encloses it":
            _Claim(5, ('maiden', 'nickname'), "a419f74143e3", None),
        "fix(#335) a marker-led bracketed clause reads as the maiden name, compounding with the CJK order flip":
            _Claim(1, ('family', 'given', 'maiden', 'nickname'), "cf370e856ae7", None),
        "fix(#410) a title and one name word name the family, whatever annotation stands beside it":
            _Claim(4, ('family', 'given'), "da1dd1473145", None),
        "fix(#430) a credential run does not end at the roman numeral describing it":
            _Claim(2, ('given', 'suffix'), "3c8fa6bc827a", None),
        "fix(#432) a dotted numeral behind a name is a middle initial, not the generation":
            _Claim(1, ('middle', 'suffix'), "e9f282da0d0f", None),
        "fix(#429) a wholly-credential segment after a one-word family renders as one entry":
            _Claim(1, ('suffix', 'title'), "9e0b9e8d5cbe", None),
        "fix(#379) a tussenvoegsel after a family comma attaches to the family":
            _Claim(13, ('_ambiguities', 'family', 'middle'), "973617235cda", None),
        "fix(#271/#272/#298) native-script CJK: family-first order, hangul segmentation, the kana license and the dots":
            _Claim(108, ('_ambiguities', 'family', 'given', 'middle'), "9a814f70c2dc", None),
        "fix(#308/#312/#319/#320) glued CJK honorific peeled off the name into suffix":
            _Claim(37, ('family', 'given', 'suffix'), "719c31233502", None),
        "fix(#307/#308/#320) spaced CJK postnominal honorific routed to suffix":
            _Claim(16, ('family', 'given', 'middle', 'suffix'), "6d390e518bd2", None),
        "fix(#309) 旧姓 maiden marker consumed, compounding with the CJK order flip":
            _Claim(5, ('family', 'given', 'maiden', 'middle'), "bc0e10dd7ec8", None),
        "fix(#272) nakaguro inside delimited content renders as a space, compounding with the CJK order flip":
            _Claim(1, ('family', 'given', 'nickname'), "d4069d459f23", None),
        "fix(#298) 间隔号 division changes the comma reading, sending the credential from title to suffix":
            _Claim(1, ('family', 'given', 'suffix', 'title'), "1d45596e6fdb", None),
        "fix(#424) an unlisted abbreviation is as transparent as a listed title to the leading particle":
            _Claim(1, ('_ambiguities', 'family', 'given'), "ca7b37af6cf8", None),
        "fix(#367) a title no longer displaces a leading particle out of the leading position":
            _Claim(3, ('family', 'given'), "724967a4a117", None),
        "fix(#380) a trailing vd after a family comma is the tussenvoegsel, not a post-nominal":
            _Claim(2, ('_ambiguities', 'family', 'suffix'), "ec0d45289dc1", None),
        "fix(#399) a maiden marker bounds the particle chain that swallowed it":
            _Claim(6, ('family', 'maiden'), "89e1f4afdd2a", ('DEFAULT',)),
        "fix(#360) mc moved into the never-given particles, so it folds into the family":
            _Claim(1, ('_ambiguities', 'family', 'given'), "ee4339908f4d", None),
        "fix(#400) abd joins the word after it as one given name":
            _Claim(11, ('given', 'middle'), "1eaed91fc574", None),
        "fix(#367) a title no longer displaces a leading never-given particle":
            _Claim(1, ('family', 'given'), "db724fb9c779", None),
        "fix(#272/#308) nakaguro division and a glued hangul honorific in one name":
            _Claim(1, ('family', 'given', 'middle', 'suffix'), "2fbf1a94f122", None),
        "fix(#411) the bound-given reserve stops counting words the maiden name takes":
            _Claim(1, ('given', 'maiden', 'middle'), "7515923c9613", None),
        "fix(#412) a connective join no longer absorbs the maiden marker beside it":
            _Claim(2, ('family', 'maiden'), "51c0eb36b5c5", None),
        "fix(#418) the connective carve-out counts the name the maiden clause leaves behind":
            _Claim(1, ('family', 'given', 'middle'), "7923e6d3c5a7", None),
        "fix(#418) accepted: a suffix word inside the maiden name ends it, connective or not":
            _Claim(1, ('family', 'maiden', 'middle'), "bedc18423d2a", None),
        "fix(#369) a given-name title licenses the bound given-name join with one word to spare":
            _Claim(3, ('family', 'given'), "724be3e6b926", None),
        "fix(#401) the bound-given reserve counts the trailing numeral assign reads as the suffix":
            _Claim(2, ('family', 'given'), "5713d4c0bd68", None),
        "fix(#421) the bound-given join never absorbs a suffix piece":
            _Claim(1, ('given', 'middle'), "9523e518e6ec", None),
        "fix(#421) the bound-given join never absorbs a split credential":
            _Claim(1, ('given', 'middle', 'suffix'), "228abe0f32ef", None),
        "fix(#425) the bound-given reserve runs assign's peel over the joined view":
            _Claim(2, ('family', 'given', 'suffix'), "ef1ab03b617e", None),
        "fix(#424) the particle chain stops before the trailing numeral":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "2c99162bc9cf", None),
        "fix(#424) the particle chain stops before a bare acronym with words to spare":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "3e3aae6a5b4b", None),
        "fix(#424) a title-led chain before the numeral is the one name piece":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "5b3a743f9e35", None),
        "fix(comma-family) a comma followed only by titles keeps the given/family split":
            _Claim(2, ('family', 'given'), "5bd9c6d96c38", None),
        "fix(comma-family) a comma followed only by titles keeps the given/family split, the C1 example":
            _Claim(2, ('family', 'given'), "a3cfff4e78f4", None),
        "fix(#296) a dropped prenominal takes the name position it occupies":
            _Claim(3, ('_ambiguities', 'given', 'middle', 'title'), "263d5957cfc1", None),
        "fix(#296) dr is not postnominal vocabulary, so a trailing Dr. is a name word":
            _Claim(11, ('family', 'middle', 'suffix'), "b9cfc0d88bf6", None),
        "fix(#296) a credential-only comma string reads a name and its postnominal":
            _Claim(2, ('suffix', 'title'), "3f983ff71dee", None),
        "fix(#296) a lone post-comma credential is a suffix":
            _Claim(18, ('suffix', 'title'), "1f79efa10444", None),
        "fix(#325) a split credential followed by another suffix after a one-word family comma reads as suffixes":
            _Claim(6, ('given', 'suffix', 'title'), "7911e0158337", None),
        "fix(#325) a credential run across a second comma reads as suffixes":
            _Claim(1, ('suffix', 'title'), "f025c5f70a4e", None),
        "fix(#296) a glued honorific before a lone credential: the credential is the postnominal":
            _Claim(1, ('family', 'suffix', 'title'), "01bf2bd3f895", None),
        "fix(#296) do is a name, so it no longer stops the leading-particle scan as a title":
            _Claim(1, ('family', 'given'), "faa2c70fc49e", None),
        "fix(#296) dr is not postnominal vocabulary, so 'John Smith, Dr.' keeps its split and its title":
            _Claim(2, ('_ambiguities', 'suffix', 'title'), "34d3d96adb65", ('DEFAULT', 'FAMILY_FIRST')),
        "fix(#296) an ambiguous acronym counts as a suffix only when written with its periods":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "e13b3c769de4", None),
        "fix(#367) an inferred title no longer displaces a leading particle either":
            _Claim(1, ('family', 'given'), "d8ee9cd5da5f", None),
        "fix(#424) accepted: a particle of the suffix vocabulary opening the trailing run is a suffix piece":
            _Claim(1, ('_ambiguities', 'family', 'middle', 'suffix'), "a564b97f7162", None),
        "fix(#424) an unlisted abbreviation is as transparent as a listed title to the leading particle, the P4 example":
            _Claim(1, ('_ambiguities', 'family', 'given'), "42b69cf1b320", None),
        "fix(#424/#445) the maiden walk stops before the trailing numeral, and the lone name word is the family":
            _Claim(1, ('_ambiguities', 'family', 'given', 'maiden', 'suffix'), "cbe5bdd97317", None),
        "fix(#445) a maiden marker makes the lone name word the family":
            _Claim(6, ('family', 'given'), "f521c94c79fc", None),
        "fix(#445) the lone name word beside a marker a connective join no longer absorbs":
            _Claim(1, ('family', 'given', 'maiden', 'middle'), "52544a41dd62", None),
        "fix(#424) a marker followed only by the numeral is just a word":
            _Claim(1, ('_ambiguities', 'family', 'maiden', 'middle', 'suffix'), "aaf53040b071", None),
        "fix(#369) the bound given-name join takes a particle-and-bound word, so no fork is reported":
            _Claim(1, ('_ambiguities',), "81cf02ffdb33", None),
        "fix(#360) ste moved into the never-given particles with mc":
            _Claim(1, ('_ambiguities', 'family', 'given'), "e62caedec864", None),
        "fix(#399) a maiden marker bounds the particle chain: the geb. spelling":
            _Claim(1, ('family', 'maiden'), "2150936a8c55", None),
        "fix(#371) a suffix never begins a name: the Ph./D. merge declines at the head":
            _Claim(4, ('family', 'given', 'middle', 'suffix', 'title'), "1425d85a2d86", None),
        "feat(#395) a leading never-given particle bounds the family under a declared family-first order":
            _Claim(1, ('family', 'given', 'middle'), "47dcff268731", ('FAMILY_FIRST', 'FAMILY_FIRST_GIVEN_LAST')),
        "fix(#399)/feat(#395) a consumed maiden marker leaves the family-first fold no given name":
            _Claim(1, ('family', 'given', 'maiden'), "504eb466e347", ('FAMILY_FIRST', 'FAMILY_FIRST_GIVEN_LAST')),
        "feat(#395)/fix(#296) a comma followed only by a title leaves the pre-comma name to the declared order's fold":
            _Claim(1, ('family', 'given', 'middle', 'suffix', 'title'), "fc6bc9e605e1", ('FAMILY_FIRST',)),
        "feat(#395)/fix(#296) a comma followed only by a title leaves the pre-comma name to the declared order's fold, the given-last spelling":
            _Claim(1, ('family', 'given', 'middle', 'suffix', 'title'), "3e43a2be022e", ('FAMILY_FIRST_GIVEN_LAST',)),
        # #484's two `_initials` rules. Both are literal name lists, so
        # reach equals what they explain here -- 27 and 1 -- and both
        # digests match the 1.4.0 ledger's, which is the point of
        # copying the list verbatim rather than restating it.
        "fix(#385/#402) an all-particle name part initials its words (R2)":
            _Claim(27, ('_initials',), "6b242c287db8", ('DEFAULT',)),
        "fix(#360) los joined the particles, so it no longer initials":
            _Claim(1, ('_initials',), "cd721215f463", ('DEFAULT',)),
        # fix(#462) reaches more than it explains -- the reach is the
        # _Claim below, and the gap is the names named here. Its regex
        # is a letter SHAPE rather than a name list, and the extra --
        # 'E Anne D', 'E Jones', 'E Maria', 'Y. L.' -- carry the E/Y in
        # the GIVEN group, which has always initialed every word it
        # holds whatever the vocabulary says, so the fix does not move
        # them. The discriminator is the GROUP and not the position:
        # 'E Anne D,Leonardo' also leads with the E, but its comma
        # re-roles the whole run into the FAMILY group, and it moves.
        # The digest is the same in all three 2.x ledgers because the
        # regex is the same string in each.
        "fix(#462) the facade keeps an initial-shaped conjunction letter":
            _Claim(18, ('_initials',), "3dd0e0276be6", ('DEFAULT',)),
    },
    # The 2.3 cycle's first rule, and a facade-only render fix: every
    # role is identical, so `_initials` alone. Reach and digest as in
    # the 2.0.0 mapping above, the same regex classifying the same
    # names.
    "expected_since_2.2.0.toml": {
        "fix(#462) the facade keeps an initial-shaped conjunction letter":
            _Claim(18, ('_initials',), "3dd0e0276be6", ('DEFAULT',)),
    },
    "expected_since_2.1.0.toml": {
        "fix(#371) a suffix never begins a name: the Ph./D. merge declines at the head":
            _Claim(4, ('family', 'given', 'middle', 'suffix', 'title'), "1425d85a2d86", None),
        "fix(#335) a marker-led clause leaves the one name word its bare reading":
            _Claim(1, ('maiden', 'nickname'), "c09cc7dba88b", None),
        "fix(#434) a multi-word maiden marker takes the maiden name":
            _Claim(1, ('family', 'maiden', 'middle'), "c428798fc6ef", None),
        "fix(#434) a multi-word marker leads a bracketed clause to the maiden name":
            _Claim(1, ('maiden', 'nickname'), "0b3ef183f283", None),
        "fix(#335) a marker-led bracketed clause reads as the maiden name whatever pair encloses it":
            _Claim(6, ('maiden', 'nickname'), "d0e857deddb2", None),
        "fix(#410) a title and one name word name the family, whatever annotation stands beside it":
            _Claim(4, ('family', 'given'), "da1dd1473145", None),
        "fix(#430) a credential run does not end at the roman numeral describing it":
            _Claim(2, ('given', 'suffix'), "3c8fa6bc827a", None),
        "fix(#432) a dotted numeral behind a name is a middle initial, not the generation":
            _Claim(1, ('middle', 'suffix'), "e9f282da0d0f", None),
        "fix(#429) a wholly-credential segment after a one-word family renders as one entry":
            _Claim(1, ('suffix', 'title'), "9e0b9e8d5cbe", None),
        "fix(#379) a tussenvoegsel after a family comma attaches to the family":
            _Claim(13, ('_ambiguities', 'family', 'middle'), "973617235cda", None),
        "fix(#424) an unlisted abbreviation is as transparent as a listed title to the leading particle":
            _Claim(1, ('_ambiguities', 'family', 'given'), "ca7b37af6cf8", None),
        "fix(#367) a title no longer displaces a leading particle out of the leading position":
            _Claim(3, ('family', 'given'), "724967a4a117", None),
        "fix(#380) a trailing vd after a family comma is the tussenvoegsel, not a post-nominal":
            _Claim(2, ('_ambiguities', 'family', 'suffix'), "ec0d45289dc1", None),
        "fix(#399) a maiden marker bounds the particle chain that swallowed it":
            _Claim(6, ('family', 'maiden'), "89e1f4afdd2a", ('DEFAULT',)),
        "fix(#360) mc moved into the never-given particles, so it folds into the family":
            _Claim(1, ('_ambiguities', 'family', 'given'), "ee4339908f4d", None),
        "fix(#400) abd joins the word after it as one given name":
            _Claim(11, ('given', 'middle'), "1eaed91fc574", None),
        "fix(#367) a title no longer displaces a leading never-given particle":
            _Claim(1, ('family', 'given'), "db724fb9c779", None),
        "fix(#411) the bound-given reserve stops counting words the maiden name takes":
            _Claim(1, ('given', 'maiden', 'middle'), "7515923c9613", None),
        "fix(#412) a connective join no longer absorbs the maiden marker beside it":
            _Claim(2, ('family', 'maiden'), "51c0eb36b5c5", None),
        "fix(#418) the connective carve-out counts the name the maiden clause leaves behind":
            _Claim(1, ('family', 'given', 'middle'), "7923e6d3c5a7", None),
        "fix(#418) accepted: a suffix word inside the maiden name ends it, connective or not":
            _Claim(1, ('family', 'maiden', 'middle'), "bedc18423d2a", None),
        "fix(#369) a given-name title licenses the bound given-name join with one word to spare":
            _Claim(3, ('family', 'given'), "724be3e6b926", None),
        "fix(#401) the bound-given reserve counts the trailing numeral assign reads as the suffix":
            _Claim(2, ('family', 'given'), "5713d4c0bd68", None),
        "fix(#421) the bound-given join never absorbs a suffix piece":
            _Claim(1, ('given', 'middle'), "9523e518e6ec", None),
        "fix(#421) the bound-given join never absorbs a split credential":
            _Claim(1, ('given', 'middle', 'suffix'), "228abe0f32ef", None),
        "fix(#425) the bound-given reserve runs assign's peel over the joined view":
            _Claim(2, ('family', 'given', 'suffix'), "ef1ab03b617e", None),
        "fix(#424) the particle chain stops before the trailing numeral":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "2c99162bc9cf", None),
        "fix(#424) the particle chain stops before a bare acronym with words to spare":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "3e3aae6a5b4b", None),
        "fix(#424) a title-led chain before the numeral is the one name piece":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "5b3a743f9e35", None),
        "fix(comma-family) a comma followed only by titles keeps the given/family split":
            _Claim(2, ('family', 'given'), "5bd9c6d96c38", None),
        "fix(comma-family) a comma followed only by titles keeps the given/family split, the C1 example":
            _Claim(2, ('family', 'given'), "a3cfff4e78f4", None),
        "fix(#296) a dropped prenominal takes the name position it occupies":
            _Claim(3, ('_ambiguities', 'given', 'middle', 'title'), "263d5957cfc1", None),
        "fix(#296) dr is not postnominal vocabulary, so a trailing Dr. is a name word":
            _Claim(11, ('family', 'middle', 'suffix'), "b9cfc0d88bf6", None),
        "fix(#296) a credential-only comma string reads a name and its postnominal":
            _Claim(2, ('suffix', 'title'), "3f983ff71dee", None),
        "fix(#296) a lone post-comma credential is a suffix":
            _Claim(18, ('suffix', 'title'), "1f79efa10444", None),
        "fix(#325) a split credential followed by another suffix after a one-word family comma reads as suffixes":
            _Claim(6, ('given', 'suffix', 'title'), "7911e0158337", None),
        "fix(#325) a credential run across a second comma reads as suffixes":
            _Claim(1, ('suffix', 'title'), "f025c5f70a4e", None),
        "fix(#296) a glued honorific before a lone credential: the credential is the postnominal":
            _Claim(1, ('suffix', 'title'), "01bf2bd3f895", None),
        "fix(#296) do is a name, so it no longer stops the leading-particle scan as a title":
            _Claim(1, ('family', 'given'), "faa2c70fc49e", None),
        "fix(#296) dr is not postnominal vocabulary, so 'John Smith, Dr.' keeps its split and its title":
            _Claim(2, ('_ambiguities', 'suffix', 'title'), "34d3d96adb65", ('DEFAULT', 'FAMILY_FIRST')),
        "fix(#296) an ambiguous acronym counts as a suffix only when written with its periods":
            _Claim(1, ('_ambiguities', 'family', 'suffix'), "e13b3c769de4", None),
        "fix(#367) an inferred title no longer displaces a leading particle either":
            _Claim(1, ('family', 'given'), "d8ee9cd5da5f", None),
        "fix(#424) accepted: a particle of the suffix vocabulary opening the trailing run is a suffix piece":
            _Claim(1, ('_ambiguities', 'family', 'middle', 'suffix'), "a564b97f7162", None),
        "fix(#424) an unlisted abbreviation is as transparent as a listed title to the leading particle, the P4 example":
            _Claim(1, ('_ambiguities', 'family', 'given'), "42b69cf1b320", None),
        "fix(#424/#445) the maiden walk stops before the trailing numeral, and the lone name word is the family":
            _Claim(1, ('_ambiguities', 'family', 'given', 'maiden', 'suffix'), "cbe5bdd97317", None),
        "fix(#445) a maiden marker makes the lone name word the family":
            _Claim(6, ('family', 'given'), "f521c94c79fc", None),
        "fix(#445) the lone name word beside a marker a connective join no longer absorbs":
            _Claim(1, ('family', 'given', 'maiden', 'middle'), "52544a41dd62", None),
        "fix(#424) a marker followed only by the numeral is just a word":
            _Claim(1, ('_ambiguities', 'family', 'maiden', 'middle', 'suffix'), "aaf53040b071", None),
        "fix(#369) the bound given-name join takes a particle-and-bound word, so no fork is reported":
            _Claim(1, ('_ambiguities',), "81cf02ffdb33", None),
        "fix(#360) ste moved into the never-given particles with mc":
            _Claim(1, ('_ambiguities', 'family', 'given'), "e62caedec864", None),
        "fix(#399) a maiden marker bounds the particle chain: the geb. spelling":
            _Claim(1, ('family', 'maiden'), "2150936a8c55", None),
        "fix(#399) a maiden marker bounds the particle chain: a native-script marker":
            _Claim(1, ('family', 'maiden'), "f016cc61ca43", None),
        "feat(#395) a leading never-given particle bounds the family under a declared family-first order":
            _Claim(1, ('family', 'given', 'middle'), "47dcff268731", ('FAMILY_FIRST', 'FAMILY_FIRST_GIVEN_LAST')),
        "fix(#399)/feat(#395) a consumed maiden marker leaves the family-first fold no given name":
            _Claim(1, ('family', 'given', 'maiden'), "504eb466e347", ('FAMILY_FIRST', 'FAMILY_FIRST_GIVEN_LAST')),
        "feat(#395)/fix(#296) a comma followed only by a title leaves the pre-comma name to the declared order's fold":
            _Claim(1, ('family', 'given', 'middle', 'suffix', 'title'), "fc6bc9e605e1", ('FAMILY_FIRST',)),
        "feat(#395)/fix(#296) a comma followed only by a title leaves the pre-comma name to the declared order's fold, the given-last spelling":
            _Claim(1, ('family', 'given', 'middle', 'suffix', 'title'), "3e43a2be022e", ('FAMILY_FIRST_GIVEN_LAST',)),
        # #484's two, the same pair as the 2.0.0 ledger's: the change
        # shipped in 2.2.0, so it is equally visible from either 2.x
        # baseline, and the reaches and digests agree because the two
        # files carry the same literal list.
        "fix(#385/#402) an all-particle name part initials its words (R2)":
            _Claim(27, ('_initials',), "6b242c287db8", ('DEFAULT',)),
        "fix(#360) los joined the particles, so it no longer initials":
            _Claim(1, ('_initials',), "cd721215f463", ('DEFAULT',)),
        # fix(#462), reach and digest as in the 2.0.0 mapping: the same
        # regex over the same corpora, and the facade bug it fixes is
        # in every 2.x wheel, so the baseline makes no difference.
        "fix(#462) the facade keeps an initial-shaped conjunction letter":
            _Claim(18, ('_initials',), "3dd0e0276be6", ('DEFAULT',)),
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
        # reaches EVERY name. #451 made that shape a startup error, so
        # no ledger reaching this line has one -- but _rules() does not
        # validate, so counting it as the whole corpus stays correct
        # rather than becoming dead. It is what such a rule claims.
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
#: claim. Keyed by name; the diff shape each one produces against that
#: baseline is compare._RECORDED_DIFFS' half (#497).
#:
#: Every other guard here measures a rule ALONE: _CORPUS_CLAIMS records
#: what a regex reaches, and the gate's total counts names. Neither can
#: see which rule wins a contest, and that is the property #372 is
#: about -- seven of these names spent months on fix(comma-family),
#: whose prose describes none of them, with every guard green and the
#: gate reporting 108/0 throughout.
#:
#: The comma family is recorded because it is where that went wrong.
#: Hundreds of corpus names are reachable by two or more rules in the
#: same tier -- 301 in the 1.4 tier as of the rules-doc corpus (#414),
#: up from 42, which is why the count is described rather than pinned:
#: it moves with every corpus addition and pinning it would only ever
#: be re-recorded. The rows below are the ones whose boundaries this
#: file argues about, and pinning the argument is cheaper than
#: re-deriving it. Note
#: 'Andrews, M.D.' diffs on the SAME {given, suffix} shape as the seven
#: peels -- only the CJK lookahead separates them, so it is the row
#: that fails if that lookahead is ever dropped.
#:
#: The shapes these rows are classified with used to sit in the keys
#: here and moved to compare._RECORDED_DIFFS (#497), because a shape is
#: something only a RUN can measure: fed to classify() as an input and
#: checked by nothing, a guessed one agreed with itself forever. That
#: comment carries what this one used to say about them -- how each was
#: measured and where the claim did not hold, that a shifted shape is a
#: finding rather than a number to update, and that they are
#: default-order only, the blind spot `orders` (#468) opened. One copy
#: of each fact, since two means one of them goes quietly stale.
_CROSS_RULE_WINNERS: dict[str, dict[str, str]] = {
    # open cycle: one rule, so nothing for a second one to contest
    "expected_since_2.2.0.toml": {},
    "expected_since_1.4.0.toml": {
        "Andrews, M.D.": "fix(comma-family)",
        "田中, 太郎さん": "fix(cjk-comma-honorific-peel)",
        "김, 민준씨": "fix(cjk-comma-honorific-peel)",
        "김, 민준씨 (Jimmy)": "fix(cjk-comma-honorific-peel)",
        "김민준, 씨": "fix(cjk-comma-honorific-peel)",
        "김민준, 씨.": "fix(cjk-comma-honorific-peel)",
        "선생님, J.씨": "fix(cjk-comma-honorific-peel)",
        "이, J.씨": "fix(cjk-comma-honorific-peel)",
        # the union rows: they move `family`, so the peel rule's fields
        # exclude them and they must stay on the compound rule
        "Dr 김민준씨, V.": "fix(cjk-comma-compound)",
        # since #296's audit the title moves too (PhD is the postnominal)
        "田中さん, PhD": "fix(cjk-comma-compound)",
        "田中さん, V.": "fix(cjk-comma-compound)",
        # #372's suffix-routing split. 'Bob Jones, author' moves NO
        # suffix, which is what disqualifies it from the routing rule;
        # 'Smith Jr.' is the Latin shape that rule is named for; the two
        # glued honorifics are the majority it also legitimately takes,
        # and cannot be given a rule of their own -- '김민준씨' and the
        # given name '김지양' are the same string shape.
        # since the all-titles repair (#296's bundle) the pre-comma name
        # keeps its split here, and the rule written for that shape is
        # ahead of the precomma merge in the file; 'MD, PHD' has one
        # pre-comma piece, no split to keep, and stays merged
        "Bob Jones, author":
            "fix(comma-family) a comma followed only by titles keeps "
            "the given/family split",
        # since #296's audit 'PHD' is a postnominal here and the string
        # is credentials only; the rule written for that shape is ahead
        # of the precomma merge in the file
        "MD, PHD":
            "fix(#296) a credential-only comma string reads a name and "
            "its postnominal",
        "Smith Jr.":
            "fix(suffix-routing) a two-token name ending in the suffix "
            "word jr keeps it in `suffix`",
        # #451's two contests with the numeral rule, whose regex reaches
        # both of these names from the very end of the file. Only the
        # first is decided by order: 'Carod i' diffs {family, suffix},
        # which both rules declare, so nothing but _sorted_rules'
        # stability inside the name_regex tier keeps it with fix(#397).
        # '田中さん II' diffs {family, given, suffix} -- 1.4 read it
        # 'first 田中さん / last II', 2.x reads 'last 田中 / suffix
        # さん, II' -- and `given` is the field the numeral rule's
        # `fields` cannot admit at any position. Both are recorded
        # because a later edit that moves either rule, or widens the
        # numeral rule's `fields`, would take one silently -- exactly the
        # absorption #451 exists to end.
        "Carod i":
            "fix(#397) NOT WANTED: a trailing Catalan/Polish linking "
            "'i' is read as a generation marker and the family is lost",
        "田中さん II":
            "fix(cjk-glued-honorific-peel) glued honorific peels into "
            "suffix",
        # #484's three `_initials` contests with a literal rule on one
        # side. fix(initials-per-word)'s particle-chain rule reaches all
        # three, declares the same lone `_initials` field, and loses
        # only because both literal rules are written ahead of it --
        # file order, which _sorted_rules leaves untouched now that
        # every rule carries a name_regex. Each of the three really does
        # diff on initials, so narrowing or deleting a literal rule
        # would hand its name to the per-word rule rather than surface
        # it: the handover this row exists to catch.
        "de los Santos":
            "fix(#360) los joined the particles, so it no longer initials",
        "van Berg Jan de":
            "fix(#385/#402) an all-particle name part initials its words (R2)",
        "van ma van":
            "fix(#385/#402) an all-particle name part initials its words (R2)",
        # the glued/spaced boundary. 'Andersonさん' and '김민준씨' left
        # suffix-routing for a rule that names them; '김민준 씨.' is
        # spaced and stays on the spaced rule, which #372 taught to
        # tolerate the trailing period.
        #
        # '김지양' is why the glued rule copies GLUED_HONORIFICS and not
        # SUFFIX_WORDS: 양 is absent from the glued set, so no rule
        # NAMED for honorifics can claim a suffix diff on a given name
        # that merely ends in one. The fields-only fix(suffix-routing)
        # still would -- measured -- which was unchanged by #372 and was
        # the residual cost of having a last-resort tier at all. Being
        # absorbed by the catch-all is recoverable; being labelled
        # 'recognized honorific' by a specific rule is not. #451 deleted
        # that catch-all, so there is no last-resort tier left in any
        # ledger and the residual cost went with it: all four rules that
        # replaced it carry a name_regex.
        "Andersonさん": "fix(cjk-glued-honorific-peel)",
        "김민준씨": "fix(cjk-glued-honorific-peel)",
        "김민준 씨.": "fix(cjk-honorific-suffix)",
        # '.,' moved off `fix(comma-family) lone post-comma piece
        # routes to suffix/title, not first`, whose Latin-range comma
        # regex reaches it, onto the A2 rule that describes it (#451).
        # Recorded because only file order separates the two rules --
        # they are in the same tier and both reach the name -- and a
        # later edit that moves either one silently hands it back.
        ".,": "fix(A2) content-free input names nobody, so every role empties",
        # The one exception the cjk-comma-compound rule's `middle`
        # argument turns on, added by #452's review. That comment says
        # ten of the eleven names it explains have a single-token
        # post-comma tail and this is the eleventh, escaping `middle`
        # only because v1's fix_phd merges the split credential before
        # parsing. Pinned because the count itself is not: _claim
        # measures regex REACH (23 here), which does not move when a
        # name inside it changes hands -- so if this name ever went to
        # another rule, the argument would go false with nothing
        # saying so. Shape measured against the 1.4.0 tag: v1 reads
        # first '田中さん', suffix 'Ph. D.'; the tree reads family
        # '田中', suffix 'さん, Ph. D.'.
        "田中さん, Ph. D.":
            "fix(cjk-comma-compound) comma routing compounds with the CJK order flip",
        # The jr rule's surplus, added by the #453 review. Its regex
        # reaches these three and does not explain them; `fields` is
        # what makes it ineligible -- none of the shapes below is a
        # subset of its {family, suffix} -- and file order is only the
        # second line. Recorded because handing one over takes TWO
        # edits (widen `fields`, move the rule up) and nothing else
        # here would report the pair: reach is per-rule, and the jr
        # rule's own _CORPUS_CLAIMS count of 5 does not move when a
        # name inside it changes hands. Shapes measured against the
        # 1.4.0 wheel, not guessed. 'Doe,, Jr.' is the fourth name the
        # regex reaches and has no row: it does not diff at this
        # baseline, so there is no winner to pin.
        "Kim, Jr.":
            "fix(#296) a lone post-comma credential is a suffix",
        "Smith, Jr.":
            "fix(#296) a lone post-comma credential is a suffix",
        "김민준씨 Jr.":
            "fix(cjk-glued-honorific-peel) glued honorific peels into suffix",
        # #484's per-word rules. Measured over the corpus, exactly ONE
        # name is reached by two of them AND diffs on `_initials`:
        # 'de la Vega y Santos Juan' carries both a connective and a
        # particle chain, and the connective rule wins it on file
        # order alone -- the two declare the same single field, so
        # `fields` cannot separate them and only position does. Five
        # more names are reached by two ('Jane van der Berg née y
        # Jones', 'Maria Luisa y de la Cruz', 'Sir abdul van der
        # Berg', 'abdul Ph. D. Smith Berg', 'van der Berg, abdul née
        # Jones') and none of them has an `_initials` diff to pin:
        # three move ROLES, so the pseudo-field never enters, and two
        # do not diff at all.
        "de la Vega y Santos Juan":
            "fix(initials-per-word) a connective run",
        # Not contested today -- the bound-given rule is the only one
        # of the four whose regex reaches these three -- and recorded
        # anyway, because the bound rule sits BEHIND the connective
        # one in file order and the two vocabularies are one widened
        # alternation apart. A connective rule grown to reach 'Abu'
        # or a particle rule grown to reach a trailing 'van' takes
        # these names silently: reach is per-rule and the gate's total
        # is per-corpus, so nothing else here would say so.
        "Abu Bakr Al Baghdadi, MD":
            "fix(initials-per-word) a bound-given run",
        "abu bakr al baghdadi":
            "fix(initials-per-word) a bound-given run",
        "Berg, abdul van": "fix(initials-per-word) a bound-given run",
    },
    # The two 2.x ledgers had NO section here until #452, and the
    # coverage assertion below was `<=`, so their absence read as "no
    # contest to pin" rather than "nobody looked". They are back to
    # empty, and it is now the other thing: a stated position, which is
    # what the equality assertion below makes sayable. Do not restore a
    # row to fill them.
    #
    # #452 gave each two rows -- 'Nguyen, Van' and 'Jane née and Jones
    # Smith', the handovers its narrowings caused -- and #497 deleted
    # all four rather than correct them. Each recorded a diff shape a
    # run contradicts (compare._RECORDED_DIFFS' provenance note has the
    # measurements and the recompute, in one copy, including why the one
    # correctable shape was not corrected), and at the shape each name
    # really produces, exactly one rule admits it. That is the defect
    # under the wrong shapes rather than beside them: a row pinning a
    # race with one runner is never exercised as a contest, so its shape
    # only ever had to agree with itself.
    #
    # EMPTY IS NOT "these ledgers hold no contested name". Measured
    # 2026-09-03 over the diffs each baseline's own run produces, 5 of
    # the 247 at 2.0.0 and 1 of the 155 at 2.1.0 move a shape two or
    # more rules admit, file order picking the winner ('MD, PHD' is the
    # one both have). Recompute: drive compare.main() at the baseline,
    # capture its `diffing` by wrapping dormant_rules, and count the
    # names for which more than one rule satisfies
    # compare._entry_matches at the measured shape. None of those
    # boundaries is argued about in this file, and this roster pins the
    # arguments this file makes -- so a row is owed when someone argues
    # one, not before. Whether that position should change now that the
    # six are measured rather than merely unexamined is #501; the answer
    # there decides whether these two sections stay empty, and nothing
    # in this file presumes it.
    #
    # Nor is "only one rule admits it" grounds on its own to delete a
    # row: 13 of the 31 above are in that position too, and say so (the
    # jr rule's surplus, the bound-given trio). They stay because the
    # shapes they pin are shapes runs actually make, so widening a
    # `fields` or moving a rule hands the name over and this test says
    # so. The four deleted rows could not do that work at any edit.
    "expected_since_2.0.0.toml": {},
    "expected_since_2.1.0.toml": {},
}


def test_the_recorded_rule_still_wins_each_contested_name() -> None:
    """Who explains what, which nothing else here asks.

    Measured when this was written: narrowing fix(cjk-comma-compound)'s
    script class sent three of these names to fix(suffix-routing) -- a
    fields-only catch-all whose prose was about two-token Latin names --
    and the gate still reported 108 intentional / 0 unexplained. Reach
    is per-rule, the total is per-corpus; neither notices a name
    changing hands. #451 has since deleted that catch-all, so the same
    narrowing would now send those three to UNEXPLAINED and the gate
    would say so -- but only because a fields-only rule happened to be
    what absorbed them. File order inside the name_regex tier hides a
    handover just as completely, which is what the #451 rows below pin.

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
        shapes = compare._RECORDED_DIFFS[ledger_name]
        for name, expected in winners.items():
            # explicit, because a bare KeyError here names a dict and a
            # string and nothing else. The readable half-recorded-pin
            # message lives in test_every_pinned_winner_has_a_recorded_shape,
            # which a `-k` selection or a first failure may not have run.
            assert name in shapes, (
                f"{ledger_name}: {name!r} is pinned a winner in "
                f"_CROSS_RULE_WINNERS with no shape in "
                f"compare._RECORDED_DIFFS, so there is nothing to ask "
                f"classify() about. Record the shape a run measures for "
                f"it, or drop the pin -- "
                f"test_every_pinned_winner_has_a_recorded_shape is the "
                f"guard that states this as its own subject")
            fields = shapes[name]
            got = compare.classify(name, set(fields), rules, never)
            assert got is not None and got.startswith(expected), (
                f"{ledger_name}: {name!r} diffing {list(fields)} is now "
                f"explained by {got!r}, not {expected!r}. Check the new "
                f"rule's prose actually describes this name before "
                f"recording it -- a rule claiming a diff it does not "
                f"describe is #372, and it stays green everywhere else")
            checked += 1
    assert checked, "no contested name was checked, so this pin is vacuous"
    assert set(_CROSS_RULE_WINNERS) == {led.name for led in _LEDGERS}, (
        f"_CROSS_RULE_WINNERS must name every ledger on disk, with an "
        f"explicit empty mapping for one that genuinely has no contest. "
        f"Missing: {sorted({L.name for L in _LEDGERS} - set(_CROSS_RULE_WINNERS))}; "
        f"unknown: {sorted(set(_CROSS_RULE_WINNERS) - {L.name for L in _LEDGERS})}. "
        f"This was `<=` until #452, which made a ledger with no rows "
        f"indistinguishable from one needing none -- and the #452 "
        f"narrowings moved shapes between rules in the two 2.x ledgers "
        f"that had no section at all. Both sibling rosters "
        f"(_CORPUS_CLAIMS, _SPAN_BEARING_RULES) use equality; this one "
        f"was the odd one out.")


def test_every_pinned_winner_has_a_recorded_shape() -> None:
    """The roster names a contested name; _RECORDED_DIFFS says what it
    diffs. A name in one and not the other is a half-recorded pin --
    the winner cannot be checked without the shape, and a shape nothing
    pins a winner for is unverified by the run for no purpose.

    The row VALUES are checked here too, against the three illegal
    states compare.validate_rules already refuses for a rule's `fields`
    (a name outside the role vocabulary, '_initials' beside a role, a
    repeated role) plus the empty one. A recorded shape is fed to
    classify() as the same kind of input a rule's `fields` is, so the
    wording below mirrors those refusals deliberately -- the two should
    read as one check written in two places.

    WHY HERE. What each illegal row does WITHOUT these assertions,
    measured 2026-09-03 by injecting one into the shipped 1.4.0 section
    and running this file: a repeated role and an empty shape pass the
    whole suite silently, and surface only as a MOVED SHAPE finding
    from a gate run -- whose message says the winner beside the shape
    "was recorded for the OLD shape", telling a contributor with a
    copy-paste slip that the parser moved. A misspelled role and an
    '_initials' beside a role happened to fail the sibling test above
    as well, because on the rows they were injected into the corrupted
    shape changed which rule classify() picks -- but that is a property
    of those rows, not of the defect: a shape a second rule admits at
    both spellings changes no winner and says nothing. Either way the
    message names a rule handover rather than the typo, and the loop
    that does catch these needs a baseline wheel and a full corpus
    pass, so the row ships green through CI. At pytest speed the answer
    is a sentence naming the typo. The `departed` assertion asks
    compare.py's `gone` question the same way and for the same reason.
    """
    compare = load_tool("compare")
    for ledger_name, winners in _CROSS_RULE_WINNERS.items():
        shapes = compare._RECORDED_DIFFS.get(ledger_name, {})
        assert set(winners) == set(shapes), (
            f"{ledger_name}: winners without a recorded shape "
            f"{sorted(set(winners) - set(shapes))}; shapes with no "
            f"pinned winner {sorted(set(shapes) - set(winners))}")
        # `gone`'s question, at pytest speed and against every ledger
        # rather than only the one a run was pointed at. The gate asks
        # it over the corpora a full run loaded; _CORPUS_NAMES is every
        # name in every corpus*.jsonl, which is the same population.
        departed = sorted(set(shapes) - set(_CORPUS_NAMES))
        assert not departed, (
            f"{ledger_name}: {departed} carry a recorded shape and sit "
            f"in no corpus. Nothing measures such a row, so it agrees "
            f"with itself forever. Settle whether the name left "
            f"DELIBERATELY before editing either roster -- "
            f"compare.py's own refusal over the full corpus carries the "
            f"question and both repairs")
        for name, shape in shapes.items():
            where = f"{ledger_name}: the recorded shape for {name!r}"
            bad = sorted(set(shape) - compare._RULE_FIELDS)
            assert not bad, (
                f"{where} names {bad}, which are not roles; expected "
                f"from {sorted(compare._RULE_FIELDS)}. classify() is "
                f"asked about the shape as a SET, so a misspelled role "
                f"is simply a role the diff does not carry: it never "
                f"reports as a typo, only as a rule handover or a "
                f"MOVED SHAPE finding blaming the parser. Checked "
                f"against _RULE_FIELDS -- the set validate_rules checks "
                f"a rule's 'fields' against, since a shape is the same "
                f"kind of input -- and not against V2_FIELDS, because "
                f"'_ambiguities' is legal in a 2.x row (it cannot "
                f"appear below 2.0) even though no row carries it today")
            dups = sorted({f for f in shape if shape.count(f) > 1})
            assert not dups, (
                f"{where} repeats {dups}. It is read as a set, so the "
                f"repeat changes nothing classify() matches -- it is a "
                f"copy-paste slip that would otherwise pass every check "
                f"here silently, and the '_initials' check below would "
                f"read ('_initials', '_initials') as '_initials' alone")
            others = sorted(set(shape) - {"_initials"})
            assert not ("_initials" in shape and others), (
                f"{where} lists '_initials' beside {others}. "
                f"'_initials' enters a diff only when every role and "
                f"the ambiguity kinds agree (#484), so no diff can "
                f"carry it with another field: this shape is one no run "
                f"can measure, and the row is unfalsifiable rather than "
                f"merely wrong")
            assert shape, (
                f"{where} is empty. main() appends to `diffing` only "
                f"where a comparison DIFFED, so no run produces an "
                f"empty shape and the row can never be contradicted")
    # Per-ledger equality above iterates the ROSTER's keys, so a
    # _RECORDED_DIFFS section for a ledger the roster does not name is
    # invisible to it -- and to the run, which reads shapes per ledger
    # too. The sibling test asserts the ROSTER's keys are exactly the
    # ledgers on disk; this carries that to _RECORDED_DIFFS, which has
    # no such check of its own.
    assert set(compare._RECORDED_DIFFS) == set(_CROSS_RULE_WINNERS), (
        f"_RECORDED_DIFFS and _CROSS_RULE_WINNERS name different "
        f"ledgers: only in _RECORDED_DIFFS "
        f"{sorted(set(compare._RECORDED_DIFFS) - set(_CROSS_RULE_WINNERS))}; "
        f"only in _CROSS_RULE_WINNERS "
        f"{sorted(set(_CROSS_RULE_WINNERS) - set(compare._RECORDED_DIFFS))}")


def test_the_family_first_fold_is_not_explained_under_the_default_order(
        ) -> None:
    """The hazard the `orders` key exists for, pinned against the
    shipped 2.x ledgers rather than a fixture.

    'de la Cruz Juan Carlos' is compared three times: twice from
    corpus_shapes.jsonl under the two family-first orders, where #395's
    fold is the intended reading, and once from corpus_rules.jsonl
    under the DEFAULT order, where rules.md#P1 says the whole string is
    the family. If the fold ever leaked into the default order it would
    move {family, given, middle} -- the same three roles, on the same
    string -- so an order-blind rule would claim the leak, label it
    feat(#395), and exit 0. That is #372's failure mode aimed at the
    most plausible regression of the very change the rule describes.

    Both directions again: declining the default-order diff is the
    point, but a rule that declined its OWN orders too would be
    silently dormant and this pin would pass on a broken ledger.

    The default-order assertion runs on EVERY ledger, before the
    scoped-rule search decides whether there is anything else to check.
    Guarding it behind that search is what made an earlier draft weak:
    dropping `orders` from one 2.x ledger takes that ledger through the
    `continue` while the other keeps `checked` above zero, and the
    suite stays green with one ledger absorbing the leak. On a ledger
    whose rules do not reach this name at all -- 1.4.0, the open cycle
    -- the assertion is trivially true, which costs nothing.
    """
    compare = load_tool("compare")
    name, moved = "de la Cruz Juan Carlos", {"family", "given", "middle"}
    checked = 0
    for ledger in _LEDGERS:
        rules = compare._sorted_rules(_rules(ledger))
        never = _exclusions(ledger)
        assert compare.classify(name, moved, rules, never) is None, (
            f"{ledger.name}: a DEFAULT-order diff moving {sorted(moved)} "
            f"on {name!r} is explained by "
            f"{compare.classify(name, moved, rules, never)!r}. That is "
            f"the family-first fold firing where P1 forbids it, and the "
            f"rule describing the fold must not absorb it -- scope it "
            f"with `orders`")
        scoped = [r for r in rules
                  if isinstance(r.get("orders"), list)
                  and re.search(str(r["name_regex"]), name)
                  and moved <= set(r["fields"])]
        for rule in scoped:
            for order in rule["orders"]:
                assert compare.classify(
                    name, moved, rules, never, order) == rule["issue"], (
                    f"{ledger.name}: {rule['issue']!r} declares order "
                    f"{order} and does not explain its own diff under "
                    f"it; the rule is dormant and the pin above is "
                    f"passing for the wrong reason")
                checked += 1
    assert checked, ("no orders-scoped rule reaches this name in any "
                     "ledger, so this pin is vacuous")


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
#:
#: A second, newer limit: `absorbed_by` is recomputed at comparison
#: order None, so an absorption that happens only under a declared
#: order is invisible to it -- true today because no exclusion
#: protects a shape that reads differently under one, and something to
#: revisit the day one does.
_EXCLUSION_EFFECT: dict[str, _Excluded] = {
    "(?i)^(?!\\s*ph\\.)(?![^\\s,]+\\s*,\\s*ph\\.\\s*d\\.\\s*$)(?![\\u0000-\\u024f]*\\b(?:jr|sr|ii|iii|iv)\\.?\\s+ph\\.\\s*d\\.\\s*$)[\\u0000-\\u024f]*\\bph\\.\\s*d\\.\\s*$":
        _Excluded(3, "5a12a8117651",
                  # fix(comma-precomma-family) JOINED this tuple in #372,
                  # it did not replace anything: it claims the {given,
                  # family} readings, which it legitimately describes for a
                  # Latin comma name, while fix(suffix-routing) claimed the
                  # readings outside its two fields. The exclusion refuses
                  # the name before either is reached; this records what
                  # would happen without it.
                  #
                  # fix(suffix-routing) LEFT the tuple in #451, which
                  # deleted the fields-only catch-all of that name: the
                  # four rules that replaced it are two-token literals and
                  # none of them reaches a trailing 'Ph. D.'. A tuple that
                  # SHRANK is the safe direction -- one fewer rule stands
                  # ready to claim a protected reading -- which is why this
                  # roster's message warns only about growth.
                  # FULL issue strings, not `fix(tag)` prefixes. The
                  # #453 review measured what the truncation cost: this
                  # ledger carries three rules beginning "fix(comma-family)"
                  # and, since #451, four beginning "fix(suffix-routing)",
                  # so a tag-keyed tuple sits at its maximum for that tag
                  # -- any of the siblings could widen onto a protected
                  # reading and this roster would stay green. The same
                  # identity-free weakness _SPAN_BEARING_RULES records.
                  #
                  # #484's phd-merge initials rule JOINED the tuple,
                  # and it is the first entrant that reaches a
                  # protected shape through the `_initials`
                  # pseudo-field rather than through a role: its
                  # `fields` is exactly ["_initials"], so the only
                  # subset it can claim is the singleton, and
                  # _protectable_fields builds that subset because it
                  # reads compare._RULE_FIELDS rather than Role.
                  #
                  # Decided rather than absorbed. The rule's regex is
                  # the bare fragment `\bph\. d\.`, which reaches all
                  # 18 corpus spellings while explaining the two
                  # LEADING ones it is named for; a trailing 'Ph. D.'
                  # is what this entry protects, and the exclusion
                  # refuses those names before any rule is consulted,
                  # so the rule claims nothing there in a real run.
                  # What the growth records is that it now STANDS
                  # READY to -- delete this entry and the initials
                  # reading of a trailing 'Ph. D.' would classify
                  # under a rule whose prose is about the merge at
                  # the front of a name. Narrowing the regex to the
                  # leading spelling would empty this tuple again and
                  # is the alternative on the table if the exclusion
                  # is ever retired.
                  ("fix(comma-family) lone post-comma piece routes to "
                   "suffix/title, not first",
                   "fix(comma-precomma-family) pre-comma run reads as "
                   "family, not given",
                   "fix(initials-per-word) the Ph. D. merge initials "
                   "each word (facade, since 2.0.0)")),
    '(^|[\\w.]\\s+)[("\'][^)"\']+[)"\'](\\s+\\w|\\s*$)':
        # 51 -> 54 as rules.md gained the bracketed Polish examples
        # (#434): 'Maria Kowalska (z domu Nowak)', 'Maria Kowalska
        # (z domu)', and the boundary 'Anna z (domu) Nowak' M2 gained
        # when the clause-straddling defect was fixed. 54 -> 55 for
        # M4's markerless clause example, 'Smith (Jones)' (#445),
        # which the exclusion costs nothing: under the default facade
        # the pair is a nickname one, so the name reads family
        # 'Smith', nickname 'Jones' exactly as 1.4.0 read it and has
        # no diff to silence. Growth in the corpus, not in the
        # exclusion -- its regex is untouched -- and `absorbed_by`
        # stayed empty, so no rule reaches the protected shape.
        # 55 -> 56 for the shape-1 variation matrix (#486): tagging
        # 'John "Jack" Kennedy' put this entry's own FIRST `examples`
        # string into a corpus for the first time. It was in none
        # before -- the radar corpora hold the smart-quote spelling
        # 'John “Jack” Kennedy' and not this one, which is why the
        # two read differently at 1.4.0 (feat(#273) classifies the
        # typographic pair; the ASCII pair is what this entry promises
        # was already recognized). It costs the entry nothing either --
        # 1.4.0 reads the quoted clause as a nickname exactly as the
        # tree does, so there is no diff to silence. 56 -> 57 for the
        # shape-2 slot the same matrix opened, 'Kennedy, John (Jack)',
        # which is the paren spelling of that clause after a family
        # comma and costs the entry nothing for the same reason.
        _Excluded(57, "35ac9a8c4195", ()),
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
                            absorbed.add(claimed)
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
    ('fix(comma-family)', 'fix(comma-precomma-family)'). Re-measured
    for #451, and the figure it replaces was wrong in both halves: it
    read ('fix(suffix-routing)',) where the answer was a three-tuple
    with those two comma rules in it, and #451's deletion of the
    fields-only fix(suffix-routing) catch-all then took the third
    entry away. The point the sentence is making is unchanged -- the
    hypothetical is still caught, by more rules than it named.

    Measured: deleting `fields = ["nickname", "middle"]` from the
    ASCII-pairs entry passes every other check in this tree. The entry
    then refuses ANY diff on every corpus name it captures -- the
    count is _EXCLUSION_EFFECT's `captures` for that pattern, above,
    which is where it is checked and where it stays current --
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
            # Every rule has a name_regex since #451, so this skip is
            # unreachable for a ledger that loads; kept because _rules()
            # does not validate. A fields-only rule would reach every
            # name by construction and so could never be statically
            # silent -- see _claim(), which counts one as the whole
            # corpus for the same reason
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
        "every rule declares `dormant`, or (impossible since #451) "
        "narrows by `fields` alone")


#: Every order-decided contest in every shipped ledger, measured with
#: exemptions IGNORED: the earlier rule's issue, the later rule's, and
#: how many corpus names their regexes both reach.
#:
#: The recorded negative control for the guard below (the
#: _EXCLUSION_EFFECT shape AGENTS.md asks of every guard): it is the
#: answer with the mechanism switched off, stored as data. Without it,
#: `precedes_narrower` could be deleted from every rule and the live
#: guard would keep passing if the predicate had quietly stopped
#: finding anything.
#:
#: 11 pairs, all in the 1.4 ledger. They divide by the tier of the
#: names they are contested over -- some reach contract-tier names,
#: the rest only radar -- and #495 argues from that division, which
#: survives a name changing tier even though its two counts there do
#: not. Read a name's tier off `_CORPUS_TIERS` and not off any one
#: demotion: the five radar-only pairs get there by two different
#: warrants, #488's `corpus_cjk_tolerated.jsonl` demotion for most of
#: the CJK names and #468's tier split for every `corpus_issues.jsonl`
#: one -- which is both 'Jr., PhD'/'MD, PHD' pairs whole, and one name
#: of the seventeen the compound/peel pair is contested over. Measured
#: 2026-09-02. A row that MOVES is a finding, not a number to update:
#: re-measure before editing it.
_ORDER_EXEMPTION_EFFECT: dict[str, list[tuple[str, str, int]]] = {
    "expected_since_1.4.0.toml": [
        ("fix(comma-family) a comma followed only by titles keeps the given/family split, the C1 example",
         "fix(comma-precomma-family) pre-comma run reads as family, not given", 2),
        ("fix(#296) a credential-only comma string reads a name and its postnominal",
         "fix(comma-family) lone post-comma piece routes to suffix/title, not first", 2),
        ("fix(#296) a credential-only comma string reads a name and its postnominal",
         "fix(comma-precomma-family) pre-comma run reads as family, not given", 2),
        ("fix(#296) a lone post-comma credential is a suffix",
         "fix(suffix-routing) a two-token name ending in the suffix word jr keeps it in `suffix`", 2),
        ("fix(#400/#274) bound-given join and maiden consumption in one name",
         "fix(#400) abd joins the word after it as one given name", 1),
        ("fix(#411/S2) a declining bound-given join leaves the suffix reading after a family comma",
         "fix(#400) abd joins the word after it as one given name", 1),
        ("fix(#272/#308) nakaguro division and a glued hangul honorific in one name",
         "fix(cjk-glued-honorific-peel) glued honorific peels into suffix", 1),
        ("fix(nickname-typographic-pairs) two typographic quote spans read as one nickname set",
         "feat(#273) typographic nickname delimiters recognized by default", 1),
        ("fix(cjk-comma-compound) comma routing compounds with the CJK order flip",
         "fix(cjk-glued-honorific-peel) glued honorific peels into suffix", 17),
        ("fix(cjk-glued-honorific-peel) glued honorific peels into suffix",
         "fix(suffix-routing) a two-token name ending in a roman numeral keeps it in `suffix`", 1),
        ("fix(cjk-glued-honorific-peel) glued honorific peels into suffix",
         "fix(suffix-routing) a two-token name ending in the suffix word jr keeps it in `suffix`", 1),
    ],
    "expected_since_2.0.0.toml": [],
    "expected_since_2.1.0.toml": [],
    "expected_since_2.2.0.toml": [],
}


def test_the_recorded_order_contests_are_what_the_ledgers_hold() -> None:
    """The negative control: every contest, exemptions ignored.

    A contest is two same-tier rules that overlap on all three of the
    keys classify() narrows by: the LATER one's `fields` are a strict
    subset of the earlier one's, both regexes reach a common corpus
    name, and neither scopes itself to `orders` the other excludes.
    There are then diffs both rules admit, and file order alone picks
    the winner.

    This roster is deliberately blind to `precedes_narrower`: it
    records the hazard, not whether it has been declared away.
    """
    compare = load_tool("compare")
    assert any(_ORDER_EXEMPTION_EFFECT.values()), (
        "every ledger's contest list is empty, so this control measures "
        "nothing: a predicate that had stopped finding anything at all "
        "would read exactly the same. That is the inert-measurement "
        "class mechanisms.md#RECORDED-ROSTERS is written against. If "
        "the last contest genuinely went away, delete this guard and "
        "its roster together -- do not leave four empty lists standing "
        "in for a measurement.")
    assert set(_ORDER_EXEMPTION_EFFECT) == {led.name for led in _LEDGERS}, (
        f"_ORDER_EXEMPTION_EFFECT must name every ledger on disk, with "
        f"an explicit empty list for one that genuinely has no contest. "
        f"Missing: {sorted({L.name for L in _LEDGERS} - set(_ORDER_EXEMPTION_EFFECT))}; "
        f"unknown: {sorted(set(_ORDER_EXEMPTION_EFFECT) - {L.name for L in _LEDGERS})}")
    for ledger in _LEDGERS:
        rules = _rules(ledger)
        # order_contests' shape leniency (see _rule_reach) is a
        # BORROWED guarantee: it trusts validate_rules to have run, and
        # `_rules()` does not run it. Calling it here turns the borrowed
        # guarantee into a local one, so this guard is not measuring a
        # ledger nothing has validated. It costs nothing on the shipped
        # files -- they already validate -- and fires first on a
        # hand-edit that would otherwise be scanned as if well-formed.
        compare.validate_rules(rules, ledger.name)
        found = [(c.earlier, c.later, len(c.names))
                 for c in compare.order_contests(rules, _CORPUS_NAMES)]
        assert found == _ORDER_EXEMPTION_EFFECT[ledger.name], (
            f"{ledger.name}: the order-decided contests are no longer "
            f"what this roster records.\n  found:    {found}\n"
            f"  recorded: {_ORDER_EXEMPTION_EFFECT[ledger.name]}\n"
            f"A contest that appeared is a new rule pair whose winner "
            f"file order is deciding; one that vanished means a rule "
            f"was narrowed or a corpus name left. Re-measure and read "
            f"the pair before editing this roster.")


def test_every_order_decided_contest_is_declared() -> None:
    """Narrow-first is the declaration-free default; wide-first says why.

    Where the later rule's `fields` are a strict subset of the earlier
    one's and both regexes reach a common corpus name, file order alone
    decides who classifies the diff. That is legal -- a wider rule can
    genuinely be the better description, and `马丁·路德·金씨` is the
    worked case: it divides on the nakaguro AND peels its honorific, so
    `fix(#272/#308)` describes it and `fix(cjk-glued-honorific-peel)`
    describes half of it. What is not legal is leaving it unsaid,
    because nothing else in the suite can see it: _CORPUS_CLAIMS
    measures each rule alone, the gate total is per-corpus, and
    _CROSS_RULE_WINNERS pins only names somebody hand-added.

    Do NOT satisfy this by reordering rules -- that moves which rule
    classifies a name and breaks _CROSS_RULE_WINNERS. Declare it.
    """
    compare = load_tool("compare")
    for ledger in _LEDGERS:
        rules = _rules(ledger)
        # Both scanners below read `precedes_narrower` through
        # _declared_over, whose docstring says outright that its shape
        # guarantee is BORROWED from validate_rules -- and `_rules()`
        # does not validate. Without this call a whitespace-only `why`
        # on a real exemption passes here, because _declared_over reads
        # the entry as a perfectly good declaration and retires the
        # pair. One line converts the borrowed guarantee into a local
        # one; the shipped ledgers already validate, so it costs
        # nothing.
        compare.validate_rules(rules, ledger.name)
        undeclared = compare.undeclared_contests(rules, _CORPUS_NAMES)
        assert not undeclared, "\n".join(
            [f"{ledger.name}: {len(undeclared)} order-decided contest(s) "
             f"nobody declared. The EARLIER rule must carry a "
             f"[[change.precedes_narrower]] block naming the later one "
             f"and saying what it describes that the later one does not:"]
            + [f"  {c.earlier!r}\n  outranks {c.later!r}\n"
               f"  on {len(c.names)} name(s), e.g. {list(c.names[:3])}"
               for c in undeclared])
        vacant = compare.vacant_exemptions(rules, _CORPUS_NAMES)
        assert not vacant, (
            f"{ledger.name}: {vacant} declare precedence over a pair "
            f"that is no longer contested. A rule was narrowed or a "
            f"corpus name left; delete the exemption rather than "
            f"leaving a justification for a hazard that is gone")
