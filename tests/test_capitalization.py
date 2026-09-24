# pickle here round-trips an object this test just built; the library's
# own pickle support is what is under test, and no foreign data is read.
import pickle

import pytest

from nameparser import HumanName
from nameparser.config import Constants

from tests.base import HumanNameTestBase


class HumanNameCapitalizationTestCase(HumanNameTestBase):
    def test_capitalization_exception_for_III(self) -> None:
        hn = HumanName('juan q. xavier velasquez y garcia iii')
        hn.capitalize()
        self.m(str(hn), 'Juan Q. Xavier Velasquez y Garcia III', hn)

    # A known failure since 2012 (the Google Code tracker's issue 22)
    # until #492: the one-case gate read the SUFFIX as evidence that
    # the writer cased the whole name, so 'III' held the lowercase
    # name back. The gate now leaves the suffixes out (rules.md#R5):
    # a generation written the way one is written says nothing about
    # how the name was cased. The name words still count, and so
    # does a title -- the two boundary rows.
    def test_capitalization_exception_for_already_capitalized_III(
        self,
    ) -> None:
        hn = HumanName('juan garcia III')
        hn.capitalize()
        self.m(str(hn), 'Juan Garcia III', hn)
        mixed = HumanName('Juan garcia III')
        mixed.capitalize()
        self.m(str(mixed), 'Juan garcia III', mixed)
        titled = HumanName('Dr. juan garcia')
        titled.capitalize()
        self.m(str(titled), 'Dr. juan garcia', titled)

    def test_capitalize_title(self) -> None:
        hn = HumanName('lt. gen. john a. kenneth doe iv')
        hn.capitalize()
        self.m(str(hn), 'Lt. Gen. John A. Kenneth Doe IV', hn)

    def test_capitalize_title_to_lower(self) -> None:
        hn = HumanName('LT. GEN. JOHN A. KENNETH DOE IV')
        hn.capitalize()
        self.m(str(hn), 'Lt. Gen. John A. Kenneth Doe IV', hn)

    # Capitalization with M(a)c and hyphenated names
    def test_capitalization_with_Mac_as_hyphenated_names(self) -> None:
        hn = HumanName('donovan mcnabb-smith')
        hn.capitalize()
        self.m(str(hn), 'Donovan McNabb-Smith', hn)

    def test_capitization_middle_initial_is_also_a_conjunction(self) -> None:
        hn = HumanName('scott e. werner')
        hn.capitalize()
        self.m(str(hn), 'Scott E. Werner', hn)

    def test_capitalize_empty_middle_produces_no_leading_space_in_surnames(self) -> None:
        # str.split(' ') on an empty string returns [''] rather than [], so an
        # absent middle produced a spurious token that leaked into surnames_list
        # and caused a leading space in the surnames property (' Doe' not 'Doe').
        hn = HumanName('john doe')
        hn.capitalize()
        self.m(hn.surnames, 'Doe', hn)
        self.assertEqual(hn.middle_list, [])
        self.assertEqual(hn.surnames_list, ['Doe'])

    def test_capitalize_force_empty_middle_produces_no_leading_space_in_surnames(self) -> None:
        # Without force=True, capitalize() exits early for mixed-case names and
        # never reaches the split lines. Confirm the fix covers that path too.
        hn = HumanName('Jane Doe')
        hn.capitalize(force=True)
        self.m(hn.surnames, 'Doe', hn)
        self.assertEqual(hn.middle_list, [])

    def test_capitalize_empty_attributes_produce_no_spurious_tokens(self) -> None:
        # Confirm the fix extends beyond surnames: empty attribute lists are []
        # not [''], and non-empty ones contain only real tokens.
        hn = HumanName('Jane Doe')
        hn.capitalize(force=True)
        self.assertEqual(hn.title_list, [])
        self.assertEqual(hn.first_list, ['Jane'])
        self.assertEqual(hn.last_list, ['Doe'])

    def test_capitalize_title_and_last_only_no_spurious_tokens(self) -> None:
        # title+last with no first or middle leaves first_list and middle_list
        # both empty. All-caps triggers capitalize() without force=True.
        hn = HumanName('DR DOE')
        hn.capitalize()
        self.assertEqual(hn.first_list, [])
        self.assertEqual(hn.middle_list, [])
        self.m(str(hn), 'Dr Doe', hn)

    def test_capitalize_empty_suffix_produces_no_spurious_tokens(self) -> None:
        # ''.split(', ') returns [''] just like ''.split(' ') did for the other
        # attributes — an absent suffix should produce suffix_list == [], not [''].
        hn = HumanName('JOHN DOE')
        hn.capitalize()
        self.assertEqual(hn.suffix_list, [])

    def test_capitalize_single_suffix_still_works(self) -> None:
        hn = HumanName('JOHN DOE PHD')
        hn.capitalize()
        self.assertEqual(hn.suffix_list, ['PhD'])

    def test_capitalize_multiple_suffixes_still_split_correctly(self) -> None:
        hn = HumanName('JOHN DOE PHD MD')
        hn.capitalize()
        # The split this guards is capitalize() giving each word its own
        # repair rather than title-casing the run, and that is
        # untouched: PHD by the exceptions map's mask, MD by the acronym
        # clause since #459 took md out of the map. The two words are
        # ONE entry since #436 -- the writer spaced them, so they render
        # with a space -- and one entry is one suffix_list element. A
        # deliberate deviation from 1.4.0, which inserted a comma into a
        # run the writer had spaced, and gave 'Ph.D.', 'M.D.' besides.
        self.assertEqual(hn.suffix_list, ['PhD MD'])

    def test_capitalize_suffix_acronym_with_dots(self) -> None:
        # Suffixes already written with dots (e.g. "M.D.") keep them and
        # do not title-case to "M.d." (issue #141). Through 2.3 the
        # exceptions map gave this string by SUBSTITUTING 'M.D.'; since
        # #459 md is a listed acronym the acronym clause writes in
        # capitals, recasing the word as written.
        hn = HumanName('GREGORY HOUSE M.D.')
        hn.capitalize()
        self.assertEqual(hn.suffix, 'M.D.')

    # A credential acronym the exceptions map doesn't carry is an
    # initialism, so a one-case suffix repairs to all-caps instead of
    # title-case (issue #459).
    def test_capitalize_suffix_acronym_is_all_caps(self) -> None:
        for src, expect in [
            ('JOHN SMITH MBA', 'John Smith MBA'),
            ('john smith jd', 'John Smith JD'),
            ('JOSE LUIS CPA', 'Jose Luis CPA'),
            ('john smith pmp', 'John Smith PMP'),
        ]:
            hn = HumanName(src)
            hn.capitalize()
            self.m(str(hn), expect, hn)

    # The exceptions map is asked before the all-caps acronym clause,
    # and since #459 it holds case MASKS: bsc and msc are listed
    # acronyms too, and the mask is what keeps them mixed-case where
    # the acronym clause would give 'BSC'. md left the map and reads
    # 'MD' by the acronym clause; 1.4.0 through 2.3.0 gave 'M.D.' and
    # 'Ph.D.', the map substituting its value for the word.
    def test_capitalize_exceptions_still_win_over_acronyms(self) -> None:
        for src, expect in [
            ('john smith md', 'John Smith MD'),
            ('john smith phd', 'John Smith PhD'),
            ('john smith ph.d.', 'John Smith Ph.D.'),
            ('john smith bsc', 'John Smith BSc'),
            ('JOHN SMITH MSC', 'John Smith MSc'),
        ]:
            hn = HumanName(src)
            hn.capitalize()
            self.m(str(hn), expect, hn)

    # #459: a capitalization_exceptions value is a case MASK -- the
    # key's own letters recased -- so a v1 Constants carrying any other
    # value raises at the first parse, where the snapshot builds the
    # Lexicon. A DECIDED exception to the shim's never-raise rule
    # (decisions.md#R4, and #3-0-reevaluations): 1.4.0 substituted
    # such a value for the word, repair now only recases, and no such
    # value was found in the tracker, the docs or any test.
    def test_a_mismatched_exception_value_raises_at_the_first_parse(
        self,
    ) -> None:
        c = Constants(capitalization_exceptions={'jr': 'Junior'})
        with pytest.raises(ValueError,
                           match="does not spell the key's letters"):
            HumanName('john smith jr', constants=c)
        ok = Constants(capitalization_exceptions={'jr': 'JR'})
        hn = HumanName('john smith jr', constants=ok)
        hn.capitalize()
        self.m(str(hn), 'John Smith JR', hn)

    # A word in the acronym vocabulary that parses as a family name
    # still repairs as an ordinary name word, not an acronym (#459).
    def test_capitalize_family_name_in_acronym_vocab_stays_title_case(self) -> None:
        hn = HumanName('anh van do')
        hn.capitalize()
        self.m(str(hn), 'Anh Van Do', hn)

    # Leaving already-capitalized names alone
    def test_no_change_to_mixed_chase(self) -> None:
        hn = HumanName('Shirley Maclaine')
        hn.capitalize()
        self.m(str(hn), 'Shirley Maclaine', hn)

    def test_force_capitalization(self) -> None:
        hn = HumanName('Shirley Maclaine')
        hn.capitalize(force=True)
        self.m(str(hn), 'Shirley MacLaine', hn)

    def test_capitalize_diacritics(self) -> None:
        hn = HumanName('matthëus schmidt')
        hn.capitalize()
        self.m(str(hn), 'Matthëus Schmidt', hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=15
    def test_downcasing_mac(self) -> None:
        hn = HumanName('RONALD MACDONALD')
        hn.capitalize()
        self.m(str(hn), 'Ronald MacDonald', hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=23
    def test_downcasing_mc(self) -> None:
        hn = HumanName('RONALD MCDONALD')
        hn.capitalize()
        self.m(str(hn), 'Ronald McDonald', hn)

    def test_short_names_with_mac(self) -> None:
        hn = HumanName('mack johnson')
        hn.capitalize()
        self.m(str(hn), 'Mack Johnson', hn)

    def test_portuguese_prefixes(self) -> None:
        hn = HumanName("joao da silva do amaral de souza")
        hn.capitalize()
        self.m(str(hn), 'Joao da Silva do Amaral de Souza', hn)

    def test_capitalize_prefix_clash_on_first_name(self) -> None:
        hn = HumanName("van nguyen")
        hn.capitalize()
        self.m(str(hn), 'Van Nguyen', hn)

    # #407, rules.md#R4. The family is one word and that word is
    # particle vocabulary, so nothing joins it to a name and it is not
    # doing a particle's work: family_base and initials have read it as
    # an ordinary name word since #404, and case repair now agrees.
    # Deliberately the v1 facade, and deliberately single-case input --
    # this MOVES v1-visible behavior (1.4.0 returns 'Anh do'), and the
    # mixed-case gate would return the input untouched (rules.md#R5).
    def test_capitalize_all_particle_family_is_a_name_word(self) -> None:
        hn = HumanName('ANH DO')
        hn.capitalize()
        self.m(str(hn), 'Anh Do', hn)

    # The reason the mark is read for the WHOLE PART rather than for a
    # particle standing alone: this family is 'van do', two particle
    # words and neither of them alone. A standing-alone rule would
    # capitalize the name above and leave this one lowercased, reading
    # the same surname two ways.
    def test_capitalize_all_particle_family_of_two_words(self) -> None:
        hn = HumanName('anh van do')
        hn.capitalize()
        self.m(str(hn), 'Anh Van Do', hn)

    # The recorded negative control for the two above (AGENTS.md's
    # guard-test convention): here 'de la' has 'vega' to join to, so
    # the particles are doing a particle's work and stay lowercase.
    # This FENCES the scope of #407 rather than pinning the fix -- it
    # passes both before and after the change, and fails only if the
    # new clause is widened to reach working particle runs.
    def test_capitalize_working_particle_stays_lowercase(self) -> None:
        hn = HumanName('juan de la vega')
        hn.capitalize()
        self.m(str(hn), 'Juan de la Vega', hn)

    # The corpus name that carries both halves of the predicate at
    # once, and the one the release-log bullet asserts: the family
    # `van der` is all particles and capitalizes, while the `y` keeps
    # its lowercase. This DOES pin the fix -- deleting the tag consult
    # gives 'y van der' -- but it is worth being exact about what it
    # does NOT pin, since a reviewer proposed it for that. It cannot
    # witness the conjunction conjunct being left ungated, and neither
    # can any other name parsed with the SHIPPED vocabulary: the mark
    # is applied to a part only where EVERY word in it carries
    # "particle" (_pipeline/_post_rules and _types._remarked alike),
    # and `particles` and `conjunctions` are disjoint in the default
    # lexicon and in all four locale packs, so no shipped conjunction
    # ever sits inside a marked part. That is a property of the
    # shipped DATA, not an invariant -- both sets are public API, and
    # `Lexicon.default().add(particles={'y'})` parses `anh y van` to
    # an all-particle family whose `y` carries the mark, giving
    # 'Anh y Van' where gating the conjunct too would give
    # 'Anh Y Van'. So the ungated conjunct decides something: it is
    # rules.md#R4's stated carve-out, matching R3's for initials,
    # rather than a no-op. The `y` here is a GIVEN-part word besides,
    # not a word of the all-particle family.
    def test_capitalize_all_particle_family_beside_a_conjunction(self) -> None:
        hn = HumanName('der, y van')
        hn.capitalize()
        self.m(str(hn), 'y Van Der', hn)

    # rules.md#R5's override, stated as a property rather than a
    # single row: mixed case is the writer making an explicit choice
    # and repair defers to it, so asking for repair REGARDLESS should
    # ignore the input's case entirely -- one name, one repaired
    # string, however it was written.
    #
    # Measured 2026-08-29, before the #383/#479 fork, on the
    # 1094-name corpus, because the promise is nearly true and the
    # exceptions are the whole story. On THIS surface --
    # `HumanName.capitalize()` and `str()`, which is what the test
    # below uses -- forcing repair differs from uppercasing the input
    # and calling `capitalize()` for 62 of the 1094, and from
    # lowercasing it for 16, so UPPERCASE IS THE WORSE DIRECTION, not
    # the clean one. Nor are the misses merely parse-level: of the 62,
    # only 25 move a role, and the other 37 parse byte-identically and
    # differ inside the repair itself. Through the v2 core --
    # `parse(n).capitalized(force=True)`, rendering all seven roles
    # -- the counts are 63 and 38, which is what decisions.md#R5
    # states. The one name the facade cannot see is
    # `Jane van der Berg nee y Jones`, whose conjunction sits in the
    # MAIDEN name: `str(HumanName)` renders the default spec, and
    # that spec omits the field. Recompute by running both forms over
    # the corpus files deduped and diffing, on whichever surface
    # you name. The #383/#479 fork removes the one-letter-conjunction
    # mechanism behind the uppercase direction (below), and a
    # re-measurement on this tree REVERSES the headline: the uppercase
    # count collapses and the direction flips, uppercase now differing
    # on fewer names than lowercase rather than more. The dated
    # re-measurement and its recipe (with the actual counts) live
    # under decisions.md#R5.
    #
    # THROUGH 2.3.0 the mechanism was v1's initial carve-out, taken in
    # the PARSE since #458 and read off the tag by the repair: a word
    # of the conjunction vocabulary was not tagged one where it was
    # written initial-shaped, and initial-shaped meant one CAPITAL
    # letter, full stop -- uppercase a name and every one-letter
    # conjunction became an initial; lowercase one and a middle
    # initial `E` became the Italian conjunction. `Velasquez y Garcia,
    # Dr. Juan Q.` forced kept `y`; uppercased then repaired gave `Y`
    # (decisions.md#R5).
    #
    # #383/#479 (rules.md#P3, decisions.md#P3) removed "one CAPITAL
    # letter" as the whole test: a name written wholly in one case
    # carries no case evidence, so the vocabulary decides instead of
    # the shape. Only the letters `Lexicon.conjunctions_ambiguous`
    # marks (just 'e' today) still read as an initial in a one-case
    # name, upper or lower alike -- so a middle initial `E` lowercased
    # into a one-case name stays an initial rather than becoming the
    # connective. A plain conjunction like 'y' now joins in a one-case
    # name the same way whichever case it is written in. This worked
    # example
    # has no bare `E`, so only the uppercase half is gone for IT --
    # measured, `HumanName('VELASQUEZ Y GARCIA, DR. JUAN Q.').capitalize()`
    # now agrees with the forced and lowercased forms, all three
    # giving `Dr. Juan Q. Velasquez y Garcia`; the lowercase half is
    # shown instead by `john e smith`
    # (tests/v2/test_render.py::test_capitalized_one_case_connective_that_reads_as_an_initial).
    # decisions.md#R5 carries the dated amendment for this. So the
    # property is pinned over names
    # carrying no single-letter word whose class case decides, and the
    # `conjunctions_ambiguous` exception is pinned beside it as data
    # rather than left to be rediscovered.
    def test_forcing_repair_ignores_the_case_it_was_given(self) -> None:
        for name in ('shirley maclaine', 'juan de la vega', 'anh van do',
                     'donovan mcnabb-smith', 'jane smith phd',
                     'lt. gen. john a. kenneth doe iv'):
            forced = HumanName(name)
            forced.capitalize(force=True)
            upper = HumanName(name.upper())
            upper.capitalize()
            lower = HumanName(name.lower())
            lower.capitalize()
            self.m(str(upper), str(forced), upper)
            self.m(str(lower), str(forced), lower)

    # This WAS the recorded exception to the property above through
    # 2.3, and the reason it was scoped rather than universal. The
    # #383/#479 fork (rules.md#P3, decisions.md#P3) reads a bare
    # capital single-letter conjunction in a one-case name as the
    # connective -- no case evidence says otherwise -- so
    # 'JUAN Y GARCIA' and 'juan y garcia' now repair to the same
    # string and the property above holds for them too. 1.4.0's
    # 'Juan Y Garcia' (measured on the released wheel) is the parity
    # break decisions.md#R5's 2026-09-13 amendment records; no ledger
    # compares case repair, which is why this test is the pin.
    #
    # The name is kept for the blame trail even though it now
    # overstates: what decides repair is the NAME's case class, not
    # the conjunction letter's own case -- 'y' reads the same way
    # whichever case it is itself written in, as long as the name
    # around it is one-case.
    def test_a_one_letter_conjunction_is_case_sensitive_to_repair(self) -> None:
        lowered = HumanName('juan y garcia')
        lowered.capitalize(force=True)
        self.m(str(lowered), 'Juan y Garcia', lowered)
        uppered = HumanName('JUAN Y GARCIA')
        uppered.capitalize()
        # #383/#479 fork, no longer inherited 1.4.0 behavior: 'JUAN Y
        # GARCIA' is written wholly in one case, so its bare capital
        # 'Y' carries no case evidence -- 'y' is not in
        # conjunctions_ambiguous, so it reads as the connective rather
        # than as an initial, and R4's carve-out lowercases it exactly
        # as it lowercases the all-lower spelling above (decisions.md#P3)
        self.m(str(uppered), 'Juan y Garcia', uppered)
        # mixed-case control: here the capital IS evidence, so 'Y'
        # reads as an initial exactly as it always has and repair
        # declines to touch it
        mixed = HumanName('Juan Y Garcia')
        mixed.capitalize()
        self.m(str(mixed), 'Juan Y Garcia', mixed)

    # The v1 parity this rests on, at the surface v1 users have. An
    # ASSIGNED field is spliced in as raw text and never classified, so
    # there is no tag to read and repair asks the vocabulary -- which is
    # what v1 always did, everywhere. Measured on the released 1.4.0
    # wheel and on 2.1.0, all four: 'John Velasquez y Garcia',
    # 'John Smith y Jones', 'John E. Smith', 'John Smith-y'. Reading the
    # tag alone (no fallback) capitalizes every one of these conjunctions
    # -- the regression #458's review caught before it shipped.
    def test_an_assigned_field_keeps_v1_conjunction_repair(self) -> None:
        for field, value, want in (
                ('last', 'velasquez y garcia', 'John Velasquez y Garcia'),
                ('last', 'smith y jones', 'John Smith y Jones'),
                # the initial carve-out: an assigned middle initial is
                # an initial, not the Italian conjunction
                ('middle', 'e.', 'John E. Smith'),
                # v1 asks per WORD of the assigned text, so the
                # conjunction ENDING a hyphenated word IS lowered here
                # -- the opposite of the parsed reading, where an edge
                # part is ordinary name text (pinned below), and the
                # difference is that one carries a reading. An
                # interior link is lowered on both paths since #478.
                ('last', 'smith-y', 'John Smith-y')):
            hn = HumanName('john smith')
            setattr(hn, field, value)
            hn.capitalize(force=True)
            self.m(str(hn), want, hn)

    # The other half of #458, and the half that MOVED: the decision is
    # the whole token's, so a conjunction word inside a longer token is
    # not one. `e` is the Italian conjunction and `e-f` is a middle
    # name; before #458 the repair re-ran the test over each word of a
    # token's text and gave 'Juan e-F Smith'. The uppercase spelling is
    # here to show the old answer was not even self-consistent: it read
    # `E` as initial-shaped and capitalized, so the same name repaired
    # to two different strings depending on how it was written.
    def test_a_conjunction_inside_a_longer_token_is_a_name_word(self) -> None:
        lowered = HumanName('juan e-f smith')
        lowered.capitalize(force=True)
        self.m(str(lowered), 'Juan E-F Smith', lowered)
        uppered = HumanName('JUAN E-F SMITH')
        uppered.capitalize()
        self.m(str(uppered), 'Juan E-F Smith', uppered)

    # #478: Ortega y Gasset is routinely hyphenated in catalogues, and
    # inside one hyphenated word a connective with a part on each side
    # keeps its lowercase -- the hyphens are the writer joining the name
    # around it, as the spaced connective does (rules.md#R4). This
    # reverses #458's answer for the INTERIOR position ('Jose
    # Ortega-Y-Gasset' at 2.2.0 and 2.3.0) and keeps it at the edges,
    # where a part has a neighbour on one side only and is ordinary
    # name text ('juan e-f smith' above, 'juan y-garcia' here). Both
    # one-case spellings now agree; 1.4.0 re-decided per word and gave
    # 'Jose Ortega-y-Gasset' lowered but 'Jose Ortega-Y-Gasset' upper
    # (measured on the released wheel), so the all-caps half is a
    # parity break, #479's one-case precedent. The SPACED form is the
    # contrast and was never in question -- there `y` is a token of its
    # own and the parse tags it the conjunction.
    def test_a_hyphenated_compound_surname_keeps_its_link_lowercase(
        self,
    ) -> None:
        lowered = HumanName('jose ortega-y-gasset')
        lowered.capitalize(force=True)
        self.m(str(lowered), 'Jose Ortega-y-Gasset', lowered)
        uppered = HumanName('JOSE ORTEGA-Y-GASSET')
        uppered.capitalize()
        self.m(str(uppered), 'Jose Ortega-y-Gasset', uppered)
        edge = HumanName('juan y-garcia')
        edge.capitalize()
        self.m(str(edge), 'Juan Y-Garcia', edge)
        spaced = HumanName('jose ortega y gasset')
        spaced.capitalize(force=True)
        self.m(str(spaced), 'Jose Ortega y Gasset', spaced)

    # The third producer of never-classified text, and the one that is
    # not an assignment: __getstate__ pickles the *_list STRINGS and
    # nothing else (mechanisms.md#FACADE-CONTRACT -- components come
    # back exactly as pickled, never re-parsed), so a load rebuilds
    # tokens with no tags on them. They are marked UNCLASSIFIED_TAG for
    # the same reason an assigned field is: reading the absent
    # conjunction tag as "not a conjunction" would repair a restored
    # 'juan ortega y gasset' to 'Juan Ortega Y Gasset', which is
    # neither 1.4.0's answer nor the same object's before pickling.
    def test_a_restored_pickle_keeps_v1_conjunction_repair(self) -> None:
        for text, want in (('juan ortega y gasset', 'Juan Ortega y Gasset'),
                           ('john de la vega', 'John de la Vega'),
                           ('juan y garcia', 'Juan y Garcia')):
            restored = pickle.loads(pickle.dumps(HumanName(text)))
            restored.capitalize(force=True)
            self.m(str(restored), want, restored)

    # One of a CLASS of names a pickle round trip changes, pinned so it
    # is not rediscovered as a bug. #458 moved the conjunction-versus-
    # initial decision into the parse, and a pickle carries no tags, so
    # the restored name is repaired the way 1.4.0 repaired everything
    # -- per word of the text, giving the Italian conjunction inside a
    # hyphenated middle name here. It is the pickle contract (strings
    # only, never a re-parse) meeting the tag read, not a defect in
    # either. 1.4.0 gave 'Juan e-F Smith' both ways. Since #383/#479
    # the one-case fork widened this class: 'JUAN Y GARCIA' and 'john e
    # smith' also diverge on a round trip now, for the same reason and
    # through the same fallback, whether the reader is capitalize() or
    # (since #528) initials() -- pinned at
    # tests/v2/test_facade.py::test_initials_of_an_unpickled_or_copied_name_ask_the_vocabulary_too.
    def test_a_pickle_round_trip_loses_the_e_f_reading(self) -> None:
        direct = HumanName('juan e-f smith')
        direct.capitalize(force=True)
        self.m(str(direct), 'Juan E-F Smith', direct)
        restored = pickle.loads(pickle.dumps(HumanName('juan e-f smith')))
        restored.capitalize(force=True)
        self.m(str(restored), 'Juan e-F Smith', restored)
