# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from io import open
import json
import os
import sys

import pytest

from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants
from nameparser.util import u

TEST_DATA_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "names"
)
print(TEST_DATA_DIRECTORY)


def load_bank(category):
    filename = category + ".json"
    test_bank_file = os.path.join(TEST_DATA_DIRECTORY, filename)

    with open(test_bank_file, "r", encoding="utf8") as infile:
    # with io.open(test_bank_file, "r") as infile:
        test_bank = json.load(infile, encoding="utf-8")
    print("Loading {} cases for {} from {}.".format(len(test_bank), category, filename))
    return test_bank


def dict_entry_test(dict_entry):
    hn = HumanName(dict_entry["raw"])
    for attr in hn._members:
        actual = getattr(hn, attr)
        expected = dict_entry.get(attr, CONSTANTS.empty_attribute_default)
        assert actual == expected


def make_ids(entry):
    return entry.get("id") or entry.get("raw")


class TestCoreFunctionality:
    @pytest.mark.parametrize(
        "entry",
        [
            {
                "id": "test_utf8",
                "raw": "de la Véña, Jüan",
                "first": "Jüan",
                "last": "de la Véña",
            },
            {
                "id": "test_escaped_utf8_bytes",
                "raw": b"B\xc3\xb6ck, Gerald",
                "first": "Gerald",
                "last": "Böck",
            },
            {
                "id": "test_conjunction_names",
                "raw": "johnny y",
                "first": "johnny",
                "last": "y",
            },
            {
                "id": "test_prefixed_names",
                "raw": "vai la",
                "first": "vai",
                "last": "la",
            },
        ],
        ids=make_ids,
    )
    def test_basics(self, entry):
        dict_entry_test(entry)

    def test_blank(self):
        # This can't be parametrized in the same way as test_basics, because
        # CONSTANTS.empty_attribute_default is itself paramatrized at the module level
        dict_entry_test(
            {
                "id": "test_blank_name",
                "raw": "",
                "first": CONSTANTS.empty_attribute_default,
                "last": CONSTANTS.empty_attribute_default,
            }
        )

    def test_string_output(self,):
        hn = HumanName("de la Véña, Jüan")
        print(hn)
        print(repr(hn))

    @pytest.mark.parametrize(
        "raw, length", [("Doe-Ray, Dr. John P., CLU, CFP, LUTC", 5), ("John Doe", 2)]
    )
    def test_len(self, raw, length):
        assert len(HumanName(raw)) == length

    def test_comparison(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        assert hn1 == hn2
        assert hn1 is not hn2
        assert hn1 == "Dr. John P. Doe-Ray CLU, CFP, LUTC"
        hn1 = HumanName("Doe, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        assert hn1 != hn2
        assert hn1 != 0
        assert hn1 != "test"
        assert hn1 != ["test"]
        assert hn1 != {"test": hn2}

    def test_assignment_to_full_name(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        assert hn.first == "John"
        assert hn.last == "Doe"
        assert hn.middle == "A. Kenneth"
        assert hn.suffix == "Jr."
        hn.full_name = "Juan Velasquez y Garcia III"
        assert hn.first == "Juan"
        assert hn.last == "Velasquez y Garcia"
        assert hn.suffix == "III"

    def test_get_full_name_attribute_references_internal_lists(self):
        hn = HumanName("John Williams")
        hn.first_list = ["Larry"]
        assert hn.full_name, "Larry Williams"

    def test_assignment_to_attribute(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        hn.last = "de la Vega"
        assert hn.last == "de la Vega"
        hn.title = "test"
        assert hn.title == "test"
        hn.first = "test"
        assert hn.first == "test"
        hn.middle = "test"
        assert hn.middle == "test"
        hn.suffix = "test"
        assert hn.suffix == "test"
        with pytest.raises(TypeError):
            hn.suffix = [["test"]]
        with pytest.raises(TypeError):
            hn.suffix = {"test": "test"}

    def test_assign_list_to_attribute(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        hn.title = ["test1", "test2"]
        assert hn.title == "test1 test2"
        hn.first = ["test3", "test4"]
        assert hn.first == "test3 test4"
        hn.middle = ["test5", "test6", "test7"]
        assert hn.middle == "test5 test6 test7"
        hn.last = ["test8", "test9", "test10"]
        assert hn.last == "test8 test9 test10"
        hn.suffix = ["test"]
        assert hn.suffix == "test"

    def test_comparison_case_insensitive(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        assert hn1 == hn2
        assert hn1 is not hn2
        assert hn1 == "Dr. John P. Doe-ray clu, CFP, LUTC"

    def test_slice(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        assert list(hn), ["Dr.", "John", "P.", "Doe-Ray", "CLU, CFP, LUTC"]
        assert hn[1:] == [
            "John",
            "P.",
            "Doe-Ray",
            "CLU, CFP, LUTC",
            hn.C.empty_attribute_default,
        ]
        assert hn[1:-2], ["John", "P.", "Doe-Ray"]

    def test_getitem(self):
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        assert hn["title"], "Dr."
        assert hn["first"], "John"
        assert hn["last"], "Doe"
        assert hn["middle"], "A. Kenneth"
        assert hn["suffix"], "Jr."

    def test_setitem(self):
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        hn["title"] = "test"
        assert hn["title"], "test"
        hn["last"] = ["test", "test2"]
        assert hn["last"], "test test2"
        with pytest.raises(TypeError):
            hn["suffix"] = [["test"]]
        with pytest.raises(TypeError):
            hn["suffix"] = {"test": "test"}

    def test_surnames_list_attribute(self):
        hn = HumanName("John Edgar Casey Williams III")
        assert hn.surnames_list, ["Edgar", "Casey", "Williams"]

    def test_surnames_attribute(self):
        hn = HumanName("John Edgar Casey Williams III")
        assert hn.surnames == "Edgar Casey Williams"


class TestPickle:

    try:
        import dill

        no_dill = False
    except ImportError:
        no_dill = True

    @pytest.mark.skipif(no_dill, reason="requires python-dill module to test pickling")
    def test_config_pickle(self):
        constants = Constants()
        self.dill.pickles(constants)

    @pytest.mark.skipif(no_dill, reason="requires python-dill module to test pickling")
    def test_name_instance_pickle(self):
        hn = HumanName("Title First Middle Middle Last, Jr.")
        self.dill.pickles(hn)


class TestHumanNameBruteForce:
    @pytest.mark.parametrize("entry", load_bank("brute_force"), ids=make_ids)
    def test_brute(self, entry):
        dict_entry_test(entry)


class TestFirstNameHandling:
    @pytest.mark.parametrize("entry", load_bank("first_name"), ids=make_ids)
    def test_json_first_name(self, entry):
        dict_entry_test(entry)

    @pytest.mark.xfail(
        reason="# TODO: Seems 'Andrews, M.D.', Andrews should be treated as a last name"
        "but other suffixes like 'George Jr.' should be first names. "
        "Might be related to https://github.com/derek73/python-nameparser/issues/2"
    )
    def test_assume_suffix_title_and_one_other_name_is_last_name(self):
        hn = HumanName("Andrews, M.D.")
        assert hn.suffix == "M.D."
        assert hn.last == "Andrews"

    @pytest.mark.xfail
    def test_first_name_is_prefix_if_three_parts(self):
        """Not sure how to fix this without breaking Mr and Mrs"""
        hn = HumanName("Mr. Van Nguyen")
        assert hn.first == "Van"
        assert hn.last == "Nguyen"


class TestHumanNameConjunction:
    @pytest.mark.parametrize("entry", load_bank("conjunction"), ids=make_ids)
    def test_json_conjunction(self, entry):
        dict_entry_test(entry)

    @pytest.mark.xfail
    def test_two_initials_conflict_with_conjunction(self):
        # Supporting this seems to screw up titles with periods in them like M.B.A.
        hn = HumanName("E.T. Smith")
        assert hn.first == "E."
        assert hn.middle == "T."
        assert hn.last == "Smith"

    @pytest.mark.xfail
    def test_conjunction_in_an_address_with_a_first_name_title(self):
        hn = HumanName("Her Majesty Queen Elizabeth")
        assert hn.title == "Her Majesty Queen"
        # if you want to be technical, Queen is in FIRST_NAME_TITLES
        assert hn.first == "Elizabeth"


class TestConstantsCustomization:
    def test_add_title(self):
        hn = HumanName("Te Awanui-a-Rangi Black", constants=None)
        start_len = len(hn.C.titles)
        assert start_len > 0
        hn.C.titles.add("te")
        assert start_len + 1 == len(hn.C.titles)
        hn.parse_full_name()
        assert hn.title == "Te"
        assert hn.first == "Awanui-a-Rangi"
        assert hn.last == "Black"

    def test_remove_title(self):
        hn = HumanName("Hon Solo", constants=None)
        start_len = len(hn.C.titles)
        assert start_len > 0
        hn.C.titles.remove("hon")
        assert start_len - 1 == len(hn.C.titles)
        hn.parse_full_name()
        assert hn.first == "Hon"
        assert hn.last == "Solo"

    def test_add_multiple_arguments(self):
        hn = HumanName("Assoc Dean of Chemistry Robert Johns", constants=None)
        hn.C.titles.add("dean", "Chemistry")
        hn.parse_full_name()
        assert hn.title == "Assoc Dean of Chemistry"
        assert hn.first == "Robert"
        assert hn.last == "Johns"

    def test_instances_can_have_own_constants(self):
        hn = HumanName("", None)
        hn2 = HumanName("")
        hn.C.titles.remove("hon")
        assert "hon" not in hn.C.titles
        assert hn.has_own_config
        assert "hon" in hn2.C.titles
        assert not hn2.has_own_config

    def test_can_change_global_constants(self):
        hn = HumanName("")
        hn2 = HumanName("")
        hn.C.titles.remove("hon")
        assert "hon" not in hn.C.titles
        assert "hon" not in hn2.C.titles
        assert not hn.has_own_config
        assert not hn2.has_own_config
        # clean up so we don't mess up other tests
        hn.C.titles.add("hon")

    def test_remove_multiple_arguments(self):
        hn = HumanName("Ms Hon Solo", constants=None)
        hn.C.titles.remove("hon", "ms")
        hn.parse_full_name()
        assert hn.first == "Ms"
        assert hn.middle == "Hon"
        assert hn.last == "Solo"

    def test_chain_multiple_arguments(self):
        hn = HumanName("Dean Ms Hon Solo", constants=None)
        hn.C.titles.remove("hon", "ms").add("dean")
        hn.parse_full_name()
        assert hn.title == "Dean"
        assert hn.first == "Ms"
        assert hn.middle == "Hon"
        assert hn.last == "Solo"

    def test_empty_attribute_default(self):
        from nameparser.config import CONSTANTS

        _orig = CONSTANTS.empty_attribute_default
        CONSTANTS.empty_attribute_default = None
        hn = HumanName("")
        assert hn.title is None
        assert hn.first is None
        assert hn.middle is None
        assert hn.last is None
        assert hn.suffix is None
        assert hn.nickname is None
        CONSTANTS.empty_attribute_default = _orig

    def test_empty_attribute_on_instance(self):
        hn = HumanName("", None)
        hn.C.empty_attribute_default = None
        assert hn.title is None
        assert hn.first is None
        assert hn.middle is None
        assert hn.last is None
        assert hn.suffix is None
        assert hn.nickname is None

    def test_none_empty_attribute_string_formatting(self):
        hn = HumanName("", None)
        hn.C.empty_attribute_default = None
        assert str(hn) == ""

    def test_add_constant_with_explicit_encoding(self):
        c = Constants()
        c.titles.add_with_encoding(b"b\351ck", encoding="latin_1")
        assert "béck" in c.titles


class TestNickname:
    @pytest.mark.parametrize("entry", load_bank("nickname"), ids=make_ids)
    def test_json_nickname(self, entry):
        dict_entry_test(entry)

    # http://code.google.com/p/python-nameparser/issues/detail?id=17
    def test_parenthesis_are_removed_from_name(self):
        hn = HumanName("John Jones (Unknown)")
        assert hn.first == "John"
        assert hn.last == "Jones"
        assert hn.nickname != CONSTANTS.empty_attribute_default

    # http://code.google.com/p/python-nameparser/issues/detail?id=17
    # not testing nicknames because we don't actually care about Google Docs here
    def test_duplicate_parenthesis_are_removed_from_name(self):
        hn = HumanName("John Jones (Google Docs), Jr. (Unknown)")
        assert hn.first == "John"
        assert hn.last == "Jones"
        assert hn.suffix == "Jr."
        assert hn.nickname != CONSTANTS.empty_attribute_default

    @pytest.mark.xfail
    def test_nickname_and_last_name_with_title(self):
        hn = HumanName('Senator "Rick" Edmonds')
        assert hn.title == "Senator"
        assert hn.first == CONSTANTS.empty_attribute_default
        assert hn.last == "Edmonds"
        assert hn.nickname == "Rick"


class TestPrefixes:
    @pytest.mark.parametrize("entry", load_bank("prefix"), ids=make_ids)
    def test_json_prefix(self, entry):
        dict_entry_test(entry)


class TestSuffixes:
    @pytest.mark.parametrize("entry", load_bank("suffix"), ids=make_ids)
    def test_json_suffix(self, entry):
        dict_entry_test(entry)

    @pytest.mark.xfail(
        reason="TODO: handle conjunctions in last names"
        " followed by first names clashing with suffixes"
    )
    def test_potential_suffix_that_is_also_first_name_comma_with_conjunction(self):
        hn = HumanName("De la Vina, Bart")
        assert hn.first == "Bart"
        assert hn.last == "De la Vina"

    @pytest.mark.xfail(reason="https://github.com/derek73/python-nameparser/issues/27")
    def test_king(self):
        hn = HumanName("Dr King Jr")
        assert hn.title == "Dr"
        assert hn.last == "King"
        assert hn.suffix == "Jr"


class TestTitle:
    @pytest.mark.parametrize("entry", load_bank("title"), ids=make_ids)
    def test_json_title(self, entry):
        dict_entry_test(entry)

    @pytest.mark.xfail(reason="TODO: fix handling of U.S.")
    def test_chained_title_first_name_title_is_initials(self):
        hn = HumanName("U.S. District Judge Marc Thomas Treadwell")
        assert hn.title == "U.S. District Judge"
        assert hn.first == "Marc"
        assert hn.middle == "Thomas"
        assert hn.last == "Treadwell"

    @pytest.mark.xfail(
        reason=" 'ben' is removed from PREFIXES in v0.2.5"
        "this test could re-enable this test if we decide to support 'ben' as a prefix"
    )
    def test_title_multiple_titles_with_apostrophe_s(self):
        hn = HumanName("The Right Hon. the President of the Queen's Bench Division")
        assert hn.title == "The Right Hon. the President of the Queen's Bench Division"

    @pytest.mark.xfail
    def test_ben_as_conjunction(self):
        hn = HumanName("Ahmad ben Husain")
        assert hn.first == "Ahmad"
        assert hn.last == "ben Husain"


class TestHumanNameCapitalization:
    @pytest.mark.parametrize("entry", load_bank("capitalization"), ids=make_ids)
    def test_json_capitalization(self, entry):
        hn = HumanName(entry["raw"])
        hn.capitalize()
        if sys.version_info.major < 3:
            assert u(hn) == entry["string"]
        else:
            assert str(hn) == entry["string"]

    @pytest.mark.parametrize(
        "name, is_forced",
        [
            ("Shirley Maclaine", {True: "Shirley MacLaine", False: "Shirley Maclaine"}),
            ("Baron Mcyolo", {True: "Baron McYolo", False: "Baron Mcyolo"}),
        ],
    )
    @pytest.mark.parametrize("force", [True, False])
    def test_no_capitalization_change_unless_forced(self, name, is_forced, force):
        hn = HumanName(name)
        hn.capitalize(force=force)
        assert str(hn) == is_forced[force]

    @pytest.mark.xfail(
        reason="FIXME: this test does not pass due to a known issue "
        "http://code.google.com/p/python-nameparser/issues/detail?id=22"
    )
    def test_capitalization_exception_for_already_capitalized_III_KNOWN_FAILURE(self):
        hn = HumanName("juan garcia III")
        hn.capitalize()
        assert str(hn) == "Juan Garcia III"


class TestHumanNameOutputFormat:
    def test_formatting_init_argument(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)", string_format="TEST1")
        assert u(hn) == "TEST1"

    def test_formatting_constants_attribute(self):
        from nameparser.config import CONSTANTS

        _orig = CONSTANTS.string_format
        CONSTANTS.string_format = "TEST2"
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        assert u(hn) == "TEST2"
        CONSTANTS.string_format = _orig

    def test_quote_nickname_formating(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        assert u(hn) == "Rev John A. Kenneth Doe III 'Kenny'"
        hn.string_format = "{last}, {title} {first} {middle}, {suffix} '{nickname}'"
        assert u(hn) == "Doe, Rev John A. Kenneth, III 'Kenny'"

    def test_formating_removing_keys_from_format_string(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        assert u(hn) == "Rev John A. Kenneth Doe III 'Kenny'"
        hn.string_format = "{last}, {title} {first} {middle}, {suffix}"
        assert u(hn) == "Doe, Rev John A. Kenneth, III"
        hn.string_format = "{last}, {title} {first} {middle}"
        assert u(hn) == "Doe, Rev John A. Kenneth"
        hn.string_format = "{last}, {first} {middle}"
        assert u(hn) == "Doe, John A. Kenneth"
        hn.string_format = "{last}, {first}"
        assert u(hn) == "Doe, John"
        hn.string_format = "{first} {last}"
        assert u(hn) == "John Doe"

    def test_formating_removing_pieces_from_name_buckets(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        assert u(hn) == "Rev John A. Kenneth Doe III 'Kenny'"
        hn.string_format = "{title} {first} {middle} {last} {suffix}"
        assert u(hn) == "Rev John A. Kenneth Doe III"
        hn.middle = ""
        assert u(hn) == "Rev John Doe III"
        hn.suffix = ""
        assert u(hn) == "Rev John Doe"
        hn.title = ""
        assert u(hn) == "John Doe"

    def test_formating_of_nicknames_with_parenthesis(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} ({nickname})"
        assert u(hn) == "Rev John A. Kenneth Doe III (Kenny)"
        hn.nickname = ""
        assert u(hn) == "Rev John A. Kenneth Doe III"

    def test_formating_of_nicknames_with_single_quotes(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        assert u(hn) == "Rev John A. Kenneth Doe III 'Kenny'"
        hn.nickname = ""
        assert u(hn) == "Rev John A. Kenneth Doe III"

    def test_formating_of_nicknames_with_double_quotes(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = '{title} {first} {middle} {last} {suffix} "{nickname}"'
        assert u(hn) == 'Rev John A. Kenneth Doe III "Kenny"'
        hn.nickname = ""
        assert u(hn) == "Rev John A. Kenneth Doe III"

    def test_formating_of_nicknames_in_middle(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} ({nickname}) {middle} {last} {suffix}"
        assert u(hn) == "Rev John (Kenny) A. Kenneth Doe III"
        hn.nickname = ""
        assert u(hn) == "Rev John A. Kenneth Doe III"

    def test_remove_emojis(self):
        hn = HumanName("Sam Smith 😊")
        assert hn.first == "Sam"
        assert hn.last == "Smith"
        assert u(hn) == "Sam Smith"

    def test_keep_non_emojis(self):
        hn = HumanName("∫≜⩕ Smith 😊")
        assert hn.first == "∫≜⩕"
        assert hn.last == "Smith"
        assert u(hn) == "∫≜⩕ Smith"

    def test_keep_emojis(self):
        constants = Constants()
        constants.regexes.emoji = False
        hn = HumanName("∫≜⩕ Smith😊", constants)
        assert hn.first == "∫≜⩕"
        assert hn.last == "Smith😊"
        assert u(hn) == "∫≜⩕ Smith😊"
        # test cleanup


class TestHumanNameVariations:
    """Test automated variations of names in TEST_NAMES.

    Helps test that the 3 code trees work the same"""

    @pytest.mark.parametrize("name", load_bank("bare_names"))
    def test_json_variations(self, name):
        self.run_variations(name)

    def run_variations(self, name):
        """ Run several variations

        This is a separate function so that individual non-parametrized tests can be
        added if desired.
        """
        hn = HumanName(name)
        if len(hn.suffix_list) > 1:
            hn = HumanName(
                "{title} {first} {middle} {last} {suffix}".format(**hn.as_dict()).split(
                    ","
                )[0]
            )
        # format strings below require empty string
        hn.C.empty_attribute_default = ""
        hn_dict = hn.as_dict()
        nocomma = HumanName(
            "{title} {first} {middle} {last} {suffix}".format(**hn_dict)
        )
        lastnamecomma = HumanName(
            "{last}, {title} {first} {middle} {suffix}".format(**hn_dict)
        )
        if hn.suffix:
            suffixcomma = HumanName(
                "{title} {first} {middle} {last}, {suffix}".format(**hn_dict)
            )
        if hn.nickname:
            nocomma = HumanName(
                "{title} {first} {middle} {last} {suffix} ({nickname})".format(
                    **hn_dict
                )
            )
            lastnamecomma = HumanName(
                "{last}, {title} {first} {middle} {suffix} ({nickname})".format(
                    **hn_dict
                )
            )
            if hn.suffix:
                suffixcomma = HumanName(
                    "{title} {first} {middle} {last}, {suffix} ({nickname})".format(
                        **hn_dict
                    )
                )
        for attr in hn._members:
            assert getattr(hn, attr) == getattr(nocomma, attr)
            assert getattr(hn, attr) == getattr(lastnamecomma, attr)
            if hn.suffix:
                assert getattr(hn, attr) == getattr(suffixcomma, attr)


class TestMaidenName:

    no_maiden_names = getattr(HumanName(), "maiden", None) is None

    @pytest.mark.skipif(no_maiden_names, reason="Maiden names not implemented.")
    def test_parenthesis_and_quotes_together(self):
        hn = HumanName("Jennifer 'Jen' Jones (Duff)")
        assert hn.first == "Jennifer"
        assert hn.last == "Jones"
        assert hn.nickname == "Jen"
        assert hn.maiden == "Duff"

    @pytest.mark.skipif(no_maiden_names, reason="Maiden names not implemented.")
    def test_maiden_name_with_nee(self):
        # https://en.wiktionary.org/wiki/née
        hn = HumanName("Mary Toogood nee Johnson")
        assert hn.first == "Mary"
        assert hn.last == "Toogood"
        assert hn.maiden == "Johnson"

    @pytest.mark.skipif(no_maiden_names, reason="Maiden names not implemented.")
    def test_maiden_name_with_accented_nee(self):
        # https://en.wiktionary.org/wiki/née
        hn = HumanName("Mary Toogood née Johnson")
        assert hn.first == "Mary"
        assert hn.last == "Toogood"
        assert hn.maiden == "Johnson"

    @pytest.mark.skipif(no_maiden_names, reason="Maiden names not implemented.")
    def test_maiden_name_with_nee_and_comma(self):
        # https://en.wiktionary.org/wiki/née
        hn = HumanName("Mary Toogood, née Johnson")
        assert hn.first == "Mary"
        assert hn.last == "Toogood"
        assert hn.maiden == "Johnson"

    @pytest.mark.skipif(no_maiden_names, reason="Maiden names not implemented.")
    def test_maiden_name_with_nee_with_parenthesis(self):
        hn = HumanName("Mary Toogood (nee Johnson)")
        assert hn.first == "Mary"
        assert hn.last == "Toogood"
        assert hn.maiden == "Johnson"

    @pytest.mark.skipif(no_maiden_names, reason="Maiden names not implemented.")
    def test_maiden_name_with_parenthesis(self):
        hn = HumanName("Mary Toogood (Johnson)")
        assert hn.first == "Mary"
        assert hn.last == "Toogood"
        assert hn.maiden == "Johnson"


if __name__ == "__main__":
    # Pass through any/all arguments to pytest
    pytest.main(sys.argv)
