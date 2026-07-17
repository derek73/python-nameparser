import copy
import pickle
import re
import warnings
from typing import Any

import pytest

from nameparser import HumanName
from nameparser.config import CONSTANTS, Constants, SetManager, TupleManager
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
        # 2.0's message names the received class rather than v1's "did you
        # mean Constants()" hint; the class-not-instance mistake still fails
        # loudly at construction
        with pytest.raises(TypeError, match=r"constants must be a Constants instance"):
            HumanName("John Doe", constants=Constants)  # type: ignore[arg-type]

    def test_assigning_invalid_constants_after_construction_raises(self) -> None:
        # #226 validated the constructor's `constants` argument, but `hn.C = ...`
        # bypassed it entirely: the bad value was accepted silently and only
        # surfaced far later, deep inside parsing, with no mention of `C` (#239)
        hn = HumanName("John Doe")
        with pytest.raises(TypeError, match="constants must be"):
            hn.C = "garbage"  # type: ignore[assignment]

    def test_assigning_constants_class_after_construction_raises_with_hint(self) -> None:
        # same message note as the constructor variant above
        hn = HumanName("John Doe")
        with pytest.raises(TypeError, match=r"constants must be a Constants instance"):
            hn.C = Constants  # type: ignore[assignment]

    def test_assigning_none_to_constants_raises(self) -> None:
        # constants=None was removed in 2.0 (#261, warned since 1.3.1): the v1
        # silently-build-a-fresh-Constants fallback is gone from the C setter
        # too; pass Constants() or CONSTANTS.copy() explicitly
        hn = HumanName("John Doe")
        with pytest.raises(TypeError, match="261"):
            hn.C = None  # type: ignore[assignment]

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
            c.titles |= 'esq'  # type: ignore[assignment]
        # |= produces a plain set that Constants.__setattr__ re-wraps in a
        # SetManager (2.0's auto-wrap; see the plain-iterable assignment
        # test below) -- mypy sees only the set-for-SetManager assignment
        c.titles |= ['Esq.']  # type: ignore[assignment]
        self.assertIn('esq', c.titles)
        hn = HumanName("Esq Jane Smith", constants=c)
        self.m(hn.title, "Esq", hn)

    def test_set_manager_operators_normalize_like_add(self) -> None:
        # add() lowercases and strips leading/trailing periods; without the
        # same normalization of operator operands, (titles | ['Esq.']) keeps
        # a raw 'Esq.', which the parser's lc()-based lookups can never match
        # — silently broken config, same failure family as the bare-string
        # shredding (#238).
        # Compared via set(...) rather than v1's .elements: the raw-set
        # accessor was internal machinery and is gone in 2.0 (#243 family);
        # 2.0 operators also return a plain set rather than a SetManager.
        sm = SetManager(['dr', 'mr'])
        self.assertEqual(set(sm | ['Esq.']), {'dr', 'mr', 'esq'})
        self.assertEqual(set(['Esq.', 'Dr.'] | sm), {'dr', 'mr', 'esq'})
        self.assertEqual(set(sm & ['Dr.']), {'dr'})
        self.assertEqual(set(['Dr.'] & sm), {'dr'})
        self.assertEqual(set(sm - ['Dr.']), {'mr'})
        self.assertEqual(set(['Dr.', 'Esq.'] - sm), {'esq'})
        self.assertEqual(set(sm ^ ['Dr.', 'Esq.']), {'mr', 'esq'})
        # pins __rxor__ separately in case it ever stops aliasing __xor__
        self.assertEqual(set(['Dr.', 'Esq.'] ^ sm), {'mr', 'esq'})

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
        self.assertEqual(set(['Dr.', 'Esq.'] - sm), {'esq'})
        self.assertEqual(set(sm - ['Dr.', 'Esq.']), {'mr'})

    def test_set_manager_constructor_normalizes_like_add(self) -> None:
        # without constructor normalization the operators misfire against
        # the exact spelling visibly stored in the set: & returns empty
        # and - silently no-ops
        sm = SetManager(['Dr.', 'MR'])
        self.assertEqual(set(sm), {'dr', 'mr'})
        self.assertEqual(set(sm & ['Dr.']), {'dr'})
        self.assertEqual(set(sm - ['Dr.']), {'mr'})

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
        with pytest.raises(TypeError, match=r"expected a str"):
            SetManager([None])  # type: ignore[list-item]
        with pytest.raises(TypeError, match=r"expected a str"):
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
        # This test exercises shared-CONSTANTS mutation specifically, which
        # 2.0 deprecates (removal 3.0; the message points at Lexicon/Policy
        # and private Constants); deprecated_call() pins the warning while
        # asserting the mutation is still honored.
        hn = HumanName("")
        hn2 = HumanName("")
        with pytest.deprecated_call(match="Lexicon"):
            hn.C.titles.remove('hon')
        self.assertEqual('hon' in hn.C.titles, False)
        self.assertEqual('hon' in hn2.C.titles, False)
        self.assertEqual(hn.has_own_config, False)
        self.assertEqual(hn2.has_own_config, False)
        # No manual cleanup needed: the autouse fixture in conftest.py snapshots
        # and restores the global CONSTANTS collections around every test.

    def test_custom_nickname_delimiter_raises(self) -> None:
        # Custom (non-sentinel) delimiter additions raise in 2.0 (deliberate
        # divergence, migration spec section 3 -- same uniform rule as
        # regexes); Policy(nickname_delimiters=...) is the replacement. The
        # #112 use case this test used to pin moved to the new API.
        hn = HumanName("")
        with pytest.raises(TypeError, match="Policy"):
            hn.C.nickname_delimiters['curly_braces'] = re.compile(r'\{(.*?)\}')

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

    def test_empty_attribute_default_removed(self) -> None:
        # empty_attribute_default was removed in 2.0 (#255, warned since
        # 1.3.0): empty attributes are always ''. Assignment raises naming
        # the issue; the attribute no longer exists to read either.
        c = Constants()
        with pytest.raises(AttributeError, match="255"):
            c.empty_attribute_default = None  # type: ignore[assignment]
        self.assertFalse(hasattr(c, 'empty_attribute_default'))
        hn = HumanName("")
        self.assertEqual(hn.first, '')
        self.assertEqual(hn.last, '')

    def test_add_with_encoding_removed(self) -> None:
        # add_with_encoding() was removed in 2.0 (#245/#263, warned in 1.4);
        # decode and use add() instead
        c = Constants()
        with pytest.raises(AttributeError, match="add_with_encoding"):
            c.titles.add_with_encoding(b'b\351ck', encoding='latin_1')  # type: ignore[attr-defined]
        c.titles.add(b'b\351ck'.decode('latin_1'))
        self.assertIn('béck', c.titles)

    def test_set_manager_add_bytes_raises_with_decode_hint(self) -> None:
        # bytes elements were removed in 2.0 (#245, warned since 1.3.0)
        sm = SetManager(['dr'])
        with pytest.raises(TypeError, match="decode"):
            sm.add(b'esq')  # type: ignore[arg-type]
        self.assertNotIn('esq', sm)

    def test_set_manager_add_str_does_not_warn(self) -> None:
        sm = SetManager(['dr'])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sm.add('esq')
        self.assertIn('esq', sm)

    def test_set_manager_call_removed(self) -> None:
        # __call__ handed out the raw underlying set, bypassing normalization
        # and change tracking; removed in 2.0 (#243, warned since 1.3.0) --
        # iterate the manager or copy with set(manager) instead
        sm = SetManager(['dr'])
        with pytest.raises(TypeError, match="not callable"):
            sm()  # type: ignore[operator]
        self.assertEqual(set(sm), {'dr'})

    def test_set_manager_discard_ignores_missing_without_warning(self) -> None:
        sm = SetManager(['dr', 'mr'])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = sm.discard('nope').discard('Dr.')  # normalizes like remove()
        self.assertIs(result, sm)
        self.assertEqual(set(sm), {'mr'})

    def test_set_manager_remove_missing_member_raises(self) -> None:
        # ignore-missing remove() became KeyError in 2.0 (#243, warned since
        # 1.3.0); discard() is the intentional ignore-missing spelling
        sm = SetManager(['dr'])
        with pytest.raises(KeyError):
            sm.remove('nope')
        self.assertEqual(set(sm), {'dr'})
        # removing a present member stays silent
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sm.remove('dr')
        self.assertEqual(len(sm), 0)

    def test_set_manager_remove_mixed_present_and_missing_in_one_call(self) -> None:
        # a single call mixing a present and a missing member raises for the
        # missing one (#243) but still applies the present removal, so
        # config state and change tracking don't silently diverge from what
        # was removed before the KeyError
        c = Constants()
        with pytest.raises(KeyError):
            c.titles.remove('hon', 'nope')
        self.assertNotIn('hon', c.titles)

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
        # (custom nickname delimiters raise in 2.0 -- see
        # test_custom_nickname_delimiter_raises -- so the delimiter leg of
        # this round-trip moved to the sentinel default below)

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))

        self.assertIn('customtitle', restored.titles)
        self.assertIn('customprefix', restored.prefixes)
        self.assertNotIn('hon', restored.titles)
        # The contributing collections must match the original exactly.
        self.assertEqual(set(restored.titles), set(c.titles))
        self.assertEqual(set(restored.prefixes), set(c.prefixes))
        # The collections must also keep their manager type, not just
        # contents (nickname_delimiters is the 2.0 delimiter manager, a
        # TupleManager subclass, so isinstance rather than exact type).
        self.assertEqual(type(restored.titles), SetManager)
        self.assertEqual(type(restored.prefixes), SetManager)
        self.assertIn('parenthesis', restored.nickname_delimiters)
        self.assertTrue(isinstance(restored.nickname_delimiters, TupleManager))

    def test_pickle_roundtrip_preserves_instance_scalar_override(self) -> None:
        """An instance-level scalar override must survive a pickle round-trip.

        Exercised via string_format: the v1 vehicle for this test,
        empty_attribute_default, was removed in 2.0 (#255).
        """
        c = Constants()
        c.string_format = "{last}"

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            restored = pickle.loads(pickle.dumps(c))

        self.assertEqual(restored.string_format, "{last}")

    def test_unpickle_legacy_state_raises(self) -> None:
        """Pre-1.3.0 pickles now raise (#279, warned since 1.3.0).

        Those blobs are recognizable by the computed
        ``suffixes_prefixes_titles`` property their dir()-sweep
        ``__getstate__`` captured; the 1.4 DeprecationWarning promised
        ValueError in 2.0, pointing at re-pickling under 1.3/1.4.
        """
        legacy_state: dict[str, object] = {
            'prefixes': {'van'},
            'titles': {'dr', 'legacytitle'},
            'suffixes_prefixes_titles': {'van', 'dr'},
        }
        restored = Constants.__new__(Constants)
        with pytest.raises(ValueError, match="279"):
            restored.__setstate__(legacy_state)

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

    def test_pickle_roundtrip_keeps_regexes_readable(self) -> None:
        """The regexes surface must survive a Constants pickle round-trip.

        In 2.0 ``regexes`` is a read-only proxy over the built-in patterns
        (not pickled state), so the v1 concern this test carried -- the
        RegexTupleManager subclass being downgraded by ``__reduce__`` -- no
        longer exists; what remains contractual is that reads keep working
        on the restored instance and unknown keys fail loudly (#256).
        """
        c = Constants()

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))

        self.assertEqual(type(restored.regexes), type(c.regexes))
        self.assertIsNotNone(restored.regexes.mac)
        with pytest.raises(AttributeError):  # unknown-key access raises (#256)
            restored.regexes.does_not_exist

    def test_regexes_deepcopy_roundtrip(self) -> None:
        """copy.deepcopy of the regexes proxy must round-trip.

        The v1 bug this pinned: __getattr__ answered every unknown name --
        including copy.deepcopy's __deepcopy__ probe -- with the EMPTY_REGEX
        default, so copy mistook a re.Pattern for a deep-copy hook. The 2.0
        proxy must keep ignoring protocol probes.
        """
        c = Constants()

        dup = copy.deepcopy(c.regexes)

        self.assertEqual(type(dup), type(c.regexes))
        self.assertEqual(set(dup.keys()), set(c.regexes.keys()))
        # Unknown keys raise in 2.0 (#256) instead of returning EMPTY_REGEX.
        with pytest.raises(AttributeError):
            dup.does_not_exist

    def test_nickname_delimiters_deepcopy_roundtrip(self) -> None:
        """copy.deepcopy of nickname_delimiters must round-trip.

        Mirrors test_regexes_deepcopy_roundtrip on the delimiter manager (a
        TupleManager subclass in 2.0). Custom entries raise in 2.0, so the
        round-trip is exercised on the three built-in sentinels.
        """
        c = Constants()

        dup = copy.deepcopy(c.nickname_delimiters)

        self.assertTrue(isinstance(dup, TupleManager))
        self.assertEqual(dict(dup), dict(c.nickname_delimiters))
        with pytest.raises(AttributeError):  # unknown-key access raises (#256)
            dup.does_not_exist
        self.assertIsNotNone(dup.parenthesis)

    def test_maiden_delimiters_deepcopy_roundtrip(self) -> None:
        """copy.deepcopy of maiden_delimiters (empty by default) must round-trip."""
        c = Constants()

        dup = copy.deepcopy(c.maiden_delimiters)

        self.assertTrue(isinstance(dup, TupleManager))
        self.assertEqual(dict(dup), {})
        with pytest.raises(AttributeError):  # unknown-key access raises (#256)
            dup.does_not_exist

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
        # The 2.0 TupleManager is a plain dict subclass, not Generic like
        # v1's -- but dict's inherited __class_getitem__ still makes the
        # subscription work at runtime, which is exactly the GenericAlias
        # __orig_class__ probe this test exists to exercise.
        tm = TupleManager[re.Pattern[str] | str]({'a': re.compile('x')})  # type: ignore[misc]
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
        # A normal (non-dunder) unknown key raises in 2.0 (#256, warned
        # since 1.4) instead of degrading to the EMPTY_REGEX default.
        with pytest.raises(AttributeError):
            c.regexes.unknown_key

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
        # A normal (non-dunder) unknown key raises in 2.0 (#256, warned
        # since 1.4) instead of returning the None default.
        with pytest.raises(AttributeError):
            tm.unknown_key

    def test_sunder_probe_reports_absent_without_deprecation_warning(self) -> None:
        # Single-underscore introspection probes (IPython/Jupyter's
        # _repr_html_, _ipython_canary_method_should_not_exist_, etc.) are
        # never config keys, just like dunders. In 2.0 they raise a plain
        # AttributeError -- the protocol-correct "absent" answer, so
        # hasattr-then-call probes work -- with no typo-flavored noise
        # (v1.4 returned the manager default silently instead).
        c = Constants()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertFalse(hasattr(c.regexes, '_repr_html_'))
            self.assertFalse(hasattr(c.capitalization_exceptions,
                                     '_ipython_canary_method_should_not_exist_'))

    def test_tuplemanager_unknown_key_raises_naming_known_keys(self) -> None:
        # unknown-key attribute access raises in 2.0 (#256, warned since
        # 1.4): AttributeError naming the known keys, as the 1.4 warning
        # promised
        c = Constants()
        tm = c.capitalization_exceptions
        with pytest.raises(AttributeError, match="phd_typo") as excinfo:
            tm.phd_typo
        message = str(excinfo.value)
        for key in tm.keys():
            self.assertIn(key, message)

    def test_tuplemanager_known_key_does_not_warn(self) -> None:
        c = Constants()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            list(c.capitalization_exceptions.keys())  # sanity: has entries
            first_key = next(iter(c.capitalization_exceptions))
            getattr(c.capitalization_exceptions, first_key)

    def test_regexes_unknown_key_raises(self) -> None:
        # the read-only regexes proxy raises on unknown keys too (#256);
        # unlike the tuple managers its message names only the missing key,
        # not the known-keys listing
        c = Constants()
        with pytest.raises(AttributeError, match="parenthesys"):
            c.regexes.parenthesys

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


    # The v1 suffixes_prefixes_titles cached-union property and its
    # invalidation machinery (including the is_rootname predicate that read
    # it) are gone in 2.0 -- change tracking is the shim's generation
    # counter, covered in tests/v2/test_config_shim.py. The ~13 tests that
    # exercised cache priming/invalidation were deleted with it; the two
    # kept below re-pin their surviving contracts on public parsing surface.

    def test_pickle_roundtrip_rewires_change_tracking(self) -> None:
        """Mutations on a deserialized Constants must still reach the parser.

        The v1 version primed and re-read suffixes_prefixes_titles; that
        cache is gone, so this pins the same contract -- post-unpickle
        mutations are honored -- through an actual parse.
        """
        c = Constants()
        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))
        hn = HumanName("Posttitle Jane Smith", constants=restored)
        self.m(hn.title, "", hn)
        restored.titles.add('posttitle')
        hn.parse_full_name()
        self.m(hn.title, "Posttitle", hn)

    def test_replaced_manager_is_wired_for_change_tracking(self) -> None:
        """Wholesale manager replacement must wire the new manager's mutations.

        Covers the config-teardown path where a fresh SetManager is assigned
        directly (v1 pinned this via the suffixes_prefixes_titles cache; the
        2.0 contract is that both the replacement and the new manager's own
        later mutations are honored by the next parse).
        """
        c = Constants()
        hn = HumanName("Brandnewtitle Jane Smith", constants=c)
        self.m(hn.title, "", hn)
        c.titles = SetManager(['brandnewtitle'])
        hn.parse_full_name()
        # The replacement is reflected...
        self.m(hn.title, "Brandnewtitle", hn)
        # ...and the new manager's own mutations are tracked too, proving
        # the change callback was re-wired to the replacement.
        c.titles.add('secondtitle')
        hn.full_name = "Secondtitle Jane Smith"
        self.m(hn.title, "Secondtitle", hn)

    def test_tuplemanager_delattr_removes_dict_entry(self) -> None:
        """Deleting a non-dunder attribute must remove the dict entry.

        TupleManager routes non-dunder attribute deletion to ``del self[attr]``
        (the mirror of its dot-notation __setattr__), so ``del tm.key`` and
        ``del tm['key']`` are the same operation.
        """
        c = Constants()
        self.assertIn('ii', c.capitalization_exceptions)
        del c.capitalization_exceptions.ii  # type: ignore[attr-defined]
        self.assertNotIn('ii', c.capitalization_exceptions)

    def test_assigning_iterable_to_set_attr_wraps_and_normalizes(self) -> None:
        """Assigning a plain iterable to a set field wraps it in a SetManager.

        2.0 divergence from v1's guard: v1 demanded a pre-built SetManager
        (raising TypeError otherwise) because a bare collection would have
        broken its cache-invalidation wiring; the shim wraps the value itself
        (with full element validation and normalization), which protects the
        same invariant -- change tracking stays wired -- without the ceremony.
        Bare strings still raise (below), so #241's silent substring-test
        corruption stays impossible.
        """
        c = Constants()
        c.titles = ['Mr.', 'ms']  # type: ignore[assignment]
        self.assertEqual(type(c.titles), SetManager)
        self.assertEqual(set(c.titles), {'mr', 'ms'})
        for name in ('first_name_titles', 'conjunctions', 'bound_first_names',
                     'non_first_name_prefixes', 'suffix_acronyms_ambiguous'):
            setattr(c, name, ['X.'])
            self.assertEqual(type(getattr(c, name)), SetManager)
            self.assertIn('x', getattr(c, name))

    def test_bare_string_assignment_to_conjunctions_raises(self) -> None:
        # the original #241 repro: 'and' assigned as a bare str would
        # silently degrade `piece.lower() in self.C.conjunctions` into a
        # substring test (or, wrapped naively, shred into {'a','n','d'})
        c = Constants()
        with pytest.raises(TypeError, match='wrap it in a list'):
            c.conjunctions = 'and'  # type: ignore[assignment]


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


class ConstantsReprTests(HumanNameTestBase):
    # The name lists live here rather than reading v1's
    # Constants._repr_collection_attrs/_repr_scalar_attrs class attributes,
    # which were internals and are gone in 2.0 (the shim keeps them as
    # module-level tuples). empty_attribute_default left the scalar list
    # with #255.
    collection_attrs = (
        'prefixes', 'suffix_acronyms', 'suffix_not_acronyms', 'titles',
        'first_name_titles', 'conjunctions', 'bound_first_names',
        'non_first_name_prefixes', 'suffix_acronyms_ambiguous',
    )
    scalar_attrs = (
        'string_format', 'initials_format', 'initials_delimiter',
        'initials_separator', 'suffix_delimiter', 'capitalize_name',
        'force_mixed_case_capitalization', 'patronymic_name_order',
        'middle_name_as_last',
    )

    def test_repr_reports_actual_collection_sizes(self) -> None:
        c = Constants()
        repr_str = repr(c)
        for name in self.collection_attrs:
            self.assertIn(f"{name}: {len(getattr(c, name))}", repr_str)

    def test_repr_omits_scalars_at_default_value(self) -> None:
        c = Constants()
        repr_str = repr(c)
        for name in self.scalar_attrs:
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

    def test_copy_preserves_scalar_override_without_warning(self) -> None:
        # copy() restores saved state rather than replaying user
        # assignments, so it must carry scalar overrides across silently.
        # (The v1 vehicle for this test, empty_attribute_default, was
        # removed in 2.0 -- #255.)
        c = Constants()
        c.string_format = "{last}"
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            dup = c.copy()
        self.assertEqual(dup.string_format, "{last}")

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


class ConstantsNoneRemovalTests(HumanNameTestBase):
    """constants=None was removed in 2.0 (#261, warned since 1.3.1).

    The v1 fallback silently built a fresh Constants(), discarding any
    customizations the caller may have expected to carry over; 2.0 raises
    TypeError at every entry point instead.
    """

    def test_explicit_none_raises_on_construction(self) -> None:
        with pytest.raises(TypeError, match="261"):
            HumanName("John Doe", constants=None)  # type: ignore[arg-type]

    def test_explicit_none_raises_on_positional_argument(self) -> None:
        with pytest.raises(TypeError, match="261"):
            HumanName("John Doe", None)  # type: ignore[arg-type]

    def test_explicit_none_raises_on_c_setter(self) -> None:
        hn = HumanName("John Doe")
        with pytest.raises(TypeError, match="261"):
            hn.C = None  # type: ignore[assignment]

    def test_none_error_names_the_replacement(self) -> None:
        with pytest.raises(TypeError) as excinfo:
            HumanName("John Doe", constants=None)  # type: ignore[arg-type]
        self.assertIn("Constants", str(excinfo.value))

    def test_omitted_constants_argument_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            HumanName("John Doe")

    def test_explicit_own_constants_instance_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            HumanName("John Doe", constants=Constants())
