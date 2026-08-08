"""Pins the pipeline's hand-duplicated regex/table copies to their
nameparser.config.regexes source of truth.

The 2.0 layering rule forbids nameparser._pipeline/_render importing
nameparser.config directly, so several patterns and tables are copied
by hand into the modules that need them, each with a "keep in sync by
hand" comment. Nothing previously enforced that promise: if
config/regexes.py changed, the copies would silently diverge with no
CI signal. Tests may legally import both sides (test_layering.py's own
convention), so this module is where the promise gets checked.

Layering is the usual reason for a copy but not the only one, so this
module's scope is the PROMISE rather than that one pair of packages:
the comma-set pin below reads _pipeline._state instead of config, and
several tests reach outside the package altogether -- four to the
differential ledgers, which could not import a Python constant if they
wanted to, one to a generated corpus whose generator can, and must
stay run.
"""
import importlib.util
import json
import re
import tomllib
from pathlib import Path
from typing import NamedTuple

import pytest

from nameparser.config import regexes as _config
from nameparser._pipeline import _assign, _post_rules, _tokenize, _vocab
from nameparser import _policy
from nameparser._policy import Script
from nameparser import _render
from nameparser.config.maiden_markers import MAIDEN_MARKERS
from nameparser.config.suffixes import (
    GLUED_HONORIFICS, SUFFIX_ACRONYMS_AMBIGUOUS, SUFFIX_NOT_ACRONYMS)


def test_emoji_ranges_match_config() -> None:
    assert _tokenize._EMOJI_RANGES == _config._EMOJI_RANGES


def test_bidi_pattern_matches_config() -> None:
    assert _tokenize._BIDI.pattern == _config.re_bidi.pattern
    assert _tokenize._BIDI.flags == _config.re_bidi.flags


def test_period_not_at_end_matches_config() -> None:
    source = _config.REGEXES["period_not_at_end"]
    assert _vocab._PERIOD_NOT_AT_END.pattern == source.pattern
    assert _vocab._PERIOD_NOT_AT_END.flags == source.flags


def test_period_abbreviation_matches_config() -> None:
    source = _config.REGEXES["period_abbreviation"]
    assert _assign._PERIOD_ABBREV.pattern == source.pattern
    assert _assign._PERIOD_ABBREV.flags == source.flags


def test_roman_numeral_matches_config() -> None:
    source = _config.REGEXES["roman_numeral"]
    assert _assign._ROMAN.pattern == source.pattern
    assert _assign._ROMAN.flags == source.flags


def test_patronymic_patterns_match_config() -> None:
    pairs = (
        (_post_rules._EAST_SLAVIC, "east_slavic_patronymic"),
        (_post_rules._EAST_SLAVIC_CYR, "east_slavic_patronymic_cyrillic"),
        (_post_rules._TURKIC, "turkic_patronymic_marker"),
        (_post_rules._TURKIC_CYR, "turkic_patronymic_marker_cyrillic"),
    )
    for copy, key in pairs:
        source = _config.REGEXES[key]
        assert copy.pattern == source.pattern, key
        assert copy.flags == source.flags, key


def test_initial_copies_agree_with_each_other_and_config() -> None:
    # _vocab._INITIAL and _render._INITIAL are both v1's "initial"
    # pattern minus its trailing "?" (documented at _render.py's
    # _INITIAL definition: the two call sites always fullmatch a
    # non-empty token, so the empty-string alternative is dropped on
    # purpose). Assert both the internal-copy agreement and the exact,
    # documented relationship to the config source, so a future edit to
    # either side that breaks the relationship fails loudly here
    # instead of silently drifting.
    assert _vocab._INITIAL.pattern == _render._INITIAL.pattern
    source = _config.REGEXES["initial"]
    # config's pattern is the pipeline copy with an extra "?" spliced in
    # just before the trailing "$", making the whole group optional.
    trimmed = _vocab._INITIAL.pattern
    reconstructed = trimmed[:-1] + "?" + trimmed[-1:]
    assert source.pattern == reconstructed
    assert source.flags == _vocab._INITIAL.flags


# The roster above grew one test at a time, and four hand-copies were
# never added to it -- _render's _SPACES, _SPACE_BEFORE_COMMA, _MAC and
# _WORD. They had not diverged, but nothing would have said so, which
# is the exact promise this module exists to keep. All four mirror a
# config key whose only other reader was v1's parser.py, deleted at the
# M11 swap, so nothing else touches them either.
#
# Declared as a roster rather than one test per copy, with a
# completeness check below: adding a pattern without declaring its
# source now fails here instead of being silently unpinned.
_SOURCES: dict[tuple[str, str], str | None] = {
    ("_assign", "_PERIOD_ABBREV"): "period_abbreviation",
    ("_assign", "_ROMAN"): "roman_numeral",
    ("_post_rules", "_EAST_SLAVIC"): "east_slavic_patronymic",
    ("_post_rules", "_EAST_SLAVIC_CYR"): "east_slavic_patronymic_cyrillic",
    ("_post_rules", "_TURKIC"): "turkic_patronymic_marker",
    ("_post_rules", "_TURKIC_CYR"): "turkic_patronymic_marker_cyrillic",
    ("_render", "_SPACES"): "spaces",
    ("_render", "_SPACE_BEFORE_COMMA"): "space_before_comma",
    ("_render", "_MAC"): "mac",
    ("_render", "_WORD"): "word",
    ("_vocab", "_PERIOD_NOT_AT_END"): "period_not_at_end",
    # Deliberately NOT a straight copy -- pinned by the dedicated tests
    # above, which assert the documented RELATIONSHIP instead:
    ("_render", "_INITIAL"): None,      # config's pattern minus one "?"
    ("_vocab", "_INITIAL"): None,       # same
    ("_tokenize", "_BIDI"): None,       # re_bidi, not a REGEXES key
    # Mirrors _pipeline._state.COMMA_CHARS, not nameparser.config
    ("_render", "_COMMA_CHAR"): None,
}

_MODULES = {"_assign": _assign, "_post_rules": _post_rules,
            "_render": _render, "_tokenize": _tokenize, "_vocab": _vocab}


@pytest.mark.parametrize(
    "where,key", [(w, k) for w, k in _SOURCES.items() if k is not None],
    ids=lambda v: v if isinstance(v, str) else f"{v[0]}.{v[1]}")
def test_declared_copy_matches_its_config_source(
        where: tuple[str, str], key: str) -> None:
    copy = getattr(_MODULES[where[0]], where[1])
    source = _config.REGEXES[key]
    assert copy.pattern == source.pattern, f"{where[1]} vs REGEXES[{key!r}]"
    assert copy.flags == source.flags, f"{where[1]} vs REGEXES[{key!r}]"


def test_every_hand_copied_pattern_is_declared() -> None:
    """The roster must cover every compiled pattern in these modules.

    Without this, the roster is just another list that a new constant
    can be left out of -- which is how the four above went unpinned.
    """
    undeclared = [
        (name, attr)
        for name, mod in _MODULES.items()
        for attr, value in vars(mod).items()
        if attr.startswith("_") and not attr.startswith("__")
        and isinstance(value, re.Pattern)
        and (name, attr) not in _SOURCES
    ]
    assert not undeclared, (
        f"compiled patterns missing from _SOURCES: {undeclared}. Add each "
        f"with its nameparser.config.regexes key, or None if it has no "
        f"config counterpart.")


def test_comma_char_matches_the_pipeline_comma_set() -> None:
    # _render splits on the same comma characters segment does; the set
    # lives in _state, so this one is pinned against that, not config.
    from nameparser._pipeline._state import COMMA_CHARS

    assert set(_render._COMMA_CHAR.pattern.strip("[]")) == set(COMMA_CHARS)


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

_TOOLS = Path(__file__).parents[2] / "tools" / "differential"

#: Every baseline's ledger, swept rather than named. #332 added a second
#: file whose four hand copies went unchecked because the pins below
#: named the 1.4 one by filename, and the count grows by one per
#: release -- see AGENTS.md's release step 8.
_LEDGERS = sorted(_TOOLS.glob("expected_since_*.toml"))

#: Every name the harness classifies, deduplicated. The ledgers exist
#: to explain diffs on THESE strings and no others, so "what does this
#: rule claim?" is answerable here without parsing anything -- a plain
#: regex search, no baseline wheel, no network.
#:
#: This is what the guards below check against, and it is why they hold
#: where four rounds of syntactic ones did not. Depth-0 pipes, nesting
#: levels and probe strings are all proxies for the question that
#: actually matters; a rule cannot widen its corpus reach and still
#: answer this one the same way, however it is spelled.
_CORPUS_NAMES = sorted({
    json.loads(line)
    for path in sorted(_TOOLS.glob("corpus*.jsonl"))
    for line in path.read_text(encoding="utf-8").splitlines() if line.strip()})


def _claimed(name_regex: str) -> list[str]:
    """Corpus names a rule's regex matches."""
    return [name for name in _CORPUS_NAMES if re.search(name_regex, name)]


def _unclassified_names() -> list[str]:
    """Corpus names carrying no codepoint _SCRIPT_RANGES classifies."""
    has_classified = _policy._script_matcher(*_policy._SCRIPT_RANGES)
    return [name for name in _CORPUS_NAMES if not has_classified(name)]


def _normalize(text: str) -> str:
    """How the config stores vocabulary: lowercase, no edge punctuation."""
    return text.strip(".,()[]\"'\u2019 ").lower()


def test_corpus_is_loaded() -> None:
    """The guards below all reduce to zero findings over an empty
    corpus, which is what a silent load failure produces."""
    assert len(_CORPUS_NAMES) > 500, len(_CORPUS_NAMES)
    assert _unclassified_names(), "no unclassified names; guard A is inert"


def test_ledger_glob_is_not_empty() -> None:
    """A parametrize over an empty list generates a single silent SKIP
    rather than a failure -- the exact silence this module exists to
    break. The swept pins cannot assert this for themselves, since a
    test that is never generated cannot complain, so it lives here."""
    assert _LEDGERS, f"no expected_since_*.toml under {_TOOLS}"


def _rules(ledger: Path) -> list[dict]:
    """The [[change]] table of one ledger."""
    # .get, matching compare.py. The open cycle's ledger is created at
    # release with no `change` key at all -- an empty [[change]] array
    # cannot be appended to in TOML -- so an absent key IS the empty
    # ledger here, not a malformed file. What stops that leniency from
    # hiding a typo'd table header lives in tests/v2/test_differential.py:
    # every other ledger must be non-empty, and the open one may define
    # nothing but `change`.
    return tomllib.loads(
        ledger.read_text(encoding="utf-8")).get("change", [])


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
        "fix(cjk-delimited-nickname)",      # the three compounds, whose
        "fix(cjk-fullwidth-paren-nickname)",  # lookaheads each carry
        "fix(cjk-comma-compound)",          # their own copy
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
        # looking, and claims 665 unclassified corpus names; this sees
        # it. Both are kept: the depth test gives the clearer message
        # for the naive spelling, and catches a widening toward a
        # script the corpora happen not to contain.
        reached = _claimed(regex)
        latin = [name for name in reached if name in set(_unclassified_names())]
        assert not latin, (
            f"{ledger.name}: {rule['issue']!r} declares the script table's "
            f"spans but claims {len(latin)} corpus names carrying no "
            f"classified codepoint at all, e.g. {latin[:3]}. A rule scoped "
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
    tools = Path(__file__).parents[2] / "tools" / "differential"
    spec = importlib.util.spec_from_file_location(
        "build_cjk_corpus", tools / "build_cjk_corpus.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checked_in = [json.loads(line) for line in
                  (tools / "corpus_cjk.jsonl")
                  .read_text(encoding="utf-8").splitlines()]
    assert checked_in == module.selected_names(), (
        "corpus_cjk.jsonl is stale: regenerate with "
        "`uv run python tools/differential/build_cjk_corpus.py`")


#: Which vocabulary constant each ledger rule's alternation is a hand
#: copy of. A roster rather than an inference: GLUED_HONORIFICS is a
#: SUBSET of SUFFIX_NOT_ACRONYMS (asserted at the bottom of
#: nameparser/config/suffixes.py), so "equals one of the two known sets"
#: would let a spaced rule that silently narrowed to exactly the glued
#: set pass by matching the other member -- a subset check wearing a
#: disguise, and the subset direction is precisely the one that removal
#: drift travels in.
#:
#: Keys are matched as substrings of a rule's `issue` and must select
#: exactly one entry. The full issue lists are the keys, not a bare
#: '#308': both 2.0 rules cite #308 while copying different constants.
_HONORIFIC_SOURCES: dict[str, set[str]] = {
    "cjk-honorific-suffix": SUFFIX_NOT_ACRONYMS,        # 1.4
    "#307/#308/#320": SUFFIX_NOT_ACRONYMS,              # 2.0, spaced
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
    entries of SUFFIX_NOT_ACRONYMS (#307) and of GLUED_HONORIFICS
    (#308) -- a toml cannot import them. Each expected set is DERIVED
    from the config by script membership (a classified codepoint
    anywhere in the entry), so adding a CJK honorific without widening
    the rule, or widening a rule with something the vocabulary does not
    ship, fails here.

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
    vocabulary: set[str]
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
}

#: Alternations that copy no vocabulary, so discovery must not demand a
#: source for them. Declared rather than inferred, on the principle
#: _SOURCES' None entries already set: an undeclared alternation is a
#: question someone answers in writing, not something to skip past.
_NOT_A_VOCABULARY_COPY = frozenset({
    frozenset({"^", " "}),      # the honorific rule's leading anchor
})

def _reaches_non_vocabulary(member: str, vocabulary: set[str]) -> list[str]:
    """Corpus text this member matches that is NOT a vocabulary entry.

    fullmatch against the vocabulary bounds what a member matches
    WITHIN those entries and says nothing about what it matches in a
    NAME. That gap was first filled with a tuple of eight hand-picked
    probe strings, and the tuple was defeated by a wider rule than the
    one it was added to stop: every entry this rule needs is three
    characters, so a member must accept some 3-character string and is
    unconstrained everywhere else -- "[acdf-uw-z]{3,}" covers `roz`,
    dodges all eight probes, and claims 563 of the corpus.

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
    assert used == set(_LATIN_ALTERNATION_SOURCES), (
        f"_LATIN_ALTERNATION_SOURCES keys matching no rule: "
        f"{sorted(set(_LATIN_ALTERNATION_SOURCES) - used)}")


#: A role a rule can claim, mapped to the vocabulary a name must carry
#: for that claim to be possible. Keyed on `fields` rather than on the
#: regex, which is the point: the two pins above discover hand copies
#: by their SYNTAX, so a copy that is not written as an alternation or
#: a character class is not undeclared, it is unseen. A brand-new rule
#: whose name_regex is "(?i)\b[a-z]{3}\b" with maiden fields passed
#: every check in this module while claiming 320 corpus names.
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
_FIELD_VOCABULARIES: dict[str, set[str]] = {
    "maiden": MAIDEN_MARKERS,
}


def _carries(name: str, vocabulary: set[str]) -> bool:
    """Whether a name contains a vocabulary entry.

    Whole-token for entries that have token boundaries, substring for
    the ones that do not: 旧姓 is written against the name it marks.
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
    it cannot be explaining a marker on a name that has none -- which
    is exactly the shape every widening in this PR's review took.
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
