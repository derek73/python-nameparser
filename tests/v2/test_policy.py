import dataclasses

import pytest

from nameparser._policy import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, GIVEN_FIRST,
    PatronymicRule, Policy, PolicyPatch, UNSET, apply_patch,
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
        "maiden_delimiters", "extra_suffix_delimiters",
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
