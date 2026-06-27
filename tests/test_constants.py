import pickle

from nameparser import HumanName
from nameparser.config import Constants, SetManager

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

    def test_pickle_roundtrip_preserves_instance_scalar_override(self) -> None:
        """An instance-level scalar override must survive a pickle round-trip."""
        c = Constants()
        c.empty_attribute_default = None

        # Safe: round-tripping a Constants the test just built, not untrusted data.
        restored = pickle.loads(pickle.dumps(c))

        self.assertEqual(restored.empty_attribute_default, None)

    def test_unpickle_legacy_state_with_property_key(self) -> None:
        """Pickles written by older versions must still load.

        The previous __getstate__ built its state from a dir() sweep, which
        always included the computed `suffixes_prefixes_titles` property (no
        customization required). That property has no setter, so __setstate__
        must skip such keys instead of raising AttributeError.

        Covers the temporary migration shim in __setstate__; remove this test
        when that shim is dropped (a release or two after 1.2.1).
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
        restored.__setstate__(legacy_state)

        # The real customization is recovered and the property key is ignored.
        self.assertIn('legacytitle', restored.titles)
