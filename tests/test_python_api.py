import copy
import pickle
import re
import warnings

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
        # bytes input was removed in 2.0 (#245, warned since 1.3.0):
        # decode first
        with pytest.raises(TypeError, match="decode"):
            HumanName(b'B\xc3\xb6ck, Gerald')  # type: ignore[arg-type]
        hn = HumanName(b'B\xc3\xb6ck, Gerald'.decode('utf-8'))
        self.m(hn.first, "Gerald", hn)
        self.m(hn.last, "Böck", hn)

    def test_bytes_full_name_raises_with_decode_hint(self) -> None:
        # bytes input was removed in 2.0 (#245); both entry points raise
        with pytest.raises(TypeError, match="decode"):
            HumanName(b'John Smith')  # type: ignore[arg-type]
        hn = HumanName("Jane Doe")
        with pytest.raises(TypeError, match="decode"):
            hn.full_name = b'John Smith'  # type: ignore[assignment]
        # the failed assignment must not have corrupted the parse
        self.m(hn.first, "Jane", hn)

    def test_str_full_name_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            hn = HumanName("John Smith")
            hn.full_name = "Jane Doe"
        self.m(hn.first, "Jane", hn)

    def test_len(self) -> None:
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(len(hn), 5, hn)
        hn = HumanName("John Doe")
        self.m(len(hn), 2, hn)
        # empty input parses to an all-empty name; len == 0 is the
        # documented emptiness check (see usage.rst)
        self.assertEqual(len(HumanName("")), 0)

    def test_iteration_restarts_after_break(self) -> None:
        hn = HumanName("John Doe")
        for _ in hn:
            break
        # a plain loop, not list(hn): list() presizes via __len__, which
        # under the old shared-cursor implementation reset the cursor and
        # masked this bug
        collected = []
        for part in hn:
            collected.append(part)
        self.assertEqual(collected, ["John", "Doe"])

    def test_iterators_are_independent(self) -> None:
        hn = HumanName("John Doe")
        it1 = iter(hn)
        it2 = iter(hn)
        self.assertEqual(next(it1), "John")
        self.assertEqual(next(it2), "John")
        self.assertEqual(next(it1), "Doe")
        self.assertEqual(next(it2), "Doe")

    def test_len_during_iteration(self) -> None:
        hn = HumanName("John Doe")
        it = iter(hn)
        self.assertEqual(next(it), "John")
        # len() must count all members and leave the live iterator intact
        self.assertEqual(len(hn), 2)
        self.assertEqual(next(it), "Doe")

    def test_instance_is_not_its_own_iterator(self) -> None:
        # iterator state must never live on the instance; see release log
        # for the next(name) -> next(iter(name)) migration
        hn = HumanName("John Doe")
        with pytest.raises(TypeError):
            next(hn)  # type: ignore[call-overload]

    def test_iterating_empty_name_yields_nothing(self) -> None:
        collected = []
        for part in HumanName(""):
            collected.append(part)
        self.assertEqual(collected, [])

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
        hn = HumanName("Smith, Dr. John", Constants())
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
        hn = HumanName("Smith, Dr. John", Constants())
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
        hn = HumanName("Smith, Dr. John", Constants())
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
        # == and hash reverted to object identity in 2.0 (#223, warned since
        # 1.3.0): distinct instances never compare equal, however they parse,
        # and strings never match. matches()/comparison_key() are the
        # replacements (covered below).
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("Dr. John P. Doe-Ray, CLU, CFP, LUTC")
        self.assertTrue(hn1 == hn1)
        self.assertFalse(hn1 == hn2)
        self.assertIsNot(hn1, hn2)
        self.assertFalse(hn1 == "Dr. John P. Doe-Ray CLU, CFP, LUTC")
        self.assertTrue(hn1.matches(hn2))  # the 2.0 spelling of the old ==
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
            hn.suffix = [['test']]  # type: ignore[list-item]
        with pytest.raises(TypeError):
            hn.suffix = {"test": "test"}  # type: ignore[assignment]

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
        # 2.0 identity semantics (#223): equivalently-parsed instances no
        # longer compare ==; matches() carries the case-insensitive
        # component comparison instead
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assertFalse(hn1 == hn2)
        self.assertIsNot(hn1, hn2)
        self.assertFalse(hn1 == "Dr. John P. Doe-ray clu, CFP, LUTC")
        self.assertTrue(hn1.matches(hn2))
        self.assertTrue(hn1.matches("Dr. John P. Doe-ray clu, CFP, LUTC"))

    def test_hash_is_identity_based(self) -> None:
        # 2.0 identity semantics (#223): hash reverted to the object default,
        # consistent with identity ==; equal-parsing instances stay distinct
        # in sets/dicts. comparison_key() is the dedup replacement.
        hn1 = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        hn2 = HumanName("dr. john p. doe-Ray, CLU, CFP, LUTC")
        self.assertEqual(hash(hn1), object.__hash__(hn1))
        self.assertEqual(len({hn1, hn2}), 2)
        # strings no longer interoperate with HumanName in sets/dicts
        hn = HumanName("John Smith")
        self.assertNotEqual(hash(hn), hash("john smith"))
        self.assertNotIn("john smith", {hn})
        self.assertEqual(hn1.comparison_key(), hn2.comparison_key())

    def test_not_equal_operator(self) -> None:
        # != routes through the 2.0 identity __eq__ (#223): any two distinct
        # instances are unequal, however similar their parse
        self.assertTrue(HumanName("John Smith") != HumanName("Jane Smith"))
        self.assertTrue(HumanName("John Smith") != HumanName("john smith"))
        hn = HumanName("John Smith")
        self.assertFalse(hn != hn)

    def test_comparison_key_components(self) -> None:
        hn = HumanName("Dr. Juan Q. Xavier de la Vega III")
        self.assertEqual(
            hn.comparison_key(),
            ('dr.', 'juan', 'q. xavier', 'de la vega', 'iii', '', ''))

    def test_comparison_key_case_insensitive_across_formats(self) -> None:
        hn1 = HumanName("Dr. Juan Q. Xavier de la Vega III")
        hn2 = HumanName("de la vega, dr. juan Q. xavier III")
        self.assertEqual(hn1.comparison_key(), hn2.comparison_key())

    def test_comparison_key_independent_of_string_format(self) -> None:
        # unlike ==, which compares str(self) and so changes meaning when
        # display config changes, the key is built from the parsed lists
        hn1 = HumanName("John Smith")
        hn2 = HumanName("John Smith", string_format="{last}")
        self.assertEqual(hn1.comparison_key(), hn2.comparison_key())

    def test_comparison_key_includes_maiden(self) -> None:
        # maiden isn't in the default string_format, so == can't see it;
        # the key includes all seven members
        hn1 = HumanName(first="Jenny", last="Baker", maiden="Johnson")
        hn2 = HumanName(first="Jenny", last="Baker")
        self.assertNotEqual(hn1.comparison_key(), hn2.comparison_key())

    def test_comparison_key_usable_for_dedup(self) -> None:
        names = [HumanName("John Smith"), HumanName("Smith, John"),
                 HumanName("JOHN SMITH"), HumanName("Jane Smith")]
        unique = {n.comparison_key(): n for n in names}
        self.assertEqual(len(unique), 2)

    def test_matches_str_is_semantic_not_textual(self) -> None:
        # any written form of the same name matches, unlike == which only
        # matches strings that render exactly like str(self)
        hn = HumanName("Dr. Juan Q. Xavier de la Vega III")
        self.assertTrue(hn.matches("de la vega, dr. juan Q. xavier III"))
        self.assertTrue(hn.matches("Dr. Juan Q. Xavier de la Vega III"))
        self.assertFalse(hn.matches("Juan de la Vega"))

    def test_matches_humanname_operand(self) -> None:
        hn = HumanName("John Smith")
        self.assertTrue(hn.matches(HumanName("JOHN SMITH")))
        self.assertFalse(hn.matches(HumanName("Jane Smith")))

    def test_matches_parses_str_with_instance_constants(self) -> None:
        # the custom title must not be a default one ('chancellor' is!), or
        # this passes without the self.C parse path ever mattering
        c = Constants()
        c.titles.add('zephyrmark')
        self.assertNotIn('zephyrmark', CONSTANTS.titles)
        hn = HumanName("Zephyrmark Jane Smith", constants=c)
        # the str operand is parsed with self.C, so the custom title is
        # recognized in the comma form; parsed with the shared CONSTANTS,
        # 'zephyrmark' would land in first/middle and the keys would differ
        self.assertTrue(hn.matches("smith, zephyrmark jane"))

    def test_matches_humanname_operand_keeps_its_own_parse(self) -> None:
        # asymmetry, pinned deliberately: a str operand is reparsed with
        # self.C, but a HumanName operand is compared as already parsed --
        # its own constants determined its components
        c = Constants()
        c.titles.add('zephyrmark')
        with_title = HumanName("Zephyrmark Jane Smith", constants=c)
        default_parse = HumanName("Zephyrmark Jane Smith")
        self.assertTrue(with_title.matches("Zephyrmark Jane Smith"))
        self.assertFalse(with_title.matches(default_parse))

    def test_empty_parses_share_a_comparison_key(self) -> None:
        # documented caveat: empty/unparsable input collapses to the
        # all-empty key, so such names match each other and collide in
        # dedup; screen with len(name) == 0 first
        self.assertTrue(HumanName("").matches(HumanName(",")))
        self.assertEqual(HumanName("()").comparison_key(),
                         HumanName("").comparison_key())

    def test_matches_non_ascii_case_insensitive(self) -> None:
        hn = HumanName("JOSÉ GARCÍA")
        self.assertTrue(hn.matches("José García"))

    def test_matches_rejects_other_types(self) -> None:
        hn = HumanName("John Smith")
        for bad in (None, 42, b"John Smith", ["John Smith"]):
            with pytest.raises(TypeError, match="str or HumanName"):
                hn.matches(bad)  # type: ignore[arg-type]

    def test_eq_and_hash_are_silent_in_2_0(self) -> None:
        # the 1.3.0/1.4 DeprecationWarnings on __eq__/__hash__ ended with the
        # 2.0 switch to identity semantics (#223): both are now warning-free
        hn1 = HumanName("John Smith")
        hn2 = HumanName("john smith")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertFalse(hn1 == hn2)
            hash(hn1)

    def test_new_comparison_api_does_not_warn(self) -> None:
        # the replacements must be adoptable before 2.0 without tripping
        # -W error test suites; matches(str) parses, so this also covers
        # the parse path
        hn = HumanName("John Smith")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            hn.comparison_key()
            hn.matches("Smith, John")
            hn.matches(HumanName("John Smith"))

    def test_unparsable_attribute_removed(self) -> None:
        # Removed in 1.3.0: the guard that reported unparsable names was
        # unreachable, so the attribute was always False after any parse.
        self.assertFalse(hasattr(HumanName("John Smith"), "unparsable"))
        self.assertFalse(hasattr(HumanName(first="John"), "unparsable"))

    def test_str_fallback_without_string_format(self) -> None:
        # string_format=None falls back to joining the non-empty attributes
        hn = HumanName("Dr. John A. Doe, Jr.")
        hn.string_format = None
        self.assertEqual(str(hn), "Dr. John A. Doe Jr.")

    def test_repr_blank_name(self) -> None:
        hn = HumanName()
        self.assertIn("first: ''", repr(hn))
        self.assertIn(hn.__class__.__name__, repr(hn))

    def test_slice_removed(self) -> None:
        # slice access was removed in 2.0 (#258, warned since 1.4); iteration
        # and string-key access are the remaining spellings
        hn = HumanName("Doe-Ray, Dr. John P., CLU, CFP, LUTC")
        self.m(list(hn), ['Dr.', 'John', 'P.', 'Doe-Ray', 'CLU, CFP, LUTC'], hn)
        with pytest.raises(TypeError, match="258"):
            hn[1:]  # type: ignore[index]
        with pytest.raises(TypeError, match="258"):
            hn[1:-3]  # type: ignore[index]
        # string-key access is unaffected and stays silent
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            hn['first']

    def test_getitem(self) -> None:
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        self.m(hn['title'], "Dr.", hn)
        self.m(hn['first'], "John", hn)
        self.m(hn['last'], "Doe", hn)
        self.m(hn['middle'], "A. Kenneth", hn)
        self.m(hn['suffix'], "Jr.", hn)

    def test_setitem_removed(self) -> None:
        # __setitem__ was removed in 2.0 (#258, warned since 1.4): item
        # assignment raises TypeError for every key, valid or not; plain
        # attribute assignment is the replacement
        hn = HumanName("Dr. John A. Kenneth Doe, Jr.")
        with pytest.raises(TypeError, match="item assignment"):
            hn['title'] = 'test'  # type: ignore[index]
        with pytest.raises(TypeError, match="item assignment"):
            hn['bogus'] = 'value'  # type: ignore[index]
        hn.first = 'Jane'  # the replacement spelling
        self.m(hn.first, "Jane", hn)

    def test_conjunction_names(self) -> None:
        hn = HumanName("johnny y")
        self.m(hn.first, "johnny", hn)
        self.m(hn.last, "y", hn)

    def test_prefix_names(self) -> None:
        hn = HumanName("vai la")
        self.m(hn.first, "vai", hn)
        self.m(hn.last, "la", hn)

    def test_degenerate_comma_input_leaves_no_empty_pieces(self) -> None:
        # Regression: HumanName(',') (no-comma path after whitespace collapse)
        # and HumanName('Doe,, Jr.') (lastname-comma path) appended '' to
        # first_list — a silent empty member in the public *_list attributes.
        hn = HumanName(",")
        self.assertEqual(hn.first_list, [])
        self.assertEqual(hn.middle_list, [])
        self.assertEqual(hn.last_list, [])
        self.assertEqual(len(hn), 0)
        hn = HumanName("Doe,, Jr.")
        self.assertEqual(hn.first_list, [])
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "Jr.", hn)
        # empty parts[0] exercises the lastname_pieces call site: the empty
        # last-name segment must not become a member of last_list
        hn = HumanName(", John")
        self.assertEqual(hn.last_list, [])
        self.m(hn.first, "John", hn)

    def test_assignment_filters_empty_tokens(self) -> None:
        # parse_pieces() drops tokens that strip to nothing at every entry
        # point, including the setters: whitespace-only strings and empty
        # list members never become *_list members (they previously survived,
        # e.g. hn.first = '  ' left first == '  ' and middle 'a  b' gained an
        # empty member from ['a', '', 'b']).
        hn = HumanName("John Doe")
        hn.first = "  "
        self.assertEqual(hn.first_list, [])
        self.m(hn.first, "", hn)
        hn.middle = ["a", "", "b"]
        self.assertEqual(hn.middle_list, ["a", "b"])
        self.m(hn.middle, "a b", hn)
        hn.last = ["", "Smith"]
        self.assertEqual(hn.last_list, ["Smith"])

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
        # empty attributes are always '' in 2.0 (#255)
        hn = HumanName("Dr. Williams")
        self.m(hn.given_names, "", hn)

    def test_override_constants(self) -> None:
        C = Constants()
        hn = HumanName(constants=C)
        self.assertIs(hn.C, C)

    def test_override_regex_raises(self) -> None:
        # Custom regexes are not supported in 2.0 (deliberate divergence,
        # shim's uniform read-only rule): the constructor kwarg raises the
        # same TypeError as attribute assignment, pointing at named Policy
        # flags. Reads of the built-in patterns stay available.
        var = TupleManager([("spaces", re.compile(r"\s+")),])
        with pytest.raises(TypeError, match="Policy"):
            Constants(regexes=var)  # type: ignore[call-arg]

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
        var = TupleManager([("abc", "ABC")])
        C = Constants(capitalization_exceptions=var)
        hn = HumanName(constants=C)
        self.assertTrue(hn.C.capitalization_exceptions == var)
