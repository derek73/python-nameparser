"""The 2.0 HumanName facade (migration spec §2)."""
import pickle
import warnings
from pathlib import Path

import pytest

from nameparser._config_shim import CONSTANTS, Constants
from nameparser._facade import HumanName
from nameparser._types import Role

_DATA_DIR = Path(__file__).parent / "data"


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


def test_component_kwargs_bypass_parsing() -> None:
    n = HumanName(first="John", last="de la Vega")
    assert n.first == "John" and n.last == "de la Vega"
    assert n.full_name == ""


def test_field_assignment_str_list_none() -> None:
    n = HumanName("John Smith")
    n.first = "Jane"
    assert n.first == "Jane"
    n.middle = ["Q", "Xavier"]               # lists join with space
    assert n.middle == "Q Xavier"
    n.middle = None                          # None clears
    assert n.middle == ""
    assert n.last == "Smith"                 # untouched fields survive
    assert n.full_name == "John Smith"       # no re-parse (v1 parity)


def test_list_attributes_are_snapshots() -> None:          # spec §2 exc. 1
    n = HumanName("John Quincy Adams Smith")
    lst = n.middle_list
    lst.append("HACKED")
    assert "HACKED" not in n.middle_list


def test_derived_views() -> None:
    n = HumanName("Juan Q. de la Vega")
    assert n.surnames == "Q. de la Vega"     # middle + last (v1 shape)
    assert n.given_names == "Juan Q."        # first + middle
    assert n.last_prefixes == "de la"
    assert n.last_base == "Vega"


def test_split_last_all_prefix_guard() -> None:
    n = HumanName(last="de la")              # every word is a particle
    assert n.last_prefixes == ""             # v1 guard: no stripping
    assert n.last_base == "de la"


@pytest.mark.parametrize("member", [
    "title", "first", "middle", "last", "suffix", "nickname", "maiden",
])
def test_every_member_set_get_and_list(member: str) -> None:
    n = HumanName()
    setattr(n, member, "Alpha Beta")
    # the suffix string view joins parts with ", " (v1 parity)
    joined = "Alpha, Beta" if member == "suffix" else "Alpha Beta"
    assert getattr(n, member) == joined
    assert getattr(n, f"{member}_list") == ["Alpha", "Beta"]


def test_list_assignment_rejects_non_str_elements() -> None:
    n = HumanName("John Smith")
    with pytest.raises(TypeError, match="strings"):
        n.first = [1, 2]  # type: ignore[list-item]
    with pytest.raises(TypeError, match="strings"):
        n.first = [None]  # type: ignore[list-item]


def test_list_assignment_multiword_elements_join() -> None:
    n = HumanName("John Smith")
    n.middle = ["ab", "cd ef"]
    assert n.middle == "ab cd ef"


def test_suffix_list_heals_joined_continuations() -> None:  # v1 fix_phd
    n = HumanName("John Ph. D.")
    assert n.suffix == "Ph. D."
    assert n.suffix_list == ["Ph. D."]       # ONE element, v1 parity


def test_str_uses_string_format_with_v1_cleanup() -> None:
    n = HumanName("Dr. Juan de la Vega III")
    assert str(n) == "Dr. Juan de la Vega III"
    n2 = HumanName("John Smith")             # empty nickname: no ' ()'
    assert str(n2) == "John Smith"
    n2.string_format = "{last}, {first}"
    assert str(n2) == "Smith, John"


def test_str_none_format_falls_back_to_space_join() -> None:
    # v1-identical: the format wraps the nickname in parens, the plain
    # member join does not
    n = HumanName('John "Jack" Kennedy')
    assert str(n) == "John Kennedy (Jack)"
    n.string_format = None
    assert str(n) == "John Kennedy Jack"


def test_getitem_unknown_key_raises_attribute_error() -> None:
    n = HumanName("John Smith")
    with pytest.raises(AttributeError):      # v1 behavior, not KeyError
        n["nope"]


def test_repr_v1_shape() -> None:
    r = repr(HumanName("John Smith"))
    assert r.startswith("<HumanName : [")
    assert "first: 'John'" in r and "last: 'Smith'" in r


def test_iter_and_len_count_nonempty() -> None:
    n = HumanName("John Smith")
    assert list(n) == ["John", "Smith"]
    assert len(n) == 2
    assert len(HumanName("")) == 0           # documented emptiness check


def test_getitem_str_ok_slice_raises() -> None:            # #258
    n = HumanName("John Smith")
    assert n["first"] == "John"
    with pytest.raises(TypeError, match="#258"):
        n[1:-1]  # type: ignore[index]
    with pytest.raises(TypeError):
        n["first"] = "Jane"  # type: ignore[index] # no __setitem__ in 2.0


def test_getitem_accepts_role_members() -> None:
    # Role is a StrEnum, so Role members reach __getitem__'s getattr;
    # the v1 spellings (first/last) must resolve for given/family too.
    hn = HumanName("Dr. John Quincy Smith Jr.")
    assert hn[Role.TITLE] == hn.title
    assert hn[Role.GIVEN] == hn.first
    assert hn[Role.MIDDLE] == hn.middle
    assert hn[Role.FAMILY] == hn.last
    assert hn[Role.SUFFIX] == hn.suffix
    assert hn[Role.NICKNAME] == hn.nickname
    assert hn[Role.MAIDEN] == hn.maiden
    # the plain strings work the same way
    assert hn["given"] == hn.first
    assert hn["family"] == hn.last


def test_eq_and_hash_are_object_identity() -> None:        # #223
    a, b = HumanName("John Smith"), HumanName("John Smith")
    assert a != b and a == a
    assert hash(a) != hash(b) or a is b      # default object hash


def test_as_dict_v1_keys() -> None:
    n = HumanName("Dr. John Smith")
    d = n.as_dict()
    assert d["title"] == "Dr." and d["first"] == "John" and d["last"] == "Smith"
    assert set(n.as_dict(include_empty=False)) == {"title", "first", "last"}


def test_initials_v1_semantics() -> None:
    assert HumanName("Sir Bob Andrew Dole").initials() == "B. A. D."
    assert HumanName("Sir Bob Andrew Dole").initials_list() == ["B", "A", "D"]
    n = HumanName("Doe, John A.", initials_delimiter="", initials_separator="")
    assert n.initials() == "J A D"
    # prefixes/conjunctions are filtered except in first names (v1 rule)
    assert HumanName("Juan de la Vega").initials() == "J. V."


def test_initials_format_kwarg() -> None:
    n = HumanName("Sir Bob Andrew Dole", initials_format="{first} {middle}")
    assert n.initials() == "B. A."


def test_render_default_setters_validate() -> None:
    n = HumanName("John Smith")
    with pytest.raises(TypeError, match="initials_delimiter"):
        n.initials_delimiter = 5  # type: ignore[assignment]
    with pytest.raises(TypeError, match="initials_format"):
        n.initials_format = 5  # type: ignore[assignment]
    with pytest.raises(TypeError, match="initials_separator"):
        n.initials_separator = None  # type: ignore[assignment]
    with pytest.raises(TypeError, match="string_format"):
        n.string_format = 5  # type: ignore[assignment]
    with pytest.raises(TypeError, match="suffix_delimiter"):
        n.suffix_delimiter = 5  # type: ignore[assignment]
    n.string_format = None                   # None allowed for these two
    n.suffix_delimiter = None


def test_capitalize_gate_and_force() -> None:
    n = HumanName("bob v. de la macdole-eisenhower phd")
    n.capitalize()
    assert str(n) == "Bob V. de la MacDole-Eisenhower Ph.D."
    m = HumanName("Shirley Maclaine")        # mixed case: untouched
    m.capitalize()
    assert str(m) == "Shirley Maclaine"
    m.capitalize(force=True)
    assert str(m) == "Shirley MacLaine"


def test_force_mixed_case_flag_feeds_default() -> None:
    c = Constants()
    c.force_mixed_case_capitalization = True
    n = HumanName("Shirley Maclaine", constants=c)
    n.capitalize()                           # force=None -> flag -> True
    assert str(n) == "Shirley MacLaine"


def test_matches_and_comparison_key() -> None:
    # NB: the task spec's example compared "Dr. John A. Smith" against
    # "John Smith" -- but matches()/comparison_key() are component-wise
    # over all seven fields (v1 parity, verified against live 1.4), so a
    # title/middle-initial mismatch always fails the match; swapped in
    # case/order variations that actually exercise "case-insensitive,
    # component-wise" without dropping fields.
    n = HumanName("Dr. John A. Smith")
    assert n.matches("dr. john a. smith")
    assert n.matches(HumanName("smith, dr. john a."))
    assert not n.matches("Jane Smith")
    assert n.comparison_key() == HumanName("DR. JOHN A. SMITH").comparison_key()


def test_pickle_round_trip_preserves_components() -> None:
    n = HumanName("Dr. Juan de la Vega III")
    n.first = "Johan"                        # mutated state must survive
    loaded = pickle.loads(pickle.dumps(n))
    assert loaded.first == "Johan"
    assert loaded.last == "de la Vega"
    assert loaded.original == "Dr. Juan de la Vega III"
    assert loaded.C is CONSTANTS             # shared sentinel restored


@pytest.mark.parametrize("bad", [
    "John",             # str: iterating yields characters
    {"John": 1},        # Mapping: iterating yields keys only
    b"John",            # bytes: iterating yields ints
    ["John", None],     # a non-str entry
])
def test_setstate_rejects_malformed_component_lists(bad: object) -> None:
    # _normset on the Lexicon side rejects str AND Mapping AND checks
    # entry types; this guard covered only str, so a dict silently
    # loaded its keys and bytes/None died later with an opaque
    # AttributeError instead of naming the field
    n = HumanName("John Smith")
    state = n.__getstate__()
    state["first_list"] = bad
    loaded = HumanName.__new__(HumanName)
    with pytest.raises(TypeError, match="first_list"):
        loaded.__setstate__(state)


def test_setstate_restores_a_foreign_multi_word_suffix_entry() -> None:
    # the parametrized round-trip tests above go through v2's own
    # __getstate__, which is self-consistent by construction. The case
    # the fix actually protects is a 1.4-produced blob carrying a
    # multi-word suffix entry, so build that state directly.
    n = HumanName("John Smith")
    state = n.__getstate__()
    state["suffix_list"] = ["Ph. D."]
    loaded = HumanName.__new__(HumanName)
    loaded.__setstate__(state)
    assert loaded.suffix_list == ["Ph. D."]
    assert loaded.suffix == "Ph. D."


#: Every name in the 486-name differential corpus whose HumanName pickle
#: round-trip drifted before the __setstate__ element-boundary fix. Each
#: carries a multi-word suffix entry -- a "joined" continuation token --
#: inside one comma segment. Verified against a live 1.4.0: all eight
#: round-trip unchanged there, so drift here is a regression, not an
#: inherited quirk.
_MULTIWORD_SUFFIX_NAMES = [
    "Andrew Perkins, Jr., Col. (Ret)",
    "Clarke, Kenneth, Q.C. M.P.",
    "Doe, John, MD PhD - FACS Fellow",
    "Franklin Washington, Jr. MD",
    "John Smith Ph. D.",
    "John Smith, Ph. D.",
    "John Smith, V Jr.",
    "John Smith, V MD",
]


@pytest.mark.parametrize("raw", _MULTIWORD_SUFFIX_NAMES)
def test_pickle_round_trip_preserves_multiword_suffix_entries(raw: str) -> None:
    # __setstate__ restores components from the pickled *_list values.
    # Joining them into one string and letting replace() re-split on
    # whitespace destroys the entry boundaries, and the suffix view's
    # ", " join then renders one credential as two ("Ph." + "D." ->
    # "Ph., D."). Entries must survive as entries.
    n = HumanName(raw)
    loaded = pickle.loads(pickle.dumps(n))
    assert loaded.suffix_list == n.suffix_list
    assert loaded.suffix == n.suffix
    assert str(loaded) == str(n)
    assert loaded.as_dict() == n.as_dict()


# -- Gap 2: parse_full_name() (v1's documented re-parse idiom) -------------


def test_parse_full_name_reparses_documented_idiom() -> None:
    c = Constants()
    n = HumanName("Zzqtitle Judy Dench", constants=c)
    assert n.title == ""                     # 'zzqtitle' not a default title
    c.titles.add("zzqtitle")                  # mutate C in place, no full_name reassignment
    n.parse_full_name()                       # documented v1 idiom
    assert n.title == "Zzqtitle"


def test_subclass_overriding_parse_full_name_warns() -> None:   # #280
    class CustomReparse(HumanName):
        def parse_full_name(self) -> None:
            pass

    with pytest.deprecated_call(match="parse_full_name"):
        CustomReparse("John Smith")


# -- Gap 3: HumanName.C setter (v1.4 #239) ----------------------------------


def test_c_setter_assigns_and_next_parse_honors_it() -> None:
    n = HumanName("John Smith")
    c2 = Constants()
    c2.titles.add("zzqtitle")
    n.C = c2
    assert n.C is c2
    n.full_name = "Zzqtitle Judy Dench"       # next parse: v1's setter only stored, no reparse
    assert n.title == "Zzqtitle"


def test_c_setter_none_raises_migration_hint() -> None:
    n = HumanName("John Smith")
    with pytest.raises(TypeError, match="constants"):
        n.C = None  # type: ignore[assignment]


def test_c_setter_non_constants_raises() -> None:
    n = HumanName("John Smith")
    with pytest.raises(TypeError):
        n.C = 42  # type: ignore[assignment]


# -- Gap 4: matches() error message names the facade type -------------------


def test_matches_type_error_names_facade_type() -> None:
    n = HumanName("John Smith")
    with pytest.raises(TypeError, match="HumanName"):
        n.matches(None)  # type: ignore[arg-type]


def test_v14_humanname_blob_unpickles() -> None:
    # tests/v2/data/humanname_v14.pickle was produced by a real 1.4.0
    # install (`uv run --no-project --with "nameparser==1.4.*" ...`) on
    # HumanName("Dr. Juan de la Vega III"); components come back exactly
    # as pickled, NOT re-parsed. Since the M11 swap replaced
    # nameparser.parser.HumanName with this facade, the blob's pickled
    # class reference now resolves here (mirrors
    # test_v14_constants_blob_unpickles_into_shim in test_config_shim.py).
    # pickle.load is safe here: humanname_v14.pickle is a repo-controlled
    # fixture generated by this task from a real 1.4.0 install (Step 2
    # above), not data from an untrusted source.
    with open(_DATA_DIR / "humanname_v14.pickle", "rb") as f:
        loaded = pickle.load(f)
    assert isinstance(loaded, HumanName)
    assert loaded.first == "Juan" and loaded.last == "de la Vega"
    assert loaded.title == "Dr." and loaded.suffix == "III"
    assert loaded.original == "Dr. Juan de la Vega III"
    assert loaded.C is CONSTANTS  # shared sentinel restored (v1.4's C: None)


def test_suffix_delimiter_reassignment_after_construction() -> None:
    n = HumanName("Doe, John, RN - CRNA")
    assert n.suffix == "RN - CRNA"          # no delimiter: one entry
    n.suffix_delimiter = " - "
    n.parse_full_name()
    assert n.suffix == "RN, CRNA"           # setter invalidated the Policy
    n.suffix_delimiter = None
    n.parse_full_name()
    assert n.suffix == "RN - CRNA"          # and back


def test_c_swap_keeps_instance_suffix_delimiter() -> None:
    # both invalidation paths together: swapping C must not lose the
    # instance-level delimiter layered onto the new snapshot's Policy
    n = HumanName("Doe, John, RN - CRNA", suffix_delimiter=" - ")
    assert n.suffix == "RN, CRNA"
    n.C = Constants()
    n.parse_full_name()
    assert n.suffix == "RN, CRNA"


def test_failed_reparse_leaves_state_consistent() -> None:
    # _resolve() raising must not leave full_name pointing at the new
    # value over the OLD parsed fields
    n = HumanName("John Smith")

    class _Boom(Exception):
        pass

    def explode() -> None:
        raise _Boom

    n._C = Constants()
    n._C._snapshot = explode  # type: ignore[method-assign, assignment]
    n._snapshot_gen = -1
    with pytest.raises(_Boom):
        n.full_name = "Jane Doe"
    assert n.full_name == "John Smith"
    assert n.first == "John"


def test_middle_as_family_list_view_matches_string_view() -> None:
    # v1 PREPENDED middle_list to last_list; the list view must agree
    # with the string view, not with raw token order
    c = Constants()
    c.middle_name_as_last = True
    n = HumanName("Hassan, Mohamad Ahmad Ali", constants=c)
    assert n.last == "Ahmad Ali Hassan"
    assert n.last_list == ["Ahmad", "Ali", "Hassan"]


def test_cold_import_order_config_first() -> None:
    # the _facade cycle-breaker (import nameparser.config first) is
    # order-dependent; this pins BOTH cold-start directions in fresh
    # interpreters so an import-sorting pass cannot silently break one
    import subprocess
    import sys

    for first in ("nameparser.config", "nameparser._facade"):
        proc = subprocess.run(
            [sys.executable, "-c",
             f"import {first}; import nameparser; "
             f"print(nameparser.HumanName('John Smith').last)"],
            capture_output=True, text=True)
        assert proc.returncode == 0, (first, proc.stderr)
        assert proc.stdout.strip() == "Smith"
