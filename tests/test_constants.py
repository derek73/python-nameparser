import copy
import pickle
import re
import timeit
import warnings
from typing import Any

import pytest

from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants, RegexTupleManager, SetManager, TupleManager
from nameparser.config.regexes import EMPTY_REGEX
from nameparser.config.titles import TITLES

from tests.base import HumanNameTestBase


class ConstantsCustomizationTests(HumanNameTestBase):

    def test_add_title(self) -> None:
        hn = HumanName("Te Awanui-a-Rangi Black", constants=Constants())
        start_len = len(hn.C.titles)
        self.assertTrue(start_len > 0)
        hn.C.titles.add('te')
        self.assertEqual(start_len + 1, len(hn.C.titles))
        hn.parse_full_name()
        self.m(hn.title, "Te", hn)
        self.m(hn.first, "Awanui-a-Rangi", hn)
        self.m(hn.last, "Black", hn)

    def test_constants_subclass_instance_is_used(self) -> None:
        class CustomConstants(Constants):
            pass

        c = CustomConstants()
        c.titles.add('chancellor')
        hn = HumanName("Chancellor Jane Smith", constants=c)
        self.assertIs(hn.C, c)
        self.m(hn.title, "Chancellor", hn)
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Smith", hn)

    def test_constants_invalid_type_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="constants must be"):
            HumanName("John Doe", constants="not a Constants")  # type: ignore[arg-type]

    def test_constants_class_instead_of_instance_raises_with_hint(self) -> None:
        with pytest.raises(TypeError, match=r"did you mean Constants\(\)"):
            HumanName("John Doe", constants=Constants)  # type: ignore[arg-type]

    def test_assigning_invalid_constants_after_construction_raises(self) -> None:
        # #226 validated the constructor's `constants` argument, but `hn.C = ...`
        # bypassed it entirely: the bad value was accepted silently and only
        # surfaced far later, deep inside parsing, with no mention of `C` (#239)
        hn = HumanName("John Doe")
        with pytest.raises(TypeError, match="constants must be"):
            hn.C = "garbage"  # type: ignore[assignment]

    def test_assigning_constants_class_after_construction_raises_with_hint(self) -> None:
        hn = HumanName("John Doe")
        with pytest.raises(TypeError, match=r"did you mean Constants\(\)"):
            hn.C = Constants  # type: ignore[assignment]

    def test_assigning_none_to_constants_after_construction_builds_new_instance(self) -> None:
        hn = HumanName("John Doe")
        with pytest.deprecated_call():
            hn.C = None
        self.assertIsNot(hn.C, CONSTANTS)
        self.assertTrue(isinstance(hn.C, Constants))

    def test_constants_bare_string_kwarg_raises_typeerror(self) -> None:
        # a bare string is an iterable of its characters, so set('dr') would
        # silently replace the default titles with {'d', 'r'} (#238); the
        # type system can't catch this because str satisfies Iterable[str]
        with pytest.raises(TypeError, match=r"wrap it in a list"):
            Constants(titles='dr')

    def test_set_manager_bare_string_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match=r"wrap it in a list"):
            SetManager('dr')

    def test_set_manager_bytes_raises_with_decode_hint(self) -> None:
        # a "wrap it in a list" hint would be a trap for bytes: [b'dr'] is
        # accepted but its elements never match parsed str tokens
        with pytest.raises(TypeError, match=r"decode it first"):
            SetManager(b'dr')  # type: ignore[arg-type]

    def test_set_manager_bare_string_operand_raises_typeerror(self) -> None:
        # Set's mixin __or__/__and__ hand _from_iterable a generator, so the
        # constructor guard alone never sees a bare-string operand; without
        # an operand check, c.titles |= 'esq' silently adds 'e', 's', 'q'
        sm = SetManager(['dr', 'mr'])
        for op in (lambda: sm | 'abc',
                   lambda: 'abc' | sm,
                   lambda: sm & 'abc',
                   lambda: 'abc' & sm,
                   lambda: sm - 'abc',
                   lambda: sm ^ 'abc'):
            with pytest.raises(TypeError, match=r"wrap it in a list"):
                op()

    def test_set_manager_operators_accept_lists(self) -> None:
        # end-to-end: an operator-built set wired back into Constants must
        # behave like an add()-built one, normalization included
        c = Constants()
        with pytest.raises(TypeError, match=r"wrap it in a list"):
            c.titles |= 'esq'
        c.titles |= ['Esq.']
        self.assertIn('esq', c.titles)
        hn = HumanName("Esq Jane Smith", constants=c)
        self.m(hn.title, "Esq", hn)

    def test_set_manager_operators_normalize_like_add(self) -> None:
        # add() lowercases and strips leading/trailing periods; without the
        # same normalization of operator operands, (titles | ['Esq.']) keeps
        # a raw 'Esq.', which the parser's lc()-based lookups can never match
        # — silently broken config, same failure family as the bare-string
        # shredding (#238)
        sm = SetManager(['dr', 'mr'])
        self.assertEqual((sm | ['Esq.']).elements, {'dr', 'mr', 'esq'})
        self.assertEqual((['Esq.', 'Dr.'] | sm).elements, {'dr', 'mr', 'esq'})
        self.assertEqual((sm & ['Dr.']).elements, {'dr'})
        self.assertEqual((['Dr.'] & sm).elements, {'dr'})
        self.assertEqual((sm - ['Dr.']).elements, {'mr'})
        self.assertEqual((['Dr.', 'Esq.'] - sm).elements, {'esq'})
        self.assertEqual((sm ^ ['Dr.', 'Esq.']).elements, {'mr', 'esq'})
        # pins __rxor__ separately in case it ever stops aliasing __xor__
        self.assertEqual((['Dr.', 'Esq.'] ^ sm).elements, {'mr', 'esq'})

    def test_set_manager_contains_normalizes_like_add(self) -> None:
        # add()/remove()/the constructor/the operators all normalize (lowercase,
        # strip leading/trailing periods) -- __contains__ was the lone holdout,
        # so `'Dr.' in c.titles` returned False even though every other
        # operation on the same value succeeded (#244)
        sm = SetManager(['dr', 'mr'])
        self.assertIn('Dr.', sm)
        self.assertIn('MR', sm)
        self.assertNotIn('Esq.', sm)

    def test_set_manager_le_uses_normalizing_contains(self) -> None:
        # the ABC comparison mixins route through __contains__, so an
        # un-normalized membership check would leak into subset/equality too
        sm = SetManager(['dr', 'mr'])
        self.assertTrue(sm <= SetManager(['dr', 'mr', 'esq']))
        self.assertTrue({'Dr.', 'Mr.'} <= sm)

    def test_set_manager_rsub_is_order_sensitive(self) -> None:
        # __sub__ and __rsub__ are hand-written separately (subtraction
        # isn't commutative, unlike |/&/^), so a copy-paste operand swap
        # in __rsub__ would silently flip the result and nothing else
        # in this file would catch it
        sm = SetManager(['dr', 'mr'])
        self.assertEqual((['Dr.', 'Esq.'] - sm).elements, {'esq'})
        self.assertEqual((sm - ['Dr.', 'Esq.']).elements, {'mr'})

    def test_set_manager_constructor_normalizes_like_add(self) -> None:
        # without constructor normalization the operators misfire against
        # the exact spelling visibly stored in the set: & returns empty
        # and - silently no-ops
        sm = SetManager(['Dr.', 'MR'])
        self.assertEqual(sm.elements, {'dr', 'mr'})
        self.assertEqual((sm & ['Dr.']).elements, {'dr'})
        self.assertEqual((sm - ['Dr.']).elements, {'mr'})

    def test_constants_kwarg_elements_are_normalized(self) -> None:
        # Constants(titles=[...]) was the last silently-dead config path:
        # a raw 'Chemistry' element can never match the parser's lc() lookups
        c = Constants(titles=['chancellor', 'Chemistry'])
        hn = HumanName("Chemistry Jane Smith", constants=c)
        self.m(hn.title, "Chemistry", hn)

    def test_default_constants_construction_does_not_alias_defaults(self) -> None:
        # Constants() reuses the prebuilt _DEFAULT_TITLES snapshot via an
        # identity check instead of re-validating ~1,400 entries; if that
        # fast path ever returned the shared elements set instead of a
        # copy, mutating one Constants() instance would corrupt every
        # other instance's (and the module-level default's) titles
        c1 = Constants()
        c1.titles.add('zzz_should_not_leak')
        c2 = Constants()
        self.assertNotIn('zzz_should_not_leak', c2.titles)
        self.assertNotIn('zzz_should_not_leak', TITLES)

    def test_equal_but_not_identical_titles_list_still_validates(self) -> None:
        # the fast path in Constants.__init__ is an `is` check against the
        # raw TITLES object, not `==`; an equal-but-copied list must still
        # go through full normalization rather than accidentally matching
        c = Constants(titles=list(TITLES) + ['Extra.'])
        self.assertIn('extra', c.titles)

    def test_set_manager_non_str_elements_raise_typeerror(self) -> None:
        # lc() on junk elements either crashes context-free (bytes, int) or
        # silently transmutes None into '' — raise a curated error instead
        with pytest.raises(TypeError, match=r"decode it first"):
            SetManager([b'dr'])  # type: ignore[list-item]
        with pytest.raises(TypeError, match=r"expected str elements"):
            SetManager([None])  # type: ignore[list-item]
        with pytest.raises(TypeError, match=r"expected str elements"):
            SetManager(['dr']) | [1]  # type: ignore[list-item]

    def test_tuplemanager_bare_string_raises_typeerror(self) -> None:
        # dict(['ab', 'cd']) shreds each 2-char string into a key/value pair
        # silently -- and dict('ab') itself raises a cryptic "dictionary update
        # sequence element #0 has length 1; 2 is required" naming no argument
        # and suggesting no fix (#242)
        with pytest.raises(TypeError, match=r"wrap it in a list"):
            TupleManager('ab')  # type: ignore[arg-type]

    def test_tuplemanager_bytes_raises_with_decode_hint(self) -> None:
        with pytest.raises(TypeError, match=r"decode it first"):
            TupleManager(b'ab')  # type: ignore[arg-type]

    def test_tuplemanager_string_element_raises_typeerror(self) -> None:
        # the silent variant: an iterable of 2-character strings is a valid
        # dict-update sequence, so each one shreds into a key/value pair
        with pytest.raises(TypeError, match=r"key and a value"):
            TupleManager(['ab', 'cd'])  # type: ignore[arg-type]

    def test_constants_capitalization_exceptions_string_elements_raise(self) -> None:
        with pytest.raises(TypeError, match=r"key and a value"):
            Constants(capitalization_exceptions=['ii'])  # type: ignore[list-item]

    def test_tuplemanager_accepts_mapping_and_pairs(self) -> None:
        # the guard must not reject the two legitimate constructor shapes
        tm = TupleManager({'a': '1'})
        self.assertEqual(tm.a, '1')
        tm2 = TupleManager([('b', '2')])
        self.assertEqual(tm2.b, '2')

    def test_remove_title(self) -> None:
        hn = HumanName("Hon Solo", constants=Constants())
        start_len = len(hn.C.titles)
        self.assertTrue(start_len > 0)
        hn.C.titles.remove('hon')
        self.assertEqual(start_len - 1, len(hn.C.titles))
        hn.parse_full_name()
        self.m(hn.first, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_add_multiple_arguments(self) -> None:
        hn = HumanName("Assoc Dean of Chemistry Robert Johns", constants=Constants())
        hn.C.titles.add('dean', 'Chemistry')
        hn.parse_full_name()
        self.m(hn.title, "Assoc Dean of Chemistry", hn)
        self.m(hn.first, "Robert", hn)
        self.m(hn.last, "Johns", hn)

    def test_instances_can_have_own_constants(self) -> None:
        hn = HumanName("", Constants())
        hn2 = HumanName("")
        hn.C.titles.remove('hon')
        self.assertEqual('hon' in hn.C.titles, False)
        self.assertEqual(hn.has_own_config, True)
        self.assertEqual('hon' in hn2.C.titles, True)
        self.assertEqual(hn2.has_own_config, False)

    def test_can_change_global_constants(self) -> None:
        hn = HumanName("")
        hn2 = HumanName("")
        hn.C.titles.remove('hon')
        self.assertEqual('hon' in hn.C.titles, False)
        self.assertEqual('hon' in hn2.C.titles, False)
        self.assertEqual(hn.has_own_config, False)
        self.assertEqual(hn2.has_own_config, False)
        # No manual cleanup needed: the autouse fixture in conftest.py snapshots
        # and restores the global CONSTANTS collections around every test.

    def test_can_add_global_nickname_delimiter(self) -> None:
        # https://github.com/derek73/python-nameparser/issues/112
        hn = HumanName("")
        hn.C.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')
        hn2 = HumanName("Benjamin {Ben} Franklin")
        self.assertEqual(hn2.has_own_config, False)
        self.m(hn2.nickname, "Ben", hn2)
        # No manual cleanup needed: the autouse fixture in conftest.py snapshots
        # and restores the global CONSTANTS collections (including
        # nickname_delimiters) around every test.

    def test_remove_multiple_arguments(self) -> None:
        hn = HumanName("Ms Hon Solo", constants=Constants())
        hn.C.titles.remove('hon', 'ms')
        hn.parse_full_name()
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_chain_multiple_arguments(self) -> None:
        hn = HumanName("Dean Ms Hon Solo", constants=Constants())
        hn.C.titles.remove('hon', 'ms').add('dean')
        hn.parse_full_name()
        self.m(hn.title, "Dean", hn)
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_clear_removes_all_entries(self) -> None:
        hn = HumanName("Ms Hon Solo", constants=Constants())
        hn.C.titles.clear()
        hn.parse_full_name()
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_empty_attribute_default_assignment_emits_deprecation_warning(self) -> None:
        # assigning empty_attribute_default is deprecated for removal in 2.0
        # (#255); empty attributes will always return '' once removed
        c = Constants()
        with pytest.deprecated_call(match="255"):
            c.empty_attribute_default = None  # type: ignore[assignment]
        self.assertIsNone(c.empty_attribute_default)

    def test_empty_attribute_default_rejects_non_str_non_none(self) -> None:
        # A cheap early check on the invariant 2.0 will fully enforce (only
        # '' will be legal): non-str/non-None values fail loudly here
        # instead of surfacing later as a confusing failure deep in some
        # unrelated HumanName string property.
        c = Constants()
        with pytest.raises(TypeError, match="str or None"):
            c.empty_attribute_default = 42  # type: ignore[assignment]
        self.assertEqual(c.empty_attribute_default, '')

    def test_empty_attribute_default_read_does_not_warn(self) -> None:
        c = Constants()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(c.empty_attribute_default, '')

    def test_empty_attribute_default(self) -> None:
        from nameparser.config import CONSTANTS
        # empty_attribute_default has no explicit annotation (mypy infers str
        # from the '' default), but None is documented/supported here -- see
        # the doctest on the attribute's docstring in config/__init__.py.
        # Not widened to str | None like string_format/suffix_delimiter
        # because it cascades into every public str-typed name accessor
        # (title, first, middle, last, suffix, nickname, maiden, surnames,
        # given_names, last_base, last_prefixes, initials()).
        with pytest.deprecated_call():
            CONSTANTS.empty_attribute_default = None  # type: ignore[assignment]
        hn = HumanName("")
        self.m(hn.title, None, hn)
        self.m(hn.first, None, hn)
        self.m(hn.middle, None, hn)
        self.m(hn.last, None, hn)
        self.m(hn.suffix, None, hn)
        self.m(hn.nickname, None, hn)

    def test_empty_attribute_on_instance(self) -> None:
        hn = HumanName("", Constants())
        with pytest.deprecated_call():
            hn.C.empty_attribute_default = None  # type: ignore[assignment]  # see test_empty_attribute_default above
        self.m(hn.title, None, hn)
        self.m(hn.first, None, hn)
        self.m(hn.middle, None, hn)
        self.m(hn.last, None, hn)
        self.m(hn.suffix, None, hn)
        self.m(hn.nickname, None, hn)

    def test_none_empty_attribute_string_formatting(self) -> None:
        hn = HumanName("", Constants())
        with pytest.deprecated_call():
            hn.C.empty_attribute_default = None  # type: ignore[assignment]  # see test_empty_attribute_default above
        self.assertEqual('', str(hn), hn)

    def test_add_constant_with_explicit_encoding(self) -> None:
        # bytes input is deprecated (#245), still supported until 2.0
        c = Constants()
        with pytest.deprecated_call():
            c.titles.add_with_encoding(b'b\351ck', encoding='latin_1')
        self.assertIn('béck', c.titles)

    def test_set_manager_add_bytes_emits_deprecation_warning(self) -> None:
        # bytes elements will be removed in 2.0 (#245); the caller should decode
        sm = SetManager(['dr'])
        with pytest.deprecated_call(match="decode"):
            sm.add(b'esq')  # type: ignore[arg-type]  # deliberately deprecated input
        self.assertIn('esq', sm)

    def test_add_with_encoding_str_emits_deprecation_warning(self) -> None:
        # add_with_encoding() itself is deprecated in 1.4 for removal in 2.0
        # (#263/#245); the str path is otherwise silent, so this method's
        # own removal is unwarned without this
        sm = SetManager(['dr'])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            sm.add_with_encoding('esq')
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        # Exactly one -- the str path must not also trip the bytes-decode
        # warning (that one's for the *other* argument type).
        self.assertEqual(len(deprecations), 1)
        self.assertIn('add()', str(deprecations[0].message))
        self.assertIn('esq', sm)

    def test_add_with_encoding_bytes_emits_two_distinct_warnings(self) -> None:
        # the bytes-decode warning (#245, shipped 1.3.0) and the
        # add_with_encoding()-removal warning (#263) are independent
        sm = SetManager(['dr'])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            sm.add_with_encoding(b'esq')
        messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(messages), 2)
        self.assertTrue(any('decode' in m for m in messages))
        self.assertTrue(any('use add() instead' in m for m in messages))

    def test_set_manager_add_str_does_not_warn(self) -> None:
        sm = SetManager(['dr'])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sm.add('esq')
        self.assertIn('esq', sm)

    def test_set_manager_call_emits_deprecation_warning(self) -> None:
        # __call__ hands out the raw underlying set, bypassing normalization
        # and cache invalidation; will be removed in 2.0 (#243)
        sm = SetManager(['dr'])
        with pytest.deprecated_call(match="raw underlying set"):
            elements = sm()
        self.assertEqual(elements, {'dr'})

    def test_set_manager_discard_ignores_missing_without_warning(self) -> None:
        sm = SetManager(['dr', 'mr'])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = sm.discard('nope').discard('Dr.')  # normalizes like remove()
        self.assertIs(result, sm)
        self.assertEqual(set(sm), {'mr'})

    def test_set_manager_discard_invalidates_cached_union(self) -> None:
        c = Constants()
        self.assertIn('hon', c.suffixes_prefixes_titles)  # prime the cache
        c.titles.discard('hon')
        self.assertNotIn('hon', c.suffixes_prefixes_titles)

    def test_set_manager_remove_missing_member_emits_deprecation_warning(self) -> None:
        # ignore-missing remove() becomes KeyError in 2.0 (#243); discard()
        # is the intentional ignore-missing spelling
        sm = SetManager(['dr'])
        with pytest.deprecated_call(match="discard"):
            sm.remove('nope')
        self.assertEqual(set(sm), {'dr'})
        # removing a present member stays silent
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sm.remove('dr')
        self.assertEqual(len(sm), 0)

    def test_set_manager_remove_mixed_present_and_missing_in_one_call(self) -> None:
        # a single call mixing a present and a missing member must still warn
        # (for the missing one) and still invalidate the cache (for the
        # present one) -- not short-circuit either behavior
        c = Constants()
        self.assertIn('hon', c.suffixes_prefixes_titles)  # prime the cache
        with pytest.deprecated_call(match="discard"):
            c.titles.remove('hon', 'nope')
        self.assertNotIn('hon', c.suffixes_prefixes_titles)

    def test_set_manager_discard_mixed_present_and_missing_in_one_call(self) -> None:
        sm = SetManager(['dr', 'mr'])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = sm.discard('dr', 'nope')
        self.assertIs(result, sm)
        self.assertEqual(set(sm), {'mr'})

    def test_pickle_roundtrip_preserves_customizations(self) -> None:
        """A pickled Constants must restore its customized collections.

        Regression test: __setstate__ previously passed the whole state dict
        to __init__ as the `prefixes` argument, so every collection silently
        reverted to its module default on unpickling.
        """
        c = Constants()
        c.titles.add('customtitle')
        c.prefixes.add('customprefix')
        c.titles.remove('hon')
        c.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))

        self.assertIn('customtitle', restored.titles)
        self.assertIn('customprefix', restored.prefixes)
        self.assertNotIn('hon', restored.titles)
        # The contributing collections must match the original exactly.
        self.assertEqual(set(restored.titles), set(c.titles))
        self.assertEqual(set(restored.prefixes), set(c.prefixes))
        # The collections must also keep their manager type, not just contents.
        self.assertEqual(type(restored.titles), SetManager)
        self.assertEqual(type(restored.prefixes), SetManager)
        self.assertIn('curly_braces', restored.nickname_delimiters)
        self.assertEqual(type(restored.nickname_delimiters), TupleManager)

    def test_pickle_roundtrip_preserves_instance_scalar_override(self) -> None:
        """An instance-level scalar override must survive a pickle round-trip."""
        c = Constants()
        with pytest.deprecated_call():
            c.empty_attribute_default = None  # type: ignore[assignment]  # see test_empty_attribute_default above

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        # Restoring a pickled state is not itself a #255-deprecated assignment.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            restored = pickle.loads(pickle.dumps(c))

        self.assertEqual(restored.empty_attribute_default, None)

    def test_unpickle_legacy_state_with_property_key(self) -> None:
        """Pickles written by older versions must still load.

        The previous __getstate__ built its state from a dir() sweep, which
        always included the computed `suffixes_prefixes_titles` property (no
        customization required). That property has no setter, so __setstate__
        must skip such keys instead of raising AttributeError.

        Covers the temporary migration shim in __setstate__; remove this test
        when that shim is dropped (a release or two after 1.3.0).
        """
        c = Constants()
        c.titles.add('legacytitle')
        # Reproduce the legacy dir()-sweep state dict, which carries the
        # read-only `suffixes_prefixes_titles` property alongside the real config.
        legacy_state = {
            name: getattr(c, name) for name in dir(c) if not name.startswith('_')
        }
        self.assertIn('suffixes_prefixes_titles', legacy_state)

        restored = Constants.__new__(Constants)
        with pytest.deprecated_call():  # legacy-format load deprecated (#279)
            restored.__setstate__(legacy_state)

        # The real customization is recovered and the property key is ignored.
        self.assertIn('legacytitle', restored.titles)

    def test_unpickle_legacy_state_emits_deprecation_warning_once(self) -> None:
        # legacy-format unpickling is deprecated for removal in 2.0 (#279):
        # the migration shim will stop skipping the computed-property key and
        # raise ValueError instead; warn once per __setstate__ call (not once
        # per skipped key) telling users to re-pickle
        c = Constants()
        legacy_state = {
            name: getattr(c, name) for name in dir(c) if not name.startswith('_')
        }
        self.assertIn('suffixes_prefixes_titles', legacy_state)

        restored = Constants.__new__(Constants)
        with pytest.deprecated_call(match="re-pickle") as record:
            restored.__setstate__(legacy_state)
        deprecations = [w for w in record.list if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(deprecations), 1)

    def test_unpickle_legacy_state_with_two_stale_property_keys_warns_once(self) -> None:
        # Pins "once per __setstate__ call, not once per skipped key": with
        # only one computed property (suffixes_prefixes_titles) on the real
        # Constants class, the test above can't distinguish the two
        # semantics. A second read-only property on a throwaway subclass
        # forces two keys through the skip branch in one __setstate__ call.
        class ConstantsWithExtraProperty(Constants):
            @property
            def another_computed_property(self) -> str:
                return 'computed'

        c = ConstantsWithExtraProperty()
        legacy_state = {
            name: getattr(c, name) for name in dir(c) if not name.startswith('_')
        }
        self.assertIn('suffixes_prefixes_titles', legacy_state)
        self.assertIn('another_computed_property', legacy_state)

        restored = ConstantsWithExtraProperty.__new__(ConstantsWithExtraProperty)
        with pytest.deprecated_call(match="re-pickle") as record:
            restored.__setstate__(legacy_state)
        deprecations = [w for w in record.list if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(deprecations), 1)

    def test_setstate_without_legacy_keys_does_not_warn(self) -> None:
        c = Constants()
        c.titles.add('legacytitle')
        state = c.__getstate__()
        self.assertNotIn('suffixes_prefixes_titles', state)

        restored = Constants.__new__(Constants)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            restored.__setstate__(state)
        self.assertIn('legacytitle', restored.titles)

    def test_pickle_roundtrip_preserves_regex_manager_subclass(self) -> None:
        """regexes must round-trip as a RegexTupleManager, not a plain TupleManager.

        TupleManager.__reduce__ previously hardcoded TupleManager, so the
        RegexTupleManager subclass was downgraded on unpickling. The difference
        is observable: RegexTupleManager returns the EMPTY_REGEX default for an
        unknown key, while a plain TupleManager returns None.
        """
        c = Constants()

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))

        self.assertEqual(type(restored.regexes), RegexTupleManager)
        with pytest.deprecated_call():  # unknown-key access deprecated (#256)
            self.assertEqual(restored.regexes.does_not_exist, EMPTY_REGEX)

    def test_regexes_deepcopy_roundtrip(self) -> None:
        """copy.deepcopy of a RegexTupleManager must round-trip.

        __getattr__ answered every unknown name with the EMPTY_REGEX default,
        including the __deepcopy__ probe copy.deepcopy issues. copy then
        mistook that re.Pattern for a deep-copy hook and tried to call it.
        """
        c = Constants()

        dup = copy.deepcopy(c.regexes)

        self.assertEqual(type(dup), RegexTupleManager)
        self.assertEqual(dict(dup), dict(c.regexes))
        # The EMPTY_REGEX default still applies to genuinely unknown keys,
        # but accessing one is now deprecated (#256).
        with pytest.deprecated_call():
            self.assertEqual(dup.does_not_exist, EMPTY_REGEX)

    def test_nickname_delimiters_deepcopy_roundtrip(self) -> None:
        """copy.deepcopy of nickname_delimiters must round-trip.

        Mirrors test_regexes_deepcopy_roundtrip: nickname_delimiters is a
        plain TupleManager (not RegexTupleManager), but shares the same
        __getattr__/__reduce__ machinery.
        """
        c = Constants()
        c.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')

        dup = copy.deepcopy(c.nickname_delimiters)

        self.assertEqual(type(dup), TupleManager)
        self.assertEqual(dict(dup), dict(c.nickname_delimiters))
        # Plain TupleManager has no EMPTY_REGEX fallback: unknown keys are
        # None, but accessing one is now deprecated (#256).
        with pytest.deprecated_call():
            self.assertIsNone(dup.does_not_exist)
        self.assertIsNotNone(dup.curly_braces)

    def test_maiden_delimiters_deepcopy_roundtrip(self) -> None:
        """copy.deepcopy of maiden_delimiters (empty by default) must round-trip."""
        c = Constants()

        dup = copy.deepcopy(c.maiden_delimiters)

        self.assertEqual(type(dup), TupleManager)
        self.assertEqual(dict(dup), {})
        with pytest.deprecated_call():  # unknown-key access deprecated (#256)
            self.assertIsNone(dup.does_not_exist)

    def test_nickname_delimiters_default_builtins_resolve_live(self) -> None:
        # The three built-ins are stored as the *name* of a regexes entry
        # (a plain string), not a copied pattern, so overriding
        # self.C.regexes.parenthesis etc. keeps affecting nickname parsing --
        # see test_overriding_builtin_regex_still_affects_nickname_parsing in
        # test_nicknames.py.
        c = Constants()
        self.assertEqual(dict(c.nickname_delimiters), {
            'quoted_word': 'quoted_word',
            'double_quotes': 'double_quotes',
            'parenthesis': 'parenthesis',
        })
        self.assertEqual(dict(c.maiden_delimiters), {})

    def test_extra_nickname_delimiters_removed(self) -> None:
        c = Constants()
        self.assertFalse(hasattr(c, 'extra_nickname_delimiters'))

    def test_tuplemanager_setattr_delattr_ignore_dunder_names(self) -> None:
        """Regression test for the bug that motivated nickname_delimiters'
        __setattr__/__delattr__ dunder guard.

        Constructing a subscripted generic, e.g.
        TupleManager[re.Pattern[str] | str]({...}), makes typing's
        GenericAlias.__call__ set __orig_class__ on the new instance right
        after __init__ returns. Before the guard existed, __setattr__ was a
        bare dict.__setitem__ alias, so that assignment silently inserted a
        bogus '__orig_class__' entry into the dict itself, corrupting
        .values()/iteration for every TupleManager instance -- exactly what
        parse_nicknames() iterates over. This bit nickname_delimiters'
        construction (#22) before the guard was added.
        """
        tm = TupleManager[re.Pattern[str] | str]({'a': re.compile('x')})
        self.assertNotIn('__orig_class__', tm)
        self.assertEqual(dict(tm), {'a': re.compile('x')})
        # Dunder assignment/deletion still work as normal object attributes,
        # just routed around dict-backed storage.
        tm.__custom_dunder__ = 'probe'  # type: ignore[attr-defined]
        self.assertEqual(tm.__custom_dunder__, 'probe')  # type: ignore[attr-defined]
        self.assertNotIn('__custom_dunder__', tm)
        del tm.__custom_dunder__  # type: ignore[attr-defined]
        self.assertFalse(hasattr(tm, '__custom_dunder__'))

    def test_regextuplemanager_ignores_dunder_lookups(self) -> None:
        """Unknown dunder names report as absent, not as the EMPTY_REGEX default.

        Dunder names are Python's protocol probes (copy.deepcopy looks up
        __deepcopy__, inspect.unwrap looks up __wrapped__, ...), never config
        keys. Answering them with a regex breaks that machinery.
        """
        c = Constants()
        sentinel = object()

        self.assertEqual(getattr(c.regexes, '__deepcopy__', sentinel), sentinel)
        # A normal (non-dunder) unknown key still yields the EMPTY_REGEX
        # default, but accessing one is now deprecated (#256).
        with pytest.deprecated_call():
            self.assertEqual(c.regexes.unknown_key, EMPTY_REGEX)

    def test_tuplemanager_ignores_dunder_lookups(self) -> None:
        """Base TupleManager must report unknown dunder names as absent too.

        It returned None for any missing attribute, so `hasattr(tm, '__x__')`
        was always True — a landmine for any probe that does hasattr-then-call.
        Guarding dunders keeps the base consistent with RegexTupleManager.
        """
        c = Constants()
        tm = c.capitalization_exceptions  # a plain TupleManager
        sentinel = object()

        self.assertEqual(type(tm), TupleManager)
        self.assertFalse(hasattr(tm, '__deepcopy__'))
        self.assertEqual(getattr(tm, '__wrapped__', sentinel), sentinel)
        # A normal (non-dunder) unknown key still returns the None default,
        # but accessing one is now deprecated (#256).
        with pytest.deprecated_call():
            self.assertEqual(tm.unknown_key, None)

    def test_sunder_probe_does_not_emit_deprecation_warning(self) -> None:
        # Single-underscore introspection probes (IPython/Jupyter's
        # _repr_html_, _ipython_canary_method_should_not_exist_, etc.) are
        # never config keys, just like dunders -- warning on them would
        # misleadingly flag a typo merely for e.g. displaying CONSTANTS.regexes
        # in a notebook. No real config key starts with '_'.
        c = Constants()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(c.regexes._repr_html_, EMPTY_REGEX)
            self.assertIsNone(c.capitalization_exceptions._ipython_canary_method_should_not_exist_)

    def test_tuplemanager_unknown_key_emits_deprecation_warning(self) -> None:
        # unknown-key attribute access is deprecated for removal in 2.0
        # (#256); will become AttributeError naming the known keys
        c = Constants()
        tm = c.capitalization_exceptions
        with pytest.deprecated_call(match="phd_typo") as record:
            result = tm.phd_typo
        self.assertIsNone(result)
        message = str(record.list[0].message)
        for key in tm.keys():
            self.assertIn(key, message)

    def test_tuplemanager_known_key_does_not_warn(self) -> None:
        c = Constants()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            list(c.capitalization_exceptions.keys())  # sanity: has entries
            first_key = next(iter(c.capitalization_exceptions))
            getattr(c.capitalization_exceptions, first_key)

    def test_regextuplemanager_unknown_key_emits_deprecation_warning(self) -> None:
        c = Constants()
        with pytest.deprecated_call(match="parenthesys") as record:
            result = c.regexes.parenthesys
        self.assertEqual(result, EMPTY_REGEX)
        message = str(record.list[0].message)
        self.assertIn('mac', message)  # a known regexes key

    def test_regextuplemanager_known_key_does_not_warn(self) -> None:
        c = Constants()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            c.regexes.mac

    def test_dunder_probe_does_not_emit_deprecation_warning(self) -> None:
        # dunder protocol probes must stay silent -- only real config typos warn
        c = Constants()
        sentinel = object()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(getattr(c.regexes, '__deepcopy__', sentinel), sentinel)
            self.assertEqual(getattr(c.capitalization_exceptions, '__deepcopy__', sentinel), sentinel)


    def test_suffixes_prefixes_titles_reflects_add_title(self) -> None:
        """suffixes_prefixes_titles must include titles added after construction."""
        c = Constants()
        _ = c.suffixes_prefixes_titles  # prime the cache so invalidation is exercised
        c.titles.add('emerita')
        self.assertIn('emerita', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_add_prefix(self) -> None:
        """suffixes_prefixes_titles must include prefixes added after construction."""
        c = Constants()
        _ = c.suffixes_prefixes_titles  # prime the cache so invalidation is exercised
        c.prefixes.add('xpfx')
        self.assertIn('xpfx', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_remove_title(self) -> None:
        """suffixes_prefixes_titles must not include a word that was only in titles and is then removed."""
        c = Constants()
        c.titles.add('emerita')
        self.assertIn('emerita', c.suffixes_prefixes_titles)
        c.titles.remove('emerita')
        self.assertNotIn('emerita', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_remove_prefix(self) -> None:
        """suffixes_prefixes_titles must not include a word that was only in prefixes and is then removed."""
        c = Constants()
        c.prefixes.add('xpfx')
        self.assertIn('xpfx', c.suffixes_prefixes_titles)
        c.prefixes.remove('xpfx')
        self.assertNotIn('xpfx', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_add_suffix_acronym(self) -> None:
        """suffixes_prefixes_titles must include suffix acronyms added after construction."""
        c = Constants()
        _ = c.suffixes_prefixes_titles  # prime the cache so invalidation is exercised
        c.suffix_acronyms.add('xsfx')
        self.assertIn('xsfx', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_add_suffix_not_acronym(self) -> None:
        """suffixes_prefixes_titles must include non-acronym suffixes added after construction."""
        c = Constants()
        _ = c.suffixes_prefixes_titles  # prime the cache so invalidation is exercised
        c.suffix_not_acronyms.add('xsfx')
        self.assertIn('xsfx', c.suffixes_prefixes_titles)

    def test_pickle_roundtrip_rewires_invalidation_callbacks(self) -> None:
        """Mutations on a deserialized Constants must still invalidate the cache."""
        c = Constants()
        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))
        _ = restored.suffixes_prefixes_titles  # prime the cache
        restored.titles.add('posttitle')
        self.assertIn('posttitle', restored.suffixes_prefixes_titles)

    def test_is_rootname_consistent_with_is_title(self) -> None:
        """is_rootname must return False for words recognised by is_title."""
        hn = HumanName("", constants=Constants())
        _ = hn.C.suffixes_prefixes_titles  # prime the cache so a stale entry would be observable
        hn.C.titles.add('emerita')
        self.assertFalse(hn.is_rootname('emerita'))

    def test_is_rootname_consistent_with_is_prefix(self) -> None:
        """is_rootname must return False for words recognised by is_prefix."""
        hn = HumanName("", constants=Constants())
        _ = hn.C.suffixes_prefixes_titles  # prime the cache so a stale entry would be observable
        hn.C.prefixes.add('xpfx')
        self.assertFalse(hn.is_rootname('xpfx'))

    def test_suffixes_prefixes_titles_reflects_remove_suffix_acronym(self) -> None:
        """suffixes_prefixes_titles must reflect a suffix acronym removed after the cache is primed."""
        c = Constants()
        c.suffix_acronyms.add('xsfx')
        self.assertIn('xsfx', c.suffixes_prefixes_titles)  # primes the cache
        c.suffix_acronyms.remove('xsfx')
        self.assertNotIn('xsfx', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_remove_suffix_not_acronym(self) -> None:
        """suffixes_prefixes_titles must reflect a non-acronym suffix removed after the cache is primed."""
        c = Constants()
        c.suffix_not_acronyms.add('xsfx')
        self.assertIn('xsfx', c.suffixes_prefixes_titles)  # primes the cache
        c.suffix_not_acronyms.remove('xsfx')
        self.assertNotIn('xsfx', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_add_with_encoding(self) -> None:
        """add_with_encoding must invalidate the cache like add()/remove() do."""
        c = Constants()
        _ = c.suffixes_prefixes_titles  # prime the cache
        with pytest.deprecated_call():  # bytes input deprecated (#245)
            c.titles.add_with_encoding(b'b\351ck', encoding='latin_1')
        self.assertIn('béck', c.suffixes_prefixes_titles)

    def test_suffixes_prefixes_titles_reflects_replaced_manager(self) -> None:
        """Replacing a whole SetManager must invalidate the cache and wire the new manager.

        Covers the config-teardown path where a fresh SetManager is assigned
        directly (e.g. ``setattr(CONSTANTS, 'titles', SetManager(...))``).
        """
        c = Constants()
        _ = c.suffixes_prefixes_titles  # prime the cache
        c.titles = SetManager(['brandnewtitle'])
        # The replacement is reflected immediately...
        self.assertIn('brandnewtitle', c.suffixes_prefixes_titles)
        # ...and the new manager's own mutations invalidate the cache too,
        # proving the on_change callback was re-wired to the replacement.
        _ = c.suffixes_prefixes_titles
        c.titles.add('secondtitle')
        self.assertIn('secondtitle', c.suffixes_prefixes_titles)

    def test_replaced_manager_no_longer_invalidates_cache(self) -> None:
        """A SetManager detached by reassignment must not invalidate the new cache."""
        c = Constants()
        replaced = c.titles
        c.titles = SetManager(['brandnewtitle'])
        primed = c.suffixes_prefixes_titles
        # Mutating the orphaned manager must leave the live cache untouched.
        replaced.add('ghost')
        self.assertIs(c.suffixes_prefixes_titles, primed)
        self.assertNotIn('ghost', c.suffixes_prefixes_titles)

    def test_tuplemanager_delattr_removes_dict_entry(self) -> None:
        """Deleting a non-dunder attribute must remove the dict entry.

        TupleManager routes non-dunder attribute deletion to ``del self[attr]``
        (the mirror of its dot-notation __setattr__), so ``del tm.key`` and
        ``del tm['key']`` are the same operation.
        """
        c = Constants()
        c.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')
        self.assertIn('curly_braces', c.nickname_delimiters)
        del c.nickname_delimiters.curly_braces  # type: ignore[attr-defined]
        self.assertNotIn('curly_braces', c.nickname_delimiters)

    def test_assigning_non_setmanager_to_cached_union_member_raises(self) -> None:
        """A cached-union attribute rejects a plain iterable, demanding a SetManager.

        The four ``_CachedUnionMember`` attributes wire an on-change callback into
        the assigned manager; a bare list would silently break cache invalidation,
        so __set__ fails loud with a message telling the caller to wrap it.
        """
        c = Constants()
        with pytest.raises(TypeError, match='SetManager'):
            c.titles = ['mr', 'ms']  # type: ignore[assignment]

    def test_assigning_non_setmanager_to_plain_set_attr_raises(self) -> None:
        """The five non-cached-union SetManager attributes reject bare assignment too.

        Only the four ``_CachedUnionMember`` attributes were guarded; these five
        were plain instance attributes, so ``c.conjunctions = 'and'`` silently
        replaced the SetManager with a str, turning later ``in`` membership
        checks into substring tests (#241).
        """
        c = Constants()
        for name in ('first_name_titles', 'conjunctions', 'bound_first_names',
                     'non_first_name_prefixes', 'suffix_acronyms_ambiguous'):
            with pytest.raises(TypeError, match='SetManager'):
                setattr(c, name, ['x'])

    def test_bare_string_assignment_to_conjunctions_raises(self) -> None:
        # the original #241 repro: 'and' assigned as a bare str silently
        # degrades `piece.lower() in self.C.conjunctions` into a substring test
        c = Constants()
        with pytest.raises(TypeError, match='SetManager'):
            c.conjunctions = 'and'  # type: ignore[assignment]

    def test_setstate_raises_on_missing_descriptor_field(self) -> None:
        """Unpickling a state blob missing a cached-union collection must fail loudly.

        __setstate__ verifies every ``_CachedUnionMember``-backed attribute was
        restored; a missing one would otherwise surface much later as an
        AttributeError on the private mangled name (e.g. ``_titles``), which is
        far harder to diagnose than a named ValueError here.
        """
        c = Constants()
        state = dict(c.__getstate__())
        del state['titles']
        restored = Constants.__new__(Constants)
        with pytest.raises(ValueError, match='titles'):
            restored.__setstate__(state)


class ParsingDoesNotMutateConfigTests(HumanNameTestBase):
    """Parsing a name must never write back into the Constants it reads.

    The parser derives extra lookup entries while parsing (period-joined
    titles/suffixes like "Lt.Gov.", conjunction-joined pieces like
    "Mr. and Mrs." or "von und zu"). Those derivations are needed within the
    parse, but historically they were add()ed to ``self.C`` — by default the
    shared module-level CONSTANTS singleton — so parsing one name permanently
    changed how every later name in the process parsed: parse results depended
    on input order, and concurrent parsing raced on the shared sets.
    """

    @staticmethod
    def _config_snapshot(constants: Constants) -> dict:
        """Snapshot every piece of configuration ``constants`` owns.

        Enumerated via ``Constants.__getstate__()`` — the canonical listing of
        an instance's own config (descriptor-backed names mapped to their
        public form, private caches like ``_pst`` excluded) — so a collection
        added to ``Constants`` later is watched automatically, with no
        attribute list to keep in sync.
        """
        snap: dict[str, Any] = {}
        for attr, value in constants.__getstate__().items():
            if isinstance(value, SetManager):
                snap[attr] = set(value)
            elif isinstance(value, TupleManager):
                snap[attr] = dict(value)
            else:
                snap[attr] = value  # scalar override
        # Fail loud if the structural discovery ever stops seeing the sets
        # the parser historically leaked into.
        assert {'titles', 'prefixes', 'conjunctions',
                'suffix_acronyms', 'suffix_not_acronyms'} <= set(snap), \
            "config snapshot no longer covers the historically-mutated sets"
        return snap

    def _assert_config_unchanged(self, constants: Constants, before: dict, parsed: str) -> None:
        after = self._config_snapshot(constants)
        diffs = []
        for attr in sorted(set(before) | set(after)):
            b, a = before.get(attr), after.get(attr)
            if b != a:
                if isinstance(b, set) and isinstance(a, set):
                    diffs.append(f"{attr}: added {sorted(a - b)}, removed {sorted(b - a)}")
                else:
                    diffs.append(f"{attr}: {b!r} -> {a!r}")
        self.assertEqual(diffs, [], f"parsing {parsed!r} changed the config: {diffs}")

    def _assert_parse_leaves_config_unchanged(self, name: str) -> HumanName:
        from nameparser.config import CONSTANTS
        before = self._config_snapshot(CONSTANTS)
        hn = HumanName(name)
        self._assert_config_unchanged(CONSTANTS, before, name)
        return hn

    def test_period_joined_title_does_not_leak_into_titles(self) -> None:
        hn = self._assert_parse_leaves_config_unchanged("Lt.Gov. John Doe")
        # the within-parse derivation must still work
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)

    def test_period_joined_suffix_does_not_leak_into_suffixes(self) -> None:
        hn = self._assert_parse_leaves_config_unchanged("John Doe JD.CPA")
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Doe", hn)
        self.m(hn.suffix, "JD.CPA", hn)

    def test_joined_conjunctions_do_not_leak_into_conjunctions(self) -> None:
        hn = self._assert_parse_leaves_config_unchanged("Louis of the Netherlands")
        self.m(hn.first, "Louis of the Netherlands", hn)

    def test_title_conjunction_join_does_not_leak_into_titles(self) -> None:
        hn = self._assert_parse_leaves_config_unchanged("Mr. and Mrs. John Smith")
        self.m(hn.title, "Mr. and Mrs.", hn)
        self.m(hn.first, "John", hn)
        self.m(hn.last, "Smith", hn)

    def test_prefix_conjunction_join_does_not_leak_into_prefixes(self) -> None:
        hn = self._assert_parse_leaves_config_unchanged("Alois von und zu Liechtenstein")
        self.m(hn.first, "Alois", hn)
        self.m(hn.last, "von und zu Liechtenstein", hn)

    def test_instance_owned_constants_not_mutated_by_parsing(self) -> None:
        hn = HumanName("", constants=Constants())
        before = self._config_snapshot(hn.C)
        hn.full_name = "Lt.Gov. John Doe"
        self._assert_config_unchanged(hn.C, before, "Lt.Gov. John Doe")
        self.m(hn.title, "Lt.Gov.", hn)

    def test_derivations_reset_between_parses_of_same_instance(self) -> None:
        # Re-assigning full_name re-parses; each parse must re-derive from a
        # clean slate and still resolve the period-joined title.
        hn = HumanName("Lt.Gov. John Doe")
        hn.full_name = "Lt.Gov. Jane Roe"
        self.m(hn.title, "Lt.Gov.", hn)
        self.m(hn.first, "Jane", hn)
        self.m(hn.last, "Roe", hn)


class SuffixesPrefixesTitlesPerformanceTests(HumanNameTestBase):
    """Guard against accidental cache removal on suffixes_prefixes_titles.

    This library is commonly used to parse large batches of names, so
    suffixes_prefixes_titles must remain cached.  Without the cache, each call
    rebuilds the union from ~700 strings; with it, repeated access is
    orders of magnitude faster.  Rather than compare against a fixed
    wall-clock budget (which flakes on slower/noisier CI runners), this
    measures the uncached build cost on the same machine and asserts cached
    access is much faster than that baseline.
    """

    def test_repeated_access_is_cached(self) -> None:
        c = Constants()
        first = c.suffixes_prefixes_titles
        second = c.suffixes_prefixes_titles
        assert first is second, "suffixes_prefixes_titles should return the same cached object on repeated access"

        # Baseline: cost of an uncached build, measured via fresh instances
        # (each instance's first access rebuilds the union) on this machine.
        m = 50
        uncached_per_call = timeit.timeit(lambda: Constants().suffixes_prefixes_titles, number=m) / m

        n = 10_000
        cached_per_call = timeit.timeit(lambda: c.suffixes_prefixes_titles, number=n) / n

        # If caching is broken, cached_per_call would be roughly the same as
        # uncached_per_call. With caching intact it should be at least an
        # order of magnitude faster.
        limit = uncached_per_call / 10
        assert cached_per_call < limit, (
            f"suffixes_prefixes_titles appears uncached: cached access averaged "
            f"{cached_per_call * 1e6:.1f} us/call vs an uncached build cost of "
            f"{uncached_per_call * 1e6:.1f} us/call. Was _pst caching removed?"
        )


class ConstantsReprTests(HumanNameTestBase):

    def test_repr_reports_actual_collection_sizes(self) -> None:
        c = Constants()
        repr_str = repr(c)
        for name in Constants._repr_collection_attrs:
            self.assertIn(f"{name}: {len(getattr(c, name))}", repr_str)

    def test_repr_omits_scalars_at_default_value(self) -> None:
        c = Constants()
        repr_str = repr(c)
        for name in Constants._repr_scalar_attrs:
            self.assertNotIn(name, repr_str)

    def test_repr_shows_scalar_override_via_constructor(self) -> None:
        c = Constants(middle_name_as_last=True)
        self.assertIn("middle_name_as_last: True", repr(c))

    def test_repr_shows_scalar_override_via_assignment(self) -> None:
        # Most _repr_scalar_attrs (e.g. capitalize_name) aren't __init__ kwargs
        # at all -- they're only ever overridden by direct assignment.
        c = Constants()
        c.capitalize_name = True
        self.assertIn("capitalize_name: True", repr(c))

    def test_repr_shows_multiple_simultaneous_scalar_overrides(self) -> None:
        c = Constants(patronymic_name_order=True)
        c.capitalize_name = True
        repr_str = repr(c)
        self.assertIn("patronymic_name_order: True", repr_str)
        self.assertIn("capitalize_name: True", repr_str)

    def test_repr_reflects_mutated_collection_size(self) -> None:
        c = Constants()
        before = len(c.titles)
        c.titles.add('a-brand-new-title-for-repr-test')
        self.assertIn(f"titles: {before + 1}", repr(c))

    def test_repr_reports_empty_collection(self) -> None:
        c = Constants(titles=[])
        self.assertIn("titles: 0", repr(c))

    def test_repr_is_bracketed_multiline(self) -> None:
        repr_str = repr(Constants())
        self.assertTrue(repr_str.startswith("<Constants : [\n"))


class ConstantsCopyTests(HumanNameTestBase):
    """Constants.copy() -- a detached snapshot, distinct from fresh Constants() defaults (#260)."""

    def test_copy_is_independent_of_original(self) -> None:
        c = Constants()
        dup = c.copy()
        dup.titles.add('a-brand-new-title-for-copy-test')
        self.assertNotIn('a-brand-new-title-for-copy-test', c.titles)

    def test_copy_is_not_the_same_object(self) -> None:
        c = Constants()
        dup = c.copy()
        self.assertIsNot(dup, c)
        self.assertTrue(isinstance(dup, Constants))

    def test_copy_preserves_subclass_type(self) -> None:
        # copy() is deepcopy-based (restored via __getstate__/__setstate__,
        # not by re-invoking type(self)(...)), so a naive reimplementation
        # could silently downgrade a subclass instance to plain Constants.
        class CustomConstants(Constants):
            pass

        c = CustomConstants()
        dup = c.copy()
        self.assertTrue(isinstance(dup, CustomConstants))

    def test_copy_preserves_empty_attribute_default_without_warning(self) -> None:
        # copy() round-trips through __getstate__/__setstate__ like pickle
        # does; restoring saved state isn't a user assignment, so it must not
        # emit #255's deprecation warning (the __setstate__ bypass exists
        # specifically for this call path, not just pickle.loads).
        c = Constants()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            c.empty_attribute_default = None  # type: ignore[assignment]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            dup = c.copy()
        self.assertIsNone(dup.empty_attribute_default)

    def test_copy_snapshots_current_customizations(self) -> None:
        # Unlike Constants(), which always starts from library defaults,
        # .copy() preserves whatever customizations the original already has.
        c = Constants()
        c.titles.add('zephyrmark')
        dup = c.copy()
        self.assertIn('zephyrmark', dup.titles)
        # and stays a snapshot -- later mutation of the original doesn't leak in
        c.titles.remove('zephyrmark')
        self.assertIn('zephyrmark', dup.titles)

    def test_fresh_constants_does_not_include_source_customizations(self) -> None:
        # Contrast case for the snapshot test above: Constants() ignores
        # whatever CONSTANTS has been customized with.
        c = Constants()
        c.titles.add('zephyrmark')
        fresh = Constants()
        self.assertNotIn('zephyrmark', fresh.titles)


class ConstantsNoneDeprecationTests(HumanNameTestBase):
    """constants=None is deprecated in favor of Constants() or CONSTANTS.copy() (#260)."""

    def test_explicit_none_warns_on_construction(self) -> None:
        with pytest.deprecated_call(match="Constants()"):
            HumanName("John Doe", constants=None)

    def test_explicit_none_warns_on_positional_argument(self) -> None:
        with pytest.deprecated_call(match="Constants()"):
            HumanName("John Doe", None)

    def test_explicit_none_warning_names_both_replacements(self) -> None:
        with pytest.warns(DeprecationWarning) as record:
            HumanName("John Doe", constants=None)
        message = str(record[0].message)
        self.assertIn("Constants()", message)
        self.assertIn("CONSTANTS.copy()", message)

    def test_explicit_none_warns_on_c_setter(self) -> None:
        hn = HumanName("John Doe")
        with pytest.deprecated_call(match="Constants()"):
            hn.C = None

    def test_omitted_constants_argument_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            HumanName("John Doe")

    def test_explicit_own_constants_instance_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            HumanName("John Doe", constants=Constants())

    def test_explicit_none_still_produces_a_working_private_config(self) -> None:
        # Behavior is unchanged, only newly warned about.
        with pytest.deprecated_call():
            hn = HumanName("John Doe", constants=None)
        self.assertTrue(hn.has_own_config)
