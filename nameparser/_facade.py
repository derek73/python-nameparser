"""The 2.0 ``HumanName`` facade (migration spec §2): a mutable wrapper
over a frozen ParsedName, delegating parsing to the core Parser resolved
from the bound Constants shim. Keeps every v1 spelling. Deleted in 3.0.

Layering: facade layer -- may import anything public plus _render.
"""
from __future__ import annotations

import dataclasses
import warnings

from nameparser._config_shim import CONSTANTS, Constants, _cached_parser
from nameparser._lexicon import _normalize
from nameparser._parser import Parser
from nameparser._types import ParsedName, Role

_V2_FIELD = {"first": "given", "last": "family"}  # v1 name -> v2 name
_MEMBERS = ("title", "first", "middle", "last", "suffix", "nickname",
            "maiden")

#: v1 parsing hooks the facade never calls (spec §2 exception 2 / #280).
_V1_HOOKS = (
    "pre_process", "post_process", "parse_full_name", "parse_pieces",
    "parse_nicknames", "join_on_conjunctions", "squash_emoji",
    "handle_firstnames", "handle_middle_name_as_last",
    "is_title", "is_conjunction", "is_prefix", "is_roman_numeral",
    "is_suffix", "is_suffix_lenient", "is_an_initial",
)
# Module-level mutable state (sanctioned exception, AGENTS.md "One
# sanctioned global"): strong-references every distinct HumanName
# subclass for process lifetime so the hook warning fires once per
# class. Fine in practice -- subclasses are statically defined, and the
# whole module is deleted with the facade layer in 3.0.
_WARNED_SUBCLASSES: set[type] = set()


def _empty_parsed() -> ParsedName:
    return ParsedName(original="", tokens=(), ambiguities=())


class HumanName:
    """v1 ``HumanName`` facade: a mutable wrapper over a frozen
    ``ParsedName``, delegating all parsing to the core ``Parser``
    resolved from the bound ``Constants`` shim (dirty-tracked via its
    ``_generation``). Keeps every v1 spelling (``first``/``last`` over
    the core ``given``/``family``); the v1 parsing hooks are never
    called (#280). Deleted with the facade layer in 3.0.
    """

    def __init__(
        self,
        full_name: str = "",
        constants: Constants | None = CONSTANTS,
        string_format: str | None = None,
        initials_format: str | None = None,
        initials_delimiter: str | None = None,
        initials_separator: str | None = None,
        suffix_delimiter: str | None = None,
        first: str | list[str] | None = None,
        middle: str | list[str] | None = None,
        last: str | list[str] | None = None,
        title: str | list[str] | None = None,
        suffix: str | list[str] | None = None,
        nickname: str | list[str] | None = None,
        maiden: str | list[str] | None = None,
    ) -> None:
        if constants is None:
            raise TypeError(
                "constants=None was removed in 2.0 (#261): pass a "
                "Constants instance, or use the new Parser/Lexicon/"
                "Policy API for per-call configuration"
            )
        if not isinstance(constants, Constants):
            raise TypeError(
                f"constants must be a Constants instance, got {constants!r}"
            )
        self._warn_overridden_hooks()
        self._C = constants
        self._snapshot_gen = -1  # forces first resolve
        _, _, defaults = constants._snapshot()
        self.string_format = (string_format if string_format is not None
                              else defaults.string_format)
        self.initials_format = (initials_format if initials_format is not None
                                else defaults.initials_format)
        self.initials_delimiter = (
            initials_delimiter if initials_delimiter is not None
            else defaults.initials_delimiter)
        self.initials_separator = (
            initials_separator if initials_separator is not None
            else defaults.initials_separator)
        # STALENESS TRAP until M9's validating setters land: these are
        # plain attributes, so reassigning one after construction (e.g.
        # n.suffix_delimiter = " - ") does NOT invalidate _snapshot_gen
        # and a cached snapshot keeps the old value. The M9 setters
        # reset _snapshot_gen to -1 on assignment.
        self.suffix_delimiter = (suffix_delimiter if suffix_delimiter is not None
                                 else defaults.suffix_delimiter)
        self._full_name = ""
        self._parsed = _empty_parsed()
        if first or middle or last or title or suffix or nickname or maiden:
            # NOTE (M6): these are plain instance attributes until the
            # field-setter properties land in M7 -- no parsing happens
            # and full_name stays "". Component-kwarg construction is
            # not exercised by this task's tests; see tests/v2/test_facade.py.
            self.first = first
            self.middle = middle
            self.last = last
            self.title = title
            self.suffix = suffix
            self.nickname = nickname
            self.maiden = maiden
        else:
            self._apply_full_name(full_name)

    @classmethod
    def _warn_overridden_hooks(cls) -> None:
        if cls is HumanName or cls in _WARNED_SUBCLASSES:
            return
        overridden = [h for h in _V1_HOOKS
                      if getattr(cls, h, None) is not getattr(
                          HumanName, h, None)]
        _WARNED_SUBCLASSES.add(cls)
        if overridden:
            warnings.warn(
                f"{cls.__name__} overrides v1 parsing hooks "
                f"({', '.join(overridden)}) that the 2.0 facade never "
                f"calls; parsing is delegated to the core Parser. "
                f"Migrate to the Lexicon/Policy API. See "
                f"https://github.com/derek73/python-nameparser/issues/280",
                DeprecationWarning, stacklevel=3)

    # -- config / parsing ---------------------------------------------------

    def _resolve(self) -> Parser:
        """Dirty-tracked parser resolution (spec §3): rebuild the
        snapshot only when the bound Constants' generation moved."""
        gen = self._C._generation
        if self._snapshot_gen != gen:
            lexicon, policy, _ = self._C._snapshot()
            if self.suffix_delimiter:
                policy = dataclasses.replace(
                    policy,
                    extra_suffix_delimiters=frozenset(
                        {self.suffix_delimiter}))
            self._lexicon, self._policy = lexicon, policy
            self._snapshot_gen = gen
        return _cached_parser(self._lexicon, self._policy)

    def _apply_full_name(self, value: str) -> None:
        if isinstance(value, bytes):
            raise TypeError(
                "bytes input was removed in 2.0 (#245): decode first, "
                "e.g. HumanName(raw.decode('utf-8'))"
            )
        if not isinstance(value, str):
            raise TypeError(f"full_name must be a str, got {value!r}")
        self._full_name = value
        self._parsed = self._resolve().parse(value)
        if self._C.capitalize_name:
            self.capitalize()  # v1 parser.py:1653 parity

    def capitalize(self) -> None:
        """Minimal M6 body (M10 ports the full force-semantics rules):
        re-capitalize the current parse against the bound lexicon."""
        self._resolve()
        self._parsed = self._parsed.capitalized(self._lexicon, force=True)

    @property
    def full_name(self) -> str:
        return self._full_name

    @full_name.setter
    def full_name(self, value: str) -> None:
        self._apply_full_name(value)

    @property
    def original(self) -> str:
        return self._parsed.original or self._full_name

    @property
    def C(self) -> Constants:
        return self._C

    @property
    def has_own_config(self) -> bool:
        return self._C is not CONSTANTS

    # -- fields ---------------------------------------------------------

    def _get_field(self, member: str) -> str:
        return getattr(self._parsed, _V2_FIELD.get(member, member))

    def _set_field(self, member: str, value: str | list[str] | None) -> None:
        if value is None:
            joined = ""
        elif isinstance(value, list):
            for element in value:
                if not isinstance(element, str):
                    raise TypeError(
                        f"name parts must be strings, got {element!r}")
            joined = " ".join(value)
        elif isinstance(value, str):
            joined = value
        else:
            raise TypeError(
                f"{member} must be a str, list, or None, got {value!r}")
        self._parsed = self._parsed.replace(
            **{_V2_FIELD.get(member, member): joined})

    def _list_for(self, member: str) -> list[str]:
        # A "joined" continuation token ("Ph." + "D.") belongs to its
        # predecessor's part, matching v1's fix_phd (suffix_list had ONE
        # "Ph. D." element). ParsedName._text_for heals only the suffix
        # string view (the ", " join); the facade list view heals for
        # every role -- a continuation is never its own list element.
        role = Role(_V2_FIELD.get(member, member))
        parts: list[str] = []
        for tok in self._parsed.tokens_for(role):
            if "joined" in tok.tags and parts:
                parts[-1] += " " + tok.text
            else:
                parts.append(tok.text)
        return parts

    @property
    def title(self) -> str:
        return self._get_field("title")

    @title.setter
    def title(self, value: str | list[str] | None) -> None:
        self._set_field("title", value)

    @property
    def title_list(self) -> list[str]:
        return self._list_for("title")

    @property
    def first(self) -> str:
        return self._get_field("first")

    @first.setter
    def first(self, value: str | list[str] | None) -> None:
        self._set_field("first", value)

    @property
    def first_list(self) -> list[str]:
        return self._list_for("first")

    @property
    def middle(self) -> str:
        return self._get_field("middle")

    @middle.setter
    def middle(self, value: str | list[str] | None) -> None:
        self._set_field("middle", value)

    @property
    def middle_list(self) -> list[str]:
        return self._list_for("middle")

    @property
    def last(self) -> str:
        return self._get_field("last")

    @last.setter
    def last(self, value: str | list[str] | None) -> None:
        self._set_field("last", value)

    @property
    def last_list(self) -> list[str]:
        return self._list_for("last")

    @property
    def suffix(self) -> str:
        return self._get_field("suffix")

    @suffix.setter
    def suffix(self, value: str | list[str] | None) -> None:
        self._set_field("suffix", value)

    @property
    def suffix_list(self) -> list[str]:
        return self._list_for("suffix")

    @property
    def nickname(self) -> str:
        return self._get_field("nickname")

    @nickname.setter
    def nickname(self, value: str | list[str] | None) -> None:
        self._set_field("nickname", value)

    @property
    def nickname_list(self) -> list[str]:
        return self._list_for("nickname")

    @property
    def maiden(self) -> str:
        return self._get_field("maiden")

    @maiden.setter
    def maiden(self, value: str | list[str] | None) -> None:
        self._set_field("maiden", value)

    @property
    def maiden_list(self) -> list[str]:
        return self._list_for("maiden")

    # -- derived views ----------------------------------------------------

    @property
    def surnames_list(self) -> list[str]:
        return self.middle_list + self.last_list

    @property
    def surnames(self) -> str:
        return " ".join(self.surnames_list)

    @property
    def given_names_list(self) -> list[str]:
        return self.first_list + self.middle_list

    @property
    def given_names(self) -> str:
        return " ".join(self.given_names_list)

    def _is_particle(self, text: str) -> bool:
        self._resolve()
        return _normalize(text) in self._lexicon.particles

    def _split_last(self) -> tuple[list[str], list[str]]:
        # v1 parser.py _split_last, verbatim: vocabulary lookup at ACCESS
        # time (so assigned last names split too), with the all-particle
        # guard (a family name is assumed not to consist entirely of
        # particles, e.g. surname "Do" which also appears in PREFIXES)
        words = " ".join(self.last_list).split()
        i = 0
        while i < len(words) and self._is_particle(words[i]):
            i += 1
        if i == len(words):
            return [], words
        return words[:i], words[i:]

    @property
    def last_prefixes_list(self) -> list[str]:
        return self._split_last()[0]

    @property
    def last_prefixes(self) -> str:
        return " ".join(self._split_last()[0])

    @property
    def last_base_list(self) -> list[str]:
        return self._split_last()[1]

    @property
    def last_base(self) -> str:
        return " ".join(self._split_last()[1])
