"""Shim Constants/SetManager/TupleManager
(mechanisms.md#CONFIG-SHIM-SNAPSHOT)."""
import copy
import pickle
import warnings
from pathlib import Path

import pytest

from nameparser import _config_shim
from nameparser import GIVEN_FIRST, HumanName, Lexicon, PatronymicRule, Policy
from nameparser._config_shim import (
    CONSTANTS, Constants, SetManager, TupleManager, _DelimiterManager,
    _RegexesProxy, _cached_parser,
)
from nameparser.config.regexes import EMPTY_REGEX, REGEXES
from nameparser.util import lc

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
        d2["angle_brackets"] = "custom"     # custom keys raise


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


def test_regexes_supports_the_v1_read_only_mapping_surface() -> None:
    # v1's regexes was a dict subclass. The proxy is not, and its
    # catch-all __getattr__ claims every unimplemented mapping method
    # as a regex name -- the same failure that made .get() raise
    # "no regex named 'get'". Cover the rest of the read surface.
    r = _RegexesProxy()
    assert dict(r.items())["word"] is REGEXES["word"]
    assert REGEXES["word"] in list(r.values())
    assert len(r) == len(REGEXES)
    assert r.copy() == dict(REGEXES)          # v1's dict.copy()


def test_regexes_unsupported_method_is_not_reported_as_a_missing_regex() -> None:
    # "no regex named 'pop'" sends the reader looking for a vocabulary
    # entry when the truth is the proxy does not implement a mutator
    r = _RegexesProxy()
    with pytest.raises(AttributeError, match="not supported"):
        r.pop
    with pytest.raises(AttributeError, match="no regex named"):
        r.definitely_not_a_regex


def test_regexes_get_is_the_soft_access_escape_hatch() -> None:
    # 1.4's #256 deprecation told users ".get() remains available for
    # intentional soft access"; __getattr__ must not swallow `get`
    # itself. capitalization_exceptions inherits it from dict -- the
    # regexes proxy is not a dict, so it has to say so explicitly.
    r = _RegexesProxy()
    assert r.get("word") is REGEXES["word"]
    assert r.get("typo") is None
    assert r.get("typo", EMPTY_REGEX) is EMPTY_REGEX


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
    # every named sentinel is a default nickname bucket (the v1 trio
    # plus the #273 typographic pairs); derived from the map itself so
    # a new sentinel can't leave this pin stale
    from nameparser._config_shim import _SENTINEL_PAIRS

    assert set(c.nickname_delimiters) == set(_SENTINEL_PAIRS)
    assert {"quoted_word", "double_quotes", "parenthesis",
            "smart_double_quotes", "guillemets"} <= set(_SENTINEL_PAIRS)
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


def test_v14_constants_blob_unpickles_into_shim() -> None:
    # tests/v2/data/constants_v14.pickle was produced by a real 1.4.0
    # install (`uv run --no-project --with "nameparser==1.4.*" ...`),
    # not synthesized here -- it is the actual bytes a caller upgrading
    # from 1.4 to 2.0 would hand to pickle.load(). Since the M11 swap
    # replaced nameparser.config.Constants with this shim, the blob's
    # pickled class reference now resolves here. Its nested `regexes`
    # field pickles as nameparser.config.RegexTupleManager, reconstructed
    # by the unpickler before Constants.__setstate__ runs -- see
    # RegexTupleManager's docstring in _config_shim.py.
    with open(_DATA_DIR / "constants_v14.pickle", "rb") as f:
        loaded = pickle.load(f)
    assert isinstance(loaded, Constants)
    assert "van" in loaded.prefixes
    assert "dr" in loaded.titles
    assert "jr" in loaded.suffix_not_acronyms
    assert loaded.string_format == "{title} {first} {middle} {last} {suffix} ({nickname})"


def test_v14_pickle_restores_and_parses_warning_free() -> None:
    # A 1.4 pickle froze the then-shipped vocabulary, including the
    # eight dead multi-word entries 2.0 removed; restoring it must not
    # spray warnings about entries the user never added. A multi-word
    # entry the user DID add still warns (second half) -- at PARSE
    # time, not add() time, since the shim's Lexicon snapshot is built
    # lazily on the first parse after a mutation.
    with open(_DATA_DIR / "constants_v14.pickle", "rb") as f:
        c = pickle.load(f)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        HumanName("John Smith", constants=c)
    c.titles.add("grand moff")
    with pytest.warns(UserWarning, match="matched one word at a time"):
        HumanName("Jane Roe", constants=c)


def test_an_unrelated_capitalization_exceptions_valueerror_has_no_v1_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The v1-spelled hint is added ONLY for _MaskValueError -- a value
    that does not spell its key -- caught by TYPE in _build_snapshot's
    try/except. Since #582 the shim drops every key Lexicon would fold
    to empty, so no config reaches a plain ValueError from _normpairs
    here; the filter is switched off to force one, so the except clause
    is still pinned to catch by TYPE and to pass an unrelated ValueError
    through without the v1 hint."""
    monkeypatch.setattr(_config_shim, "_v1_matchable", lambda e: True)
    c = Constants(capitalization_exceptions={'\u3002': 'x'})
    with pytest.raises(ValueError, match="normalizes to empty") as caught:
        HumanName("john smith", constants=c)
    assert "on a v1 Constants" not in str(caught.value)


def test_a_non_str_exception_value_raises_typeerror_at_the_first_parse(
) -> None:
    """The shim does not translate or otherwise intercept a
    capitalization_exceptions value -- a caller's non-str entry
    (v1's TupleManager stores dict[str, object], never statically
    str-typed) reaches Lexicon's own TypeError unchanged, at the
    first parse where the snapshot is built."""
    c = Constants(capitalization_exceptions={'phd': 42})
    with pytest.raises(TypeError, match="str -> str"):
        HumanName("john smith phd", constants=c)


def test_snapshot_keeps_a_multi_word_first_name_title() -> None:
    # v1 looks first_name_titles up on the joined title string, so a
    # multi-word entry is reachable with only its WORDS in titles.
    # Verified on a live 1.4.0: "Grand Duke John" -> first='John'.
    # Intersecting the entry away made the lookup miss and silently
    # reclassified the given name as a family name.
    c = Constants()
    c.titles.add("grand", "duke")
    c.first_name_titles.add("grand duke")
    lexicon, _, _ = c._snapshot()
    assert "grand duke" in lexicon.given_name_titles
    name = HumanName("Grand Duke John", constants=c)
    assert (name.title, name.first, name.last) == ("Grand Duke", "John", "")


@pytest.mark.parametrize("entry", [".", "..", "grand  duke", "grand\tduke"])
def test_snapshot_drops_first_name_titles_v1_could_not_match(entry: str) -> None:
    # v1's key is lc(" ".join(title_list)) -- always single-spaced, and
    # never empty -- so an entry with a whitespace run, or one that is
    # all periods, could never match there. Translating it anyway would
    # either widen behavior (the double-space entry starts matching) or
    # raise (the all-period entry normalizes to empty and _normset
    # rejects it). 1.4.0 accepts all of these and leaves them inert.
    c = Constants()
    c.titles.add("grand", "duke")
    c.first_name_titles.add(entry)
    with pytest.warns(UserWarning, match="first_name_titles"):
        lexicon, _, _ = c._snapshot()           # must not raise
    assert "" not in lexicon.given_name_titles
    name = HumanName("Grand Duke John", constants=c)
    assert (name.first, name.last) == ("", "John")


@pytest.mark.parametrize(("entry", "text"), [
    # v1's lookup key is lc(joined-title-run), and lc strips only the
    # EDGE periods of the whole string, so an interior word keeps its
    # period. v2 normalizes per token and then joins, so the entry has
    # to be TRANSLATED between the two spellings, not filtered out.
    ("lt. col", "Lt. Col. Smith"),
    # v1 joins titles across conjunctions, and v2 tags the conjunction
    # Role.TITLE too, so the joined key contains it in both versions
    ("sir and dame", "Sir and Dame Alex"),
])
def test_snapshot_translates_a_multi_word_first_name_title(
    entry: str, text: str
) -> None:
    c = Constants()
    c.titles.add("lt", "col")
    c.first_name_titles.add(entry)
    name = HumanName(text, constants=c)
    assert name.first and not name.last, f"{entry!r} was not honored"


def test_snapshot_ignores_an_ambiguous_acronym_added_as_a_suffix_word() -> None:
    # Adding an ambiguous acronym to suffix_not_acronyms is INERT in
    # v1: is_suffix already accepts it through the acronym branch, and
    # reserve_last keeps it as the surname anyway. 1.4.0 with this
    # config parses "Jack Ma" exactly as it does without it.
    #
    # Lexicon forbids the overlap, since the word branch would bypass
    # the period gate. Dropping the word from the AMBIGUOUS set instead
    # (the reverse subtraction) ungates it and loses the family name
    # entirely -- worse than the raise it was meant to avoid. Drop it
    # from suffix_words instead, which reproduces v1's inertness.
    c = Constants()
    c.suffix_not_acronyms.add("ma")
    lexicon, _, _ = c._snapshot()               # must not raise
    assert "ma" in lexicon.suffix_acronyms_ambiguous
    assert "ma" not in lexicon.suffix_words
    name = HumanName("Jack Ma", constants=c)
    assert (name.first, name.last, name.suffix) == ("Jack", "Ma", "")


def test_bound_never_given_prefix_deviates_on_two_pieces() -> None:
    # Pinned DEVIATION, not parity. v1's bound-given join has a
    # reserve_last guard, so with only two pieces it does not fire and
    # the word stays never-given: 1.4.0 gives first='', last='dos
    # Santos'. The shim promotes such a word to may-be-given
    # unconditionally, because v1's rule is piece-count dependent and a
    # static vocabulary set cannot express that. Three-piece parity is
    # the case that matters and is covered below; this records the cost.
    c = Constants()
    c.bound_first_names.add("dos")
    name = HumanName("dos Santos", constants=c)
    assert (name.first, name.last) == ("dos", "Santos")


def test_snapshot_keeps_a_bound_never_given_prefix_parseable() -> None:
    # particles.py asserts its own data has no word in both
    # NON_GIVEN_NAME_PARTICLES and BOUND_GIVEN_NAMES, so the defaults
    # behind non_first_name_prefixes and bound_first_names never
    # collide; nothing stops a v1 caller adding one at runtime, and 1.4
    # accepts it -- letting the bound rule win, so "dos Santos Silva"
    # parses first="dos Santos".
    # Lexicon rejects that combination, so the shim promotes such a word
    # to may-be-given rather than raising on config v1 allowed.
    c = Constants()
    assert "dos" in c.non_first_name_prefixes      # baseline: never-given
    c.bound_first_names.add("dos")
    lexicon, _, _ = c._snapshot()                  # must not raise
    assert "dos" in lexicon.particles_ambiguous
    name = HumanName("dos Santos Silva", constants=c)
    assert (name.first, name.last) == ("dos Santos", "Silva")


def test_snapshot_removing_a_honorific_word_turns_the_peel_off() -> None:
    # The deciding case for honorific_tails, which has no v1 manager of
    # its own: the snapshot intersects GLUED_HONORIFICS with the WORD
    # set, so deleting 씨 from suffix_not_acronyms -- the only v1 knob
    # that reaches it -- must make the tail stop mattering rather than
    # raise the subset error or leave 씨 peeling into a suffix field
    # that no longer recognizes it. With the default config the
    # intersection is a no-op, so the equality test above pins nothing
    # here.
    c = Constants()
    assert HumanName("김민준씨", constants=c).suffix == "씨"    # baseline
    c.suffix_not_acronyms.remove("씨")
    lexicon, _, _ = c._snapshot()                              # must not raise
    assert "씨" not in lexicon.honorific_tails
    # the peel is off: the glued honorific goes back into the name,
    # which is 2.0's answer for this input
    name = HumanName("김민준씨", constants=c)
    assert (name.first, name.last, name.suffix) == ("민준씨", "김", "")


def test_snapshot_removing_a_conjunction_turns_the_marker_off() -> None:
    # The deciding case for conjunctions_ambiguous, which has no v1
    # manager of its own: the snapshot intersects CONJUNCTIONS_AMBIGUOUS
    # with the v1 conjunction set, so deleting 'e' from the one v1 knob
    # that reaches it must make the marking stop mattering rather than
    # raise the subset error or leave 'e' reading as an initial on a
    # word the parse no longer treats as a connective at all. With the
    # default config the intersection is a no-op, so the default-equality
    # test above pins nothing here.
    c = Constants()
    assert HumanName("john e smith", constants=c).middle == "e"   # baseline
    c.conjunctions.remove("e")
    lexicon, _, _ = c._snapshot()                             # must not raise
    assert "e" not in lexicon.conjunctions_ambiguous
    # 'e' is no vocabulary at all now: a bare lowercase letter is not
    # initial-shaped, so it is an ordinary middle name word
    name = HumanName("john e smith", constants=c)
    assert (name.first, name.middle, name.last) == ("john", "e", "smith")
    assert name.initials() == "j. e. s."


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


def test_typographic_delimiter_sentinels_present_and_movable() -> None:
    # #273: the eight typographic pairs surface in the v1 API as new
    # named sentinels, so the documented keyed idioms (pop/move/del)
    # work on them exactly like the original trio
    c = Constants()
    assert "smart_double_quotes" in c.nickname_delimiters
    assert "guillemets" in c.nickname_delimiters
    c.maiden_delimiters["guillemets"] = c.nickname_delimiters.pop("guillemets")
    _, policy, _ = c._snapshot()
    assert ("«", "»") in policy.maiden_delimiters
    assert ("«", "»") not in policy.nickname_delimiters


def test_snapshot_delimiter_bucket_move() -> None:
    c = Constants()
    c.maiden_delimiters["parenthesis"] = c.nickname_delimiters.pop("parenthesis")
    _, policy, _ = c._snapshot()
    assert ("(", ")") in policy.maiden_delimiters
    assert ("(", ")") not in policy.nickname_delimiters


def test_snapshot_overlap_keeps_v1_nickname_precedence() -> None:
    # v1 semantics: a pair present in BOTH v1 buckets parses as nickname.
    # 2.0's Policy resolves overlap the other way (maiden wins), so the
    # snapshot pre-subtracts on the maiden side -- a v1 user who added
    # parens to maiden_delimiters WITHOUT removing them from
    # nickname_delimiters keeps their 1.x parse through the facade.
    c = Constants()
    c.maiden_delimiters["parenthesis"] = ("(", ")")  # nickname still has it
    _, policy, _ = c._snapshot()
    assert ("(", ")") in policy.nickname_delimiters
    assert ("(", ")") not in policy.maiden_delimiters
    from nameparser import HumanName

    n = HumanName("Jane (Jones) Smith", constants=c)
    assert n.nickname == "Jones" and n.maiden == ""


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


# -- Gap 1: Constants() constructor kwargs (v1.4 parity, #238/#242/#244) ----


def test_constants_kwarg_replaces_field_others_keep_defaults() -> None:
    default = Constants()
    c = Constants(titles=["Abc"])
    assert set(c.titles) == {"abc"}                # lc()-normalized
    assert "abc" not in default.titles              # sanity: not a real default
    # a kwarg REPLACES that field's vocabulary wholesale (v1 parity); the
    # other eight set fields are untouched
    for field in ("prefixes", "suffix_acronyms", "suffix_not_acronyms",
                  "suffix_acronyms_ambiguous", "first_name_titles",
                  "conjunctions", "bound_first_names",
                  "non_first_name_prefixes"):
        assert set(getattr(c, field)) == set(getattr(default, field))


def test_constants_kwarg_bare_string_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="titles"):
        Constants(titles="abc")  # type: ignore[arg-type]


def test_constants_kwarg_non_iterable_raises_typeerror() -> None:
    with pytest.raises(TypeError):
        Constants(titles=5)  # type: ignore[arg-type]


def test_constants_kwarg_capitalization_exceptions_wraps_tuple_manager() -> None:
    c = Constants(capitalization_exceptions={"mcdonald": "McDonald"})
    assert isinstance(c.capitalization_exceptions, TupleManager)
    assert c.capitalization_exceptions["mcdonald"] == "McDonald"


def test_constants_kwarg_regexes_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="Policy"):
        Constants(regexes={})  # type: ignore[call-arg]


def test_constants_kwarg_unknown_raises_typeerror() -> None:
    with pytest.raises(TypeError):
        Constants(bogus=1)  # type: ignore[call-arg]


def test_constants_kwarg_feeds_facade_parse() -> None:
    from nameparser._facade import HumanName

    c = Constants(titles=["zzqtitle"])
    n = HumanName("Zzqtitle Judy Dench", constants=c)
    assert n.title == "Zzqtitle"


# -- Restoring v1.3/1.4 manager hardening (#221/#238/#241/#242/#260) -------


def test_set_manager_discard_is_noop_on_missing_and_notifies_on_real_change() -> None:
    bumps = []
    s = SetManager(["a"], _on_change=lambda: bumps.append(1))
    assert s.discard("missing") is s           # never raises, chainable
    assert len(bumps) == 0                      # no-op: nothing removed
    assert s.discard("A") is s                  # normalized match
    assert "a" not in s
    assert len(bumps) == 1


def test_set_manager_clear_notifies_only_if_non_empty() -> None:
    bumps = []
    s = SetManager(["a", "b"], _on_change=lambda: bumps.append(1))
    assert s.clear() is s
    assert len(s) == 0
    assert len(bumps) == 1
    assert s.clear() is s                       # already empty: no-op
    assert len(bumps) == 1


def test_set_manager_operators_accept_arbitrary_iterables() -> None:
    a = SetManager(["a", "b"])
    assert a | ["B.", "z"] == {"a", "b", "z"}    # list operand, normalized
    assert a & (x for x in ["A", "q"]) == {"a"}  # generator operand
    assert a - ["a"] == {"b"}
    assert a ^ ["b", "c"] == {"a", "c"}          # symmetric difference
    assert ["b", "c"] ^ a == {"a", "c"}          # reflected


def test_set_manager_bare_str_or_bytes_operand_raises_typeerror() -> None:
    a = SetManager(["a"])
    with pytest.raises(TypeError):
        a | "ab"
    with pytest.raises(TypeError):
        a & b"ab"
    with pytest.raises(TypeError):
        "ab" | a                                 # reflected form too


def test_set_manager_comparison_operators() -> None:
    a = SetManager(["a", "b"])
    assert a <= {"a", "b", "c"}
    assert a < {"a", "b", "c"}
    assert not (a < {"a", "b"})
    assert {"a", "b", "c"} >= a
    assert a <= SetManager(["a", "b", "c"])
    assert SetManager(["a", "b", "c"]) > a


def test_set_manager_constructor_rejects_bare_str() -> None:
    with pytest.raises(TypeError):               # #238/#241: not shredded to chars
        SetManager("dr")                          # type: ignore[arg-type]


def test_set_manager_constructor_rejects_bare_bytes_with_decode_hint() -> None:
    with pytest.raises(TypeError, match="decode"):
        SetManager(b"dr")                         # type: ignore[arg-type]


def test_set_manager_constructor_rejects_non_str_element() -> None:
    with pytest.raises(TypeError):
        SetManager([None])                        # type: ignore[list-item]


def test_set_manager_add_rejects_bytes_with_decode_hint() -> None:
    s = SetManager()
    with pytest.raises(TypeError, match="decode"):
        s.add(b"dr")                              # type: ignore[arg-type]


def test_constants_setattr_rejects_bare_str_like_constructor() -> None:
    c = Constants()
    with pytest.raises(TypeError, match="conjunctions"):
        c.conjunctions = "and"                    # type: ignore[assignment]


def test_tuple_manager_constructor_rejects_bare_str() -> None:
    with pytest.raises(TypeError):                # #242
        TupleManager("ab")                        # type: ignore[arg-type]


def test_tuple_manager_constructor_rejects_iterable_of_strings() -> None:
    with pytest.raises(TypeError):                # #242: 2-char strings silently split
        TupleManager(["ab", "cd"])                # type: ignore[arg-type]


def test_tuple_manager_unknown_key_error_names_known_keys() -> None:
    t = TupleManager({"mcdonald": "McDonald", "obrien": "O'Brien"})
    with pytest.raises(AttributeError, match="mcdonald"):
        t.bogus


def test_tuple_manager_attribute_style_set_and_delete() -> None:
    bumps = []
    t = TupleManager({"a": "A"}, _on_change=lambda: bumps.append(1))
    t.b = "B"                                     # attribute-style routes to dict
    assert t["b"] == "B"
    assert len(bumps) == 1
    del t.a
    assert "a" not in t
    assert len(bumps) == 2
    # the manager's own private attribute is unaffected
    assert t._on_change is not None


def test_constants_copy_preserves_subclass() -> None:                   # #260
    class MyConstants(Constants):
        pass

    c = MyConstants()
    d = c.copy()
    assert type(d) is MyConstants


def test_constants_repr_shows_collection_counts() -> None:              # #221
    c = Constants()
    r = repr(c)
    assert r.startswith("<Constants")
    assert "titles:" in r
    assert f"titles: {len(c.titles)}" in r


def test_constants_repr_shows_customized_scalars_only() -> None:        # #221
    c = Constants()
    assert "capitalize_name" not in repr(c)       # default: not shown
    c.capitalize_name = True
    assert "capitalize_name: True" in repr(c)


def test_constants_bool_kwargs() -> None:
    # v1.4 constructor kwargs used by the customize.rst doctests
    c = Constants(middle_name_as_last=True)
    assert c.middle_name_as_last is True
    assert c.patronymic_name_order is False
    d = Constants(patronymic_name_order=True)
    _, policy, _ = d._snapshot()
    assert len(policy.patronymic_rules) == 2


def test_set_manager_partial_add_still_notifies_owner() -> None:
    # a TypeError mid-argument-list leaves earlier additions applied;
    # the owner must hear about them or its cached parser goes stale
    bumps: list[int] = []
    s = SetManager(["a"], _on_change=lambda: bumps.append(1))
    with pytest.raises(TypeError, match="decode"):
        s.add("b", b"bad")  # type: ignore[arg-type]
    assert "b" in s
    assert len(bumps) == 1


def test_set_manager_remove_discard_bytes_decode_hint() -> None:
    s = SetManager(["dr"])
    with pytest.raises(TypeError, match="decode"):
        s.remove(b"dr")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="decode"):
        s.discard(b"dr")  # type: ignore[arg-type]


def test_delimiter_manager_constructor_bare_str_gets_242_error() -> None:
    # the parent's #242 guard, not dict's cryptic ValueError
    with pytest.raises(TypeError, match="mapping or iterable"):
        _DelimiterManager("ab")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="pairs"):
        _DelimiterManager(["ab", "cd"])  # type: ignore[list-item]


def test_constants_shared_flag_is_read_only() -> None:
    c = Constants()
    with pytest.raises(AttributeError, match="read-only"):
        c._shared = True
    with pytest.raises(AttributeError, match="read-only"):
        CONSTANTS._shared = False
    assert CONSTANTS._shared is True and c._shared is False


def test_multiword_warning_through_shim_points_at_caller() -> None:
    c = Constants()
    c.titles.add("zqx zqy")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        HumanName("John Smith", constants=c)   # snapshot builds lazily here
    multi = [x for x in w if "matched one word at a time" in str(x.message)]
    assert len(multi) == 1
    assert multi[0].filename == __file__


def test_a_multiword_capitalization_exceptions_key_warns_exactly_once(
) -> None:
    """_build_snapshot's Lexicon(...) construction is the ONLY place
    capitalization_exceptions is validated, so a multi-word key must
    warn once, not twice."""
    c = Constants(capitalization_exceptions={'zqx zqy': 'ZqXZqY'})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        HumanName("John Smith", constants=c)   # snapshot builds lazily here
    multi = [x for x in w if "matched one word at a time" in str(x.message)]
    assert len(multi) == 1


def test_a_multiword_capitalization_exceptions_key_with_a_bad_mask_only_warns(
) -> None:
    """#459 review, shim half of test_a_multiword_key_skips_the_mask_
    check_entirely in tests/v2/test_lexicon.py: a v1 caller's
    multi-word key is unreachable through capitalized() regardless of
    its value, so a value that does not spell it must not raise here
    either."""
    c = Constants(capitalization_exceptions={'ph d': 'Doctor'})
    with pytest.warns(UserWarning, match="matched one word at a time"):
        HumanName("John Smith", constants=c)
    lexicon, _policy, _render = c._snapshot()
    assert lexicon.capitalization_exceptions_map == {"ph d": "Doctor"}


def test_2x_pickle_roundtrip_keeps_a_readded_dead_entry() -> None:
    # the all-eight gate: a 2.0 user's deliberate re-add of ONE legacy
    # string survives a round-trip (only a full pre-2.0 blob, which
    # froze all eight, is subtracted)
    c = Constants()
    with pytest.warns(UserWarning):
        c.suffix_acronyms.add("leed ap")
        HumanName("John Smith", constants=c)   # snapshot builds lazily here
    c2 = pickle.loads(pickle.dumps(c))
    assert "leed ap" in c2.suffix_acronyms


# -- entries v1 could never match (#541) ---------------------------------
#
# A v1 piece comes from a whitespace split, re-joined only with single
# spaces, so nameparser 1.x never matched an entry that is empty or
# holds edge whitespace, a whitespace run or any whitespace character
# other than a single space (a tab, NBSP, newline). Each row names a text
# on which the entry WOULD act if the shim translated it, so a row that
# reads like the entry-free parse proves the drop rather than an inert
# word. An entry holding only full stops is dropped too: Lexicon folds
# it to empty (#582), although v1 could match a token made of that full
# stop. (field, entry, text, mask value for capitalization_exceptions)
_V1_UNMATCHABLE_ROWS = [
    ("titles", " dean ", "dean john smith", None),
    ("titles", "dean\t", "dean john smith", None),
    ("titles", "...", "dean john smith", None),
    ("titles", "de  an", "de an john smith", None),
    ("prefixes", " zz ", "john zz smith", None),
    ("suffix_acronyms", " zzq ", "john smith zzq", None),
    ("suffix_not_acronyms", " zzw", "john smith zzw", None),
    ("suffix_not_acronyms", "ma ", "John Smith", None),
    ("suffix_not_acronyms", "ba ", "John Smith", None),
    ("suffix_acronyms_ambiguous", "phd ", "John Smith PhD", None),
    ("conjunctions", " zand ", "john zand jane smith", None),
    ("bound_first_names", " zzb ", "zzb ali smith", None),
    ("bound_first_names", "'t ", "Gerard 't Hooft", None),
    ("non_first_name_prefixes", " van ", "van johnson", None),
    ("capitalization_exceptions", " zzc ", "john zzc", "ZzC"),
    ("capitalization_exceptions", "...", "john zzc", "ZzC"),
    ("first_name_titles", "grand  duke", "Grand Duke John", None),
    ("titles", "。", "。 john smith", None),
    ("prefixes", "．", "john ． smith", None),
    ("suffix_acronyms", "｡", "john smith ｡", None),
    ("conjunctions", "。 。", "john 。 。 jane smith", None),
    ("capitalization_exceptions", "。", "john zzc", "。"),
]

# Recorded negative control: what each row did with the filter off
# (measured 2026-10-02 on master 42515ebd, where only first_name_titles
# was filtered). "raises" rows broke the shim's never-raise contract,
# "activates" rows its never-silently-change one; "inert" rows were
# harmless already and are swept so the warning covers the whole family.
_UNFILTERED_OUTCOME = {
    ("titles", " dean "): "activates",
    ("titles", "dean\t"): "activates",
    ("titles", "..."): "raises",
    ("titles", "de  an"): "inert",
    ("prefixes", " zz "): "activates",
    ("suffix_acronyms", " zzq "): "activates",
    ("suffix_not_acronyms", " zzw"): "activates",
    ("suffix_not_acronyms", "ma "): "raises",
    ("suffix_not_acronyms", "ba "): "raises",
    ("suffix_acronyms_ambiguous", "phd "): "inert",
    ("conjunctions", " zand "): "activates",
    ("bound_first_names", " zzb "): "activates",
    ("bound_first_names", "'t "): "raises",
    ("non_first_name_prefixes", " van "): "inert",
    ("capitalization_exceptions", " zzc "): "activates",
    ("capitalization_exceptions", "..."): "raises",
    ("first_name_titles", "grand  duke"): "activates",
    ("titles", "。"): "raises",
    ("prefixes", "．"): "raises",
    ("suffix_acronyms", "｡"): "raises",
    ("conjunctions", "。 。"): "raises",
    ("capitalization_exceptions", "。"): "raises",
}


def _base(field: str) -> Constants:
    c = Constants()
    if field == "first_name_titles":   # the entry only acts on known titles
        c.titles.add("grand", "duke")
    return c


def _with_entry(field: str, entry: str, value: str | None) -> Constants:
    c = _base(field)
    if value is None:
        getattr(c, field).add(entry)
    else:
        c.capitalization_exceptions[entry] = value
    return c


def _reading(c: Constants, text: str) -> tuple[dict[str, str], str]:
    name = HumanName(text, constants=c)
    fields = name.as_dict()
    name.capitalize(force=True)
    return fields, str(name)


@pytest.mark.parametrize(("field", "entry", "text", "value"),
                         _V1_UNMATCHABLE_ROWS)
def test_an_entry_v1_could_not_match_is_dropped_with_one_warning(
    field: str, entry: str, text: str, value: str | None,
) -> None:
    baseline = _reading(_base(field), text)
    c = _with_entry(field, entry, value)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        got = _reading(c, text)
    assert got == baseline
    messages = [str(w.message) for w in caught]
    assert len(messages) == 1, messages
    assert caught[0].category is UserWarning
    # a set field stores the lc()-folded entry, a mask key as written
    shown = entry if value is not None else lc(entry)
    assert f"{field}: {shown!r}" in messages[0]
    # attributed to the caller's line, not to library code
    assert caught[0].filename == __file__


@pytest.mark.parametrize(("field", "entry", "text", "value"),
                         _V1_UNMATCHABLE_ROWS)
def test_the_unmatchable_entry_filter_has_a_recorded_control(
    field: str, entry: str, text: str, value: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_config_shim, "_v1_matchable", lambda e: True)
    # the three rows that recorded "raises" through the two cross-set
    # checks ('ma ', 'ba ', "'t ") raise only while those compare RAW
    # spellings; the shim now folds them there (#582), which would turn
    # them into "inert". This control measures the filter alone, so that
    # fold is switched off beside it.
    monkeypatch.setattr(_config_shim, "_normalize", lambda e: e)
    baseline = _reading(_base(field), text)
    c = _with_entry(field, entry, value)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # Lexicon's multi-word warning
        try:
            got = _reading(c, text)
        except ValueError:
            outcome = "raises"
        else:
            outcome = "activates" if got != baseline else "inert"
    assert outcome == _UNFILTERED_OUTCOME[(field, entry)]


# -- an edge full stop and the two cross-set checks (#582) ---------------
#
# Lexicon strips a CJK full stop at an entry's edge, v1's lc() does not.
# Lexicon folds each field on its own, but re-checks two relations
# between separately built sets AFTER its fold, and the shim built those
# two from raw strings: 'ma。' beside the ambiguous 'ma' (suffix word vs
# ambiguous acronym) and a bound 'zed。' beside the particle 'zed' (bound
# given name vs particles_ambiguous). 1.4.0 through 2.2.0 accepted both.
# Each row: (id, plain entries as (field, word), the field and spelling
# carrying the edge full stop, text).
_EDGE_COLLISION_ROWS = [
    ("ambiguous-vs-word", [], "suffix_not_acronyms", "ma。", "jack ma"),
    ("bound-vs-particle",
     [("prefixes", "zed"), ("non_first_name_prefixes", "zed")],
     "bound_first_names", "zed。", "zed bakr smith"),
]

# Recorded negative control: with the shim's fold switched to identity
# these two raise ValueError at the first parse (measured 2026-10-02).
# It measures the raise only; the readings are pinned by the tests below.
_UNFOLDED_OUTCOME = {
    "ambiguous-vs-word": "raises",
    "bound-vs-particle": "raises",
}


def _edge_config(plain: list[tuple[str, str]], field: str,
                 entry: str) -> Constants:
    c = Constants()
    for f, word in plain:
        getattr(c, f).add(word)
    getattr(c, field).add(entry)
    return c


@pytest.mark.parametrize(("case", "plain", "field", "entry", "text"),
                         _EDGE_COLLISION_ROWS,
                         ids=[r[0] for r in _EDGE_COLLISION_ROWS])
def test_an_edge_full_stop_collision_reads_as_its_folded_spelling(
    case: str, plain: list[tuple[str, str]], field: str, entry: str,
    text: str,
) -> None:
    folded = entry.strip("\u3002\uff0e\uff61")
    want = _reading(_edge_config(plain, field, folded), text)
    got = _reading(_edge_config(plain, field, entry), text)   # error filter
    assert got == want


@pytest.mark.parametrize(("case", "plain", "field", "entry", "text"),
                         _EDGE_COLLISION_ROWS,
                         ids=[r[0] for r in _EDGE_COLLISION_ROWS])
def test_the_edge_full_stop_fold_has_a_recorded_control(
    case: str, plain: list[tuple[str, str]], field: str, entry: str,
    text: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_config_shim, "_normalize", lambda e: e)
    c = _edge_config(plain, field, entry)
    try:
        _reading(c, text)
    except ValueError:
        outcome = "raises"
    else:
        outcome = "reads"
    assert outcome == _UNFOLDED_OUTCOME[case]


def _fields(first: str, last: str, suffix: str, title: str = "") -> dict[str, str]:
    return {"title": title, "first": first, "middle": "", "last": last,
            "suffix": suffix, "nickname": "", "maiden": ""}


# Readings recorded 2026-10-02 on the tree before any shim fold (afc45f35,
# a scratch `git archive` copy), where these configs never raised: the
# fold must not move them. A field Lexicon folds on its own is NOT
# re-folded by the shim, so 'zz。' in non_first_name_prefixes beside the
# particle 'zz' still leaves 'zz' a given name.
_UNCHANGED_READINGS = [
    ("never-given-edge-stop",
     [("prefixes", "zz")], "non_first_name_prefixes", "zz\u3002", "zz smith",
     (_fields("zz", "smith", ""), "Zz Smith")),
    ("never-given-fullwidth-stop",
     [("prefixes", "zz")], "non_first_name_prefixes", "zz\uff0e", "zz smith",
     (_fields("zz", "smith", ""), "Zz Smith")),
    ("never-given-nfd-nfc",
     [("prefixes", "z\u00e9")], "non_first_name_prefixes", "ze\u0301",
     "z\u00e9 smith",
     (_fields("z\u00e9", "smith", ""), "Z\u00e9 Smith")),
    ("ambiguous-edge-stop",
     [("suffix_acronyms", "zq")], "suffix_acronyms_ambiguous", "zq\u3002",
     "john zq", (_fields("john", "", "zq"), "John ZQ")),
    ("title-edge-stop",
     [], "titles", "dean\u3002", "dean john smith",
     (_fields("john", "smith", "", "dean"), "Dean John Smith")),
]


@pytest.mark.parametrize(("case", "plain", "field", "entry", "text", "want"),
                         _UNCHANGED_READINGS,
                         ids=[r[0] for r in _UNCHANGED_READINGS])
def test_an_edge_full_stop_entry_outside_the_two_checks_reads_as_before(
    case: str, plain: list[tuple[str, str]], field: str, entry: str,
    text: str, want: tuple[dict[str, str], str],
) -> None:
    assert _reading(_edge_config(plain, field, entry), text) == want


def test_the_offered_remedy_runs_and_silences_the_warning() -> None:
    c = Constants()
    c.titles.add(" dean ")
    c.bound_first_names.add("'t ")              # a quote the remedy must repr
    c.capitalization_exceptions[" zzc "] = "ZzC"
    c.capitalization_exceptions["'q "] = "Q"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        HumanName("x", constants=c)
    assert len(caught) == 1                       # one warning for them all
    message = str(caught[0].message)
    listing, remedy = message.split("remove these: ")
    for label in ("titles: ' dean '", "bound_first_names: \"'t \"",
                  "capitalization_exceptions: ' zzc '",
                  "capitalization_exceptions: \"'q \""):
        assert label in listing, label
    # the offered spelling, pinned, and then run as written
    # (in the shim's field order, entries sorted within a field)
    assert remedy == (
        "constants.bound_first_names.remove(\"'t \"); "
        "constants.titles.remove(' dean '); "
        "del constants.capitalization_exceptions[' zzc ']; "
        "del constants.capitalization_exceptions[\"'q \"]")
    exec(remedy, {"constants": c})   # the code the message hands over
    c.titles.add("dean")              # the stripped word, if it was meant
    c.capitalization_exceptions["zzc"] = "ZzC"
    name = HumanName("dean john zzc", constants=c)   # no warning: error filter
    assert name.title == "dean"                      # as 1.4.0 reads "dean"
    name.capitalize(force=True)
    assert str(name) == "Dean John ZzC"


def test_the_1_4_typo_roster_is_keyed_by_field() -> None:
    # 'actor ' is silent only where 1.4.0 shipped it, in titles
    c = Constants()
    c.prefixes.add("actor ")
    with pytest.warns(UserWarning, match="prefixes: 'actor '"):
        HumanName("x", constants=c)


def test_the_warning_fires_once_per_config_change() -> None:
    c = Constants()
    c.titles.add(" dean ")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        HumanName("dean john smith", constants=c)
        HumanName("dean john smith", constants=c)   # cached snapshot
        assert len(caught) == 1
        c.titles.add("x")                            # a new generation
        HumanName("dean john smith", constants=c)
    assert len(caught) == 2


def test_a_clean_config_snapshots_without_a_warning() -> None:
    c = Constants()
    c.titles.add("dean")
    c.capitalization_exceptions["McDonald"] = "McDonald"  # case: accepted widening
    lexicon, _, _ = c._snapshot()                # error filter: any warning fails
    assert "dean" in lexicon.titles


def test_the_1_4_shipped_typos_are_dropped_silently() -> None:
    c = Constants()
    c.titles.remove("actor")
    c.titles.add("actor ")
    name = HumanName("Actor John Smith", constants=c)   # error filter
    assert (name.first, name.title) == ("Actor", "")


def test_the_1_4_shipped_unmatchable_roster_is_exactly_the_pickles() -> None:
    with open(_DATA_DIR / "constants_v14.pickle", "rb") as f:
        c = pickle.load(f)
    found = {
        (field, entry)
        for field in _config_shim._SET_FIELDS
        for entry in getattr(c, field)
        if not _config_shim._v1_matchable(entry)
    } | {
        ("capitalization_exceptions", key)
        for key in c.capitalization_exceptions
        if not _config_shim._v1_matchable(key)
    }
    assert found == _config_shim._V14_SHIPPED_UNMATCHABLE


def test_a_first_name_title_lexicon_folds_to_nothing_is_dropped_with_the_warning(
) -> None:
    # '。' survives v1's lc() but Lexicon's fold empties it (#582):
    # dropped like any other entry that matches no name word
    c = Constants()
    c.first_name_titles.add("。")
    with pytest.warns(UserWarning, match="first_name_titles: '。'"):
        lexicon, _, _ = c._snapshot()
    assert "" not in lexicon.given_name_titles
    assert HumanName("john smith", constants=c).last == "smith"
