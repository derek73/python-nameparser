"""The 2.0 HumanName facade (mechanisms.md#FACADE-CONTRACT)."""
import copy
import pickle
import warnings
from pathlib import Path

import pytest

from nameparser._config_shim import CONSTANTS, Constants
from nameparser._facade import HumanName
from nameparser._types import UNCLASSIFIED_TAG, Role, Token

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


def test_list_attributes_are_snapshots() -> None:
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


def test_the_joined_tag_never_reaches_a_title(  # #429 regression guard
) -> None:
    """The "joined" tag is role-BLIND and _list_tokens_for heals it for
    every role (_list_for is only the string view built from that walk),
    so a tag placed for the suffix view is read by the title view too.

    So the pass that writes it (post_rules' R1 entry pass, #436) walks
    the SUFFIX tokens alone and reads every other role as transparent
    to the run rather than as part of it. #429's first draft, over the
    piece-shaped join this replaced, let any piece open an entry: a
    title piece doing so tagged the title behind it, and title_list
    collapsed. The shape of that bug survives the rewrite, which is why
    this guard does.

    Asserted on the LIST views because the string views cannot see it --
    titles render space-joined either way, which is why the case table
    and the differential (both string-only) stayed green while this was
    broken.
    """
    n = HumanName("Smith, Rev. Dr.")
    assert n.title == "Rev. Dr."             # unchanged, and why it hid
    assert n.title_list == ["Rev.", "Dr."]   # TWO elements

    # The other half: with a suffix already standing from the pre-comma
    # segment, a title opening the entry glued the next suffix backward
    # across the writer's own comma.
    m = HumanName("Smith Jr., Mr. Jr.")
    assert m.suffix == "Jr., Jr."
    assert m.suffix_list == ["Jr.", "Jr."]

    # The control: where the pieces really are one entry, they DO heal.
    k = HumanName("Smith, MD PhD")
    assert k.suffix_list == ["MD PhD"]        # ONE element

    # And the pin for the _RENDERS_ELSEWHERE transparency itself, which
    # the three above miss: a role that renders elsewhere is stepped
    # OVER by the pass -- it pairs each SUFFIX with the NEXT SUFFIX --
    # and is never stepped onto. Pair a suffix with the tokens that
    # follow it instead, and MD reaches both titles here in its own
    # comma bucket with nothing parting them: both are tagged, and
    # title_list collapses to ['Rev. Dr.']. It needs a suffix word
    # FIRST, so a run is legitimately open, and then TWO titles --
    # which is why 'Smith, Rev. Dr.' above (no suffix at all, so the
    # pass never runs) cannot reach this mutant.
    j = HumanName("Smith, MD Rev. Dr.")
    assert j.suffix == "MD"
    assert j.title == "Rev. Dr."             # identical either way
    assert j.title_list == ["Rev.", "Dr."]   # the mutant gives ['Rev. Dr.']


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


def test_assigning_v2_field_spellings_warns_but_still_sets() -> None:
    # "given"/"family" are 2.0 spellings the facade has no attribute
    # for, so plain assignment silently forks the name: a stray
    # instance attribute appears while the parse (and .first/.last)
    # keeps the old value. Warn -- but still set, so any v1-legal code
    # that worked keeps working.
    hn = HumanName("John Smith")
    with pytest.warns(UserWarning, match=r"use \.first"):
        hn.given = "Jane"  # type: ignore[attr-defined]
    assert hn.given == "Jane"  # type: ignore[attr-defined]  # stray attr still set
    assert hn.first == "John"      # the parse did not change
    with pytest.warns(UserWarning, match=r"use \.last"):
        setattr(hn, Role.FAMILY, "Doe")   # StrEnum member, same trap


def test_other_attribute_assignment_stays_silent() -> None:
    # The five 2.0 field names that ARE facade properties go through
    # their setters; the v1 spellings work; ad-hoc attribute stashing
    # is a legal v1 pattern. None of these warn.
    hn = HumanName("John Smith")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        hn.title = "Dr."
        hn.first = "Jane"
        hn.my_cache = 42  # type: ignore[attr-defined]
    assert hn.title == "Dr." and hn.first == "Jane"


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


def test_facade_reads_wholly_han_names_family_first() -> None:
    # classified fix(#271): script_orders reaches the v1 surface.
    # Constants has no opt-out knob (v1 surface is frozen); the
    # migration path is v2 Policy(script_orders={}).
    n = HumanName("毛 泽东")
    assert (n.last, n.first) == ("毛", "泽东")
    # unsplit (Han segmentation is locales.ZH, v2-only), but the lone
    # wholly-Han token now takes the family role, not first
    assert HumanName("毛泽东").last == "毛泽东"
    assert HumanName("毛泽东").first == ""


def test_facade_reads_kana_licensed_names_family_first() -> None:
    n = HumanName("高橋 みなみ")
    assert (n.last, n.first) == ("高橋", "みなみ")


def test_facade_parses_unspaced_korean_by_default() -> None:
    # the default-behavior fix flows through the v1 facade (its
    # lexicon mirrors Lexicon.default() via the shim snapshot)
    n = HumanName("김민준")
    assert (n.last, n.first) == ("김", "민준")


def test_list_tokens_for_carries_the_list_view_s_own_elements() -> None:
    # #528: the initials view needs the TOKEN behind each word, and the
    # element boundaries are the whole point -- a "joined" continuation
    # belongs to its predecessor's part and a folded middle sorts first.
    # One walk builds both views so they cannot drift apart.
    #
    # Verified at review (2026-09-13): 0 mismatches between
    # _list_tokens_for's join and _list_for's own output over the
    # full corpus, 1173 non-empty names (the glob holds 1174 distinct
    # names, one of them empty) x 7 members = 8211 pairs. That sweep
    # can't fail by construction -- _list_for IS DEFINED as that join
    # -- so it does not stand as a test by itself. What a per-token
    # walk COULD get wrong is the element BOUNDARIES, so this pins the
    # three shapes where that could diverge by name: a folded middle
    # (reordered ahead of the other parts), a "joined" continuation
    # (two tokens sharing one element), and a spliced field
    # (UNCLASSIFIED_TAG tokens from replace(), no STABLE tag to walk).
    folded_c = Constants()
    folded_c.middle_name_as_last = True
    spliced = HumanName("john smith")
    spliced.middle = "e f"
    cases: list[tuple[HumanName, str, list[list[str]], list[str]]] = [
        (HumanName("Hassan, Mohamad Ahmad Ali", constants=folded_c), "last",
         [["Ahmad"], ["Ali"], ["Hassan"]],             # folded middle, first
         ["Ahmad", "Ali", "Hassan"]),
        (HumanName("Ph. D., John"), "last",
         [["Ph.", "D."]],                              # "joined" continuation
         ["Ph. D."]),
        (spliced, "middle", [["e"], ["f"]],            # spliced field
         ["e", "f"]),
    ]
    for n, member, expected_shape, expected_str in cases:
        groups = n._list_tokens_for(member)
        assert [[t.text for t in g] for g in groups] == expected_shape, \
            (n.original, member)
        # Asserted against its own literal, not against _list_for(member) --
        # _list_for IS DEFINED as this same join, so comparing the two
        # can't fail by construction (measured; see the comment above).
        assert n._list_for(member) == expected_str, (n.original, member)

    for name in ("Ph. D., John", "Dr. Juan Q. Xavier de la Vega III",
                 "der, y van", "JUAN GARCIA Y LOPEZ", "Doe, John A."):
        n = HumanName(name)
        for member in ("title", "first", "middle", "last", "suffix",
                       "nickname", "maiden"):
            groups = n._list_tokens_for(member)
            # `all(g for g in groups)` cannot fail by construction either --
            # _list_tokens_for never emits an empty group, vacuously true
            # (including over the empty list every unused member here
            # returns). What IS worth pinning: a second call returns an
            # EQUAL grouping. That is not a given for free -- a one-shot
            # walk built over an exhausted iterator behind tokens_for()
            # would return nothing at all the second time, not merely a
            # fresh-but-equal list, so this assert would catch that shape
            # of bug too.
            assert n._list_tokens_for(member) == groups, (name, member)


def test_token_is_conjunction_reads_the_tag_then_the_vocabulary() -> None:
    # #528, the two-way decision. A token the parser classified answers
    # from its tags -- the source the core's initials() reads
    # (mechanisms.md#RENDER-HONORS-THE-PARSE) -- so a one-case 'e' that
    # rules.md#P3 tagged `initial` is a name word and a bare capital 'Y'
    # that P3 tagged `conjunction` is not, which is the reverse of what
    # the vocabulary-and-shape test said about either.
    parsed = HumanName("JUAN Y GARCIA")
    tags = {t.text: t for t in parsed._parsed.tokens}
    assert parsed._token_is_conjunction(tags["Y"]) is True
    assert parsed._token_is_conjunction(tags["JUAN"]) is False

    fork = HumanName("john e smith")
    e = {t.text: t for t in fork._parsed.tokens}["e"]
    assert fork._token_is_conjunction(e) is False

    # A field spliced in as raw text was read by no parse, so there is
    # no tag to honor and the vocabulary answers -- the same fallback
    # rules.md#R4's case repair takes, through the same helper.
    spliced = HumanName("john smith")
    spliced.middle = "e"
    lower = spliced._parsed.tokens_for(Role.MIDDLE)[0]
    assert UNCLASSIFIED_TAG in lower.tags
    assert spliced._token_is_conjunction(lower) is True
    spliced.middle = "E"
    upper = spliced._parsed.tokens_for(Role.MIDDLE)[0]
    assert spliced._token_is_conjunction(upper) is False


def test_token_is_conjunction_resolves_an_unresolved_instance() -> None:
    # _token_is_conjunction calls self._resolve() before reading
    # self._lexicon (see the comment on that call). Pinning that it is
    # load-bearing, not defensive dead code: a keyword-constructed
    # HumanName never runs the full-string parse path other callers
    # rely on to have resolved already, so _lexicon is absent here
    # until this method's own _resolve() call builds it.
    hn = HumanName(first="John", middle="y", last="Smith")
    assert not hasattr(hn, "_lexicon")
    tok = hn._list_tokens_for("middle")[0][0]
    assert hn._token_is_conjunction(tok) is True


def test_process_initial_direct_call_keeps_the_v1_string_path() -> None:
    # tests/test_initials.py calls this with a bare string and no
    # tokens, which is v1's shape and stays supported: with no tokens
    # there is no parse to honor, so every word takes the spliced-text
    # fallback -- the reading this method had for every word before
    # #528. These five are measured, not predicted. _process_initial
    # joins with initials_separator only (never initials_delimiter --
    # that is applied by the caller in initials()), so the bare-string
    # probes with the default Constants come back undotted: 'j s' and
    # 'J Y G', not 'j. s.' / 'J. Y. G.'.
    hn = HumanName("", initials_separator="-", initials_delimiter=".")
    assert hn._process_initial("Van Berg", firstname=True) == "V-B"
    hn2 = HumanName("", initials_separator="")
    assert hn2._process_initial("Van Berg", firstname=True) == "VB"
    hn3 = HumanName("")
    assert hn3._process_initial("john e smith") == "j s"
    assert hn3._process_initial("JUAN Y GARCIA") == "J Y G"
    assert hn3._process_initial("de la") == ""


def test_process_initial_with_tokens_reads_the_parse() -> None:
    # The same two name parts, this time handed the tokens the parse
    # built: the answer flips on both, which is #528 in one assertion.
    hn = HumanName("JUAN Y GARCIA")
    middle = hn._list_tokens_for("middle")[0]
    assert hn._process_initial("", firstname=False, tokens=middle) == ""
    fork = HumanName("john e smith")
    fork_middle = fork._list_tokens_for("middle")[0]
    assert fork._process_initial("", firstname=False,
                                 tokens=fork_middle) == "e"


def test_v1_signature_override_raises_from_initials() -> None:
    # The stated break (Derek, 2026-09-13): _initials_lists always
    # calls _process_initial with `tokens=`, so a subclass overriding
    # it with v1's two-argument signature (name_part, firstname=False)
    # raises TypeError the moment initials() runs, rather than being
    # silently skipped. Accepted over the alternative -- a string
    # wrapper kept over a token core -- which would make such an
    # override silently ineffective instead: the override would look
    # like it works and never actually run. Cited by the docs commit
    # as the accepted cost of #528's move to tokens.
    class LegacyOverride(HumanName):
        # Deliberately v1's narrower signature -- the incompatibility
        # IS the break under test, not a typing slip.
        def _process_initial(self, name_part: str,  # type: ignore[override]
                             firstname: bool = False) -> str:
            return super()._process_initial(name_part, firstname)

    hn = LegacyOverride("John Smith")
    with pytest.raises(TypeError, match="tokens"):
        hn.initials()


def test_an_override_that_forwards_tokens_keeps_working() -> None:
    # The remedy for the break above, pinned because the OBVIOUS
    # remedy is wrong in the quiet direction: widening the signature
    # alone -- `**kwargs`, or a `tokens=None` the super() call drops --
    # leaves the override reading `name_part`, which the token path
    # now passes as the group's own text (Derek, 2026-09-14 -- #528
    # passed "" here originally), so a widen-only override takes the
    # STRING path instead of raising or going silent: it gets the
    # PRE-#528 answer, computed from the vocabulary fallback rather
    # than the parse. "john e smith" is where the two views disagree
    # -- the parse TAGS the middle "e" an initial
    # (test_process_initial_with_tokens_reads_the_parse); rules.md#P3's
    # one-case fork reads it from the vocabulary, not from its shape,
    # which is exactly why the bare-word vocabulary fallback below
    # reads it the other way -- "e" is not initial-SHAPED by any
    # pattern over the bare word, so a fallback with no parse behind it
    # reads lowercase "e" as the
    # without #528's fix. Accepting AND FORWARDING `tokens` is still
    # the only way to receive the fix. decisions.md#R3's 2026-09-13
    # entry (amended 2026-09-14) and the 2.4.0 release note both
    # state this.
    class Forwards(HumanName):
        def _process_initial(self, name_part: str,
                             firstname: bool = False,
                             tokens: tuple[Token, ...] | None = None) -> str:
            return super()._process_initial(name_part, firstname,
                                            tokens=tokens)

    class WidensOnly(HumanName):
        # The recorded negative control. `**kwargs` is the spelling a
        # reader reaches for first, and mypy rejects it here -- worth
        # noting, since a typed caller is warned and an untyped one is
        # not, which is who this control is written for.
        def _process_initial(self, name_part: str,  # type: ignore[override]
                             firstname: bool = False,
                             **kwargs: object) -> str:
            return super()._process_initial(name_part, firstname)

    assert HumanName("john e smith").initials() == "j. e. s."
    assert Forwards("john e smith").initials() == "j. e. s."
    assert WidensOnly("john e smith").initials() == "j. s."

    # The multi-token-group pin: "Ph." + "D." is a "joined" continuation
    # (_list_tokens_for), the only producer of a group with more than one
    # token, so it is the one place the join's SHAPE -- space-separated,
    # both words -- is observable at all. A join without the separator,
    # or with only one token, gives "J. P." / "J. D." and passes every
    # single-token name; this is what actually exercises `zip(words,
    # conjunctions, strict=True)` over more than one element per group.
    # Measured 2026-09-14.
    assert HumanName("Ph. D., John").initials() == "J. P D."
    assert Forwards("Ph. D., John").initials() == "J. P D."
    assert WidensOnly("Ph. D., John").initials() == "J. P D."
    assert (WidensOnly("Ph. D., John", initials_separator="-").initials()
            == "J. P-D.")


def test_initials_honor_an_overridden_list_property() -> None:
    # F1, second review round: before #528, _initials_lists read
    # self.first_list/middle_list/last_list -- public properties a v1
    # subclass may override -- and #528 switched it to the private
    # token walk (_list_tokens_for) directly, which does not consult
    # such an override. last_base/surnames/given_names still honor it
    # (they route through _split_last, which reads self.last_list), so
    # initials() alone went silently stale. The fix detects an
    # overridden property per member (a cheap class-attribute identity
    # check) and, for that member only, takes the pre-#528 STRING path
    # over the override's own strings -- same degradation a
    # WidensOnly-style _process_initial override gets, and the same
    # pre-#528 answer. Measured 2026-09-14 against `git show
    # 338daf7:nameparser/_facade.py` (before #528): both values below
    # are that package's answer for the same construction.
    class Sub(HumanName):
        @property
        def first_list(self) -> list[str]:
            return [p.upper() for p in super().first_list]

        @property
        def middle_list(self) -> list[str]:
            return [p for p in super().middle_list if not p.startswith("X")]

        @property
        def last_list(self) -> list[str]:
            return ["Zorro"]

    sub = Sub("john Xavier smith")
    assert sub.initials() == "J. Z."
    # last_base/surnames already honored the override before this fix;
    # pinned here so a future change can't silently regress it back
    # into agreement with initials() for the wrong reason.
    assert sub.last_base == "Zorro"
    assert sub.surnames == "Zorro"

    class SubLastOnly(HumanName):
        @property
        def last_list(self) -> list[str]:
            return ["Zorro"]

    # Only ONE property overridden: first/middle are un-overridden and
    # must keep the (post-#528) TOKEN path -- the middle "e" is "e."
    # because the parse tagged it an initial, not the connective -- and
    # only last takes the string path and the override's "Zorro".
    assert SubLastOnly("john e smith").initials() == "j. e. Z."


def test_initials_of_a_spliced_field_ask_the_vocabulary() -> None:
    # A field assigned after the parse is raw text: ParsedName.replace()
    # stamps UNCLASSIFIED_TAG on it, which says the words were read by
    # nothing rather than read and found plain. There is no tag to
    # honor, so this view falls back to the vocabulary for the one
    # question a word can answer alone -- the same fallback and the
    # same helper as rules.md#R4's case repair. The lowercase spelling
    # reads as the connective and drops; the capital is initial-shaped
    # and stays, keeping the letter's case as every initial does.
    lower = HumanName("john smith")
    lower.middle = "e"
    assert lower.initials() == "j. s."
    upper = HumanName("john smith")
    upper.middle = "E"
    assert upper.initials() == "j. E. s."


def test_initials_freeze_the_connective_answer_at_parse_time() -> None:
    # The accepted cost of #528 (Derek, 2026-09-13): for a word backed
    # by a token, "is this the connective" is decided when the name is
    # parsed, exactly as capitalize()'s answer already was. A
    # vocabulary edit after the parse therefore takes effect on the
    # next full_name assignment, not on the next initials() call.
    # A local Constants, never CONSTANTS: the shared singleton would
    # leak the removal into every later test in the process.
    constants = Constants()
    name = HumanName("juan y garcia", constants=constants)
    assert name.initials() == "j. g."
    constants.conjunctions.remove("y")
    assert name.initials() == "j. g."           # frozen at parse time
    # capitalize() has behaved this way all along, which is the
    # precedent this cost was accepted on
    name.capitalize()
    assert str(name) == "Juan y Garcia"
    name.full_name = "juan y garcia"            # re-parse applies it
    assert name.initials() == "j. y. g."


def test_initials_of_an_unpickled_or_copied_name_ask_the_vocabulary_too() -> None:
    # __setstate__ is the second producer of UNCLASSIFIED_TAG tokens: a
    # v1 pickle carries the *_list STRINGS and no tags, so a restored
    # name is spliced text throughout and takes the fallback above.
    # That makes it disagree with a live parse of the same string on
    # the two names rules.md#P3's one-case fork moved -- which
    # capitalize() has done since the tag was introduced, for the same
    # reason and through the same helper. Pinned rather than left to
    # prose; decisions.md#R3 records it.
    #
    # copy.copy and copy.deepcopy go through the same __getstate__/
    # __setstate__ hooks as pickle -- HumanName's own pair, defined
    # right here in nameparser/_facade.py (not nameparser/_types.py's
    # guarded pair, which belongs to a different set of classes) -- so
    # a copied name takes the identical vocabulary fallback -- measured,
    # not assumed.
    for name, live_initials, restored_initials, live_cap, restored_cap in (
            ("JUAN Y GARCIA", "J. G.", "J. Y. G.",
             "Juan y Garcia", "Juan Y Garcia"),
            ("john e smith", "j. e. s.", "j. s.",
             "John E Smith", "John e Smith")):
        assert HumanName(name).initials() == live_initials
        deep = copy.deepcopy(HumanName(name))
        assert deep.initials() == restored_initials
        shallow = copy.copy(HumanName(name))
        assert shallow.initials() == restored_initials
        restored = pickle.loads(pickle.dumps(HumanName(name)))
        assert restored.initials() == restored_initials
        live = HumanName(name)
        live.capitalize()
        assert str(live) == live_cap
        restored.capitalize()
        assert str(restored) == restored_cap
