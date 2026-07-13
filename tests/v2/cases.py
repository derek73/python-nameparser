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

CASES: tuple[Case, ...] = (
    Case("plain", "John Smith", {"given": "John", "family": "Smith"}),
    Case("family_comma", "Smith, John",
         {"given": "John", "family": "Smith"}),
    Case("suffix_comma", "John Smith, PhD",
         {"given": "John", "family": "Smith", "suffix": "PhD"}),
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
