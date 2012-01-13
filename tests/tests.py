#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Run this file to run the tests, e.g "python tests.py" or "./tests.py".
Post a ticket and/or patch/diff of this file for names that fail and I will try to fix it.
http://code.google.com/p/python-nameparser/issues/entry
"""

from nameparser import HumanName
from nameparser.parser import log

import unittest
class HumanNameTests(unittest.TestCase):
    
    def assertMatches(self, actual, expected, parsed):
        """assertEquals with a better message"""
        try:
            self.assertEquals(actual, expected, u"'%s' != '%s' for '%s'\n%s" % (
                    actual, 
                    expected, 
                    parsed.full_name, 
                    parsed
                )
            )
        except UnicodeDecodeError:
            self.assertEquals(actual, expected )
    
    def test_utf8(self):
        parsed = HumanName("de la Véña, Jüan")
        self.assertMatches(parsed.first,u"Jüan", parsed)
        self.assertMatches(parsed.last, u"de la Véña", parsed)
    
    def test_unicode(self):
        parsed = HumanName(u"de la Véña, Jüan")
        self.assertMatches(parsed.first,u"Jüan", parsed)
        self.assertMatches(parsed.last, u"de la Véña", parsed)
    
    def test_len(self):
        parsed = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.assertMatches(len(parsed), 5, parsed)
        parsed = HumanName("John Doe")
        self.assertMatches(len(parsed), 2, parsed)
    
    def test_comparison(self):
        parsed1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        parsed2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assert_(parsed1 == parsed2)
        self.assert_(not parsed1 is parsed2)
        self.assert_(parsed1 == "Dr. John P. Doe-Ray CLU, CFP, LUTC")
        parsed1 = HumanName("Doe, Dr. John P., CLU, CFP, LUTC")
        parsed2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assert_(not parsed1 == parsed2)
        self.assert_(not parsed1 == 0)
        self.assert_(not parsed1 == "test")
        self.assert_(not parsed1 == ["test"])
        self.assert_(not parsed1 == {"test":parsed2})
    
    def test_comparison_case_insensitive(self):
        parsed1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        parsed2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assert_(parsed1 == parsed2)
        self.assert_(not parsed1 is parsed2)
        self.assert_(parsed1 == "Dr. John P. Doe-ray clu, CFP, LUTC")
    
    def test_slice(self):
        parsed = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.assertMatches(list(parsed), [u'Dr.', u'John', u'P.', u'Doe-Ray', u'CLU, CFP, LUTC'], parsed)
        self.assertMatches(parsed[1:], [u'John', u'P.', u'Doe-Ray', u'CLU, CFP, LUTC'], parsed)
        self.assertMatches(parsed[1:-1], [u'John', u'P.', u'Doe-Ray'], parsed)
    
    def test1(self):
        parsed = HumanName("John Doe")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
    
    def test2(self):
        parsed = HumanName("John Doe, Jr.")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test3(self):
        parsed = HumanName("John Doe III")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test4(self):
        parsed = HumanName("Doe, John")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
    
    def test5(self):
        parsed = HumanName("Doe, John, Jr.")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test6(self):
        parsed = HumanName("Doe, John III")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test7(self):
        parsed = HumanName("John A. Doe")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
    
    def test8(self):
        parsed = HumanName("John A. Doe, Jr.")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test9(self):
        parsed = HumanName("John A. Doe III")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test10(self):
        parsed = HumanName("Doe, John. A.")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
    
    def test11(self):
        parsed = HumanName("Doe, John. A., Jr.")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test12(self):
        parsed = HumanName("Doe, John. A., III")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test13(self):
        parsed = HumanName("John A. Kenneth Doe")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
    
    def test14(self):
        parsed = HumanName("John A. Kenneth Doe, Jr.")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test15(self):
        parsed = HumanName("John A. Kenneth Doe III")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test16(self):
        parsed = HumanName("Doe, John. A. Kenneth")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
    
    def test17(self):
        parsed = HumanName("Doe, John. A. Kenneth, Jr.")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test18(self):
        parsed = HumanName("Doe, John. A. Kenneth III")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test19(self):
        parsed = HumanName("Dr. John Doe")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
    
    def test20(self):
        parsed = HumanName("Dr. John Doe, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test21(self):
        parsed = HumanName("Dr. John Doe III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test22(self):
        parsed = HumanName("Doe, Dr. John")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
    
    def test23(self):
        parsed = HumanName("Doe, Dr. John, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test24(self):
        parsed = HumanName("Doe, Dr. John III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test25(self):
        parsed = HumanName("Dr. John A. Doe")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
    
    def test26(self):
        parsed = HumanName("Dr. John A. Doe, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test27(self):
        parsed = HumanName("Dr. John A. Doe III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test28(self):
        parsed = HumanName("Doe, Dr. John A.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
    
    def test29(self):
        parsed = HumanName("Doe, Dr. John A. Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test30(self):
        parsed = HumanName("Doe, Dr. John A. III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test31(self):
        parsed = HumanName("Dr. John A. Kenneth Doe")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
    
    def test32(self):
        parsed = HumanName("Dr. John A. Kenneth Doe, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test33(self):
        parsed = HumanName("Al Arnold Gore, Jr.")
        self.assertMatches(parsed.middle,"Arnold", parsed)
        self.assertMatches(parsed.first,"Al", parsed)
        self.assertMatches(parsed.last,"Gore", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test34(self):
        parsed = HumanName("Dr. John A. Kenneth Doe III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test35(self):
        parsed = HumanName("Doe, Dr. John A. Kenneth")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
    
    def test36(self):
        parsed = HumanName("Doe, Dr. John A. Kenneth Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test37(self):
        parsed = HumanName("Doe, Dr. John A. Kenneth III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test38(self):
        parsed = HumanName("Juan de la Vega")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test39(self):
        parsed = HumanName("Juan de la Vega, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test40(self):
        parsed = HumanName("Juan de la Vega III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test41(self):
        parsed = HumanName("de la Vega, Juan")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test42(self):
        parsed = HumanName("de la Vega, Juan, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test43(self):
        parsed = HumanName("de la Vega, Juan III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test44(self):
        parsed = HumanName("Juan Velasquez y Garcia")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test45(self):
        parsed = HumanName("Juan Velasquez y Garcia, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test46(self):
        parsed = HumanName("Juan Velasquez y Garcia III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test47(self):
        parsed = HumanName("Velasquez y Garcia, Juan")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test48(self):
        parsed = HumanName("Velasquez y Garcia, Juan, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test49(self):
        parsed = HumanName("Velasquez y Garcia, Juan III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test50(self):
        parsed = HumanName("Dr. Juan de la Vega")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test51(self):
        parsed = HumanName("Dr. Juan de la Vega, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test52(self):
        parsed = HumanName("Dr. Juan de la Vega III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test53(self):
        parsed = HumanName("de la Vega, Dr. Juan")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test54(self):
        parsed = HumanName("de la Vega, Dr. Juan, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test55(self):
        parsed = HumanName("de la Vega, Dr. Juan III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test56(self):
        parsed = HumanName("Dr. Juan Velasquez y Garcia")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test57(self):
        parsed = HumanName("Dr. Juan Velasquez y Garcia, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test58(self):
        parsed = HumanName("Dr. Juan Velasquez y Garcia III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test59(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test60(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test61(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan III")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test62(self):
        parsed = HumanName("Juan Q. de la Vega")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test63(self):
        parsed = HumanName("Juan Q. de la Vega, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test64(self):
        parsed = HumanName("Juan Q. de la Vega III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test65(self):
        parsed = HumanName("de la Vega, Juan Q.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test66(self):
        parsed = HumanName("de la Vega, Juan Q., Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test67(self):
        parsed = HumanName("de la Vega, Juan Q. III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test68(self):
        parsed = HumanName("Juan Q. Velasquez y Garcia")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test69(self):
        parsed = HumanName("Juan Q. Velasquez y Garcia, Jr.")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test70(self):
        parsed = HumanName("Juan Q. Velasquez y Garcia III")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test71(self):
        parsed = HumanName("Velasquez y Garcia, Juan Q.")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test72(self):
        parsed = HumanName("Velasquez y Garcia, Juan Q., Jr.")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test73(self):
        parsed = HumanName("Velasquez y Garcia, Juan Q. III")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test74(self):
        parsed = HumanName("Dr. Juan Q. de la Vega")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test75(self):
        parsed = HumanName("Dr. Juan Q. de la Vega, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test76(self):
        parsed = HumanName("Dr. Juan Q. de la Vega III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test77(self):
        parsed = HumanName("de la Vega, Dr. Juan Q.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
    
    def test78(self):
        parsed = HumanName("de la Vega, Dr. Juan Q., Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
    
    def test79(self):
        parsed = HumanName("de la Vega, Dr. Juan Q. III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last, u"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
    
    def test80(self):
        parsed = HumanName("Dr. Juan Q. Velasquez y Garcia")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test81(self):
        parsed = HumanName("Dr. Juan Q. Velasquez y Garcia, Jr.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test82(self):
        parsed = HumanName("Dr. Juan Q. Velasquez y Garcia III")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test83(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan Q.")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test84(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan Q., Jr.")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test85(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan Q. III")
        self.assertMatches(parsed.middle,"Q.", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test86(self):
        parsed = HumanName("Juan Q. Xavier de la Vega")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test87(self):
        parsed = HumanName("Juan Q. Xavier de la Vega, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test88(self):
        parsed = HumanName("Juan Q. Xavier de la Vega III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test89(self):
        parsed = HumanName("de la Vega, Juan Q. Xavier")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test90(self):
        parsed = HumanName("de la Vega, Juan Q. Xavier, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test91(self):
        parsed = HumanName("de la Vega, Juan Q. Xavier III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test92(self):
        parsed = HumanName("Dr. Juan Q. Xavier de la Vega")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test93(self):
        parsed = HumanName("Dr. Juan Q. Xavier de la Vega, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test94(self):
        parsed = HumanName("Dr. Juan Q. Xavier de la Vega III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test95(self):
        parsed = HumanName("de la Vega, Dr. Juan Q. Xavier")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
    
    def test96(self):
        parsed = HumanName("de la Vega, Dr. Juan Q. Xavier, Jr.")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test97(self):
        parsed = HumanName("de la Vega, Dr. Juan Q. Xavier III")
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"de la Vega", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test98(self):
        parsed = HumanName("Juan Q. Xavier Velasquez y Garcia")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test99(self):
        parsed = HumanName("Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test100(self):
        parsed = HumanName("Juan Q. Xavier Velasquez y Garcia III")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test101(self):
        parsed = HumanName("Velasquez y Garcia, Juan Q. Xavier")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test102(self):
        parsed = HumanName("Velasquez y Garcia, Juan Q. Xavier, Jr.")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test103(self):
        parsed = HumanName("Velasquez y Garcia, Juan Q. Xavier III")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test104(self):
        parsed = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test105(self):
        parsed = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test106(self):
        parsed = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia III")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test107(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
    
    def test108(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier, Jr.")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test109(self):
        parsed = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier III")
        self.assertMatches(parsed.middle,"Q. Xavier", parsed)
        self.assertMatches(parsed.first,"Juan", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.last,"Velasquez y Garcia", parsed)
        self.assertMatches(parsed.suffix,"III", parsed)
    
    def test110(self):
        parsed = HumanName("John Doe, CLU, CFP, LUTC")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"CLU, CFP, LUTC", parsed)
    
    def test111(self):
        parsed = HumanName("John P. Doe, CLU, CFP, LUTC")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.middle,"P.", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.suffix,"CLU, CFP, LUTC", parsed)
    
    def test112(self):
        parsed = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.middle,"P.", parsed)
        self.assertMatches(parsed.last,"Doe-Ray", parsed)
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.suffix,"CLU, CFP, LUTC", parsed)
    
    def test113(self):
        parsed = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.assertMatches(parsed.title,"Dr.", parsed)
        self.assertMatches(parsed.middle,"P.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe-Ray", parsed)
        self.assertMatches(parsed.suffix,"CLU, CFP, LUTC", parsed)
    
    def test114(self):
        parsed = HumanName("Hon Oladapo")
        self.assertMatches(parsed.first,"Hon", parsed)
        self.assertMatches(parsed.last,"Oladapo", parsed)
    
    def test115(self):
        parsed = HumanName("Hon. Barrington P. Doe-Ray, Jr.")
        self.assertMatches(parsed.title,"Hon.", parsed)
        self.assertMatches(parsed.middle,"P.", parsed)
        self.assertMatches(parsed.first,"Barrington", parsed)
        self.assertMatches(parsed.last,"Doe-Ray", parsed)
    
    def test116(self):
        parsed = HumanName("Doe-Ray, Hon. Barrington P. Jr., CFP, LUTC")
        self.assertMatches(parsed.title,"Hon.", parsed)
        self.assertMatches(parsed.middle,"P.", parsed)
        self.assertMatches(parsed.first,"Barrington", parsed)
        self.assertMatches(parsed.last,"Doe-Ray", parsed)
        self.assertMatches(parsed.suffix,"Jr., CFP, LUTC", parsed)
    
    # Last name with conjunction
    def test117(self):
        parsed = HumanName('Jose Aznar y Lopez')
        self.assertMatches(parsed.first,"Jose", parsed)
        self.assertMatches(parsed.last,"Aznar y Lopez", parsed)
    
    # Potential conjunction/prefix treated as initial (because uppercase)
    def test118(self):
        parsed = HumanName('John E Smith')
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.middle,"E", parsed)
        self.assertMatches(parsed.last,"Smith", parsed)
    
    # The prefix "e"
    def test119(self):
        parsed = HumanName('John e Smith')
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"e Smith", parsed)
    
    def test_couples_names(self):
        parsed = HumanName('John and Jane Smith')
        self.assertMatches(parsed.first,"John and Jane", parsed)
        self.assertMatches(parsed.last,"Smith", parsed)
    
    # def test_couple_titles(self):
    #     parsed = HumanName('Mr. and Mrs. John and Jane Smith')
    #     self.assertMatches(parsed.title,"Mr. and Mrs.", parsed)
    #     self.assertMatches(parsed.first,"John and Jane", parsed)
    #     self.assertMatches(parsed.last,"Smith", parsed)
    
    # Capitalization, including conjunction and exception for 'III'
    def test121(self):
        parsed = HumanName('juan q. xavier velasquez y garcia iii')
        parsed.capitalize()
        self.assertMatches(str(parsed), 'Juan Q. Xavier Velasquez y Garcia III', parsed)
    
    # Capitalization with M(a)c and hyphenated names
    def test122(self):
        parsed = HumanName('donovan mcnabb-smith')
        parsed.capitalize()
        self.assertMatches(str(parsed), 'Donovan McNabb-Smith', parsed)
    
    # Leaving already-capitalized names alone
    def test123(self):
        parsed = HumanName('Shirley Maclaine')
        parsed.capitalize()
        self.assertMatches(str(parsed), 'Shirley Maclaine', parsed)
    
    # tests for Rev. title (Reverend)
    def test124(self):
        parsed = HumanName("Rev. John A. Kenneth Doe")
        self.assertMatches(parsed.title,"Rev.", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
    
    def test125(self):
        parsed = HumanName("Rev John A. Kenneth Doe")
        self.assertMatches(parsed.title,"Rev", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
    
    def test126(self):
        parsed = HumanName("Doe, Rev. John A. Jr.")
        self.assertMatches(parsed.title,"Rev.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A.", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    def test127(self):
        parsed = HumanName("Buca di Beppo")
        self.assertMatches(parsed.first,"Buca", parsed)
        self.assertMatches(parsed.last,"di Beppo", parsed)
    
    def test_lc_comparison_of_military_prefix(self):
        parsed = HumanName("Lt.Gen. John A. Kenneth Doe IV")
        self.assertMatches(parsed.title,"Lt.Gen.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"IV", parsed)
    
    def test_two_part_prefix(self):
        parsed = HumanName("Lt. Gen. John A. Kenneth Doe IV")
        self.assertMatches(parsed.title,"Lt. Gen.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"IV", parsed)
    
    def test_two_part_prefix_with_lastname_comma(self):
        parsed = HumanName("Doe, Lt. Gen. John A. Kenneth IV")
        self.assertMatches(parsed.title,"Lt. Gen.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"IV", parsed)
    
    def test_two_part_prefix_with_suffix_comma(self):
        parsed = HumanName("Lt. Gen. John A. Kenneth Doe, Jr.")
        self.assertMatches(parsed.title,"Lt. Gen.", parsed)
        self.assertMatches(parsed.first,"John", parsed)
        self.assertMatches(parsed.last,"Doe", parsed)
        self.assertMatches(parsed.middle,"A. Kenneth", parsed)
        self.assertMatches(parsed.suffix,"Jr.", parsed)
    
    

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
    "Doe, John. A.",
    "Doe, John. A., Jr.",
    "Doe, John. A. III",
    "John A. Kenneth Doe",
    "John A. Kenneth Doe, Jr.",
    "John A. Kenneth Doe III",
    "Doe, John. A. Kenneth",
    "Doe, John. A. Kenneth, Jr.",
    "Doe, John. A. Kenneth III",
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
    "Hon Oladapo",
    "Jose Aznar y Lopez",
    "John E Smith",
    "John e Smith",
    "John and Jane Smith",
    "Rev. John A. Kenneth Doe",
    "Rev John A. Kenneth Doe",
    "Doe, Rev. John A. Jr.",
    "Buca di Beppo",
    "Lt. Gen. John A. Kenneth Doe, Jr.",
    "Doe, Lt. Gen. John A. Kenneth IV",
    "Lt. Gen. John A. Kenneth Doe IV",
    # 'Mr. and Mrs. John Smith',
)

if __name__ == '__main__':
    if log.level > 0:
        for name in TEST_NAMES:
            parsed = HumanName(name)
            print unicode(name)
            print unicode(parsed)
            print repr(parsed)
            print "\n-------------------------------------------\n"
    unittest.main()
