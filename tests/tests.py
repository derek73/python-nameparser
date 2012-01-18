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

class HumanNameTestBase(unittest.TestCase):
    
    def m(self, actual, expected, hn):
        """assertEquals with a better message"""
        try:
            self.assertEquals(actual, expected, u"'%s' != '%s' for '%s'\n%s" % (
                    actual, 
                    expected, 
                    hn.full_name, 
                    hn
                )
            )
        except UnicodeDecodeError:
            self.assertEquals(actual, expected )
    


class HumanNameBruteForceTests(HumanNameTestBase):
    
    def test_utf8(self):
        hn = HumanName("de la Véña, Jüan")
        self.m(hn.first,u"Jüan", hn)
        self.m(hn.last, u"de la Véña", hn)
    
    def test_unicode(self):
        hn = HumanName(u"de la Véña, Jüan")
        self.m(hn.first,u"Jüan", hn)
        self.m(hn.last, u"de la Véña", hn)
    
    def test_len(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(len(hn), 5, hn)
        hn = HumanName("John Doe")
        self.m(len(hn), 2, hn)
    
    def test_comparison(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assert_(hn1 == hn2)
        self.assert_(not hn1 is hn2)
        self.assert_(hn1 == "Dr. John P. Doe-Ray CLU, CFP, LUTC")
        hn1 = HumanName("Doe, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assert_(not hn1 == hn2)
        self.assert_(not hn1 == 0)
        self.assert_(not hn1 == "test")
        self.assert_(not hn1 == ["test"])
        self.assert_(not hn1 == {"test":hn2})
    
    def test_assignment_to_full_name(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"Jr.", hn)
        hn.full_name = "Juan Velasquez y Garcia III"
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test_assignment_to_attribute(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        hn.last = "de la Vega"
        self.m(hn.last,"de la Vega", hn)
        hn.title = "test"
        self.m(hn.title,"test", hn)
        hn.first = "test"
        self.m(hn.first,"test", hn)
        hn.middle = "test"
        self.m(hn.middle,"test", hn)
        hn.suffix = "test"
        self.m(hn.suffix,"test", hn)
    
    def test_comparison_case_insensitive(self):
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assert_(hn1 == hn2)
        self.assert_(not hn1 is hn2)
        self.assert_(hn1 == "Dr. John P. Doe-ray clu, CFP, LUTC")
    
    def test_slice(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(list(hn), [u'Dr.', u'John', u'P.', u'Doe-Ray', u'CLU, CFP, LUTC'], hn)
        self.m(hn[1:], [u'John', u'P.', u'Doe-Ray', u'CLU, CFP, LUTC'], hn)
        self.m(hn[1:-1], [u'John', u'P.', u'Doe-Ray'], hn)

    def test_conjunction_names(self):
        hn = HumanName("johnny y")
        self.m(hn.first,"johnny", hn)
        self.m(hn.last,"y", hn)

    def test_prefix_names(self):
        hn = HumanName("vai la")
        self.m(hn.first,"vai", hn)
        self.m(hn.last,"la", hn)
    
    def test1(self):
        hn = HumanName("John Doe")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
    
    def test2(self):
        hn = HumanName("John Doe, Jr.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test3(self):
        hn = HumanName("John Doe III")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"III", hn)
    
    def test4(self):
        hn = HumanName("Doe, John")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
    
    def test5(self):
        hn = HumanName("Doe, John, Jr.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test6(self):
        hn = HumanName("Doe, John III")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"III", hn)
    
    def test7(self):
        hn = HumanName("John A. Doe")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
    
    def test8(self):
        hn = HumanName("John A. Doe, Jr.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test9(self):
        hn = HumanName("John A. Doe III")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"III", hn)
    
    def test10(self):
        hn = HumanName("Doe, John. A.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
    
    def test11(self):
        hn = HumanName("Doe, John. A., Jr.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test12(self):
        hn = HumanName("Doe, John. A., III")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"III", hn)
    
    def test13(self):
        hn = HumanName("John A. Kenneth Doe")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
    
    def test14(self):
        hn = HumanName("John A. Kenneth Doe, Jr.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test15(self):
        hn = HumanName("John A. Kenneth Doe III")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"III", hn)
    
    def test16(self):
        hn = HumanName("Doe, John. A. Kenneth")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
    
    def test17(self):
        hn = HumanName("Doe, John. A. Kenneth, Jr.")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test18(self):
        hn = HumanName("Doe, John. A. Kenneth III")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"III", hn)
    
    def test19(self):
        hn = HumanName("Dr. John Doe")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.title,"Dr.", hn)
    
    def test20(self):
        hn = HumanName("Dr. John Doe, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test21(self):
        hn = HumanName("Dr. John Doe III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"III", hn)
    
    def test22(self):
        hn = HumanName("Doe, Dr. John")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
    
    def test23(self):
        hn = HumanName("Doe, Dr. John, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test24(self):
        hn = HumanName("Doe, Dr. John III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"III", hn)
    
    def test25(self):
        hn = HumanName("Dr. John A. Doe")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
    
    def test26(self):
        hn = HumanName("Dr. John A. Doe, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test27(self):
        hn = HumanName("Dr. John A. Doe III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"III", hn)
    
    def test28(self):
        hn = HumanName("Doe, Dr. John A.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
    
    def test29(self):
        hn = HumanName("Doe, Dr. John A. Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test30(self):
        hn = HumanName("Doe, Dr. John A. III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"III", hn)
    
    def test31(self):
        hn = HumanName("Dr. John A. Kenneth Doe")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
    
    def test32(self):
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test33(self):
        hn = HumanName("Al Arnold Gore, Jr.")
        self.m(hn.middle,"Arnold", hn)
        self.m(hn.first,"Al", hn)
        self.m(hn.last,"Gore", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test34(self):
        hn = HumanName("Dr. John A. Kenneth Doe III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"III", hn)
    
    def test35(self):
        hn = HumanName("Doe, Dr. John A. Kenneth")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
    
    def test36(self):
        hn = HumanName("Doe, Dr. John A. Kenneth Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test37(self):
        hn = HumanName("Doe, Dr. John A. Kenneth III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"III", hn)
    
    def test38(self):
        hn = HumanName("Juan de la Vega")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test39(self):
        hn = HumanName("Juan de la Vega, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test40(self):
        hn = HumanName("Juan de la Vega III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"III", hn)
    
    def test41(self):
        hn = HumanName("de la Vega, Juan")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test42(self):
        hn = HumanName("de la Vega, Juan, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test43(self):
        hn = HumanName("de la Vega, Juan III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"III", hn)
    
    def test44(self):
        hn = HumanName("Juan Velasquez y Garcia")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test45(self):
        hn = HumanName("Juan Velasquez y Garcia, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test46(self):
        hn = HumanName("Juan Velasquez y Garcia III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test47(self):
        hn = HumanName("Velasquez y Garcia, Juan")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test48(self):
        hn = HumanName("Velasquez y Garcia, Juan, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test49(self):
        hn = HumanName("Velasquez y Garcia, Juan III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test50(self):
        hn = HumanName("Dr. Juan de la Vega")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test51(self):
        hn = HumanName("Dr. Juan de la Vega, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test52(self):
        hn = HumanName("Dr. Juan de la Vega III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"III", hn)
    
    def test53(self):
        hn = HumanName("de la Vega, Dr. Juan")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test54(self):
        hn = HumanName("de la Vega, Dr. Juan, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test55(self):
        hn = HumanName("de la Vega, Dr. Juan III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"III", hn)
    
    def test56(self):
        hn = HumanName("Dr. Juan Velasquez y Garcia")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test57(self):
        hn = HumanName("Dr. Juan Velasquez y Garcia, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test58(self):
        hn = HumanName("Dr. Juan Velasquez y Garcia III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test59(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test60(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test61(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan III")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test62(self):
        hn = HumanName("Juan Q. de la Vega")
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test63(self):
        hn = HumanName("Juan Q. de la Vega, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test64(self):
        hn = HumanName("Juan Q. de la Vega III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.suffix,"III", hn)
    
    def test65(self):
        hn = HumanName("de la Vega, Juan Q.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test66(self):
        hn = HumanName("de la Vega, Juan Q., Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test67(self):
        hn = HumanName("de la Vega, Juan Q. III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.suffix,"III", hn)
    
    def test68(self):
        hn = HumanName("Juan Q. Velasquez y Garcia")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test69(self):
        hn = HumanName("Juan Q. Velasquez y Garcia, Jr.")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test70(self):
        hn = HumanName("Juan Q. Velasquez y Garcia III")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test71(self):
        hn = HumanName("Velasquez y Garcia, Juan Q.")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test72(self):
        hn = HumanName("Velasquez y Garcia, Juan Q., Jr.")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test73(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. III")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test74(self):
        hn = HumanName("Dr. Juan Q. de la Vega")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test75(self):
        hn = HumanName("Dr. Juan Q. de la Vega, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test76(self):
        hn = HumanName("Dr. Juan Q. de la Vega III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.suffix,"III", hn)
    
    def test77(self):
        hn = HumanName("de la Vega, Dr. Juan Q.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.title,"Dr.", hn)
    
    def test78(self):
        hn = HumanName("de la Vega, Dr. Juan Q., Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.suffix,"Jr.", hn)
        self.m(hn.title,"Dr.", hn)
    
    def test79(self):
        hn = HumanName("de la Vega, Dr. Juan Q. III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last, u"de la Vega", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.suffix,"III", hn)
        self.m(hn.title,"Dr.", hn)
    
    def test80(self):
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test81(self):
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia, Jr.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test82(self):
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia III")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test83(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q.")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test84(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q., Jr.")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test85(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. III")
        self.m(hn.middle,"Q.", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test86(self):
        hn = HumanName("Juan Q. Xavier de la Vega")
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test87(self):
        hn = HumanName("Juan Q. Xavier de la Vega, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test88(self):
        hn = HumanName("Juan Q. Xavier de la Vega III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"III", hn)
    
    def test89(self):
        hn = HumanName("de la Vega, Juan Q. Xavier")
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test90(self):
        hn = HumanName("de la Vega, Juan Q. Xavier, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test91(self):
        hn = HumanName("de la Vega, Juan Q. Xavier III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"III", hn)
    
    def test92(self):
        hn = HumanName("Dr. Juan Q. Xavier de la Vega")
        self.m(hn.first,"Juan", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test93(self):
        hn = HumanName("Dr. Juan Q. Xavier de la Vega, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test94(self):
        hn = HumanName("Dr. Juan Q. Xavier de la Vega III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"III", hn)
    
    def test95(self):
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier")
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.last,"de la Vega", hn)
    
    def test96(self):
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier, Jr.")
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test97(self):
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier III")
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"de la Vega", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.suffix,"III", hn)
    
    def test98(self):
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test99(self):
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test100(self):
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia III")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test101(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test102(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier, Jr.")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test103(self):
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier III")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test104(self):
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test105(self):
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test106(self):
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia III")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test107(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
    
    def test108(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier, Jr.")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test109(self):
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier III")
        self.m(hn.middle,"Q. Xavier", hn)
        self.m(hn.first,"Juan", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.last,"Velasquez y Garcia", hn)
        self.m(hn.suffix,"III", hn)
    
    def test110(self):
        hn = HumanName("John Doe, CLU, CFP, LUTC")
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"CLU, CFP, LUTC", hn)
    
    def test111(self):
        hn = HumanName("John P. Doe, CLU, CFP, LUTC")
        self.m(hn.first,"John", hn)
        self.m(hn.middle,"P.", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.suffix,"CLU, CFP, LUTC", hn)
    
    def test112(self):
        hn = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.m(hn.first,"John", hn)
        self.m(hn.middle,"P.", hn)
        self.m(hn.last,"Doe-Ray", hn)
        self.m(hn.title,"Dr.", hn)
        self.m(hn.suffix,"CLU, CFP, LUTC", hn)
    
    def test113(self):
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(hn.title,"Dr.", hn)
        self.m(hn.middle,"P.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe-Ray", hn)
        self.m(hn.suffix,"CLU, CFP, LUTC", hn)
    
    def test114(self):
        hn = HumanName("Hon Oladapo")
        self.m(hn.first,"Hon", hn)
        self.m(hn.last,"Oladapo", hn)
    
    def test115(self):
        hn = HumanName("Hon. Barrington P. Doe-Ray, Jr.")
        self.m(hn.title,"Hon.", hn)
        self.m(hn.middle,"P.", hn)
        self.m(hn.first,"Barrington", hn)
        self.m(hn.last,"Doe-Ray", hn)
    
    def test116(self):
        hn = HumanName("Doe-Ray, Hon. Barrington P. Jr., CFP, LUTC")
        self.m(hn.title,"Hon.", hn)
        self.m(hn.middle,"P.", hn)
        self.m(hn.first,"Barrington", hn)
        self.m(hn.last,"Doe-Ray", hn)
        self.m(hn.suffix,"Jr., CFP, LUTC", hn)
    
class HumanNameConjunctionTestCase(HumanNameTestBase):
    
    # Last name with conjunction
    def test117(self):
        hn = HumanName('Jose Aznar y Lopez')
        self.m(hn.first,"Jose", hn)
        self.m(hn.last,"Aznar y Lopez", hn)
    
    # Potential conjunction/prefix treated as initial (because uppercase)
    def test118(self):
        hn = HumanName('John E Smith')
        self.m(hn.first,"John", hn)
        self.m(hn.middle,"E", hn)
        self.m(hn.last,"Smith", hn)
    
    # The prefix "e"
    def test_middle_initial_e_conflict_with_conjunction(self):
        # It's not clear what to do here since 'e' is a conjunction. 
        # "E" or "e." would be counted as an intial, but we can't tell that
        # it's an initial w/o capitalization or a period, afaik.
        hn = HumanName('John e Smith')
        self.m(hn.first,"John e Smith", hn)
        self.m(hn.last,"", hn)
    
    def test_couples_names(self):
        hn = HumanName('John and Jane Smith')
        self.m(hn.first,"John and Jane", hn)
        self.m(hn.last,"Smith", hn)
    
    def test_couples_names_with_conjunction_lastname(self):
        hn = HumanName('John and Jane Aznar y Lopez')
        self.m(hn.first,"John and Jane", hn)
        self.m(hn.last,"Aznar y Lopez", hn)
    
    def test_couple_titles(self):
        hn = HumanName('Mr. and Mrs. John and Jane Smith')
        self.m(hn.title,"Mr. and Mrs.", hn)
        self.m(hn.first,"John and Jane", hn)
        self.m(hn.last,"Smith", hn)
    
    # tests for Rev. title (Reverend)
    def test124(self):
        hn = HumanName("Rev. John A. Kenneth Doe")
        self.m(hn.title,"Rev.", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
    
    def test125(self):
        hn = HumanName("Rev John A. Kenneth Doe")
        self.m(hn.title,"Rev", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
    
    def test126(self):
        hn = HumanName("Doe, Rev. John A. Jr.")
        self.m(hn.title,"Rev.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test127(self):
        hn = HumanName("Buca di Beppo")
        self.m(hn.first,"Buca", hn)
        self.m(hn.last,"di Beppo", hn)
    
class HumanNameTitleTestCase(HumanNameTestBase):
    
    def test_lc_comparison_of_title(self):
        hn = HumanName("Lt.Gen. John A. Kenneth Doe IV")
        self.m(hn.title,"Lt.Gen.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"IV", hn)
    
    def test_two_part_title(self):
        hn = HumanName("Lt. Gen. John A. Kenneth Doe IV")
        self.m(hn.title,"Lt. Gen.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"IV", hn)
    
    def test_two_part_title_with_lastname_comma(self):
        hn = HumanName("Doe, Lt. Gen. John A. Kenneth IV")
        self.m(hn.title,"Lt. Gen.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"IV", hn)
    
    def test_two_part_title_with_suffix_comma(self):
        hn = HumanName("Lt. Gen. John A. Kenneth Doe, Jr.")
        self.m(hn.title,"Lt. Gen.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A. Kenneth", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test_possible_conflict_with_middle_initial_that_could_be_suffix(self):
        hn = HumanName("Doe, Rev. John V, Jr.")
        self.m(hn.title,"Rev.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"V", hn)
        self.m(hn.suffix,"Jr.", hn)
    
    def test_possible_conflict_with_suffix_that_could_be_initial(self):
        hn = HumanName("Doe, Rev. John A., V, Jr.")
        self.m(hn.title,"Rev.", hn)
        self.m(hn.first,"John", hn)
        self.m(hn.last,"Doe", hn)
        self.m(hn.middle,"A.", hn)
        self.m(hn.suffix,"V, Jr.", hn)
    

class HumanNameCapitalizationTestCase(HumanNameTestBase):
    
    def test_capitalization_exception_for_III(self):
        hn = HumanName('juan q. xavier velasquez y garcia iii')
        hn.capitalize()
        self.m(str(hn), 'Juan Q. Xavier Velasquez y Garcia III', hn)
    
    def test_capitalize_title(self):
        hn = HumanName('lt. gen. john a. kenneth doe iv')
        hn.capitalize()
        self.m(str(hn), 'Lt. Gen. John A. Kenneth Doe IV', hn)
    
    # Capitalization with M(a)c and hyphenated names
    def test_capitalization_with_Mac_as_hyphenated_names(self):
        hn = HumanName('donovan mcnabb-smith')
        hn.capitalize()
        self.m(str(hn), 'Donovan McNabb-Smith', hn)
    
    # Leaving already-capitalized names alone
    def test123(self):
        hn = HumanName('Shirley Maclaine')
        hn.capitalize()
        self.m(str(hn), 'Shirley Maclaine', hn)

    def test_capitalize_diacritics(self):
        hn = HumanName(u'matth\xe4us schmidt')
        hn.capitalize()
        self.m(unicode(hn), u'Matth\xe4us Schmidt', hn)
    

class HumanNameOutputFormatTests(HumanNameTestBase):
    
    def test_formating(self):
        hn = HumanName("Rev John A. Kenneth Doe III")
        hn.string_format = "{title} {first} {middle} {last} {suffix}"
        self.assertEqual(unicode(hn), "Rev John A. Kenneth Doe III")
        hn.string_format = "{last}, {title} {first} {middle}, {suffix}"
        self.assertEqual(unicode(hn), "Doe, Rev John A. Kenneth, III")


class HumanNameIterativeTestCase(HumanNameTestBase):
    
    # Add the test values to the TEST_NAMES iterable. Seems better approach 
    # but I'm not interested in rewritting all the tests right now. Consider
    # adding new tests here.
    
    TEST_NAMES = (
        ("John Doe", {'first':'John','last':'Doe'}),
        ("John Doe, Jr.", {'first':'John','last':'Doe','suffix':'Jr.'}),
    )
    
    def test_given(self):
        for name in self.TEST_NAMES:
            hn = HumanName(name[0])
            for attr in name[1].keys():
                self.m(getattr(hn,attr), name[1][attr], hn)
    
    def test_variations_of_TEST_NAMES(self):
        for name in self.TEST_NAMES:
            hn = HumanName(name[0])
            if len(hn.suffix_list) > 1:
                hn = HumanName("{title} {first} {middle} {last} {suffix}".format(**hn._dict).split(',')[0])
            nocomma = HumanName("{title} {first} {middle} {last} {suffix}".format(**hn._dict))
            lastnamecomma = HumanName("{last}, {title} {first} {middle} {suffix}".format(**hn._dict))
            suffixcomma = HumanName("{title} {first} {middle} {last}, {suffix}".format(**hn._dict))
            for attr in name[1].keys():
                self.m(getattr(hn,attr),getattr(nocomma,attr),hn)
                self.m(getattr(hn,attr),getattr(lastnamecomma,attr),hn)
                if hn.suffix:
                    self.m(getattr(hn,attr),getattr(suffixcomma,attr),hn)



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
    "Donovan McNabb-Smith",
    "Rev John A. Kenneth Doe",
    "Doe, Rev. John A. Jr.",
    "Buca di Beppo",
    "Lt. Gen. John A. Kenneth Doe, Jr.",
    "Doe, Lt. Gen. John A. Kenneth IV",
    "Lt. Gen. John A. Kenneth Doe IV",
    'Mr. and Mrs. John Smith',
)

class HumanNameVariationTests(HumanNameTestBase):
    
    # test automated variations of names in TEST_NAMES. 
    # Helps test that the 3 code trees work the same
    
    TEST_NAMES = TEST_NAMES
    
    def test_variations_of_TEST_NAMES(self):
        for name in self.TEST_NAMES:
            hn = HumanName(name)
            if len(hn.suffix_list) > 1:
                hn = HumanName("{title} {first} {middle} {last} {suffix}".format(**hn._dict).split(',')[0])
            nocomma = HumanName("{title} {first} {middle} {last} {suffix}".format(**hn._dict))
            lastnamecomma = HumanName("{last}, {title} {first} {middle} {suffix}".format(**hn._dict))
            suffixcomma = HumanName("{title} {first} {middle} {last}, {suffix}".format(**hn._dict))
            for attr in hn._members:
                self.m(getattr(hn,attr),getattr(nocomma,attr),hn)
                self.m(getattr(hn,attr),getattr(lastnamecomma,attr),hn)
                if hn.suffix:
                    self.m(getattr(hn,attr),getattr(suffixcomma,attr),hn)
            

if __name__ == '__main__':
    if log.level > 0:
        for name in TEST_NAMES:
            hn = HumanName(name)
            print unicode(name)
            print unicode(hn)
            print repr(hn)
            print "\n-------------------------------------------\n"
    unittest.main()
