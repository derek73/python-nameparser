# -*- coding: utf-8 -*-
from __future__ import unicode_literals
"""
Run this file to run the tests.

``python tests.py``

Or install nose and run nosetests.

``pip install nose``

then:

``nosetests``

Post a ticket and/or clone and fix it. Pull requests with tests gladly accepted.
https://github.com/derek73/python-nameparser/issues
https://github.com/derek73/python-nameparser/pulls
"""

import logging
try:
    import dill
except ImportError:
    dill = False

from nameparser import HumanName
from nameparser.util import u
from nameparser.config import Constants

log = logging.getLogger('HumanName')

import json
import unittest
try:
    unittest.expectedFailure
except AttributeError:
    # Python 2.6 backport
    import unittest2 as unittest


class HumanNameTestBase(unittest.TestCase):
    def m(self, actual, expected, hn):
        """assertEquals with a better message and awareness of hn.C.empty_attribute_default"""
        expected = expected or hn.C.empty_attribute_default
        try:
            self.assertEqual(actual, expected, "'%s' != '%s' for '%s'\n%r" % (
                actual,
                expected,
                hn.full_name,
                hn
            ))
        except UnicodeDecodeError:
            self.assertEquals(actual, expected)

class HumanNameBruteForceTests(HumanNameTestBase):

    def test_json_names(self):
        all_name_tests = json.load(open('testnames.json', 'r'))
        for testname in all_name_tests.keys():
            hn = HumanName(all_name_tests[testname]['name'])
            for part in all_name_tests[testname].keys():
                if part == 'name': continue
                self.m(getattr(hn, part),
                       all_name_tests[testname][part],
                       hn)

class HumanNamePythonTests(HumanNameTestBase):

    def test_string_output(self):
        hn = HumanName("de la Véña, Jüan")
        print(hn)
        print(repr(hn))

    def test_escaped_utf8_bytes(self):
        hn = HumanName(b'B\xc3\xb6ck, Gerald')
        self.m(hn.first, "Gerald", hn)
        self.m(hn.last, "Böck", hn)

    def test_len(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(len(hn), 5, hn)
        hn = HumanName("John Doe")
        self.m(len(hn), 2, hn)

    @unittest.skipUnless(dill,"requires python-dill module to test pickling")
    def test_config_pickle(self):
        C = Constants()
        self.assertTrue(dill.pickles(C))

    @unittest.skipUnless(dill,"requires python-dill module to test pickling")
    def test_name_instance_pickle(self):
        hn = HumanName("Title First Middle Middle Last, Jr.")
        self.assertTrue(dill.pickles(hn))

    def test_comparison(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1 == hn2)
        self.assertTrue(not hn1 is hn2)
        self.assertTrue(hn1 == "Dr. John P. Doe-Ray CLU, CFP, LUTC")
        hn1 = HumanName("Doe, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(not hn1 == hn2)
        self.assertTrue(not hn1 == 0)
        self.assertTrue(not hn1 == "test")
        self.assertTrue(not hn1 == ["test"])
        self.assertTrue(not hn1 == {"test": hn2})

    def test_assignment_to_full_name(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)
        hn.full_name = "Juan Velasquez y Garcia III"
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test_assignment_to_attribute(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        hn.last = "de la Vega"
        self.m(hn.last, "de la Vega", hn)
        hn.title = "test"
        self.m(hn.title, "test", hn)
        hn.first = "test"
        self.m(hn.first, "test", hn)
        hn.middle = "test"
        self.m(hn.middle, "test", hn)
        hn.suffix = "test"
        self.m(hn.suffix, "test", hn)
        with self.assertRaises(TypeError):
            hn.suffix = [['test']]
        with self.assertRaises(TypeError):
            hn.suffix = {"test":"test"}

    def test_assign_list_to_attribute(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        hn.title = ["test1","test2"]
        self.m(hn.title, "test1 test2", hn)
        hn.first = ["test3","test4"]
        self.m(hn.first, "test3 test4", hn)
        hn.middle = ["test5","test6","test7"]
        self.m(hn.middle, "test5 test6 test7", hn)
        hn.last = ["test8","test9","test10"]
        self.m(hn.last, "test8 test9 test10", hn)
        hn.suffix = ['test']
        self.m(hn.suffix, "test", hn)

    def test_comparison_case_insensitive(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1 == hn2)
        self.assertTrue(not hn1 is hn2)
        self.assertTrue(hn1 == "Dr. John P. Doe-ray clu, CFP, LUTC")

    def test_slice(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(list(hn), ['Dr.', 'John', 'P.', 'Doe-Ray', 'CLU, CFP, LUTC'], hn)
        self.m(hn[1:], ['John', 'P.', 'Doe-Ray', 'CLU, CFP, LUTC',hn.C.empty_attribute_default], hn)
        self.m(hn[1:-2], ['John', 'P.', 'Doe-Ray'], hn)

    def test_getitem(self):
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        self.m(hn['title'], "Dr.", hn)
        self.m(hn['first'], "John", hn)
        self.m(hn['last'], "Doe", hn)
        self.m(hn['middle'], "A. Kenneth", hn)
        self.m(hn['suffix'], "Jr.", hn)

    def test_setitem(self):
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        hn['title'] = 'test'
        self.m(hn['title'], "test", hn)
        hn['last'] = ['test','test2']
        self.m(hn['last'], "test test2", hn)
        with self.assertRaises(TypeError):
            hn["suffix"] = [['test']]
        with self.assertRaises(TypeError):
            hn["suffix"] = {"test":"test"}

class FirstNameHandlingTests(HumanNameTestBase):

    # TODO: Seems "Andrews, M.D.", Andrews should be treated as a last name
    # but other suffixes like "George Jr." should be first names. Might be 
    # related to https://github.com/derek73/python-nameparser/issues/2
    @unittest.expectedFailure
    def test_assume_suffix_title_and_one_other_name_is_last_name(self):
        hn = HumanName("Andrews, M.D.")
        self.m(hn.suffix, "M.D.", hn)
        self.m(hn.last, "Andrews", hn)

    def test_first_name_is_not_prefix_if_only_two_parts(self):
        """When there are only two parts, don't join prefixes or conjunctions"""
        hn = HumanName("Van Nguyen")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)

    @unittest.expectedFailure
    def test_first_name_is_prefix_if_three_parts(self):
        """Not sure how to fix this without breaking Mr and Mrs"""
        hn = HumanName("Mr. Van Nguyen")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)
        

class HumanNameConjunctionTestCase(HumanNameTestBase):

    @unittest.expectedFailure
    def test_two_initials_conflict_with_conjunction(self):
        # Supporting this seems to screw up titles with periods in them like M.B.A.
        hn = HumanName('E.T. Smith')
        self.m(hn.first, "E.", hn)
        self.m(hn.middle, "T.", hn)
        self.m(hn.last, "Smith", hn)

    @unittest.expectedFailure
    def test_conjunction_in_an_address_with_a_first_name_title(self):
        hn = HumanName("Her Majesty Queen Elizabeth")
        self.m(hn.title, "Her Majesty Queen", hn)
        # if you want to be technical, Queen is in FIRST_NAME_TITLES
        self.m(hn.first, "Elizabeth", hn)

class ConstantsCustomization(HumanNameTestBase):

    def test_add_title(self):
        hn = HumanName("Te Awanui-a-Rangi Black", constants=None)
        hn.C.titles.add('te')
        hn.parse_full_name()
        self.m(hn.title,"Te", hn)
        self.m(hn.first,"Awanui-a-Rangi", hn)
        self.m(hn.last,"Black", hn)
    
    def test_remove_title(self):
        hn = HumanName("Hon Solo", constants=None)
        hn.C.titles.remove('hon')
        hn.parse_full_name()
        self.m(hn.first,"Hon", hn)
        self.m(hn.last,"Solo", hn)
    
    def test_add_multiple_arguments(self):
        hn = HumanName("Assoc Dean of Chemistry Robert Johns", constants=None)
        hn.C.titles.add('dean', 'Chemistry')
        hn.parse_full_name()
        self.m(hn.title,"Assoc Dean of Chemistry", hn)
        self.m(hn.first,"Robert", hn)
        self.m(hn.last,"Johns", hn)

    def test_instances_can_have_own_constants(self):
        hn = HumanName("", None)
        hn2 = HumanName("")
        hn.C.titles.remove('hon')
        self.assertEqual('hon' in hn.C.titles, False)
        self.assertEqual(hn.has_own_config, True)
        self.assertEqual('hon' in hn2.C.titles, True)
        self.assertEqual(hn2.has_own_config, False)
    
    
    def test_can_change_global_constants(self):
        hn = HumanName("")
        hn2 = HumanName("")
        hn.C.titles.remove('hon')
        self.assertEqual('hon' in hn.C.titles, False)
        self.assertEqual('hon' in hn2.C.titles, False)
        self.assertEqual(hn.has_own_config, False)
        self.assertEqual(hn2.has_own_config, False)
        # clean up so we don't mess up other tests
        hn.C.titles.add('hon')
    
    def test_remove_multiple_arguments(self):
        hn = HumanName("Ms Hon Solo", constants=None)
        hn.C.titles.remove('hon', 'ms')
        hn.parse_full_name()
        self.m(hn.first,"Ms", hn)
        self.m(hn.middle,"Hon", hn)
        self.m(hn.last,"Solo", hn)

    def test_chain_multiple_arguments(self):
        hn = HumanName("Dean Ms Hon Solo", constants=None)
        hn.C.titles.remove('hon', 'ms').add('dean')
        hn.parse_full_name()
        self.m(hn.title,"Dean", hn)
        self.m(hn.first,"Ms", hn)
        self.m(hn.middle,"Hon", hn)
        self.m(hn.last,"Solo", hn)

    def test_empty_attribute_default(self):
        from nameparser.config import CONSTANTS
        _orig = CONSTANTS.empty_attribute_default
        CONSTANTS.empty_attribute_default = None
        hn = HumanName("")
        self.m(hn.title, None, hn)
        self.m(hn.first, None, hn)
        self.m(hn.middle, None, hn)
        self.m(hn.last, None, hn)
        self.m(hn.suffix, None, hn)
        self.m(hn.nickname, None, hn)
        CONSTANTS.empty_attribute_default = _orig

    def test_empty_attribute_on_instance(self):
        hn = HumanName("", None)
        hn.C.empty_attribute_default = None
        self.m(hn.title, None, hn)
        self.m(hn.first, None, hn)
        self.m(hn.middle, None, hn)
        self.m(hn.last, None, hn)
        self.m(hn.suffix, None, hn)
        self.m(hn.nickname, None, hn)

    def test_none_empty_attribute_string_formatting(self):
        hn = HumanName("", None)
        hn.C.empty_attribute_default = None
        self.assertEqual('', str(hn), hn)

class HumanNameNicknameTestCase(HumanNameTestBase):

# https://code.google.com/p/python-nameparser/issues/detail?id=33





    # it would be hard to support this without breaking some of the
    # other examples with single quotes in the names.
    @unittest.expectedFailure
    def test_nickname_in_single_quotes(self):
        hn = HumanName("Benjamin 'Ben' Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)









    #http://code.google.com/p/python-nameparser/issues/detail?id=17
    def test_parenthesis_are_removed(self):
        hn = HumanName("John Jones (Google Docs)")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)
        # not testing the nicknames because we don't actually care
        # about Google Docs.

class SuffixesTestCase(HumanNameTestBase):

    def test_two_suffixes(self):
        hn = HumanName("Kenneth Clarke QC MP")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        # NOTE: this adds a comma when the orginal format did not have one. 
        # not ideal but at least its in the right bucket
        self.m(hn.suffix, "QC, MP", hn)

    def test_two_suffixes_lastname_comma_format(self):
        hn = HumanName("Washington Jr. MD, Franklin")
        self.m(hn.first, "Franklin", hn)
        self.m(hn.last, "Washington", hn)
        # NOTE: this adds a comma when the orginal format did not have one. 
        self.m(hn.suffix, "Jr., MD", hn)

    @unittest.expectedFailure
    def test_phd_with_erroneous_space(self):
        hn = HumanName("John Smith, Ph. D.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "Ph. D.", hn)

    # TODO: handle conjunctions in last names followed by first names clashing with suffixes
    @unittest.expectedFailure
    def test_potential_suffix_that_is_also_first_name_comma_with_conjunction(self):
        hn = HumanName("De la Vina, Bart")
        self.m(hn.first, "Bart", hn)
        self.m(hn.last, "De la Vina", hn)

    # https://github.com/derek73/python-nameparser/issues/27
    @unittest.expectedFailure
    def test_king(self):
        hn = HumanName("Dr King Jr")
        self.m(hn.title, "Dr", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr", hn)

class TitleTestCase(HumanNameTestBase):

    # TODO: fix handling of U.S.
    @unittest.expectedFailure
    def test_chained_title_first_name_initial(self):
        hn = HumanName("U.S. District Judge Marc Thomas Treadwell")
        self.m(hn.title, "U.S. District Judge", hn)
        self.m(hn.first, "Marc", hn)
        self.m(hn.middle, "Thomas", hn)
        self.m(hn.last, "Treadwell", hn)

    @unittest.expectedFailure
    def test_title_multiple_titles_with_apostrophe_s(self):
        hn = HumanName("The Right Hon. the President of the Queen's Bench Division")
        self.m(hn.title, "The Right Hon. the President of the Queen's Bench Division", hn)

    def test_initials_also_suffix(self):
        hn = HumanName("Smith, J.R.")
        self.m(hn.first, "J.R.", hn)
        # self.m(hn.middle, "R.", hn)
        self.m(hn.last, "Smith", hn)

    # 'ben' is removed from PREFIXES in v0.2.5
    # this test could re-enable this test if we decide to support 'ben' as a prefix
    @unittest.expectedFailure
    def test_ben_as_conjunction(self):
        hn = HumanName("Ahmad ben Husain")
        self.m(hn.first,"Ahmad", hn)
        self.m(hn.last,"ben Husain", hn)

class HumanNameCapitalizationTestCase(HumanNameTestBase):
    def test_capitalization_exception_for_III(self):
        hn = HumanName('juan q. xavier velasquez y garcia iii')
        hn.capitalize()
        self.m(str(hn), 'Juan Q. Xavier Velasquez y Garcia III', hn)

    # FIXME: this test does not pass due to a known issue
    # http://code.google.com/p/python-nameparser/issues/detail?id=22
    @unittest.expectedFailure
    def test_capitalization_exception_for_already_capitalized_III_KNOWN_FAILURE(self):
        hn = HumanName('juan garcia III')
        hn.capitalize()
        self.m(str(hn), 'Juan Garcia III', hn)

    def test_capitalize_title(self):
        hn = HumanName('lt. gen. john a. kenneth doe iv')
        hn.capitalize()
        self.m(str(hn), 'Lt. Gen. John A. Kenneth Doe IV', hn)

    def test_capitalize_title_to_lower(self):
        hn = HumanName('LT. GEN. JOHN A. KENNETH DOE IV')
        hn.capitalize()
        self.m(str(hn), 'Lt. Gen. John A. Kenneth Doe IV', hn)

    # Capitalization with M(a)c and hyphenated names
    def test_capitalization_with_Mac_as_hyphenated_names(self):
        hn = HumanName('donovan mcnabb-smith')
        hn.capitalize()
        self.m(str(hn), 'Donovan McNabb-Smith', hn)

    def test_capitization_middle_initial_is_also_a_conjunction(self):
        hn = HumanName('scott e. werner')
        hn.capitalize()
        self.m(str(hn), 'Scott E. Werner', hn)

    # Leaving already-capitalized names alone
    def test_no_change_to_mixed_chase(self):
        hn = HumanName('Shirley Maclaine')
        hn.capitalize()
        self.m(str(hn), 'Shirley Maclaine', hn)

    def test_force_capitalization(self):
        hn = HumanName('Shirley Maclaine')
        hn.capitalize(force=True)
        self.m(str(hn), 'Shirley MacLaine', hn)

    def test_capitalize_diacritics(self):
        hn = HumanName('matthëus schmidt')
        hn.capitalize()
        self.m(u(hn), 'Matthëus Schmidt', hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=15
    def test_downcasing_mac(self):
        hn = HumanName('RONALD MACDONALD')
        hn.capitalize()
        self.m(str(hn), 'Ronald MacDonald', hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=23
    def test_downcasing_mc(self):
        hn = HumanName('RONALD MCDONALD')
        hn.capitalize()
        self.m(str(hn), 'Ronald McDonald', hn)


class HumanNameOutputFormatTests(HumanNameTestBase):
    
    def test_formatting_init_argument(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)", 
            string_format = "TEST1")
        self.assertEqual(u(hn), "TEST1")

    def test_formatting_constants_attribute(self):
        from nameparser.config import CONSTANTS
        _orig = CONSTANTS.string_format
        CONSTANTS.string_format = "TEST2"
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        self.assertEqual(u(hn), "TEST2")
        CONSTANTS.string_format = _orig

    def test_quote_nickname_formating(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.string_format = "{last}, {title} {first} {middle}, {suffix} '{nickname}'"
        self.assertEqual(u(hn), "Doe, Rev John A. Kenneth, III 'Kenny'")

    def test_formating_removing_keys_from_format_string(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.string_format = "{last}, {title} {first} {middle}, {suffix}"
        self.assertEqual(u(hn), "Doe, Rev John A. Kenneth, III")
        hn.string_format = "{last}, {title} {first} {middle}"
        self.assertEqual(u(hn), "Doe, Rev John A. Kenneth")
        hn.string_format = "{last}, {first} {middle}"
        self.assertEqual(u(hn), "Doe, John A. Kenneth")
        hn.string_format = "{last}, {first}"
        self.assertEqual(u(hn), "Doe, John")
        hn.string_format = "{first} {last}"
        self.assertEqual(u(hn), "John Doe")

    def test_formating_removing_pieces_from_name_buckets(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.string_format = "{title} {first} {middle} {last} {suffix}"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")
        hn.middle=''
        self.assertEqual(u(hn), "Rev John Doe III")
        hn.suffix=''
        self.assertEqual(u(hn), "Rev John Doe")
        hn.title=''
        self.assertEqual(u(hn), "John Doe")

    def test_formating_of_nicknames_with_parenthesis(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} ({nickname})"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III (Kenny)")
        hn.nickname=''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_single_quotes(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.nickname=''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_double_quotes(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} \"{nickname}\""
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III \"Kenny\"")
        hn.nickname=''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_in_middle(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} ({nickname}) {middle} {last} {suffix}"
        self.assertEqual(u(hn), "Rev John (Kenny) A. Kenneth Doe III")
        hn.nickname=''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")
    
    def test_remove_emojis(self):
        hn = HumanName("Sam Smith 😊")
        self.m(hn.first,"Sam", hn)
        self.m(hn.last,"Smith", hn)
        self.assertEqual(u(hn), "Sam Smith")

    def test_keep_non_emojis(self):
        hn = HumanName("∫≜⩕ Smith 😊")
        self.m(hn.first,"∫≜⩕", hn)
        self.m(hn.last,"Smith", hn)
        self.assertEqual(u(hn), "∫≜⩕ Smith")

    def test_keep_emojis(self):
        from nameparser.config import Constants
        constants = Constants()
        constants.regexes.emoji = False
        hn = HumanName("∫≜⩕ Smith😊", constants)
        self.m(hn.first,"∫≜⩕", hn)
        self.m(hn.last,"Smith😊", hn)
        self.assertEqual(u(hn), "∫≜⩕ Smith😊")
        # test cleanup

TEST_NAMES = (
    "John Doe",
    "John Doe, Jr.",
    "John Doe III",
    "Doe, John",
    "Doe, John, Jr.",
    "Doe, John III",
    "John A. Doe",
    "John A. Doe, Jr.",
    "John A. Doe III",
    "Doe, John A.",
    "Doe, John A., Jr.",
    "Doe, John A. III",
    "John A. Kenneth Doe",
    "John A. Kenneth Doe, Jr.",
    "John A. Kenneth Doe III",
    "Doe, John A. Kenneth",
    "Doe, John A. Kenneth, Jr.",
    "Doe, John A. Kenneth III",
    "Dr. John Doe",
    "Dr. John Doe, Jr.",
    "Dr. John Doe III",
    "Doe, Dr. John",
    "Doe, Dr. John, Jr.",
    "Doe, Dr. John III",
    "Dr. John A. Doe",
    "Dr. John A. Doe, Jr.",
    "Dr. John A. Doe III",
    "Doe, Dr. John A.",
    "Doe, Dr. John A. Jr.",
    "Doe, Dr. John A. III",
    "Dr. John A. Kenneth Doe",
    "Dr. John A. Kenneth Doe, Jr.",
    "Dr. John A. Kenneth Doe III",
    "Doe, Dr. John A. Kenneth",
    "Doe, Dr. John A. Kenneth Jr.",
    "Doe, Dr. John A. Kenneth III",
    "Juan de la Vega",
    "Juan de la Vega, Jr.",
    "Juan de la Vega III",
    "de la Vega, Juan",
    "de la Vega, Juan, Jr.",
    "de la Vega, Juan III",
    "Juan Velasquez y Garcia",
    "Juan Velasquez y Garcia, Jr.",
    "Juan Velasquez y Garcia III",
    "Velasquez y Garcia, Juan",
    "Velasquez y Garcia, Juan, Jr.",
    "Velasquez y Garcia, Juan III",
    "Dr. Juan de la Vega",
    "Dr. Juan de la Vega, Jr.",
    "Dr. Juan de la Vega III",
    "de la Vega, Dr. Juan",
    "de la Vega, Dr. Juan, Jr.",
    "de la Vega, Dr. Juan III",
    "Dr. Juan Velasquez y Garcia",
    "Dr. Juan Velasquez y Garcia, Jr.",
    "Dr. Juan Velasquez y Garcia III",
    "Velasquez y Garcia, Dr. Juan",
    "Velasquez y Garcia, Dr. Juan, Jr.",
    "Velasquez y Garcia, Dr. Juan III",
    "Juan Q. de la Vega",
    "Juan Q. de la Vega, Jr.",
    "Juan Q. de la Vega III",
    "de la Vega, Juan Q.",
    "de la Vega, Juan Q., Jr.",
    "de la Vega, Juan Q. III",
    "Juan Q. Velasquez y Garcia",
    "Juan Q. Velasquez y Garcia, Jr.",
    "Juan Q. Velasquez y Garcia III",
    "Velasquez y Garcia, Juan Q.",
    "Velasquez y Garcia, Juan Q., Jr.",
    "Velasquez y Garcia, Juan Q. III",
    "Dr. Juan Q. de la Vega",
    "Dr. Juan Q. de la Vega, Jr.",
    "Dr. Juan Q. de la Vega III",
    "de la Vega, Dr. Juan Q.",
    "de la Vega, Dr. Juan Q., Jr.",
    "de la Vega, Dr. Juan Q. III",
    "Dr. Juan Q. Velasquez y Garcia",
    "Dr. Juan Q. Velasquez y Garcia, Jr.",
    "Dr. Juan Q. Velasquez y Garcia III",
    "Velasquez y Garcia, Dr. Juan Q.",
    "Velasquez y Garcia, Dr. Juan Q., Jr.",
    "Velasquez y Garcia, Dr. Juan Q. III",
    "Juan Q. Xavier de la Vega",
    "Juan Q. Xavier de la Vega, Jr.",
    "Juan Q. Xavier de la Vega III",
    "de la Vega, Juan Q. Xavier",
    "de la Vega, Juan Q. Xavier, Jr.",
    "de la Vega, Juan Q. Xavier III",
    "Juan Q. Xavier Velasquez y Garcia",
    "Juan Q. Xavier Velasquez y Garcia, Jr.",
    "Juan Q. Xavier Velasquez y Garcia III",
    "Velasquez y Garcia, Juan Q. Xavier",
    "Velasquez y Garcia, Juan Q. Xavier, Jr.",
    "Velasquez y Garcia, Juan Q. Xavier III",
    "Dr. Juan Q. Xavier de la Vega",
    "Dr. Juan Q. Xavier de la Vega, Jr.",
    "Dr. Juan Q. Xavier de la Vega III",
    "de la Vega, Dr. Juan Q. Xavier",
    "de la Vega, Dr. Juan Q. Xavier, Jr.",
    "de la Vega, Dr. Juan Q. Xavier III",
    "Dr. Juan Q. Xavier Velasquez y Garcia",
    "Dr. Juan Q. Xavier Velasquez y Garcia, Jr.",
    "Dr. Juan Q. Xavier Velasquez y Garcia III",
    "Velasquez y Garcia, Dr. Juan Q. Xavier",
    "Velasquez y Garcia, Dr. Juan Q. Xavier, Jr.",
    "Velasquez y Garcia, Dr. Juan Q. Xavier III",
    "John Doe, CLU, CFP, LUTC",
    "John P. Doe, CLU, CFP, LUTC",
    "Dr. John P. Doe-Ray, CLU, CFP, LUTC",
    "Doe-Ray, Dr. John P., CLU, CFP, LUTC",
    "Hon. Barrington P. Doe-Ray, Jr.",
    "Doe-Ray, Hon. Barrington P. Jr.",
    "Doe-Ray, Hon. Barrington P. Jr., CFP, LUTC",
    "Jose Aznar y Lopez",
    "John E Smith",
    "John e Smith",
    "John and Jane Smith",
    "Rev. John A. Kenneth Doe",
    "Donovan McNabb-Smith",
    "Rev John A. Kenneth Doe",
    "Doe, Rev. John A. Jr.",
    "Buca di Beppo",
    "Lt. Gen. John A. Kenneth Doe, Jr.",
    "Doe, Lt. Gen. John A. Kenneth IV",
    "Lt. Gen. John A. Kenneth Doe IV",
    'Mr. and Mrs. John Smith',
    'John Jones (Google Docs)',
    'john e jones',
    'john e jones, III',
    'jones, john e',
    'E.T. Smith',
    'E.T. Smith, II',
    'Smith, E.T., Jr.',
    'A.B. Vajpayee',
    'Rt. Hon. Paul E. Mary',
    'Maid Marion',
    'Amy E. Maid',
    'Jane Doctor',
    'Doctor, Jane E.',
    'dr. ben alex johnson III',
    'Lord of the Universe and Supreme King of the World Lisa Simpson',
    'Benjamin (Ben) Franklin',
    'Benjamin "Ben" Franklin',
    "Brian O'connor",
    "Sir Gerald",
    "Magistrate Judge John F. Forster, Jr",
    # "Magistrate Judge Joaquin V.E. Manibusan, Jr", Intials seem to mess this up
    "Magistrate-Judge Elizabeth Todd Campbell",
    "Mag-Judge Harwell G Davis, III",
    "Mag. Judge Byron G. Cudmore",
    "Chief Judge J. Leon Holmes",
    "Chief Judge Sharon Lovelace Blackburn",
    "Judge James M. Moody",
    "Judge G. Thomas Eisele",
    # "Judge Callie V. S. Granade",
    "Judge C Lynwood Smith, Jr",
    "Senior Judge Charles R. Butler, Jr",
    "Senior Judge Harold D. Vietor",
    "Senior Judge Virgil Pittman",
    "Honorable Terry F. Moorer",
    "Honorable W. Harold Albritton, III",
    "Honorable Judge W. Harold Albritton, III",
    "Honorable Judge Terry F. Moorer",
    "Honorable Judge Susan Russ Walker",
    "Hon. Marian W. Payson",
    "Hon. Charles J. Siragusa",
    "US Magistrate Judge T Michael Putnam",
    "Designated Judge David A. Ezra",
    "Sr US District Judge Richard G Kopf",
    "U.S. District Judge Marc Thomas Treadwell")
    

class HumanNameVariationTests(HumanNameTestBase):
    # test automated variations of names in TEST_NAMES.
    # Helps test that the 3 code trees work the same

    TEST_NAMES = TEST_NAMES

    def test_variations_of_TEST_NAMES(self):
        for name in self.TEST_NAMES:
            hn = HumanName(name)
            if len(hn.suffix_list) > 1:
                hn = HumanName("{title} {first} {middle} {last} {suffix}".format(**hn.as_dict()).split(',')[0])
            hn.C.empty_attribute_default = '' # format strings below require empty string
            hn_dict = hn.as_dict()
            attrs = [
                'title',
                'first',
                'middle',
                'last',
                'suffix',
                'nickname',
            ]
            nocomma = HumanName("{title} {first} {middle} {last} {suffix}".format(**hn_dict))
            lastnamecomma = HumanName("{last}, {title} {first} {middle} {suffix}".format(**hn_dict))
            if hn.suffix:
                suffixcomma = HumanName("{title} {first} {middle} {last}, {suffix}".format(**hn_dict))
            if hn.nickname:
                nocomma = HumanName("{title} {first} {middle} {last} {suffix} ({nickname})".format(**hn_dict))
                lastnamecomma = HumanName("{last}, {title} {first} {middle} {suffix} ({nickname})".format(**hn_dict))
                if hn.suffix:
                    suffixcomma = HumanName("{title} {first} {middle} {last}, {suffix} ({nickname})".format(**hn_dict))
            for attr in hn._members:
                self.m(getattr(hn, attr), getattr(nocomma, attr), hn)
                self.m(getattr(hn, attr), getattr(lastnamecomma, attr), hn)
                if hn.suffix:
                    self.m(getattr(hn, attr), getattr(suffixcomma, attr), hn)


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        log.setLevel(logging.ERROR)
        log.addHandler(logging.StreamHandler())
        name = sys.argv[1]
        hn = HumanName(name, encoding=sys.stdout.encoding)
        print((repr(hn)))
        hn.capitalize()
        print((repr(hn)))
    else:
        print("-"*80)
        print("Running tests")
        unittest.main(exit=False)
        print("-"*80)
        print("Running tests with empty_attribute_default = None")
        from nameparser.config import CONSTANTS
        CONSTANTS.empty_attribute_default = None
        unittest.main()
