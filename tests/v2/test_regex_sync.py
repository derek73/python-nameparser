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
the last three tests reach outside the package altogether -- two to a
TOML file that could not import a Python constant if it wanted to,
one to a generated corpus whose generator can, and must stay run.
"""
import importlib.util
import json
import re
import tomllib
from pathlib import Path

import pytest

from nameparser.config import regexes as _config
from nameparser._pipeline import _assign, _post_rules, _tokenize, _vocab
from nameparser import _policy
from nameparser._policy import Script
from nameparser import _render
from nameparser.config.suffixes import GLUED_HONORIFICS, SUFFIX_NOT_ACRONYMS


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
# classified flanking character already. Single-sourced: both span
# pins below read this set.
_SANCTIONED_EXTRAS = frozenset({(0xFF65, 0xFF65)})

_TOOLS = Path(__file__).parents[2] / "tools" / "differential"

#: Every baseline's ledger, swept rather than named. #332 added a second
#: file whose four hand copies went unchecked because the pins below
#: named the 1.4 one by filename, and the count grows by one per
#: release -- see AGENTS.md's release step 8.
_LEDGERS = sorted(_TOOLS.glob("expected_since_*.toml"))


def test_ledger_glob_is_not_empty() -> None:
    """A parametrize over an empty list generates zero tests and passes
    vacuously -- the exact silence this module exists to break. The
    swept pins cannot assert this for themselves, so it lives here."""
    assert _LEDGERS, f"no expected_since_*.toml under {_TOOLS}"


def _rules(ledger: Path) -> list[dict]:
    """The [[change]] table of one ledger."""
    return tomllib.loads(ledger.read_text(encoding="utf-8"))["change"]


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
    hypothetical: this file's own convention mixes both spellings (see
    the interpunct note in expected_since_2.0.0.toml), and the ledgers'
    non-span classes are written literally.

    The consequence is worst in the widening direction the equality is
    supposed to cover. Appending "a-z" to a pinned CJK class passes both
    that equality and compare.validate_rules' sentinel probe, and lets
    the rule claim every Latin diff in the corpus as intended -- exactly
    the regression-absorbing failure the harness exists to prevent.

    So: a class that declares any span must declare NOTHING else.
    Classes carrying no spans (the delimiter sets) are a different
    decision surface and are out of scope here.
    """
    return [rest
            for body in re.findall(r"\[([^\]]*)\]", name_regex)
            if _SPAN.search(body)
            for rest in [_SPAN.sub("", body)]
            if rest]


def _expected_bmp_spans() -> set[tuple[int, int]]:
    """What a full CJK character class in the toml must declare: the
    table's BMP spans plus the sanctioned extras."""
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

    Han's astral block is the single exception, out of scope on both
    sides -- no corpus name reaches it, see the comment there -- so the
    span comparisons run over the BMP spans only.

    The rules are also WIDER than the table by exactly one span, which
    the equality has to know about or it would just fail forever. The
    halfwidth middle dot U+FF65 changes parses without being classified
    as anything: tokenize separates on it, so a halfwidth transcription
    splits where 1.4 kept one token, while halfwidth kana stays out of
    _SCRIPT_RANGES on purpose. U+00B7 -- the context-sensitive 间隔号
    (#298) -- also changes parses yet is deliberately NOT an extra: its
    flank guard means every name it can change matches the class through
    a flanking character already, and a B7 span's only actual effect
    would be letting a rule claim diffs on punt-volat Latin names
    (Gal·la), pre-excusing a regression on exactly the guarded class.
    Naming the sanctioned span rather than relaxing the comparisons to a
    subset check is what keeps the pins honest in both directions: an
    unsanctioned source of divergence still fails, and each sanctioned
    difference has to be written down to exist. The guard below is what
    makes "sanctioned" mean something -- an extra that BECOMES
    classified belongs in the table, not in the exception list.

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
}

#: The leading `fix(...)`/`feat(...)` tag of a rule's `issue`, which is
#: what _SPAN_BEARING_RULES names rules by. Unique within each ledger
#: among span-bearing rules (asserted below), and stable across the
#: prose that follows it.
_ISSUE_TAG = re.compile(r"^[a-z]+\([^)]*\)")


def _tag(issue: str) -> str:
    match = _ISSUE_TAG.match(issue)
    assert match, f"rule issue does not open with a fix(...) tag: {issue!r}"
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
    none, so neither a per-file `== 1` nor a global one is true; what is
    true is that EVERY such rule must carry the sanctioned trigger set,
    and that at least one must exist somewhere or this is checking
    nothing."""
    found = []
    for ledger in _LEDGERS:
        for rule in _rules(ledger):
            if "cjk-delimited-nickname" not in rule["issue"]:
                continue
            found.append(f"{ledger.name}: {rule['issue']}")
            assert _NICKNAME_DELIMITERS in rule.get("name_regex", ""), (
                f"{ledger.name}: the compound rule's delimiter set "
                f"changed; decide deliberately, then update "
                f"_NICKNAME_DELIMITERS")
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
#: Still unreadable to it, by construction: an alternation with a
#: nested group, one with a "|" or paren inside a character class, and
#: a single-member "group". The first two surface through the STALE
#: half of the roster check below -- the rule stops matching its key --
#: rather than passing quietly.
_ALTERNATION = re.compile(r"\((?:\?:|(?!\?))((?:[^()|]+\|)+[^()|]+)\)")


def _cjk_alternations(name_regex: str) -> list[set[str]]:
    """Every alternation in a rule with a script-classified member."""
    has_classified = _policy._script_matcher(*_policy._SCRIPT_RANGES)
    return [members
            for body in _ALTERNATION.findall(name_regex)
            for members in [set(body.split("|"))]
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
        f"deleted rule left its entry behind -- drop it -- or that rule's "
        f"alternation is no longer parseable by _ALTERNATION (a nested "
        f"group, or a '|' inside a character class), which is how a "
        f"still-present hand copy silently leaves this pin.")
