import re

import pytest

from nameparser import HumanName
from nameparser.config import Constants

from tests.base import HumanNameTestBase


class NicknameTestCase(HumanNameTestBase):
    # https://code.google.com/p/python-nameparser/issues/detail?id=33
    def test_nickname_in_parenthesis(self) -> None:
        hn = HumanName("Benjamin (Ben) Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    # https://github.com/derek73/python-nameparser/issues/112
    def test_add_custom_nickname_delimiter_raises(self) -> None:
        # Custom (non-sentinel) delimiter additions raise in 2.0 (deliberate
        # divergence, migration spec section 3 -- same uniform rule as
        # regexes); Policy(nickname_delimiters=...) is the replacement. The
        # v1 tests for removing custom delimiters, registering several at
        # once, and the ambiguous-acronym carve-out through a custom
        # delimiter died with the mechanism.
        hn = HumanName("Benjamin {Ben} Franklin", constants=Constants())
        # curly braces aren't a recognized delimiter by default
        self.m(hn.nickname, "", hn)
        with pytest.raises(TypeError, match="Policy"):
            hn.C.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')

    def test_overriding_builtin_regex_raises(self) -> None:
        # v1's other customization path -- replacing a regexes entry so the
        # built-in delimiter sentinels resolve to it live -- is the same
        # uniform 2.0 removal: any regexes assignment raises, pointing at
        # Policy.
        hn = HumanName("Benjamin [Ben] Franklin", constants=Constants())
        self.m(hn.nickname, "", hn)
        with pytest.raises(TypeError, match="Policy"):
            hn.C.regexes['parenthesis'] = re.compile(r'\[(.*?)\]')

    def test_two_word_nickname_in_parenthesis(self) -> None:
        hn = HumanName("Benjamin (Big Ben) Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_two_words_in_quotes(self) -> None:
        hn = HumanName('Benjamin "Big Ben" Franklin')
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_nickname_in_parenthesis_with_comma(self) -> None:
        hn = HumanName("Franklin, Benjamin (Ben)")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_parenthesis_with_comma_and_suffix(self) -> None:
        hn = HumanName("Franklin, Benjamin (Ben), Jr.")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_single_quotes(self) -> None:
        hn = HumanName("Benjamin 'Ben' Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_double_quotes(self) -> None:
        hn = HumanName("Benjamin \"Ben\" Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_single_quotes_on_first_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("Brian Andrew O'connor")
        self.m(hn.first, "Brian", hn)
        self.m(hn.middle, "Andrew", hn)
        self.m(hn.last, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_both_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("La'tanya O'connor")
        self.m(hn.first, "La'tanya", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_end_of_last_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("Mari' Aube'")
        self.m(hn.first, "Mari'", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Aube'", hn)
        self.m(hn.nickname, "", hn)

    def test_okina_inside_name_not_treated_as_nickname(self) -> None:
        hn = HumanName("Harrieta Keōpūolani Nāhiʻenaʻena")
        self.m(hn.first, "Harrieta", hn)
        self.m(hn.middle, "Keōpūolani", hn)
        self.m(hn.last, "Nāhiʻenaʻena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Hawaiian_example(self) -> None:
        hn = HumanName("Harietta Keopuolani Nahi'ena'ena")
        self.m(hn.first, "Harietta", hn)
        self.m(hn.middle, "Keopuolani", hn)
        self.m(hn.last, "Nahi'ena'ena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Kenyan_example(self) -> None:
        hn = HumanName("Naomi Wambui Ng'ang'a")
        self.m(hn.first, "Naomi", hn)
        self.m(hn.middle, "Wambui", hn)
        self.m(hn.last, "Ng'ang'a", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Samoan_example(self) -> None:
        hn = HumanName("Va'apu'u Vitale")
        self.m(hn.first, "Va'apu'u", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Vitale", hn)
        self.m(hn.nickname, "", hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=17
    def test_parenthesis_are_removed_from_name(self) -> None:
        hn = HumanName("John Jones (Unknown)")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)
        # not testing the nicknames because we don't actually care
        # about Google Docs here

    def test_duplicate_parenthesis_are_removed_from_name(self) -> None:
        hn = HumanName("John Jones (Google Docs), Jr. (Unknown)")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_nickname_and_last_name(self) -> None:
        hn = HumanName('"Rick" Edmonds')
        self.m(hn.first, "", hn)
        self.m(hn.last, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)

    @pytest.mark.xfail
    def test_nickname_and_last_name_with_title(self) -> None:
        hn = HumanName('Senator "Rick" Edmonds')
        self.m(hn.title, "Senator", hn)
        self.m(hn.first, "", hn)
        self.m(hn.last, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)

    def test_ambiguous_suffix_acronym_in_parenthesis_stays_nickname(self) -> None:
        # JD is in SUFFIX_ACRONYMS_AMBIGUOUS: both a law-degree acronym and a
        # common given-name nickname. Existing behavior (nickname) must be
        # preserved -- see issue #111.
        hn = HumanName("JEFFREY (JD) BRICKEN")
        self.m(hn.nickname, "JD", hn)
        self.m(hn.suffix, "", hn)

class MaidenNameTestCase(HumanNameTestBase):
    def test_maiden_assignment_and_property(self) -> None:
        hn = HumanName("Jenny Baker")
        hn.maiden = "Johnson"
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_defaults_empty(self) -> None:
        hn = HumanName("Jenny Baker")
        self.m(hn.maiden, "", hn)

    def test_maiden_key_always_in_as_dict(self) -> None:
        # empty attributes are always '' in 2.0 (#255)
        hn = HumanName("Bob Dole")
        self.assertEqual(hn.as_dict()['maiden'], '')
        self.assertNotIn('maiden', hn.as_dict(False))

    def test_maiden_appears_in_as_dict_when_populated(self) -> None:
        hn = HumanName("Jenny Baker")
        hn.maiden = "Johnson"
        self.assertEqual(hn.as_dict()['maiden'], "Johnson")
        self.assertEqual(hn.as_dict(False)['maiden'], "Johnson")

    def test_maiden_appears_in_slice(self) -> None:
        # list(hn), not the deprecated hn[:] slice (#258)
        hn = HumanName("Jenny Baker")
        hn.maiden = "Johnson"
        self.assertIn("Johnson", list(hn))

    def test_maiden_via_constructor_kwarg(self) -> None:
        hn = HumanName(first="Jenny", last="Baker", maiden="Johnson")
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_name_in_parenthesis_with_comma(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Baker (Johnson), Jenny", constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_name_in_parenthesis_no_comma(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Jenny Baker (Johnson)", constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_quotes_still_nickname_when_parens_routed_to_maiden(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName('Jenny "JJ" Baker (Johnson)', constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.nickname, "JJ", hn)
        self.m(hn.maiden, "Johnson", hn)

    def test_maiden_off_by_default_parenthesis_still_routes_to_nickname(self) -> None:
        hn = HumanName("Baker (Johnson), Jenny")
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.nickname, "Johnson", hn)
        self.m(hn.maiden, "", hn)

    def test_suffix_shaped_content_in_maiden_bucket_stays_in_place(self) -> None:
        # The #189 suffix-shaped carve-out in handle_match() applies
        # regardless of which bucket the delimiter routes to.
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Baker (Jr.), Jenny", constants=C)
        self.m(hn.first, "Jenny", hn)
        self.m(hn.last, "Baker", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.maiden, "", hn)

    def test_marker_inside_maiden_parenthesis_is_consumed(self) -> None:
        # #329 through the v1 API, which is where the release log
        # promises it. The shared case table cannot reach this: its
        # maiden_delimiters rows all skip the facade runner (Policy's
        # maiden-wins canonicalization takes the pair away from
        # nickname, so the row no longer matches the v1-expressible
        # shape), and the bucket move below is the spelling that does
        # express it. Same value as the bare "Jane Smith née Jones",
        # which is the agreement #329 was about.
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Jane Smith (née Jones)", constants=C)
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.maiden, "Jones", hn)

    def test_unmarked_maiden_parenthesis_keeps_every_word(self) -> None:
        # The other side of the same rule: the drop is conditioned on
        # the first word being a marker, so ordinary two-word content
        # arrives whole.
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Jane Smith (Mary Jones)", constants=C)
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.maiden, "Mary Jones", hn)

    def test_lone_marker_word_in_its_own_parenthesis_is_a_name(self) -> None:
        # `Nee` is a real surname (Irish Ní/Nee, and a Chinese
        # romanization), so a one-word clause is content whatever it
        # spells -- even with a second clause following that could read
        # as the name it marks.
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Jane Smith (Nee) (Jones)", constants=C)
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.maiden, "Nee Jones", hn)

    def test_maiden_appears_in_as_dict_via_routing(self) -> None:
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.nickname_delimiters.pop('parenthesis')
        hn = HumanName("Baker (Johnson), Jenny", constants=C)
        self.assertEqual(hn.as_dict()['maiden'], "Johnson")

    def test_unresolvable_string_sentinel_raises(self) -> None:
        # A string value that doesn't name a real delimiter used to silently
        # fall back to EMPTY_REGEX in v1 (matching at every position and
        # corrupting parsing) until 1.3 made the parse raise ValueError. 2.0
        # enforces the invariant one step earlier: the delimiter managers
        # accept only the named sentinels, so the typo fails loudly at
        # assignment instead of at the next parse.
        C = Constants()
        with pytest.raises(TypeError, match="sentinel"):
            C.nickname_delimiters['typo'] = 'parenthesus'

    def test_routing_same_delimiter_to_both_buckets_nickname_wins(self) -> None:
        # Misuse case: assigning the same key into both dicts instead of
        # moving it with pop() (as the docs instruct). nickname_delimiters is
        # processed first in parse_nicknames()'s bucket loop, so it consumes
        # the match via re.sub() before maiden_delimiters ever sees it --
        # maiden stays empty. Pinning this precedence so it doesn't silently
        # change if the bucket processing order is ever reordered.
        C = Constants()
        C.maiden_delimiters['parenthesis'] = C.regexes['parenthesis']
        hn = HumanName("Baker (Johnson), Jenny", constants=C)
        self.m(hn.nickname, "Johnson", hn)
        self.m(hn.maiden, "", hn)

