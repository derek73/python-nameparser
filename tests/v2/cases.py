"""THE shared behavior case table (rules.md cites it as the pin of
CURRENT behavior).

Format is fixed here, in the first pipeline PR, and never per-PR:
one Case per input, expected values for exactly the non-empty fields,
optional Policy/Locale context, and a mandatory classification --
"parity" (matches v1.4.0, pinned live 2026-07-12) or "fix(#N)" /
"fix(<slug>)" (an intentional 2.0 behavior change, annotated with its
issue or a design-decision slug). No silent expectation edits:
changing a row means changing its classification.

"UNDETERMINED" is a fourth value and a TEMPORARY one: a row added
before anyone has run its input against 1.4.0 carries it until the
comparison is made and it resolves to one of the three above. It is
not a standing category, and nothing enforces its removal -- a row
still wearing it is a row whose parity is simply unknown.

The v1 suite's full corpus is extracted into this table by the
migration plan (facade runner consumes the same rows); this file seeds
it with the pinned battery.
"""
from __future__ import annotations

from dataclasses import dataclass

from nameparser import Policy
from nameparser._policy import (FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST,
                               PatronymicRule)


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    expect: dict[str, str]          # field -> value; absent fields == ""
    policy: Policy | None = None
    locale: str | None = None       # locale CODE (keeps this table
                                     # import-light); mutually exclusive
                                     # with policy
    classification: str = "parity"
    ambiguities: tuple[str, ...] = ()   # expected AmbiguityKind values
    notes: str = ""

    def __post_init__(self) -> None:
        if self.policy is not None and self.locale is not None:
            raise ValueError(
                f"{self.id}: policy and locale are mutually exclusive")


_ES = Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC}))
_TK = Policy(patronymic_rules=frozenset({PatronymicRule.TURKIC}))
_SD = Policy(extra_suffix_delimiters=frozenset({" - "}))

CASES: tuple[Case, ...] = (
    Case("plain", "John Smith", {"given": "John", "family": "Smith"}),
    Case("family_comma", "Smith, John",
         {"given": "John", "family": "Smith"}),
    Case("suffix_comma", "John Smith, PhD",
         {"given": "John", "family": "Smith", "suffix": "PhD"}),
    Case("bound_given_pairwise_only", "Salem, Abdul Rahman Ahmed",
         {"given": "Abdul Rahman", "middle": "Ahmed", "family": "Salem"},
         notes="the bound-given join is PAIRWISE (one merge, v1 "
               "parity): the third piece stays a middle name"),
    Case("family_comma_three_part_trailing_strict", "Smith, John V, Jr.",
         {"given": "John", "middle": "V", "family": "Smith",
          "suffix": "Jr."},
         notes="the lenient trailing test applies only to TWO-part "
               "names; a third comma part makes the trailing token a "
               "middle initial (v1 parity, pinned live 2026-07-17)"),
    Case("triple_trailing_commas", "Doe,,,",
         {"family": "Doe"},
         notes="one trailing comma is cosmetic; the rest are "
               "structural empties (pinned live 2026-07-17)"),
    Case("paren_suffix_word_escapes_nickname", "John Smith (Esq)",
         {"given": "John", "family": "Smith", "suffix": "Esq"},
         notes="the suffix_words branch of the delimited-content "
               "escape (v1 parity, pinned live 2026-07-17)"),
    Case("suffix_acronym_multidot_spelling", "John Smith E.S.Q.",
         {"given": "John", "family": "Smith", "suffix": "E.S.Q."},
         notes="'esq' is in BOTH suffix_acronyms and suffix_words on "
               "purpose, and the two are not redundant: the word test "
               "strips only EDGE periods, the acronym test strips all "
               "of them, so only the acronym membership matches the "
               "multi-dot spelling (v1 parity, pinned live 2026-07-19)"),
    Case("bound_given_whole_segment", "salem, abdul salam",
         {"given": "abdul salam", "family": "salem"},
         notes="v1 joins bound given names freely in the post-comma "
               "segment (reserve_last=False, parser.py:1366) -- even "
               "when the join consumes the whole segment"),
    Case("middle_as_family_fold_order", "Hassan, Mohamad Ahmad Ali",
         {"given": "Mohamad", "family": "Ahmad Ali Hassan"},
         policy=Policy(middle_as_family=True),
         notes="v1 PREPENDED middle_list to last_list; folded tokens "
               "carry vocab:folded-middle and the family view orders "
               "them first (spans cannot reorder)"),
    Case("ambiguous_surname_acronyms", "Jack MA",
         {"given": "Jack", "family": "MA"},
         ambiguities=("suffix-or-name",),
         notes="'ma'/'do' joined suffix_acronyms_ambiguous: with only "
               "two pieces, 'one of them is a credential' is the less "
               "likely reading, so the ambiguous acronym stays the "
               "family name (v1 parity via its reserve_last)"),
    Case("ambiguous_surname_acronym_with_suffix", "Jack MA Jr",
         {"given": "Jack", "family": "MA", "suffix": "Jr"},
         ambiguities=("suffix-or-name",),
         notes="'Jr' peels first; 'MA' would then be the only piece "
               "left beside the given name, so it stays family"),
    Case("ambiguous_acronym_is_a_suffix_when_a_family_name_remains",
         "John Smith MA",
         {"given": "John", "family": "Smith", "suffix": "MA"},
         ambiguities=("suffix-or-name",),
         notes="the other half of the same rule: three pieces means "
               "peeling 'MA' still leaves given+family, so the "
               "credential reading wins (v1 parity)"),
    Case("ambiguous_acronym_suffix_with_middle", "John Q Smith MA",
         {"given": "John", "middle": "Q", "family": "Smith",
          "suffix": "MA"},
         ambiguities=("suffix-or-name",)),
    Case("titled_ambiguous_particle_does_not_chain", "Dr. Van Johnson",
         {"title": "Dr.", "given": "Van", "family": "Johnson"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="reads exactly as the untitled 'Van Johnson' does, "
               "because a title is not part of the name and so cannot "
               "decide whether the NAME begins with a particle (#367). "
               "This row pinned the opposite until 2.2 -- title 'Dr.', "
               "family 'Van Johnson', the chain having fired because "
               "the title shifted Van off piece index 0 -- and cited "
               "v1 parity for it. Parity was real (1.4.0 gives last "
               "'Van Johnson') and still not the tiebreaker it looked "
               "like: this is the SAME shape as 'Mr. Van Nguyen', "
               "which v1 shipped as an xfail calling the reading "
               "wrong, so v1 pinned one shape both as correct and as "
               "broken. Resolved toward the xfail, which now passes "
               "(tests/test_first_name.py::"
               "test_first_name_is_prefix_if_three_parts). The fork is "
               "still reported, from assign rather than group -- the "
               "same place the untitled 'Van Johnson' reports it"),
    Case("titled_ambiguous_particle_keeps_its_middles", "Dr. Van Johnson Smith",
         {"title": "Dr.", "given": "Van", "middle": "Johnson",
          "family": "Smith"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="the release log names this shape and nothing asserted "
               "it. 1.4.0 gives title 'Dr.', last 'Van Johnson Smith'; "
               "un-chaining leaves three name pieces, so the middle "
               "appears where the whole thing used to be one surname"),
    Case("given_name_title_ambiguous_particle", "Sir Van Johnson",
         {"title": "Sir", "given": "Van", "family": "Johnson"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="a GIVEN-NAME title, which is the worse half of the bug "
               "#367 fixed: 1.4.0 and 2.1 alike gave first "
               "'Van Johnson' and no family name at all, the chain "
               "having fired and then been handed whole to `given`. "
               "Now identical to the untitled 'Van Johnson'"),
    Case("given_name_title_never_given_particle", "Sir de Mesnil",
         {"title": "Sir", "family": "de Mesnil"},
         classification="fix(#367)",
         notes="the never-given half: `de` is not an ambiguous "
               "particle, so there is no fork to report and post_rules "
               "1b folds the name into the family. 1.4.0 and 2.1 gave "
               "first 'de Mesnil' with no family, because the chain "
               "left 1b nothing standing alone to fire on"),
    Case("title_plus_one_word_with_maiden", "Dr. Smith née Jones",
         {"title": "Dr.", "family": "Smith", "maiden": "Jones"},
         classification="fix(#410)",
         notes="H1's 'and nothing else' counted a maiden name as a "
               "further name word, so adding a maiden clause moved the "
               "surname into `given` and emptied `family`: 'Dr. Smith' "
               "reads family 'Smith' and 'Dr. Smith née Jones' read "
               "given 'Smith'. A maiden name is announced beside the "
               "name, not part of it. 1.4.0 had no maiden SUPPORT -- "
               "the field exists, but no default marker vocabulary "
               "routes to it -- and read first 'Smith', middle 'née', "
               "last 'Jones'"),
    Case("title_plus_one_word_with_maiden_particle_spelling",
         "Freiherr von Richthofen geb. Albrecht",
         {"title": "Freiherr", "family": "von Richthofen",
          "maiden": "Albrecht"},
         classification="fix(#410)",
         ambiguities=("particle-or-given",),
         notes="the spelling #410 was found through: #399 stopped the "
               "particle chain at the marker, which routed the "
               "canonical title-and-particle shape into H1 for the "
               "first time and so into this bug. 1.4.0 read the whole "
               "tail as one surname, last 'von Richthofen geb. "
               "Albrecht'"),
    Case("given_name_title_plus_one_word_with_maiden",
         "Sir John née Jones",
         {"title": "Sir", "given": "John", "maiden": "Jones"},
         classification="fix(#274)",
         notes="H1's carve-out is untouched by #410: a given-name "
               "title addresses by given name, so the one name word "
               "stays `given` and the family stays empty, exactly as "
               "'Sir John' reads -- in the DEFAULT order, which is "
               "what this row pins: under either family-first order "
               "the same name reads family 'John', H1 being a no-op "
               "there because assign has already placed the word. "
               "The boundary of the widening, and "
               "the row that fails if the retag is made unconditional. "
               "The fix classification is #274's marker consumption, "
               "which is what makes this differ from 1.4.0 (first "
               "'John', middle 'née', last 'Jones')"),
    Case("title_plus_one_word_comma_suffix", "Dr. King, Jr.",
         {"title": "Dr.", "family": "King", "suffix": "Jr."},
         classification="fix(#410)",
         notes="the most ordinary shape H1's widening touches, and "
               "the one the suite could least afford to leave "
               "unpinned: mutating H1 to decline on any name carrying "
               "a comma left all 5819 tests green. Nothing else sees "
               "the class -- the corpus-wide maiden-clause property "
               "test filters commas out of its parametrization "
               "(_clause_free_latin_corpus_names), and "
               "'Smith, Dr.' takes its family from the comma rule "
               "(C1), not from H1. 1.4.0 had the same empty family "
               "here (title 'Dr.', first 'King', last ''), so this "
               "row records a v1 bug fixed, not a v2 divergence"),
    Case("title_plus_one_word_multi_word_maiden",
         "Dr. Smith née Mary Jones",
         {"title": "Dr.", "family": "Smith", "maiden": "Mary Jones"},
         classification="fix(#410)",
         notes="the maiden name at two words rather than one. H1 "
               "counts what stands in the NAME, so the arity of the "
               "clause beside it is irrelevant -- a rule that "
               "declined on a second maiden token would pass every "
               "single-word row above. 1.4.0 read first 'Smith', "
               "middle 'née Mary', last 'Jones'"),
    Case("given_name_title_plus_one_word_multi_word_maiden",
         "Sir John née Mary Jones",
         {"title": "Sir", "given": "John", "maiden": "Mary Jones"},
         classification="fix(#410)",
         notes="the carve-out at the same arity: 'whatever maiden "
               "name stands beside it' has to leave the given-name "
               "title alone however long the clause is. Without this "
               "row the `whatever` is asserted only at one word. "
               "1.4.0 read first 'John', middle 'née Mary', last "
               "'Jones'"),
    Case("title_plus_one_word_two_suffixes", "Dr. Smith PhD Jr.",
         {"title": "Dr.", "family": "Smith", "suffix": "PhD, Jr."},
         classification="fix(#410)",
         notes="two suffix pieces, not one. The removed term asked "
               "whether ANY token carried a suffix role, so a guard "
               "rebuilt to decline on the SECOND one would look "
               "correct against every row that carries a single "
               "credential. 1.4.0 split them, reading first 'Smith', "
               "last 'PhD', suffix 'Jr.'"),
    Case("title_plus_one_word_nickname_and_suffix",
         "Dr. (Bud) Smith Jr.",
         {"title": "Dr.", "family": "Smith", "suffix": "Jr.",
          "nickname": "Bud"},
         classification="fix(#410)",
         notes="two DIFFERENT annotations at once, which is the "
               "combination the single-annotation rows cannot reach: "
               "a guard declining only where a nickname and a suffix "
               "are both present passes all of them. 1.4.0 read first "
               "'Smith', last 'Jr.' with nickname 'Bud' -- the "
               "credential taking the family slot"),
    # The smallest shape in which the two family-first orders can
    # disagree about this rule's leftovers: with one leftover both
    # send it to `given`, and two or more is what separates them (the
    # orders differ on plenty of names outside this rule -- 186 of the
    # 751 corpus names -- so the claim is about the fold, not about
    # the orders). Spanish because the listing is real: "Apellidos
    # Nombres" keeps the particle in place, where Dutch moves it
    # behind the given name ("Jong, Jan Pieter de", the tussenvoegsel
    # convention -- rule P6's subject, though P6's attachment is
    # deviates: #379, so that spelling does not yet parse the way P6
    # describes). Added before #395 landed, when all three orders
    # still agreed, each taking the whole name into the family.
    Case("leading_never_given_particle_two_leftovers",
         "de la Cruz Juan Carlos",
         {"family": "de la Cruz Juan Carlos"},
         classification="parity",
         notes="the DEFAULT order, which #395 leaves alone: with no "
               "order declared there is no evidence that 'Juan Carlos' "
               "is anything but more surname, and a particle followed "
               "by several words really can be all surname -- 'von "
               "Bergen Wessels' is one. (An earlier draft cited "
               "'pennie von bergen wessels' as the same SHAPE, which "
               "it is not: pennie is the given name there and von is "
               "ambiguous, so this fold cannot fire on it. See "
               "decisions.md#P1, 2026-08-17.) 1.4.0 gives last 'de la "
               "Cruz Juan Carlos' too, so this row must not move when "
               "#395 lands"),
    Case("leading_never_given_particle_two_leftovers_family_first",
         "de la Cruz Juan Carlos",
         {"family": "de la Cruz", "given": "Juan", "middle": "Carlos"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="feat(#395)",
         notes="core-only: name_order has no v1 spelling. The run "
               "stops at 'Cruz' because the declared order says what "
               "follows the family is not more surname. It reaches "
               "'Cruz' THROUGH ambiguous 'la', which is the chain a "
               "stop keyed on never-given membership would break"),
    Case("leading_never_given_particle_two_leftovers_"
         "family_first_given_last",
         "de la Cruz Juan Carlos",
         {"family": "de la Cruz", "middle": "Juan", "given": "Carlos"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
         classification="feat(#395)",
         notes="the row that makes the leftover DISTRIBUTION testable, "
               "and the divergence is here: FAMILY_FIRST reads 'Juan' "
               "as the given name, this order reads 'Carlos'. Nothing "
               "with fewer leftovers can tell the two apart. When "
               "PR #394 put the placing in grouping, its review found "
               "the whole suite passed with name_order discarded from "
               "it; on this branch the same mutation fails three "
               "tests, this row among them"),
    # The Dutch alphabetized listing: "Beethoven, Ludwig van" is how
    # "Ludwig van Beethoven" is filed, the tussenvoegsel moved behind
    # the given name but belonging to the surname (#379).
    Case("tussenvoegsel_after_family_comma", "Beethoven, Ludwig van",
         {"given": "Ludwig", "family": "van Beethoven"},
         classification="fix(#379)",
         notes="1.4.0 gives middle 'van', last 'Beethoven'. The "
               "particle attaches to the family the comma already "
               "named and renders before it, so the derived views "
               "move with it -- family_particles 'van', family_base "
               "'Beethoven', which is what #130 asked for"),
    Case("tussenvoegsel_multiword", "Berg, Jan van der",
         {"given": "Jan", "family": "van der Berg"},
         classification="fix(#379)",
         notes="the whole run attaches, not just its last word"),
    Case("tussenvoegsel_outranks_the_suffix_reading", "Berg, Jan vd",
         {"given": "Jan", "family": "vd Berg"},
         classification="fix(#380)",
         notes="'vd' is particle AND suffix vocabulary, and assign "
               "read the trailing one as a post-nominal (1.4.0 and "
               "2.1 alike gave suffix 'vd'). After a family comma the "
               "tussenvoegsel abbreviation is far more often the "
               "reading meant; P6 states that precedence over S2"),
    Case("tussenvoegsel_behind_a_post_nominal", "Berg, Jan van Jr.",
         {"given": "Jan", "family": "van Berg", "suffix": "Jr."},
         classification="fix(#379)",
         notes="the credential sits BEHIND the tussenvoegsel in this "
               "listing, so the run is found by walking past it. "
               "Without that walk the same name parsed two ways on "
               "whether a comma preceded the credential -- "
               "'Berg, Jan van, Jr.' attached and this one did not"),
    Case("tussenvoegsel_declines_with_no_given_word_left",
         "Smith, de Mesnil van",
         {"family": "Smith de Mesnil van"},
         classification="fix(comma-precomma-family)",
         notes="P1's fold has already made all of segment 1 the "
               "family, so no GIVEN word remains and the "
               "attachment declines. Testing for any NAME role here "
               "instead would pass on family text P1 just produced, "
               "and hoist 'van' in front of a base it never preceded "
               "('van Smith de Mesnil'). NOT parity: 1.4.0 leaves no "
               "given name either, but renders last 'de Mesnil van "
               "Smith' -- it treats only the leading 'de' as a "
               "last-prefix and leaves 'van' inside the base. The "
               "structure agrees, the string does not"),
    Case("tussenvoegsel_behind_a_comma_post_nominal",
         "Berg, Jan van, Jr.",
         {"given": "Jan", "family": "van Berg", "suffix": "Jr."},
         classification="fix(#379)",
         notes="the credential in its own comma segment, which is the "
               "spelling the no-comma row is defined against -- both "
               "must read the same, and gating the rule on a two"
               "-segment name silently reverts this one"),
    Case("tussenvoegsel_behind_a_title", "Berg, Dr. Jan van",
         {"title": "Dr.", "given": "Jan", "family": "van Berg"},
         classification="fix(#379)",
         notes="the words-to-spare test asks whether ANY word ahead "
               "of the run holds a given role, not whether all of "
               "them do: the title does not, and the rule must still "
               "fire. decisions.md#P6 calls that guard load-bearing"),
    Case("tussenvoegsel_takes_the_vietnamese_reading", "Nguyen, Thi Van",
         {"given": "Thi", "family": "Van Nguyen"},
         classification="fix(#379)",
         notes="the accepted cost, pinned so it cannot move without "
               "someone deciding to move it: Nguyen Thi Van is "
               "family-middle-given, so the given name Van is lost "
               "here. The listing is identical to the Dutch one and "
               "nothing separates them. The comma-LESS family-first "
               "spelling reads it correctly, which is what makes the "
               "loss acceptable -- see rules.md#P6"),
    Case("tussenvoegsel_needs_a_given_word_to_spare", "Nguyen, Van",
         {"given": "Van", "family": "Nguyen"},
         classification="parity",
         notes="the words-to-spare boundary: the only given word IS "
               "the particle, so it stays a given name rather than "
               "leaving the name with none. Vietnamese Van is exactly "
               "the case that guard protects"),
    # A family made only of particle vocabulary. Position decides:
    # nothing joins these words to a name, so they are not acting as
    # particles and they anchor the base (rules.md#R2, #404).
    Case("all_particle_family_anchors_its_own_base", "Anh Do",
         {"given": "Anh", "family": "Do"},
         classification="parity",
         ambiguities=("suffix-or-name",),
         notes="the ROLES are parity -- 1.4.0 gives first 'Anh', last "
               "'Do' too -- and the views are what #404 moved, which "
               "this table cannot assert (no initials or base column; "
               "rules.md#R2/#R3 carry those). Worth recording which "
               "way: 1.4.0's own _split_last guard kept last_base "
               "'Do', so the empty family_base was a 2.0 regression "
               "and this restores it. The initials half was broken in "
               "both: 'A.' at 1.4.0 and 2.1, 'A. D.' now"),
    Case("all_particle_family_multi_word", "Juan van der",
         {"given": "Juan", "family": "van der"},
         classification="parity",
         notes="roles are parity again; R3's Accepted block used to "
               "pin the views the other way, reasoning that 'van der' "
               "has no borne name to anchor a base. Position trumps "
               "that -- neither word joins anything here, so both are "
               "name words. 1.4.0 also gave last_base 'van der'; the "
               "core's '' was the 2.0 regression"),
    Case("particle_beside_a_name_still_a_particle", "Juan de la Vega",
         {"given": "Juan", "family": "de la Vega"},
         classification="parity",
         notes="the boundary the row above needs: here the particles "
               "DO join a name word, so they stay particles -- base "
               "'Vega', particles 'de la', initials 'J. V.'"),
    Case("suffix_word_title_ambiguous_particle", "Jr. Van Johnson",
         {"title": "Jr.", "given": "Van", "family": "Johnson"},
         classification="fix(#367)",
         ambiguities=("particle-or-given",),
         notes="a leading 'Jr.' classifies as a TITLE, not a suffix, "
               "which is why the transparency scan does not step over "
               "suffix pieces -- see tests/v2/pipeline/test_group.py::"
               "test_a_suffix_shaped_leading_piece_is_not_stepped_over. "
               "1.4.0 gives title 'Jr.', last 'Van Johnson'"),
    Case("titled_particle_chain_survives_a_title_that_is_also_a_particle",
         "Freiherr von Richthofen",
         {"title": "Freiherr", "family": "von Richthofen"},
         ambiguities=("particle-or-given",),
         notes="#367's title transparency skips a piece that can ONLY "
               "be a title, never one that could be the name's own "
               "first piece. 'freiherr' is both a title and an "
               "ambiguous particle, so it stops the scan and stays the "
               "leading NAME piece; 'von' behind it is therefore "
               "non-leading and chains, exactly as before 2.2. This is "
               "also the CANONICAL shape reaching group's "
               "PARTICLE_OR_GIVEN emitter, not the only one -- 'St Van "
               "Johnson', 'Do St Johnson' and 'Dr. Do van Johnson' "
               "reach it too, the last with a plain title ahead of the "
               "both-vocabulary word; see tests/v2/test_parser.py -- "
               "and the class that a plain "
               "'first piece that is not a title' test broke: it "
               "skipped 'St'/'Do'/'Freiherr' and collapsed the "
               "untitled 'St John Smith' into one given name"),
    Case("titled_ambiguous_particle_no_op_chain", "St Van Jr.",
         {"title": "St", "family": "Van", "suffix": "Jr."},
         notes="the piece after the particle is a suffix, so the chain "
               "scan never advances and the merge is a no-op -- nothing "
               "was chained, so there is no fork to report (the emitter "
               "fired here for all 39 ambiguous particles, and _assign "
               "double-reported the same token). Spelled with 'St' "
               "since #296's audit took 'do' out of TITLES; before that "
               "with 'Do', and before 2.2 with 'Dr.': "
               "under #367 a plain title is transparent, so 'Dr. Van "
               "Jr.' leaves Van the leading name piece and the chain "
               "loop skips it without ever reaching the no-op. 'Do' is "
               "a title AND a particle, which stops the transparency "
               "scan, so the chain does fire on Van and the j > k + 1 "
               "guard is what declines it -- the same reading of the "
               "name, reached through the branch the row exists to pin. "
               "Not parity, and not #367's doing either: 1.4.0 reads "
               "'Do Van Jr.' as first 'Do Van', last 'Jr.', so the "
               "divergence is 2.0's suffix routing plus 'do' being a "
               "title -- both older than this row's respelling"
               " -- and since #410 the one name word left standing "
               "behind the title reads as the family, the suffix no "
               "longer counting as something else in the name",
         classification="fix"),
    Case("initial_shaped_not_conjunction", "john e. smith",
         {"given": "john", "middle": "e.", "family": "smith"},
         notes="v1 is_conjunction excludes initials at classify too"),
    Case("family_comma_lenient_trailing", "Smith, John V",
         {"given": "John", "family": "Smith", "suffix": "V"},
         notes="v1 #144: the trailing piece of a two-part comma name "
               "takes the lenient suffix test"),
    Case("family_comma_first_piece_is_given", "Steven Hardman, RN - CRNA",
         {"given": "RN", "middle": "-", "family": "Steven Hardman",
          "suffix": "CRNA"},
         notes="v1 walk order: the first post-comma piece is the given "
               "before any suffix check (the delimiter is UNSET here "
               "-- v1's documented limitation, kept)"),
    Case("family_comma_lone_suffix_piece", "Andrews, M.D.",
         {"family": "Andrews", "suffix": "M.D."},
         classification="fix(comma-family)",
         notes="v1 made the lone post-comma strict-suffix piece the "
               "given; 2.0 routes it to suffix (same family as the "
               "'Smith, Dr.' row)"),
    Case("family_comma_suffix_run_renders_unjoined", "Smith, MD PhD",
         {"family": "Smith", "suffix": "MD PhD"},
         classification="fix(comma-family)",
         notes="a space-separated post-nominal run after a family "
               "comma RENDERED with a comma the input never had "
               "('MD, PhD'), because the one-entry join was asked by "
               "segment index and this segment is not a tail one. The "
               "full-name 'John Smith, MD PhD' has rendered 'MD PhD' "
               "since 1.4.0, and #429 brought this form into line with "
               "it. The roles were already right after #428; this was "
               "its remaining half"),
    Case("period_joined_ambiguous_chunk", "John Doe, Msc.Ed.",
         {"given": "John", "family": "Doe", "suffix": "Msc.Ed."},
         notes="chunk-level suffix membership is v1's is_suffix: bare "
               "ambiguous acronyms count within period-joined tokens"),
    Case("suffix_comma_split_phd", "John Smith, Ph. D.",
         {"given": "John", "family": "Smith", "suffix": "Ph. D."},
         notes="the adjacent Ph./D. pair counts as one suffix unit in "
               "the suffix-comma detection (v1 fix_phd parity). The "
               "pair leads the run here; the row below is where it does "
               "not"),
    Case("suffix_comma_split_phd_after_another_suffix",
         "John Smith, Jr. Ph. D.",
         {"given": "John", "family": "Smith", "suffix": "Jr. Ph. D."},
         classification="fix(credential-pair-order)",
         notes="the pair is merged wherever it sits in the run, not "
               "only at its head, and the row above cannot say so -- "
               "there the pair IS the head. Restricted to position 0 "
               "the merge never fires, 'D.' is suffix vocabulary in no "
               "lexicon, and the run stops being wholly suffix: this "
               "reads as a FAMILY comma instead, family 'John Smith' / "
               "title 'Jr.' / suffix 'Ph. D.'. Pinned at the segment "
               "stage too (test_segment.test_the_credential_pair_"
               "merges_anywhere_in_the_run), because the neighbouring "
               "input 'John Smith, MD, Jr. Ph. D.' keeps every field "
               "under that break and gains only a comma-structure "
               "ambiguity, so fields alone do not catch it. Measured: "
               "1.4.0 gave suffix 'Ph. D., Jr.' -- fix_phd EXTRACTED "
               "the pair pre-parse and re-appended it, reordering the "
               "tail, where 2.0 renders it as written. Same words, "
               "same roles, different order, and the harness cannot "
               "currently see it: expected_since_1.4.0.toml states that a "
               "diffing trailing 'Ph. D.' must fail the run, but this "
               "input is absorbed by fix(comma-family), whose "
               "name_regex is a bare comma -- measured on a probe "
               "corpus, unexplained 0. See the note there"),
    Case("tail_segment_entry_space_joined", "John Smith, V MD",
         {"given": "John", "family": "Smith", "suffix": "V MD"},
         notes="v1 renders each tail comma segment as ONE suffix "
               "entry; words within an entry space-join via the "
               "'joined' tag"),
    Case("maiden_delimiters_win_when_shared",
         'Baker (Johnson), Jenny',
         {"given": "Jenny", "family": "Baker", "maiden": "Johnson"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         notes="listing a pair in maiden_delimiters drops it from the "
               "effective nickname set (maiden wins, 2026-07-19) -- the "
               "one-liner replaces the bucket-move idiom. The facade "
               "runner reaches this row by making that same move, so "
               "it agrees. What v1 does NOT agree on is a pair left in "
               "BOTH buckets, which it gives to nickname; that spelling "
               "is a different config, not this row, and is pinned in "
               "test_config_shim"),
    # #269 follow-up: Arabic-script bound given names, mirroring the
    # Latin transliterations' behavior (probed live 2026-07-19: bound
    # join fires only with 3+ tokens, eats the NEXT token into given;
    # two-token kunya stays split -- 'أبو مازن' pinned in test_locales;
    # non-leading أبو still prefix-chains onto family).
    Case("arabic_bound_given_abd", 'عبد الرحمن محمد',
         {"given": "عبد الرحمن", "family": "محمد"},
         classification="feat(#269)",
         notes="script twin of 'Abdul Rahman Mohammed'; عبد was the "
               "missing bound entry -- 1.x split it into given عبد + "
               "middle الرحمن"),
    Case("arabic_bound_given_kunya", 'أبو بكر أحمد',
         {"given": "أبو بكر", "family": "أحمد"},
         classification="feat(#269)"),
    Case("arabic_bound_given_kunya_hamzaless", 'ابو بكر احمد',
         {"given": "ابو بكر", "family": "احمد"},
         classification="feat(#269)",
         notes="both kunya spellings ship, like the أبو/ابو prefix pair"),
    Case("arabic_bound_given_umm", 'أم كلثوم إبراهيم',
         {"given": "أم كلثوم", "family": "إبراهيم"},
         classification="feat(#269)"),
    # #273: typographic nickname delimiters ship as defaults -- one row
    # per new pair; expectations verified live 2026-07-19 before the
    # pairs were added to DEFAULT_NICKNAME_DELIMITERS.
    Case("smart_double_quotes_nickname", 'John “Jack” Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         classification="feat(#273)"),
    Case("low_high_quotes_nickname", 'Hans „Hansi“ Müller',
         {"given": "Hans", "family": "Müller", "nickname": "Hansi"},
         classification="feat(#273)",
         notes="the closing '“' doubles as the English pair's opener; "
               "no spurious unbalanced-delimiter ambiguity (pinned in "
               "test_extract)"),
    Case("guillemets_nickname_inner_spaces", 'Jean « Petit » Dupont',
         {"given": "Jean", "family": "Dupont", "nickname": "Petit"},
         classification="feat(#273)",
         notes="French spacing: inner padding is trimmed from the "
               "extracted nickname"),
    Case("reversed_guillemets_nickname", 'Hans »Hansi« Müller',
         {"given": "Hans", "family": "Müller", "nickname": "Hansi"},
         classification="feat(#273)"),
    Case("swedish_right_quotes_nickname", 'Anna ”Ann” Larsson',
         {"given": "Anna", "family": "Larsson", "nickname": "Ann"},
         classification="feat(#273)"),
    Case("cjk_corner_bracket_nickname", '山田「タロ」太郎',
         {"family": "山田", "given": "太郎", "nickname": "タロ"},
         classification="feat(#273) + fix(#271)",
         notes="extraction also splits the unspaced remainder -- the "
               "masked region acts as a token boundary. Both name "
               "pieces are then wholly Han, so script_orders reads "
               "them family-first; the nickname's kana is outside the "
               "name pieces and does not enter that test"),
    Case("cjk_white_corner_bracket_nickname", '田中『ハナ』花子',
         {"family": "田中", "given": "花子", "nickname": "ハナ"},
         classification="feat(#273) + fix(#271)"),
    Case("fullwidth_paren_nickname", 'John （Jack） Kennedy',
         {"given": "John", "family": "Kennedy", "nickname": "Jack"},
         classification="feat(#273)"),
    Case("curly_apostrophe_stays_literal", 'Sean O’Connor',
         {"given": "Sean", "family": "O’Connor"},
         notes="U+2019 is the typographic apostrophe; curly single "
               "quotes are deliberately NOT delimiters (#273 excludes "
               "them)"),
    Case("family_segment_trailing_suffix", "Smith Jr., John",
         {"given": "John", "family": "Smith", "suffix": "Jr."},
         notes="v1: the family part may have suffixes in it "
               "(parser.py:1368); the first piece is always the family "
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
         {"title": "Xyz.", "family": "Smith", "nickname": "Bud"},
         classification="fix(#410)",
         notes="v1's lone-piece nickname rule counts the segment "
               "BEFORE title peeling (parser.py:1285, pinned live "
               "2026-07-17), which is what this row pins and what "
               "#410 does not change. The FIELD moved: a nickname is "
               "not a further name word, so the one name word behind "
               "the title is the family. 1.4.0 read first 'Smith'"),
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
         notes="v1 suffix_delimiter parity (#206): the delimiter token "
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
         {"given": "John", "family": "Smith", "suffix": "V"},
         ambiguities=("suffix-or-name",),
         notes="a trailing single letter is a name part unless it is a "
               "roman numeral; V/X/I are also ordinary middle initials, "
               "so the reading is reported"),
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
    Case("diminutive_that_was_a_marker_keeps_the_family",
         "Rosalind Roz Smith",
         {"given": "Rosalind", "middle": "Roz", "family": "Smith"},
         notes="'roz', the Czech/Slovak abbreviation, shipped in "
               "MAIDEN_MARKERS through 2.1 and collided with the "
               "English diminutive of Rosalind -- matching is "
               "whole-token, case-folded and period-insensitive, so "
               "Roz, roz and roz. are one string. This name read "
               "maiden 'Smith' with NO family name at all (measured on "
               "the pre-removal tree), because M2 hands the marker "
               "every word after it. The entry is gone in 2.2, which "
               "is what this row pins. Nothing to do with the "
               "delimited path: the defect is M2's, it predates #335, "
               "and the one-word '(Roz)' spelling was never affected "
               "since M3 declines a lone marker. Parity, and it is "
               "RESTORED parity rather than untouched -- 1.4.0 has no "
               "maiden support and read first Rosalind / middle Roz / "
               "last Smith (2026-08-26), which is where the removal "
               "puts this name back"),
    Case("full_participle_marker_still_consumes",
         "Anna Nováková rozená Svobodová",
         {"given": "Anna", "family": "Nováková", "maiden": "Svobodová"},
         classification="fix(#274)",
         notes="the other half of the roz removal, and the reason it "
               "was a removal and not a retreat from Czech: the full "
               "participle rozená stays, being a word no one is "
               "called. Pinned because deleting a vocabulary entry "
               "invites deleting its neighbours, and because nothing "
               "else in the suite reaches this entry: removing "
               "rozená from MAIDEN_MARKERS fails exactly this row's "
               "two tests, one per runner, and nothing else (measured "
               "2026-08-26) -- the position "
               "maiden_marker_delimited_unaccented holds for 'nee'. "
               "The cost the removal accepts is the "
               "abbreviation: 'Anna Nováková roz. Svobodová' now reads "
               "middle 'Nováková roz.', family 'Svobodová' (measured), "
               "which is exactly how 1.4.0 read it. 1.4.0 read this "
               "row middle 'Nováková rozená' / last Svobodová "
               "(2026-08-26) -- the marker inside the name, the "
               "ordinary v1 reading of every marker"),
    Case("maiden_marker_after_particle_chain",
         "Ursula von der Leyen geb. Albrecht",
         {"given": "Ursula", "family": "von der Leyen",
          "maiden": "Albrecht"},
         classification="fix(#399)",
         notes="#399: the chain that joins 'von der' to Leyen used to "
               "run on past the marker and take the maiden name with "
               "it (family 'von der Leyen geb. Albrecht', maiden ''), "
               "because the marker is consumed AFTER the chain merges "
               "and by then there is no lone marker piece left to "
               "find. A suffix already stopped the chain; a marker now "
               "does too. The same words one chain apart -- "
               "maiden_marker_no_particle below is the control"),
    Case("maiden_marker_no_particle", "Ursula Leyen geb. Albrecht",
         {"given": "Ursula", "family": "Leyen", "maiden": "Albrecht"},
         classification="fix(#274)",
         notes="the control for maiden_marker_after_particle_chain: "
               "identical but for the particles, and it always worked. "
               "Pinned so a regression in the plain path cannot hide "
               "behind the particle rows"),
    Case("maiden_marker_after_one_particle", "Anna von Müller geb. Schmidt",
         {"given": "Anna", "family": "von Müller", "maiden": "Schmidt"},
         classification="fix(#399)",
         notes="one particle is enough to break it -- #399 is not "
               "about the length of the run"),
    Case("maiden_marker_after_leading_particle", "von Müller geb. Schmidt",
         {"given": "von", "family": "Müller", "maiden": "Schmidt"},
         classification="fix(#274)",
         ambiguities=("particle-or-given",),
         notes="the second control for #399, and the one that shows "
               "where the old boundary fell: a LEADING particle chains "
               "nothing (P4), so it never reached the marker and this "
               "shape always worked. given 'von' is P4 plus P1 "
               "declining to fold ('von' is outside the never-given "
               "particles), which is also why the row reports the "
               "fork -- not R2, whose output here is the family "
               "('Müller', base 'Müller', particles '')"),
    Case("maiden_marker_after_leading_particle_run",
         "von der Müller geb. Schmidt",
         {"given": "von", "family": "der Müller", "maiden": "Schmidt"},
         classification="fix(#399)",
         ambiguities=("particle-or-given",),
         notes="a leading RUN of two broke where a leading single did "
               "not: 'der' is not the leading piece, so its own chain "
               "fired and swallowed the marker. What #399 left alone "
               "is the given/family SPLIT -- given 'von', family "
               "starting at 'der' (P4 + R2); the family itself shed "
               "the marker and the maiden name it had swallowed "
               "('der Müller geb. Schmidt' -> 'der Müller')"),
    Case("maiden_marker_after_particle_chain_with_suffix",
         "Jane van der Berg née Jones PhD",
         {"given": "Jane", "family": "van der Berg", "maiden": "Jones",
          "suffix": "PhD"},
         classification="fix(#399)",
         notes="marker and suffix in the same name: M2's walk takes "
               "the maiden name up to the suffix before the chain "
               "runs, so the chain has nothing to stop at (under #399 "
               "it stopped at the marker). Dutch spelling of the same "
               "defect, and 'née' unaccented-vs-accented is not the "
               "variable here"),
    Case("maiden_marker_stops_the_leading_run_family_first",
         "de la Cruz née Vega",
         {"family": "de la Cruz", "maiden": "Vega"},
         policy=Policy(name_order=FAMILY_FIRST),
         classification="fix(#399)",
         notes="#399's open question, answered by the marker being "
               "consumed before anything can place it rather than by "
               "a rule of its own: the marker used to "
               "survive as an ordinary name word and compete for the "
               "leftover given slot, so this read given 'née' / middle "
               "'Vega'. Consumed and dropped, it never reaches the "
               "placement. No given name at all is the right answer "
               "for family-plus-maiden input"),
    Case("maiden_marker_leaves_family_all_particles",
         "Jane de la née Jones",
         {"given": "Jane", "family": "de la", "maiden": "Jones"},
         classification="fix(#399)",
         notes="taking the marker before the chain runs can leave a "
               "family group that is wholly particles, which is exactly "
               "the shape R2 "
               "reserves: they are not in particle position, so they "
               "report as ordinary words -- family_base 'de la', "
               "family_particles ''. test_cases pins that split only "
               "up to the partition invariant (non-empty base, words "
               "conserved), so base 'la' / particles 'de' would also "
               "satisfy it. Before #399 this read family 'de la née "
               "Jones' with base 'née Jones'. Nonsense input either "
               "way; pinned "
               "because the two rules have to compose without "
               "either producing an empty base"),
    Case("maiden_marker_trailing_after_particles",
         "Jane van der Berg née",
         {"given": "Jane", "family": "van der Berg née"},
         notes="M2's boundary on the particle side. A marker with "
               "nothing after it is just a word: the consumer declines "
               "it and the chain takes it like any other word. A chain "
               "that stopped at it instead left the marker as a piece "
               "of its own, which then took the whole family field and "
               "demoted the real surname to the middle (family 'née', "
               "middle 'van der Berg'). The first cut "
               "of #399 did exactly that -- the marker-less spelling "
               "'Jones née' -> family 'née' is M2's own boundary "
               "example, and the particle spelling has to agree with "
               "the rest of the family name, not replace it"),
    Case("maiden_marker_trailing_before_suffix",
         "Jane van der Berg née PhD",
         {"given": "Jane", "family": "van der Berg née",
          "suffix": "PhD"},
         notes="the other way the consumer declines: it walks only up "
               "to a trailing suffix, so a marker with nothing but a "
               "suffix after it is not consumed either, and the chain "
               "takes it. Pinned "
               "separately from the row above because the two reach "
               "the same decision through different conditions -- last "
               "piece vs nothing-but-suffix-follows -- and #399's chain "
               "stop, keyed on only one of them, looked correct on the "
               "other"),
    Case("maiden_marker_surname_spelling_keeps_its_particles",
         "Jane van der Nee",
         {"given": "Jane", "family": "van der Nee"},
         notes="'Nee' is an attested surname as well as a marker "
               "spelling, which M1 already says ('a one-word clause "
               "keeps its word, which may itself be a surname'). "
               "Because nothing follows it the consumer declines, so a "
               "Dutch bearer of the surname keeps the tussenvoegsel "
               "in the family name. Ungated, #399 moved 'van der' out "
               "to the middle and left family 'Nee'"),
    Case("maiden_marker_trailing_keeps_the_fork_report",
         "St St née",
         {"title": "St", "family": "St née"},
         ambiguities=("particle-or-given",),
         notes="'st' is both a title and an ambiguous particle (#367), "
               "so this shape reaches group's PARTICLE_OR_GIVEN "
               "emitter, which is guarded on the chain having merged "
               "something. An ungated marker stop made the chain merge "
               "nothing for a DIFFERENT reason than the guard assumes, "
               "silencing the report while still deciding the fork -- "
               "the shape A1 forbids and #405 tracks. Pinned because "
               "removing a report a caller already sees is worse than "
               "never emitting one"),
    Case("maiden_marker_particles_on_both_sides",
         "Anna von der Müller geb. von der Berg",
         {"given": "Anna", "family": "von der Müller",
          "maiden": "von der Berg"},
         classification="fix(#399)",
         notes="a particle chain on each side of the marker. This is "
               "the shape decisions.md#M2 first cited against moving "
               "the maiden handler ahead of the chain and then "
               "retracted -- merged and unmerged pieces hand the "
               "consumer the same words -- and the handler now does "
               "run ahead (#420); pinned so the claim that the reorder "
               "cannot disturb it stays checked. Before #399 the marker rode "
               "into the middle name (middle 'von der Müller geb.')"),
    Case("maiden_marker_stops_the_leading_run", "de la Cruz née Vega",
         {"family": "de la Cruz", "maiden": "Vega"},
         classification="fix(#399)",
         notes="the default-order reading of the family-first row "
               "below, added because that one is core-only and the "
               "facade runner would otherwise never see this class. "
               "Before #399: family 'de la Cruz née Vega'"),
    Case("maiden_marker_stops_the_leading_run_family_first_given_last",
         "de la Cruz née Vega",
         {"family": "de la Cruz", "maiden": "Vega"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
         classification="fix(#399)",
         notes="the sibling of the family-first row, and the point is "
               "that the two orders now AGREE: consuming the marker "
               "leaves no leftover to distribute, so the reading that "
               "distinguishes them has nothing to work on. Before "
               "#399 they differed -- given 'Vega' middle 'née' here "
               "against given 'née' middle 'Vega' under FAMILY_FIRST"),
    Case("connective_join_never_reaches_a_taken_marker",
         "Jane van der Berg née y Jones",
         {"given": "Jane", "family": "van der Berg",
          "maiden": "y Jones"},
         classification="fix(#412)",
         notes="the last of the join-swallows. #399's stop tested for "
               "a LONE marker piece, and P3's connective join ran "
               "earlier in the same stage and merged the marker into "
               "a multi-word piece the stop could not see. The marker "
               "pass now runs before every join, so there is no piece "
               "list on which a join can reach a taken marker. The "
               "maiden name is 'y Jones' by M2's own reading: the "
               "marker takes the words after it, and a connective is "
               "one of them"),
    Case("connective_carveout_counts_the_surviving_name",
         "juan y garcia nee jones",
         {"given": "juan", "middle": "y", "family": "garcia",
          "maiden": "jones"},
         classification="fix(#418)",
         notes="P3's three-word carve-out counted the marker and the "
               "maiden name, so a two-word maiden clause lifted "
               "'juan y garcia' from three words to five, 'y' joined, "
               "and when the clause left nothing was behind for the "
               "family: given 'juan y garcia', family ''. The count "
               "now sees the name that remains, so the clause changes "
               "nothing about how the rest of this name reads -- the "
               "reading is 'juan y garcia' plus a maiden name. "
               "test_parser.py asserts that over the corpus, and "
               "since #410 the only names it steps over are those "
               "that parse to nothing at all"),
    Case("bound_given_reserve_excludes_a_multi_word_maiden_name",
         "Abd Berg née Mary Jones",
         {"given": "Abd", "family": "Berg", "maiden": "Mary Jones"},
         classification="fix(#411)",
         notes="the maiden name is TWO pieces, which is what "
               "distinguishes excluding the span from excluding the "
               "marker plus one. Capping the exclusion at two pieces "
               "reproduces #411 exactly -- given 'Abd Berg', family "
               "'' -- and every other row here has a one-word maiden "
               "name, so none of them can tell the two apart. A "
               "particle-led maiden name does NOT serve: P2's chain "
               "makes 'van der Jones' a single piece"),
    Case("bound_given_join_sees_only_the_surviving_name",
         "abd née Jones Jr Smith Berg",
         {"given": "abd", "middle": "Jr Smith", "family": "Berg",
          "maiden": "Jones"},
         classification="fix(#418)",
         notes="#411's shape, re-pinned twice. The maiden walk stops "
               "at the inner suffix and takes only 'Jones'; with the "
               "marker pass ahead of the joins, P5 then sees 'abd Jr "
               "Smith Berg' and reads it exactly as it reads that "
               "name written alone. Under #411 the join declined here "
               "because the piece it would absorb was the marker; "
               "under #420 the marker was gone before P5 looked and "
               "the join took the suffix instead, given 'abd Jr'; "
               "since #421 the join declines a suffix piece as it "
               "declines a marker, so it takes nothing and 'Jr Smith' "
               "is the middle name, as for 'John Jr Smith Berg'"),
    Case("bound_given_join_takes_a_chain_carrying_a_declined_marker",
         "Abd van der Berg née Jr Jones",
         {"given": "Abd van der Berg née", "middle": "Jr",
          "family": "Jones"},
         classification="fix(#417)",
         notes="the field-level face of #417. The consumer declines "
               "(a suffix follows the marker), the particle chain "
               "takes the declined marker as the word M2 says it is, "
               "and P5 then joins the bound word to the chain -- a "
               "name piece like any other. P5's decline is for a "
               "marker standing as a word of its own, and this one "
               "is not. Under the #399 stop this read given 'Abd van "
               "der Berg', middle 'née Jr'. Pinned here because the "
               "lone-piece reading is the nicer-looking one: a "
               "marker test widened to match inside a piece would "
               "give given 'Abd', middle 'van der Berg née Jr' with "
               "the whole suite otherwise green"),
    Case("bound_given_join_declines_a_marker_before_only_a_suffix",
         "Berg, abdul née PhD",
         {"given": "abdul", "middle": "née", "family": "Berg",
          "suffix": "PhD"},
         classification="fix(#411)",
         notes="a marker the consumer declines is still a piece when "
               "P5 looks, which is why the join asks about the marker "
               "directly rather than relying on the marker pass having "
               "removed it. Nothing but a suffix follows the marker, so "
               "M2 declines -- yet the join would "
               "still absorb it, reading given 'abdul née'. The "
               "marker stays an ordinary word here (M2: with nothing "
               "after it, it is just a word)"),
    Case("bound_given_join_declines_leaving_the_suffix_reading",
         "Berg, abd née Jones",
         {"family": "Berg", "suffix": "abd", "maiden": "Jones"},
         classification="fix(#411)",
         notes="'abd' is the one word in both the bound-given and the "
               "suffix vocabulary, and P5 says the suffix reading "
               "wins in the given slot after a family comma. With the "
               "join declining, that reading is what is left -- so "
               "the name has no given name at all, matching how "
               "'Berg, abd' alone has always parsed. Pinned because "
               "it is the shape where the declining join changes most "
               "and it reads alarmingly"),
    Case("bound_given_marker_immediately_after_the_bound_word",
         "abd née Jones",
         {"given": "abd", "maiden": "Jones"},
         classification="fix(#411)",
         notes="the shortest form of the same decision: the very next "
               "piece is the marker. Empty family is M2's ordinary "
               "one-name-word behaviour, not a leftover of the join "
               "-- 'Jane née Jones' reads the same way and always "
               "has"),
    Case("bound_given_reserve_arabic_script",
         "عبد Berg née Jones",
         {"given": "عبد", "family": "Berg", "maiden": "Jones"},
         classification="fix(#411)",
         notes="the Arabic-script bound word, in the vocabulary since "
               "2.0, pinned so the reserve change reaches it too. "
               "Script segmentation is NOT the point and does not "
               "fire: the segments and the effective script are the "
               "same as for the Latin row, so what this adds is "
               "vocabulary coverage, not a second code path"),
    Case("bound_given_join_no_longer_swallows_a_marker",
         "van der Berg, abdul née Jones",
         {"given": "abdul", "family": "van der Berg",
          "maiden": "Jones"},
         classification="fix(#411)",
         notes="was the second of #412's two join-swallows and is now "
               "fixed as a side effect of #411, which is why the row "
               "is renamed rather than deleted. P5's join used to "
               "merge 'abdul' with the marker before M2's bound could "
               "see a lone marker piece. #411 made the join decline by "
               "counting the reserve without the words the maiden name "
               "takes; since #420 the marker pass takes 'née Jones' "
               "before P5 looks, leaving 'abdul' alone with nothing to "
               "join. P3's connective join was the "
               "last to go, under #412 -- "
               "connective_join_never_reaches_a_taken_marker"),
    Case("maiden_marker_ahead_of_a_conjunction",
         "Jane née and Jones Smith",
         {"given": "Jane", "maiden": "and Jones Smith"},
         classification="fix(#412)",
         notes="M2's greedy reading, with a connective among the "
               "words taken: the same as 'Jane née Jones Smith' with "
               "'and' inside it. Until #412 closed, P3's join ran "
               "first and produced a marker-HEADED piece 'née and "
               "Jones' that the lone-piece test could not see, so the "
               "name read middle 'née and Jones', family 'Smith'. "
               "The lone-piece test stays as M2's own wording "
               "('standing as a word of its own'), but with the pass "
               "ahead of the joins no default-vocabulary input reaches "
               "a marker-headed piece any more, so nothing pins its "
               "`len(piece) == 1` half: kept as definition, not as a "
               "guard -- the comment at _is_maiden_marker_piece "
               "records the measurement"),
    Case("maiden_marker_after_particles_in_a_comma_segment",
         "Smith, Jane van der Berg née Jones",
         {"given": "Jane", "middle": "van der Berg",
          "family": "Smith", "maiden": "Jones"},
         classification="fix(#399)",
         notes="the listing form, where the chain and the marker are "
               "both on the given side of the comma. Before #399 the "
               "marker and the maiden name stayed in the middle name "
               "('van der Berg née Jones'). Distinct from M2's "
               "remaining Accepted note, which is about a marker "
               "standing straight AFTER the comma"),
    Case("bound_given_reserve_excludes_the_maiden_name",
         "Abd Berg née Jones",
         {"given": "Abd", "family": "Berg", "maiden": "Jones"},
         classification="fix(#411)",
         notes="#411: P5 reserves a name word so the join always "
               "leaves a family name behind, but until #420 the "
               "reserve was counted while the marker and the maiden "
               "name were still pieces, the marker pass running after "
               "the join. Four words counted, the join fired, and when "
               "the two departed nothing was left for the family: given "
               "'Abd Berg', family ''. The pass now runs first, so the "
               "reserve sees the two-word name P5 says must not join"),
    Case("bound_given_reserve_excludes_the_maiden_name_with_particles",
         "Abd van der Berg née Jones",
         {"given": "Abd", "family": "van der Berg", "maiden": "Jones"},
         classification="fix(#411)",
         notes="the particle spelling of the row above, which is how "
               "#411 was found -- #399's chain stop put this shape in "
               "front of the reserve for the first time. The chain "
               "makes 'van der Berg' ONE piece, so the count is the "
               "same three-versus-two question"),
    Case("bound_given_reserve_still_joins_with_a_word_to_spare",
         "Abd Allah Smith née Jones",
         {"given": "Abd Allah", "family": "Smith", "maiden": "Jones"},
         classification="fix(#400)",
         notes="the control: one more name word, so the join has its "
               "word to spare even after the maiden name leaves, and "
               "fires exactly as it does without a maiden clause. "
               "Unchanged by #411 -- pinned so the fix cannot be "
               "mistaken for switching the join off near a marker"),
    Case("bound_given_reserve_maiden_and_suffix",
         "Abd Berg née Jones PhD",
         {"given": "Abd", "family": "Berg", "maiden": "Jones",
          "suffix": "PhD"},
         classification="fix(#411)",
         notes="the marker walk stops at a trailing suffix, so the "
               "excluded span is the marker plus 'Jones' and not the "
               "suffix -- which the reserve already discounted. Two "
               "different reasons for a piece not to count, on one "
               "name"),
    Case("maiden_marker_kyusei", "山田花子 旧姓 佐藤",
         {"family": "山田花子", "maiden": "佐藤"},
         classification="fix(#309)",
         notes="旧姓 is default vocabulary, not pack data: a "
               "native-script marker cannot collide with a Latin-script "
               "name and matching is whole-token, the same rule that "
               "admitted урожд. Reaches a marker that is its own TOKEN. "
               "Japanese more often brackets the marker and writes a "
               "fullwidth colon after it, and '山田（旧姓：佐藤）' under "
               "maiden_delimiters still gives maiden '旧姓：佐藤', marker "
               "and colon attached -- not because the marker escapes "
               "tagging (classify tags it fine wherever it is a token; "
               "what #329 fixed was the CONSUMING, since group's #274 "
               "rule walks pieces and a role-bearing token is not in "
               "pieces) but because ：glues marker to name into a "
               "single token, leaving nothing to drop. The spaced "
               "bracketed form is pinned by "
               "maiden_marker_kyusei_delimited below; the glued one "
               "wants the head-peel #317 tracks. 1.4.0 read this "
               "first 山田花子 / middle 旧姓 / last 佐藤 -- the marker "
               "sat in the name"),
    Case("maiden_marker_kyusei_segmented", "山田 花子 旧姓 佐藤",
         {"given": "花子", "family": "山田", "maiden": "佐藤"},
         classification="fix(#309)",
         notes="the row above with the family name spaced, so the "
               "marker is consumed from a name that already has a "
               "given side -- pinned because #274's consuming rule "
               "takes the marker plus the piece after it, and the "
               "pieces before it are what could have gone wrong. "
               "1.4.0 read this first 山田 / middle '花子 旧姓' / "
               "last 佐藤"),
    Case("maiden_marker_delimited", "Jane Smith (née Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="#329: the bracketed form now agrees with the bare "
               "maiden_marker row above -- both give maiden 'Jones'. "
               "Before, the marker rode along inside the value: "
               "extract records the clause as a span (it makes no "
               "tokens at all), tokenize gives the tokens it cuts "
               "there Role.MAIDEN, and group's #274 consuming rule "
               "walks pieces, which hold no role-bearing token; the "
               "fix drops the marker inside the CLAUSE instead. The "
               "facade runner reaches this row by performing the "
               "bucket move itself, so it is exercised twice. 1.4.0 "
               "expresses the policy the same way: "
               "measured 2026-08-02 through the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis'), it gave first "
               "Jane / last Smith / maiden 'née Jones' -- same name "
               "fields, marker still inside the value, which is the "
               "single field this change moves. Since #335 the same "
               "input reads identically with NO policy at all "
               "(maiden_marked_clause_reads_maiden_by_default below), "
               "which does not make this row redundant: the pair "
               "sitting in the maiden bucket settles the role before "
               "M3 is consulted, so this row exercises M1's path and "
               "that one exercises M3's. Rewriting it to drop the "
               "policy would delete the configured path's coverage "
               "rather than move it"),
    Case("maiden_marker_delimited_unaccented", "Jane Smith (nee Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the row above with the marker spelled unaccented, and "
               "it is the ONLY row in the suite whose value depends "
               "on 'nee' being in the default MAIDEN_MARKERS: "
               "everything else reaches the marker branch through "
               "'née', 'geb' or '旧姓', or through a stage lexicon of "
               "its own. Removing the entry now fails exactly this "
               "row's two tests, one per runner (measured 2026-08-03); "
               "before this row existed it left the whole suite green, "
               "so the shipped spelling English writes most often was "
               "one vocabulary edit from silence. 1.4.0 under the "
               "bucket-move idiom gave first Jane / last Smith / "
               "maiden 'nee Jones' (2026-08-03) -- the same diff the "
               "accented row records, which is the point: the two "
               "spellings behave alike on both sides"),
    Case("maiden_marked_clause_reads_maiden_by_default",
         "Jane Smith (née Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#335)",
         notes="rules.md#M3 -- the clause says 'maiden' out loud, so the "
               "pair enclosing it does not have to be configured. "
               "maiden_marker_delimited above is the same input under "
               "Policy(maiden_delimiters=...) and reads identically -- "
               "what M3 adds is the DEFAULT reading, where 1.4.0 and "
               "2.1 alike gave nickname 'née Jones'"),
    Case("maiden_marked_clause_interior_keeps_the_family",
         "Jane (née Jones) Smith",
         {"given": "Jane", "family": "Smith", "maiden": "Jones"},
         classification="fix(#335)",
         notes="the row that decides the MECHANISM. Extracting the "
               "clause as a Role.MAIDEN region keeps the closing "
               "delimiter as the maiden name's right boundary; masking "
               "the delimiters and letting M2's bare-marker rule "
               "consume the content instead would read maiden 'Jones "
               "Smith' with an empty family, because M2's take runs to "
               "the end of the name. The parens say where it stops"),
    Case("maiden_marked_clause_one_word_stays_a_nickname",
         "Jane Smith (née)",
         {"given": "Jane", "family": "Smith", "nickname": "née"},
         notes="M3's boundary: a marker with no word after it is not a "
               "maiden clause. Without this condition the default "
               "reading of a lone parenthesized marker would flip to "
               "maiden 'née', and M1's own (Nee) boundary -- a "
               "one-word clause keeps its word, which may be the "
               "surname Nee -- would be contradicted on the "
               "unconfigured path. Parity: 1.4.0 read nickname 'née'"),
    Case("markerless_parenthesized_clause_stays_a_nickname",
         "Cherice J. (Johnson) Williams",
         {"given": "Cherice", "middle": "J.", "family": "Williams",
          "nickname": "Johnson"},
         notes="M3's other boundary, and the reason the maiden "
               "delimiters remain worth configuring: the parenthesized "
               "birth surname without a marker is a real US convention "
               "and a corpus name (corpus_issues.jsonl), but nothing in "
               "the clause says 'maiden', so it stays a nickname by "
               "default. Only a caller who knows their data can say "
               "otherwise, which is what Policy(maiden_delimiters=...) "
               "is for. Parity"),
    Case("maiden_marked_clause_beside_a_nickname",
         'Jane "Janey" Smith (née Jones)',
         {"given": "Jane", "family": "Smith", "nickname": "Janey",
          "maiden": "Jones"},
         classification="fix(#335)",
         notes="two clauses, two roles. Through 2.1 both were "
               "nicknames and the facade joined them into one value, "
               "'Janey née Jones' -- the merged-nickname half of #335"),
    Case("maiden_marker_delimited_unmarked_content",
         "Jane Smith (Mary Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Mary Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="parity",
         notes="the row the rest of the #329 battery leaves out: a "
               "multi-token clause whose first token is NOT a marker, "
               "which keeps every one of its tokens. The clause-size "
               "test and the marker-tag test are separate conditions, "
               "and this shape is one of the two that separates them "
               "-- with the tag test removed the pass eats the opening "
               "word of every delimited maiden name ('Jones' here), "
               "and five tests go red across this row and "
               "maiden_marker_delimited_trailing_marker (measured "
               "2026-08-03). What is this row's alone is that NO token "
               "in its clause is a marker; the trailing-marker row has "
               "one, just not first. Measured against "
               "1.4.0 2026-08-03 through the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis'): first Jane / "
               "last Smith / maiden 'Mary Jones', so #329 leaves this "
               "input exactly where v1 had it"),
    Case("maiden_marker_delimited_three_token_clause",
         "Jane Smith (née Mary Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Mary Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the only clause in the battery holding THREE tokens, "
               "which is what bounds the drop in both directions: it "
               "takes the marker and stops. Every other delimited row "
               "has a two-token clause, where 'the first token' and "
               "'all but the last token' agree, so two opposite "
               "mistakes both survive them -- restricting the drop to "
               "a clause of exactly two tokens gives maiden 'née Mary "
               "Jones' here (marker never dropped), and letting it eat "
               "the token after the marker gives maiden 'Jones' "
               "(a name eaten). Both measured 2026-08-03. 1.4.0 under "
               "the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis') gave first Jane "
               "/ last Smith / maiden 'née Mary Jones' (2026-08-03) -- "
               "marker inside the value, the single field #329 moves"),
    Case("maiden_marker_delimited_trailing_marker",
         "Jane Smith (Jones née)",
         {"given": "Jane", "family": "Smith", "maiden": "Jones née"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="parity",
         notes="the drop takes the clause's FIRST token or nothing: a "
               "marker anywhere else in the clause is content. Pinned "
               "because the cheap generalization -- drop every marker "
               "in the clause -- passes the whole battery above and "
               "gives maiden 'Jones' here, and because no marker the "
               "shipped vocabulary carries is written after the name "
               "it marks. Measured against 1.4.0 2026-08-03 "
               "through the bucket-move idiom: first Jane / last "
               "Smith / maiden 'Jones née'"),
    Case("maiden_marker_delimited_beside_a_nickname_clause",
         'Jane "née Janie" Smith {née Jones}',
         {"given": "Jane", "family": "Smith", "maiden": "Janie Jones"},
         policy=Policy(maiden_delimiters=frozenset({("{", "}")})),
         classification="fix(#335)",
         notes="#335 took this row's job away, and the row is kept to "
               "record that. It was the pin for the #329 drop pass "
               "being scoped to MAIDEN clauses -- two extracted "
               "clauses, both opening with a marker word, only the "
               "maiden one losing it, nickname 'née Janie' and maiden "
               "'Jones'. M3 now reads the QUOTED clause as maiden too, "
               "since it is marker-led like the braced one and M3 is "
               "keyed on content rather than on which pair matched, so "
               "there is no nickname left to contrast: both clauses "
               "are maiden and M1's independence rule joins them into "
               "one value. The role filter it used to discriminate "
               "(the 'role is not Role.MAIDEN' branch of "
               "_group.group's drop pass) is still reachable and "
               "still pinned -- "
               "that job moved to "
               "marker_glued_to_punctuation_keeps_the_clause_a_nickname "
               "below, which reaches a marker-led clause M3 declines. "
               "1.4.0 cannot express a brace delimiter at "
               "all (its buckets hold the NAMES of compiled regexes "
               "and there is no brace one; measured 2026-08-03, "
               "maiden_delimiters['brace'] = ('{', '}') is accepted "
               "and then raises ValueError('references unknown "
               "regexes key') at parse time), so the "
               "classification compares against its single reading, "
               "first Jane / middle 'Smith {née' / last 'Jones}' / "
               "nickname 'née Janie' -- braces as name text, the same "
               "convention maiden_marker_kyusei_delimited uses for a "
               "knob with no v1 spelling (re-measured 2026-08-26, "
               "unchanged)"),
    Case("marker_glued_to_punctuation_keeps_the_clause_a_nickname",
         'Jane "née, Janie" Smith (née Jones)',
         {"given": "Jane", "family": "Smith", "nickname": "née Janie",
          "maiden": "Jones"},
         classification="fix(#335)",
         notes="M3 and the #329 drop pass ask the marker question of "
               "different things, and this row is where the two "
               "answers differ. M3 splits the clause on WHITESPACE and "
               "normalizes the first word: 'née,' normalizes to "
               "'née,' -- _normalize strips a trailing period but not "
               "a comma -- so M3 declines and the quoted clause stays "
               "a nickname. tokenize splits the comma off as a "
               "separator, so the clause's first TOKEN is 'née' and "
               "carries vocab:maiden-marker, which is exactly what "
               "the 'role is not Role.MAIDEN' branch of "
               "_group.group's drop pass exists to refuse. Measured 2026-08-26: with that "
               "branch removed this reads nickname 'Janie', the "
               "marker dropped out of a nickname. BOTH clauses are "
               "load-bearing -- the drop pass is gated on the name "
               "holding a MAIDEN region at all, so the same quoted "
               "clause alone ('Jane \"née, Janie\" Smith') leaves the "
               "branch unexercised, removing it measurably changes "
               "nothing there. The paren clause is what opens the "
               "block, and M3 is what makes it maiden. The comma is "
               "absent from the nickname VALUE because tokenize "
               "treats COMMA_CHARS as a separator inside every region "
               "including an extracted one, which predates #335 and "
               "is not part of it. 1.4.0 gave first Jane / last Smith "
               "/ nickname 'née, Janie née Jones' (2026-08-26) -- "
               "comma kept, both clauses merged into the one field, "
               "which is the merged-nickname half of #335"),
    Case("maiden_marker_delimited_two_clauses",
         "Jane Smith (Nee) (Jones)",
         {"given": "Jane", "family": "Smith", "maiden": "Nee Jones"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="parity",
         notes="the scoping pin for #329, and the row a simplification "
               "would break: the drop is CLAUSE-scoped, so a one-token "
               "clause keeps its token even when the next clause could "
               "read as the name it marks. A neighbour-scoped rule -- "
               "drop a marker whose successor is also maiden -- gives "
               "'Jones' here, eating a real surname (Irish Ní/Nee, and "
               "a Chinese romanization). Unaccented 'nee' is in the "
               "default MAIDEN_MARKERS, so the 'Nee' token really is "
               "tagged and the CLAUSE bound is the only thing keeping "
               "it -- which is what makes this row kill a rule that "
               "drops the bound. The VALUE does not depend on that "
               "vocabulary entry, though: the clause test is checked "
               "before the tag test, so 'nee' leaving MAIDEN_MARKERS "
               "would leave this expectation green. "
               "maiden_marker_delimited_unaccented above is the row "
               "that fails when it goes. "
               "Parity is measured, not inferred from the row being "
               "untouched: 1.4.0 under the same bucket move gave first "
               "Jane / last Smith / maiden 'Nee Jones' (2026-08-02), "
               "so the two clauses joined with a space on that side "
               "too -- the classification the facade runner checks "
               "against, since it expresses this policy through the "
               "same bucket move"),
    Case("maiden_marker_delimited_content_free", "(née —)",
         {},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the drop can empty the WHOLE parse, and that is a "
               "decision rather than fallout. assemble's content test "
               "runs over the SURVIVING tokens, so once the marker "
               "goes structural the em dash is the only one left, no "
               "alnum character remains and every field clears -- "
               "bool() False. Reachable only where a maiden clause is "
               "the entire input and its non-marker tokens are pure "
               "punctuation -- the same clause inside a name is "
               "maiden_marker_delimited_content_free_in_a_name below. "
               "Coherent with the model 2.0 "
               "already had: a dropped marker is structural like a "
               "delimiter character, and '(-)' empties on both sides "
               "of this change. Structurally unreachable on the bare "
               "#274 path, whose scan starts at piece 1, so a token "
               "always survives ahead of the marker ('née —' gives "
               "given 'née', family '—'). Do NOT restore the old value "
               "with a guard on what else the clause holds: that is a "
               "different rule, and it would leave maiden holding "
               "marker-plus-punctuation. fix rather than parity "
               "because 1.4.0 CAN express this policy and disagrees: "
               "measured 2026-08-03 through the bucket-move idiom "
               "maiden_delimiters['parenthesis'] = "
               "nickname_delimiters.pop('parenthesis'), it gave maiden "
               "'née —' and a truthy name, as pre-#329 did. The 2.0 "
               "content rule already deviated from 1.4.0 here ('(-)' "
               "is maiden '-' in 1.4.0); this change moves one more "
               "input into its reach"),
    Case("maiden_marker_delimited_content_free_in_a_name",
         "Jane Smith (née —)",
         {"given": "Jane", "family": "Smith", "maiden": "—"},
         policy=Policy(maiden_delimiters=frozenset({("(", ")")})),
         classification="fix(#329)",
         notes="the row above with a name in front of the clause, "
               "which is what bounds the emptying: assemble's content "
               "test is about the WHOLE parse, so a clause of "
               "marker-plus-punctuation empties only a name that is "
               "nothing else. Here Jane Smith carries the alnum "
               "content and maiden keeps the em dash. Pinned because "
               "the drop could plausibly have been widened to take the "
               "clause's punctuation with the marker -- that mutation "
               "gives maiden '' here (measured 2026-08-03) and leaves "
               "the row above green, since both readings empty a parse "
               "that is only the clause. 1.4.0 under the bucket-move "
               "idiom gave first Jane / last Smith / maiden 'née —' "
               "(2026-08-03)"),
    Case("maiden_marker_kyusei_delimited", "山田 花子（旧姓 佐藤）",
         {"given": "花子", "family": "山田", "maiden": "佐藤"},
         policy=Policy(
             maiden_delimiters=frozenset({("(", ")"), ("（", "）")})),
         classification="fix(#329)",
         notes="the Japanese bracketed form that #329 reaches: the "
               "marker is spaced off inside fullwidth brackets, so it "
               "is a token of its own and the clause-scoped drop "
               "applies. The form Japanese more often writes puts a "
               "fullwidth colon after the marker instead, and "
               "'山田（旧姓：佐藤）' is ONE token -- nothing reaches it, "
               "and it wants the head-peel #317 tracks (see "
               "maiden_marker_kyusei above). Unlike its two Latin "
               "siblings, 1.4.0 cannot express this policy at all: v1's "
               "delimiter buckets hold the NAMES of compiled regexes, "
               "and no fullwidth pair is among them (#273 added it), so "
               "maiden_delimiters['fullwidth_parenthesis'] = ('（', '）') "
               "raises ValueError('references unknown regexes key') at "
               "parse time. The classification therefore compares "
               "against 1.4.0's single reading, first 山田 / middle "
               "'花子（旧姓' / last '佐藤）' -- the brackets were name "
               "text -- the same convention "
               "ko_honorific_period_under_strict_comma_suffixes uses "
               "for a knob with no v1 spelling. That reading is also "
               "what the differential harness sees, since it runs the "
               "corpus under the DEFAULT policy where （） is a #273 "
               "NICKNAME delimiter and nothing in #329 is reachable; "
               "the diff is classified there under "
               "fix(cjk-fullwidth-paren-nickname)"),
    Case("east_slavic", "Сидоров Иван Петрович",
         {"given": "Иван", "middle": "Петрович", "family": "Сидоров"},
         policy=_ES),
    Case("turkic", "Mammadova Aygun Ali kizi",
         {"given": "Aygun", "middle": "Ali kizi", "family": "Mammadova"},
         policy=_TK),
    Case("ru_pack_formal_rotation", "Сидоров Иван Петрович",
         {"given": "Иван", "middle": "Петрович", "family": "Сидоров"},
         locale="ru",
         notes="the RU pack end-to-end: same expectation as the "
               "east_slavic synthetic row, through parser_for"),
    Case("ru_pack_transliterated", "Petrov Ivan Sergeyevich",
         {"given": "Ivan", "middle": "Sergeyevich", "family": "Petrov"},
         locale="ru"),
    Case("ru_pack_comma_untouched", "Петров, Иван",
         {"given": "Иван", "family": "Петров"},
         locale="ru",
         notes="a comma is an explicit signal that suppresses the "
               "rotation (rule O1)"),
    Case("tr_az_pack_marker", "Mammadova Aygun Ali kizi",
         {"given": "Aygun", "middle": "Ali kizi", "family": "Mammadova"},
         locale="tr_az",
         notes="the TR_AZ pack end-to-end: same expectation as the "
               "turkic synthetic row (pinned live during Plan 3), "
               "through parser_for"),
    Case("empty", "", {}),
    Case("whitespace", "   ", {}),
    Case("bare_ambiguous_acronym", "John Ed",
         {"given": "John", "family": "Ed"},
         ambiguities=("suffix-or-name",),
         notes="'ed' is an ambiguous acronym; bare form is a name (C1), "
               "and the parse reports which reading it took"),
    Case("comma_ambiguous_acronym", "Smith, Ed",
         {"given": "Ed", "family": "Smith"}),
    Case("ambiguous_acronym_with_suffix", "John Ed III",
         {"given": "John", "family": "Ed", "suffix": "III"},
         ambiguities=("suffix-or-name",)),
    Case("phd_split", "John Ph. D.",
         {"given": "John", "suffix": "Ph. D."},
         notes="v1 fix_phd; healed via the stable 'joined' tag"),
    Case("phd_split_mid_name", "Dr. John Ph. D. Smith",
         {"title": "Dr.", "given": "John", "family": "Smith",
          "suffix": "Ph. D."}),
    Case("phd_split_leading", "Ph. D. John Smith",
         {"given": "John", "family": "Smith", "suffix": "Ph. D."},
         classification="fix",
         notes="v1 healed 'Ph.'+'D.' only when trailing; leading it "
               "split them (title 'Ph.', given 'D.', real given name "
               "pushed to middle). Surfaced by the issue-tracker "
               "corpus, which is where this shape existed at all."),
    Case("leading_never_given_particle", "de la Vega",
         {"family": "de la Vega"},
         notes="v1 handle_non_first_name_prefix: never-given leading "
               "particle folds the whole name into family"),
    Case("unbalanced_quote", 'Jon "Nick Smith',
         {"given": "Jon", "middle": '"Nick', "family": "Smith"},
         ambiguities=("unbalanced-delimiter",),
         notes="quote char stays literal (rule N2)"),
    Case("suffix_stays_suffix", "Johnson PhD",
         {"given": "Johnson", "suffix": "PhD"},
         classification="fix(suffix-routing)",
         notes="v1 routes a lone trailing suffix to family "
               "(first=Johnson last=PhD); v2 keeps recognized "
               "suffixes in suffix"),
    Case("suffix_stays_suffix_title", "Mr. Johnson PhD",
         {"title": "Mr.", "family": "Johnson", "suffix": "PhD"},
         classification="fix(#410)",
         notes="two fixes meet here. v1 routed a lone trailing suffix "
               "to family (title 'Mr.', first 'Johnson', last 'PhD') "
               "and v2 keeps recognized suffixes in `suffix` "
               "(fix(suffix-routing)); that left 'Johnson' in `given` "
               "with an empty family until #410 stopped counting the "
               "suffix as a further name word"),
    Case("family_comma_lone_title", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="pre-comma is definitionally family; v1 put it in first"),
    Case("family_comma_all_title_segment_keeps_split", "John Smith, Mr.",
         {"title": "Mr.", "given": "John", "family": "Smith"},
         classification="fix(comma-family)",
         notes="a comma followed only by titles said nothing about "
               "where the family name ends, so segment 0 keeps its "
               "positional read instead of merging into one family "
               "name (v1 read first 'John Smith'; 2.0 read it as the "
               "family, the comma-precomma-family move)"),
    Case("family_comma_all_title_segment_needs_two_pieces", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="the guard on family_comma_all_title_segment_keeps_split: "
               "one pre-comma piece has no split to keep, and the "
               "positional read would make it a lone GIVEN"),
    Case("family_comma_untitled_segment_still_merges", "John Smith, Jones",
         {"given": "Jones", "family": "John Smith"},
         notes="the non-flip: a post-comma NAME means the comma did fix "
               "the family, so segment 0 stays wholly family (v1 parity)"),
    # -- #296: the TITLES/suffix overlap audit. A word that is only ever
    # a postnominal leaves TITLES, so the title peel stops claiming it
    # first. Leading position is the price and is pinned here.
    Case("audit_phd_leading_is_a_name", "PhD Smith",
         {"given": "PhD", "family": "Smith"},
         classification="fix(#296)",
         notes="'phd' left TITLES because M.D./Ph.D. are postnominal "
               "only; nothing is prenominal-'PhD', so the leading "
               "position falls through to the positional read"),
    Case("audit_jr_leading_is_a_name", "Jr Smith",
         {"given": "Jr", "family": "Smith"},
         classification="fix(#296)",
         notes="same as audit_phd_leading_is_a_name: 'jr' is never "
               "prenominal in any tradition"),
    Case("audit_md_leading_stays_a_title", "Md Abdul Karim",
         {"title": "Md", "given": "Abdul", "family": "Karim"},
         notes="the one word the 2026-07-30 table got wrong: 'md' KEEPS "
               "dual membership. Bare 'Md' before a name is the "
               "Bengali and South Asian Muslim abbreviation of "
               "Muhammad (#343/#345's corpus rows), a prenominal use "
               "the 'postnominal only' disposition did not consider; "
               "'MD' after the name is the degree. Position decides, "
               "as for 'sr'"),
    Case("audit_md_after_comma_is_the_degree", "Smith, MD",
         {"family": "Smith", "suffix": "MD"},
         classification="fix(#296)",
         notes="the third leg of 'position decides' for 'md'"),
    Case("audit_do_leading_is_a_name", "Do Nguyen",
         {"given": "Do", "family": "Nguyen"},
         ambiguities=("particle-or-given",),
         classification="fix(#296)",
         notes="the disposition's own argument, realized: 'Do' is a "
               "Vietnamese name, and dropping the title membership is "
               "what lets it be read as one -- with the fork 'Van "
               "Johnson' reports, since 'do' is an ambiguous particle "
               "too and the title membership had been hiding the fork"),
    Case("audit_se_leading_is_a_name", "SE Smith",
         {"given": "SE", "family": "Smith"},
         classification="fix(#296)",
         notes="Structural Engineer is a US licensure postnominal (the "
               "PE/SE pair); no prenominal SE convention exists"),
    Case("audit_junior_leading_is_a_name", "Junior Smith",
         {"given": "Junior", "family": "Smith"},
         classification="fix(#296)",
         notes="and 'Junior' is a real given name besides"),
    # the non-flips: trailing position was already right and must stay
    Case("audit_phd_trailing_unchanged", "John Smith PhD",
         {"given": "John", "family": "Smith", "suffix": "PhD"}),
    Case("audit_jr_trailing_unchanged", "John Smith Jr.",
         {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Case("audit_lt_leading_stays_a_title", "Lt. Smith",
         {"title": "Lt.", "family": "Smith"},
         notes="'lt' KEPT its dual membership -- a prenominal rank with "
               "real retired-designation postnominal use; position "
               "decides, so leading is untouched"),
    Case("audit_sr_leading_stays_a_title", "Sr. Garcia",
         {"title": "Sr.", "family": "Garcia"},
         notes="Señor (leading) vs Senior (trailing): kept dual, and "
               "the leading read is the peel's normal path"),
    Case("audit_sra_leading_stays_a_title", "Sra Garcia",
         {"title": "Sra", "family": "Garcia"},
         notes="Señora is title-only; the SUFFIX_ACRONYMS entry was v1 "
               "residue and is what got dropped, not this"),
    Case("audit_dr_leading_stays_a_title", "Dr. Smith",
         {"title": "Dr.", "family": "Smith"}),
    Case("audit_dr_after_comma_is_a_title", "Smith, Dr.",
         {"title": "Dr.", "family": "Smith"},
         classification="fix(comma-family)",
         notes="'dr' left SUFFIX_WORDS: 'Dr.' is not a postnominal in "
               "any tradition and the entry was v1 residue. This is "
               "what keeps the postnominal reading of a lone post-comma "
               "suffix piece from taking it -- the vocabulary decides, "
               "not the position"),
    Case("audit_dr_after_two_word_comma_keeps_the_split", "John Smith, Dr.",
         {"title": "Dr.", "given": "John", "family": "Smith"},
         classification="fix(comma-family)",
         notes="with 'dr' gone from the suffix sets the post-comma word "
               "is a title only, so the no-name-word repair keeps the "
               "pre-comma split. v1, and 2.0 through master, kept the "
               "same split by a different route -- 'dr' was "
               "suffix-tagged, making this a SUFFIX_COMMA -- but put "
               "'Dr.' in suffix, not title: a change against every "
               "baseline"),
    Case("audit_sra_after_comma_is_a_title", "Smith, Sra",
         {"title": "Sra", "family": "Smith"},
         classification="fix(comma-family)",
         notes="the same removal on the acronym side"),
    Case("audit_ms_after_comma_is_the_degree", "Smith, MS",
         {"family": "Smith", "suffix": "MS"},
         classification="fix(#296)",
         notes="'ms' is a genuine dual -- 'Ms.' leading, 'MS' the "
               "degree trailing -- and position decides. The 2026-07-30 "
               "table put it in the AMBIGUOUS set so bare 'MS' would "
               "read as the honorific; measured, that gate is "
               "position-blind: 'John Smith, MS' lost its suffix-comma "
               "route and read title 'MS', and 'Smith, Ms.' passed the "
               "gate on its one period anyway. The second deviation "
               "from the table, with 'md'"),
    Case("audit_ms_after_two_word_comma_is_the_degree", "John Smith, MS",
         {"given": "John", "family": "Smith", "suffix": "MS"},
         notes="the common listing, unchanged at every baseline -- "
               "what the ambiguous gate would have cost"),
    Case("audit_ms_leading_is_the_honorific", "Ms. Smith",
         {"title": "Ms.", "family": "Smith"}),
    Case("audit_perioded_ms_is_the_degree", "Smith, M.S.",
         {"family": "Smith", "suffix": "M.S."}),
    Case("audit_ms_honorific_spelling_after_comma_is_the_postnominal",
         "Smith, Ms.",
         {"family": "Smith", "suffix": "Ms."},
         classification="fix(#296)",
         notes="the cost of the dual, recorded: after a family comma "
               "the slot is postnominal and the vocabulary says suffix, "
               "whatever the period suggests -- as for 'Smith, Sr.'. "
               "Every baseline read title 'Ms.' (the design-docs "
               "review found the flip unrecorded). 'Smith, Ms. Jane' "
               "still reads the title: a name word follows"),
    Case("audit_ms_before_a_name_after_comma_is_the_title",
         "Smith, Ms. Jane",
         {"title": "Ms.", "given": "Jane", "family": "Smith"}),
    Case("audit_sa_after_comma_is_the_postnominal", "Smith, SA",
         {"family": "Smith", "suffix": "SA"},
         classification="fix(#296)",
         notes="the same dual: Special Agent leading, the business "
               "form trailing"),
    Case("audit_perioded_sa_is_the_postnominal", "Smith, S.A.",
         {"family": "Smith", "suffix": "S.A."}),
    Case("audit_bare_do_after_comma_is_a_name", "Smith, DO",
         {"given": "DO", "family": "Smith"},
         classification="fix(#296)",
         notes="'do' left TITLES but was already AMBIGUOUS, so the bare "
               "spelling is neither title nor suffix and falls to the "
               "given position -- the period gate handles the real "
               "collision, which is that 'Do' is a name"),
    Case("audit_perioded_do_after_comma_is_a_suffix", "Smith, D.O.",
         {"family": "Smith", "suffix": "D.O."}),
    # -- the TRAILING half of the same two removals. `dr` and `sra` are
    # the ONLY audit words that lose SUFFIX membership; every other
    # audit word keeps its suffix membership, so trailing position is
    # untouched for them.
    Case("audit_dr_trailing_joins_the_title_word_gap", "John Smith Dr.",
         {"given": "John", "middle": "Smith", "family": "Dr."},
         classification="fix(#296)",
         notes="'dr' left SUFFIX_WORDS, so a trailing 'Dr.' is no "
               "longer suffix vocabulary and falls to the positional "
               "read, taking the family name with it. NOT a new defect "
               "class -- no trailing title word routes to title on the "
               "no-comma path, so 'John Smith Prof.' and 'John Smith "
               "Mr.' already read this way (both pinned below; #316 is "
               "the open question). The v1-residue suffix entry was the "
               "only thing making 'dr' behave unlike every other "
               "title-only word. This row records that 'dr' JOINED the "
               "existing behavior, not that the behavior is right"),
    Case("audit_sra_trailing_joins_the_title_word_gap", "John Smith Sra",
         {"given": "John", "middle": "Smith", "family": "Sra"},
         classification="fix(#296)",
         notes="the same move for the other word losing suffix "
               "membership"),
    Case("family_comma_lone_generational_suffix", "Smith, Jr.",
         {"family": "Smith", "suffix": "Jr."},
         classification="fix(#296)",
         notes="the issue as filed: the peel's whole-segment exception "
               "claimed 'Jr.' through the period-abbreviation inference "
               "even after the audit, so the ordering change is what "
               "actually reaches this input"),
    Case("family_comma_lone_generational_suffix_bare", "Smith, Jr",
         {"family": "Smith", "suffix": "Jr"},
         classification="fix(#296)"),
    Case("family_comma_lone_degree", "Smith, PhD",
         {"family": "Smith", "suffix": "PhD"},
         classification="fix(#296)"),
    Case("family_comma_dual_word_reads_postnominal", "Smith, Sr.",
         {"family": "Smith", "suffix": "Sr."},
         classification="fix(#296)",
         notes="Señor vs Senior: 'sr' keeps both memberships and this "
               "is the position that picks Senior"),
    Case("family_comma_dual_rank_reads_postnominal", "Smith, CPT",
         {"family": "Smith", "suffix": "CPT"},
         classification="fix(#296)",
         notes="the retired-designation reading of a prenominal rank"),
    Case("family_comma_lone_esquire_is_the_postnominal", "Smith, Esq.",
         {"family": "Smith", "suffix": "Esq."},
         classification="fix(#296)",
         notes="H2's period-abbreviation inference reads a LEADING "
               "'Esq.' as a title ('Esq. Smith'); after a family comma "
               "the slot is postnominal and the vocabulary says "
               "suffix, so the inference does not run"),
    # -- #325: the whole credential run, not the lone piece
    Case("family_comma_split_credential_run", "Smith, Ph. D. Jr.",
         {"family": "Smith", "suffix": "Ph. D. Jr."},
         classification="fix(#325) + fix(#429)",
         notes="one word before the comma, the space-split 'Ph. D.' "
               "and a suffix after it: the lone-piece route did not "
               "apply and the merged credential fell through to the "
               "given name (a 1.4.0 regression -- v1 read suffix 'Ph. "
               "D.', title 'Jr.'). A run that is nothing but suffix "
               "pieces is the credential run C1 describes, whole -- "
               "and #429 made it render whole too, where #325 shipped "
               "it as 'Ph. D., Jr.' with a comma the writer never "
               "typed. The full-name 'John Smith, Ph. D. Jr.' rendered "
               "it unjoined at 2.0.0 and after -- 1.4.0 rendered "
               "'Ph. D., Jr.' there too -- so this row now agrees with "
               "the form it has agreed with since 2.0"),
    Case("family_comma_credential_run_then_numeral", "Smith, Ph. D. III",
         {"family": "Smith", "suffix": "Ph. D. III"},
         classification="fix(#325) + fix(#429)",
         notes="the numeral does not end the run; the render lost its "
               "inserted comma with the rest (#429)"),
    Case("family_comma_two_credentials", "Smith, PhD Jr.",
         {"family": "Smith", "suffix": "PhD Jr."},
         classification="fix(#325) + fix(#429)",
         notes="'PhD' led the run as a title until the audit; the audit "
               "alone would have made it the given name, which is why "
               "the ordering shipped in the same commit. The run is "
               "suffixes, and since #429 renders as one entry rather "
               "than 'PhD, Jr.'"),
    Case("family_comma_title_led_credential_run", "Smith, Dr. MD PhD",
         {"title": "Dr.", "family": "Smith", "suffix": "MD PhD"},
         classification="fix(#429)",
         notes="the title-led run: assign routes Dr. to TITLE and the "
               "two credentials to SUFFIX, so the ENTRY is the "
               "credential run, not the whole segment. 384 inputs of "
               "this shape moved with #429 and none was pinned until "
               "the review said so"),
    Case("family_comma_title_between_credentials", "Smith, MD Dr. PhD",
         {"title": "Dr.", "family": "Smith", "suffix": "MD PhD"},
         classification="fix(#429)",
         notes="the entry is sticky across a piece that is not in it: "
               "an interleaved title must not split the run it sits "
               "in, or the render inserts the very comma #429 removes"),
    Case("family_comma_title_led_run_keeps_the_written_comma",
         "Smith Jr., Mr. Jr.",
         {"title": "Mr.", "family": "Smith", "suffix": "Jr., Jr."},
         notes="THE #429 REGRESSION GUARD, and unchanged since 1.4.0. "
               "The pre-comma name leaves a suffix, and the segment "
               "after the comma is title-led. #429's first draft let "
               "the title piece OPEN the entry, so the following Jr. "
               "was tagged as a continuation and the view joined it "
               "backward across the writer's own comma -- suffix "
               "'Jr. Jr.', the exact inverse of the bug #429 fixes. "
               "Only a piece that renders into the same run may "
               "continue an entry"),
    Case("family_comma_written_commas_are_kept", "Smith, MD, PhD",
         {"family": "Smith", "suffix": "MD, PhD"},
         notes="the negative control for #429, and the distinction the "
               "whole change rests on: the parser renders the run as "
               "the writer spaced it, and never stops emitting a comma "
               "the writer typed. Parity at every baseline"),
    Case("family_comma_run_matches_the_full_name_form", "John Smith, MD PhD",
         {"given": "John", "family": "Smith", "suffix": "MD PhD"},
         notes="the full-name twin of family_comma_suffix_run_renders_"
               "unjoined, and the reference #429 brought the one-word "
               "form into line with. Unchanged since 1.4.0, so this row "
               "fails if a future change fixes one form by breaking the "
               "other"),
    Case("family_comma_segment_zero_is_not_the_run", "MD PhD Jr., John",
         {"given": "John", "family": "MD", "suffix": "PhD, Jr."},
         notes="segment 0 is the family segment even when it is wholly "
               "credential-shaped, so the one-entry join is asked of "
               "segment 1 alone. Dropping that conjunct left the whole "
               "suite green while this shape's suffix silently became "
               "'PhD Jr.' (the mutation matrix found it)"),
    Case("family_comma_run_ending_in_a_numeral", "Smith, PSM I",
         {"family": "Smith", "suffix": "PSM I"},
         classification="fix(#430)",
         notes="the credential run does not end because its last word "
               "is a roman numeral: PSM I is Professional Scrum Master "
               "level I, and the numeral describes the credential "
               "rather than the person's generation. The run read as "
               "given 'PSM' + suffix 'I' because the initial veto in "
               "is_suffix_piece keeps a numeral out of a credential "
               "run, so the segment did not look like one"),
    Case("family_comma_run_numeral_ignores_the_period", "Smith, PSM I.",
         {"family": "Smith", "suffix": "PSM I."},
         classification="fix(#430)",
         notes="and the period does not end it either. After a suffix "
               "word the numeral is describing that suffix, and an "
               "initial in that position is not a name shape anyone "
               "writes -- so the abbreviation reading that governs "
               "#432 does not reach here. The full-name 'John Smith, "
               "PSM I.' has read it this way all along"),
    Case("family_comma_run_numeral_after_a_dual_word", "Smith, MD I",
         {"family": "Smith", "suffix": "MD I"},
         classification="fix(#430)",
         notes="the same shape reached through the leading-title peel "
               "instead: md is TITLES vocabulary too (the #296 "
               "deviation), so this read title 'MD' + given 'I' where "
               "'Smith, PSM I' read given 'PSM' + suffix 'I'. Two "
               "wrong answers, one cause -- a fix verified on PSM "
               "alone would leave this one broken and look green. "
               "'Smith, Jr. I' is the same story by the other route, "
               "reaching the peel through the period-abbreviation "
               "inference rather than TITLES membership, and is the "
               "spelling a writer actually produces; it had a row of "
               "its own until the mutation matrix showed the two trace "
               "identically once fixed -- both heads are suffix pieces "
               "now, so is_leading_title is never consulted for either"),
    Case("family_comma_numeral_after_a_name_is_an_initial",
         "Smith, John V.",
         {"given": "John", "middle": "V.", "family": "Smith"},
         classification="fix(#432)",
         notes="the other half of the boundary: after a NAME word the "
               "period is decisive, because it marks an abbreviation "
               "and an abbreviation is name material. 'Smith, John B.' "
               "has always read middle 'B.'; the only thing that made "
               "V. different is that V is also suffix vocabulary"),
    Case("family_comma_bare_numeral_after_a_name_is_the_suffix",
         "Smith, John V",
         {"given": "John", "family": "Smith", "suffix": "V"},
         notes="THE BOUNDARY, and v1 parity (#144): with no period "
               "there is no abbreviation, so the numeral is the "
               "generation it looks like. This row is what makes "
               "#432's fix a period test rather than a numeral test"),
    Case("family_comma_title_resets_the_credential_run", "Smith, PSM Dr. I",
         {"given": "PSM", "middle": "Dr.", "family": "Smith",
          "suffix": "I"},
         notes="THE RESET, and unchanged since 1.4.0. A title ends the "
               "run: what follows a bare title is not continuing a "
               "credential, so the numeral behind it does not join and "
               "the segment is no run at all. Removing that one line "
               "left the whole suite green while this became title "
               "'Dr.' + suffix 'PSM I' -- the reset fires 60 times "
               "across the suite and until this row no input observed "
               "it, which is the inert-measurement shape"),
    Case("family_comma_run_numeral_after_a_split_credential",
         "Smith, Ph. D. I",
         {"family": "Smith", "suffix": "Ph. D. I"},
         classification="fix(#430)",
         notes="the numeral continues a run whose head is a MERGED "
               "piece -- the Ph./D. pair the #325 split-credential "
               "merge builds, which carries 'suffix' in its piece tags "
               "rather than on a single token. A structurally different "
               "pin on the same three readers as the PSM rows, so an "
               "edit to those cannot quietly unpin the render join"),
    Case("family_comma_numeral_behind_a_suffix_is_not_an_initial",
         "Smith, John PhD I.",
         {"given": "John", "family": "Smith", "suffix": "PhD, I."},
         notes="THE OTHER BOUNDARY, and parity at every baseline. The "
               "period makes a numeral name material only behind a NAME "
               "word; behind a suffix the run owns it, and the first "
               "draft of #432 read the piece alone and made this middle "
               "'I.'. Rendered with the comma because the writer typed "
               "no run here -- the segment holds a name, so it is the "
               "walk, not the one-entry join"),
    Case("family_comma_strict_keeps_the_initial_veto",
         "Smith, PSM I.",
         {"given": "PSM", "family": "Smith", "suffix": "I."},
         policy=Policy(lenient_comma_suffixes=False),
         notes="C1's strict knob still vetoes initial-shaped words, so "
               "the run ends at the numeral where lenient continues "
               "through it. #430's first draft read no policy at all "
               "and silently overrode the one knob a caller sets to "
               "prevent exactly this; nothing in the suite saw it"),
    Case("family_comma_run_with_a_name_is_not_a_run", "Smith, John Jr.",
         {"given": "John", "family": "Smith", "suffix": "Jr."},
         notes="the non-flip: a name word in the run makes it the "
               "given-and-suffix walk v1 had"),
    Case("family_comma_title_then_suffix", "Smith, Dr. Jr.",
         {"title": "Dr.", "family": "Smith", "suffix": "Jr."},
         classification="fix(comma-family)",
         notes="a title and a postnominal, each read where it stands "
               "-- the 2.0 deviation's other case (v1 read first "
               "'Jr.'), and what keeps the no-name-word test from "
               "reading 'Dr. Jr.' as one title run"),
    Case("family_comma_title_then_suffix_mr", "Smith, Mr. Jr.",
         {"title": "Mr.", "family": "Smith", "suffix": "Jr."},
         classification="fix(comma-family)"),
    Case("family_comma_title_then_suffix_keeps_the_split",
         "John Smith, Mr. Jr.",
         {"title": "Mr.", "given": "John", "family": "Smith",
          "suffix": "Jr."},
         classification="fix(#296)",
         notes="no name word after the comma, so it fixed no family "
               "boundary -- the same reasoning as 'John Smith, Mr.'; "
               "v1 read first 'Jr.', last 'John Smith', and 2.0 through "
               "master family 'John Smith' (the design-docs review "
               "found C1 silent on the shape)"),
    Case("family_comma_title_run_keeps_the_split", "John Smith, Mr. Dr.",
         {"title": "Mr. Dr.", "given": "John", "family": "Smith"},
         classification="fix(#296)"),
    Case("family_comma_title_run_one_word", "Smith, Mr. Dr.",
         {"title": "Mr. Dr.", "family": "Smith"},
         classification="fix(#296)",
         notes="one pre-comma piece, no split to keep; the run is "
               "titles (master read suffix 'Dr.')"),
    Case("family_comma_three_segments_credential_run", "Smith, Jr., PhD",
         {"family": "Smith", "suffix": "Jr., PhD"},
         classification="fix(#325)",
         notes="segments 2+ compose with the credential run"),
    Case("family_comma_suffixed_family_before_a_title", "Smith Jr., Dr.",
         {"title": "Dr.", "family": "Smith", "suffix": "Jr."},
         classification="fix(#296)",
         notes="two pre-comma pieces but ONE name piece: the positional "
               "read peels the suffix first and would have left a lone "
               "given and no family (the code review found 'Smith Jr., "
               "Mr.' reading so), so the guard counts name pieces and "
               "the family stays. v1 read first 'Smith', last 'Jr.', "
               "suffix 'Dr.'; 2.0 through master family 'Smith', "
               "suffix 'Jr.', title 'Mr.' for the Mr. spelling"),
    Case("family_comma_suffixed_family_before_a_title_mr", "Smith Jr., Mr.",
         {"title": "Mr.", "family": "Smith", "suffix": "Jr."},
         notes="unchanged at every baseline -- the shape the guard "
               "protects"),
    Case("family_comma_suffixed_two_word_family_before_a_title",
         "John Smith Jr., Mr.",
         {"title": "Mr.", "given": "John", "family": "Smith",
          "suffix": "Jr."},
         classification="fix(#296)",
         notes="two name pieces, so the split is kept"),
    # -- the positional read keeps its ORDER, so the family-first fold
    # (P1) reaches a particle-led pre-comma name as it does without
    # the comma (the test review found it reading family 'de')
    Case("family_comma_no_name_word_family_first", "de Mesnil Juan, Dr.",
         {"title": "Dr.", "given": "Juan", "family": "de Mesnil"},
         policy=Policy(name_order=FAMILY_FIRST),
         notes="as 'de Mesnil Juan' reads under the same order; master "
               "read it through the suffix-comma route ('dr' was "
               "suffix vocabulary) and got the fold that way"),
    Case("family_comma_no_name_word_family_first_given_last",
         "de la Cruz Juan Carlos, Dr.",
         {"title": "Dr.", "given": "Carlos", "middle": "Juan",
          "family": "de la Cruz"},
         policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST)),
    Case("family_comma_no_name_word_family_first_plain", "John Smith, Dr.",
         {"title": "Dr.", "given": "Smith", "family": "John"},
         policy=Policy(name_order=FAMILY_FIRST),
         notes="the declared order applies to the pre-comma name as it "
               "does to 'John Smith' alone -- deliberate"),
    Case("title_word_trailing_is_not_a_title", "John Smith Prof.",
         {"given": "John", "middle": "Smith", "family": "Prof."},
         notes="the pre-existing behavior the audit_dr_trailing and "
               "audit_sra_trailing rows join, pinned so the pair reads "
               "as consistency rather than as damage -- and so the "
               "general fix (#316) has a row to flip when it lands. "
               "Contrast 'Smith, Prof.', which the comma path DOES "
               "route to title: the two paths disagree today"),
    Case("ja_honorific_glued_family_comma_title_only", "田中さん, Dr.",
         {"title": "Dr.", "family": "田中さん"},
         classification="fix(#296)",
         notes="Accepted (C1): with 'dr' out of the suffix sets the "
               "comma is a family comma, and the honorific peel runs "
               "in script_segment on the other structures only, before "
               "group or assign can say this comma fixed nothing -- so "
               "the honorific stays glued, joining master's '田中さん, "
               "Mr.'. Master peeled it through the suffix-comma route"),
    Case("title_word_trailing_is_not_a_title_mr", "John Smith Mr.",
         {"given": "John", "middle": "Smith", "family": "Mr."}),

    # -- #271: script-scoped order + segmentation (amendment 2026-07-27)
    Case("ko_unspaced_default", "김민준",
         {"family": "김", "given": "민준"},
         classification="fix(#271)",
         notes="hangul is unambiguously Korean: census surnames ship "
               "as default vocabulary and HANGUL segmentation is "
               "default-on"),
    Case("ko_two_syllable_surname_default", "남궁민수",
         {"family": "남궁", "given": "민수"},
         classification="fix(#271)",
         ambiguities=("segmentation",),
         notes="남 is itself a shipped surname; longest-first takes "
               "남궁 and records the decided fork"),
    Case("ko_bare_two_syllable_surname", "남궁",
         {"family": "남궁"},
         classification="fix(#271)",
         notes="a token that IS a surname never splits by its "
               "shorter prefix (남+궁); whole token takes the script "
               "order's first role; nothing was split, so no fork is "
               "recorded"),
    Case("ko_family_comma_stays_whole", "남궁민수, 지훈",
         {"family": "남궁민수", "given": "지훈"},
         classification="fix(#271)",
         notes="the comma already decided the family: segmentation "
               "is inert under FAMILY_COMMA (comma doctrine -- see "
               "the script_segment stage docstring, which uses this "
               "exact example)"),
    Case("ko_suffix_comma_name_part_splits", "Dr 김민준, Jr.",
         {"title": "Dr", "family": "김", "given": "민준", "suffix": "Jr."},
         classification="fix(#271)",
         notes="the one comma structure where segmentation still "
               "fires: a second word before the comma makes it "
               "SUFFIX_COMMA, and the name part is a full positional "
               "name"),
    Case("ko_spaced_family_first_default", "김 민준",
         {"family": "김", "given": "민준"},
         classification="fix(#271)",
         notes="script_orders, no segmentation involved"),
    Case("han_spaced_family_first_default", "毛 泽东",
         {"family": "毛", "given": "泽东"},
         classification="fix(#271)",
         notes="Han ORDER is default-safe without knowing zh from ja "
               "(both write family-first natively); only "
               "SEGMENTATION needs the zh opt-in"),
    Case("han_unspaced_unsegmented_default", "毛泽东",
         {"family": "毛泽东"},
         classification="fix(#271)",
         notes="no default Han segmentation: one token, and a lone "
               "wholly-Han token takes the script order's first "
               "role = family"),
    Case("mixed_script_untouched_by_script_orders", "John 王",
         {"given": "John", "family": "王"},
         notes="effective_script is None for a mixed name: script_orders "
               "declines and the positional default governs"),
    Case("two_han_scripts_untouched_by_script_orders", "毛 김",
         {"given": "毛", "family": "김"},
         notes="two scripts also decline -- the rule is one script, or "
               "the Han/kana repertoire the #272 license covers"),

    Case("zh_unspaced", "毛泽东",
         {"family": "毛", "given": "泽东"},
         locale="zh", classification="fix(#271)"),
    Case("zh_unspaced_two_char", "张伟",
         {"family": "张", "given": "伟"},
         locale="zh", classification="fix(#271)"),
    Case("zh_compound_tie_break", "夏侯惇",
         {"family": "夏侯", "given": "惇"},
         locale="zh", classification="fix(#271)",
         ambiguities=("segmentation",),
         notes="夏 (rank 65) is itself listed, so longest-first "
               "decides a real fork here and records it; most "
               "compounds' first chars are NOT listed"),
    Case("zh_compound_two_char_given", "司马相如",
         {"family": "司马", "given": "相如"},
         locale="zh", classification="fix(#271)"),
    Case("zh_traditional_compound", "諸葛亮",
         {"family": "諸葛", "given": "亮"},
         locale="zh", classification="fix(#271)"),
    Case("zh_no_surname_match", "阿明",
         {"family": "阿明"},
         locale="zh", classification="fix(#271)",
         notes="no surname prefix in the vocabulary: the token stays "
               "whole and takes the script order's first role"),
    Case("zh_japanese_kanji_tradeoff", "高橋一郎",
         {"family": "高", "given": "橋一郎"},
         locale="zh", classification="fix(#271)",
         notes="the RECORDED tradeoff, not a bug: applying the zh "
               "pack declares the data Chinese, so Japanese kanji "
               "names mis-split (高橋 is the real surname). This is "
               "why Han segmentation is opt-in and why the gate "
               "cannot guard it (DEVIATES declares all Han); "
               "Japanese data belongs under locales.JA and its "
               "segmenter instead"),

    # -- #272: the kana license + nakaguro (amendment 2026-07-29).
    # Segmenter-dependent divisions cannot live here (Case has no
    # segmenter field); they are pinned in test_locales.py's
    # integration tests instead.
    Case("ja_kana_spaced_family_first", "高橋 みなみ",
         {"family": "高橋", "given": "みなみ"},
         classification="fix(#272)",
         notes="hiragana identifies Japanese as certainly as hangul "
               "identifies Korean; kana-licensed names read "
               "family-first by default"),
    Case("ja_kanji_katakana_pieces", "山田 エミ",
         {"family": "山田", "given": "エミ"},
         classification="fix(#272)",
         notes="a kanji piece + a katakana piece cannot be a foreign "
               "transcription (those are katakana-only): native, "
               "licensed"),
    Case("ja_unspaced_unsegmented_default", "高橋みなみ",
         {"family": "高橋みなみ"},
         classification="fix(#272)",
         notes="no segmenter by default: one token, family role via "
               "the kana license"),
    Case("ja_pure_katakana_positional", "マイケル ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         notes="parity row guarding the license's boundary: "
               "pure-katakana is predominantly transcribed foreign "
               "names in original order -- never licensed"),
    Case("ja_nakaguro_divides_the_transcription", "マイケル・ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         classification="fix(#272)",
         notes="the katakana middle dot is the transcription's own "
               "part divider: it separates like whitespace, the "
               "license declines each katakana token, and the "
               "positional default keeps the source-language order"),
    Case("ja_nakaguro_han_takes_the_han_order", "高橋・一郎",
         {"family": "高橋", "given": "一郎"},
         classification="fix(#272)",
         notes="the dot splits; both tokens are pure Han, so the HAN "
               "family-first entry fires -- the katakana row's sibling "
               "through the other outcome"),
    Case("ja_lone_hiragana_takes_family", "みなみ",
         {"family": "みなみ"},
         classification="fix(#272)",
         notes="hiragana earns a script_orders entry in its own right: "
               "a lone token takes the entry's first role"),
    Case("ja_lone_katakana_stays_given", "マイケル",
         {"given": "マイケル"},
         notes="parity: katakana deliberately has no entry, so the "
               "positional default holds -- transcribed foreign names "
               "keep source order"),
    Case("ja_iteration_mark_is_han", "佐々木 太郎",
         {"family": "佐々木", "given": "太郎"},
         classification="fix(#272)",
         notes="々 (U+3005, the ideographic iteration mark) repeats "
               "the preceding kanji and is Script=Han under UAX #24, "
               "but sits outside every CJK ideograph BLOCK -- and the "
               "classifier is a block table, so it needs its own "
               "entry to count as Han; without one 佐々木 -- a top-20 "
               "Japanese surname -- would be a mixed-script token and "
               "reverse"),
    Case("ja_shime_mark_is_han", "〆木 太郎",
         {"family": "〆木", "given": "太郎"},
         classification="fix(shime-mark)",
         notes="〆 (U+3006, the shime mark) opens real Japanese "
               "surnames -- 〆木 Shimeki, 〆谷 Shimetani, 〆野 -- but "
               "carries Script=Common under UAX #24; the table counts "
               "it as Han anyway (a deliberate step PAST the Script "
               "property, unlike 々's), else 〆木 is a mixed-script "
               "token and the name reverses"),
    Case("ja_shime_lone_token_takes_family", "〆木太郎",
         {"family": "〆木太郎"},
         classification="fix(shime-mark)",
         notes="wholly-Han lone token under the family-first entry: "
               "the whole token lands in family, unsegmented by "
               "default"),
    Case("ja_shime_with_kana_given", "〆木 ひろ",
         {"family": "〆木", "given": "ひろ"},
         classification="fix(shime-mark)",
         notes="the kana license composes with the widened Han span: "
               "〆木 reads as kanji beside a kana given name"),
    Case("ja_nakaguro_inside_a_nickname",
         "山田 太郎 (マイケル・ジャクソン)",
         {"family": "山田", "given": "太郎",
          "nickname": "マイケル ジャクソン"},
         classification="fix(#272)",
         notes="delimited content tokenizes under the same separator "
               "rules: the dot renders back as a space in the nickname "
               "join -- a decision, not an accident"),
    Case("zh_interpunct_transcription_source_order", "威廉·莎士比亚",
         {"given": "威廉", "family": "莎士比亚"},
         classification="fix(#298)",
         notes="间隔号-divided Han is a transcribed foreign name and "
               "keeps source order -- the B7 is the transcription "
               "marker, playing the role pure katakana plays in the "
               "kana license; it divides only between classified "
               "characters"),
    Case("zh_interpunct_nakaguro_typed_stays_roster", "威廉・莎士比亚",
         {"given": "莎士比亚", "family": "威廉"},
         classification="fix(#272)",
         notes="the SAME transcription typed with the Japanese "
               "nakaguro reads as the dot's own typography says -- a "
               "姓・名 roster pair, family-first (#272) -- because the "
               "nakaguro records nothing (per decisions.md#T3, "
               "codepoint-scoped; only the Chinese B7 marks a "
               "transcription). A limitation row: chosen, not "
               "accidental -- cross-convention input reads by the "
               "convention of the codepoint it was typed with"),
    Case("ja_interpunct_b7_katakana", "マイケル·ジャクソン",
         {"given": "マイケル", "family": "ジャクソン"},
         classification="fix(#298)",
         notes="sloppy-IME B7 between katakana divides like the "
               "nakaguro; katakana was never licensed, so order was "
               "already positional -- the split is the fix"),
    Case("latin_punt_volat_is_name_interior", "Gal·la Marcet",
         {"given": "Gal·la", "family": "Marcet"},
         notes="the Catalan punt volat: U+00B7 with Latin neighbors "
               "is interior to the name, never a divider -- the flank "
               "guard's whole reason"),
    Case("zh_interpunct_suppresses_segmentation", "马丁·路德·金",
         {"given": "马丁", "middle": "路德", "family": "金"},
         locale="zh",
         classification="fix(#298)",
         notes="马 is a listed zh surname, but a 间隔号-divided name "
               "is a transcription: the dot gates segmentation off, "
               "so 马丁 stays whole and the positional read stands"),
    Case("ko_interpunct_transcription_source_order", "마이클·잭슨",
         {"given": "마이클", "family": "잭슨"},
         classification="fix(#298)",
         notes="Korean writes transcribed foreign names with the "
               "interpunct too: the dot suppresses the hangul "
               "family-first entry AND the default segmentation -- 마 "
               "is a listed census surname, and the spaced form "
               "마이클 잭슨 really does mis-split 마|이클 today, so "
               "the dot is what rescues the ko transcription"),
    Case("zh_interpunct_with_suffix_comma", "威廉·莎士比亚, PhD",
         {"given": "威廉", "family": "莎士比亚", "suffix": "PhD"},
         classification="fix(#298)",
         notes="the transcription reading composes with a suffix "
               "comma: the marker is structure-independent"),
    Case("zh_interpunct_half_flanked_stays", "王·Smith",
         {"given": "王·Smith"},
         notes="one classified neighbor is not enough: the guard "
               "requires both, so the undivided dot remains part of "
               "the word -- declining, not deciding"),
    Case("zh_honorific_suffix_spaced", "王小明 先生",
         {"family": "王小明", "suffix": "先生"},
         classification="fix(#307) + fix(#271)",
         notes="CJK honorifics FOLLOW the name; a spaced 先生 (Mr.) is "
               "a suffix, and recognizing it must come before the "
               "family-first order hands it a role -- unrecognized it "
               "read as the GIVEN name under the 2.1 defaults"),
    Case("ko_honorific_ssi", "김민준 씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#307) + fix(#271)",
         notes="Korean orthography standardly SPACES 씨, so the "
               "whole-token suffix machinery reaches it; the name "
               "still segments (suffix classification runs after the "
               "script_segment stage, which only ever saw 김민준)"),
    Case("ko_degree_baksa", "김민준 박사",
         {"family": "김", "given": "민준", "suffix": "박사"},
         classification="fix(#307) + fix(#271)",
         notes="박사 (doctorate) is the ko analogue of a trailing "
               "PhD: fix(suffix-routing)'s two-token shape, one "
               "script over"),
    Case("ja_sama_spaced", "田中 太郎 様",
         {"family": "田中", "given": "太郎", "suffix": "様"},
         classification="fix(#307) + fix(#271)",
         notes="the spaced 様 of forms and databases, which whole-token "
               "matching reaches on its own; the glued "
               "mail-addressing form is ja_sama_glued below, reached "
               "by #308's peel instead"),
    Case("ja_san_spaced", "田中 さん",
         {"family": "田中", "suffix": "さん"},
         classification="fix(#308) + fix(#271)",
         notes="the kana honorifics ship as suffix vocabulary so the "
               "glued peel has somewhere to hand its tail; spaced "
               "recognition falls out of the same entry -- until this "
               "change さん read as the given name under the "
               "family-first default"),
    Case("ja_san_glued", "田中さん",
         {"family": "田中", "suffix": "さん"},
         classification="fix(#308) + fix(#271)",
         notes="the everyday glued form, and the one that also "
               "corrupted classification: 田中さん is Han plus "
               "hiragana, so the kana license read the whole string "
               "as a Japanese name. The peel runs before the license "
               "is consulted, so it now sees 田中 alone"),
    Case("ja_honorific_glued_before_a_roman_suffix", "田中さん II",
         {"family": "田中", "suffix": "さん, II"},
         classification="fix(#308) + fix(#271)",
         notes="an unrelated trailing suffix does not hide the peel "
               "site: the scan-back steps over II and peels さん off "
               "the token behind it. Half of the pair that pins "
               "_is_post_nominal's use of is_suffix_STRICT -- the "
               "other half is the row below, and swapping in "
               "is_suffix_lenient changes that one and not this one"),
    Case("ja_honorific_glued_before_an_initial", "田中さん V.",
         {"given": "田中さん", "family": "V."},
         notes="the strict/lenient discriminator, and the reason "
               "_is_post_nominal reads is_suffix_strict. Bare 'v' is "
               "a suffix word, but 'V.' is an initial and the strict "
               "test vetoes it -- so the scan-back stops HERE rather "
               "than stepping over it, finds no tail on 'V.', and "
               "does not peel. Under is_suffix_lenient it would step "
               "over and give given 田中, middle さん, family 'V.'. "
               "Parity besides: 1.4.0 read this first 田中さん / last "
               "'V.', which is these fields under the 2.0 names. "
               "Classification agrees with what classify does with "
               "the same token downstream -- 'V.' is a middle "
               "initial, not a post-nominal"),
    Case("ja_honorific_with_a_period_no_comma", "田中さん 様.",
         {"family": "田中", "suffix": "さん, 様."},
         classification="fix(#320)",
         notes="the SPACED form, and the example _vocab.is_initial's "
               "own docstring cites as what #320 cost. Same fields as "
               "the comma row below, reached without a comma: the peel "
               "scans segment 0 either way, and with '様.' no longer "
               "vetoed the scan-back steps over it onto 田中さん and "
               "peels さん. Worth its own row because it is the only "
               "one of the pair where the SCAN-BACK is what #320 "
               "fixes, and since #319 the only one where the PEEL "
               "depends on #320 at all: here '様.' shares the run with "
               "田中さん and has to be stepped over, while the comma "
               "form declines its post-comma run and never looks at "
               "'様.' in the peel. That decline does not carry the "
               "veto over -- is_wholly_suffix asks is_suffix_lenient "
               "under the default policy, which takes '様.' whether "
               "the veto is in place or not (see the row below) -- so "
               "restoring the veto strands さん HERE and nowhere else "
               "in the pair, giving given '田中さん', family '様.'. "
               "(Before #319 the distinction was structural -- "
               "FAMILY_COMMA flattened TWO runs before scanning where "
               "this has one -- which is no longer what separates "
               "them.) 1.4.0 read this first "
               "田中さん / last '様.', which is what 2.0 produced until "
               "#320: parity before, a classified change after"),
    Case("ja_honorific_period_does_not_stop_the_peel", "田中さん, 様.",
         {"family": "田中", "suffix": "さん, 様."},
         classification="fix(#320)",
         notes="the comma spelling of the row above, and since #319 a "
               "DIFFERENT dependence on #320. At #320 this row was "
               "about the peel: the veto made _is_suffix_strict say "
               "no of '様.', so the #312 scan-back stopped AT it as "
               "the site, found no listed tail there and abandoned, "
               "leaving さん glued to 田中 over one period. #319 then "
               "declined the post-comma run outright, and what is "
               "left here for #320 to fix is the ASSIGNMENT -- with "
               "the veto restored the peel still fires (family 田中, "
               "suffix さん) and only '様.' moves, to given. The "
               "fields and the classification are unchanged either "
               "way. CORRECTION, recorded here because commit "
               "4aff219's message claims otherwise and cannot be "
               "amended: the veto does NOT reach is_wholly_suffix "
               "under this row's DEFAULT policy, so it is not true "
               "that #319 merely handed the same veto to a different "
               "predicate. is_wholly_suffix selects is_suffix_lenient "
               "there, whose contract is suffix_words accepted "
               "unconditionally, BYPASSING the initial veto, and "
               "_normalize('様.') is '様', a suffix word -- so "
               "is_wholly_suffix(['様.']) is True veto or no veto, "
               "the run is declined either way, and simulating the "
               "veto PEELS さん here rather than stranding it. The "
               "is_wholly_suffix route to an abandoned peel exists "
               "only under Policy(lenient_comma_suffixes=False), "
               "which drops the call to is_suffix_strict and gives "
               "family '田中さん', given '様.'; this row does not set "
               "that knob, and "
               "ko_honorific_period_under_strict_comma_suffixes is "
               "the table's row for it. Was the "
               "shape of "
               "ja_honorific_glued_before_an_initial above, except "
               "that here the token stopping the scan is a real "
               "honorific rather than an initial, which is what makes "
               "it a bug rather than the intended veto. The structure "
               "is FAMILY_COMMA throughout -- SUFFIX_COMMA needs more "
               "than one word ahead of the comma and 田中さん is one -- "
               "so at #320 both runs were in the peel's reach and "
               "only the strict test's answer moved. "
               "1.4.0 read "
               "this first '様.' / last 田中さん, which is exactly what "
               "2.0 produced before this change -- the row sat at "
               "parity until #320 moved it"),
    Case("ja_sama_glued", "山田太郎様",
         {"family": "山田太郎", "suffix": "様"},
         classification="fix(#308) + fix(#271)",
         notes="the mail-addressing form. Undivided without a "
               "segmenter -- no surname list divides a kanji name -- "
               "so the family name is the whole 山田太郎; "
               "tests/v2/test_locales.py pins the divided twin under "
               "locales.JA"),
    Case("ko_honorific_nim_glued", "김민준님",
         {"family": "김", "given": "민준", "suffix": "님"},
         classification="fix(#308) + fix(#271)",
         notes="the online/formal glued address form, 씨's twin"),
    Case("ko_honorific_written_with_a_period", "김민준, 씨.",
         {"family": "김민준", "suffix": "씨."},
         classification="fix(#320)",
         notes="the period-written form of ko_honorific_after_comma "
               "('김민준, 씨'), whose field ASSIGNMENT it must match "
               "and before #320 did not -- same roles, the suffix "
               "VALUE differing by the period it was written with. "
               "_normalize strips the trailing period, "
               "so the vocabulary sees 씨 either way -- the initial "
               "veto was the only thing rejecting the written form, "
               "and literally the veto: is_suffix_piece is "
               "'vocab:suffix' in tags and 'initial' not in tags, and "
               "'씨.' carried both, so the suffix-shaped piece went to "
               "the given. 1.4.0 read this first '씨.' / last 김민준 -- "
               "the same fields 2.0 gave before this change, so the row "
               "was at parity and #320 is what moves it"),
    Case("ko_honorific_period_under_strict_comma_suffixes", "김민준, 씨.",
         {"family": "김민준", "suffix": "씨."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#320)",
         notes="the row above under the knob that governs exactly this "
               "shape, and one of the table's three exercises of it "
               "(ja_honorific_glued_family_comma_strict_knob is the "
               "second, on the initial-shaped side of the same gap; "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob is the third, showing where the knob changes "
               "nothing). "
               "lenient_comma_suffixes=False drops segment's post-comma "
               "test to the strict one, so a 'Family, Suffix' input "
               "whose suffix is INITIAL-SHAPED reads as a given-name "
               "initial instead ('John Smith, V' -> given 'V'). '씨.' "
               "is a single character plus a period, so it was in that "
               "class by shape, and before #320 the knob decided it: "
               "given '씨.' / family 김민준. It is out of the class now, "
               "and the honorific parses identically under both "
               "settings -- which is the claim this row exists to "
               "hold, since the knob's own documentation scopes it to "
               "the initial-shaped suffix words ('John Smith, V') and "
               "_script_segment names it as the setting that keeps a "
               "glued honorific inside the name in a neighbouring "
               "shape ('田中さん, V.' gives family '田中さん' under "
               "it). No v1 spelling exists for the knob "
               "(the facade runner skips this row), so the "
               "classification compares against 1.4.0's single "
               "reading, first '씨.' / last 김민준 -- the same fields "
               "2.0 gave under EITHER setting before this change"),
    Case("ko_honorific_with_a_period_no_comma", "김민준 씨.",
         {"given": "민준", "family": "김", "suffix": "씨."},
         classification="fix(#320)",
         notes="the period-written ko_honorific_ssi ('김민준 씨'), and "
               "#320 by a different route than the row above: the veto "
               "left '씨.' a NAME piece, and effective_script('씨.') is "
               "None because the trailing period defeats the "
               "wholly-one-script test, so script_orders declined for "
               "the whole name and the three pieces fell back to "
               "name_order -- given 김, middle 민준, family '씨.'. "
               "Hangul segmentation is NOT what moves: it divides "
               "김민준 identically either way, and only the order the "
               "pieces are read in changes. 1.4.0 read this first "
               "김민준 / last '씨.' -- undivided, no suffix. The only "
               "row of the three that already differed from 1.4.0 "
               "before this change, but it differed as given 김 / "
               "middle 민준 / family '씨.'; the fields above are #320's, "
               "not the segmenter's, so the row is classified to it -- "
               "as ko_honorific_ssi is classified to #307 without "
               "naming the same segmentation it also depends on"),
    Case("ko_honorific_glued_teacher", "김선생님",
         {"family": "김", "suffix": "선생님"},
         classification="fix(#307) + fix(#271)",
         notes="longest-first, end to end: 선생님 peels whole where "
               "님 alone would have left 김선생 to segment into a "
               "family 김 and a given 선생. Classified to #307 "
               "because the fields do not move in this change -- "
               "segmentation already delivered this shape (김 is a "
               "listed surname, so the split reached it); #308 "
               "changes which mechanism gets there first"),
    Case("latin_stem_glued_kana_honorific", "Andersonさん",
         {"given": "Anderson", "suffix": "さん"},
         classification="fix(#308)",
         notes="no script precondition on the remainder -- the tail "
               "is the license. Japanese text about a foreigner, and "
               "the Latin remainder keeps the positional default. "
               "Single-issue on purpose where the block around it is "
               "compound: measured, disabling script_orders and "
               "segment_scripts leaves this row unchanged, because a "
               "Latin remainder never reaches either"),
    Case("latin_stem_glued_hangul_honorific", "Anderson선생님",
         {"given": "Anderson", "suffix": "선생님"},
         classification="fix(#308)",
         notes="the hangul twin of latin_stem_glued_kana_honorific, "
               "and the one that shows why a post-nominal is not a "
               "surname site: 선 is a listed census surname, so the "
               "peeled 선생님 would otherwise be split into 선 + 생님 "
               "-- the stage dissecting the honorific it had just "
               "manufactured. Single-issue for the same reason as its "
               "kana twin: the remainder is Latin, so #271 never "
               "applies"),
    Case("ko_honorific_glued_doctor", "김민준박사님",
         {"family": "김", "given": "민준", "suffix": "박사님"},
         classification="fix(#308) + fix(#271)",
         notes="박사님 is one honorific, not 박사 plus 님, and ships "
               "as one entry: 선생님, 교수님 and 박사님 are the three "
               "standard -님 professional honorifics and the first two "
               "shipped without it, which stranded 박사 in the given "
               "name here and rendered the spaced 김민준 박사님 as two "
               "suffixes. This row USED to pin the one-peel rule "
               "(named ko_glued_stack_peels_once) on the reading that "
               "left 박사 behind; no shipped vocabulary now has that "
               "shape, so the pin lives at stage level with a "
               "synthetic lexicon -- test_script_segment.py's "
               "test_one_peel_never_a_stack"),
    Case("ko_honorific_glued_doctor_spaced", "김민준 박사님",
         {"family": "김", "given": "민준", "suffix": "박사님"},
         classification="fix(#308) + fix(#271)",
         notes="the spaced twin, and the second half of the same gap: "
               "without a 박사님 entry the peel cut this token too -- "
               "it is not a whole-token suffix word, so 박사 + 님 came "
               "back as two suffixes for one honorific"),
    Case("ko_glued_tail_alone_never_peels", "씨",
         {"family": "씨"},
         classification="fix(#271)",
         notes="a token that IS a tail is not a peel site at all -- "
               "every tail is a suffix word, so the site scan steps "
               "past it and finds nothing else. NOT the length cap, "
               "which is never reached here. Classified to #271 "
               "because that is what moves the lone token from first "
               "to family; the row exists for the guard"),
    Case("ko_honorific_token_alone_stays_whole", "선생님",
         {"family": "선생님"},
         classification="fix(#308) + fix(#271)",
         notes="a lone honorific is not a name to be taken apart: it "
               "is not a peel site (every tail is a suffix word) and "
               "not a surname site, though 선 is listed and the "
               "default segmentation split it 선 + 생님 before this "
               "change"),
    Case("ja_glued_tail_alone_never_peels", "さん",
         {"family": "さん"},
         classification="fix(#272)",
         notes="the kana twin of ko_glued_tail_alone_never_peels, and "
               "of that row only: a lone さん carries none of "
               "ko_honorific_token_alone_stays_whole's risk, since no "
               "surname vocabulary is written in kana. The field "
               "placement is the kana-licensed order default, not the "
               "peel"),
    Case("ja_glued_degree_stays", "田中博士",
         {"family": "田中博士"},
         classification="fix(#271)",
         notes="the exclusion pinned: glued 田中博士 IS Tanaka "
               "Hiroshi, an attested given name, so 博士 never peels "
               "-- it stays recognized in the SPACED position only, "
               "where the writer's own token boundary settles it"),
    Case("zh_glued_jun_stays", "王君",
         {"family": "王君"},
         classification="fix(#271)",
         notes="likewise unpeeled: 君 is a common Chinese given-name "
               "final, so 王君 is a complete name, not Mr. Wang. "
               "Unlike its neighbours here, 君 is in NEITHER set -- "
               "there is no spaced entry to fall back on either, and "
               "only its kana spelling くん peels"),
    Case("zh_glued_shi_stays", "王氏",
         {"family": "王氏"},
         classification="fix(#271)",
         notes="likewise: 王氏 is a historical name form ('the Wang "
               "woman'). The spaced 田中氏 keeps its entry"),
    Case("ja_glued_dono_stays", "鵜殿",
         {"family": "鵜殿"},
         classification="fix(#271)",
         notes="the exclusion with the longest argument behind it and, "
               "until this row, the only one nothing held: adding 殿 "
               "back to GLUED_HONORIFICS passed the whole suite. 鵜殿 "
               "(Udono) is a real surname, one of roughly ninety "
               "Japanese surnames ending in 殿 (真殿, 大殿, ...), and a "
               "peeled 殿 would give family 鵜 with 殿 in suffix. It "
               "has to be the BARE surname: in a two-token 真殿 太郎 "
               "the site scan lands on 太郎 and the exclusion is never "
               "consulted, so only a lone surname discriminates. "
               "Classified to #271 like its neighbours, not parity: "
               "1.4 gave first 鵜殿 and no last, and it is the CJK "
               "order flip that makes the one token a family name"),
    Case("ja_dono_spaced", "田中 殿",
         {"family": "田中", "suffix": "殿"},
         classification="fix(#308) + fix(#271)",
         notes="殿 waited on an argument in #307 and gets one here: "
               "spaced it is safe for the reason 양/군 are -- a "
               "殿-surnamed person's name LEADS, and the suffix gate "
               "is trailing-only -- while glued it would cut 鵜殿 and "
               "真殿 in two, so it ships spaced only"),
    Case("ko_honorific_nim_spaced", "김민준 님",
         {"family": "김", "given": "민준", "suffix": "님"},
         classification="fix(#308) + fix(#271)",
         notes="님 is new in both sets -- #307 shipped only the -님 "
               "compounds 선생님/교수님. Standardly glued in online "
               "address, spaced too, and never the end of a Korean "
               "given name, which is what qualifies it for the "
               "harsher glued vetting as well"),
    Case("ko_honorific_glued_via_segmentation", "김씨",
         {"family": "김", "suffix": "씨"},
         classification="fix(#307) + fix(#271)",
         notes="the one glued shape that was already reachable before "
               "#308, which is why this row stays fix(#307) where its "
               "neighbours are fix(#308): stage order alone delivered "
               "it, since segmentation split 김 off the front and the "
               "honorific was whatever remained. The peel now takes 씨 "
               "off the END before segmentation is consulted, so the "
               "route changed and these fields did not. The glued "
               "shapes that needed the peel to be reached at all are "
               "the rows around it (김민준씨 below)"),
    Case("ko_honorific_after_comma", "김민준, 씨",
         {"family": "김민준", "suffix": "씨"},
         classification="fix(#307)",
         notes="the post-comma run is normally the given name -- "
               "'김민준, 태호' gives given 태호 -- and group's "
               "is_suffix_piece diverts this one because 씨 is a "
               "single-token piece carrying vocab:suffix. NOT the "
               "lenient comma gate, which an earlier note named: "
               "measured, lenient_comma_suffixes=False leaves this "
               "row unchanged. The comma disables segmentation per "
               "the comma doctrine, so 김민준 stays whole -- which is "
               "also why this row stays single-issue while the rest of "
               "the block is compound with fix(#271): measured, the "
               "order table and the segmenter both leave it alone, "
               "because the comma already decided the family"),
    Case("ko_honorific_glued_given", "김민준씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#308) + fix(#271)",
         notes="the common full-name glued shape, and the row this "
               "replaces (ko_honorific_glued_given_stays) pinned the "
               "old boundary: 씨 peels off the last token first, and "
               "the remainder 김민준 then segments as usual -- peel "
               "and split compose, in that order"),
    Case("ko_honorific_glued_given_trailing_suffix", "김민준씨 Jr.",
         {"family": "김", "given": "민준", "suffix": "씨, Jr."},
         classification="fix(#308) + fix(#271)",
         notes="the peel site is the last token that is not itself a "
               "post-nominal, so an unrelated trailing suffix cannot "
               "hide it -- this now agrees with the comma-written "
               "'Dr 김민준씨, Jr.', where the suffix comma had "
               "already put 씨 within reach"),
    Case("ko_honorific_glued_given_suffix_comma", "Dr 김민준씨, Jr.",
         {"title": "Dr", "family": "김", "given": "민준",
          "suffix": "씨, Jr."},
         classification="fix(#308) + fix(#271)",
         notes="the peel scans the NAME's runs, not the token stream: "
               "under a suffix comma that is segments[0] alone, a "
               "strict subset, and the peel site is found within it "
               "(a FAMILY comma is the one structure that splits the "
               "name across two runs, #312). Pairs with "
               "ko_honorific_glued_given_trailing_suffix, whose "
               "comma-less spelling of the same name reaches the same "
               "answer by the scan-back instead"),
    Case("ko_honorific_glued_given_nickname", "김민준씨 (Jimmy)",
         {"family": "김", "given": "민준", "suffix": "씨",
          "nickname": "Jimmy"},
         classification="fix(#308) + fix(#271)",
         notes="the other half of scanning the NAME's runs: extracted "
               "content is still in the token stream at this stage but "
               "in NO segment, so the scan-back never reaches "
               "Jimmy. Scanning the tokens instead would take Jimmy as "
               "the site -- it is no post-nominal -- and lose the peel "
               "entirely, with 씨 back in the given name. Nothing else "
               "pins that choice: under NO_COMMA the two are otherwise "
               "the same run"),
    Case("ko_honorific_glued_given_nickname_family_comma",
         "김, 민준씨 (Jimmy)",
         {"family": "김", "given": "민준", "suffix": "씨",
          "nickname": "Jimmy"},
         classification="fix(#312)",
         notes="the family-comma half of the same argument, which the "
               "row above cannot make: there the two runs are one, so "
               "'flatten the name's segments' and 'take segments[0]' "
               "agree. Here the peel has to cross the comma AND still "
               "not reach Jimmy, so declining to cross whenever "
               "extract_delimited claimed something passes the row "
               "above and fails only here"),
    Case("ja_honorific_glued_family_comma", "田中さん, PhD",
         {"family": "田中", "suffix": "さん, PhD"},
         classification="fix(#312)",
         notes="the peel reaches 田中さん across the comma, though no "
               "longer by crossing it: since #319 is_wholly_suffix "
               "declines the post-comma run outright (PhD is suffix "
               "vocabulary and it is the whole run), so the scan never "
               "meets the comma. PhD reads as the postnominal it is "
               "since #296's audit took 'phd' out of TITLES -- this row "
               "carried title 'PhD' until then, which was the title "
               "peel claiming a credential because v1's lists put it "
               "where v1's parser needed it"),
    Case("ja_honorific_glued_family_comma_suffixy_second_run",
         "田中さん, V.",
         {"given": "V.", "family": "田中", "suffix": "さん"},
         classification="fix(#319)",
         notes="under a family comma the peel scanned both runs on "
               "the premise that segments[1] is name text, and here it "
               "is not: segment picks FAMILY_COMMA when the pre-comma "
               "part is a single word, even where the post-comma part "
               "is entirely suffix-shaped, so the scan reached 'V.' -- "
               "which is_suffix_strict rejects as an initial where "
               "segment admitted the run on is_suffix_lenient. 'V.' "
               "was therefore the site, ended in no tail, and the peel "
               "was abandoned with さん still in the family name. #319 "
               "asks segment's own predicate (_vocab.is_wholly_suffix) "
               "instead of inferring name text from the structure: the "
               "run is declined, the scan stays inside segments[0], "
               "and さん peels off 田中さん as it always did without a "
               "second run. Same credential, three spellings, ONE "
               "answer FROM THE PEEL now -- this, '田中さん, PhD' "
               "above and '田中さん, Ph. D.' in "
               "ja_honorific_glued_family_comma_credential_pair below "
               "all reach 田中さん. Where the credential itself LANDS "
               "still differs by spelling (title 'PhD', given 'V.', "
               "suffix 'さん, Ph. D.'); that is assign's question, not the "
               "peel's, and this row is not a claim about it. Nor does "
               "the comma form now agree with its SPACED twin: "
               "ja_honorific_glued_before_an_initial ('田中さん V.') "
               "still does not peel, because under NO_COMMA there is "
               "one run and 'V.' is inside the name's own tokens where "
               "the scan-back legitimately stops -- declining a "
               "post-comma run does not reach it. Parity with 1.4.0 "
               "(first V., last 田中さん) until this change, which is "
               "what moves it; the 1.4.0 fields are still reachable "
               "through Policy(lenient_comma_suffixes=False), pinned "
               "by ja_honorific_glued_family_comma_strict_knob below"),
    Case("ja_honorific_glued_family_comma_credential_pair",
         "田中さん, Ph. D.",
         {"family": "田中", "suffix": "さん, Ph. D."},
         classification="fix(#319)",
         notes="the third of the three spellings #319 named, and the "
               "only one the Ph./D. merge reaches: is_wholly_suffix "
               "folds the adjacent pair into the single unit 'phd' "
               "(v1's fix_phd extracted the credential pre-parse), so "
               "the run counts as wholly suffix, the peel declines it, "
               "and さん comes off 田中さん exactly as in "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "above. The merge is also why this spelling is NOT the "
               "one to reach for when exercising "
               "Policy(lenient_comma_suffixes=False): 'phd' satisfies "
               "is_suffix_strict as readily as is_suffix_lenient, so "
               "the run is declined under EITHER setting and this row "
               "is identical under the knob, which "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob below holds rather than leaving to the claim -- "
               "ja_honorific_glued_family_comma_strict_knob below uses "
               "'V.' because the initial-shaped words are where the "
               "two predicates actually part. Where the credential "
               "lands is a separate question and answers differently "
               "again: suffix here, title for 'PhD', given for 'V.' "
               "Measured: 1.4.0 gave first 田中さん / suffix 'Ph. D.' "
               "(fix_phd lifted the credential pre-parse, leaving a "
               "lone pre-comma word), so like "
               "ja_honorific_glued_family_comma above the expectation "
               "carries TWO deviations -- the peel is #319's, first -> "
               "family is comma-family's, which 2.0 already had before "
               "this change (family 田中さん / suffix 'Ph. D.')"),
    Case("ja_honorific_glued_family_comma_strict_knob", "田中さん, V.",
         {"family": "田中さん", "given": "V."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="parity",
         notes="the same input as "
               "ja_honorific_glued_family_comma_suffixy_second_run "
               "above under the knob that keeps the pre-#319 answer, "
               "and one of the table's three exercises of it "
               "(ko_honorific_period_under_strict_comma_suffixes and "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob are the others). The knob drops is_wholly_suffix "
               "to the "
               "strict predicate, which rejects 'V.' as an initial, so "
               "the post-comma run reads as name text after all, the "
               "scan crosses into it, 'V.' is the site, it ends in no "
               "listed tail and the peel is abandoned -- さん stays in "
               "the family name. Not a blanket freeze of pre-#319 "
               "behavior, and the row must not be read as one: it "
               "holds for the INITIAL-shaped suffix words ('V.', 'V', "
               "'I'), which is the whole of where the strict/lenient "
               "gap lives. The counterexample is the row above, "
               "ja_honorific_glued_family_comma_credential_pair: its "
               "Ph./D. pair merges to a form strict accepts too, so "
               "that run is "
               "declined and the peel fires under this setting as "
               "well -- pinned, not merely stated, by "
               "ja_honorific_glued_family_comma_credential_pair_strict_"
               "knob above. No v1 spelling exists for the knob, so the "
               "facade runner skips this row and the classification "
               "compares against 1.4.0's single reading of the same "
               "text, as the other exercise of the knob named above "
               "does: measured, 1.4.0 gave first 'V.' / last "
               "田中さん, which is field for field what the knob holds "
               "here -- parity, and the point of the knob"),
    Case("ja_honorific_glued_family_comma_credential_pair_strict_knob",
         "田中さん, Ph. D.",
         {"family": "田中", "suffix": "さん, Ph. D."},
         policy=Policy(lenient_comma_suffixes=False),
         classification="fix(#319)",
         notes="the counterexample the two rows above assert and "
               "neither measured: the knob does NOT freeze the "
               "pre-#319 reading in general, only for the "
               "initial-shaped suffix words. Here the Ph./D. merge "
               "folds the run into 'phd', which is_suffix_strict "
               "accepts as readily as is_suffix_lenient, so the run is "
               "declined and さん peels under this setting exactly as "
               "under the default -- field for field the same "
               "expectation as "
               "ja_honorific_glued_family_comma_credential_pair, which "
               "is the whole claim. Cheap to hold and worth holding "
               "separately, because the two rows differ only in the "
               "policy and a knob that started gating the decline "
               "wholesale would move this one alone. Same "
               "classification and the same two deviations as its "
               "default-policy twin (1.4.0: first 田中さん / suffix "
               "'Ph. D.'), which is also why the knob cannot be judged "
               "against a v1 spelling here -- there is none, so the "
               "facade runner skips this row as it does the other two "
               "knob rows"),
    Case("ko_honorific_glued_family_comma_suffixy_second_run",
         "김민준씨, V.",
         {"given": "V.", "family": "김민준", "suffix": "씨"},
         classification="fix(#319)",
         notes="ja_honorific_glued_family_comma_suffixy_second_run in "
               "hangul, and pinned because the decline reads no script "
               "at all: it asks is_wholly_suffix about the post-comma "
               "run and the peel's own scan-back about segments[0], "
               "both vocabulary questions, so a script-conditional "
               "regression would be invisible in a table whose every "
               "other witness to #319 is written in kana. The family "
               "stays 김민준 undivided -- the FAMILY comma gates the "
               "surname split off, so hangul segmentation never runs "
               "here and only the peel acts. 1.4.0 gave first 'V.' / "
               "last 김민준씨, peeling nothing"),
    Case("zh_honorific_glued_family_comma_suffixy_second_run",
         "王先生, V.",
         {"given": "V.", "family": "王", "suffix": "先生"},
         classification="fix(#319)",
         notes="the Han spelling of the row above, and the third "
               "script. 先生 is a shipped tail, so the peel fires with "
               "no locale opted in -- honorific_tails is licensed by "
               "the entries themselves rather than by "
               "Policy.segment_scripts, and HAN is not activated here "
               "(the family is what the peel left behind, not a "
               "vocabulary split). 1.4.0 gave first 'V.' / last "
               "王先生"),
    Case("ko_honorific_glued_family_comma_site_only_beyond_the_comma",
         "이, J.씨",
         {"given": "J.", "family": "이", "suffix": "씨"},
         classification="fix(#312)",
         notes="the limit of #319's decline, and the row that says why "
               "it carries a second condition. is_wholly_suffix reaches "
               "period_joined_vocab, which calls an interior-period "
               "token a suffix when ANY chunk is suffix vocabulary -- "
               "and every honorific tail is a suffix WORD by the "
               "Lexicon invariant, so 'J.씨' reads as suffix-shaped "
               "BECAUSE of the 씨 the peel exists to remove. Declining "
               "on that evidence does not move the peel elsewhere the "
               "way 田中さん, V. does: segments[0] is the lone 이, which "
               "ends in no tail, so the scan finds no site at all, "
               "nothing peels, and the given name goes to suffix "
               "glued to its honorific ('J.씨'). So the gate declines "
               "only where segments[0] holds a peel site of its own, "
               "and this input reaches the pre-#319 fields by having "
               "none. Not rescued by "
               "Policy(lenient_comma_suffixes=False) either, unlike the "
               "strict-knob row above: the knob picks between "
               "is_suffix_lenient and is_suffix_strict per token and "
               "period_joined_vocab is downstream of neither, so both "
               "settings call this run wholly suffix. 1.4.0 gave first "
               "'J.씨' / last 이 -- it peels nothing, so the deviation "
               "here is #312's crossing, which is what puts the site on "
               "'J.씨' in the first place"),
    Case("ko_honorific_glued_family_comma_site_in_both_runs",
         "김민준씨, J.씨",
         {"family": "김민준", "suffix": "씨, J.씨"},
         classification="fix(#319)",
         notes="the two-honorific input, where both runs hold a site "
               "and the decline therefore stands -- a deliberate choice "
               "between two readings rather than a fallout. Pre-#319 "
               "the scan crossed and took the LAST site, peeling the 씨 "
               "off the junk 'J.씨' and leaving the person's own "
               "honorific glued in the family name (given 'J.', family "
               "김민준씨, suffix 씨); now 씨 comes off 김민준씨 and "
               "'J.씨' is consumed whole as a suffix. It is also the "
               "row that rules out the narrower gate: declining only "
               "where the SECOND run has no peel site fixes "
               "ko_honorific_glued_family_comma_site_only_beyond_the_"
               "comma above and reverts this input to the pre-#319 "
               "reading, which is the worse of the two -- the same "
               "junk-tail reach "
               "ko_honorific_glued_given_suffix_comma_initial's note "
               "names under a suffix comma. 1.4.0 gave first 'J.씨' / "
               "last 김민준씨, peeling neither"),
    Case("ko_honorific_glued_family_comma_lone_post_nominal_before_it",
         "선생님, J.씨",
         {"given": "J.", "family": "선생님", "suffix": "씨"},
         classification="fix(#312)",
         notes="segments[0] is a single token that IS a listed tail "
               "entire, which the site scan skips as a post-nominal "
               "(the same guard that keeps 선생님 from being peeled to "
               "선생 + 님) -- so there is no site before the comma, the "
               "run beyond it is scanned after all, and the fields are "
               "the pre-#319 ones as in the 이 row above. Pinned "
               "because it separates asking for the site with the "
               "peel's own scan-back from asking the cheaper question, "
               "whether any token ENDS in a tail: the cheaper one "
               "counts 선생님, declines, and then finds nothing to cut "
               "-- 씨 lost into suffix 'J.씨'. Only the lone-token "
               "shape of that divergence is reachable from the gate, "
               "which is why this row is one token before the comma; "
               "_peel_site's docstring derives the bound. "
               "1.4.0 gave first 'J.씨' / last 선생님"),
    Case("ko_honorific_glued_given_after_family_comma", "김, 민준씨",
         {"family": "김", "given": "민준", "suffix": "씨"},
         classification="fix(#312)",
         notes="under a family comma the name spans both segments and "
               "the honorific is on the GIVEN side, where the peel "
               "never looked before #312. Agrees with the spaced "
               "김 민준씨"),
    Case("ja_honorific_glued_given_after_family_comma", "田中, 太郎さん",
         {"family": "田中", "given": "太郎", "suffix": "さん"},
         classification="fix(#312)",
         notes="the Han twin of the row above"),
    Case("zh_interpunct_transcription_glued_honorific", "威廉·莎士比亚さん",
         {"given": "威廉", "family": "莎士比亚", "suffix": "さん"},
         classification="fix(#312)",
         notes="the dot still gates the surname split -- a "
               "transcription's pieces are syllable groups -- but an "
               "honorific glued to a transcribed name is still an "
               "honorific, so the peel crosses it. Agrees with the "
               "spaced 威廉·莎士比亚 さん"),
    Case("ja_honorific_glued_family_comma_no_site", "田中さん, 太郎",
         {"family": "田中さん", "given": "太郎"},
         notes="unchanged, and pinned because a naive fix breaks it: "
               "the site is the last NON-POST-NOMINAL token, which is "
               "太郎, so nothing peels -- exactly as in the spaced "
               "田中さん 太郎. #312 was originally filed naming this "
               "pair as a disagreement; it never was one"),
    Case("ko_honorific_glued_given_suffix_comma_initial", "Dr 김민준씨, V.",
         {"title": "Dr", "family": "김", "given": "민준",
          "suffix": "씨, V."},
         classification="fix(#308) + fix(#271)",
         notes="fix(#308) rather than fix(#312) because the fields do "
               "not move in this change -- a SUFFIX comma keeps the "
               "whole name in segments[0], which is what the peel "
               "already scanned. The row is here as the end-to-end "
               "guard for the scoping #312 introduced: widen the scan "
               "to every segment and 'V.' becomes the site, since "
               "segment admits a post-comma run on is_suffix_lenient "
               "while the site scan asks is_suffix_strict and an "
               "initial fails it. 'V.' then ends in no tail, the peel "
               "is abandoned, and 씨 is back in the given name -- the "
               "original bug. It was the table's only witness to that "
               "widening until #319; ja_honorific_glued_family_comma_"
               "suffixy_second_run and "
               "ja_honorific_glued_family_comma_credential_pair notice "
               "it as well now, but from the FAMILY_COMMA side, where "
               "the guard is is_wholly_suffix rather than this "
               "structural scoping. Their strict-knob sibling does NOT "
               "join them: under the knob is_wholly_suffix is False on "
               "the same run, so the scan was already crossing into "
               "segments[1] and widening past it changes nothing. This "
               "row is still the only SUFFIX comma among the three. "
               "Its comma-less twin ja_honorific_glued_before_an_initial "
               "shows the same veto from the other side, where 'V.' is "
               "in the name's own run and so IS the site"),
    Case("zh_honorific_glued_surname", "王先生",
         {"family": "王", "suffix": "先生"},
         locale="zh",
         classification="fix(#307) + fix(#271)",
         notes="the Han twin of 김씨: the zh pack's segmentation "
               "splits off the surname and the remaining 先生 is the "
               "honorific token"),
    Case("zh_honorific_glued_given", "王小明先生",
         {"family": "王", "given": "小明", "suffix": "先生"},
         locale="zh",
         classification="fix(#308) + fix(#271)",
         notes="the Han twin, replacing zh_honorific_glued_given_stays: "
               "先生 peels, and the zh pack's surname vocabulary then "
               "divides the remainder 王小明"),
    Case("zh_honorific_glued_given_default", "王小明先生",
         {"family": "王小明", "suffix": "先生"},
         classification="fix(#308) + fix(#271)",
         notes="the same input WITHOUT the pack: the peel is default-on "
               "and script-independent, so the honorific still routes "
               "to suffix -- only the surname split needs the opt-in, "
               "so the undivided 王小明 stays one family name"),
    Case("ko_suffix_matching_is_whole_token", "김지양",
         {"family": "김", "given": "지양"},
         classification="fix(#271)",
         notes="지양 ENDS with the honorific 양 but is a given name: "
               "suffix matching is whole-token, never endswith -- the "
               "pin the differential rule's anchor mirrors at the "
               "name-string level. #308 leaves it alone too: 양 is "
               "excluded from the glued tail set for exactly this "
               "name. Classified to #271, not parity: 1.4 gave first "
               "김지양 and no last, and it is #271's hangul "
               "segmentation plus the CJK order flip that produces "
               "these two fields"),
    Case("ko_surname_yang_leads", "양 미선",
         {"family": "양", "given": "미선"},
         classification="fix(#271)",
         notes="양 is both a top-tier surname (Yang) and a shipped "
               "honorific: position decides, and a surname LEADS -- "
               "the trailing-only suffix gate never sees it here. "
               "Classified to #271, not parity: 1.4 gave first 양, "
               "last 미선, and it is the CJK order flip that swaps "
               "them"),
    Case("ko_honorific_yang_trails", "김민준 양",
         {"family": "김", "given": "민준", "suffix": "양"},
         classification="fix(#307) + fix(#271)",
         notes="the other side of ko_surname_yang_leads: the same "
               "token trailing a name is 'Miss', and that is the whole "
               "argument shipping it -- suffixes.py singles 양 out "
               "(with 군) as the risk class it takes, a top-tier "
               "surname admitted to the vocabulary on the strength of "
               "position alone. Nothing pinned the trailing reading "
               "before this row, so the leading rows carried the pair "
               "by themselves. Classified to #307 like ko_honorific_ssi "
               "(1.4 gave first 김민준, last 양; the recognition and "
               "the order flip both move it) -- the point of the row "
               "is the twin below"),
    Case("ko_honorific_yang_written_with_a_period", "김민준 양.",
         {"family": "김", "given": "민준", "suffix": "양."},
         classification="fix(#320)",
         notes="the period-written twin, whose fields must equal the "
               "row above and before #320 did not (given 김, middle "
               "민준, family '양.' -- the veto kept '양.' a name piece, "
               "exactly ko_honorific_with_a_period_no_comma's route). "
               "The pair is the point: 양 is the shipped vocabulary's "
               "acknowledged risk, so if the 양/군 policy is ever "
               "tightened or withdrawn, both spellings have to move "
               "together and neither row can be adjusted alone. 군 "
               "gets no pair of its own -- it parses identically and "
               "is the SAFER half (no surname reading), so it would "
               "pin nothing these two do not. Classified to #320 like "
               "its 씨 counterpart: 1.4.0 read this first 김민준 / last "
               "'양.', and the fields above are the ones this change "
               "produced, not the segmenter's"),
    Case("ko_surname_yang_leads_a_segmentable_given", "양 지훈",
         {"family": "양", "given": "지훈"},
         classification="fix(#271)",
         notes="양 is a surname AND a shipped honorific, and 지 is a "
               "listed surname too -- so this is the name that "
               "catches a segmentation site scanning PAST the "
               "honorific reading of 양 into the given name. The "
               "first script-written token decides, and deciding "
               "includes deciding there is no surname site. "
               "Classified to #271, not parity: 1.4 gave first 양, "
               "last 지훈, and it is the CJK order flip that puts 양 "
               "in family -- nothing in #308 moves these fields"),
    Case("ko_honorific_stack", "김민준 박사 씨",
         {"family": "김", "given": "민준", "suffix": "박사, 씨"},
         classification="fix(#307) + fix(#271)",
         notes="a trailing RUN of honorifics peels whole, like "
               "'Smith PhD MD' -- the multi-suffix loop the peel "
               "shares with Latin suffixes"),
)
