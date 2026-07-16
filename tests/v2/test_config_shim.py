"""Shim Constants/SetManager/TupleManager (migration spec §3)."""
import copy
import pickle

import pytest

from nameparser._config_shim import (
    SetManager, TupleManager, _DelimiterManager, _RegexesProxy,
)


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
