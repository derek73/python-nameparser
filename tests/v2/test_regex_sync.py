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


def _declared_spans(name_regex: str) -> set[tuple[int, int]]:
    """The \\uXXXX-\\uXXXX span pairs a rule's character class declares."""
    return {
        (int(lo, 16), int(hi, 16))
        for lo, hi in re.findall(r"\\u([0-9A-Fa-f]{4})-\\u([0-9A-Fa-f]{4})",
                                 name_regex)}


def _expected_bmp_spans() -> set[tuple[int, int]]:
    """What a full CJK character class in the toml must declare: the
    table's BMP spans plus the sanctioned extras."""
    return {span
            for spans in _policy._SCRIPT_RANGES.values()
            for span in spans
            if span[1] <= 0xFFFF} | set(_SANCTIONED_EXTRAS)


def test_differential_cjk_rule_matches_the_script_ranges() -> None:
    """The CJK rule in tools/differential/expected_changes.toml hand-
    copies the script spans from _policy._SCRIPT_RANGES into a character
    class. A TOML file cannot import the constant, so this is the one
    copy with no possible alternative -- and the one whose divergence
    is quietest, because the harness is run by hand rather than in CI.

    Both failure directions matter, which is why this compares sets
    rather than checking coverage. A span MISSING from the class turns
    an intended #271/#272 change into an UNEXPLAINED diff (a release
    blocker for the wrong reason); a span that should not be there
    silently classifies a real regression as intended, which is the
    failure the whole harness exists to prevent.

    Every table entry is in scope. The rule covered HAN and HANGUL
    alone while the kana members existed only for classification, but
    #272 gave HIRAGANA a default order entry and made the kana blocks
    part of the same first/middle/last diff shape the rule explains,
    so scoping it by issue no longer draws a real line. Comparing
    against the whole table is also the stronger promise: a script
    added to _SCRIPT_RANGES for ANY reason fails here until someone
    decides, in writing, whether the rule should cover it.

    Han's astral block is the single exception, out of scope on both
    sides. The rule omits it deliberately -- no corpus name reaches
    it, see the comment there -- so the comparison runs over the BMP
    spans only.

    The rule is also WIDER than the table by exactly one span, which
    the equality has to know about or it would just fail forever. The
    halfwidth middle dot U+FF65 changes parses without being
    classified as anything: tokenize separates on it, so a halfwidth
    transcription splits where 1.4 kept one token, while halfwidth
    kana stays out of _SCRIPT_RANGES on purpose. U+00B7 -- the
    context-sensitive 间隔号 (#298) -- also changes parses yet is
    deliberately NOT an extra: its flank guard means every name it
    can change matches the class through a flanking character
    already, and a B7 span's only actual effect would be letting the
    rule claim diffs on punt-volat Latin names (Gal·la), pre-excusing
    a regression on exactly the guarded class. Naming the sanctioned
    span here rather than relaxing the comparison to a subset check
    is what keeps the pin honest in both directions: an unsanctioned
    source of divergence still fails, and each sanctioned difference
    has to be written down to exist.
    """
    toml_path = (Path(__file__).parents[2] / "tools" / "differential"
                 / "expected_changes.toml")
    rules = tomllib.loads(toml_path.read_text())["change"]
    matched = [r for r in rules
               if "#271" in r["issue"] or "#272" in r["issue"]]
    assert len(matched) == 1, (
        f"expected exactly one CJK rule in {toml_path.name}, "
        f"found {len(matched)}")
    # A new table entry must force an explicit decision rather than
    # quietly widening (or failing to widen) the rule above.
    assert set(_policy._SCRIPT_RANGES) == {
        Script.HAN, Script.HANGUL, Script.HIRAGANA, Script.KATAKANA}, (
        "a Script joined _SCRIPT_RANGES: decide whether the "
        f"differential rule in {toml_path.name} should cover it, then "
        "update this assertion")
    declared = _declared_spans(matched[0]["name_regex"])
    # the extras must stay UNclassified, or they belong in the table
    for xlo, xhi in _SANCTIONED_EXTRAS:
        assert not any(lo <= xhi and xlo <= hi
                       for spans in _policy._SCRIPT_RANGES.values()
                       for lo, hi in spans), (
            f"U+{xlo:04X}-U+{xhi:04X} is classified now; drop it "
            "from _SANCTIONED_EXTRAS")
    expected = _expected_bmp_spans()
    assert declared == expected, (
        f"{toml_path.name}'s CJK name_regex declares {sorted(declared)}; "
        f"_SCRIPT_RANGES' BMP spans are {sorted(expected)}")


def test_every_span_bearing_rule_matches_the_script_ranges() -> None:
    """Auto-discovered pin for every FURTHER hand copy of the script
    spans in the toml: any rule whose character class declares spans
    intersecting _SCRIPT_RANGES must declare the whole expected class
    (table BMP spans + sanctioned extras). The compound rules'
    require-a-classified-codepoint lookaheads exist so their trigger
    sets alone (delimiters; a comma) cannot claim a Latin name's
    regression -- and each such lookahead is a copy nothing else
    checks. Discovery replaces a hand-maintained slug roster: a new
    compound rule's copy is pinned by existing here, not by an author
    remembering to enroll it. Rules whose spans touch OTHER scripts
    (Cyrillic, say) are out of scope and skipped by the intersection
    test.

    Selection note for future rule authors: the canonical-rule pin
    above selects by the literal '#271'/'#272' substrings and asserts
    uniqueness -- compound slugs must avoid them.
    """
    toml_path = (Path(__file__).parents[2] / "tools" / "differential"
                 / "expected_changes.toml")
    rules = tomllib.loads(toml_path.read_text())["change"]
    table_spans = _expected_bmp_spans()
    checked = []
    for rule in rules:
        regex = rule.get("name_regex")
        if not isinstance(regex, str):
            continue
        declared = _declared_spans(regex)
        if not declared & table_spans:
            continue
        checked.append(rule["issue"])
        assert declared == table_spans, (
            f"{rule['issue']!r} declares {sorted(declared)}; expected "
            f"{sorted(table_spans)}")
    # the canonical rule plus both compound rules, today -- if this
    # count drops, a hand copy fell out of discovery's reach
    assert len(checked) >= 3, checked
    # the delimiter compound's trigger set is its own decision surface
    nickname = [r for r in rules
                if "cjk-delimited-nickname" in r["issue"]]
    assert len(nickname) == 1
    assert "[\u300C\u300D\u300E\u300F\u30FB\uFF65]" in nickname[0][
        "name_regex"] or "[「」『』・･]" in nickname[0]["name_regex"], (
        "the compound rule's delimiter set changed; decide deliberately")


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
