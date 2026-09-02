"""The 2.0 ``HumanName`` facade (mechanisms.md#FACADE-CONTRACT): a
mutable wrapper
over a frozen ParsedName, delegating parsing to the core Parser resolved
from the bound Constants shim. Keeps every v1 spelling. Deleted in 3.0.

Layering: facade layer -- may import anything public plus _render.
"""
from __future__ import annotations

import dataclasses
import warnings
from collections.abc import Iterator, Mapping
from typing import Any

# Import order matters here -- breaks a real import cycle. nameparser.
# config's package __init__ re-exports CONSTANTS/Constants/etc. from
# _config_shim (the v1 nameparser.config.Constants compat path), while
# _config_shim's own default CONSTANTS singleton needs nameparser.config's
# DATA submodules (titles, prefixes, ...), imported lazily -- see
# _config_shim.py's module docstring. If _config_shim were the first of
# the two ever touched, building its CONSTANTS would need to import
# nameparser.config, whose __init__ would in turn need _config_shim's
# (not-yet-built) CONSTANTS: ImportError. Importing the config package
# here first lets its __init__ run to completion; when IT then imports
# _config_shim to build the default CONSTANTS, nameparser.config is
# already registered in sys.modules, so its data-submodule imports
# resolve directly instead of re-entering (and failing on) its own
# still-executing __init__.
import nameparser.config  # noqa: F401

import nameparser._render as _render
from nameparser._config_shim import CONSTANTS, Constants, _cached_parser
from nameparser._lexicon import _normalize
from nameparser._parser import Parser
from nameparser._types import (FOLDED_TAG, UNCLASSIFIED_TAG, ParsedName,
                               Role, Token)

_V2_FIELD = {"first": "given", "last": "family"}  # v1 name -> v2 name
_V1_SPELLING = {v2: v1 for v1, v2 in _V2_FIELD.items()}
# derived from Role: declaration order IS the canonical field order
# (never restated), rendered in the v1 spellings
_MEMBERS = tuple(_V1_SPELLING.get(r.value, r.value) for r in Role)



#: v1 parsing hooks the facade never calls
#: (mechanisms.md#FACADE-CONTRACT / #280).
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
        # These five assignments route through the validating properties
        # below. The suffix_delimiter setter resets _snapshot_gen to -1
        # on every assignment (including this one, harmlessly -- it's
        # already -1 above), so reassigning it post-construction (e.g.
        # n.suffix_delimiter = " - ") correctly forces the next
        # _resolve() to rebuild the Policy with the new delimiter.
        self.suffix_delimiter = (suffix_delimiter if suffix_delimiter is not None
                                 else defaults.suffix_delimiter)
        self._full_name = ""
        self._parsed = _empty_parsed()
        if first or middle or last or title or suffix or nickname or maiden:
            # These route through the field-setter properties (None
            # clears the field); no full-string parse, full_name stays "".
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

    # -- render defaults -----------------------------------------------------
    # One-line validating setters (mechanisms.md#FACADE-CONTRACT):
    # assigning a non-str (or, for
    # the two fields that allow it, non-str-non-None) raises TypeError at
    # assignment time instead of failing later inside .format().

    @property
    def string_format(self) -> str | None:
        return self._string_format

    @string_format.setter
    def string_format(self, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise TypeError(
                f"string_format must be a str or None, got {value!r}")
        self._string_format = value

    @property
    def initials_format(self) -> str:
        return self._initials_format

    @initials_format.setter
    def initials_format(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"initials_format must be a str, got {value!r}")
        self._initials_format = value

    @property
    def initials_delimiter(self) -> str:
        return self._initials_delimiter

    @initials_delimiter.setter
    def initials_delimiter(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"initials_delimiter must be a str, got {value!r}")
        self._initials_delimiter = value

    @property
    def initials_separator(self) -> str:
        return self._initials_separator

    @initials_separator.setter
    def initials_separator(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"initials_separator must be a str, got {value!r}")
        self._initials_separator = value

    @property
    def suffix_delimiter(self) -> str | None:
        return self._suffix_delimiter

    @suffix_delimiter.setter
    def suffix_delimiter(self, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise TypeError(
                f"suffix_delimiter must be a str or None, got {value!r}")
        self._suffix_delimiter = value
        # Invalidate the cached Policy: _resolve() layers suffix_delimiter
        # onto extra_suffix_delimiters, so a stale snapshot would keep
        # parsing against the old delimiter.
        self._snapshot_gen = -1

    # -- config / parsing ---------------------------------------------------

    def _resolve(self) -> Parser:
        """Dirty-tracked parser resolution
        (mechanisms.md#CONFIG-SHIM-SNAPSHOT): rebuild the
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
            self._parser = _cached_parser(lexicon, policy)
            self._snapshot_gen = gen
        # the fast path is a plain attribute return: hashing the two
        # value objects for the lru lookup is the whole fast-path cost
        return self._parser

    def parse_full_name(self) -> None:
        """Re-parse the stored ``full_name`` (v1's documented re-parse
        trigger, docs/customize.rst): mutate ``name.C`` then call this to
        force a re-parse without reassigning ``full_name``. The v1
        parsing INTERNALS this name evokes live in the core ``Parser``,
        not here; a subclass overriding this method still triggers the
        #280 hook-override warning, and full_name assignment never
        consults it."""
        self._apply_full_name(self._full_name)

    def _apply_full_name(self, value: str) -> None:
        if isinstance(value, bytes):
            raise TypeError(
                "bytes input was removed in 2.0 (#245): decode first, "
                "e.g. HumanName(raw.decode('utf-8'))"
            )
        if not isinstance(value, str):
            raise TypeError(f"full_name must be a str, got {value!r}")
        # parse FIRST: if snapshot resolution raises, the instance must
        # not be left with a new full_name over the old parsed fields
        parsed = self._resolve().parse(value)
        self._full_name = value
        self._parsed = parsed
        if self._C.capitalize_name:
            self.capitalize()  # v1 parser.py:1653 parity

    def capitalize(self, force: bool | None = None) -> None:
        """Re-capitalize the current parse against the bound lexicon.
        force=None reads the bound Constants' render default
        (force_mixed_case_capitalization); the core's capitalized()
        implements the single-case gate (v1 parity) -- not
        re-implemented here."""
        self._resolve()
        if force is None:
            force = self._C.force_mixed_case_capitalization
        self._parsed = self._parsed.capitalized(self._lexicon, force=force)

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

    @C.setter
    def C(self, constants: Constants | None) -> None:
        # v1.4 closed #239 by making C a validating setter that ONLY
        # stores the new value -- no re-parse (checked against v1.4:
        # `git show 2d5d8c2:nameparser/parser.py` lines ~204-206, the C
        # setter body is exactly `self._C = self._validate_constants(...)`).
        # A caller who wants the new config reflected must still trigger
        # a re-parse, e.g. via parse_full_name() or a full_name
        # reassignment -- matched here rather than re-parsing eagerly.
        if constants is None:
            raise TypeError(
                "assigning constants=None to C was removed in 2.0 (#261): "
                "pass a Constants instance, or use the new Parser/Lexicon/"
                "Policy API for per-call configuration"
            )
        if not isinstance(constants, Constants):
            raise TypeError(
                f"constants must be a Constants instance, got {constants!r}"
            )
        self._C = constants
        self._snapshot_gen = -1  # invalidate: next _resolve() rebuilds

    @property
    def has_own_config(self) -> bool:
        """True when this instance is not using the shared module-level
        CONSTANTS."""
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
        # v1 setters stay on replace(): revise()'s vocabulary tags would
        # change v1 parity
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
        folded: list[str] = []
        for tok in self._parsed.tokens_for(role):
            if "joined" in tok.tags and parts:
                parts[-1] += " " + tok.text
            elif FOLDED_TAG in tok.tags:
                # middle_as_family fold: v1 PREPENDED middle_list to
                # last_list -- keep the list view consistent with the
                # string view (_text_for orders folded-first too)
                folded.append(tok.text)
            else:
                parts.append(tok.text)
        return folded + parts

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

    def _is_conjunction(self, text: str) -> bool:
        self._resolve()
        return _normalize(text) in self._lexicon.conjunctions

    def _split_last(self) -> tuple[list[str], list[str]]:
        # rules.md#R2: "a name part whose every word is particle
        # vocabulary is a part where none of them is doing a
        # particle's work" -- the all-particle guard
        # below is this rule, and predates its statement: v1 assumed a
        # family name does not consist entirely of particles, e.g. the
        # surname "Do" which also appears in PARTICLES. v1
        # parser.py _split_last otherwise verbatim, vocabulary lookup
        # at ACCESS time so assigned last names split too.
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

    # -- initials -------------------------------------------------------------

    def _process_initial(self, name_part: str, firstname: bool = False) -> str:
        # after v1 parser.py:427, not verbatim: particles and
        # conjunctions are filtered from initials unless the part is a
        # first name. split() rather than split(" "): *_list
        # attributes assigned directly bypass whitespace normalization,
        # and split(" ") yields empty strings for repeated spaces
        # (#232).
        parts = name_part.split()
        initials = []
        for part in parts:
            # v1 parser.py:771 (1.4.0): is_conjunction was "in the
            # conjunctions set AND NOT is_an_initial", so a dotted or
            # bare-capital E/Y is the initial it looks like rather
            # than the connective. The 2.0 facade dropped that half
            # and lost the middle initial of 'Scott E. Werner' (#462).
            # _render._INITIAL is v1's `initial` shape, kept in step
            # with the pipeline's copy by tests/v2/test_regex_sync.py;
            # the facade may import _render but not _pipeline
            # (tests/v2/test_layering.py). Scoped here rather than in
            # _is_conjunction: this is the only caller, and a future
            # one should not inherit a decision made for initials.
            conjunction = (self._is_conjunction(part)
                           and not _render._INITIAL.fullmatch(part))
            if not (self._is_particle(part) or conjunction) or firstname:
                initials.append(part[0])
        if len(initials) > 0:
            return self.initials_separator.join(initials)
        # Return '' (never empty_attribute_default, which may be None)
        # when a part has no initialable words. group_initials below
        # decides what that means: one such element among others is
        # dropped; a group that yields nothing AND is wholly particles
        # initials its words; and a group that yields nothing for any
        # other reason -- a conjunction, or particles mixed with one --
        # is still dropped ("Vega, Santa de y" drops its middle).
        return ""

    def _initials_lists(self) -> tuple[list[str], list[str], list[str]]:
        """Initials for the first, middle and last name groups. Parts
        that yield no initials are dropped rather than kept as empty
        strings -- except a part that is wholly PARTICLES, whose words
        initial as ordinary name words since #404, so the prefix-only
        middle name "de la" is no longer an example of the dropping.
        """
        def group_initials(names: list[str],
                            firstname: bool = False) -> list[str]:
            got = [i for i in (self._process_initial(n, firstname)
                                for n in names if n) if i]
            words = [w for n in names if n for w in n.split()]
            if got or not words or not all(self._is_particle(w)
                                           for w in words):
                return got
            # rules.md#R3: "except the particles of a part whose every
            # word is one, which are not acting as particles there"
            # -- nothing survived
            # the filter, so the whole group is particles. The
            # facade's twin of the core's
            # UNJOINED_TAG. NOT pinned against it by the case runners,
            # which compare the seven role fields only (Case carries
            # no initials column); the covering test is
            # tests/test_initials.py::test_initials_middle_name_all_prefixes,
            # and since #484 the differential compares initials() on
            # both surfaces for names whose roles agree. _split_last
            # already applies the same guard to the base, which is why
            # last_base was never empty here.
            return [w[0] for w in words]
        return (group_initials(self.first_list, True),
                group_initials(self.middle_list),
                group_initials(self.last_list))

    def initials_list(self) -> list[str]:
        first, middle, last = self._initials_lists()
        return first + middle + last

    def initials(self) -> str:
        first, middle, last = self._initials_lists()
        joiner = self.initials_delimiter + self.initials_separator

        def group(items: list[str]) -> str:
            return joiner.join(items) + self.initials_delimiter \
                if items else ""

        # A fully-empty result renders as "" -- the v1 fallback to
        # C.empty_attribute_default (which may be None) is dropped per
        # #255.
        _s = self.initials_format.format(
            first=group(first), middle=group(middle), last=group(last))
        return self.collapse_whitespace(_s)

    # -- comparison -----------------------------------------------------------

    def matches(self, other: str | HumanName) -> bool:
        """Component-wise case-insensitive comparison (v1 parity); a
        str argument is parsed with this instance's resolved parser."""
        if not isinstance(other, (str, HumanName)):
            # pre-check so the error names the facade type a caller
            # actually passed HumanName.matches(), not the core
            # ParsedName it delegates to below
            raise TypeError(
                f"matches() takes a str or HumanName, got {other!r}")
        target = other._parsed if isinstance(other, HumanName) else other
        return self._parsed.matches(target, parser=self._resolve())

    def comparison_key(self) -> tuple[str, ...]:
        """One casefolded component per field in canonical order -- the
        v1 replacement for ==/hash (#223); see ParsedName.comparison_key."""
        return self._parsed.comparison_key()

    # -- dunders ------------------------------------------------------------

    def collapse_whitespace(self, string: str) -> str:
        # v1 parser.py:976 verbatim, over _render's regexes (the #254
        # collapse owns them; this public method keeps v1's narrower
        # two-step contract for initials() and direct callers)
        string = _render._SPACES.sub(" ", string.strip())
        if string and _render._COMMA_CHAR.fullmatch(string[-1]):
            string = string[:-1]
        return string

    def __str__(self) -> str:
        if self.string_format is not None:
            rendered = self.string_format.format(
                **{k: v or "" for k, v in self.as_dict().items()})
            # the full #254 collapse is _render._collapse -- one owner
            # for the cleanup chain the v1 __str__ spelled inline
            return _render._collapse(rendered)
        return " ".join(self)

    def __repr__(self) -> str:
        attrs = (
            f"    title: {self.title or ''!r}\n"
            f"    first: {self.first or ''!r}\n"
            f"    middle: {self.middle or ''!r}\n"
            f"    last: {self.last or ''!r}\n"
            f"    suffix: {self.suffix or ''!r}\n"
            f"    nickname: {self.nickname or ''!r}\n"
            f"    maiden: {self.maiden or ''!r}"
        )
        return f"<{self.__class__.__name__} : [\n{attrs}\n]>"

    def __iter__(self) -> Iterator[str]:
        return (value for member in _MEMBERS
                if (value := getattr(self, member)))

    def __len__(self) -> int:
        return sum(1 for member in _MEMBERS if getattr(self, member))

    def __getitem__(self, key: str) -> str:
        if isinstance(key, slice):
            raise TypeError(
                "slicing a HumanName was removed in 2.0 (#258); access "
                "the named attributes instead"
            )
        # Role is a StrEnum, so Role members (and the plain 'given'/
        # 'family' strings) reach here too -- translate to the v1
        # spelling the facade actually exposes as attributes.
        return getattr(self, _V1_SPELLING.get(key, key))

    def __setattr__(self, name: str, value: object) -> None:
        # "given"/"family" are the 2.0 spellings of first/last; the
        # facade has no such attributes, so plain assignment creates a
        # stray instance attribute while the parse (and .first/.last)
        # keeps the old value -- a silently forked name. Warn but
        # still set: ad-hoc attribute stashing is a legal v1 pattern,
        # so any code that worked keeps working. Only these two names
        # warn -- the other five 2.0 field names are real properties
        # whose setters work, and Role members reach here as their
        # string values (StrEnum).
        if name in _V1_SPELLING:
            warnings.warn(
                f"assigning HumanName.{name} creates an inert attribute; "
                f"the parse is unchanged -- use .{_V1_SPELLING[name]} "
                f"(the v1 spelling) to update the name",
                UserWarning, stacklevel=2)
        super().__setattr__(name, value)

    def as_dict(self, include_empty: bool = True) -> dict[str, str]:
        """The seven v1-named components as a dict; include_empty=False
        drops empty fields."""
        d = {member: getattr(self, member) for member in _MEMBERS}
        if include_empty:
            return d
        return {k: v for k, v in d.items() if v}

    # -- pickle (v1-shaped state; one path for 1.4 and 2.x blobs) -----------

    def __getstate__(self) -> dict[str, Any]:
        # The emitted key set matches v1.4's pickle shape (minus
        # encoding/_had_comma/_derived_*, which are v1-internal and
        # ignored on read), so one __setstate__ path serves both eras.
        state: dict[str, Any] = {
            "_full_name": self._full_name,
            "original": self.original,
            "C": None if self._C is CONSTANTS else self._C,
            "string_format": self.string_format,
            "initials_format": self.initials_format,
            "initials_delimiter": self.initials_delimiter,
            "initials_separator": self.initials_separator,
            "suffix_delimiter": self.suffix_delimiter,
        }
        for member in _MEMBERS:
            state[f"{member}_list"] = getattr(self, f"{member}_list")
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        c = state.get("C")
        self._C = CONSTANTS if c is None else c
        self._snapshot_gen = -1
        defaults = self._C._snapshot()[2]
        self._string_format = state.get("string_format",
                                        defaults.string_format)
        self._initials_format = state.get("initials_format",
                                          defaults.initials_format)
        self._initials_delimiter = state.get("initials_delimiter",
                                             defaults.initials_delimiter)
        self._initials_separator = state.get("initials_separator",
                                             defaults.initials_separator)
        self._suffix_delimiter = state.get("suffix_delimiter",
                                           defaults.suffix_delimiter)
        self._full_name = state.get("_full_name", "")
        # Components come back exactly as pickled
        # (mechanisms.md#FACADE-CONTRACT): synthetic
        # tokens, never a re-parse. Build them per *_list ENTRY rather
        # than from one joined string -- an entry may hold several words
        # ("Ph. D.", "Q.C. M.P."), and re-splitting the joined string on
        # whitespace would promote each word to its own entry, which the
        # suffix view then renders comma-separated ("Ph., D."). Marking
        # continuation words "joined" is the inverse of _list_for's heal,
        # so list -> pickle -> list is the identity v1 gave us.
        tokens: list[Token] = []
        for member in _MEMBERS:
            role = Role(_V2_FIELD.get(member, member))
            entries = state.get(f"{member}_list") or []
            # Everything here is iterable but shreds differently: a str
            # yields characters ("John" -> first "J o h n"), a Mapping
            # yields keys only, bytes yields ints. v1 stored lists, so
            # this only guards foreign or hand-built state -- but it
            # names the field at the load site instead of failing
            # opaquely later, or not at all.
            if isinstance(entries, (str, bytes, Mapping)):
                raise TypeError(
                    f"{member}_list must be a list of strings, not "
                    f"{type(entries).__name__} ({entries!r}); this "
                    f"pickle was not written by nameparser"
                )
            for entry in entries:
                if not isinstance(entry, str):
                    raise TypeError(
                        f"{member}_list entries must be strings, got "
                        f"{entry!r}; this pickle was not written by "
                        f"nameparser"
                    )
                for position, word in enumerate(entry.split()):
                    # UNCLASSIFIED_TAG for the same reason replace()
                    # stamps it: a pickle carries the *_list STRINGS
                    # and no tags, so nothing here was read by a parse
                    # and case repair must ask the vocabulary rather
                    # than read an absent conjunction tag. Without it a
                    # restored "juan ortega y gasset" repairs to
                    # "Ortega Y Gasset", which is neither v1's answer
                    # nor the same name's unpickled one.
                    tags = {UNCLASSIFIED_TAG}
                    if position:
                        tags.add("joined")
                    tokens.append(Token(word, None, role, frozenset(tags)))
        self._parsed = ParsedName(
            original=str(state.get("original", "")), tokens=tuple(tokens))
