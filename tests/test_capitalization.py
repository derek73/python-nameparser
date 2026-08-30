import pytest

from nameparser import HumanName

from tests.base import HumanNameTestBase


class HumanNameCapitalizationTestCase(HumanNameTestBase):
    def test_capitalization_exception_for_III(self) -> None:
        hn = HumanName('juan q. xavier velasquez y garcia iii')
        hn.capitalize()
        self.m(str(hn), 'Juan Q. Xavier Velasquez y Garcia III', hn)

    # FIXME: this test does not pass due to a known issue
    # http://code.google.com/p/python-nameparser/issues/detail?id=22
    @pytest.mark.xfail
    def test_capitalization_exception_for_already_capitalized_III_KNOWN_FAILURE(self) -> None:
        hn = HumanName('juan garcia III')
        hn.capitalize()
        self.m(str(hn), 'Juan Garcia III', hn)

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
        self.assertEqual(hn.suffix_list, ['Ph.D.'])

    def test_capitalize_multiple_suffixes_still_split_correctly(self) -> None:
        hn = HumanName('JOHN DOE PHD MD')
        hn.capitalize()
        self.assertEqual(hn.suffix_list, ['Ph.D.', 'M.D.'])

    def test_capitalize_suffix_acronym_with_dots(self) -> None:
        # Suffixes already written with dots (e.g. "M.D.") should capitalize
        # to their exception form, not title-case to "M.d." (issue #141)
        hn = HumanName('GREGORY HOUSE M.D.')
        hn.capitalize()
        self.assertEqual(hn.suffix, 'M.D.')

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
    # Measured over the 1094-name differential corpus (2026-08-29),
    # because the promise is nearly true and the exceptions are the
    # whole story. On THIS surface -- `HumanName.capitalize()` and
    # `str()`, which is what the test below uses -- forcing repair
    # differs from uppercasing the input and calling `capitalize()`
    # for 62 of the 1094, and from lowercasing it for 16, so
    # UPPERCASE IS THE WORSE DIRECTION, not the clean one. Nor are
    # the misses merely parse-level: of the 62, only 25 move a role,
    # and the other 37 parse byte-identically and differ inside the
    # repair itself. Through the v2 core --
    # `parse(n).capitalized(force=True)`, rendering all seven roles
    # -- the counts are 63 and 38, which is what decisions.md#R5
    # states. The one name the facade cannot see is
    # `Jane van der Berg nee y Jones`, whose conjunction sits in the
    # MAIDEN name: `str(HumanName)` renders the default spec, and
    # that spec omits the field. Recompute by running both forms over
    # the four corpus files deduped and diffing, on whichever surface
    # you name.
    #
    # The mechanism is v1's initial carve-out, taken in the PARSE
    # since #458 and read off the tag by the repair: a word of the
    # conjunction vocabulary is not tagged one where it is written
    # initial-shaped, and initial-shaped means one CAPITAL letter
    # (nameparser/_pipeline/_classify.py, and the tests beside it --
    # the repair no longer asks). Uppercase a name and
    # every one-letter conjunction becomes an initial; lowercase one
    # and a middle initial `E` becomes the Italian conjunction. So
    # the property is pinned over names carrying no single-letter
    # word whose class case decides, and the exception is pinned
    # beside it as data rather than left to be rediscovered.
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

    # The recorded exception to the property above, and the reason it
    # is scoped rather than universal. 1.4.0 does exactly this too
    # (measured on the released wheel: 'JUAN Y GARCIA' capitalizes to
    # 'Juan Y Garcia'), so it is inherited behavior and not a 2.x
    # regression -- recorded here, deliberately not fixed here.
    def test_a_one_letter_conjunction_is_case_sensitive_to_repair(self) -> None:
        lowered = HumanName('juan y garcia')
        lowered.capitalize(force=True)
        self.m(str(lowered), 'Juan y Garcia', lowered)
        uppered = HumanName('JUAN Y GARCIA')
        uppered.capitalize()
        # 'Y' is initial-shaped, so the conjunction rule declines it
        self.m(str(uppered), 'Juan Y Garcia', uppered)

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
                # conjunction inside a hyphenated word IS lowered here
                # -- the opposite of the parsed reading pinned below,
                # and the difference is that one carries a reading
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
