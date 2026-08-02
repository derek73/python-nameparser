"""Immutable behavior configuration for the 2.0 API.

Layering: imports nameparser._types only (enforced by
tests/v2/test_layering.py).
"""
from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from typing import Any

from nameparser._types import Role, _guarded_getstate, _guarded_setstate


class PatronymicRule(StrEnum):
    """Stable rule names (API); implementations live in the pipeline.
    Enable via ``Policy(patronymic_rules={...})`` or, more commonly, a
    locale pack (:mod:`nameparser.locales`)."""

    #: East Slavic formal order: "Sidorov Ivan Petrovich"
    #: (family, given, patronymic) is detected by the patronymic
    #: ending and reordered. Enabled by locales.RU.
    EAST_SLAVIC = "east-slavic"
    #: Turkic patronymic markers: a standalone "oglu"/"qizi"/"kyzy"
    #: (etc.) binds to the preceding name as a patronymic. Enabled by
    #: locales.TR_AZ.
    TURKIC = "turkic"


class Script(StrEnum):
    """Writing systems the parser can key SCRIPT-CONDITIONAL behavior
    on: per-script name order (``Policy.script_orders``) and
    unspaced-name segmentation (``Policy.segment_scripts``). The rule
    that admits these (amendment 2026-07-27): script-conditional
    behavior only where the script itself determines the convention --
    Latin-script input is never affected. The codepoint table backing
    these members is internal."""

    #: Chinese Hanzi -- and Japanese Kanji: a pure-Han string cannot
    #: say which language it is, which is fine for ORDER (both write
    #: family-first natively) and exactly why Han SEGMENTATION is
    #: opt-in, per language: locales.ZH brings the Chinese surname
    #: list, locales.JA activates the same stage for a pluggable
    #: segmenter to divide kanji names with.
    HAN = "han"
    #: Korean Hangul (precomposed syllables). Unambiguously Korean.
    HANGUL = "hangul"
    #: Japanese hiragana. Never transcribes foreign names, so a mixed
    #: kanji+kana token (高橋みなみ) is Japanese and resolves HERE --
    #: this member is the carrier key in script_orders/segment_scripts.
    HIRAGANA = "hiragana"
    #: Japanese katakana. A PURE-katakana token is predominantly a
    #: transcribed foreign name in its original order (マイケル), so
    #: no default behavior keys on this member; it exists so the
    #: classifier can name what it deliberately declines.
    KATAKANA = "katakana"


# Codepoint ranges per Script (#271). This integer table is the single
# source of truth for what a script covers; every matcher DERIVES from
# it -- _pipeline/_vocab.py compiles its per-script patterns from it,
# and it is importable from the pipeline and the locale packs alike,
# so the packs' predicates build on it too, through _script_matcher
# below (the table lives here rather than in the pipeline because
# packs must not import the pipeline).
# HAN: the ideographic iteration mark U+3005 and the shime mark
# U+3006, the URO plus Extension A, the compatibility block, and the
# supplementary-plane block
# (Ext B-I + CJK Compat Ideographs Supplement, 0x20000-0x323AF) --
# rare surnames are the biggest real source of supplementary-plane
# hanzi in personal names (e.g. 𠮷田's 𠮷, U+20BB7), so leaving them
# out silently mis-orders those names; unassigned gaps inside the span
# are harmless, since no real name contains an unassigned codepoint.
# U+3005 々 is the block-vs-Script case, running the OPPOSITE way to
# U+30FB below: 々 already IS Script=Han under UAX #24 (Scripts.txt
# reads `3005 ; Han`), but it sits in CJK Symbols and Punctuation,
# outside every CJK ideograph block this table spans -- so a
# singleton entry was what a BLOCK table needed to reach a character
# the Script property would have classified correctly for free. It
# earns the reach: 々 repeats the preceding kanji and appears only
# inside Han-written names -- 佐々木 (Sasaki, a top-20 Japanese
# surname), 野々村, 奈々. Omitting it made 佐々木 a mixed-script token:
# the name reversed and never gated into segmentation.
# U+3006 〆 (the shime mark) extends that singleton to a two-codepoint
# span on a DIFFERENT justification: unlike 々, 〆 is Script=Common
# under UAX #24, so this is the table deliberately reaching PAST the
# Script property, not around a block boundary -- justified because
# within personal names 〆 appears solely in Japanese surnames (〆木
# Shimeki, 〆谷 Shimetani, 〆野) -- its other uses (the envelope
# closing mark, 〆切) never reach a name parser -- and it appears in
# no other script's names.
# HANGUL: precomposed syllables only -- modern Korean
# text never writes names as bare jamo.
# HIRAGANA/KATAKANA (#272): the two kana blocks, each in full. There
# IS a supplementary-plane kana repertoire (Kana Supplement, Kana
# Extended-A/B, Small Kana Extension, U+1AFF0-U+1B16F, a few hundred
# assigned codepoints -- no exact count here, it moves with the
# Unicode version) but none of it is WORTH chasing the way Han's astral
# block is: those codepoints are hentaigana and other archaic/
# phonetic-extension forms no modern Japanese name uses, unlike
# supplementary Han, which real surnames genuinely need. The Katakana
# Phonetic Extensions block (U+31F0-U+31FF, 16 small katakana for Ainu
# transcription) is excluded for the same reason -- no modern Japanese
# personal name uses them. Halfwidth kana (U+FF65-U+FF9F, including
# the voiced/semi-voiced sound marks U+FF9E/U+FF9F) is likewise
# deliberately excluded -- legacy bank/CSV data uses it, but it is a
# separate normalization problem; #272 Task 2b's separator handling
# only touches the halfwidth DOT (U+FF65), not the rest of that block.
# This table classifies by Unicode BLOCK, not the UAX #24 Script
# property: U+30A0, U+30FB (the middle dot), and U+30FC (the
# prolonged sound mark) all carry Script=Common under UAX #24, and the
# four kana voicing marks U+3099-U+309C split two and two -- U+3099
# and U+309A are the COMBINING forms (Script=Inherited), U+309B and
# U+309C the spacing ones (Script=Common) -- yet every one of them is
# needed here, and block membership, not the Script property, is what
# puts them in range. The katakana block's upper end (U+30FF) takes in
# the middle dot U+30FB, kept rather than carved out for a smaller
# reason than it looks: tokenize (#272 Task 2b) turns U+30FB into a
# token separator, so no real parse shows the classifier a string
# containing one. It is kept so that a DIRECT whole-string call --
# effective_script (_pipeline/_vocab.py) on "マイケル・ジャクソン", which
# the unit tests (tests/v2/pipeline/test_vocab.py) make -- still
# classifies instead of returning None. The ranges below must
# stay mutually disjoint: single_script (_pipeline/_vocab.py) returns
# the FIRST covering entry (dict iteration order), so an overlapping
# future script would make the result order-dependent instead of
# well-defined.
_SCRIPT_RANGES: dict[Script, tuple[tuple[int, int], ...]] = {
    Script.HAN: ((0x3005, 0x3006), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
                 (0xF900, 0xFAFF), (0x20000, 0x323AF)),
    Script.HANGUL: ((0xAC00, 0xD7A3),),
    Script.HIRAGANA: ((0x3040, 0x309F),),
    Script.KATAKANA: ((0x30A0, 0x30FF),),
}

#: The Japanese repertoire: the three scripts Japanese names draw on.
#: The kana license (_pipeline/_vocab.py's effective_script), the ja
#: pack's DEVIATES, and the segmenter adapter's repertoire guard all
#: quantify over this one union (HANGUL simply omitted).
_JA_SCRIPTS = (Script.HAN, Script.HIRAGANA, Script.KATAKANA)

#: Scripts whose characters cannot BE an initial. The criterion is
#: orthographic CONVENTION, not what a character is: does the writing
#: tradition abbreviate a given name to ONE character plus a period,
#: the way "J." stands in for "John"? Han, hangul and kana have no
#: such convention, so a lone punctuated 씨/様/김 is not a shortened
#: name and the veto has nothing to veto there. Do not restate that
#: phonologically ("letters, not syllables") -- Devanagari is an
#: abugida and Arabic an abjad, neither has letters in that sense, and
#: both abbreviate, so should Script.CYRILLIC or Script.DEVANAGARI
#: ever be added neither belongs here; their initials are real and
#: pinned as such ("А. С. Пушкин", "م. الفارسي").
#:
#: Enumerated rather than derived from _SCRIPT_RANGES' keys: the
#: Script enum admits a member so that SOME behavior may key on it
#: (see Script), on assorted grounds -- KATAKANA is in it so the
#: classifier can name what it deliberately declines, and neither
#: DEFAULT_SCRIPT_ORDERS nor segment_scripts' default mentions it.
#: Membership therefore settles nothing about abbreviation: the four
#: coinciding today is what has been implemented, not a property of
#: the enum, and a new member must not inherit this answer.
#:
#: Decide it from CLDR rather than from the script's typology: count
#: the LOCALE-AUTHORED namePattern entries in common/main/<locale>.xml's
#: personNames block that produce an initial. ja and ko author 29 and
#: 32 patterns and use one in none of them; ru uses initials in 7 of 39
#: ("{given-initial} {given2-initial} {surname}"); zh abbreviates but
#: overrides initialPattern to "{0}", no period, which is why the
#: period is part of the test above. Do NOT read initialPattern alone
#: -- root defaults it to "{0}." and nearly every locale inherits it,
#: so it reports a period convention for locales that have none.
#: Measured 2026-08-02: th is 0 of 20, so Thai (#317) belongs here
#: once it earns a member.
_NO_INITIALS = (Script.HAN, Script.HANGUL, Script.HIRAGANA,
                Script.KATAKANA)


def _script_matcher(*scripts: Script,
                    whole: bool = False) -> Callable[[str], bool]:
    """A predicate over strings, compiled once from the union of the
    named scripts' spans in _SCRIPT_RANGES. whole=False: True when the
    string CONTAINS any such character -- DEVIATES' contract, where
    over-declaring is the gate's safe direction. whole=True: True when
    the string is non-empty and consists WHOLLY of such characters --
    the ja adapter's repertoire guard and _vocab's script
    classifiers. Meant to be called at MODULE
    scope: "compiled once" is per matcher, and each call compiles a
    fresh pattern. The compiled pattern lives in the closure ON
    PURPOSE, and the compilation lives HERE rather than in a pack-
    local closure: tests/v2/test_locales.py classifies any pack module
    holding a module-level re.Pattern as a marker pack needing rotator
    branch coverage, and its registry gate goes further -- a pack that
    so much as IMPORTS re without exposing such a pattern fails
    "imports re but exposes no module-level pattern" -- so a
    range-declaring pack must not import re at all; predicates built
    here keep the packs invisible to that sweep by construction (and
    spare _vocab's derived matchers a declaration row in
    tests/v2/test_regex_sync.py's completeness sweep, which scans the
    pipeline modules (plus _render) for private module-level
    patterns)."""
    if not scripts:
        raise ValueError("_script_matcher needs at least one Script")
    cls = "".join(f"\\U{lo:08x}-\\U{hi:08x}"
                  for script in scripts
                  for lo, hi in _SCRIPT_RANGES[script])
    # one pattern serves both modes: fullmatch of [cls]+ is wholly-of,
    # and search over [cls]+ is exactly contains-any
    pattern = re.compile(f"[{cls}]+")
    match = pattern.fullmatch if whole else pattern.search

    def matcher(text: str) -> bool:
        return match(text) is not None
    return matcher


# Order-spec constants (#270). Each reads as its contents because roles
# are named given/family, not first/last.

#: Western order (the default): the first word of positional input is
#: the given name, the last is the family name, everything between is
#: middle. One of the three valid ``Policy(name_order=...)`` values.
GIVEN_FIRST = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)
#: Family name first, given name second, remaining words middle
#: (e.g. Hungarian, or East Asian order). One of the three valid
#: ``Policy(name_order=...)`` values.
FAMILY_FIRST = (Role.FAMILY, Role.GIVEN, Role.MIDDLE)
#: Family name first, given name LAST, words between middle
#: (e.g. Vietnamese full-name order). One of the three valid
#: ``Policy(name_order=...)`` values.
FAMILY_FIRST_GIVEN_LAST = (Role.FAMILY, Role.MIDDLE, Role.GIVEN)

_ORDER_CONSTANT_NAMES: dict[tuple[Role, ...], str] = {
    GIVEN_FIRST: "GIVEN_FIRST",
    FAMILY_FIRST: "FAMILY_FIRST",
    FAMILY_FIRST_GIVEN_LAST: "FAMILY_FIRST_GIVEN_LAST",
}


def _order_repr(value: tuple[Role, ...]) -> str:
    # Unreachable via Policy's constructor (its __post_init__ restricts
    # name_order to the three named orders) but REACHABLE via
    # PolicyPatch, which defers name_order validation to apply time by
    # design -- value may hold non-Role, even unhashable, elements. A
    # value smuggled in through __setstate__ (which validates layout,
    # not values) can also be a non-tuple container or not iterable at
    # all. repr must never raise, so the named-lookup path is taken
    # only for a TUPLE whose every element is confirmed a Role;
    # everything else renders via repr(value). (The annotation states
    # the Policy-side truth; the PolicyPatch call site passes
    # getattr-Any.)
    if isinstance(value, tuple) and all(isinstance(r, Role) for r in value):
        named = _ORDER_CONSTANT_NAMES.get(value)
        if named is not None:
            return named
        return "(" + ", ".join(r.name for r in value) + ")"
    return repr(value)


# Single source for the migration hint raised by both Policy and
# PolicyPatch when patronymic_rules gets a non-iterable (True is the
# likeliest wrong value -- v1's flag was a bool that enabled BOTH rules).
_PATRONYMIC_MIGRATION_HINT = (
    "v1's patronymic_name_order=True enabled both rules -- "
    "patronymic_rules={PatronymicRule.EAST_SLAVIC, "
    "PatronymicRule.TURKIC} (or pick one via "
    "parser_for(locales.RU) / locales.TR_AZ)"
)

#: Policy.script_orders' default: wholly-Han, wholly-Hangul, and
#: kana-licensed names read family-first. Public and named so opting
#: out or extending reads against a documented value (the
#: DEFAULT_NICKNAME_DELIMITERS precedent). The HAN entry is safe
#: WITHOUT knowing Chinese from Japanese: both write family-first in
#: native script -- the languages differ, the convention doesn't.
#: HIRAGANA joins by the same rule as HANGUL (the kana license,
#: amendment 2026-07-29): a mixed Han-and-kana token cannot be
#: Chinese (it contains kana) and is not a foreign transcription
#: (transcriptions are katakana-only), so it is Japanese, written
#: family-first -- another default change in a minor, release-log-
#: classified fix, #294's mechanism. KATAKANA is deliberately absent:
#: a PURE-katakana token is predominantly a transcribed foreign name
#: kept in its source (usually given-first) order, so nothing should
#: default on it. Canonical form: sorted (Script, order) pairs,
#: matching the field's storage.
DEFAULT_SCRIPT_ORDERS: tuple[
    tuple[Script, tuple[Role, Role, Role]], ...] = (
    (Script.HAN, FAMILY_FIRST),
    (Script.HANGUL, FAMILY_FIRST),
    (Script.HIRAGANA, FAMILY_FIRST),
)

#: Policy.nickname_delimiters' default. Public and named so
#: customizations read as set math against a documented value -- e.g.
#: ``DEFAULT_NICKNAME_DELIMITERS | {("｟", "｠")}`` -- instead of a
#: rebuilt literal the user had to go discover. The v1 trio (straight
#: quotes + parentheses) plus the typographic conventions (#273):
#: smart quotes, low-high and right-right quotes, guillemets both
#: directions, CJK corner brackets, fullwidth parentheses. Curly
#: SINGLE quotes are deliberately absent: U+2019 is the typographic
#: apostrophe ("O’Connor").
DEFAULT_NICKNAME_DELIMITERS = frozenset({
    ("'", "'"), ('"', '"'), ("(", ")"),      # v1 trio
    ("“", "”"),                              # smart quotes (en, zh)
    ("„", "“"),                              # low-high (de, pl, cs, hu)
    ("”", "”"),                              # right-right (sv, fi)
    ("«", "»"),                              # guillemets (fr, ru, it, el)
    ("»", "«"),                              # reversed guillemets (de alt)
    ("「", "」"), ("『", "』"),                # CJK corner brackets (ja)
    ("（", "）"),                             # fullwidth parentheses (CJK)
})


def _reject_bare_string_order(value: object, field_name: str) -> None:
    # tuple("gmf") would be ("g", "m", "f") -- catch the bare string
    # with the same TypeError every other iterable field raises.
    # Single-sourced: called from Policy AND PolicyPatch __post_init__.
    # field_name is REQUIRED, with no name_order default: script_orders'
    # values obey the same rule (via _validated_order), and a defaulted
    # caller that forgot to pass it would silently name the wrong field.
    if isinstance(value, str):
        raise TypeError(
            f"{field_name} must be an iterable of three Roles, "
            f"not a bare string: {value!r}"
        )
    # A {Role: position} dict iterates to the right three Roles in the
    # right order, so it would be accepted -- harmlessly today, since
    # the result is checked against the three exported orders anyway.
    # Guarded regardless: "iterating this yields something plausible
    # but not what you wrote" is one bug class, and leaving one field
    # out of it is how the PolicyPatch hole happened.
    if isinstance(value, Mapping):
        raise TypeError(
            f"{field_name} must be an iterable of three Roles, not a "
            f"mapping: {value!r}"
        )
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"{field_name} must be an iterable of three Roles, not "
            f"{type(value).__name__} -- decode first, e.g. "
            f"raw.decode('utf-8')"
        )


def _reject_str_and_mapping(value: object, field_name: str) -> None:
    """The two shapes that iterate into something plausible but wrong.

    A bare string yields its characters (and '' yields nothing at all,
    so it silently stored an empty set); a Mapping yields only its keys.
    Both used to be accepted here, storing a value the caller never
    wrote. Lexicon._normset rejects the same two by name -- the wording
    is deliberately parallel, since a caller who hits one field's guard
    should recognize the other's.
    """
    if isinstance(value, str):
        raise TypeError(
            f"{field_name} must be an iterable, not a bare string: "
            f"{value!r}"
        )
    # bytes iterate to ints, so the entry check would report a byte
    # value and name neither the cause nor the fix; same decode hint
    # Lexicon and parse() give.
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"{field_name} must be an iterable of strings, not "
            f"{type(value).__name__} -- decode first, e.g. "
            f"raw.decode('utf-8')"
        )
    if isinstance(value, Mapping):
        # Name the way out, not just the harm. "contributes only its
        # keys" is no help for the two mappings people actually pass:
        # {} (meant as an empty set -- Python's oldest trap, and the
        # keys story does not apply because there are none), and an
        # {open: close} dict, whose keys are only half the pair.
        raise TypeError(
            f"{field_name} must be an iterable, not a mapping: "
            f"{value!r}. A mapping yields only its keys -- write "
            f"frozenset() for an empty set, or .items() if this is an "
            f"{{open: close}} pair mapping"
        )


def _require_iterable(value: Iterable[Any], field_name: str,
                      expected: str = "an iterable") -> Iterable[Any]:
    """Probe a value's iterability and return its iterator, raising a
    TypeError naming the field if it has none. `expected` carries the
    field's own phrasing ("a mapping of Script to order"); the default
    suits every plain iterable field.

    Probing with iter() is what makes the message possible: a
    non-iterable (an int, a bool, ...) is named here, matching the
    treatment patronymic_rules already gets, instead of a bare "'int'
    object is not iterable" surfacing from whatever tuple()/frozenset()
    happens to run first. It is ALSO the reason callers consume the
    returned iterator OUTSIDE any try of their own: an exception raised
    inside a caller's generator while it is being consumed is the
    caller's own error, and must propagate untouched rather than be
    rewritten as a shape complaint about the field.
    """
    try:
        return iter(value)
    except TypeError:
        raise TypeError(
            f"{field_name} must be {expected}, got {value!r}"
        ) from None


def _validated_order(value: Iterable[Any],
                     field_name: str) -> tuple[Role, Role, Role]:
    """name_order's element/permutation check, single-sourced so
    script_orders values obey the identical rule (only the three
    exported orders have implemented assignment semantics)."""
    _reject_bare_string_order(value, field_name)
    order = tuple(_require_iterable(value, field_name))
    # Sole rejection point for plain-string tuples: Role is a StrEnum,
    # so the named-order membership check below compares EQUAL for
    # ("given", "middle", "family") -- do not remove this loop as
    # redundant.
    for element in order:
        if not isinstance(element, Role):
            raise TypeError(
                f"{field_name} elements must be Role members, "
                f"got {element!r}"
            )
    # Only the three exported orders have implemented assignment
    # semantics; the unnamed permutations would silently misassign.
    # Pre-2.0 strictness is free -- relaxing later is compatible.
    if order not in (GIVEN_FIRST, FAMILY_FIRST,
                     FAMILY_FIRST_GIVEN_LAST):
        raise ValueError(
            f"{field_name} must be one of the exported orders, got "
            f"{order!r}; use GIVEN_FIRST, FAMILY_FIRST, or "
            f"FAMILY_FIRST_GIVEN_LAST"
        )
    return order  # type: ignore[return-value]  # length checked above


def _validated_script(key: object) -> Script:
    """Coerce one Script key, with the message every script-keyed field
    shares. Single-sourced deliberately: script_orders and the
    script-keyed fields that follow it must not each grow their own
    wording for the same lookup."""
    try:
        # Enum lookup accepts ANY value at runtime and answers a
        # non-member with ValueError -- which is the contract here, and
        # the taxonomy's rule for a failed enum lookup whatever the
        # input type was (stdlib EnumType precedent).
        return Script(key)  # type: ignore[arg-type]
    except ValueError:
        valid = ", ".join(v.value for v in Script)
        raise ValueError(
            f"unknown script {key!r}; valid scripts: {valid}"
        ) from None


def _validated_script_orders(
        value: object) -> tuple[tuple[Script, tuple[Role, Role, Role]], ...]:
    """Policy.script_orders' whole check, from raw input to canonical
    storage. script_orders is the one MAPPING-shaped field, so the
    guards read inverted from every other one here: a Mapping is what
    the caller SHOULD pass, and a bare string is the shape that would
    otherwise iterate into plausible-looking garbage."""
    if isinstance(value, str):
        raise TypeError(
            f"script_orders must be a mapping of Script to order, "
            f"not a bare string: {value!r}"
        )
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"script_orders must be a mapping of Script to order, "
            f"not {type(value).__name__} -- decode first, "
            f"e.g. raw.decode('utf-8')"
        )
    raw = value.items() if isinstance(value, Mapping) else value
    raw_iter = _require_iterable(
        raw, "script_orders",  # type: ignore[arg-type]
        "a mapping of Script to order")
    canonical: dict[Script, tuple[Role, Role, Role]] = {}
    for entry in raw_iter:
        try:
            key, order = entry
        except (TypeError, ValueError):
            raise TypeError(
                f"script_orders entries must be (Script, order) "
                f"pairs, got {entry!r}"
            ) from None
        canonical[_validated_script(key)] = _validated_order(
            order, "script_orders")
    # Sorted pairs, not a dict: Policy is hashable, and two
    # differently-written but equivalent tables must converge (the
    # capitalization_exceptions precedent).
    return tuple(sorted(canonical.items()))


def _validated_segment_scripts(value: object) -> frozenset[Script]:
    """segment_scripts' check: an iterable of Script members (or
    their string values), coerced via _validated_script so the
    unknown-script wording stays single-sourced."""
    _reject_str_and_mapping(value, "segment_scripts")
    script_iter = _require_iterable(
        value, "segment_scripts",  # type: ignore[arg-type]
        "an iterable of Script members")
    return frozenset(_validated_script(s) for s in script_iter)


def _canonical_script_pair(pair: Iterable[Any]) -> tuple[Any, ...]:
    """Hashability-only canonicalization of one PolicyPatch
    script_orders entry: tuple-ize the pair AND the order value inside
    it. Shallow was not enough -- a {Script: [Role, ...]} patch stored
    the list, and hash() then raised far from the construction site,
    the same failure name_order's canonicalization exists to prevent.
    A malformed entry is still tuple-ized (that is the hashability
    floor); its CONTENTS are left exactly as written so Policy quotes
    the caller's own value when it raises at apply time."""
    out = tuple(pair)
    if len(out) != 2:
        return out                          # not a (Script, order) pair
    key, value = out
    # str/bytes are iterable, so tuple() would shred exactly the two
    # values whose deferred errors ("not a bare string", the decode
    # hint) need to quote what the caller wrote.
    if isinstance(value, (str, bytes, bytearray, memoryview)):
        return out
    try:
        return (key, tuple(value))
    except TypeError:
        return out                          # non-iterable order value


def _canonical_patch_script_orders(value: object) -> object:
    """Canonicalize a PolicyPatch.script_orders value for hashability
    without validating it: malformed shapes are stored so Policy can
    quote them at apply time; a caller-generator's own exception
    propagates from the UNGUARDED materialization below (deferring is
    impossible once a one-shot iterator is consumed)."""
    # Excluded HERE rather than delegated: a string's elements are
    # themselves tuple-izable, so no TypeError ever fires to signal
    # "leave this alone" -- "han" would shred to (("h",), ("a",),
    # ("n",)) and Policy's bare-string message would have nothing left
    # to quote. bytes shred the same way, into ints.
    if isinstance(value, (str, bytes, bytearray, memoryview)):
        return value                  # deferred whole: Policy's guards quote it
    # Any, not object: a patch defers validation, so anything a caller
    # wrote can arrive here, and the probe below is precisely the
    # runtime question mypy has no way to answer statically.
    pairs: Any = value.items() if isinstance(value, Mapping) else value
    try:
        pairs_iter = iter(pairs)      # probe only
    except TypeError:
        return value                  # non-iterable: defer to apply
    items = tuple(pairs_iter)         # UNGUARDED: caller errors propagate
    try:
        return tuple(map(_canonical_script_pair, items))
    except TypeError:
        return items                  # malformed entry: materialized, so
                                      # Policy can still re-iterate + quote


@dataclass(frozen=True, slots=True)
class Policy:
    """The behavior switches a parser runs with: name order,
    patronymic rules, delimiter routing, input scrubbing. Immutable
    and hashable; every field has a safe default, so construct with
    only what you change -- ``Policy(maiden_delimiters={("(", ")")})``
    -- and pass the result to ``Parser(policy=...)``."""

    #: How positional (no-comma) input maps onto given/middle/family.
    #: Valid values are exactly the three exported
    #: :ref:`name-order constants <name-order-constants>` --
    #: GIVEN_FIRST (the default), FAMILY_FIRST, and
    #: FAMILY_FIRST_GIVEN_LAST; any other tuple of Roles raises
    #: ValueError. Ignored when a comma separates family from given:
    #: "Thomas, John" puts the family name first no matter which words
    #: could otherwise be either ("Thomas" and "John" both work as
    #: given or family names). A comma that only sets off suffixes
    #: ("John Smith, Jr.") leaves name_order governing the name part.
    name_order: tuple[Role, Role, Role] = GIVEN_FIRST
    #: Per-script overrides of name_order (#271), consulted when every
    #: name piece is written wholly in one script, or in the
    #: Han/Hiragana/Katakana repertoire the #272 kana license shares
    #: across pieces: {Script: order} (constructor accepts a mapping;
    #: stored as sorted pairs). The default reads wholly-Han/Hangul
    #: names, and kana-licensed Japanese names, family-first -- see
    #: :data:`~nameparser.DEFAULT_SCRIPT_ORDERS`. Opt out with
    #: ``script_orders={}``. Latin-script and mixed-script input is
    #: never affected. Like name_order, ignored where a comma already
    #: decides the family name.
    script_orders: tuple[tuple[Script, tuple[Role, Role, Role]], ...] = (
        DEFAULT_SCRIPT_ORDERS)
    #: Scripts for which the unspaced-name segmentation stage is
    #: active (#271): the first token written wholly in an activated
    #: script is split by longest surname match against
    #: :attr:`Lexicon.surnames <nameparser.Lexicon.surnames>`, and,
    #: where that vocabulary declines, by a
    #: :data:`~nameparser.Segmenter` if one was given to the parser
    #: (#272). Default: {Script.HANGUL} -- hangul is unambiguously
    #: Korean and Korean surnames are a closed default-shipped set.
    #: Han is NOT default: a zh surname list corrupts Japanese names
    #: (高橋一郎 must not split as 高+橋一郎), so it's opt-in via
    #: locales.ZH for Chinese and locales.JA -- which activates
    #: Script.HIRAGANA alongside it, the kana license's carrier key --
    #: for Japanese.
    #: Opt out with ``segment_scripts=()``; note a PolicyPatch unions
    #: rather than replaces, so a pack can only add scripts, never
    #: disable one.
    segment_scripts: frozenset[Script] = frozenset({Script.HANGUL})
    #: Opt-in detectors that reorder patronymic-shaped names
    #: (EAST_SLAVIC, TURKIC); usually set via a locale pack.
    patronymic_rules: frozenset[PatronymicRule] = frozenset()
    #: Folds middle into family instead of splitting them (v1's
    #: middle_name_as_last) -- for data where unrecognized interior
    #: words are surname parts, not middle names: multi-part surnames
    #: like Spanish/Portuguese dual surnames ("Gabriel García Márquez"
    #: -> family "García Márquez" instead of middle "García").
    middle_as_family: bool = False  # v1's middle_name_as_last
    #: (open, close) pairs whose enclosed content becomes the nickname
    #: field. Defaults to
    #: :data:`~nameparser.DEFAULT_NICKNAME_DELIMITERS` (#273).
    nickname_delimiters: frozenset[tuple[str, str]] = DEFAULT_NICKNAME_DELIMITERS
    #: (open, close) pairs whose enclosed content becomes the maiden
    #: field instead; a pair listed here is dropped from the effective
    #: nickname set (maiden wins, see __post_init__), so
    #: maiden_delimiters={("(", ")")} is the whole recipe (#274).
    maiden_delimiters: frozenset[tuple[str, str]] = frozenset()
    #: Additional separators that split suffix groups (e.g. " - " for
    #: "Jane Smith, RN - CRNA"). Additive only: the comma always
    #: splits suffix groups and cannot be replaced -- comma handling
    #: is structural (the same comma reading that parses
    #: "Family, Given" input), not a configurable delimiter.
    extra_suffix_delimiters: frozenset[str] = frozenset()
    #: Governs "Family, Suffix"-shaped input where the suffix word is
    #: also initial-shaped (a single letter, bare or period-written --
    #: of the default vocabulary that means the roman numerals "I" and
    #: "V"): "John Smith, V" reads as John Smith the fifth when True
    #: (the default, v1 behavior); False reads "V" as a given-name
    #: initial instead (family "John Smith", given "V"). Multi-letter
    #: suffixes ("III", "MD") parse the same either way.
    lenient_comma_suffixes: bool = True
    #: Excludes emoji from tokenization: they appear in no token,
    #: field, or rendered view. The original string keeps them (input
    #: is never modified -- spans stay true).
    strip_emoji: bool = True
    #: Excludes bidirectional control characters from tokenization:
    #: they appear in no token, field, or rendered view; the original
    #: string keeps them.
    strip_bidi: bool = True  # =False replaces v1's opt-out CONSTANTS.regexes.bidi = False

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "name_order", _validated_order(self.name_order,
                                                 "name_order"))
        object.__setattr__(
            self, "script_orders",
            _validated_script_orders(self.script_orders))
        object.__setattr__(
            self, "segment_scripts",
            _validated_segment_scripts(self.segment_scripts))
        _reject_str_and_mapping(self.patronymic_rules, "patronymic_rules")
        # Probe with iter() rather than wrapping tuple(): non-iterables
        # (True especially -- v1's patronymic_name_order was a bool flag,
        # so it's the likeliest wrong value here) get the migration-
        # pointing message, while an exception raised inside a caller's
        # generator still propagates untouched from the tuple() below
        # instead of being rewritten. Only the enum lookup itself gets
        # the unknown-rule message, naming the offender.
        try:
            rule_iter = iter(self.patronymic_rules)
        except TypeError:
            raise TypeError(
                f"patronymic_rules must be an iterable of PatronymicRule "
                f"names, got {self.patronymic_rules!r}; "
                f"{_PATRONYMIC_MIGRATION_HINT}"
            ) from None
        items = tuple(rule_iter)
        rules = set()
        for r in items:
            try:
                rules.add(PatronymicRule(r))
            except ValueError:
                valid = ", ".join(v.value for v in PatronymicRule)
                raise ValueError(
                    f"unknown patronymic rule {r!r}; valid rules: {valid}"
                ) from None
        object.__setattr__(self, "patronymic_rules", frozenset(rules))
        for pairs_name in ("nickname_delimiters", "maiden_delimiters"):
            _reject_str_and_mapping(getattr(self, pairs_name), pairs_name)
            pairs = tuple(_require_iterable(getattr(self, pairs_name), pairs_name))
            for pair in pairs:
                if (not isinstance(pair, tuple) or len(pair) != 2
                        or not all(isinstance(s, str) for s in pair)):
                    raise TypeError(
                        f"{pairs_name} entries must be (open, close) tuples "
                        f"of strings, got {pair!r}"
                    )
                if not all(pair):
                    raise ValueError(
                        f"{pairs_name} entries must be pairs of non-empty "
                        f"strings, got {pair!r}"
                    )
            object.__setattr__(self, pairs_name, frozenset(pairs))
        # Maiden wins: a pair can route to exactly one field, and listing
        # it in maiden_delimiters is the specific intent, so the effective
        # nickname set drops it. Canonicalization, not validation (the
        # name_order coercion precedent): differently-written but
        # equivalent Policies converge to equal values. The v1 facade
        # keeps v1's nickname-wins precedence via a pre-subtraction in
        # _config_shim's snapshot instead.
        object.__setattr__(
            self, "nickname_delimiters",
            self.nickname_delimiters - self.maiden_delimiters)
        _reject_str_and_mapping(self.extra_suffix_delimiters,
                                "extra_suffix_delimiters")
        delimiters = tuple(_require_iterable(
            self.extra_suffix_delimiters, "extra_suffix_delimiters"))
        for d in delimiters:
            if not isinstance(d, str):
                raise TypeError(
                    f"extra_suffix_delimiters entries must be strings, "
                    f"got {d!r}"
                )
            if not d:
                raise ValueError(
                    "extra_suffix_delimiters entries must be non-empty strings"
                )
        object.__setattr__(
            self, "extra_suffix_delimiters", frozenset(delimiters)
        )
        # Truthy strings ("no", "false") would silently invert the
        # caller's intent downstream; bools are the one field kind the
        # coercing checks above can't cover.
        for flag in ("middle_as_family", "lenient_comma_suffixes",
                     "strip_emoji", "strip_bidi"):
            value = getattr(self, flag)
            if not isinstance(value, bool):
                raise TypeError(
                    f"{flag} must be a bool, got {value!r}"
                )

    def __repr__(self) -> str:
        # Bounded: only fields that deviate from the default are shown
        # (design rule, see nameparser._types module docstring).
        parts = []
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if value == f.default:
                continue
            if f.name == "name_order":
                parts.append(f"name_order={_order_repr(value)}")
            else:
                parts.append(f"{f.name}={value!r}")
        return f"Policy({', '.join(parts)})"

    # -- editing ------------------------------------------------------

    def patched(self, patch: PolicyPatch) -> Policy:
        """Fold a :class:`PolicyPatch` onto this Policy and return the
        combined Policy. Set-valued fields union with the patch's;
        scalar fields are overridden by the patch; UNSET fields are
        left alone. Patch VALUES are validated here (Policy's
        constructor re-runs on the result), not at patch construction
        -- see PolicyPatch. The maiden-wins canonicalization applies
        to the combined result exactly as if it had been constructed
        directly."""
        if not isinstance(patch, PolicyPatch):
            raise TypeError(f"patched() takes a PolicyPatch, got {patch!r}")
        return apply_patch(self, patch)


class _Unset(Enum):
    UNSET = auto()


#: Sentinel for "this patch does not set this field" (picklable enum
#: member, distinguishable from every real value including None/False).
UNSET = _Unset.UNSET

_UNION = {"compose": "union"}  # field metadata: set-valued -> union


@dataclass(frozen=True, slots=True)
class PolicyPatch:
    """A partial Policy: one field per Policy field, all defaulting to
    UNSET. Composition per field is DECLARED via metadata -- set-valued
    fields union, scalars override (later wins). Kept in lockstep with
    Policy by the parity test in tests/v2/test_policy.py.

    Values are validated when the patch is applied (Policy's constructor
    re-runs), not at patch construction.
    """

    name_order: tuple[Role, Role, Role] | _Unset = UNSET
    #: Composes as a SCALAR (override, not merge) -- deliberate: nothing
    #: shipped patches it today, so the simpler rule is the one to
    #: defend; revisit if a pack ever needs to add one script's entry
    #: without restating the rest.
    script_orders: tuple[
        tuple[Script, tuple[Role, Role, Role]], ...] | _Unset = UNSET
    segment_scripts: frozenset[Script] | _Unset = field(
        default=UNSET, metadata=_UNION)
    patronymic_rules: frozenset[PatronymicRule] | _Unset = field(
        default=UNSET, metadata=_UNION)
    middle_as_family: bool | _Unset = UNSET
    nickname_delimiters: frozenset[tuple[str, str]] | _Unset = field(
        default=UNSET, metadata=_UNION)
    maiden_delimiters: frozenset[tuple[str, str]] | _Unset = field(
        default=UNSET, metadata=_UNION)
    extra_suffix_delimiters: frozenset[str] | _Unset = field(
        default=UNSET, metadata=_UNION)
    lenient_comma_suffixes: bool | _Unset = UNSET
    strip_emoji: bool | _Unset = UNSET
    strip_bidi: bool | _Unset = UNSET

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        # Canonicalize (but do NOT validate) collection fields so a patch
        # built from a set/list literal is hashable and unions cleanly in
        # apply_patch. name_order needs the same treatment: Policy would
        # coerce a list at apply time, but the patch itself (and any
        # Locale holding it) must already be hashable.
        if self.name_order is not UNSET:
            _reject_bare_string_order(self.name_order, "name_order")
            object.__setattr__(self, "name_order", tuple(self.name_order))
        # Same reason for script_orders, one level deeper: a patch built
        # from a {Script: order} dict (or a list of pairs) must already
        # be hashable, since a Locale holds it -- and hashable all the
        # way down, hence _canonical_script_pair. Validation still
        # belongs to Policy at apply time, so a shape the canonicalizer
        # cannot digest is left for it to report; the one-shot and
        # malformed-entry cases are _canonical_patch_script_orders'.
        if self.script_orders is not UNSET:
            object.__setattr__(
                self, "script_orders",
                _canonical_patch_script_orders(self.script_orders))
        for f in dataclasses.fields(self):
            if f.metadata.get("compose") != "union":
                continue
            value = getattr(self, f.name)
            if value is UNSET:
                continue
            # Shared with Policy, not re-implemented: this used to be an
            # inline copy of the bare-string half only, so the mapping
            # half never reached a patch -- and frozenset() below
            # destroys the evidence, leaving nothing for Policy to catch
            # at apply time. A Locale pack ships one of these.
            _reject_str_and_mapping(value, f.name)
            # same iter() probe as Policy: curated message for
            # non-iterables (with the v1-flag hint where it applies),
            # caller-generator exceptions propagate from frozenset()
            try:
                iter(value)
            except TypeError:
                hint = ("; " + _PATRONYMIC_MIGRATION_HINT
                        if f.name == "patronymic_rules" else "")
                raise TypeError(
                    f"{f.name} must be an iterable, got {value!r}{hint}"
                ) from None
            object.__setattr__(self, f.name, frozenset(value))
        # middle_as_family, lenient_comma_suffixes, strip_emoji, and
        # strip_bidi are scalar (compose="override") fields and
        # DELIBERATELY get no type check here, unlike name_order and
        # the union fields above: a PolicyPatch(strip_emoji="off") is
        # constructible, and only raises once apply_patch runs
        # Policy.__post_init__'s bool check. This is the one place the
        # module's eager-validation ethos doesn't apply -- see the
        # class docstring ("Values are validated when the patch is
        # applied... not at patch construction").

    def __repr__(self) -> str:
        # Bounded: only fields the patch actually sets are shown; UNSET
        # fields are omitted (design rule, see nameparser._types module
        # docstring -- the sibling of Policy's deviation-only repr).
        parts = []
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if value is UNSET:
                continue
            if f.name == "name_order":
                parts.append(f"name_order={_order_repr(value)}")
            else:
                parts.append(f"{f.name}={value!r}")
        return f"PolicyPatch({', '.join(parts)})"


def apply_patch(policy: Policy, patch: PolicyPatch) -> Policy:
    """Fold a PolicyPatch onto a Policy. Policy.__post_init__ re-runs via
    dataclasses.replace, so patched values are revalidated for free --
    including the maiden-wins canonicalization: a patch that adds a
    maiden pair removes that pair from the base's effective nickname
    set, exactly as if the combined Policy had been constructed
    directly. Intended (decided 2026-07-19): maiden_delimiters
    membership IS the routing decision, whoever contributes it."""
    updates: dict[str, object] = {}
    for f in dataclasses.fields(PolicyPatch):
        value = getattr(patch, f.name)
        if value is UNSET:
            continue
        if f.metadata.get("compose") == "union":
            value = getattr(policy, f.name) | value
        updates[f.name] = value
    if not updates:
        return policy
    # Known mypy limitation with **dict-unpacked replace; see the full
    # explanation at Lexicon._edit in _lexicon.py.
    return dataclasses.replace(policy, **updates)  # type: ignore[arg-type]
