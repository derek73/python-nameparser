"""THE shared behavior case table (core spec §7.2).

Format is fixed here, in the first pipeline PR, and never per-PR:
one Case per input, expected values for exactly the non-empty fields,
optional Policy/Locale context, and a mandatory classification --
"parity" (matches v1.4.0, pinned live 2026-07-12) or "fix(#N)" /
"fix(<slug>)" (an intentional 2.0 behavior change, annotated with its
issue or a design-decision slug). No silent expectation edits:
changing a row means changing its classification.

The v1 suite's full corpus is extracted into this table by the
migration plan (facade runner consumes the same rows); this file seeds
it with the pinned battery.
"""
from __future__ import annotations

from dataclasses import dataclass

from nameparser import Policy
from nameparser._policy import PatronymicRule


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    expect: dict[str, str]          # field -> value; absent fields == ""
    policy: Policy | None = None
    classification: str = "parity"
    ambiguities: tuple[str, ...] = ()   # expected AmbiguityKind values
    notes: str = ""


_ES = Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC}))
_TK = Policy(patronymic_rules=frozenset({PatronymicRule.TURKIC}))
_SD = Policy(extra_suffix_delimiters=frozenset({" - "}))

CASES: tuple[Case, ...] = (
    Case("plain", "John Smith", {"given": "John", "family": "Smith"}),
    Case("family_comma", "Smith, John",
         {"given": "John", "family": "Smith"}),
    Case("suffix_comma", "John Smith, PhD",
         {"given": "John", "family": "Smith", "suffix": "PhD"}),
    Case("family_segment_trailing_suffix", "Smith Jr., John",
         {"given": "John", "family": "Smith", "suffix": "Jr."},
         notes="v1: the family part may have suffixes in it "
               "(parser.py:1370); the first piece is always the family "
               "(pinned live 2026-07-17)"),
    Case("family_segment_multiple_suffixes", "Smith Jr. MD, John",
         {"given": "John", "family": "Smith", "suffix": "Jr., MD"}),
    Case("family_segment_particle_chain_suffix", "de la Vega III, Juan",
         {"given": "Juan", "family": "de la Vega", "suffix": "III"}),
    Case("interior_periods_block_vocab", "Smith, J.R.",
         {"given": "J.R.", "family": "Smith"},
         notes="v1's lc() keeps interior periods: 'J.R.' is not the "
               "title 'jr' (pinned live 2026-07-17)"),
    Case("dotted_acronym_suffix", "John Smith M.D.",
         {"given": "John", "family": "Smith", "suffix": "M.D."},
         notes="suffix-ACRONYM membership alone strips periods (v1 "
               "is_suffix parity)"),
    Case("nickname_rule_counts_whole_segment", "Xyz. (Bud) Smith",
         {"title": "Xyz.", "given": "Smith", "nickname": "Bud"},
         notes="v1's lone-piece nickname rule counts the segment "
               "BEFORE title peeling (parser.py:1285, pinned live "
               "2026-07-17)"),
    Case("suffix_comma_decided_by_first_segment",
         "Dr. John P. Doe-Ray, CLU, CFP, LUTC",
         {"title": "Dr.", "given": "John", "middle": "P.",
          "family": "Doe-Ray", "suffix": "CLU, CFP, LUTC"},
         ambiguities=("comma-structure",),
         notes="only parts[1] decides the suffix-comma structure "
               "(v1 parser.py:1318); 'lutc' is not in the vocabulary "
               "but rides along (v1 parity, pinned live 2026-07-16)"),
    Case("suffix_comma_nonsuffix_tail_flagged", "John Smith, MD, Xyzzy",
         {"given": "John", "family": "Smith", "suffix": "MD, Xyzzy"},
         ambiguities=("comma-structure",),
         notes="the unrecognized tail is consumed best-effort with the "
               "flag (v1 consumed it silently)"),
    Case("period_joined_titles", "Lt.Gov. John Doe",
         {"title": "Lt.Gov.", "given": "John", "family": "Doe"},
         notes="v1 derived-title rule: ANY period chunk being a title "
               "makes the token a title (pinned live 2026-07-16)"),
    Case("period_joined_suffixes", "John Doe JD.CPA",
         {"given": "John", "family": "Doe", "suffix": "JD.CPA"}),
    Case("period_joined_any_rule", "Mr.Smith",
         {"title": "Mr.Smith"},
         notes="the ANY rule is deliberate v1 parity: one title chunk "
               "claims the whole token"),
    Case("doubled_comma_suffix", "Doe,, Jr.",
         {"family": "Doe", "suffix": "Jr."},
         notes="the EMPTY given segment keeps its position: 'Jr.' is a "
               "tail suffix, not a lone post-comma title (v1 parity, "
               "pinned live 2026-07-16)"),
    Case("doubled_comma_given_kept", "Doe, John,, Jr.",
         {"given": "John", "family": "Doe", "suffix": "Jr."}),
    Case("single_trailing_comma_cosmetic", "John,",
         {"given": "John"},
         notes="v1 collapse_whitespace strips exactly ONE trailing "
               "comma before parsing"),
    Case("double_trailing_comma_structural", "Doe,,",
         {"family": "Doe"},
         notes="one trailing comma is cosmetic, the second is "
               "structural: an empty given segment makes this a "
               "family-comma parse (v1 parity, pinned live 2026-07-16)"),
    Case("doubled_comma_blocks_suffix_comma", "John Smith,, MD",
         {"family": "John Smith", "suffix": "MD"},
         notes="an empty segment 1 fails the suffix-comma detection "
               "(v1 parity)"),
    Case("suffix_delimiter_tail_segment", "Doe, John, RN - CRNA",
         {"given": "John", "family": "Doe", "suffix": "RN, CRNA"},
         policy=_SD,
         notes="v1 suffix_delimiter parity (#191): the delimiter token "
               "is dropped from consumed tail segments (pinned live "
               "2026-07-16)"),
    Case("suffix_delimiter_detection", "Doe, John RN - CRNA",
         {"given": "John", "middle": "-", "family": "Doe",
          "suffix": "RN, CRNA"},
         policy=_SD,
         notes="the delimiter fires only at suffix sites; the stray "
               "token keeps its per-piece walk role (v1 parity, pinned "
               "live 2026-07-16)"),
    Case("suffix_delimiter_suffix_comma", "John Smith, RN - CRNA",
         {"given": "John", "family": "Smith", "suffix": "RN, CRNA"},
         policy=_SD,
         notes="delimiter transparency in the SUFFIX_COMMA "
               "determination: the post-comma segment counts as "
               "all-suffix (v1 parity, pinned live 2026-07-16)"),
    Case("suffix_delimiter_no_space_core", "John Smith, RN/CRNA",
         {"given": "John", "family": "Smith", "suffix": "RN/CRNA"},
         policy=Policy(extra_suffix_delimiters=frozenset({"/"})),
         classification="fix(suffix-delimiter-rendering)",
         notes="v1 split 'RN/CRNA' and rendered 'RN, CRNA'; v2 keeps "
               "the token whole (anti-#100) with Role.SUFFIX -- role "
               "assignment matches, rendering differs (migration plan "
               "deviation 5, release-log classified)"),
    Case("suffix_delimiter_name_segment_untouched", "Doe, Mary - Kate, RN",
         {"given": "Mary", "middle": "- Kate", "family": "Doe",
          "suffix": "RN"},
         policy=_SD,
         notes="a delimiter token in a NAME segment is kept (v1 parity, "
               "pinned live 2026-07-16)"),
    Case("comma_extras_become_suffixes", "Smith, John, Extra, Jr.",
         {"given": "John", "family": "Smith", "suffix": "Extra, Jr."},
         ambiguities=("comma-structure",),
         notes="post-comma segments land in suffix even when not "
               "suffix-shaped; the ambiguity flags the guess (v1 "
               "parity, pinned live 2026-07-13)"),
    Case("delavega", "Dr. Juan de la Vega III",
         {"title": "Dr.", "given": "Juan", "family": "de la Vega",
          "suffix": "III"}),
    Case("prefix_chain_to_end", "Juan de la Vega Martinez",
         {"given": "Juan", "family": "de la Vega Martinez"}),
    Case("van_johnson", "Van Johnson",
         {"given": "Van", "family": "Johnson"},
         ambiguities=("particle-or-given",),
         notes="v2 surfaces #121's irreducible ambiguity"),
    Case("family_comma_particles", "de la Vega, Juan",
         {"given": "Juan", "family": "de la Vega"}),
    Case("paren_suffix_escapes_nickname", "Andrew Perkins (MBA)",
         {"given": "Andrew", "family": "Perkins", "suffix": "MBA"},
         notes="v1 parse_nicknames: suffix-shaped delimited content is "
               "left in place for normal parsing (pinned live "
               "2026-07-17)"),
    Case("paren_period_escapes_nickname", "Andrew Perkins (Ret.)",
         {"given": "Andrew", "family": "Perkins", "suffix": "Ret."}),
    Case("nickname_quotes", 'John "Jack" Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"}),
    Case("nickname_parens", "John (Jack) Kennedy",
         {"given": "John", "family": "Kennedy", "nickname": "Jack"}),
    Case("sir_bob", "Sir Bob Andrew Dole",
         {"title": "Sir", "given": "Bob", "middle": "Andrew",
          "family": "Dole"}),
    Case("long_title", "President of the United States Barack Obama",
         {"title": "President of the United States",
          "given": "Barack", "family": "Obama"}),
    Case("secretary", "The Secretary of State Hillary Clinton",
         {"title": "The Secretary of State", "given": "Hillary",
          "family": "Clinton"}),
    Case("comma_middle_initial", "Doe, John A.",
         {"given": "John", "middle": "A.", "family": "Doe"}),
    Case("single", "John", {"given": "John"}),
    Case("title_only", "Dr.", {"title": "Dr."}),
    Case("double_comma_suffix", "Smith, John, Jr.",
         {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Case("bound_given_two", "abdul rahman",
         {"given": "abdul", "family": "rahman"}),
    Case("bound_given_three", "abdul rahman al-said",
         {"given": "abdul rahman", "family": "al-said"}),
    Case("mr_and_mrs", "Mr. and Mrs. John Smith",
         {"title": "Mr. and Mrs.", "given": "John", "family": "Smith"}),
    Case("roman_suffix", "John Smith V",
         {"given": "John", "family": "Smith", "suffix": "V"}),
    Case("initial_not_suffix", "John V. Smith",
         {"given": "John", "middle": "V.", "family": "Smith"}),
    Case("lenient_after_comma", "John Ingram, V",
         {"given": "John", "family": "Ingram", "suffix": "V"}),
    Case("comma_then_title", "Smith, Dr. John",
         {"title": "Dr.", "given": "John", "family": "Smith"}),
    Case("nickname_single_name", "John (Jack)",
         {"family": "John", "nickname": "Jack"}),
    Case("nickname_only", "(Jack)", {"nickname": "Jack"}),
    Case("suffix_run", "John Jack Kennedy PhD MD",
         {"given": "John", "middle": "Jack", "family": "Kennedy",
          "suffix": "PhD, MD"}),
    Case("maiden_marker", "Jane Smith née Jones",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#274)",
         notes="v1 mangles to middle='Smith née'"),
    Case("east_slavic", "Сидоров Иван Петрович",
         {"given": "Иван", "middle": "Петрович", "family": "Сидоров"},
         policy=_ES),
    Case("turkic", "Mammadova Aygun Ali kizi",
         {"given": "Aygun", "middle": "Ali kizi", "family": "Mammadova"},
         policy=_TK),
    Case("empty", "", {}),
    Case("whitespace", "   ", {}),
    Case("bare_ambiguous_acronym", "John Ed",
         {"given": "John", "family": "Ed"},
         notes="'ed' is an ambiguous acronym; bare form is a name (C1)"),
    Case("comma_ambiguous_acronym", "Smith, Ed",
         {"given": "Ed", "family": "Smith"}),
    Case("ambiguous_acronym_with_suffix", "John Ed III",
         {"given": "John", "family": "Ed", "suffix": "III"}),
    Case("phd_split", "John Ph. D.",
         {"given": "John", "suffix": "Ph. D."},
         notes="v1 fix_phd; healed via the stable 'joined' tag"),
    Case("phd_split_mid_name", "Dr. John Ph. D. Smith",
         {"title": "Dr.", "given": "John", "family": "Smith",
          "suffix": "Ph. D."}),
    Case("leading_never_given_particle", "de la Vega",
         {"family": "de la Vega"},
         notes="v1 handle_non_first_name_prefix: never-given leading "
               "particle folds the whole name into family"),
    Case("unbalanced_quote", 'Jon "Nick Smith',
         {"given": "Jon", "middle": '"Nick', "family": "Smith"},
         ambiguities=("unbalanced-delimiter",),
         notes="quote char stays literal (spec §5a)"),
    Case("suffix_stays_suffix", "Johnson PhD",
         {"given": "Johnson", "suffix": "PhD"},
         classification="fix(suffix-routing)",
         notes="v1 routes a lone trailing suffix to family "
               "(first=Johnson last=PhD); v2 keeps recognized "
               "suffixes in suffix"),
    Case("suffix_stays_suffix_title", "Mr. Johnson PhD",
         {"title": "Mr.", "given": "Johnson", "suffix": "PhD"},
         classification="fix(suffix-routing)",
         notes="v1 routes a lone trailing suffix to family "
               "(title=Mr. first=Johnson last=PhD); v2 keeps "
               "recognized suffixes in suffix"),
    Case("family_comma_lone_title", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="pre-comma is definitionally family; v1 put it in first"),
)
