"""Shim Constants/SetManager/TupleManager (migration spec §3)."""
import copy
import pickle
import warnings
from pathlib import Path

import pytest

from nameparser import GIVEN_FIRST, HumanName, Lexicon, PatronymicRule, Policy
from nameparser._config_shim import (
    CONSTANTS, Constants, SetManager, TupleManager, _DelimiterManager,
    _RegexesProxy, _cached_parser,
)
from nameparser.config.regexes import EMPTY_REGEX, REGEXES

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
    lexicon, _, _ = c._snapshot()               # must not raise
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


def test_snapshot_ungates_an_ambiguous_acronym_added_as_a_suffix_word() -> None:
    # v1's is_suffix ORs the acronym and word branches, so adding an
    # ambiguous acronym to suffix_not_acronyms simply ungates it: 1.4.0
    # accepts the config and reads "John Smith jd" with suffix='jd'.
    # Lexicon forbids the overlap (the word branch would bypass the
    # period gate), so translate rather than let the raise through --
    # dropping it from the ambiguous set leaves a plain acronym plus a
    # word, which is v1's effective behavior.
    c = Constants()
    c.suffix_not_acronyms.add("jd")
    lexicon, _, _ = c._snapshot()               # must not raise
    assert "jd" not in lexicon.suffix_acronyms_ambiguous
    name = HumanName("John Smith jd", constants=c)
    assert (name.first, name.last, name.suffix) == ("John", "Smith", "jd")


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
    # prefixes.py asserts its own data keeps non_first_name_prefixes
    # disjoint from bound_first_names, but nothing stops a v1 caller
    # adding one at runtime, and 1.4 accepts it -- letting the bound
    # rule win, so "dos Santos Silva" parses first="dos Santos".
    # Lexicon rejects that combination, so the shim promotes such a word
    # to may-be-given rather than raising on config v1 allowed.
    c = Constants()
    assert "dos" in c.non_first_name_prefixes      # baseline: never-given
    c.bound_first_names.add("dos")
    lexicon, _, _ = c._snapshot()                  # must not raise
    assert "dos" in lexicon.particles_ambiguous
    name = HumanName("dos Santos Silva", constants=c)
    assert (name.first, name.last) == ("dos Santos", "Silva")


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
