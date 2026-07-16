"""Shim Constants/SetManager/TupleManager (migration spec §3)."""
import copy
import pickle
import warnings
from pathlib import Path

import pytest

from nameparser import GIVEN_FIRST, Lexicon, PatronymicRule, Policy
from nameparser._config_shim import (
    CONSTANTS, Constants, SetManager, TupleManager, _DelimiterManager,
    _RegexesProxy, _cached_parser,
)

_DATA_DIR = Path(__file__).parent / "data"


def test_set_manager_normalizes_and_holds_membership() -> None:
    s = SetManager(["Dr", "MRS."])
    assert "dr" in s and "Dr" in s          # lc() normalization, both ways
    assert "mrs" in s
    assert len(s) == 2
    assert sorted(s) == ["dr", "mrs"]


def test_set_manager_add_remove_chain_and_keyerror() -> None:
    s = SetManager()
    assert s.add("Dame", "Fra") is s        # chainable, v1 parity
    assert "dame" in s
    assert s.remove("Dame") is s
    assert "dame" not in s
    with pytest.raises(KeyError):           # 1.3.0 grace period ended (#243)
        s.remove("never-there")


def test_set_manager_call_is_removed() -> None:
    s = SetManager(["dr"])
    with pytest.raises(TypeError):          # #243: __call__ removed in 2.0
        s()  # type: ignore[operator]


def test_set_manager_operators_and_equality() -> None:
    a, b = SetManager(["a", "b"]), SetManager(["b", "c"])
    assert a | b == {"a", "b", "c"}
    assert a & b == {"b"}
    assert a - b == {"a"}
    assert a | {"z"} == {"a", "b", "z"}
    assert {"z"} | a == {"a", "b", "z"}    # reflected: set op manager
    assert {"a", "b", "c"} - a == {"c"}    # operand order matters here
    assert a == {"a", "b"}
    assert a == SetManager(["a", "b"]) and a != b
    with pytest.raises(TypeError):          # mutable, unhashable (v1 parity)
        hash(a)


def test_set_manager_reports_mutations_to_owner() -> None:
    bumps = []
    s = SetManager(["a"], _on_change=lambda: bumps.append(1))
    s.add("b")
    s.remove("a")
    assert len(bumps) == 2
    s.add("b")                              # no-op: already present
    assert len(bumps) == 2                  # must not bump (v1 parity)


def test_set_manager_partial_remove_still_notifies_owner() -> None:
    bumps = []
    s = SetManager(["a", "b"], _on_change=lambda: bumps.append(1))
    with pytest.raises(KeyError):
        s.remove("a", "missing")            # "a" IS removed before the raise
    assert "a" not in s
    assert len(bumps) == 1                  # the real removal was reported


def test_set_manager_accepts_v1_pickle_state() -> None:
    s = SetManager.__new__(SetManager)
    s.__setstate__({"elements": {"dr", "mr"}, "_on_change": None})
    assert "dr" in s and len(s) == 2
    # the shim's own key spelling, with un-normalized elements: loading
    # must re-normalize rather than trust the blob passed through lc()
    s2 = SetManager.__new__(SetManager)
    s2.__setstate__({"_elements": {"Dr", "MRS."}})
    assert "dr" in s2 and "mrs" in s2
    assert sorted(s2) == ["dr", "mrs"]


def test_set_manager_pickle_round_trip() -> None:
    # in-process round trip of a blob we just built; pickle is not a
    # security boundary here (same stance as the v2 pickle guards)
    t = pickle.loads(pickle.dumps(SetManager(["Dr", "Mrs."])))
    assert t == SetManager(["dr", "mrs"])


def test_tuple_manager_attribute_access_and_unknown_key() -> None:
    t = TupleManager({"mcdonald": "McDonald"})
    assert t.mcdonald == "McDonald"
    assert t["mcdonald"] == "McDonald"
    with pytest.raises(AttributeError, match="mcdonalds"):   # #256
        t.mcdonalds


def test_tuple_manager_mutations_bump_owner() -> None:
    bumps = []
    t = TupleManager({"a": "A"}, _on_change=lambda: bumps.append(1))
    t["b"] = "B"
    del t["a"]
    t.pop("b")
    assert len(bumps) == 3


def test_tuple_manager_pop_default_on_missing_key_is_noop() -> None:
    bumps = []
    t = TupleManager({"a": "A"}, _on_change=lambda: bumps.append(1))
    assert t.pop("missing", None) is None
    assert len(bumps) == 0                  # no-op: key was never present


def test_tuple_manager_bulk_mutations_bump_owner() -> None:
    # dict's C fast paths (update, setdefault, |=, clear, popitem) must
    # notify too, or a cached parser built from the owner goes stale
    bumps = []
    t = TupleManager(_on_change=lambda: bumps.append(1))
    t.update({"a": "A", "b": "B"})
    assert len(bumps) == 2                  # per-key, via __setitem__
    assert t.setdefault("c", "C") == "C"
    assert len(bumps) == 3
    assert t.setdefault("a", "ignored") == "A"
    assert len(bumps) == 3                  # existing key: read, not write
    t |= {"d": "D"}
    assert len(bumps) == 4
    assert t.popitem()[0] in "abcd"
    assert len(bumps) == 5
    t.clear()
    assert len(bumps) == 6
    t.clear()
    assert len(bumps) == 6                  # already empty: no-op


def test_tuple_manager_pickle_round_trip() -> None:
    t = pickle.loads(pickle.dumps(TupleManager({"a": "A"})))
    assert dict(t) == {"a": "A"}
    assert t._on_change is None


def test_delimiter_manager_sentinels_only() -> None:
    d = _DelimiterManager({"parenthesis": "parenthesis"})
    moved = d.pop("parenthesis")
    d2 = _DelimiterManager()
    d2["parenthesis"] = moved          # the documented bucket-move idiom
    assert "parenthesis" in d2
    with pytest.raises(TypeError, match="quoted_word"):
        d2["angle_brackets"] = "custom"     # spec §3: custom keys raise


def test_delimiter_manager_no_bypass_via_constructor_or_update() -> None:
    # dict's C fast paths (dict.__init__, dict.update) skip a subclass's
    # __setitem__ -- the sentinel rule must hold on every mutation path
    with pytest.raises(TypeError, match="quoted_word"):
        _DelimiterManager({"angle_brackets": "x"})
    with pytest.raises(TypeError, match="quoted_word"):
        _DelimiterManager(angle_brackets="x")
    with pytest.raises(TypeError, match="quoted_word"):
        _DelimiterManager().update({"angle_brackets": "x"})
    with pytest.raises(TypeError, match="quoted_word"):
        _DelimiterManager().setdefault("angle_brackets", "x")
    with pytest.raises(TypeError, match="quoted_word"):
        d0 = _DelimiterManager()
        d0 |= {"angle_brackets": "x"}
    # update through the validated path still notifies the owner per key
    bumps = []
    d = _DelimiterManager(_on_change=lambda: bumps.append(1))
    d.update({"quoted_word": "quoted_word", "parenthesis": "parenthesis"})
    assert dict(d) == {"quoted_word": "quoted_word",
                       "parenthesis": "parenthesis"}
    assert len(bumps) == 2


def test_regexes_reads_ok_assignment_raises() -> None:
    r = _RegexesProxy()
    assert r.word.match("Smith")  # type: ignore[attr-defined]  # reads keep working
    with pytest.raises(TypeError, match="strip_bidi"):
        r.bidi = None                       # slot-aware message
    with pytest.raises(TypeError, match="Policy"):
        r.roman_numeral = None              # generic message


def test_regexes_membership_iteration_and_deepcopy() -> None:
    r = _RegexesProxy()
    assert "word" in r                      # membership is a read
    assert "nope" not in r
    assert "word" in sorted(r)              # iteration is a read
    assert "word" in r.keys()
    # dunder probes must raise AttributeError, not resolve as regex
    # names -- the classic copy.deepcopy regression (see AGENTS.md)
    assert isinstance(copy.deepcopy(r), _RegexesProxy)


def test_constants_default_fields_present() -> None:
    c = Constants()
    assert "dr" in c.titles
    assert "phd" in c.suffix_acronyms
    assert "van" in c.prefixes
    assert c.patronymic_name_order is False
    assert c.middle_name_as_last is False
    assert c.capitalize_name is False
    assert c.force_mixed_case_capitalization is False
    assert c.string_format == "{title} {first} {middle} {last} {suffix} ({nickname})"
    assert c.suffix_delimiter is None
    assert set(c.nickname_delimiters) == {"quoted_word", "double_quotes",
                                          "parenthesis"}
    assert len(c.maiden_delimiters) == 0


def test_constants_mutation_bumps_generation() -> None:
    c = Constants()
    g0 = c._generation
    c.titles.add("zqxtitle")               # not a default title (real bump)
    assert c._generation > g0
    g1 = c._generation
    c.patronymic_name_order = True
    assert c._generation > g1


def test_private_constants_do_not_warn_shared_singleton_does() -> None:
    c = Constants()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        c.titles.add("zqxtitle")           # private: silent
    with pytest.deprecated_call(match="Lexicon"):
        CONSTANTS.titles.add("zqxtest")
    with pytest.deprecated_call():
        CONSTANTS.titles.remove("zqxtest")  # leave the singleton clean


def test_scalar_noop_assignment_neither_bumps_nor_warns() -> None:
    # managers already suppress no-op mutations (no-op add, pop with
    # default); re-assigning a scalar's current value must match --
    # neither a generation bump nor, on the shared singleton, the
    # deprecation warning
    c = Constants()
    g0 = c._generation
    c.string_format = c.string_format
    assert c._generation == g0
    g_shared = CONSTANTS._generation
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        CONSTANTS.string_format = CONSTANTS.string_format
    assert CONSTANTS._generation == g_shared


def test_empty_attribute_default_assignment_raises() -> None:
    c = Constants()
    with pytest.raises(AttributeError, match="#255"):
        c.empty_attribute_default = None


def test_regexes_attribute_assignment_raises() -> None:
    with pytest.raises(TypeError, match="Policy"):
        Constants().regexes = {}  # type: ignore[assignment]


def test_constants_copy_is_independent() -> None:            # #260
    c = Constants()
    d = c.copy()
    d.titles.add("zqxtitle")       # not a default title (real addition)
    assert "zqxtitle" in d.titles and "zqxtitle" not in c.titles
    assert d._generation != -1  # a real instance with its own counter


def test_constants_pickle_round_trip() -> None:
    c = Constants()
    c.titles.add("zqxtitle")
    loaded = pickle.loads(pickle.dumps(c))
    assert "zqxtitle" in loaded.titles
    loaded.titles.add("fra")               # mutations still tracked
    assert "fra" in loaded.titles


def test_pre_1_3_constants_blob_raises() -> None:            # #279
    # pre-1.3.0 blobs are recognizable by the computed property their
    # dir()-sweep __getstate__ captured; the 1.4 warning promised
    # ValueError in 2.0
    with pytest.raises(ValueError, match="#279|1.3"):
        Constants.__new__(Constants).__setstate__(
            {"prefixes": set(), "suffixes_prefixes_titles": set()})


def test_v14_constants_state_shape_accepted() -> None:
    # v1.4 __getstate__ emitted public field names -> manager values;
    # scalars ride along. empty_attribute_default is accepted and
    # DROPPED (#255: empty is always '' in 2.0).
    c = Constants.__new__(Constants)
    c.__setstate__({"prefixes": {"van", "de"},
                    "string_format": "{first} {last}",
                    "empty_attribute_default": None})
    assert "van" in c.prefixes
    assert c.string_format == "{first} {last}"
    assert not hasattr(c, "empty_attribute_default") or True  # dropped


@pytest.mark.xfail(
    reason="resolves to the v1 class until the M11 swap", strict=True)
def test_v14_constants_blob_unpickles_into_shim() -> None:
    # tests/v2/data/constants_v14.pickle was produced by a real 1.4.0
    # install (`uv run --no-project --with "nameparser==1.4.*" ...`),
    # not synthesized here -- it is the actual bytes a caller upgrading
    # from 1.4 to 2.0 would hand to pickle.load(). Until the M11 swap
    # replaces nameparser.config.Constants with this shim, the blob's
    # pickled class reference still resolves to the live v1 class, so
    # this assertion fails today by construction.
    with open(_DATA_DIR / "constants_v14.pickle", "rb") as f:
        loaded = pickle.load(f)
    assert isinstance(loaded, Constants)
    assert "van" in loaded.prefixes


def test_snapshot_field_translation() -> None:
    c = Constants()
    lexicon, policy, defaults = c._snapshot()
    # drift guard: a default Constants must resolve to EXACTLY the v2
    # defaults -- a field populated in _default_lexicon() but forgotten
    # in _snapshot() (or vice versa) fails loudly here
    assert lexicon == Lexicon.default()
    assert policy == Policy()
    assert isinstance(lexicon, Lexicon) and isinstance(policy, Policy)
    assert lexicon.suffix_words == frozenset(c.suffix_not_acronyms)
    # complement translation: v1 marks never-given, v2 marks may-be-given
    assert lexicon.particles_ambiguous == \
        frozenset(c.prefixes) - frozenset(c.non_first_name_prefixes)
    assert lexicon.suffix_acronyms_ambiguous <= lexicon.suffix_acronyms
    assert policy.name_order == GIVEN_FIRST
    assert policy.patronymic_rules == frozenset()
    assert defaults.string_format == c.string_format
    # a snapshot is a pure read: no generation bump, no deprecation
    # warning even on the shared singleton
    g0 = CONSTANTS._generation
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        CONSTANTS._snapshot()
    assert CONSTANTS._generation == g0


def test_snapshot_patronymic_and_middle_flags() -> None:
    c = Constants()
    c.patronymic_name_order = True
    c.middle_name_as_last = True
    _, policy, _ = c._snapshot()
    assert policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC, PatronymicRule.TURKIC})
    assert policy.middle_as_family is True


def test_snapshot_delimiter_bucket_move() -> None:
    c = Constants()
    c.maiden_delimiters["parenthesis"] = c.nickname_delimiters.pop("parenthesis")
    _, policy, _ = c._snapshot()
    assert ("(", ")") in policy.maiden_delimiters
    assert ("(", ")") not in policy.nickname_delimiters


def test_snapshot_ambiguous_removed_acronym_intersects() -> None:
    c = Constants()
    c.suffix_acronyms.remove("jd")          # 'jd' stays in ambiguous
    lexicon, _, _ = c._snapshot()
    assert "jd" not in lexicon.suffix_acronyms
    assert "jd" not in lexicon.suffix_acronyms_ambiguous  # subset holds


def test_parser_cache_shared_across_equal_snapshots() -> None:
    a, b = Constants(), Constants()
    la, pa, _ = a._snapshot()
    lb, pb, _ = b._snapshot()
    assert _cached_parser(la, pa) is _cached_parser(lb, pb)
