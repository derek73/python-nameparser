from nameparser import HumanName

from tests.base import HumanNameTestBase

from types import SimpleNamespace


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
    "Herr Klaus Schmidt",
    "Frau Anna Müller",
    "Monsieur Jean Dupont",
    "Señor Carlos García",
    "Señora María García",
    "Signor Marco Rossi",
    "Mevrouw Anna de Vries",

)


class HumanNameVariationTests(HumanNameTestBase):
    # test automated variations of names in TEST_NAMES.
    # Helps test that the 3 code trees work the same

    TEST_NAMES = TEST_NAMES

    def test_variations_of_TEST_NAMES(self) -> None:
        for name in self.TEST_NAMES:
            hn = HumanName(name)
            if len(hn.suffix_list) > 1:
                d = SimpleNamespace(**hn.as_dict())
                hn = HumanName(f"{d.title} {d.first} {d.middle} {d.last} {d.suffix}".split(',')[0])
            # v1 forced empty_attribute_default='' here so the format
            # strings below got '' for empty parts; 2.0 removed the setting
            # (#255) and empty attributes are always '' -- nothing to force.
            d = SimpleNamespace(**hn.as_dict())
            nocomma = HumanName(f"{d.title} {d.first} {d.middle} {d.last} {d.suffix}")
            lastnamecomma = HumanName(f"{d.last}, {d.title} {d.first} {d.middle} {d.suffix}")
            if d.suffix:
                suffixcomma = HumanName(f"{d.title} {d.first} {d.middle} {d.last}, {d.suffix}")
            if d.nickname:
                nocomma = HumanName(f"{d.title} {d.first} {d.middle} {d.last} {d.suffix} ({d.nickname})")
                lastnamecomma = HumanName(f"{d.last}, {d.title} {d.first} {d.middle} {d.suffix} ({d.nickname})")
                if d.suffix:
                    suffixcomma = HumanName(f"{d.title} {d.first} {d.middle} {d.last}, {d.suffix} ({d.nickname})")
            # v1 iterated the private hn._members; 2.0's public equivalent
            # is the as_dict() key set (same seven fields)
            for attr in hn.as_dict():
                self.m(getattr(hn, attr), getattr(nocomma, attr), hn)
                self.m(getattr(hn, attr), getattr(lastnamecomma, attr), hn)
                if hn.suffix:
                    self.m(getattr(hn, attr), getattr(suffixcomma, attr), hn)
