import dataclasses
from collections.abc import Iterator

import pytest

from nameparser._policy import (
    DEFAULT_SCRIPT_ORDERS, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST, PatronymicRule, Policy, PolicyPatch, Script, UNSET,
    apply_patch,
)
from nameparser._types import Role


def test_order_constants_read_as_their_contents() -> None:
    assert GIVEN_FIRST == (Role.GIVEN, Role.MIDDLE, Role.FAMILY)
    assert FAMILY_FIRST == (Role.FAMILY, Role.GIVEN, Role.MIDDLE)
    assert FAMILY_FIRST_GIVEN_LAST == (Role.FAMILY, Role.MIDDLE, Role.GIVEN)


def test_policy_defaults() -> None:
    p = Policy()
    assert p.name_order == GIVEN_FIRST
    assert p.patronymic_rules == frozenset()
    assert ("(", ")") in p.nickname_delimiters
    assert p.maiden_delimiters == frozenset()
    assert p.strip_emoji and p.strip_bidi and p.lenient_comma_suffixes


def test_policy_is_hashable_and_replaceable() -> None:
    p = dataclasses.replace(Policy(), name_order=FAMILY_FIRST)
    assert p.name_order == FAMILY_FIRST
    assert isinstance(hash(p), int)


def test_name_order_must_be_permutation_and_error_names_constants() -> None:
    with pytest.raises(ValueError, match="FAMILY_FIRST_GIVEN_LAST"):
        Policy(name_order=(Role.TITLE, Role.GIVEN, Role.FAMILY))
    with pytest.raises(ValueError, match="GIVEN_FIRST"):
        Policy(name_order=(Role.GIVEN, Role.GIVEN, Role.FAMILY))


def test_name_order_restricted_to_the_three_exported_orders() -> None:
    # _name_positions only implements the three exported semantics; the
    # unnamed permutations would silently misassign (PR review I7).
    # Pre-2.0 strictness is free: relaxing later is compatible.
    with pytest.raises(ValueError, match="GIVEN_FIRST"):
        Policy(name_order=(Role.MIDDLE, Role.GIVEN, Role.FAMILY))


def test_name_order_rejects_non_role_elements_with_type_error() -> None:
    # taxonomy: wrong element type -> TypeError, not the permutation
    # ValueError (PR review polish)
    with pytest.raises(TypeError, match="Role"):
        Policy(name_order=(1, 2, 3))  # type: ignore[arg-type]


def test_name_order_rejects_plain_string_tuples() -> None:
    # Role is a StrEnum, so ("given", ...) == GIVEN_FIRST -- the
    # isinstance loop is the only guard rejecting string elements.
    with pytest.raises(TypeError, match="must be Role members"):
        Policy(name_order=("given", "middle", "family"))  # type: ignore[arg-type]


def test_script_values_are_the_public_names() -> None:
    assert Script.HAN == "han" and Script.HANGUL == "hangul"
    assert Script.HIRAGANA == "hiragana" and Script.KATAKANA == "katakana"


def test_patronymic_rules_coerce_and_reject() -> None:
    p = Policy(patronymic_rules=frozenset({"east-slavic"}))  # type: ignore[arg-type]
    assert p.patronymic_rules == frozenset({PatronymicRule.EAST_SLAVIC})
    with pytest.raises(ValueError, match="east-slavic, turkic"):
        Policy(patronymic_rules=frozenset({"klingon"}))  # type: ignore[arg-type]


def test_delimiter_pairs_must_be_nonempty_string_pairs() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Policy(nickname_delimiters=frozenset({("", ")")}))


def test_delimiter_pair_rejects_two_char_string() -> None:
    with pytest.raises(TypeError, match="tuples"):
        Policy(nickname_delimiters=frozenset({"()"}))  # type: ignore[arg-type]


def test_patronymic_rules_rejects_bare_string_and_non_iterable() -> None:
    with pytest.raises(TypeError, match="bare string"):
        Policy(patronymic_rules="east-slavic")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="iterable"):
        Policy(patronymic_rules=5)  # type: ignore[arg-type]


def test_patronymic_rules_true_points_at_the_v1_migration() -> None:
    # v1's patronymic_name_order was a BOOL flag, so True is the single
    # likeliest wrong value a migrator passes here -- the message must
    # name the v1 flag and the working replacements, not just say
    # "not iterable". Same guard on the PolicyPatch path (packs).
    with pytest.raises(TypeError, match="patronymic_name_order"):
        Policy(patronymic_rules=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="patronymic_name_order"):
        PolicyPatch(patronymic_rules=True)  # type: ignore[arg-type]
    # non-patronymic union fields get the generic curated message
    with pytest.raises(TypeError, match="extra_suffix_delimiters"):
        PolicyPatch(extra_suffix_delimiters=True)  # type: ignore[arg-type]


def test_maiden_delimiters_win_over_nickname_defaults() -> None:
    # A pair routes to exactly one field, and listing it in
    # maiden_delimiters is the specific intent -- so the one-liner works
    # without knowing (or rebuilding) the nickname default set. The
    # review that prompted this: routing parens to maiden used to
    # require both buckets edited in tandem.
    p = Policy(maiden_delimiters=frozenset({("(", ")")}))
    assert ("(", ")") in p.maiden_delimiters
    assert ("(", ")") not in p.nickname_delimiters
    # canonicalization: the explicit-removal spelling (the documented
    # set-math idiom) converges to the same value (equal AND same hash
    # -- cache keys agree)
    from nameparser import DEFAULT_NICKNAME_DELIMITERS

    explicit = Policy(
        nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS - {("(", ")")},
        maiden_delimiters=frozenset({("(", ")")}),
    )
    assert p == explicit and hash(p) == hash(explicit)


def test_maiden_wins_applies_to_typographic_pairs_too() -> None:
    # the subtraction is pair-agnostic; pin one #273 pair end-to-end
    from nameparser import Parser

    p = Policy(maiden_delimiters=frozenset({("«", "»")}))
    assert ("«", "»") not in p.nickname_delimiters
    n = Parser(policy=p).parse("Jean «Dupont» Martin")
    assert n.maiden == "Dupont" and n.nickname == ""


def test_maiden_precedence_applies_through_policy_patch() -> None:
    # apply_patch re-runs Policy's constructor, so a patch (e.g. from a
    # locale pack) adding a maiden pair gets the same subtraction
    patched = apply_patch(
        Policy(), PolicyPatch(maiden_delimiters=frozenset({("(", ")")})))
    assert ("(", ")") in patched.maiden_delimiters
    assert ("(", ")") not in patched.nickname_delimiters


def test_default_nickname_delimiters_constant_is_the_default() -> None:
    from nameparser import DEFAULT_NICKNAME_DELIMITERS

    assert Policy().nickname_delimiters == DEFAULT_NICKNAME_DELIMITERS
    # the documented set-math idiom stays valid input
    p = Policy(nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS | {("«", "»")})
    assert ("«", "»") in p.nickname_delimiters


def test_policy_delimiters_coerce_to_frozensets() -> None:
    p = Policy(nickname_delimiters=[("(", ")")])  # type: ignore[arg-type]
    assert isinstance(p.nickname_delimiters, frozenset)
    assert isinstance(hash(p), int)
    assert p == Policy(nickname_delimiters=frozenset({("(", ")")}))


def test_policy_delimiters_do_not_alias_caller_containers() -> None:
    source = {("(", ")")}
    p = Policy(nickname_delimiters=source)  # type: ignore[arg-type]
    source.add(("'", "'"))
    assert ("'", "'") not in p.nickname_delimiters


def test_extra_suffix_delimiters_validated_and_coerced() -> None:
    with pytest.raises(TypeError, match="bare string"):
        Policy(extra_suffix_delimiters="ab")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be strings"):
        Policy(extra_suffix_delimiters=frozenset({5}))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty strings"):
        Policy(extra_suffix_delimiters=frozenset({""}))
    p = Policy(extra_suffix_delimiters=["-"])  # type: ignore[arg-type]
    assert p.extra_suffix_delimiters == frozenset({"-"})
    assert isinstance(hash(p), int)


def test_non_iterable_fields_name_the_offending_field() -> None:
    # Non-iterables (an int, a bool) used to fall through to tuple()/
    # frozenset() and surface as a bare "'int' object is not iterable",
    # with no hint which field was wrong -- unlike patronymic_rules,
    # which has always named itself. Every iterable-typed Policy field
    # gets the same treatment.
    with pytest.raises(TypeError, match="name_order"):
        Policy(name_order=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="nickname_delimiters"):
        Policy(nickname_delimiters=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="maiden_delimiters"):
        Policy(maiden_delimiters=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="extra_suffix_delimiters"):
        Policy(extra_suffix_delimiters=5)  # type: ignore[arg-type]


def test_policy_patch_mirrors_policy_field_names() -> None:
    policy_fields = {f.name for f in dataclasses.fields(Policy)}
    patch_fields = {f.name for f in dataclasses.fields(PolicyPatch)}
    assert policy_fields == patch_fields


def test_policy_patch_mirrors_policy_field_types() -> None:
    for f in dataclasses.fields(Policy):
        patch_annotation = PolicyPatch.__dataclass_fields__[f.name].type
        assert patch_annotation == f"{f.type} | _Unset"


def test_policy_patch_canonicalizes_union_fields() -> None:
    p = PolicyPatch(extra_suffix_delimiters=frozenset({"-"}))
    assert isinstance(p.extra_suffix_delimiters, frozenset)
    assert isinstance(hash(p), int)
    out = apply_patch(Policy(), PolicyPatch(extra_suffix_delimiters=["-"]))  # type: ignore[arg-type]
    assert out.extra_suffix_delimiters == frozenset({"-"})


def test_policy_patch_rejects_bare_string_union_fields() -> None:
    with pytest.raises(TypeError, match="bare string"):
        PolicyPatch(extra_suffix_delimiters="ab")  # type: ignore[arg-type]


def test_apply_patch_overrides_scalars_and_unions_sets() -> None:
    base = Policy(patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC}))
    patch = PolicyPatch(
        name_order=FAMILY_FIRST,
        patronymic_rules=frozenset({PatronymicRule.TURKIC}),
    )
    out = apply_patch(base, patch)
    assert out.name_order == FAMILY_FIRST                      # override
    assert out.patronymic_rules == frozenset(                   # union
        {PatronymicRule.EAST_SLAVIC, PatronymicRule.TURKIC})
    assert out.strip_emoji is True                              # untouched


def test_apply_patch_with_empty_patch_returns_same_policy() -> None:
    base = Policy()
    assert apply_patch(base, PolicyPatch()) is base


def test_unset_fields_are_distinguishable_from_defaults() -> None:
    patch = PolicyPatch(strip_emoji=True)  # explicitly set to the default value
    assert patch.strip_emoji is True
    assert PolicyPatch().strip_emoji is UNSET


def test_policy_rejects_non_bool_flags() -> None:
    # "no" and "false" are truthy: storing them would silently invert
    # the caller's intent downstream.
    for flag in ("middle_as_family", "lenient_comma_suffixes",
                 "strip_emoji", "strip_bidi"):
        with pytest.raises(TypeError, match="must be a bool"):
            Policy(**{flag: "no"})  # type: ignore[arg-type]


def test_patronymic_rules_generator_errors_propagate_untouched() -> None:
    # A ValueError raised inside the caller's own generator must not be
    # rewritten as "unknown patronymic rule" with the traceback erased.
    def bad_loader():  # noqa: ANN202
        yield "east-slavic"
        raise ValueError("config line 7: bad int")

    with pytest.raises(ValueError, match="config line 7"):
        Policy(patronymic_rules=bad_loader())  # type: ignore[arg-type]


def test_unknown_patronymic_rule_error_names_the_offender() -> None:
    with pytest.raises(ValueError, match="klingon"):
        Policy(patronymic_rules=iter(["east-slavic", "klingon"]))  # type: ignore[arg-type]


def test_policy_patch_canonicalizes_scalar_name_order() -> None:
    # A list name_order stored as-is made the patch -- and any Locale
    # holding it -- unhashable, failing far from the construction site.
    p = PolicyPatch(name_order=[Role.FAMILY, Role.GIVEN, Role.MIDDLE])  # type: ignore[arg-type]
    assert p.name_order == (Role.FAMILY, Role.GIVEN, Role.MIDDLE)
    assert isinstance(hash(p), int)


def test_policy_patch_canonicalizes_script_orders_all_the_way_down() -> None:
    # Same failure as name_order above, one level deeper: tuple-izing
    # only the (Script, order) pair left the ORDER a list, so the patch
    # -- and any Locale holding it -- was still unhashable.
    p = PolicyPatch(script_orders={Script.HAN: [Role.FAMILY, Role.GIVEN,  # type: ignore[arg-type]
                                                Role.MIDDLE]})
    assert p.script_orders == ((Script.HAN, FAMILY_FIRST),)
    assert isinstance(hash(p), int)


def test_apply_patch_overrides_script_orders_as_a_scalar() -> None:
    # script_orders composes as a SCALAR: a patch REPLACES the table
    # rather than merging into it, so an empty one is how a pack turns
    # the default off. An UNSET patch must leave the default alone --
    # the distinction a union field would blur.
    cleared = apply_patch(Policy(), PolicyPatch(script_orders={}))  # type: ignore[arg-type]
    assert cleared.script_orders == ()
    untouched = apply_patch(Policy(), PolicyPatch())
    assert untouched.script_orders == DEFAULT_SCRIPT_ORDERS
    replaced = apply_patch(
        Policy(), PolicyPatch(script_orders={Script.HANGUL: GIVEN_FIRST}))  # type: ignore[arg-type]
    assert replaced.script_orders == ((Script.HANGUL, GIVEN_FIRST),)


def test_apply_patch_revalidates_deferred_script_orders() -> None:
    # The value half defers exactly like name_order's, and the error
    # must name script_orders -- not name_order, whose message the
    # check is shared with.
    bad = PolicyPatch(script_orders={Script.HAN: (Role.MIDDLE, Role.GIVEN,  # type: ignore[arg-type]
                                                  Role.FAMILY)})
    with pytest.raises(ValueError, match="script_orders must be one of"):
        apply_patch(Policy(), bad)


def test_policy_patch_defers_malformed_script_orders_verbatim() -> None:
    # The canonicalization must not eat the evidence: a bare string
    # would shred to character tuples (its elements are themselves
    # tuple-izable, so nothing raises to stop it) and bytes to ints,
    # leaving Policy's curated messages nothing of the caller's to
    # quote. Both shapes must survive the patch and raise at APPLY.
    with pytest.raises(TypeError, match="bare string"):
        apply_patch(Policy(), PolicyPatch(script_orders="han"))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="decode first"):
        apply_patch(Policy(), PolicyPatch(script_orders=b"han"))  # type: ignore[arg-type]


def test_apply_patch_revalidates_deferred_values() -> None:
    # PolicyPatch documents lazy validation: invalid values sit latent in
    # the patch and must fail when applied, not silently flow into Policy.
    bad_order = PolicyPatch(name_order=(Role.TITLE, Role.GIVEN, Role.FAMILY))
    with pytest.raises(ValueError, match="exported orders"):
        apply_patch(Policy(), bad_order)
    bad_rules = PolicyPatch(patronymic_rules=frozenset({"klingon"}))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="valid rules"):
        apply_patch(Policy(), bad_rules)


def test_all_set_valued_patch_fields_declare_union_composition() -> None:
    # apply_patch is driven by this metadata; dropping it from one field
    # would silently flip locale layering from union to override.
    union_fields = {
        f.name for f in dataclasses.fields(PolicyPatch)
        if f.metadata.get("compose") == "union"
    }
    assert union_fields == {
        "patronymic_rules", "nickname_delimiters",
        "maiden_delimiters", "extra_suffix_delimiters", "segment_scripts",
    }


def test_policy_and_patch_pickle_round_trip_preserves_unset_identity() -> None:
    import pickle

    p = Policy(patronymic_rules=frozenset({PatronymicRule.TURKIC}))
    assert pickle.loads(pickle.dumps(p)) == p
    patch = PolicyPatch(strip_emoji=False)
    loaded = pickle.loads(pickle.dumps(patch))
    assert loaded == patch
    # apply_patch gates on 'value is UNSET'; an unpickled patch is only
    # correct because Enum members round-trip BY IDENTITY. A plain
    # object() sentinel would break this silently.
    assert loaded.name_order is UNSET
    assert loaded.strip_emoji is False


def test_setstate_rejects_layout_skew() -> None:
    state = dict(Policy().__getstate__())
    del state["name_order"]
    with pytest.raises(ValueError, match="name_order"):
        Policy.__new__(Policy).__setstate__(state)


def test_name_order_rejects_bare_string() -> None:
    # tuple("gmf") is ("g","m","f"): without the guard a bare string
    # fell through to the permutation ValueError instead of the
    # taxonomy's bare-string TypeError every other iterable field raises
    with pytest.raises(TypeError, match="bare string"):
        Policy(name_order="gmf")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="bare string"):
        PolicyPatch(name_order="gmf")  # type: ignore[arg-type]


# Policy's collection fields had no guard against the two shapes
# Lexicon._normset rejects by name: a bare string (iterates into
# characters) and a Mapping (contributes only its keys). Both were
# accepted silently, storing a value the caller never wrote -- the
# expensive failure this library guards against elsewhere.
#
# Parametrized over BOTH classes on purpose. PolicyPatch had its own
# inline copy of the bare-string half and never grew the mapping half,
# so the two silently diverged; a patch is also what a Locale pack
# ships, and its frozenset() coercion destroys the evidence before
# Policy could catch it at apply time.
_GUARDED = ["nickname_delimiters", "maiden_delimiters",
            "extra_suffix_delimiters", "patronymic_rules", "segment_scripts"]


@pytest.mark.parametrize("cls", [Policy, PolicyPatch])
@pytest.mark.parametrize("field", _GUARDED)
@pytest.mark.parametrize("value", [{"dr": "Dr"}, {}])
def test_collection_fields_reject_a_mapping(
        cls: type, field: str, value: dict) -> None:
    # {} is the sharp one: it is Python's empty-set trap, so a caller
    # disabling delimiters writes it and silently gets what they meant
    # -- until the day they write a non-empty one.
    with pytest.raises(TypeError, match="mapping"):
        cls(**{field: value})

@pytest.mark.parametrize("cls", [Policy, PolicyPatch])
@pytest.mark.parametrize("field", _GUARDED)
@pytest.mark.parametrize("value", ["", "()", "dr"])
def test_collection_fields_reject_a_bare_string(
        cls: type, field: str, value: str) -> None:
    # '' iterates to nothing, so it silently stored an empty frozenset
    # rather than failing.
    with pytest.raises(TypeError, match="bare string"):
        cls(**{field: value})


@pytest.mark.parametrize("cls", [Policy, PolicyPatch])
@pytest.mark.parametrize("field,items,expected", [
    ("nickname_delimiters", [("<", ">")], frozenset({("<", ">")})),
    ("maiden_delimiters", [("[", "]")], frozenset({("[", "]")})),
    ("extra_suffix_delimiters", ["/"], frozenset({"/"})),
    ("patronymic_rules", ["turkic"], frozenset({PatronymicRule.TURKIC})),
    ("segment_scripts", [Script.HAN], frozenset({Script.HAN})),
])
def test_legitimate_iterables_are_accepted_and_stored_intact(
        cls: type, field: str, items: list, expected: frozenset) -> None:
    """The guards must not over-reject -- and must not consume.

    Asserts the STORED value, not merely that construction returned.
    `assert cls(...) is not None` is a tautology for a dataclass: it
    passes for a guard that accepts a one-shot iterable, exhausts it,
    and stores frozenset(). That is the same "stored a value the caller
    never wrote" failure the guards exist to prevent, so the generator
    and iter() entries below are the ones that matter.

    All four fields, both classes: an over-strict guard on
    maiden_delimiters was invisible to the entire suite, because every
    other call site happens to pass it a frozenset.
    """
    for value in (frozenset(items), set(items), list(items), tuple(items),
                  (x for x in items), iter(items)):
        stored = getattr(cls(**{field: value}), field)
        assert stored == expected, (
            f"{cls.__name__}.{field} stored {stored!r} for "
            f"{type(value).__name__}")


@pytest.mark.parametrize("cls", [Policy, PolicyPatch])
def test_a_pair_mapping_is_accepted_through_items(cls: type) -> None:
    # The escape the mapping guard's message recommends. It works only
    # because ItemsView is a Set rather than a Mapping; if that ever
    # stops being true, the advice becomes wrong and this fails.
    stored = cls(nickname_delimiters={"<": ">"}.items()).nickname_delimiters
    assert stored == frozenset({("<", ">")})


@pytest.mark.parametrize("cls", [Policy, PolicyPatch])
@pytest.mark.parametrize("value", [b" - ", bytearray(b" - "), memoryview(b" - ")])
@pytest.mark.parametrize(
    "field", ["extra_suffix_delimiters", "nickname_delimiters",
              "maiden_delimiters", "patronymic_rules", "name_order",
              "segment_scripts"])
def test_every_field_rejects_a_buffer_with_a_decode_hint(
        cls: type, field: str, value: object) -> None:
    # Same cryptic int message Lexicon had, and name_order was the one
    # field the first pass missed.
    with pytest.raises(TypeError, match="decode"):
        cls(**{field: value})


def test_patched_unions_set_valued_fields() -> None:
    base = Policy(extra_suffix_delimiters={"|"})  # type: ignore[arg-type]
    out = base.patched(
        PolicyPatch(extra_suffix_delimiters={"/"}))  # type: ignore[arg-type]
    assert out.extra_suffix_delimiters == frozenset({"|", "/"})


def test_patched_overrides_scalars_and_leaves_unset_alone() -> None:
    base = Policy(middle_as_family=True, lenient_comma_suffixes=False)
    out = base.patched(PolicyPatch(strip_emoji=False))
    assert out.strip_emoji is False
    assert out.middle_as_family is True
    assert out.lenient_comma_suffixes is False


def test_patched_with_empty_patch_returns_same_policy() -> None:
    base = Policy(middle_as_family=True)
    assert base.patched(PolicyPatch()) is base


def test_patched_validates_patch_values_at_apply_time() -> None:
    # PolicyPatch scalars validate lazily by design; the error surfaces
    # when the patch is applied.
    patch = PolicyPatch(strip_emoji="off")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="strip_emoji must be a bool"):
        Policy().patched(patch)


def test_patched_rejects_non_patch() -> None:
    with pytest.raises(TypeError, match="takes a PolicyPatch"):
        Policy().patched({"strip_emoji": False})  # type: ignore[arg-type]


def test_script_orders_default_and_canonical_storage() -> None:
    p = Policy()
    assert p.script_orders == DEFAULT_SCRIPT_ORDERS
    # constructor tolerates a Mapping; storage is the sorted pair
    # tuple (hashability, the capitalization_exceptions precedent --
    # which is also why the mapping spelling needs the ignore: the
    # field is annotated with what it STORES)
    q = Policy(script_orders={Script.HANGUL: FAMILY_FIRST,  # type: ignore[arg-type]
                              Script.HAN: FAMILY_FIRST})
    assert q == p and hash(q) == hash(p)
    assert Policy(script_orders={}).script_orders == ()  # type: ignore[arg-type]


def test_script_orders_validates_keys_and_values() -> None:
    with pytest.raises(ValueError, match="han, hangul"):
        Policy(script_orders={"klingon": FAMILY_FIRST})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="exported orders"):
        Policy(script_orders={Script.HAN: (Role.MIDDLE, Role.GIVEN,  # type: ignore[arg-type]
                                           Role.FAMILY)})
    with pytest.raises(TypeError, match="bare string"):
        Policy(script_orders="han")  # type: ignore[arg-type]


def test_segment_scripts_defaults_to_hangul_and_coerces() -> None:
    # hangul segmentation is default-on (amendment 2026-07-27):
    # hangul is unambiguously Korean and the surname set is closed
    assert Policy().segment_scripts == frozenset({Script.HANGUL})
    p = Policy(segment_scripts=["han", Script.HANGUL])  # type: ignore[arg-type]
    assert p.segment_scripts == frozenset({Script.HAN, Script.HANGUL})
    assert Policy(segment_scripts=()).segment_scripts == frozenset()  # type: ignore[arg-type]


def test_segment_scripts_rejects_unknown_script() -> None:
    # bare-string/mapping rejection is covered by the _GUARDED family
    # sweep (test_collection_fields_reject_a_bare_string /
    # test_collection_fields_reject_a_mapping); this pins the one
    # check unique to segment_scripts -- the unknown-script message.
    with pytest.raises(ValueError, match="han, hangul"):
        Policy(segment_scripts={"klingon"})  # type: ignore[arg-type]


def test_segment_scripts_rejects_non_iterable_with_curated_message() -> None:
    # parallel to patronymic_rules: name the expected shape rather than
    # letting _require_iterable's default "an iterable" phrasing stand
    with pytest.raises(TypeError,
                       match="segment_scripts must be an iterable of "
                             "Script members, got True"):
        Policy(segment_scripts=True)  # type: ignore[arg-type]


def test_segment_scripts_patch_unions() -> None:
    patched = apply_patch(
        Policy(), PolicyPatch(segment_scripts={Script.HAN}))  # type: ignore[arg-type]
    assert patched.segment_scripts == frozenset(
        {Script.HAN, Script.HANGUL})
    stringly = apply_patch(
        Policy(), PolicyPatch(segment_scripts={"han"}))  # type: ignore[arg-type]
    assert all(isinstance(s, Script) for s in stringly.segment_scripts)


# One item per field, used to build a bad_iter() below that yields a
# legitimate first entry, then raises -- forcing consumption past the
# iter()-probe stage so a rewrite-vs-propagate bug can only be caught
# by actually running the generator.
_PROPAGATION_FIELD_VALUES = {
    "segment_scripts": Script.HAN,
    "patronymic_rules": PatronymicRule.TURKIC,
    "script_orders": (Script.HAN, FAMILY_FIRST),
    "nickname_delimiters": ("<", ">"),
    "maiden_delimiters": ("[", "]"),
    "extra_suffix_delimiters": "/",
}


@pytest.mark.parametrize("cls,field", [
    (Policy, "segment_scripts"),
    (Policy, "patronymic_rules"),
    (Policy, "script_orders"),
    (Policy, "nickname_delimiters"),
    (Policy, "maiden_delimiters"),
    (Policy, "extra_suffix_delimiters"),
    (PolicyPatch, "segment_scripts"),
    (PolicyPatch, "patronymic_rules"),
    (PolicyPatch, "script_orders"),
    (PolicyPatch, "nickname_delimiters"),
    (PolicyPatch, "maiden_delimiters"),
    (PolicyPatch, "extra_suffix_delimiters"),
])
def test_caller_generator_errors_propagate_untouched(
        cls: type, field: str) -> None:
    """A TypeError raised INSIDE a caller's generator, after it has
    already yielded a legitimate value, must reach the caller with its
    own message -- not be rewritten as "not an iterable" by whichever
    guard happens to consume the generator to check its shape.

    Probe-only-in-try is what makes this true: iter() succeeds (so the
    guard doesn't fire), and only the SEPARATE, unguarded consumption
    step sees the generator's own exception. PolicyPatch.script_orders
    is the scalar (non-union) field with its own canonicalization
    block, distinct from the shared union loop the other fields go
    through below -- it needs the identical probe/consume split, since
    deferring a caller-generator error to apply time is impossible
    once the generator is already exhausted (verified: the error would
    otherwise be lost for good, not merely delayed)."""
    def bad_iter() -> Iterator[object]:
        yield _PROPAGATION_FIELD_VALUES[field]
        raise TypeError("boom")

    with pytest.raises(TypeError, match="boom"):
        cls(**{field: bad_iter()})


def test_policy_patch_script_orders_non_iterable_still_defers_to_apply() -> None:
    # The deferral contract this fix must NOT break: a genuinely
    # non-iterable script_orders value is not a caller-generator error
    # -- it fails the iter() probe itself, so PolicyPatch construction
    # stays lazy (and hashable) and Policy's own guard raises the
    # curated message once the patch is actually applied.
    patch = PolicyPatch(script_orders=5)  # type: ignore[arg-type]
    assert isinstance(hash(patch), int)
    with pytest.raises(TypeError, match="script_orders must be a mapping"):
        apply_patch(Policy(), patch)


def test_canonical_script_pair_defers_each_malformed_shape() -> None:
    # _canonical_script_pair's three per-pair deferral branches, each
    # constructible (hashable) and each quoted by Policy's own guard at
    # apply time: a pair of the wrong arity; a str order value (which
    # tuple() would shred to characters); a non-iterable order value.
    arity = PolicyPatch(
        script_orders=[(Script.HAN, FAMILY_FIRST, "extra")])  # type: ignore[arg-type]
    assert isinstance(hash(arity), int)
    with pytest.raises(TypeError, match=r"\(Script, order\) pairs"):
        apply_patch(Policy(), arity)
    stringly = PolicyPatch(script_orders={Script.HAN: "gmf"})  # type: ignore[arg-type]
    assert isinstance(hash(stringly), int)
    with pytest.raises(TypeError, match="bare string"):
        apply_patch(Policy(), stringly)
    lone = PolicyPatch(script_orders={Script.HAN: 5})  # type: ignore[arg-type]
    assert isinstance(hash(lone), int)
    with pytest.raises(TypeError, match="must be an iterable, got 5"):
        apply_patch(Policy(), lone)


def test_policy_patch_one_shot_bad_tail_defers_without_silent_drop() -> None:
    # The silent-drop repro: a ONE-SHOT generator whose first item is a
    # good pair and whose second is a bad shape (not caller-generator
    # code raising -- just a malformed entry). PolicyPatch construction
    # must not raise (this is a shape problem, deferred to apply time,
    # like the bytes case), but the exhausted-generator hole meant
    # apply_patch used to silently store () -- "opt out of per-script
    # ordering" -- with NO error anywhere, dropping the Han/Hangul
    # family-first defaults. The list form of the identical input
    # already raised correctly; only the one-shot form leaked.
    gen = (x for x in [(Script.HAN, FAMILY_FIRST), 5])
    patch = PolicyPatch(script_orders=gen)  # type: ignore[arg-type]
    # Materialized into a re-iterable tuple, not left as the exhausted
    # generator -- Policy can still quote the caller's bad entry (5).
    assert patch.script_orders == ((Script.HAN, FAMILY_FIRST), 5)
    with pytest.raises(TypeError,
                       match=r"script_orders entries must be .* got 5"):
        apply_patch(Policy(), patch)
