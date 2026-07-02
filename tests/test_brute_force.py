from nameparser import HumanName

from tests.base import HumanNameTestBase


class HumanNameBruteForceTests(HumanNameTestBase):

    def test1(self) -> None:
        hn = HumanName("John Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test2(self) -> None:
        hn = HumanName("John Doe, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test3(self) -> None:
        hn = HumanName("John Doe III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test4(self) -> None:
        hn = HumanName("Doe, John")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test5(self) -> None:
        hn = HumanName("Doe, John, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test6(self) -> None:
        hn = HumanName("Doe, John III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test7(self) -> None:
        hn = HumanName("John A. Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test8(self) -> None:
        hn = HumanName("John A. Doe, Jr")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr", hn)

    def test9(self) -> None:
        hn = HumanName("John A. Doe III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "III", hn)

    def test10(self) -> None:
        hn = HumanName("Doe, John A.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test11(self) -> None:
        hn = HumanName("Doe, John A., Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test12(self) -> None:
        hn = HumanName("Doe, John A., III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "III", hn)

    def test13(self) -> None:
        hn = HumanName("John A. Kenneth Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)

    def test14(self) -> None:
        hn = HumanName("John A. Kenneth Doe, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test15(self) -> None:
        hn = HumanName("John A. Kenneth Doe III")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "III", hn)

    def test16(self) -> None:
        # "John." is an unrecognized period-abbreviation in the leading
        # title position of the lastname-comma format, so is_leading_title()
        # now treats it as a title rather than a first name (see #109).
        hn = HumanName("Doe, John. A. Kenneth")
        self.m(hn.title, "John.", hn)
        self.m(hn.first, "A.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "Kenneth", hn)

    def test17(self) -> None:
        # Same period-abbreviation-as-title behavior as test16 (see #109).
        hn = HumanName("Doe, John. A. Kenneth, Jr.")
        self.m(hn.title, "John.", hn)
        self.m(hn.first, "A.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test18(self) -> None:
        # Same period-abbreviation-as-title behavior as test16 (see #109).
        hn = HumanName("Doe, John. A. Kenneth III")
        self.m(hn.title, "John.", hn)
        self.m(hn.first, "A.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "Kenneth", hn)
        self.m(hn.suffix, "III", hn)

    def test19(self) -> None:
        hn = HumanName("Dr. John Doe")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.title, "Dr.", hn)

    def test20(self) -> None:
        hn = HumanName("Dr. John Doe, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test21(self) -> None:
        hn = HumanName("Dr. John Doe III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test22(self) -> None:
        hn = HumanName("Doe, Dr. John")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test23(self) -> None:
        hn = HumanName("Doe, Dr. John, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test24(self) -> None:
        hn = HumanName("Doe, Dr. John III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test25(self) -> None:
        hn = HumanName("Dr. John A. Doe")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test26(self) -> None:
        hn = HumanName("Dr. John A. Doe, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test27(self) -> None:
        hn = HumanName("Dr. John A. Doe III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "III", hn)

    def test28(self) -> None:
        hn = HumanName("Doe, Dr. John A.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)

    def test29(self) -> None:
        hn = HumanName("Doe, Dr. John A. Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test30(self) -> None:
        hn = HumanName("Doe, Dr. John A. III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test31(self) -> None:
        hn = HumanName("Dr. John A. Kenneth Doe")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test32(self) -> None:
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test33(self) -> None:
        hn = HumanName("Al Arnold Gore, Jr.")
        self.m(hn.middle, "Arnold", hn)
        self.m(hn.first, "Al", hn)
        self.m(hn.last, "Gore", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test34(self) -> None:
        hn = HumanName("Dr. John A. Kenneth Doe III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test35(self) -> None:
        hn = HumanName("Doe, Dr. John A. Kenneth")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test36(self) -> None:
        hn = HumanName("Doe, Dr. John A. Kenneth Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test37(self) -> None:
        hn = HumanName("Doe, Dr. John A. Kenneth III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "III", hn)

    def test38(self) -> None:
        hn = HumanName("Juan de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test39(self) -> None:
        hn = HumanName("Juan de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test40(self) -> None:
        hn = HumanName("Juan de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test41(self) -> None:
        hn = HumanName("de la Vega, Juan")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test42(self) -> None:
        hn = HumanName("de la Vega, Juan, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test43(self) -> None:
        hn = HumanName("de la Vega, Juan III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test44(self) -> None:
        hn = HumanName("Juan Velasquez y Garcia")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test45(self) -> None:
        hn = HumanName("Juan Velasquez y Garcia, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test46(self) -> None:
        hn = HumanName("Juan Velasquez y Garcia III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test47(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test48(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test49(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test50(self) -> None:
        hn = HumanName("Dr. Juan de la Vega")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test51(self) -> None:
        hn = HumanName("Dr. Juan de la Vega, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test52(self) -> None:
        hn = HumanName("Dr. Juan de la Vega III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test53(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)

    def test54(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test55(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test56(self) -> None:
        hn = HumanName("Dr. Juan Velasquez y Garcia")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test57(self) -> None:
        hn = HumanName("Dr. Juan Velasquez y Garcia, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test58(self) -> None:
        hn = HumanName("Dr. Juan Velasquez y Garcia III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test59(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test60(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test61(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan III")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test62(self) -> None:
        hn = HumanName("Juan Q. de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test63(self) -> None:
        hn = HumanName("Juan Q. de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test64(self) -> None:
        hn = HumanName("Juan Q. de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.suffix, "III", hn)

    def test65(self) -> None:
        hn = HumanName("de la Vega, Juan Q.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test66(self) -> None:
        hn = HumanName("de la Vega, Juan Q., Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test67(self) -> None:
        hn = HumanName("de la Vega, Juan Q. III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "III", hn)

    def test68(self) -> None:
        hn = HumanName("Juan Q. Velasquez y Garcia")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test69(self) -> None:
        hn = HumanName("Juan Q. Velasquez y Garcia, Jr.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test70(self) -> None:
        hn = HumanName("Juan Q. Velasquez y Garcia III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test71(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan Q.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test72(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan Q., Jr.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test73(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan Q. III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test74(self) -> None:
        hn = HumanName("Dr. Juan Q. de la Vega")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test75(self) -> None:
        hn = HumanName("Dr. Juan Q. de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test76(self) -> None:
        hn = HumanName("Dr. Juan Q. de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.suffix, "III", hn)

    def test77(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan Q.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)

    def test78(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan Q., Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "Jr.", hn)
        self.m(hn.title, "Dr.", hn)

    def test79(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan Q. III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.suffix, "III", hn)
        self.m(hn.title, "Dr.", hn)

    def test80(self) -> None:
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test81(self) -> None:
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia, Jr.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test82(self) -> None:
        hn = HumanName("Dr. Juan Q. Velasquez y Garcia III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test83(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q.")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test84(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q., Jr.")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test85(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. III")
        self.m(hn.middle, "Q.", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test86(self) -> None:
        hn = HumanName("Juan Q. Xavier de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.last, "de la Vega", hn)

    def test87(self) -> None:
        hn = HumanName("Juan Q. Xavier de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test88(self) -> None:
        hn = HumanName("Juan Q. Xavier de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test89(self) -> None:
        hn = HumanName("de la Vega, Juan Q. Xavier")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.last, "de la Vega", hn)

    def test90(self) -> None:
        hn = HumanName("de la Vega, Juan Q. Xavier, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test91(self) -> None:
        hn = HumanName("de la Vega, Juan Q. Xavier III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test92(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier de la Vega")
        self.m(hn.first, "Juan", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "de la Vega", hn)

    def test93(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier de la Vega, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test94(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier de la Vega III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test95(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier")
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.last, "de la Vega", hn)

    def test96(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier, Jr.")
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test97(self) -> None:
        hn = HumanName("de la Vega, Dr. Juan Q. Xavier III")
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "de la Vega", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.suffix, "III", hn)

    def test98(self) -> None:
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test99(self) -> None:
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test100(self) -> None:
        hn = HumanName("Juan Q. Xavier Velasquez y Garcia III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test101(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test102(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test103(self) -> None:
        hn = HumanName("Velasquez y Garcia, Juan Q. Xavier III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test104(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test105(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test106(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier Velasquez y Garcia III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test107(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)

    def test108(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier, Jr.")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "Jr.", hn)

    def test109(self) -> None:
        hn = HumanName("Velasquez y Garcia, Dr. Juan Q. Xavier III")
        self.m(hn.middle, "Q. Xavier", hn)
        self.m(hn.first, "Juan", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test110(self) -> None:
        hn = HumanName("John Doe, CLU, CFP, LUTC")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test111(self) -> None:
        hn = HumanName("John P. Doe, CLU, CFP, LUTC")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test112(self) -> None:
        hn = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.m(hn.first, "John", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.last, "Doe-Ray", hn)
        self.m(hn.title, "Dr.", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test113(self) -> None:
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(hn.title, "Dr.", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe-Ray", hn)
        self.m(hn.suffix, "CLU, CFP, LUTC", hn)

    def test115(self) -> None:
        hn = HumanName("Hon. Barrington P. Doe-Ray, Jr.")
        self.m(hn.title, "Hon.", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.first, "Barrington", hn)
        self.m(hn.last, "Doe-Ray", hn)

    def test116(self) -> None:
        hn = HumanName("Doe-Ray, Hon. Barrington P. Jr., CFP, LUTC")
        self.m(hn.title, "Hon.", hn)
        self.m(hn.middle, "P.", hn)
        self.m(hn.first, "Barrington", hn)
        self.m(hn.last, "Doe-Ray", hn)
        self.m(hn.suffix, "Jr., CFP, LUTC", hn)

    def test117(self) -> None:
        hn = HumanName("Rt. Hon. Paul E. Mary")
        self.m(hn.title, "Rt. Hon.", hn)
        self.m(hn.first, "Paul", hn)
        self.m(hn.middle, "E.", hn)
        self.m(hn.last, "Mary", hn)

    def test119(self) -> None:
        hn = HumanName("Lord God Almighty")
        self.m(hn.title, "Lord", hn)
        self.m(hn.first, "God", hn)
        self.m(hn.last, "Almighty", hn)
