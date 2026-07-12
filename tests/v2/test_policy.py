import dataclasses

import pytest

from nameparser._policy import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, GIVEN_FIRST,
    PatronymicRule, Policy,
)
from nameparser._types import Role


def test_order_constants_read_as_their_contents():
    assert GIVEN_FIRST == (Role.GIVEN, Role.MIDDLE, Role.FAMILY)
    assert FAMILY_FIRST == (Role.FAMILY, Role.GIVEN, Role.MIDDLE)
    assert FAMILY_FIRST_GIVEN_LAST == (Role.FAMILY, Role.MIDDLE, Role.GIVEN)


def test_policy_defaults():
    p = Policy()
    assert p.name_order == GIVEN_FIRST
    assert p.patronymic_rules == frozenset()
    assert ("(", ")") in p.nickname_delimiters
    assert p.maiden_delimiters == frozenset()
    assert p.strip_emoji and p.strip_bidi and p.lenient_comma_suffixes


def test_policy_is_hashable_and_replaceable():
    p = dataclasses.replace(Policy(), name_order=FAMILY_FIRST)
    assert p.name_order == FAMILY_FIRST
    assert isinstance(hash(p), int)


def test_name_order_must_be_permutation_and_error_names_constants():
    with pytest.raises(ValueError, match="FAMILY_FIRST_GIVEN_LAST"):
        Policy(name_order=(Role.TITLE, Role.GIVEN, Role.FAMILY))
    with pytest.raises(ValueError, match="GIVEN_FIRST"):
        Policy(name_order=(Role.GIVEN, Role.GIVEN, Role.FAMILY))


def test_patronymic_rules_coerce_and_reject():
    p = Policy(patronymic_rules=frozenset({"east-slavic"}))
    assert p.patronymic_rules == frozenset({PatronymicRule.EAST_SLAVIC})
    with pytest.raises(ValueError, match="east-slavic, turkic"):
        Policy(patronymic_rules=frozenset({"klingon"}))


def test_delimiter_pairs_must_be_nonempty_string_pairs():
    with pytest.raises(ValueError, match="non-empty"):
        Policy(nickname_delimiters=frozenset({("", ")")}))


def test_delimiter_pair_rejects_two_char_string():
    with pytest.raises(ValueError, match="tuples"):
        Policy(nickname_delimiters=frozenset({"()"}))  # type: ignore[arg-type]


def test_patronymic_rules_rejects_bare_string_and_non_iterable():
    with pytest.raises(ValueError, match="bare string"):
        Policy(patronymic_rules="east-slavic")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="valid rules"):
        Policy(patronymic_rules=5)  # type: ignore[arg-type]
