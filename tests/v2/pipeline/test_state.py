import dataclasses
import inspect
from collections.abc import Callable

import pytest

from nameparser._lexicon import Lexicon
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken, _copy_refusals,
    _copyable_fields,
    copy_with,
)
from nameparser._policy import Policy
from nameparser._types import AmbiguityKind, Role, Span


def _state(text: str) -> ParseState:
    return ParseState(original=text, lexicon=Lexicon.empty(), policy=Policy())


def test_state_defaults_are_empty() -> None:
    s = _state("John Smith")
    assert s.tokens == () and s.segments == () and s.pieces == ()
    assert s.structure is Structure.NO_COMMA
    assert s.ambiguities == () and s.extracted == () and s.masked == ()
    assert s.comma_offsets == () and s.interpunct_offsets == ()
    assert s.dropped == () and s.piece_tags == ()
    assert s.segmenter is None
    assert s.one_case is None


def test_state_is_frozen_and_replace_works() -> None:
    s = _state("x")
    tok = WorkToken("x", Span(0, 1))
    s2 = dataclasses.replace(s, tokens=(tok,))
    assert s.tokens == () and s2.tokens == (tok,)
    assert s2.tokens[0].role is None and s2.tokens[0].tags == frozenset()


def test_copy_with_builds_what_dataclasses_replace_builds() -> None:
    # copy_with stands in for dataclasses.replace on every pipeline
    # dataclass, so the two have to agree on each of them.
    tok = WorkToken("x", Span(0, 1))
    pending = PendingAmbiguity(AmbiguityKind.COMMA_STRUCTURE, "detail")
    for obj, changes in (
        (_state("x"), {"tokens": (tok,), "one_case": True}),
        (tok, {"role": Role.GIVEN, "tags": frozenset({"initial"})}),
        (pending, {"indices": (0,)}),
    ):
        assert copy_with(obj, **changes) == dataclasses.replace(obj, **changes)
        assert copy_with(obj) == obj and copy_with(obj) is not obj


def test_copy_with_rejects_a_field_the_class_does_not_have() -> None:
    with pytest.raises(TypeError, match="no field named rol"):
        copy_with(WorkToken("x", Span(0, 1)), rol=Role.GIVEN)  # type: ignore[call-arg]


def test_copy_with_copies_only_the_pipeline_dataclasses() -> None:
    with pytest.raises(TypeError, match="not _Validated"):
        copy_with(_Validated(1), value=2)


@dataclasses.dataclass(frozen=True)
class _Validated:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("negative")


@dataclasses.dataclass(frozen=True)
class _OwnInit:
    value: int

    def __init__(self, value: int) -> None:
        if value < 0:
            raise ValueError("negative")
        object.__setattr__(self, "value", value)


@dataclasses.dataclass(frozen=True)
class _Derived:
    value: int
    doubled: int = dataclasses.field(init=False, default=0)


@dataclasses.dataclass
class _Base:
    value: int


class _Undecorated(_Base):
    def __init__(self, value: int) -> None:
        super().__init__(value)
        self.extra = "set by __init__"


@dataclasses.dataclass(frozen=True)
class _OwnNew:
    value: int

    def __new__(cls, value: int) -> "_OwnNew":
        if value < 0:
            raise ValueError("negative")
        return super().__new__(cls)


@dataclasses.dataclass(frozen=True)
class _FrozenBase:
    value: int


@dataclasses.dataclass(frozen=True)
class _Other:
    # `extra` is set by the __init__ without being one of its
    # parameters, so a class borrowing it takes exactly its own fields
    value: int
    extra: str = dataclasses.field(
        default_factory=lambda: "set by _Other.__init__", init=False)


class _Borrower(_FrozenBase):
    __init__ = _Other.__init__


class _Spoof(_FrozenBase):
    # borrows _Other's __init__ and takes its name, so the name test
    # passes and only the missing decoration gives it away
    __init__ = _Other.__init__
    __qualname__ = "_Other"


@dataclasses.dataclass(frozen=True)
class _WithInitVar:
    value: int
    token: dataclasses.InitVar[int]


@dataclasses.dataclass
class _Guarded:
    value: int

    def __setattr__(self, name: str, value: object) -> None:
        if name == "value" and isinstance(value, int) and value < 0:
            raise ValueError("negative")
        super().__setattr__(name, value)


class _ValidatingMeta(type):
    def __call__(cls, *args: object, **kwargs: object) -> object:
        if any(isinstance(v, int) and v < 0 for v in (*args, *kwargs.values())):
            raise ValueError("negative")
        return super().__call__(*args, **kwargs)


@dataclasses.dataclass(frozen=True)
class _MetaBuilt(metaclass=_ValidatingMeta):
    value: int


def _derived_with_doubled_set() -> _Derived:
    obj = _Derived(1)
    object.__setattr__(obj, "doubled", 2)
    return obj


def _unguarded_copy(obj: object, **changes: object) -> object:
    new = object.__new__(type(obj))
    for f in dataclasses.fields(obj):  # type: ignore[arg-type]
        object.__setattr__(new, f.name, changes.get(f.name, getattr(obj, f.name)))
    return new


def _outcome(copy: Callable[[], object]) -> object:
    """What a caller reads off the copy: every field, plus any attribute
    set outside the fields, or "raises" where the copy refused (a
    missing InitVar is a ValueError to `replace` through 3.12 and a
    TypeError from 3.13)."""
    try:
        result = copy()
    except (ValueError, TypeError):
        return "raises"
    names = [f.name for f in dataclasses.fields(result)]  # type: ignore[arg-type]
    return {name: getattr(result, name) for name in dict.fromkeys([*names, *vars(result)])}


#: What dataclasses.replace builds for each class the guard refuses, and
#: what a field copy without the guard would build instead: the negative
#: control, recorded so the refusal test cannot pass vacuously.
_UNGUARDED_EFFECT = [
    ("validating __post_init__", _Validated(1), {"value": -1},
     "raises", {"value": -1}, ["defines __post_init__"]),
    ("validating __init__", _OwnInit(1), {"value": -1},
     "raises", {"value": -1}, ["__init__ not generated for it"]),
    ("validating __new__", _OwnNew(1), {"value": -1},
     "raises", {"value": -1}, ["defines __new__"]),
    ("init=False field", _derived_with_doubled_set(), {"value": 3},
     {"value": 3, "doubled": 0}, {"value": 3, "doubled": 2},
     ["has an init=False field"]),
    ("undecorated subclass", _Undecorated(1), {"value": 2},
     {"value": 2, "extra": "set by __init__"}, {"value": 2},
     ["not decorated as a dataclass itself",
      "__init__ not generated for it"]),
    ("borrowed __init__", _Borrower(1), {"value": 2},
     {"value": 2, "extra": "set by _Other.__init__"}, {"value": 2},
     ["not decorated as a dataclass itself",
      "__init__ not generated for it"]),
    ("borrowed __init__ under the lender's name", _Spoof(1), {"value": 2},
     {"value": 2, "extra": "set by _Other.__init__"}, {"value": 2},
     ["not decorated as a dataclass itself"]),
    ("InitVar", _WithInitVar(1, 5), {"value": 2},
     "raises", {"value": 2}, ["__init__ does not take exactly its init fields"]),
    ("validating __setattr__", _Guarded(1), {"value": -1},
     "raises", {"value": -1}, ["not frozen"]),
    ("validating metaclass __call__", _MetaBuilt(1), {"value": -1},
     "raises", {"value": -1}, ["built by a metaclass"]),
]


@pytest.mark.parametrize(
    "shape,obj,changes,by_replace,by_field_copy,refusals", _UNGUARDED_EFFECT,
    ids=[row[0] for row in _UNGUARDED_EFFECT])
def test_the_guard_refuses_a_class_a_field_copy_would_get_wrong(
        shape: str, obj: object, changes: dict[str, object],
        by_replace: object, by_field_copy: object,
        refusals: list[str]) -> None:
    assert _outcome(lambda: dataclasses.replace(obj, **changes)) == by_replace  # type: ignore[type-var]
    assert _outcome(lambda: _unguarded_copy(obj, **changes)) == by_field_copy
    assert _copy_refusals(type(obj)) == refusals
    with pytest.raises(TypeError, match="cannot copy"):
        _copyable_fields(type(obj))


def test_every_guard_condition_alone_refuses_a_recorded_shape() -> None:
    # The table is the guard's negative control, so each condition must
    # be the ONLY reason for at least one row: otherwise dropping it
    # would fail nothing here. The count ties the table to the code.
    sole = {row[5][0] for row in _UNGUARDED_EFFECT if len(row[5]) == 1}
    conditions = inspect.getsource(_copy_refusals).count("reasons.append(")
    assert len(sole) == conditions, sorted(sole)


def test_worktoken_carries_optional_role() -> None:
    t = WorkToken("Jack", Span(6, 10), role=Role.NICKNAME)
    assert t.role is Role.NICKNAME


def test_stage_field_ownership() -> None:
    # The ParseState docstring's ownership map, pinned mechanically: run
    # the whole case corpus through the fold stage by stage and assert
    # each stage only changes the fields it owns. Converts the prose
    # contract into a test (a future stage clobbering another stage's
    # field fails here, not in a distant assertion).
    import dataclasses as _dc

    from nameparser import Lexicon as _Lexicon
    from nameparser._pipeline import STAGES

    from ..cases import CASES

    ownership = {
        "extract_delimited": {"extracted", "masked", "ambiguities"},
        # tokenize also rewrites ambiguities: extract_delimited runs
        # before tokens exist, so its UNBALANCED_DELIMITER entries carry
        # a character offset that tokenize resolves to a token index
        "tokenize": {"tokens", "comma_offsets", "interpunct_offsets",
                     "ambiguities"},
        # segment records `one_case` too, lazily, only where C2's flag
        # on a part past the second comma asks for it (#289/#516, #613);
        # a name that never asks pays nothing.
        "segment": {"segments", "structure", "ambiguities", "one_case"},
        # script_segment splits one unspaced CJK token into n+1 pieces
        # (n = 1 from the vocabulary, any n from a segmenter), so it
        # rewrites tokens and shifts every later index the earlier
        # stages recorded -- the segment runs included. It is
        # deliberately absent from token_ownership below, whose
        # token-count assert is the one contract this stage is exempt
        # from. structure and segmenter it only READS (the
        # FAMILY_COMMA opt-out, asked again for itself since #613, and
        # the hook it consults on a vocabulary decline).
        "script_segment": {"tokens", "segments", "ambiguities"},
        # classify also emits SUFFIX_OR_NICKNAME: the delimiter escape
        # that decides it lives in extract_delimited, which has no token
        # index to point at, so the report is raised here instead
        "classify": {"tokens", "ambiguities", "one_case"},
        # group also emits PARTICLE_OR_GIVEN: the prefix chain takes
        # the particle branch of a fork whose given branch _assign
        # takes, so each stage reports the side it decides
        # and since #613 group writes `structure`: segment hands every
        # comma form over as the family comma, and group's head decides
        # it once classify has tagged the words (_comma.decide),
        # binding a postnominal part's roles and dropping its cores
        # and empties the segment of a part it bound, so no join can
        # reach it (#613's /simplify)
        # and since #614 the trailing run it reads once at its head,
        # handed to assign (`tail_reads`)
        "group": {"tokens", "pieces", "piece_tags", "dropped",
                  "ambiguities", "structure", "segments", "tail_reads"},
        # assign also records `order`: the effective order it read the
        # name under, which post_rules needs and must not re-derive
        "assign": {"tokens", "ambiguities", "order"},
        # post_rules also emits PARTICLE_OR_GIVEN: P6's no-comma
        # attachment (#467) takes the family branch of a fork whose
        # other branches assign and group take, so each stage reports
        # the side it decides; the comma site is assign's since #613
        "post_rules": {"tokens", "ambiguities"},
    }
    assert {s.__name__ for s in STAGES} == set(ownership)
    # Within the tokens themselves the contract is finer: texts and
    # spans are fixed at tokenize (the anti-#100 invariant -- tokens
    # are never re-created), classify touches only tags, and the
    # role-assigning stages touch only roles (group also tags, for the
    # ph-d "joined" marker and the caps shape's acronym marks
    # `_comma.decide` writes on a bound part (#564, #613), assign for P6's folded-middle mark after a
    # comma, and post_rules for the entry "joined" marker beside its
    # own folded-middle marks).
    token_ownership = {
        "classify": {"tags"},
        "group": {"tags", "role"},
        # assign also tags since #613: P6's attachment after a family
        # comma marks the particles it joins to the family
        # vocab:folded-middle, for the family view's prepend order
        "assign": {"role", "tags"},
        # post_rules also tags: P6's attachments it still makes (the
        # no-comma site, and after a comma with nothing before it) and
        # the middle_as_family fold mark folded tokens
        # vocab:folded-middle for the family view's prepend order, R2
        # and R3 write their unjoined marks, and R1's entry pass marks
        # a post-nominal "joined" when the writer wrote no comma
        # before it (#436)
        "post_rules": {"role", "tags"},
    }
    for case in CASES:
        if case.locale is not None:
            # locale rows dissolve into a Policy only through parser_for
            # (nameparser._parser); this test exercises the raw stage
            # pipeline directly, and the same inputs already run here
            # under the equivalent synthetic Policy row (_ES/_TK) --
            # covering them again through a resolved locale policy would
            # be redundant, not additive.
            continue
        state = ParseState(original=case.text, lexicon=_Lexicon.default(),
                           policy=case.policy or Policy())
        for stage in STAGES:
            before = {f.name: getattr(state, f.name)
                      for f in _dc.fields(state)}
            state = stage(state)
            changed = {name for name, value in before.items()
                       if getattr(state, name) != value}
            assert changed <= ownership[stage.__name__], (
                f"{case.id}: {stage.__name__} changed {changed - ownership[stage.__name__]}")
            if stage.__name__ not in token_ownership:
                continue
            allowed = token_ownership[stage.__name__]
            assert len(state.tokens) == len(before["tokens"]), (
                f"{case.id}: {stage.__name__} changed the token count")
            for old, new in zip(before["tokens"], state.tokens):
                token_changed = {
                    f.name for f in _dc.fields(old)
                    if getattr(old, f.name) != getattr(new, f.name)}
                assert token_changed <= allowed, (
                    f"{case.id}: {stage.__name__} changed token fields "
                    f"{token_changed - allowed} on {old.text!r}")
