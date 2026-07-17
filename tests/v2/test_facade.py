"""The 2.0 HumanName facade (migration spec §2)."""
import warnings

import pytest

from nameparser._config_shim import CONSTANTS, Constants
from nameparser._facade import HumanName


def test_basic_parse_and_v1_spellings() -> None:
    n = HumanName("Dr. Juan de la Vega III")
    assert n.title == "Dr."
    assert n.first == "Juan"                 # v1 spelling of core 'given'
    assert n.last == "de la Vega"            # v1 spelling of core 'family'
    assert n.suffix == "III"
    assert n.original == "Dr. Juan de la Vega III"
    assert n.full_name == "Dr. Juan de la Vega III"


def test_bytes_raises_with_decode_hint() -> None:            # #245
    with pytest.raises(TypeError, match="decode"):
        HumanName(b"John Smith")  # type: ignore[arg-type]


def test_constants_none_raises_migration_hint() -> None:     # #261
    with pytest.raises(TypeError, match="constants"):
        HumanName("John Smith", constants=None)


def test_full_name_assignment_reparses() -> None:
    n = HumanName("John Smith")
    n.full_name = "Jane Doe"
    assert (n.first, n.last) == ("Jane", "Doe")


def test_private_constants_mutation_honored_lazily() -> None:
    # NB: the task spec's example used "dame" as a marker not in the
    # default titles, but nameparser/config/titles.py already lists
    # "dame" -- swapped in a nonsense marker to keep the test's premise
    # (mutate a private Constants, next parse sees the change) true.
    c = Constants()
    n = HumanName("Zzqtitle Judy Dench", constants=c)
    assert n.title == ""                     # 'zzqtitle' not a default title
    c.titles.add("zzqtitle")
    n.full_name = "Zzqtitle Judy Dench"      # next parse sees the change
    assert n.title == "Zzqtitle"


def test_capitalize_name_flag_capitalizes_on_parse() -> None:
    c = Constants()
    c.capitalize_name = True
    n = HumanName("john smith", constants=c)
    assert (n.first, n.last) == ("John", "Smith")


def test_constructor_suffix_delimiter_layers_onto_policy() -> None:
    n = HumanName("Doe, John, RN - CRNA", constants=Constants(),
                  suffix_delimiter=" - ")
    assert n.suffix == "RN, CRNA"


def test_subclass_overriding_no_hooks_never_warns() -> None:
    class Plain(HumanName):
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Plain("John Smith")


def test_subclass_hook_override_warns_once_per_class() -> None:   # #280
    class Custom(HumanName):
        def parse_pieces(self, parts: object, additional_parts_count: int = 0) -> object:
            return parts

    with pytest.deprecated_call(match="parse_pieces"):
        Custom("John Smith")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Custom("Jane Doe")                   # second instance: silent


def test_c_property_and_has_own_config() -> None:
    n = HumanName("John Smith")
    assert n.C is CONSTANTS
    assert n.has_own_config is False
    m = HumanName("John Smith", constants=Constants())
    assert m.has_own_config is True


def test_dirty_tracking_reuses_cached_parser_across_unchanged_generation() -> None:
    n = HumanName("John Smith")
    assert n._resolve() is n._resolve()

    c = Constants()
    m = HumanName("John Smith", constants=c)
    parser_before = m._resolve()
    c.titles.add("zzq")  # bumps the generation
    parser_after = m._resolve()
    assert parser_before is not parser_after
