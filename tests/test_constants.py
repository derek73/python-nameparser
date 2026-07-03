import copy
import pickle
import re
import timeit

from nameparser import HumanName
from nameparser.config import Constants, RegexTupleManager, SetManager, TupleManager
from nameparser.config.regexes import EMPTY_REGEX

from tests.base import HumanNameTestBase


class ConstantsCustomizationTests(HumanNameTestBase):

    def test_add_title(self) -> None:
        hn = HumanName("Te Awanui-a-Rangi Black", constants=None)
        start_len = len(hn.C.titles)
        self.assertTrue(start_len > 0)
        hn.C.titles.add('te')
        self.assertEqual(start_len + 1, len(hn.C.titles))
        hn.parse_full_name()
        self.m(hn.title, "Te", hn)
        self.m(hn.first, "Awanui-a-Rangi", hn)
        self.m(hn.last, "Black", hn)

    def test_remove_title(self) -> None:
        hn = HumanName("Hon Solo", constants=None)
        start_len = len(hn.C.titles)
        self.assertTrue(start_len > 0)
        hn.C.titles.remove('hon')
        self.assertEqual(start_len - 1, len(hn.C.titles))
        hn.parse_full_name()
        self.m(hn.first, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_add_multiple_arguments(self) -> None:
        hn = HumanName("Assoc Dean of Chemistry Robert Johns", constants=None)
        hn.C.titles.add('dean', 'Chemistry')
        hn.parse_full_name()
        self.m(hn.title, "Assoc Dean of Chemistry", hn)
        self.m(hn.first, "Robert", hn)
        self.m(hn.last, "Johns", hn)

    def test_instances_can_have_own_constants(self) -> None:
        hn = HumanName("", None)
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
        hn = HumanName("Ms Hon Solo", constants=None)
        hn.C.titles.remove('hon', 'ms')
        hn.parse_full_name()
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_chain_multiple_arguments(self) -> None:
        hn = HumanName("Dean Ms Hon Solo", constants=None)
        hn.C.titles.remove('hon', 'ms').add('dean')
        hn.parse_full_name()
        self.m(hn.title, "Dean", hn)
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_clear_removes_all_entries(self) -> None:
        hn = HumanName("Ms Hon Solo", constants=None)
        hn.C.titles.clear()
        hn.parse_full_name()
        self.m(hn.first, "Ms", hn)
        self.m(hn.middle, "Hon", hn)
        self.m(hn.last, "Solo", hn)

    def test_empty_attribute_default(self) -> None:
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

    def test_empty_attribute_on_instance(self) -> None:
        hn = HumanName("", None)
        hn.C.empty_attribute_default = None
        self.m(hn.title, None, hn)
        self.m(hn.first, None, hn)
        self.m(hn.middle, None, hn)
        self.m(hn.last, None, hn)
        self.m(hn.suffix, None, hn)
        self.m(hn.nickname, None, hn)

    def test_none_empty_attribute_string_formatting(self) -> None:
        hn = HumanName("", None)
        hn.C.empty_attribute_default = None
        self.assertEqual('', str(hn), hn)

    def test_add_constant_with_explicit_encoding(self) -> None:
        c = Constants()
        c.titles.add_with_encoding(b'b\351ck', encoding='latin_1')
        self.assertIn('béck', c.titles)

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
        c.empty_attribute_default = None

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))

        self.assertEqual(restored.empty_attribute_default, None)

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
        # The EMPTY_REGEX default still applies to genuinely unknown keys.
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
        # Plain TupleManager has no EMPTY_REGEX fallback: unknown keys are None.
        self.assertIsNone(dup.does_not_exist)
        self.assertIsNotNone(dup.curly_braces)

    def test_maiden_delimiters_deepcopy_roundtrip(self) -> None:
        """copy.deepcopy of maiden_delimiters (empty by default) must round-trip."""
        c = Constants()

        dup = copy.deepcopy(c.maiden_delimiters)

        self.assertEqual(type(dup), TupleManager)
        self.assertEqual(dict(dup), {})
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

    def test_regextuplemanager_ignores_dunder_lookups(self) -> None:
        """Unknown dunder names report as absent, not as the EMPTY_REGEX default.

        Dunder names are Python's protocol probes (copy.deepcopy looks up
        __deepcopy__, inspect.unwrap looks up __wrapped__, ...), never config
        keys. Answering them with a regex breaks that machinery.
        """
        c = Constants()
        sentinel = object()

        self.assertEqual(getattr(c.regexes, '__deepcopy__', sentinel), sentinel)
        # A normal (non-dunder) unknown key still yields the EMPTY_REGEX default.
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
        # A normal (non-dunder) unknown key still returns the None default.
        self.assertEqual(tm.unknown_key, None)


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
        hn = HumanName("", constants=None)
        _ = hn.C.suffixes_prefixes_titles  # prime the cache so a stale entry would be observable
        hn.C.titles.add('emerita')
        self.assertFalse(hn.is_rootname('emerita'))

    def test_is_rootname_consistent_with_is_prefix(self) -> None:
        """is_rootname must return False for words recognised by is_prefix."""
        hn = HumanName("", constants=None)
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


class SuffixesPrefixesTitlesPerformanceTests(HumanNameTestBase):
    """Guard against accidental cache removal on suffixes_prefixes_titles.

    This library is commonly used to parse large batches of names, so
    suffixes_prefixes_titles must remain cached.  Without the cache, each call
    rebuilds the union from ~700 strings (~50-100 µs); with it, repeated access
    is ~1000x faster.  This test asserts that 10 000 repeated calls complete
    well within the time a single uncached union build would take.
    """

    def test_repeated_access_is_cached(self) -> None:
        c = Constants()
        first = c.suffixes_prefixes_titles
        second = c.suffixes_prefixes_titles
        assert first is second, "suffixes_prefixes_titles should return the same cached object on repeated access"

        n = 10_000
        elapsed = timeit.timeit(lambda: c.suffixes_prefixes_titles, number=n)

        # One uncached union build over ~700 strings takes ~50-100 µs on any
        # modern machine.  If caching is broken, 10 000 calls would take
        # seconds; with caching they finish in well under 10 ms total.
        limit = 0.010  # 10 ms = 1 µs/call average
        assert elapsed < limit, (
            f"suffixes_prefixes_titles appears uncached: {n} calls took "
            f"{elapsed * 1000:.1f} ms (limit {limit * 1000:.0f} ms). "
            "Was _pst caching removed?"
        )
