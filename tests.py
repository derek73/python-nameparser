# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import unittest
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
import re
try:
    import dill
except ImportError:
    dill = False

from nameparser import HumanName
from nameparser.util import u
from nameparser.config import Constants, TupleManager

log = logging.getLogger('HumanName')

try:
    unittest.expectedFailure
except AttributeError:
    # Python 2.6 backport
    import unittest2 as unittest


class HumanNameTestBase(unittest.TestCase):
    def m(self, actual, expected, hn):
        """assertEqual with a better message and awareness of hn.C.empty_attribute_default"""
        expected = expected or hn.C.empty_attribute_default
        try:
            self.assertEqual(actual, expected, "'%s' != '%s' for '%s'\n%r" % (
                actual,
                expected,
                hn.original,
                hn
            ))
        except UnicodeDecodeError:
            self.assertEqual(actual, expected)


class HumanNamePythonTests(HumanNameTestBase):

    def test_utf8(self):
        hn = HumanName("de la Véña, Jüan")
        self.m(hn.first, "Jüan", hn)
        self.m(hn.last, "de la Véña", hn)

    def test_string_output(self):
        hn = HumanName("de la Véña, Jüan")

    def test_escaped_utf8_bytes(self):
        hn = HumanName(b'B\xc3\xb6ck, Gerald')
        self.m(hn.first, "Gerald", hn)
        self.m(hn.last, "Böck", hn)

    def test_len(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(len(hn), 5, hn)
        hn = HumanName("John Doe")
        self.m(len(hn), 2, hn)

    @unittest.skipUnless(dill, "requires python-dill module to test pickling")
    def test_config_pickle(self):
        constants = Constants()
        self.assertTrue(dill.pickles(constants))

    @unittest.skipUnless(dill, "requires python-dill module to test pickling")
    def test_name_instance_pickle(self):
        hn = HumanName("Title First Middle Middle Last, Jr.")
        self.assertTrue(dill.pickles(hn))

    def test_comparison(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1 == hn2)
        self.assertTrue(hn1 is not hn2)
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

    def test_get_full_name_attribute_references_internal_lists(self):
        hn = HumanName("John Williams")
        hn.first_list = ["Larry"]
        self.m(hn.full_name, "Larry Williams", hn)

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
            hn.suffix = {"test": "test"}

    def test_assign_list_to_attribute(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        hn.title = ["test1", "test2"]
        self.m(hn.title, "test1 test2", hn)
        hn.first = ["test3", "test4"]
        self.m(hn.first, "test3 test4", hn)
        hn.middle = ["test5", "test6", "test7"]
        self.m(hn.middle, "test5 test6 test7", hn)
        hn.last = ["test8", "test9", "test10"]
        self.m(hn.last, "test8 test9 test10", hn)
        hn.suffix = ['test']
        self.m(hn.suffix, "test", hn)

    def test_comparison_case_insensitive(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1 == hn2)
        self.assertTrue(hn1 is not hn2)
        self.assertTrue(hn1 == "Dr. John P. Doe-ray clu, CFP, LUTC")

    def test_slice(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(list(hn), ['Dr.', 'John', 'P.', 'Doe-Ray', 'CLU, CFP, LUTC'], hn)
        self.m(hn[1:], ['John', 'P.', 'Doe-Ray', 'CLU, CFP, LUTC', hn.C.empty_attribute_default], hn)
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
        hn['last'] = ['test', 'test2']
        self.m(hn['last'], "test test2", hn)
        with self.assertRaises(TypeError):
            hn["suffix"] = [['test']]
        with self.assertRaises(TypeError):
            hn["suffix"] = {"test": "test"}

    def test_conjunction_names(self):
        hn = HumanName("johnny y")
        self.m(hn.first, "johnny", hn)
        self.m(hn.last, "y", hn)

    def test_prefix_names(self):
        hn = HumanName("vai la")
        self.m(hn.first, "vai", hn)
        self.m(hn.last, "la", hn)

    def test_blank_name(self):
        hn = HumanName()
        self.m(hn.first, "", hn)
        self.m(hn.last, "", hn)

    def test_surnames_list_attribute(self):
        hn = HumanName("John Edgar Casey Williams III")
        self.m(hn.surnames_list, ["Edgar", "Casey", "Williams"], hn)

    def test_surnames_attribute(self):
        hn = HumanName("John Edgar Casey Williams III")
        self.m(hn.surnames, "Edgar Casey Williams", hn)

    def test_is_prefix_with_list(self):
        hn = HumanName()
        items = ['firstname', 'lastname', 'del']
        self.assertTrue(hn.is_prefix(items))
        self.assertTrue(hn.is_prefix(items[1:]))

    def test_is_conjunction_with_list(self):
        hn = HumanName()
        items = ['firstname', 'lastname', 'and']
        self.assertTrue(hn.is_conjunction(items))
        self.assertTrue(hn.is_conjunction(items[1:]))

    def test_override_constants(self):
        C = Constants()
        hn = HumanName(constants=C)
        self.assertTrue(hn.C is C)

    def test_override_regex(self):
        var = TupleManager([("spaces", re.compile(r"\s+", re.U)),])
        C = Constants(regexes=var)
        hn = HumanName(constants=C)
        self.assertTrue(hn.C.regexes == var)

    def test_override_titles(self):
        var = ["abc","def"]
        C = Constants(titles=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.titles) == sorted(var))

    def test_override_first_name_titles(self):
        var = ["abc","def"]
        C = Constants(first_name_titles=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.first_name_titles) == sorted(var))

    def test_override_prefixes(self):
        var = ["abc","def"]
        C = Constants(prefixes=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.prefixes) == sorted(var))

    def test_override_suffix_acronyms(self):
        var = ["abc","def"]
        C = Constants(suffix_acronyms=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.suffix_acronyms) == sorted(var))

    def test_override_suffix_not_acronyms(self):
        var = ["abc","def"]
        C = Constants(suffix_not_acronyms=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.suffix_not_acronyms) == sorted(var))

    def test_override_conjunctions(self):
        var = ["abc","def"]
        C = Constants(conjunctions=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.conjunctions) == sorted(var))

    def test_override_capitalization_exceptions(self):
        var = TupleManager([("spaces", re.compile(r"\s+", re.U)),])
        C = Constants(capitalization_exceptions=var)
        hn = HumanName(constants=C)
        self.assertTrue(hn.C.capitalization_exceptions == var)


class FirstNameHandlingTests(HumanNameTestBase):
    def test_first_name(self):
        hn = HumanName("Andrew")
        self.m(hn.first, "Andrew", hn)

    def test_assume_title_and_one_other_name_is_last_name(self):
        hn = HumanName("Rev Andrews")
        self.m(hn.title, "Rev", hn)
        self.m(hn.last, "Andrews", hn)

    # TODO: Seems "Andrews, M.D.", Andrews should be treated as a last name
    # but other suffixes like "George Jr." should be first names. Might be
    # related to https://github.com/derek73/python-nameparser/issues/2
    @unittest.expectedFailure
    def test_assume_suffix_title_and_one_other_name_is_last_name(self):
        hn = HumanName("Andrews, M.D.")
        self.m(hn.suffix, "M.D.", hn)
        self.m(hn.last, "Andrews", hn)

    def test_suffix_in_lastname_part_of_lastname_comma_format(self):
        hn = HumanName("Smith Jr., John")
        self.m(hn.last, "Smith", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_sir_exception_to_first_name_rule(self):
        hn = HumanName("Sir Gerald")
        self.m(hn.title, "Sir", hn)
        self.m(hn.first, "Gerald", hn)

    def test_king_exception_to_first_name_rule(self):
        hn = HumanName("King Henry")
        self.m(hn.title, "King", hn)
        self.m(hn.first, "Henry", hn)

    def test_queen_exception_to_first_name_rule(self):
        hn = HumanName("Queen Elizabeth")
        self.m(hn.title, "Queen", hn)
        self.m(hn.first, "Elizabeth", hn)

    def test_dame_exception_to_first_name_rule(self):
        hn = HumanName("Dame Mary")
        self.m(hn.title, "Dame", hn)
        self.m(hn.first, "Mary", hn)

    def test_first_name_is_not_prefix_if_only_two_parts(self):
        """When there are only two parts, don't join prefixes or conjunctions"""
        hn = HumanName("Van Nguyen")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)

    def test_first_name_is_not_prefix_if_only_two_parts_comma(self):
        hn = HumanName("Nguyen, Van")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)

    @unittest.expectedFailure
    def test_first_name_is_prefix_if_three_parts(self):
        """Not sure how to fix this without breaking Mr and Mrs"""
        hn = HumanName("Mr. Van Nguyen")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Nguyen", hn)


class HumanNameBruteForceTests(HumanNameTestBase):

    def test1(self):
        hn = HumanName("John Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test2(self):
        hn = HumanName("John Doe, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test3(self):
        hn = HumanName("John Doe III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test4(self):
        hn = HumanName("Doe, John")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test5(self):
        hn = HumanName("Doe, John, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test6(self):
        hn = HumanName("Doe, John III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test7(self):
        hn = HumanName("John A. Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test8(self):
        hn = HumanName("John A. Doe, Jr")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr", hn)

    def test9(self):
        hn = HumanName("John A. Doe III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "III", hn)

    def test10(self):
        hn = HumanName("Doe, John A.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test11(self):
        hn = HumanName("Doe, John A., Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test12(self):
        hn = HumanName("Doe, John A., III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "III", hn)

    def test13(self):
        hn = HumanName("John A. Kenneth Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)

    def test14(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test15(self):
        hn = HumanName("John A. Kenneth Doe III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "III", hn)

    def test16(self):
        hn = HumanName("Doe, John. A. Kenneth")
        self.m(hn.first, "John.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)

    def test17(self):
        hn = HumanName("Doe, John. A. Kenneth, Jr.")
        self.m(hn.first, "John.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test18(self):
        hn = HumanName("Doe, John. A. Kenneth III")
        self.m(hn.first, "John.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "III", hn)

    def test19(self):
        hn = HumanName("Dr. John Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.title, "Dr.", hn)

    def test20(self):
        hn = HumanName("Dr. John Doe, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test21(self):
        hn = HumanName("Dr. John Doe III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test22(self):
        hn = HumanName("Doe, Dr. John")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test23(self):
        hn = HumanName("Doe, Dr. John, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test24(self):
        hn = HumanName("Doe, Dr. John III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test25(self):
        hn = HumanName("Dr. John A. Doe")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test26(self):
        hn = HumanName("Dr. John A. Doe, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test27(self):
        hn = HumanName("Dr. John A. Doe III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "III", hn)

    def test28(self):
        hn = HumanName("Doe, Dr. John A.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test29(self):
        hn = HumanName("Doe, Dr. John A. Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test30(self):
        hn = HumanName("Doe, Dr. John A. III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test31(self):
        hn = HumanName("Dr. John A. Kenneth Doe")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test32(self):
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test33(self):
        hn = HumanName("Al Arnold Gore, Jr.")
        self.m(hn.middle, "Arnold", hn)
        self.m(hn.first, "Al", hn)
        self.m(hn.last, "Gore", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test34(self):
        hn = HumanName("Dr. John A. Kenneth Doe III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test35(self):
        hn = HumanName("Doe, Dr. John A. Kenneth")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test36(self):
        hn = HumanName("Doe, Dr. John A. Kenneth Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test37(self):
        hn = HumanName("Doe, Dr. John A. Kenneth III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test38(self):
        hn = HumanName("Juan de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test39(self):
        hn = HumanName("Juan de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test40(self):
        hn = HumanName("Juan de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test41(self):
        hn = HumanName("de la Vega, Juan")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test42(self):
        hn = HumanName("de la Vega, Juan, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test43(self):
        hn = HumanName("de la Vega, Juan III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test44(self):
        hn = HumanName("Juan Velasquez y Garcia")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test45(self):
        hn = HumanName("Juan Velasquez y Garcia, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test46(self):
        hn = HumanName("Juan Velasquez y Garcia III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test47(self):
        hn = HumanName("Velasquez y Garcia, Juan")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test48(self):
        hn = HumanName("Velasquez y Garcia, Juan, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test49(self):
        hn = HumanName("Velasquez y Garcia, Juan III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test50(self):
        hn = HumanName("Dr. Juan de la Vega")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test51(self):
        hn = HumanName("Dr. Juan de la Vega, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test52(self):
        hn = HumanName("Dr. Juan de la Vega III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test53(self):
        hn = HumanName("de la Vega, Dr. Juan")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test54(self):
        hn = HumanName("de la Vega, Dr. Juan, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test55(self):
        hn = HumanName("de la Vega, Dr. Juan III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test56(self):
        hn = HumanName("Dr. Juan Velasquez y Garcia")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test57(self):
        hn = HumanName("Dr. Juan Velasquez y Garcia, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test58(self):
        hn = HumanName("Dr. Juan Velasquez y Garcia III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test59(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test60(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test61(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test62(self):
        hn = HumanName("Juan Q. de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test63(self):
        hn = HumanName("Juan Q. de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test64(self):
        hn = HumanName("Juan Q. de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test65(self):
        hn = HumanName("de la Vega, Juan Q.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test66(self):
        hn = HumanName("de la Vega, Juan Q., Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test67(self):
        hn = HumanName("de la Vega, Juan Q. III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "III", hn)

    def test68(self):
        hn = HumanName("Juan Q. Velasquez y Garcia")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test69(self):
        hn = HumanName("Juan Q. Velasquez y Garcia, Jr.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test70(self):
        hn = HumanName("Juan Q. Velasquez y Garcia III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test71(self):
        hn = HumanName("Velasquez y Garcia, Juan Q.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test72(self):
        hn = HumanName("Velasquez y Garcia, Juan Q., Jr.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test73(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test74(self):
        hn = HumanName("Dr. Juan Q. de la Vega")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test75(self):
        hn = HumanName("Dr. Juan Q. de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test76(self):
        hn = HumanName("Dr. Juan Q. de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.suffix, "III", hn)

    def test77(self):
        hn = HumanName("de la Vega, Dr. Juan Q.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)

    def test78(self):
        hn = HumanName("de la Vega, Dr. Juan Q., Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.title, "Dr.", hn)

    def test79(self):
        hn = HumanName("de la Vega, Dr. Juan Q. III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "III", hn)
        self.m(hn.title, "Dr.", hn)

    def test80(self):
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test81(self):
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test82(self):
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test83(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test84(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q., Jr.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test85(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test86(self):
        hn = HumanName("Juan Q. Xavier de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.last, "de la Vega", hn)

    def test87(self):
        hn = HumanName("Juan Q. Xavier de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test88(self):
        hn = HumanName("Juan Q. Xavier de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test89(self):
        hn = HumanName("de la Vega, Juan Q. Xavier")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.last, "de la Vega", hn)

    def test90(self):
        hn = HumanName("de la Vega, Juan Q. Xavier, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test91(self):
        hn = HumanName("de la Vega, Juan Q. Xavier III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test92(self):
        hn = HumanName("Dr. Juan Q. Xavier de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test93(self):
        hn = HumanName("Dr. Juan Q. Xavier de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test94(self):
        hn = HumanName("Dr. Juan Q. Xavier de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test95(self):
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier")
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.last, "de la Vega", hn)

    def test96(self):
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test97(self):
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test98(self):
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test99(self):
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test100(self):
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test101(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test102(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test103(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test104(self):
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test105(self):
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test106(self):
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test107(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test108(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test109(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test110(self):
        hn = HumanName("John Doe, CLU, CFP, LUTC")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test111(self):
        hn = HumanName("John P. Doe, CLU, CFP, LUTC")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test112(self):
        hn = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.last, "Doe-Ray", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test113(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe-Ray", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test115(self):
        hn = HumanName("Hon. Barrington P. Doe-Ray, Jr.")
        self.m(hn.title, "Hon.", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.first, "Barrington", hn)
        self.m(hn.last, "Doe-Ray", hn)

    def test116(self):
        hn = HumanName("Doe-Ray, Hon. Barrington P. Jr., CFP, LUTC")
        self.m(hn.title, "Hon.", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.first, "Barrington", hn)
        self.m(hn.last, "Doe-Ray", hn)
        self.m(hn.suffix, "Jr., CFP, LUTC", hn)

    def test117(self):
        hn = HumanName("Rt. Hon. Paul E. Mary")
        self.m(hn.title, "Rt. Hon.", hn)
        self.m(hn.first, "Paul", hn)
        self.m(hn.middle, "E.", hn)
        self.m(hn.last, "Mary", hn)

    def test119(self):
        hn = HumanName("Lord God Almighty")
        self.m(hn.title, "Lord", hn)
        self.m(hn.first, "God", hn)
        self.m(hn.last, "Almighty", hn)


class HumanNameConjunctionTestCase(HumanNameTestBase):
    # Last name with conjunction
    def test_last_name_with_conjunction(self):
        hn = HumanName('Jose Aznar y Lopez')
        self.m(hn.first, "Jose", hn)
        self.m(hn.last, "Aznar y Lopez", hn)

    def test_multiple_conjunctions(self):
        hn = HumanName("part1 of The part2 of the part3 and part4")
        self.m(hn.first, "part1 of The part2 of the part3 and part4", hn)

    def test_multiple_conjunctions2(self):
        hn = HumanName("part1 of and The part2 of the part3 And part4")
        self.m(hn.first, "part1 of and The part2 of the part3 And part4", hn)

    def test_ends_with_conjunction(self):
        hn = HumanName("Jon Dough and")
        self.m(hn.first, "Jon", hn)
        self.m(hn.last, "Dough and", hn)

    def test_ends_with_two_conjunctions(self):
        hn = HumanName("Jon Dough and of")
        self.m(hn.first, "Jon", hn)
        self.m(hn.last, "Dough and of", hn)

    def test_starts_with_conjunction(self):
        hn = HumanName("and Jon Dough")
        self.m(hn.first, "and Jon", hn)
        self.m(hn.last, "Dough", hn)

    def test_starts_with_two_conjunctions(self):
        hn = HumanName("the and Jon Dough")
        self.m(hn.first, "the and Jon", hn)
        self.m(hn.last, "Dough", hn)

    # Potential conjunction/prefix treated as initial (because uppercase)
    def test_uppercase_middle_initial_conflict_with_conjunction(self):
        hn = HumanName('John E Smith')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.last, "Smith", hn)

    def test_lowercase_middle_initial_with_period_conflict_with_conjunction(self):
        hn = HumanName('john e. smith')
        self.m(hn.first, "john", hn)
        self.m(hn.middle, "e.", hn)
        self.m(hn.last, "smith", hn)

    # The conjunction "e" can also be an initial
    def test_lowercase_first_initial_conflict_with_conjunction(self):
        hn = HumanName('e j smith')
        self.m(hn.first, "e", hn)
        self.m(hn.middle, "j", hn)
        self.m(hn.last, "smith", hn)

    def test_lowercase_middle_initial_conflict_with_conjunction(self):
        hn = HumanName('John e Smith')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)

    def test_lowercase_middle_initial_and_suffix_conflict_with_conjunction(self):
        hn = HumanName('John e Smith, III')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "III", hn)

    def test_lowercase_middle_initial_and_nocomma_suffix_conflict_with_conjunction(self):
        hn = HumanName('John e Smith III')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "III", hn)

    def test_lowercase_middle_initial_comma_lastname_and_suffix_conflict_with_conjunction(self):
        hn = HumanName('Smith, John e, III, Jr')
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "e", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "III, Jr", hn)

    @unittest.expectedFailure
    def test_two_initials_conflict_with_conjunction(self):
        # Supporting this seems to screw up titles with periods in them like M.B.A.
        hn = HumanName('E.T. Smith')
        self.m(hn.first, "E.", hn)
        self.m(hn.middle, "T.", hn)
        self.m(hn.last, "Smith", hn)

    def test_couples_names(self):
        hn = HumanName('John and Jane Smith')
        self.m(hn.first, "John and Jane", hn)
        self.m(hn.last, "Smith", hn)

    def test_couples_names_with_conjunction_lastname(self):
        hn = HumanName('John and Jane Aznar y Lopez')
        self.m(hn.first, "John and Jane", hn)
        self.m(hn.last, "Aznar y Lopez", hn)

    def test_couple_titles(self):
        hn = HumanName('Mr. and Mrs. John and Jane Smith')
        self.m(hn.title, "Mr. and Mrs.", hn)
        self.m(hn.first, "John and Jane", hn)
        self.m(hn.last, "Smith", hn)

    def test_title_with_three_part_name_last_initial_is_suffix_uppercase_no_period(self):
        hn = HumanName("King John Alexander V")
        self.m(hn.title, "King", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Alexander", hn)
        self.m(hn.suffix, "V", hn)

    def test_four_name_parts_with_suffix_that_could_be_initial_lowercase_no_period(self):
        hn = HumanName("larry james edward johnson v")
        self.m(hn.first, "larry", hn)
        self.m(hn.middle, "james edward", hn)
        self.m(hn.last, "johnson", hn)
        self.m(hn.suffix, "v", hn)

    def test_four_name_parts_with_suffix_that_could_be_initial_uppercase_no_period(self):
        hn = HumanName("Larry James Johnson I")
        self.m(hn.first, "Larry", hn)
        self.m(hn.middle, "James", hn)
        self.m(hn.last, "Johnson", hn)
        self.m(hn.suffix, "I", hn)

    def test_roman_numeral_initials(self):
        hn = HumanName("Larry V I")
        self.m(hn.first, "Larry", hn)
        self.m(hn.middle, "V", hn)
        self.m(hn.last, "I", hn)
        self.m(hn.suffix, "", hn)

    # tests for Rev. title (Reverend)
    def test124(self):
        hn = HumanName("Rev. John A. Kenneth Doe")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test125(self):
        hn = HumanName("Rev John A. Kenneth Doe")
        self.m(hn.title, "Rev", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test126(self):
        hn = HumanName("Doe, Rev. John A. Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test127(self):
        hn = HumanName("Buca di Beppo")
        self.m(hn.first, "Buca", hn)
        self.m(hn.last, "di Beppo", hn)

    def test_le_as_last_name(self):
        hn = HumanName("Yin Le")
        self.m(hn.first, "Yin", hn)
        self.m(hn.last, "Le", hn)

    def test_le_as_last_name_with_middle_initial(self):
        hn = HumanName("Yin a Le")
        self.m(hn.first, "Yin", hn)
        self.m(hn.middle, "a", hn)
        self.m(hn.last, "Le", hn)

    def test_conjunction_in_an_address_with_a_title(self):
        hn = HumanName("His Excellency Lord Duncan")
        self.m(hn.title, "His Excellency Lord", hn)
        self.m(hn.last, "Duncan", hn)

    @unittest.expectedFailure
    def test_conjunction_in_an_address_with_a_first_name_title(self):
        hn = HumanName("Her Majesty Queen Elizabeth")
        self.m(hn.title, "Her Majesty Queen", hn)
        # if you want to be technical, Queen is in FIRST_NAME_TITLES
        self.m(hn.first, "Elizabeth", hn)

    def test_name_is_conjunctions(self):
        hn = HumanName("e and e")
        self.m(hn.first, "e and e", hn)


class ConstantsCustomization(HumanNameTestBase):

    def test_add_title(self):
        hn = HumanName("Te Awanui-a-Rangi Black", constants=None)
        start_len = len(hn.C.titles)
        self.assertTrue(start_len > 0)
        hn.C.titles.add('te')
        self.assertEqual(start_len + 1, len(hn.C.titles))
        hn.parse_full_name()
        self.m(hn.title, "Te", hn)
        self.m(hn.first, "Awanui-a-Rangi", hn)
        self.m(hn.last, "Black", hn)

    def test_remove_title(self):
        hn = HumanName("Hon Solo", constants=None)
        start_len = len(hn.C.titles)
        self.assertTrue(start_len > 0)
        hn.C.titles.remove('hon')
        self.assertEqual(start_len - 1, len(hn.C.titles))
        hn.parse_full_name()
        self.m(hn.first, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_add_multiple_arguments(self):
        hn = HumanName("Assoc Dean of Chemistry Robert Johns", constants=None)
        hn.C.titles.add('dean', 'Chemistry')
        hn.parse_full_name()
        self.m(hn.title, "Assoc Dean of Chemistry", hn)
        self.m(hn.first, "Robert", hn)
        self.m(hn.last, "Johns", hn)

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
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_chain_multiple_arguments(self):
        hn = HumanName("Dean Ms Hon Solo", constants=None)
        hn.C.titles.remove('hon', 'ms').add('dean')
        hn.parse_full_name()
        self.m(hn.title, "Dean", hn)
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

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

    def test_add_constant_with_explicit_encoding(self):
        c = Constants()
        c.titles.add_with_encoding(b'b\351ck', encoding='latin_1')
        self.assertIn('béck', c.titles)


class NicknameTestCase(HumanNameTestBase):
    # https://code.google.com/p/python-nameparser/issues/detail?id=33
    def test_nickname_in_parenthesis(self):
        hn = HumanName("Benjamin (Ben) Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_two_word_nickname_in_parenthesis(self):
        hn = HumanName("Benjamin (Big Ben) Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_two_words_in_quotes(self):
        hn = HumanName('Benjamin "Big Ben" Franklin')
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Big Ben", hn)

    def test_nickname_in_parenthesis_with_comma(self):
        hn = HumanName("Franklin, Benjamin (Ben)")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_parenthesis_with_comma_and_suffix(self):
        hn = HumanName("Franklin, Benjamin (Ben), Jr.")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_single_quotes(self):
        hn = HumanName("Benjamin 'Ben' Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_nickname_in_double_quotes(self):
        hn = HumanName("Benjamin \"Ben\" Franklin")
        self.m(hn.first, "Benjamin", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.nickname, "Ben", hn)

    def test_single_quotes_on_first_name_not_treated_as_nickname(self):
        hn = HumanName("Brian Andrew O'connor")
        self.m(hn.first, "Brian", hn)
        self.m(hn.middle, "Andrew", hn)
        self.m(hn.last, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_both_name_not_treated_as_nickname(self):
        hn = HumanName("La'tanya O'connor")
        self.m(hn.first, "La'tanya", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "O'connor", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_on_end_of_last_name_not_treated_as_nickname(self):
        hn = HumanName("Mari' Aube'")
        self.m(hn.first, "Mari'", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Aube'", hn)
        self.m(hn.nickname, "", hn)

    def test_okina_inside_name_not_treated_as_nickname(self):
        hn = HumanName("Harrieta Keōpūolani Nāhiʻenaʻena")
        self.m(hn.first, "Harrieta", hn)
        self.m(hn.middle, "Keōpūolani", hn)
        self.m(hn.last, "Nāhiʻenaʻena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Hawaiian_example(self):
        hn = HumanName("Harietta Keopuolani Nahi'ena'ena")
        self.m(hn.first, "Harietta", hn)
        self.m(hn.middle, "Keopuolani", hn)
        self.m(hn.last, "Nahi'ena'ena", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Kenyan_example(self):
        hn = HumanName("Naomi Wambui Ng'ang'a")
        self.m(hn.first, "Naomi", hn)
        self.m(hn.middle, "Wambui", hn)
        self.m(hn.last, "Ng'ang'a", hn)
        self.m(hn.nickname, "", hn)

    def test_single_quotes_not_treated_as_nickname_Samoan_example(self):
        hn = HumanName("Va'apu'u Vitale")
        self.m(hn.first, "Va'apu'u", hn)
        self.m(hn.middle, "", hn)
        self.m(hn.last, "Vitale", hn)
        self.m(hn.nickname, "", hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=17
    def test_parenthesis_are_removed_from_name(self):
        hn = HumanName("John Jones (Unknown)")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)
        # not testing the nicknames because we don't actually care
        # about Google Docs here

    def test_duplicate_parenthesis_are_removed_from_name(self):
        hn = HumanName("John Jones (Google Docs), Jr. (Unknown)")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_nickname_and_last_name(self):
        hn = HumanName('"Rick" Edmonds')
        self.m(hn.first, "", hn)
        self.m(hn.last, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)

    @unittest.expectedFailure
    def test_nickname_and_last_name_with_title(self):
        hn = HumanName('Senator "Rick" Edmonds')
        self.m(hn.title, "Senator", hn)
        self.m(hn.first, "", hn)
        self.m(hn.last, "Edmonds", hn)
        self.m(hn.nickname, "Rick", hn)


# class MaidenNameTestCase(HumanNameTestBase):
#
#     def test_parenthesis_and_quotes_together(self):
#         hn = HumanName("Jennifer 'Jen' Jones (Duff)")
#         self.m(hn.first, "Jennifer", hn)
#         self.m(hn.last, "Jones", hn)
#         self.m(hn.nickname, "Jen", hn)
#         self.m(hn.maiden, "Duff", hn)
#
#     def test_maiden_name_with_nee(self):
#         # https://en.wiktionary.org/wiki/née
#         hn = HumanName("Mary Toogood nee Johnson")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_accented_nee(self):
#         # https://en.wiktionary.org/wiki/née
#         hn = HumanName("Mary Toogood née Johnson")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_nee_and_comma(self):
#         # https://en.wiktionary.org/wiki/née
#         hn = HumanName("Mary Toogood, née Johnson")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_nee_with_parenthesis(self):
#         hn = HumanName("Mary Toogood (nee Johnson)")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#
#     def test_maiden_name_with_parenthesis(self):
#         hn = HumanName("Mary Toogood (Johnson)")
#         self.m(hn.first, "Mary", hn)
#         self.m(hn.last, "Toogood", hn)
#         self.m(hn.maiden, "Johnson", hn)
#

class PrefixesTestCase(HumanNameTestBase):

    def test_prefix(self):
        hn = HumanName("Juan del Sur")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "del Sur", hn)

    def test_prefix_with_period(self):
        hn = HumanName("Jill St. John")
        self.m(hn.first, "Jill", hn)
        self.m(hn.last, "St. John", hn)

    def test_prefix_before_two_part_last_name(self):
        hn = HumanName("pennie von bergen wessels")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)

    def test_prefix_is_first_name(self):
        hn = HumanName("Van Johnson")
        self.m(hn.first, "Van", hn)
        self.m(hn.last, "Johnson", hn)

    def test_prefix_is_first_name_with_middle_name(self):
        hn = HumanName("Van Jeremy Johnson")
        self.m(hn.first, "Van", hn)
        self.m(hn.middle, "Jeremy", hn)
        self.m(hn.last, "Johnson", hn)

    def test_prefix_before_two_part_last_name_with_suffix(self):
        hn = HumanName("pennie von bergen wessels III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_prefix_before_two_part_last_name_with_acronym_suffix(self):
        hn = HumanName("pennie von bergen wessels M.D.")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "M.D.", hn)

    def test_two_part_last_name_with_suffix_comma(self):
        hn = HumanName("pennie von bergen wessels, III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_two_part_last_name_with_suffix(self):
        hn = HumanName("von bergen wessels, pennie III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "III", hn)

    def test_last_name_two_part_last_name_with_two_suffixes(self):
        hn = HumanName("von bergen wessels MD, pennie III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD, III", hn)

    def test_comma_two_part_last_name_with_acronym_suffix(self):
        hn = HumanName("von bergen wessels, pennie MD")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD", hn)

    def test_comma_two_part_last_name_with_suffix_in_first_part(self):
        # I'm kinda surprised this works, not really sure if this is a
        # realistic place for a suffix to be.
        hn = HumanName("von bergen wessels MD, pennie")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD", hn)

    def test_title_two_part_last_name_with_suffix_in_first_part(self):
        hn = HumanName("pennie von bergen wessels MD, III")
        self.m(hn.first, "pennie", hn)
        self.m(hn.last, "von bergen wessels", hn)
        self.m(hn.suffix, "MD, III", hn)

    def test_portuguese_dos(self):
        hn = HumanName("Rafael Sousa dos Anjos")
        self.m(hn.first, "Rafael", hn)
        self.m(hn.middle, "Sousa", hn)
        self.m(hn.last, "dos Anjos", hn)

    def test_portuguese_prefixes(self):
        hn = HumanName("Joao da Silva do Amaral de Souza")
        self.m(hn.first, "Joao", hn)
        self.m(hn.middle, "da Silva do Amaral", hn)
        self.m(hn.last, "de Souza", hn)

    def test_three_conjunctions(self):
        hn = HumanName("Dr. Juan Q. Xavier de la dos Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test_lastname_three_conjunctions(self):
        hn = HumanName("de la dos Vega, Dr. Juan Q. Xavier III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test_comma_three_conjunctions(self):
        hn = HumanName("Dr. Juan Q. Xavier de la dos Vega, III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la dos Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)


class SuffixesTestCase(HumanNameTestBase):

    def test_suffix(self):
        hn = HumanName("Joe Franklin Jr")
        self.m(hn.first, "Joe", hn)
        self.m(hn.last, "Franklin", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_suffix_with_periods(self):
        hn = HumanName("Joe Dentist D.D.S.")
        self.m(hn.first, "Joe", hn)
        self.m(hn.last, "Dentist", hn)
        self.m(hn.suffix, "D.D.S.", hn)

    def test_two_suffixes(self):
        hn = HumanName("Kenneth Clarke QC MP")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        # NOTE: this adds a comma when the original format did not have one.
        # not ideal but at least its in the right bucket
        self.m(hn.suffix, "QC, MP", hn)

    def test_two_suffixes_lastname_comma_format(self):
        hn = HumanName("Washington Jr. MD, Franklin")
        self.m(hn.first, "Franklin", hn)
        self.m(hn.last, "Washington", hn)
        # NOTE: this adds a comma when the original format did not have one.
        self.m(hn.suffix, "Jr., MD", hn)

    def test_two_suffixes_suffix_comma_format(self):
        hn = HumanName("Franklin Washington, Jr. MD")
        self.m(hn.first, "Franklin", hn)
        self.m(hn.last, "Washington", hn)
        self.m(hn.suffix, "Jr. MD", hn)

    def test_suffix_containing_periods(self):
        hn = HumanName("Kenneth Clarke Q.C.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C.", hn)

    def test_suffix_containing_periods_lastname_comma_format(self):
        hn = HumanName("Clarke, Kenneth, Q.C. M.P.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C. M.P.", hn)

    def test_suffix_containing_periods_suffix_comma_format(self):
        hn = HumanName("Kenneth Clarke Q.C., M.P.")
        self.m(hn.first, "Kenneth", hn)
        self.m(hn.last, "Clarke", hn)
        self.m(hn.suffix, "Q.C., M.P.", hn)

    def test_suffix_with_single_comma_format(self):
        hn = HumanName("John Doe jr., MD")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "jr., MD", hn)

    def test_suffix_with_double_comma_format(self):
        hn = HumanName("Doe, John jr., MD")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "jr., MD", hn)

    def test_phd_with_erroneous_space(self):
        hn = HumanName("John Smith, Ph. D.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)
        self.m(hn.suffix, "Ph. D.", hn)

    def test_phd_conflict(self):
        hn = HumanName("Adolph D")
        self.m(hn.first, "Adolph", hn)
        self.m(hn.last, "D", hn)

    # http://en.wikipedia.org/wiki/Ma_(surname)

    def test_potential_suffix_that_is_also_last_name(self):
        hn = HumanName("Jack Ma")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)

    def test_potential_suffix_that_is_also_last_name_comma(self):
        hn = HumanName("Ma, Jack")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)

    def test_potential_suffix_that_is_also_last_name_with_suffix(self):
        hn = HumanName("Jack Ma Jr")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_potential_suffix_that_is_also_last_name_with_suffix_comma(self):
        hn = HumanName("Ma III, Jack Jr")
        self.m(hn.first, "Jack", hn)
        self.m(hn.last, "Ma", hn)
        self.m(hn.suffix, "III, Jr", hn)

    # https://github.com/derek73/python-nameparser/issues/27
    @unittest.expectedFailure
    def test_king(self):
        hn = HumanName("Dr King Jr")
        self.m(hn.title, "Dr", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr", hn)

    def test_multiple_letter_suffix_with_periods(self):
        hn = HumanName("John Doe Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_suffix_with_periods_with_comma(self):
        hn = HumanName("John Doe, Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)

    def test_suffix_with_periods_with_lastname_comma(self):
        hn = HumanName("Doe, John Msc.Ed.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Msc.Ed.", hn)


class TitleTestCase(HumanNameTestBase):

    def test_last_name_is_also_title(self):
        hn = HumanName("Amy E Maid")
        self.m(hn.first, "Amy", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.last, "Maid", hn)

    def test_last_name_is_also_title_no_comma(self):
        hn = HumanName("Dr. Martin Luther King Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Martin", hn)
        self.m(hn.middle, "Luther", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_last_name_is_also_title_with_comma(self):
        hn = HumanName("Dr Martin Luther King, Jr.")
        self.m(hn.title, "Dr", hn)
        self.m(hn.first, "Martin", hn)
        self.m(hn.middle, "Luther", hn)
        self.m(hn.last, "King", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_last_name_is_also_title3(self):
        hn = HumanName("John King")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "King", hn)

    def test_title_with_conjunction(self):
        hn = HumanName("Secretary of State Hillary Clinton")
        self.m(hn.title, "Secretary of State", hn)
        self.m(hn.first, "Hillary", hn)
        self.m(hn.last, "Clinton", hn)

    def test_compound_title_with_conjunction(self):
        hn = HumanName("Cardinal Secretary of State Hillary Clinton")
        self.m(hn.title, "Cardinal Secretary of State", hn)
        self.m(hn.first, "Hillary", hn)
        self.m(hn.last, "Clinton", hn)

    def test_title_is_title(self):
        hn = HumanName("Coach")
        self.m(hn.title, "Coach", hn)

    # TODO: fix handling of U.S.
    @unittest.expectedFailure
    def test_chained_title_first_name_title_is_initials(self):
        hn = HumanName("U.S. District Judge Marc Thomas Treadwell")
        self.m(hn.title, "U.S. District Judge", hn)
        self.m(hn.first, "Marc", hn)
        self.m(hn.middle, "Thomas", hn)
        self.m(hn.last, "Treadwell", hn)

    def test_conflict_with_chained_title_first_name_initial(self):
        hn = HumanName("U. S. Grant")
        self.m(hn.first, "U.", hn)
        self.m(hn.middle, "S.", hn)
        self.m(hn.last, "Grant", hn)

    def test_chained_title_first_name_initial_with_no_period(self):
        hn = HumanName("US Magistrate Judge T Michael Putnam")
        self.m(hn.title, "US Magistrate Judge", hn)
        self.m(hn.first, "T", hn)
        self.m(hn.middle, "Michael", hn)
        self.m(hn.last, "Putnam", hn)

    def test_chained_hyphenated_title(self):
        hn = HumanName("US Magistrate-Judge Elizabeth E Campbell")
        self.m(hn.title, "US Magistrate-Judge", hn)
        self.m(hn.first, "Elizabeth", hn)
        self.m(hn.middle, "E", hn)
        self.m(hn.last, "Campbell", hn)

    def test_chained_hyphenated_title_with_comma_suffix(self):
        hn = HumanName("Mag-Judge Harwell G Davis, III")
        self.m(hn.title, "Mag-Judge", hn)
        self.m(hn.first, "Harwell", hn)
        self.m(hn.middle, "G", hn)
        self.m(hn.last, "Davis", hn)
        self.m(hn.suffix, "III", hn)

    @unittest.expectedFailure
    def test_title_multiple_titles_with_apostrophe_s(self):
        hn = HumanName("The Right Hon. the President of the Queen's Bench Division")
        self.m(hn.title, "The Right Hon. the President of the Queen's Bench Division", hn)

    def test_title_starts_with_conjunction(self):
        hn = HumanName("The Rt Hon John Jones")
        self.m(hn.title, "The Rt Hon", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Jones", hn)

    def test_conjunction_before_title(self):
        hn = HumanName('The Lord of the Universe')
        self.m(hn.title, "The Lord of the Universe", hn)

    def test_double_conjunction_on_title(self):
        hn = HumanName('Lord of the Universe')
        self.m(hn.title, "Lord of the Universe", hn)

    def test_triple_conjunction_on_title(self):
        hn = HumanName('Lord and of the Universe')
        self.m(hn.title, "Lord and of the Universe", hn)

    def test_multiple_conjunctions_on_multiple_titles(self):
        hn = HumanName('Lord of the Universe and Associate Supreme Queen of the World Lisa Simpson')
        self.m(hn.title, "Lord of the Universe and Associate Supreme Queen of the World", hn)
        self.m(hn.first, "Lisa", hn)
        self.m(hn.last, "Simpson", hn)

    def test_title_with_last_initial_is_suffix(self):
        hn = HumanName("King John V.")
        self.m(hn.title, "King", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "V.", hn)

    def test_initials_also_suffix(self):
        hn = HumanName("Smith, J.R.")
        self.m(hn.first, "J.R.", hn)
        # self.m(hn.middle, "R.", hn)
        self.m(hn.last, "Smith", hn)

    def test_two_title_parts_separated_by_periods(self):
        hn = HumanName("Lt.Gen. John A. Kenneth Doe IV")
        self.m(hn.title, "Lt.Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title(self):
        hn = HumanName("Lt. Gen. John A. Kenneth Doe IV")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title_with_lastname_comma(self):
        hn = HumanName("Doe, Lt. Gen. John A. Kenneth IV")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "IV", hn)

    def test_two_part_title_with_suffix_comma(self):
        hn = HumanName("Lt. Gen. John A. Kenneth Doe, Jr.")
        self.m(hn.title, "Lt. Gen.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_possible_conflict_with_middle_initial_that_could_be_suffix(self):
        hn = HumanName("Doe, Rev. John V, Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "V", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test_possible_conflict_with_suffix_that_could_be_initial(self):
        hn = HumanName("Doe, Rev. John A., V, Jr.")
        self.m(hn.title, "Rev.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "V, Jr.", hn)

    # 'ben' is removed from PREFIXES in v0.2.5
    # this test could re-enable this test if we decide to support 'ben' as a prefix
    @unittest.expectedFailure
    def test_ben_as_conjunction(self):
        hn = HumanName("Ahmad ben Husain")
        self.m(hn.first, "Ahmad", hn)
        self.m(hn.last, "ben Husain", hn)

    def test_ben_as_first_name(self):
        hn = HumanName("Ben Johnson")
        self.m(hn.first, "Ben", hn)
        self.m(hn.last, "Johnson", hn)

    def test_ben_as_first_name_with_middle_name(self):
        hn = HumanName("Ben Alex Johnson")
        self.m(hn.first, "Ben", hn)
        self.m(hn.middle, "Alex", hn)
        self.m(hn.last, "Johnson", hn)

    def test_ben_as_middle_name(self):
        hn = HumanName("Alex Ben Johnson")
        self.m(hn.first, "Alex", hn)
        self.m(hn.middle, "Ben", hn)
        self.m(hn.last, "Johnson", hn)

    # http://code.google.com/p/python-nameparser/issues/detail?id=13
    def test_last_name_also_prefix(self):
        hn = HumanName("Jane Doctor")
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Doctor", hn)

    def test_title_with_periods(self):
        hn = HumanName("Lt.Gov. John Doe")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test_title_with_periods_lastname_comma(self):
        hn = HumanName("Doe, Lt.Gov. John")
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test_mac_with_spaces(self):
        hn = HumanName("Jane Mac Beth")
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Mac Beth", hn)

    def test_mac_as_first_name(self):
        hn = HumanName("Mac Miller")
        self.m(hn.first, "Mac", hn)
        self.m(hn.last, "Miller", hn)

    def test_multiple_prefixes(self):
        hn = HumanName("Mike van der Velt")
        self.m(hn.first, "Mike", hn)
        self.m(hn.last, "van der Velt", hn)


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

    def test_short_names_with_mac(self):
        hn = HumanName('mack johnson')
        hn.capitalize()
        self.m(str(hn), 'Mack Johnson', hn)

    def test_portuguese_prefixes(self):
        hn = HumanName("joao da silva do amaral de souza")
        hn.capitalize()
        self.m(str(hn), 'Joao da Silva do Amaral de Souza', hn)

    def test_capitalize_prefix_clash_on_first_name(self):
        hn = HumanName("van nguyen")
        hn.capitalize()
        self.m(str(hn), 'Van Nguyen', hn)


class HumanNameOutputFormatTests(HumanNameTestBase):

    def test_formatting_init_argument(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)",
                       string_format="TEST1")
        self.assertEqual(u(hn), "TEST1")

    def test_formatting_constants_attribute(self):
        from nameparser.config import CONSTANTS
        _orig = CONSTANTS.string_format
        CONSTANTS.string_format = "TEST2"
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        self.assertEqual(u(hn), "TEST2")
        CONSTANTS.string_format = _orig

    def test_capitalize_name_constants_attribute(self):
        from nameparser.config import CONSTANTS
        CONSTANTS.capitalize_name = True
        hn = HumanName("bob v. de la macdole-eisenhower phd")
        self.assertEqual(str(hn), "Bob V. de la MacDole-Eisenhower Ph.D.")
        CONSTANTS.capitalize_name = False

    def test_force_mixed_case_capitalization_constants_attribute(self):
        from nameparser.config import CONSTANTS
        CONSTANTS.force_mixed_case_capitalization = True
        hn = HumanName('Shirley Maclaine')
        hn.capitalize()
        self.assertEqual(str(hn), "Shirley MacLaine")
        CONSTANTS.force_mixed_case_capitalization = False

    def test_capitalize_name_and_force_mixed_case_capitalization_constants_attributes(self):
        from nameparser.config import CONSTANTS
        CONSTANTS.capitalize_name = True
        CONSTANTS.force_mixed_case_capitalization = True
        hn = HumanName('Shirley Maclaine')
        self.assertEqual(str(hn), "Shirley MacLaine")

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
        hn.middle = ''
        self.assertEqual(u(hn), "Rev John Doe III")
        hn.suffix = ''
        self.assertEqual(u(hn), "Rev John Doe")
        hn.title = ''
        self.assertEqual(u(hn), "John Doe")

    def test_formating_of_nicknames_with_parenthesis(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} ({nickname})"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III (Kenny)")
        hn.nickname = ''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_single_quotes(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} '{nickname}'"
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III 'Kenny'")
        hn.nickname = ''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_with_double_quotes(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} {middle} {last} {suffix} \"{nickname}\""
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III \"Kenny\"")
        hn.nickname = ''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")

    def test_formating_of_nicknames_in_middle(self):
        hn = HumanName("Rev John A. Kenneth Doe III (Kenny)")
        hn.string_format = "{title} {first} ({nickname}) {middle} {last} {suffix}"
        self.assertEqual(u(hn), "Rev John (Kenny) A. Kenneth Doe III")
        hn.nickname = ''
        self.assertEqual(u(hn), "Rev John A. Kenneth Doe III")

    def test_remove_emojis(self):
        hn = HumanName("Sam Smith 😊")
        self.m(hn.first, "Sam", hn)
        self.m(hn.last, "Smith", hn)
        self.assertEqual(u(hn), "Sam Smith")

    def test_keep_non_emojis(self):
        hn = HumanName("∫≜⩕ Smith 😊")
        self.m(hn.first, "∫≜⩕", hn)
        self.m(hn.last, "Smith", hn)
        self.assertEqual(u(hn), "∫≜⩕ Smith")

    def test_keep_emojis(self):
        from nameparser.config import Constants
        constants = Constants()
        constants.regexes.emoji = False
        hn = HumanName("∫≜⩕ Smith😊", constants)
        self.m(hn.first, "∫≜⩕", hn)
        self.m(hn.last, "Smith😊", hn)
        self.assertEqual(u(hn), "∫≜⩕ Smith😊")
        # test cleanup


class InitialsTestCase(HumanNameTestBase):
    def test_initials(self):
        hn = HumanName("Andrew Boris Petersen")
        self.m(hn.initials(), "A. B. P.", hn)

    def test_initials_simple_name(self):
        hn = HumanName("John Doe")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("John Doe", initials_format="{first} {last}")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("John Doe", initials_format="{last}")
        self.m(hn.initials(), "D.", hn)
        hn = HumanName("John Doe", initials_format="{first}")
        self.m(hn.initials(), "J.", hn)
        hn = HumanName("John Doe", initials_format="{middle}")
        self.m(hn.initials(), "", hn)

    def test_initials_complex_name(self):
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. A. K. D.", hn)

    def test_initials_format(self):
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first} {middle}")
        self.m(hn.initials(), "J. A. K.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first} {last}")
        self.m(hn.initials(), "J. D.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{middle} {last}")
        self.m(hn.initials(), "A. K. D.", hn)
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_format="{first}, {last}")
        self.m(hn.initials(), "J., D.", hn)

    def test_initials_format_constants(self):
        from nameparser.config import CONSTANTS
        _orig = CONSTANTS.initials_format
        CONSTANTS.initials_format = "{first} {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. D.", hn)
        CONSTANTS.initials_format = "{first}  {last}"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J. D.", hn)
        CONSTANTS.initials_format = _orig

    def test_initials_delimiter(self):
        hn = HumanName("Doe, John A. Kenneth, Jr.", initials_delimiter=";")
        self.m(hn.initials(), "J; A; K; D;", hn)

    def test_initials_delimiter_constants(self):
        from nameparser.config import CONSTANTS
        _orig = CONSTANTS.initials_delimiter
        CONSTANTS.initials_delimiter = ";"
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials(), "J; A; K; D;", hn)
        CONSTANTS.initials_delimiter = _orig

    def test_initials_list(self):
        hn = HumanName("Andrew Boris Petersen")
        self.m(hn.initials_list(), ["A", "B", "P"], hn)

    def test_initials_list_complex_name(self):
        hn = HumanName("Doe, John A. Kenneth, Jr.")
        self.m(hn.initials_list(), ["J", "A", "K", "D"], hn)

    def test_initials_with_prefix_firstname(self):
        hn = HumanName("Van Jeremy Johnson")
        self.m(hn.initials_list(), ["V", "J", "J"], hn)

    def test_initials_with_prefix(self):
        hn = HumanName("Alex van Johnson")
        self.m(hn.initials_list(), ["A", "J"], hn)


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
    "U.S. District Judge Marc Thomas Treadwell",
    "Dra. Andréia da Silva",
    "Srta. Andréia da Silva",

)


class HumanNameVariationTests(HumanNameTestBase):
    # test automated variations of names in TEST_NAMES.
    # Helps test that the 3 code trees work the same

    TEST_NAMES = TEST_NAMES

    def test_variations_of_TEST_NAMES(self):
        for name in self.TEST_NAMES:
            hn = HumanName(name)
            if len(hn.suffix_list) > 1:
                hn = HumanName("{title} {first} {middle} {last} {suffix}".format(**hn.as_dict()).split(',')[0])
            hn.C.empty_attribute_default = ''  # format strings below require empty string
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
        name_string = sys.argv[1]
        hn_instance = HumanName(name_string, encoding=sys.stdout.encoding)
        print((repr(hn_instance)))
        hn_instance.capitalize()
        print((repr(hn_instance)))
        print("Initials: " + hn_instance.initials())
    else:
        print("-"*80)
        print("Running tests")
        unittest.main(exit=False)
        print("-"*80)
        print("Running tests with empty_attribute_default = None")
        from nameparser.config import CONSTANTS
        CONSTANTS.empty_attribute_default = None
        unittest.main()
