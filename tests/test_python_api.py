import copy
import pickle
import re

import pytest

try:
    import dill
except ImportError:
    dill = False  # type: ignore[assignment]

from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants, TupleManager

from tests.base import HumanNameTestBase


class HumanNamePythonTests(HumanNameTestBase):

    def test_utf8(self) -> None:
        hn = HumanName("de la Véña, Jüan")
        self.m(hn.first, "Jüan", hn)
        self.m(hn.last, "de la Véña", hn)

    def test_string_output(self) -> None:
        hn = HumanName("de la Véña, Jüan")
        self.m(str(hn), "Jüan de la Véña", hn)

    def test_escaped_utf8_bytes(self) -> None:
        hn = HumanName(b'B\xc3\xb6ck, Gerald')
        self.m(hn.first, "Gerald", hn)
        self.m(hn.last, "Böck", hn)

    def test_len(self) -> None:
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(len(hn), 5, hn)
        hn = HumanName("John Doe")
        self.m(len(hn), 2, hn)

    @pytest.mark.skipif(not dill, reason="requires python-dill module to test pickling")
    def test_config_pickle(self) -> None:
        constants = Constants()
        self.assertTrue(dill.pickles(constants))

    @pytest.mark.skipif(not dill, reason="requires python-dill module to test pickling")
    def test_name_instance_pickle(self) -> None:
        hn = HumanName("Title First Middle Middle Last, Jr.")
        self.assertTrue(dill.pickles(hn))

    def test_name_instance_pickle_preserves_instance_config(self) -> None:
        """A HumanName carrying its own config must parse identically after a
        pickle round-trip.

        HumanName pickles its instance Constants (``.C``) through the default
        __dict__ path, so a broken Constants round-trip silently produced a
        differently-configured parser on the other side.
        """
        # Passing None as the second argument gives this name its own Constants.
        hn = HumanName("Smith, Dr. John", None)
        hn.C.titles.add('chancellor')
        hn.parse_full_name()

        # Safe: round-tripping a HumanName the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(hn))

        self.assertIn('chancellor', restored.C.titles)
        restored.full_name = "Chancellor Jane Smith"
        self.assertEqual(restored.title, "Chancellor")

    def test_name_instance_deepcopy(self) -> None:
        """copy.deepcopy of a HumanName must round-trip.

        HumanName has no custom copy hooks, so deepcopy recurses into its
        Constants (`.C`), and previously into `.C.regexes`, whose __getattr__
        answered copy's __deepcopy__ probe with a re.Pattern — making
        deepcopy of *any* HumanName raise TypeError.
        """
        hn = HumanName("Dr. John P. Doe-Ray, CLU")

        dup = copy.deepcopy(hn)

        self.assertEqual(str(dup), str(hn))

    def test_name_instance_deepcopy_isolates_instance_config(self) -> None:
        """A deep-copied HumanName with its own config must be independent."""
        hn = HumanName("Smith, Dr. John", None)
        hn.C.titles.add('chancellor')

        dup = copy.deepcopy(hn)
        dup.C.titles.add('marker')

        self.assertIn('chancellor', dup.C.titles)
        self.assertNotIn('marker', hn.C.titles)

    def test_pickle_default_name_preserves_singleton_identity(self) -> None:
        """A default HumanName must re-attach to CONSTANTS after a pickle round-trip.

        Without __getstate__/__setstate__, pickle serializes .C by value, so the
        restored name gets a detached copy — has_own_config flips to True and
        every pickled default name carries a full Constants copy.
        """
        hn = HumanName("John Doe")
        self.assertFalse(hn.has_own_config)
        self.assertIs(hn.C, CONSTANTS)

        # Safe: round-tripping an object we just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(hn))

        self.assertIs(restored.C, CONSTANTS)
        self.assertFalse(restored.has_own_config)
        self.assertEqual(str(restored), str(hn))
        self.assertEqual(restored.first, hn.first)
        self.assertEqual(restored.last, hn.last)

    def test_pickle_instance_config_name_preserves_own_config(self) -> None:
        """A HumanName with its own Constants must not be collapsed onto CONSTANTS after pickle."""
        hn = HumanName("Smith, Dr. John", None)
        hn.C.titles.add('chancellor')
        hn.parse_full_name()
        self.assertTrue(hn.has_own_config)
        self.assertIsNot(hn.C, CONSTANTS)

        # Safe: round-tripping a HumanName the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(hn))

        self.assertTrue(restored.has_own_config)
        self.assertIsNot(restored.C, CONSTANTS)
        self.assertIn('chancellor', restored.C.titles)

    def test_shallow_copy_default_name_preserves_singleton_identity(self) -> None:
        """copy.copy of a default HumanName shares the CONSTANTS reference without hooks."""
        hn = HumanName("John Doe")

        sc = copy.copy(hn)

        self.assertIs(sc.C, CONSTANTS)
        self.assertFalse(sc.has_own_config)

    def test_deepcopy_default_name_preserves_singleton_identity(self) -> None:
        """copy.deepcopy of a default HumanName must re-attach to CONSTANTS."""
        hn = HumanName("John Doe")

        dup = copy.deepcopy(hn)

        self.assertIs(dup.C, CONSTANTS)
        self.assertFalse(dup.has_own_config)
        self.assertEqual(str(dup), str(hn))
        self.assertEqual(dup.first, hn.first)
        self.assertEqual(dup.last, hn.last)

    def test_comparison(self) -> None:
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1 == hn2)
        self.assertIsNot(hn1, hn2)
        self.assertTrue(hn1 == "Dr. John P. Doe-Ray CLU, CFP, LUTC")
        hn1 = HumanName("Doe, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(not hn1 == hn2)
        self.assertTrue(not hn1 == 0)
        self.assertTrue(not hn1 == "test")
        self.assertTrue(not hn1 == ["test"])
        self.assertTrue(not hn1 == {"test": hn2})

    def test_assignment_to_full_name(self) -> None:
        hn = HumanName("John A. Kenneth Doe, Jr.")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.middle, "A. Kenneth", hn)
        self.m(hn.suffix, "Jr.", hn)
        hn.full_name = "Juan Velasquez y Garcia III"
        self.m(hn.first, "Juan", hn)
        self.m(hn.last, "Velasquez y Garcia", hn)
        self.m(hn.suffix, "III", hn)

    def test_get_full_name_attribute_references_internal_lists(self) -> None:
        hn = HumanName("John Williams")
        hn.first_list = ["Larry"]
        self.m(hn.full_name, "Larry Williams", hn)

    def test_assignment_to_attribute(self) -> None:
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
        with pytest.raises(TypeError):
            hn.suffix = [['test']]
        with pytest.raises(TypeError):
            hn.suffix = {"test": "test"}

    def test_assign_list_to_attribute(self) -> None:
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

    def test_comparison_case_insensitive(self) -> None:
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1 == hn2)
        self.assertIsNot(hn1, hn2)
        self.assertTrue(hn1 == "Dr. John P. Doe-ray clu, CFP, LUTC")

    def test_slice(self) -> None:
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(list(hn), ['Dr.', 'John', 'P.', 'Doe-Ray', 'CLU, CFP, LUTC'], hn)
        self.m(hn[1:], ['John', 'P.', 'Doe-Ray', 'CLU, CFP, LUTC', hn.C.empty_attribute_default, hn.C.empty_attribute_default], hn)
        self.m(hn[1:-3], ['John', 'P.', 'Doe-Ray'], hn)

    def test_getitem(self) -> None:
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        self.m(hn['title'], "Dr.", hn)
        self.m(hn['first'], "John", hn)
        self.m(hn['last'], "Doe", hn)
        self.m(hn['middle'], "A. Kenneth", hn)
        self.m(hn['suffix'], "Jr.", hn)

    def test_setitem(self) -> None:
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        hn['title'] = 'test'
        self.m(hn['title'], "test", hn)
        hn['last'] = ['test', 'test2']
        self.m(hn['last'], "test test2", hn)
        with pytest.raises(TypeError):
            hn["suffix"] = [['test']]
        with pytest.raises(TypeError):
            hn["suffix"] = {"test": "test"}

    def test_conjunction_names(self) -> None:
        hn = HumanName("johnny y")
        self.m(hn.first, "johnny", hn)
        self.m(hn.last, "y", hn)

    def test_prefix_names(self) -> None:
        hn = HumanName("vai la")
        self.m(hn.first, "vai", hn)
        self.m(hn.last, "la", hn)

    def test_blank_name(self) -> None:
        hn = HumanName()
        self.m(hn.first, "", hn)
        self.m(hn.last, "", hn)

    def test_surnames_list_attribute(self) -> None:
        hn = HumanName("John Edgar Casey Williams III")
        self.m(hn.surnames_list, ["Edgar", "Casey", "Williams"], hn)

    def test_surnames_attribute(self) -> None:
        hn = HumanName("John Edgar Casey Williams III")
        self.m(hn.surnames, "Edgar Casey Williams", hn)

    def test_given_names_list_attribute(self) -> None:
        hn = HumanName("John Edgar Casey Williams III")
        self.m(hn.given_names_list, ["John", "Edgar", "Casey"], hn)

    def test_given_names_attribute(self) -> None:
        hn = HumanName("John Edgar Casey Williams III")
        self.m(hn.given_names, "John Edgar Casey", hn)

    def test_given_names_attribute_first_only(self) -> None:
        hn = HumanName("John Williams")
        self.m(hn.given_names_list, ["John"], hn)
        self.m(hn.given_names, "John", hn)

    def test_given_names_attribute_empty(self) -> None:
        hn = HumanName("Dr. Williams")
        self.m(hn.given_names, hn.C.empty_attribute_default, hn)

    def test_is_prefix_with_list(self) -> None:
        hn = HumanName()
        items = ['firstname', 'lastname', 'del']
        self.assertTrue(hn.is_prefix(items))
        self.assertTrue(hn.is_prefix(items[1:]))

    def test_is_conjunction_with_list(self) -> None:
        hn = HumanName()
        items = ['firstname', 'lastname', 'and']
        self.assertTrue(hn.is_conjunction(items))
        self.assertTrue(hn.is_conjunction(items[1:]))

    def test_override_constants(self) -> None:
        C = Constants()
        hn = HumanName(constants=C)
        self.assertIs(hn.C, C)

    def test_override_regex(self) -> None:
        var = TupleManager([("spaces", re.compile(r"\s+")),])
        C = Constants(regexes=var)
        hn = HumanName(constants=C)
        self.assertTrue(hn.C.regexes == var)

    def test_override_titles(self) -> None:
        var = ["abc","def"]
        C = Constants(titles=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.titles) == sorted(var))

    def test_override_first_name_titles(self) -> None:
        var = ["abc","def"]
        C = Constants(first_name_titles=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.first_name_titles) == sorted(var))

    def test_override_prefixes(self) -> None:
        var = ["abc","def"]
        C = Constants(prefixes=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.prefixes) == sorted(var))

    def test_override_suffix_acronyms(self) -> None:
        var = ["abc","def"]
        C = Constants(suffix_acronyms=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.suffix_acronyms) == sorted(var))

    def test_override_suffix_not_acronyms(self) -> None:
        var = ["abc","def"]
        C = Constants(suffix_not_acronyms=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.suffix_not_acronyms) == sorted(var))

    def test_override_conjunctions(self) -> None:
        var = ["abc","def"]
        C = Constants(conjunctions=var)
        hn = HumanName(constants=C)
        self.assertTrue(sorted(hn.C.conjunctions) == sorted(var))

    def test_override_capitalization_exceptions(self) -> None:
        var = TupleManager([("spaces", re.compile(r"\s+")),])
        C = Constants(capitalization_exceptions=var)
        hn = HumanName(constants=C)
        self.assertTrue(hn.C.capitalization_exceptions == var)
