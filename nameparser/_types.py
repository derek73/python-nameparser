"""Core value types for the 2.0 API.

Layering (enforced by tests/v2/test_layering.py): this module imports
nothing from nameparser at module level -- it is the bottom of the
module-import dependency graph. The rendering delegates import _render
and matches() imports _parser at call time; TYPE_CHECKING-only imports
supply the Lexicon/Parser annotations.

Repr policy (applies to every v2 type's __repr__, across this module and
_lexicon.py/_policy.py/_locale.py): bounded output only. No repr may scale
with vocabulary size -- collections render as counts or deltas, never
contents.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, NamedTuple, NoReturn, TypeVar

if TYPE_CHECKING:
    from nameparser._lexicon import Lexicon
    from nameparser._parser import Parser


class Role(StrEnum):
    """The seven fields of a parsed name, one per :class:`Token`.
    Declaration order is the canonical field order everywhere
    (``as_dict()``, ``comparison_key()``, rendering). A StrEnum, like
    :class:`AmbiguityKind`: members ARE their string values, so
    ``token.role == "given"`` compares directly and
    ``str(Role.GIVEN) == "given"``. Members order as strings, so
    ``sorted()`` yields alphabetical order -- iterate ``Role`` itself
    for the canonical order."""

    # Declaration order IS the canonical field order (conventions §3):
    # every listing of the seven fields anywhere derives from this.

    #: Pre-nominal titles and honorifics ("Dr.", "Sir", "Capt.").
    TITLE = "title"
    #: The given (first) name, or its initial.
    GIVEN = "given"
    #: Names between given and family -- middle names or initials.
    MIDDLE = "middle"
    #: The family (last) name, including any particles ("de la Vega").
    FAMILY = "family"
    #: Post-nominal pieces ("III", "Jr.", "PhD").
    SUFFIX = "suffix"
    #: Delimited nickname content ("Jonathan 'Jack' Kennedy" -> "Jack").
    NICKNAME = "nickname"
    #: A birth surname, from a marker word ("Jane Smith née Jones" ->
    #: "Jones") or a delimiter pair routed via Policy.maiden_delimiters.
    MAIDEN = "maiden"


class Span(NamedTuple):
    """Where a :class:`Token` came from: a character range into
    :attr:`ParsedName.original` such that ``original[start:end]`` is
    the token's source text (``end`` exclusive). A plain two-int
    NamedTuple; ``None`` in :attr:`Token.span` marks a synthetic token
    with no source position."""

    #: First character index (0-based).
    start: int
    #: One past the last character index.
    end: int

    def __add__(self, other: object) -> NoReturn:  # type: ignore[override]
        # Inherited tuple + would concatenate two spans into a 4-tuple.
        # There is deliberately NO covering-span operation: grouping is
        # index-run based (the anti-#100 invariant: never resolve by
        # joining text back together) and never merges spans.
        raise TypeError(
            "Span does not support +; tuple concatenation is not a "
            "covering span"
        )


#: The four :attr:`Token.tags` values that are stable API.
#: "particle" marks a word from the particle vocabulary ("de", "van")
#: wherever it lands -- including a given-name "Van" -- so combine it
#: with Role.FAMILY (as family_particles does) to get actual family
#: particles; "conjunction" a joining word ("and", "y"); "initial" an
#: initial-shaped word ("J.", "Q");
#: "joined" a continuation of the previous token within one merged
#: piece ("Ph." + "D."), which the suffix view joins with a space
#: instead of ", ". Every other tag is namespaced ("vocab:...") and is
#: unstable debugging provenance -- never match against those.
STABLE_TAGS = frozenset({"particle", "conjunction", "initial", "joined"})

#: The one sanctioned view-reorder marker (namespaced = unstable API).
#: Tokens cannot reorder (span order is validated), so a role fold that
#: must render BEFORE the role's original tokens tags them with this;
#: _text_for and the facade lists prepend carriers. Single-sourced here
#: so the emitter (_pipeline/_post_rules) and the consumers cannot
#: drift.
FOLDED_TAG = "vocab:folded-middle"

_E = TypeVar("_E", bound=Enum)


def _coerce_enum(value: object, enum_cls: type[_E], noun: str, plural: str) -> _E:
    """Coerce value to enum_cls, or raise the enriched ValueError listing
    every valid member (enum lookups stay ValueError for any input --
    stdlib EnumType precedent, see AGENTS.md's taxonomy rule)."""
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        valid = ", ".join(str(m.value) for m in enum_cls)
        raise ValueError(
            f"unknown {noun} {value!r}; valid {plural}: {valid}"
        ) from None


# Pickle support shared by the frozen slots dataclasses: fail at the
# LOAD site when a pickle's field layout does not match this version of
# the class (version skew) -- silently loading would defer the failure
# to a distant attribute read. Values are deliberately NOT re-validated:
# pickle is not a security boundary (arbitrary pickles can execute code
# anyway), and canonical state only comes from a validated instance.
# These are ASSIGNED IN EACH CLASS BODY (not inherited from a mixin):
# @dataclass(slots=True) regenerates the class and installs its own
# pickle methods unless __getstate__/__setstate__ are in the class's
# own __dict__. Lexicon duplicates this logic by design (its slots also
# carry a rebuilt mappingproxy) -- layering keeps _lexicon import-free
# of _types.


def _guarded_getstate(self: object) -> dict[str, object]:
    fields = dataclasses.fields(self)  # type: ignore[arg-type]
    return {f.name: getattr(self, f.name) for f in fields}


def _guarded_setstate(self: object, state: dict[str, object]) -> None:
    fields = dataclasses.fields(self)  # type: ignore[arg-type]
    expected = {f.name for f in fields}
    if set(state) != expected:
        missing = ", ".join(sorted(expected - set(state))) or "none"
        unexpected = ", ".join(sorted(set(state) - expected)) or "none"
        raise ValueError(
            f"incompatible {type(self).__name__} pickle: missing "
            f"fields: {missing}; unexpected fields: {unexpected}"
        )
    for name, value in state.items():
        object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class Token:
    """One classified word of a parsed name: its text, where it came
    from, which field it belongs to, and how it was classified. Read
    tokens off :attr:`ParsedName.tokens` or
    :meth:`ParsedName.tokens_for`; you only construct one directly
    when hand-building a :class:`ParsedName`."""

    #: The word exactly as written in the input (never empty).
    text: str
    #: Position in ParsedName.original; None marks a synthetic token
    #: (e.g. introduced by replace()) with no source position.
    span: Span | None
    #: The field this token belongs to.
    role: Role
    #: Classification labels. Exactly the four members of
    #: :data:`~nameparser.STABLE_TAGS` ("particle", "conjunction",
    #: "initial", "joined") are API; namespaced tags like "vocab:..."
    #: are unstable debugging provenance -- never match against them.
    tags: frozenset[str] = frozenset()

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError(
                f"Token.text must be a str, got {self.text!r}"
            )
        if not self.text:
            raise ValueError("Token.text must be a non-empty string")
        object.__setattr__(
            self, "role", _coerce_enum(self.role, Role, "Role", "roles"))
        if self.span is not None:
            if not (
                isinstance(self.span, tuple)
                and len(self.span) == 2
                # bool is an int subclass: (False, True) is a comparison
                # result leaking into a coordinate slot, not a span
                and all(isinstance(v, int) and not isinstance(v, bool)
                        for v in self.span)
            ):
                raise TypeError(
                    f"invalid span {self.span!r}: expected a (start, end) "
                    "pair of ints or None"
                )
            start, end = self.span
            if start < 0 or end < start:
                raise ValueError(
                    f"invalid span ({start}, {end}): need 0 <= start <= end"
                )
            object.__setattr__(self, "span", Span(start, end))
        # The same guards _normset applies to Lexicon vocabulary: a bare
        # string would become its character set, a mapping would silently
        # contribute only its keys.
        if isinstance(self.tags, str):
            raise TypeError(
                "Token.tags must be an iterable of strings, "
                "not a bare string"
            )
        if isinstance(self.tags, Mapping):
            raise TypeError(
                "Token.tags must be an iterable of strings, not a mapping"
            )
        tags = frozenset(self.tags)
        for tag in tags:
            if not isinstance(tag, str):
                raise TypeError(
                    f"Token.tags must contain only strings, got {tag!r}"
                )
        object.__setattr__(self, "tags", tags)

    def __repr__(self) -> str:
        # Bounded output: a single token's text/span/role/tags, never
        # scales with vocabulary size (design rule -- see module docstring).
        where = (f"@{self.span.start}:{self.span.end}"
                 if self.span is not None else "@synthetic")
        tags = f" {{{', '.join(sorted(self.tags))}}}" if self.tags else ""
        return f"Token({self.text!r} {where} {self.role.name}{tags})"


class AmbiguityKind(StrEnum):
    """The stable vocabulary of :class:`Ambiguity` kinds. A StrEnum:
    members ARE their string values, so ``kind == "particle-or-given"``
    compares directly. New kinds may be added in minor releases;
    existing values never change meaning.

    A kind names a FORK THE PARSE HAD TO CALL, not a word that could be
    read two ways: the same token elsewhere in a name may present no
    choice at all and is then reported by nothing. Reporting is also
    partial -- a kind listed here is not necessarily emitted everywhere
    its fork occurs (the comma paths stay quiet by design), and coverage
    grows over releases. A non-empty tuple is a signal to act on; an
    empty one is not a guarantee of certainty."""

    #: Reserved: the name's field order itself is uncertain (e.g. a
    #: two-word name under a non-default name_order). Not yet emitted;
    #: planned for 2.x.
    ORDER = "order"
    #: Delimited content is an ambiguous suffix acronym, so it reads
    #: plausibly as either a post-nominal or a nickname -- "JEFFREY
    #: (JD) BRICKEN" keeps the nickname reading, where the
    #: unambiguous "(MBA)" escapes to suffix on vocabulary alone.
    SUFFIX_OR_NICKNAME = "suffix-or-nickname"
    #: A trailing word reads plausibly as either a post-nominal or an
    #: ordinary name part. Covers an ambiguous acronym written without
    #: periods ("John Smith MA" takes MA as a credential because a
    #: family name remains; "Jack MA" keeps it as the name because none
    #: would) and a trailing roman numeral, which is a suffix where any
    #: other single letter would be a name ("John Smith V" vs "John
    #: Smith B"). Which name part was declined depends on position and
    #: ``name_order``, so ``detail`` names it rather than the kind.
    SUFFIX_OR_NAME = "suffix-or-name"
    #: A leading ambiguous particle was read as a given name -- the
    #: right call for "Van Johnson" (the actor's given name), the
    #: wrong one for a bare "Van Buren" (the presidential surname);
    #: the two-word shape cannot distinguish them.
    PARTICLE_OR_GIVEN = "particle-or-given"
    #: A nickname/maiden delimiter opened without closing (or closed
    #: without opening); the text was kept as literal name content, so
    #: the tokens are the one the stray character ended up inside.
    #: Two cases leave that tuple empty: a character that lands in no
    #: token at all (inside a masked region), and an input with no
    #: alphanumeric content anywhere, which parses to an empty name --
    #: the report survives because "was this malformed?" is the only
    #: question left, but there is no token for it to point at.
    #: ``parse("(")`` is the second case, not an exotic one.
    UNBALANCED_DELIMITER = "unbalanced-delimiter"
    #: More comma-separated segments than any recognized name shape;
    #: the parse is best-effort over the extra segments.
    COMMA_STRUCTURE = "comma-structure"
    #: An unspaced CJK token had more than one vocabulary-supported
    #: surname split ("夏侯惇": 夏侯 + 惇 was taken, 夏 + 侯惇 also
    #: matched); the longest surname won, and ``detail`` names both
    #: readings. Points at the two tokens the split produced. (#271)
    SEGMENTATION = "segmentation"


@dataclass(frozen=True, slots=True)
class Ambiguity:
    """A call the parser made that could legitimately have gone the
    other way, surfaced on :attr:`ParsedName.ambiguities` instead of
    silently guessed away. The parse still commits to one reading --
    an Ambiguity is a flag for review, not an error."""

    #: Which known ambiguity shape this is (stable API values).
    kind: AmbiguityKind
    #: Human-readable specifics of this occurrence (wording unstable).
    detail: str
    #: The tokens involved -- always a value-equal subset of the owning
    #: ParsedName's tokens (checked with ==, not identity: two distinct
    #: Token instances with identical text/span/role/tags satisfy this);
    #: may be empty (e.g. unbalanced-delimiter).
    tokens: tuple[Token, ...]

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "kind",
            _coerce_enum(self.kind, AmbiguityKind, "AmbiguityKind", "kinds"))
        if not isinstance(self.detail, str):
            raise TypeError(
                f"Ambiguity.detail must be a str, got {self.detail!r}"
            )
        if not self.detail:
            raise ValueError("Ambiguity.detail must be a non-empty string")
        toks = tuple(self.tokens)
        for tok in toks:
            if not isinstance(tok, Token):
                raise TypeError(
                    f"Ambiguity.tokens must contain only Token instances, "
                    f"got {tok!r}"
                )
        object.__setattr__(self, "tokens", toks)

    def __repr__(self) -> str:
        texts = "/".join(repr(t.text) for t in self.tokens)
        return f"Ambiguity({self.kind.value!r}: {texts})"


def _validated_field_strings(fields: dict[str, str]) -> dict[Role, str]:
    """Shared by ParsedName.replace and Parser.revise: validate a
    **fields mapping of role names to replacement strings and key it
    by Role. TypeErrors match replace()'s historical wording."""
    by_value = {role.value: role for role in Role}
    for key, value in fields.items():
        if key not in by_value:
            raise TypeError(
                f"unknown field {key!r}; expected one of "
                f"{', '.join(by_value)}"
            )
        if not isinstance(value, str):
            raise TypeError(
                f"field {key!r} must be a str, got {value!r}"
            )
    return {by_value[k]: v for k, v in fields.items()}


@dataclass(frozen=True, slots=True)
class ParsedName:
    """The immutable result of parsing one name string. Read the seven
    fields as strings (``.given``, ``.family``, ...); inspect structure
    through :attr:`tokens` / :meth:`tokens_for`; correct a parse with
    :meth:`replace` (returns a new value; Parser.revise is the
    tag-preserving form); produce output with
    :meth:`render`, :meth:`initials`, :meth:`capitalized`, or ``str()``.

    Constructor-enforced invariants: spans ascending, non-overlapping,
    in bounds of `original`; every Ambiguity's tokens are a value-equal
    subset of `tokens` (see Ambiguity.tokens). Provenance semantics
    (text == original[span] for parser-produced names) are documented,
    not enforced -- transforms like replace() legitimately break them.
    """

    #: The input string exactly as passed to parse().
    original: str
    #: Every classified token, in document order.
    tokens: tuple[Token, ...]
    #: Judgment calls that could have gone the other way; empty for
    #: most names (see Ambiguity).
    ambiguities: tuple[Ambiguity, ...] = ()

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not isinstance(self.original, str):
            raise TypeError(
                f"ParsedName.original must be a str, got {self.original!r}"
            )
        object.__setattr__(self, "tokens", tuple(self.tokens))
        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))
        for tok in self.tokens:
            if not isinstance(tok, Token):
                raise TypeError(
                    f"ParsedName.tokens must contain only Token instances, "
                    f"got {tok!r}"
                )
        for amb in self.ambiguities:
            if not isinstance(amb, Ambiguity):
                raise TypeError(
                    f"ParsedName.ambiguities must contain only Ambiguity "
                    f"instances, got {amb!r}"
                )
        prev_end = 0
        for tok in self.tokens:
            if tok.span is None:
                continue
            if tok.span.end > len(self.original):
                raise ValueError(
                    f"token {tok.text!r} span {tuple(tok.span)} is out of "
                    f"bounds for original of length {len(self.original)}"
                )
            if tok.span.start < prev_end:
                raise ValueError(
                    f"token spans must be ascending and non-overlapping; "
                    f"token {tok.text!r} at {tuple(tok.span)} begins before "
                    f"offset {prev_end}"
                )
            prev_end = tok.span.end
        # Hash once rather than rescanning the tuple per referenced
        # token: a name can carry an ambiguity per token (a string of
        # stray delimiters does), and the linear form made construction
        # quadratic in their product. Set membership uses the same value
        # equality the tuple scan did -- Token is frozen and hashable.
        if self.ambiguities:
            known = set(self.tokens)
            for amb in self.ambiguities:
                for tok in amb.tokens:
                    # membership is by Token's value equality, not
                    # identity: this only guarantees a value-equal token
                    # exists in self.tokens, not that `tok` IS one of
                    # those objects.
                    if tok not in known:
                        raise ValueError(
                            f"Ambiguity token {tok.text!r} is not a "
                            f"subset of this ParsedName's tokens"
                        )

    def __bool__(self) -> bool:
        return bool(self.tokens)

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        # 4-space indent, matching HumanName's repr (v1 style)
        lines = []
        for role in Role:
            text = self._text_for(role)
            if text:
                lines.append(f"    {role.value}: {text!r}")
        if self.ambiguities:
            kinds = [a.kind.value for a in self.ambiguities]
            lines.append(f"    ambiguities: {kinds!r}")
        body = "\n".join(lines)
        return f"<ParsedName: [\n{body}\n]>" if lines else "<ParsedName: []>"

    # -- string views (canonical order = Role declaration order) --------

    def _text_for(self, *roles: Role, tag: str | None = None,
                  without_tag: str | None = None) -> str:
        suffix_join = roles == (Role.SUFFIX,)
        parts: list[str] = []
        folded: list[str] = []
        for tok in self.tokens:
            if tok.role not in roles:
                continue
            if tag is not None and tag not in tok.tags:
                continue
            if without_tag is not None and without_tag in tok.tags:
                continue
            # "joined" (stable tag) marks a continuation of the previous
            # token ("Ph." + "D."): attach with a space so the suffix
            # view's ", " join does not split one credential in two
            if suffix_join and "joined" in tok.tags and parts:
                parts[-1] += " " + tok.text
            elif FOLDED_TAG in tok.tags:
                # middle_as_family fold: v1 PREPENDED middle_list to
                # last_list; spans cannot reorder, so the view does
                folded.append(tok.text)
            else:
                parts.append(tok.text)
        return (", " if suffix_join else " ").join(folded + parts)

    @property
    def title(self) -> str:
        return self._text_for(Role.TITLE)

    @property
    def given(self) -> str:
        return self._text_for(Role.GIVEN)

    @property
    def middle(self) -> str:
        return self._text_for(Role.MIDDLE)

    @property
    def family(self) -> str:
        return self._text_for(Role.FAMILY)

    @property
    def suffix(self) -> str:
        return self._text_for(Role.SUFFIX)

    @property
    def nickname(self) -> str:
        return self._text_for(Role.NICKNAME)

    @property
    def maiden(self) -> str:
        return self._text_for(Role.MAIDEN)

    # -- derived views (filters over roles + STABLE tags only) ----------

    @property
    def family_particles(self) -> str:
        return self._text_for(Role.FAMILY, tag="particle")

    @property
    def family_base(self) -> str:
        return self._text_for(Role.FAMILY, without_tag="particle")

    @property
    def surnames(self) -> str:
        return self._text_for(Role.MIDDLE, Role.FAMILY)

    @property
    def given_names(self) -> str:
        return self._text_for(Role.GIVEN, Role.MIDDLE)

    # -- structured access ----------------------------------------------

    def tokens_for(self, role: Role | str) -> tuple[Token, ...]:
        """The tokens of one field, in document order. Takes a Role
        member or its string value; anything else raises ValueError
        naming the valid roles."""
        role = _coerce_enum(role, Role, "Role", "roles")
        return tuple(t for t in self.tokens if t.role is role)

    def as_dict(self, *, include_empty: bool = True) -> dict[str, str]:
        # _text_for handles the suffix ", "-join (single-role SUFFIX call)
        d = {role.value: self._text_for(role) for role in Role}
        if not include_empty:
            d = {k: v for k, v in d.items() if v}
        return d

    # -- editing ----------------------------------------------------------

    def replace(self, **fields: str) -> ParsedName:
        """Return a new ParsedName with the named fields re-tokenized as
        synthetic tokens (span=None). Whitespace-splits each value; an
        empty value clears the field. original is unchanged (provenance).
        Ambiguities referencing replaced tokens are dropped.

        Replacement tokens carry NO tags, so tag-driven views degrade:
        family_particles empties, particles regain their initials, and
        a multi-word suffix is comma-joined. Parser.revise() is the
        tag-preserving alternative.
        """
        replaced = _validated_field_strings(fields)
        synthetic = {
            role: tuple(Token(word, None, role) for word in value.split())
            for role, value in replaced.items()
        }
        return self._with_field_tokens(synthetic)

    def _with_field_tokens(
        self, replaced: Mapping[Role, tuple[Token, ...]],
    ) -> ParsedName:
        """Shared tail of replace()/Parser.revise(): splice each role's
        replacement tokens in at the role's first position (appended in
        canonical order when the role had no tokens); drop ambiguities
        whose referents were replaced."""
        # Private contract, made self-enforcing: a token filed under a
        # key that is not its own role is the one way this shared tail
        # could build a semantically wrong ParsedName (the splice keys
        # on the mapping, the views key on the token).
        for role, toks in replaced.items():
            for tok in toks:
                if tok.role is not role:
                    raise ValueError(
                        f"replacement token {tok.text!r} has role "
                        f"{tok.role.value}, not {role.value}"
                    )
        new_tokens: list[Token] = []
        emitted: set[Role] = set()
        for tok in self.tokens:
            if tok.role in replaced:
                if tok.role not in emitted:
                    new_tokens.extend(replaced[tok.role])
                    emitted.add(tok.role)
                continue
            new_tokens.append(tok)
        for role in Role:
            if role in replaced and role not in emitted:
                new_tokens.extend(replaced[role])
        kept = tuple(
            amb for amb in self.ambiguities
            if all(t in new_tokens for t in amb.tokens)
        )
        return ParsedName(self.original, tuple(new_tokens), kept)

    # -- comparison -------------------------------------------------------

    def comparison_key(self) -> tuple[str, ...]:
        """One casefolded component per Role, in canonical order, for
        dedup, dict keys, and sorting. The semantic layer; __eq__ stays
        strict.
        """
        return tuple(self._text_for(role).casefold() for role in Role)

    def matches(self, other: str | ParsedName, *,
                parser: Parser | None = None) -> bool:
        """Component-wise case-insensitive comparison (the semantic
        layer; __eq__ stays strict). A str argument is parsed with
        `parser`, or with the DEFAULT parser when None -- if this name
        came from a custom Parser, pass that parser (or use
        Parser.matches); otherwise the comparison silently runs under
        the wrong configuration."""
        if isinstance(other, str):
            import nameparser._parser as _parser
            active = parser if parser is not None else _parser._default_parser()
            other = active.parse(other)
        if not isinstance(other, ParsedName):
            raise TypeError(
                f"matches() takes a str or ParsedName, got {other!r}")
        return self.comparison_key() == other.comparison_key()

    # -- rendering delegates ----------------------------------------------
    # One-line delegation to nameparser._render: parsing code physically
    # cannot import formatting logic (layering rule, enforced by
    # tests/v2/test_layering.py), so these import at call time -- module
    # level stays internal-import-free.

    def render(
        self,
        spec: str = ('{title} {given} "{nickname}" {middle} {family} '
                     "({maiden}) {suffix}"),
    ) -> str:
        """Fill the str.format spec from the seven role fields and the
        derived views; empty fields collapse (#254), including the
        default spec's decorations (empty '""' and '()' wrappers).
        The default shows every non-empty field: the nickname quoted
        after the given name, the maiden name parenthesized after the
        family name. Unknown keys raise KeyError naming the valid
        fields."""
        import nameparser._render as _render
        return _render.render(self, spec)

    def initials(self, spec: str = "{given} {middle} {family}",
                 delimiter: str = ".", separator: str = " ") -> str:
        """Initials per group; v1's initials_format/_delimiter/_separator
        become call-site arguments instead of Config-wide settings.
        Valid spec keys: given, middle, family."""
        import nameparser._render as _render
        return _render.initials(self, spec, delimiter, separator)

    def capitalized(self, lexicon: Lexicon | None = None, *,
                    force: bool = False) -> ParsedName:
        """Case-fixing transform -> new ParsedName, same spans, new
        token texts. Needs a lexicon for capitalization_exceptions and
        particle rules; None uses the DEFAULT lexicon -- if this name
        came from a custom Parser, pass its lexicon or use
        Parser.capitalized. force=False preserves mixed-case input
        (v1 parity). Idempotent."""
        import nameparser._render as _render
        return _render.capitalized(self, lexicon, force=force)
