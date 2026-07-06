"""
The :py:mod:`nameparser.config` module manages the configuration of the
nameparser. 

A module-level instance of :py:class:`~nameparser.config.Constants` is created
and used by default for all HumanName instances. You can adjust the entire module's
configuration by importing this instance and changing it.

::

    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.titles.remove('hon').add('chemistry','dean') # doctest: +SKIP

You can also adjust the configuration of individual instances by passing
``None`` as the second argument upon instantiation.

::

    >>> from nameparser import HumanName
    >>> hn = HumanName("Dean Robert Johns", None)
    >>> hn.C.titles.add('dean') # doctest: +SKIP
    >>> hn.parse_full_name() # need to run this again after config changes

**Potential Gotcha**: If you do not pass ``None`` (or your own
:py:class:`Constants` instance) as the second argument, ``hn.C`` will be a
reference to the module config, possibly yielding unexpected results. See
`Customizing the Parser <customize.html>`_.
"""
import re
import sys
import warnings
from collections.abc import Callable, Iterable, Iterator, Mapping, Set
from typing import Any, TypeVar, overload

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from nameparser.util import lc
from nameparser.config.prefixes import PREFIXES, NON_FIRST_NAME_PREFIXES
from nameparser.config.bound_first_names import BOUND_FIRST_NAMES
from nameparser.config.capitalization import CAPITALIZATION_EXCEPTIONS
from nameparser.config.conjunctions import CONJUNCTIONS
from nameparser.config.suffixes import SUFFIX_ACRONYMS
from nameparser.config.suffixes import SUFFIX_NOT_ACRONYMS
from nameparser.config.suffixes import SUFFIX_ACRONYMS_AMBIGUOUS
from nameparser.config.titles import TITLES
from nameparser.config.titles import FIRST_NAME_TITLES
from nameparser.config.regexes import EMPTY_REGEX, REGEXES

DEFAULT_ENCODING = 'UTF-8'


def _reject_bare_str_or_bytes(value: object, expected: str) -> None:
    # A bare string is an iterable of its characters, so e.g. set('dr') or
    # dict('ab') would silently shred it, and bytes iterates to ints, which
    # can never match parsed str tokens -- shared by SetManager's constructor/
    # operands (#238) and TupleManager's constructor (#242).
    if isinstance(value, bytes):
        raise TypeError(
            f"expected {expected}, got a single bytes; "
            f"decode it first: [{value!r}.decode()]"
        )
    if isinstance(value, str):
        raise TypeError(
            f"expected {expected}, got a single str; wrap it in a list: [{value!r}]"
        )


class SetManager(Set):
    '''
    Easily add and remove config variables per module or instance. Subclass of
    ``collections.abc.Set``.

    Special functionality beyond that provided by set() is to normalize
    constants for comparison (lowercase, leading/trailing periods stripped)
    when they are add()ed and remove()d, and to allow passing multiple
    string arguments to the :py:func:`add()` and :py:func:`remove()`
    methods. The constructor and the set operators apply the same
    normalization to their elements and operands, so every entry is stored
    in the form the parser's lookups expect, and they reject a bare string
    with ``TypeError``, since e.g. ``set('dr')`` would silently build a set
    of single characters.

    '''

    _on_change: Callable[[], None] | None

    @classmethod
    def _normalized_elements(cls, elements: Iterable[str]) -> set[str]:
        # a SetManager's elements were validated and normalized when it was
        # built, so copy them instead of re-validating — this is what keeps
        # chained unions (suffixes_prefixes_titles) and default Constants()
        # construction from re-checking ~1,400 entries per step
        if isinstance(elements, SetManager):
            return set(elements.elements)
        _reject_bare_str_or_bytes(elements, "an iterable of strings")
        # apply the same lc() normalization (lowercase, strip leading/
        # trailing periods) that add() applies, and reject junk elements:
        # lc() on bytes or int crashes without naming the culprit, and
        # lc(None) silently transmutes to ''. Divergence from add() is
        # deliberate: add_with_encoding() decodes bytes for back-compat,
        # bulk boundaries stay strict.
        normalized = set()
        for s in elements:
            if isinstance(s, bytes):
                raise TypeError(
                    f"expected str elements, got bytes; decode it first: {s!r}.decode()"
                )
            if not isinstance(s, str):
                raise TypeError(
                    f"expected str elements, got {type(s).__name__}: {s!r}"
                )
            normalized.add(lc(s))
        return normalized

    @classmethod
    def _from_normalized(cls, elements: set[str]) -> 'SetManager':
        # Private fast constructor: bypasses __init__ so results aren't
        # re-validated element by element. This performs NO validation or
        # normalization of `elements` -- the caller is fully responsible
        # for guaranteeing every element is already a str that has passed
        # through lc(). Only call this with a set built from other
        # SetManagers' already-normalized .elements (operator results,
        # prebuilt default copies); passing anything else silently defeats
        # the constructor's #238 guarantees with no error raised here.
        obj = cls.__new__(cls)
        obj.elements = elements
        obj._on_change = None
        return obj

    def __init__(self, elements: Iterable[str]) -> None:
        self.elements = self._normalized_elements(elements)
        # Optional invalidation hook, wired by an owning Constants so that
        # in-place add()/remove() can clear its cached suffixes_prefixes_titles
        # union. None when the manager is used standalone.
        self._on_change = None

    def __call__(self) -> Set[str]:
        """
        .. deprecated:: 1.3.0
            Removed in 2.0 (see issue #243). Returns the raw underlying set,
            so mutating it bypasses normalization and cache invalidation;
            iterate the manager or copy with ``set(manager)`` instead.
        """
        warnings.warn(
            "Calling a SetManager to get the raw underlying set is "
            "deprecated and will be removed in 2.0; iterate the manager or "
            "copy it with set(manager) instead. See "
            "https://github.com/derek73/python-nameparser/issues/243",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.elements

    def __repr__(self) -> str:
        # Sorted so repr is stable across runs -- set() iteration order
        # depends on string hash randomization, which varies per process.
        elements = "{" + ", ".join(repr(e) for e in sorted(self.elements)) + "}" if self.elements else "set()"
        return f"SetManager({elements})"  # used for docs

    def __iter__(self) -> Iterator[str]:
        return iter(self.elements)

    def __contains__(self, value: object) -> bool:
        # add()/remove()/the constructor/the operators all normalize (lowercase,
        # strip leading/trailing periods) before comparing; without the same
        # normalization here, `'Dr.' in c.titles` returns False even though
        # every other operation on the same value succeeds (#244). The parser's
        # own lookups (e.g. `piece.lower() in self.C.conjunctions`) already pass
        # an lc()-normalized value, which is the hot path during parsing, so
        # try the raw value first and only pay for lc() on a miss.
        if value in self.elements:
            return True
        return isinstance(value, str) and lc(value) in self.elements

    def __len__(self) -> int:
        return len(self.elements)

    # The ABC mixins compare raw operand elements against stored (normalized)
    # ones, and their __or__/__and__ accept a bare str as Iterable, so every
    # operand is validated and normalized here. Results are built with plain
    # set ops on already-normalized elements instead of delegating to the
    # mixins, whose _from_iterable would re-validate the whole result
    # through __init__.
    #
    # the runtime ABC accepts any Iterable operand, so annotate honestly and
    # ignore typeshed's narrower AbstractSet declarations
    def __or__(self, other: Iterable[str]) -> 'SetManager':  # type: ignore[override]
        return self._from_normalized(self.elements | self._normalized_elements(other))

    __ror__ = __or__

    def __and__(self, other: Iterable[str]) -> 'SetManager':  # type: ignore[override]
        return self._from_normalized(self.elements & self._normalized_elements(other))

    __rand__ = __and__

    def __sub__(self, other: Iterable[str]) -> 'SetManager':  # type: ignore[override]
        return self._from_normalized(self.elements - self._normalized_elements(other))

    def __rsub__(self, other: Iterable[str]) -> 'SetManager':
        return self._from_normalized(self._normalized_elements(other) - self.elements)

    def __xor__(self, other: Iterable[str]) -> 'SetManager':  # type: ignore[override]
        return self._from_normalized(self.elements ^ self._normalized_elements(other))

    __rxor__ = __xor__

    def _add_normalized(self, s: str | bytes, encoding: str | None, *, stacklevel: int) -> None:
        # Shared by add() and add_with_encoding() so each can call it
        # directly with a stacklevel that attributes the warning to *its own*
        # caller -- add() delegating to add_with_encoding() would otherwise
        # add a frame and misattribute the warning to this module.
        stdin_encoding = None
        if sys.stdin:
            stdin_encoding = sys.stdin.encoding
        encoding = encoding or stdin_encoding or DEFAULT_ENCODING
        if isinstance(s, bytes):
            warnings.warn(
                "Passing bytes to SetManager.add()/add_with_encoding() is "
                "deprecated and will raise TypeError in 2.0; decode it "
                "first, e.g. value.decode('utf-8'). See "
                "https://github.com/derek73/python-nameparser/issues/245",
                DeprecationWarning,
                stacklevel=stacklevel,
            )
            s = s.decode(encoding)
        normalized = lc(s)
        if normalized not in self.elements:
            self.elements.add(normalized)
            if self._on_change:
                self._on_change()

    def add_with_encoding(self, s: str | bytes, encoding: str | None = None) -> None:
        """
        Add the lowercased, leading/trailing-periods-stripped version of the string to the set. Pass an
        explicit `encoding` parameter to specify the encoding of binary strings that
        are not DEFAULT_ENCODING (UTF-8).

        .. deprecated:: 1.3.0
            ``bytes`` arguments will raise ``TypeError`` in 2.0 (see issue
            #245); decode before adding.
        """
        self._add_normalized(s, encoding, stacklevel=3)

    def add(self, *strings: str) -> Self:
        """
        Add the lowercased, leading/trailing-periods-stripped version of the string arguments to the set.
        Returns ``self`` for chaining.

        .. deprecated:: 1.3.0
            ``bytes`` arguments will raise ``TypeError`` in 2.0 (see issue
            #245); decode before adding.
        """
        for s in strings:
            self._add_normalized(s, None, stacklevel=3)

        return self

    def remove(self, *strings: str) -> Self:
        """
        Remove the lower case and no-period version of the string arguments from the set.
        Returns ``self`` for chaining.

        .. deprecated:: 1.3.0
            Removing a *missing* member currently does nothing but will
            raise ``KeyError`` in 2.0, matching ``set.remove`` (see issue
            #243); use :py:func:`discard` to ignore missing members.
        """
        changed = False
        for s in strings:
            if (lower := lc(s)) in self.elements:
                self.elements.remove(lower)
                changed = True
            else:
                warnings.warn(
                    "SetManager.remove() of a missing member currently does "
                    "nothing, but will raise KeyError in 2.0; use discard() "
                    "to ignore missing members. See "
                    "https://github.com/derek73/python-nameparser/issues/243",
                    DeprecationWarning,
                    stacklevel=2,
                )
        if changed and self._on_change:
            self._on_change()
        return self

    def discard(self, *strings: str) -> Self:
        """
        Remove the lower case and no-period version of the string arguments
        from the set if present; missing members are ignored, like
        ``set.discard``. Returns ``self`` for chaining.
        """
        changed = False
        for s in strings:
            if (lower := lc(s)) in self.elements:
                self.elements.remove(lower)
                changed = True
        if changed and self._on_change:
            self._on_change()
        return self

    def clear(self) -> Self:
        """Remove all entries from the set. Returns ``self`` for chaining."""
        if self.elements:
            self.elements.clear()
            if self._on_change:
                self._on_change()
        return self


T = TypeVar('T')


def _is_dunder(attr: str) -> bool:
    # Dunder names are Python's protocol probes (copy looks up __deepcopy__,
    # inspect.unwrap looks up __wrapped__, typing's GenericAlias.__call__ sets
    # __orig_class__, ...), never config keys. The TupleManager attribute hooks
    # all route dunders to normal object-attribute behavior so those probes
    # work instead of being mistaken for dict entries.
    return attr.startswith("__") and attr.endswith("__")


# The default config sets are module constants that never change, so
# validate and normalize each one exactly once at import. Constants()
# copies these via _normalized_elements' SetManager fast path instead of
# re-checking ~1,400 elements per construction — a cost that otherwise
# repeats on the per-instance-config path, HumanName(constants=None).
#
# This snapshot is taken once, at import time: mutating a raw constant
# (e.g. `TITLES.add('x')`) after import is *not* picked up by Constants()
# built afterward, since the identity check in Constants.__init__ reuses
# this frozen SetManager rather than re-wrapping the (now-changed) raw
# set. That's a behavior change from re-wrapping every time, but the
# documented customization path mutates the SetManager wrapper on a
# Constants instance (``CONSTANTS.titles.add(...)``), not the raw
# constant, so this only affects an unsupported/undocumented pattern.
_DEFAULT_PREFIXES = SetManager(PREFIXES)
_DEFAULT_SUFFIX_ACRONYMS = SetManager(SUFFIX_ACRONYMS)
_DEFAULT_SUFFIX_NOT_ACRONYMS = SetManager(SUFFIX_NOT_ACRONYMS)
_DEFAULT_SUFFIX_ACRONYMS_AMBIGUOUS = SetManager(SUFFIX_ACRONYMS_AMBIGUOUS)
_DEFAULT_TITLES = SetManager(TITLES)
_DEFAULT_FIRST_NAME_TITLES = SetManager(FIRST_NAME_TITLES)
_DEFAULT_CONJUNCTIONS = SetManager(CONJUNCTIONS)
_DEFAULT_BOUND_FIRST_NAMES = SetManager(BOUND_FIRST_NAMES)
_DEFAULT_NON_FIRST_NAME_PREFIXES = SetManager(NON_FIRST_NAME_PREFIXES)


class TupleManager(dict[str, T]):
    '''
    A dictionary with dot.notation access. Subclass of ``dict``. Wraps the
    mapping config constants (``capitalization_exceptions``, ``regexes``, and
    the nickname/maiden delimiter buckets). The name is historical: before
    1.3.0 these constants were tuples of pairs.
    '''

    def __init__(
        self,
        arg: Mapping[str, T] | Iterable[tuple[str, T]] = (),
        **kwargs: T,
    ) -> None:
        # dict.__init__ accepts a bare str/bytes as an iterable-of-pairs
        # argument (each character iterates further, and dict() only
        # complains once it hits a "pair" of the wrong length) and accepts an
        # iterable of 2-character strings as if each one were a (key, value)
        # pair, silently shredding it -- mirrors SetManager's guard against
        # the same class of mistake (#238), applied to the mapping
        # constructor's own failure modes (#242).
        _reject_bare_str_or_bytes(arg, "a mapping or iterable of (key, value) pairs")
        if not isinstance(arg, Mapping):
            checked = []
            for item in arg:
                if isinstance(item, (str, bytes)):
                    raise TypeError(
                        "expected (key, value) pairs, got a "
                        f"{'bytes' if isinstance(item, bytes) else 'str'} "
                        f"element {item!r}; a 2-character string silently "
                        "splits into a key and a value"
                    )
                checked.append(item)
            arg = checked
        super().__init__(arg, **kwargs)

    def __getattr__(self, attr: str) -> T | None:
        # Otherwise the dict default (None) is mistaken for a real protocol hook.
        if _is_dunder(attr):
            raise AttributeError(attr)
        return self.get(attr)

    def __setattr__(self, attr: str, value: T) -> None:
        # Fall back to normal object attribute storage for dunders; everything
        # else keeps the dict-backed dot-notation behavior this class exists
        # for. Concretely: constructing a subscripted generic, e.g.
        # TupleManager[re.Pattern[str] | str](...), makes typing's
        # GenericAlias.__call__ set `__orig_class__` on the new instance right
        # after __init__ returns. Without this guard that assignment falls
        # through to dict.__setitem__ and silently inserts a bogus
        # '__orig_class__' entry into the dict itself, corrupting
        # .values()/iteration.
        if _is_dunder(attr):
            object.__setattr__(self, attr, value)
        else:
            self[attr] = value

    def __delattr__(self, attr: str) -> None:
        if _is_dunder(attr):
            object.__delattr__(self, attr)
        else:
            del self[attr]

    def __getstate__(self) -> Mapping[str, T]:
        return dict(self)

    def __setstate__(self, state: Mapping[str, T]) -> None:
        self.update(state)

    def __reduce__(self) -> tuple[type, tuple[()], Mapping[str, T]]:
        # Use type(self), not TupleManager, so subclasses such as
        # RegexTupleManager survive a pickle round-trip instead of being
        # downgraded to a plain TupleManager (which loses the EMPTY_REGEX
        # default for unknown keys).
        return (type(self), (), self.__getstate__())


class RegexTupleManager(TupleManager[re.Pattern[str]]):
    def __getattr__(self, attr: str) -> re.Pattern[str]:
        # Otherwise EMPTY_REGEX is returned for a dunder probe; copy.deepcopy
        # then tries to call the returned re.Pattern and raises TypeError.
        if _is_dunder(attr):
            raise AttributeError(attr)
        return self.get(attr, EMPTY_REGEX)


class _SetManagerAttribute:
    """Descriptor enforcing ``isinstance(value, SetManager)`` on assignment.

    Backs the five plain SetManager attributes (``first_name_titles``,
    ``conjunctions``, ``bound_first_names``, ``non_first_name_prefixes``,
    ``suffix_acronyms_ambiguous``). Without this guard, e.g.
    ``c.conjunctions = 'and'`` is accepted silently, and every later
    ``piece.lower() in self.C.conjunctions`` becomes a substring test against
    the plain str instead of a set membership test (#241).

    ``_CachedUnionMember`` subclasses this to add ``_pst`` cache invalidation
    for the four attributes whose union ``Constants`` caches.
    """

    _attr: str

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr = '_' + name

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> '_SetManagerAttribute': ...
    @overload
    def __get__(self, obj: 'Constants', objtype: type | None = None) -> SetManager: ...

    def __get__(self, obj: 'Constants | None', objtype: type | None = None) -> 'SetManager | _SetManagerAttribute':
        if obj is None:
            return self
        return getattr(obj, self._attr)

    def _validate(self, value: SetManager) -> None:
        if not isinstance(value, SetManager):
            raise TypeError(
                f"Expected a SetManager instance, got {type(value).__name__!r}. "
                "Wrap your iterable: SetManager(['mr', 'ms'])"
            )

    def __set__(self, obj: 'Constants', value: SetManager) -> None:
        self._validate(value)
        setattr(obj, self._attr, value)


class _CachedUnionMember(_SetManagerAttribute):
    """Descriptor for the four ``SetManager`` attributes whose union ``Constants``
    caches in ``_pst`` (``prefixes``, ``suffix_acronyms``, ``suffix_not_acronyms``,
    ``titles``).

    Assigning a new manager — or mutating one in place via ``add()`` / ``remove()``
    — invalidates that cache. Keeping the behavior on a descriptor scopes it to
    exactly these attributes, beside their declarations, rather than spreading it
    across a catch-all ``__setattr__`` and a separate attribute-name list.
    """

    def __set__(self, obj: 'Constants', value: SetManager) -> None:
        self._validate(value)
        previous = getattr(obj, self._attr, None)
        if isinstance(previous, SetManager):
            previous._on_change = None  # detach the replaced manager so it no longer invalidates
        value._on_change = obj._invalidate_pst
        obj._invalidate_pst()
        setattr(obj, self._attr, value)


class Constants:
    """
    An instance of this class hold all of the configuration constants for the parser.

    :param set prefixes: 
        :py:attr:`prefixes` wrapped with :py:class:`SetManager`.
    :param set titles: 
        :py:attr:`titles` wrapped with :py:class:`SetManager`.
    :param set first_name_titles: 
        :py:attr:`~titles.FIRST_NAME_TITLES` wrapped with :py:class:`SetManager`.
    :param set suffix_acronyms: 
        :py:attr:`~suffixes.SUFFIX_ACRONYMS`  wrapped with :py:class:`SetManager`.
    :param set suffix_not_acronyms:
        :py:attr:`~suffixes.SUFFIX_NOT_ACRONYMS`  wrapped with :py:class:`SetManager`.
    :param set suffix_acronyms_ambiguous:
        :py:attr:`~suffixes.SUFFIX_ACRONYMS_AMBIGUOUS` wrapped with :py:class:`SetManager`.
    :param set conjunctions:
        :py:attr:`conjunctions`  wrapped with :py:class:`SetManager`.
    :param set bound_first_names:
        :py:attr:`~bound_first_names.BOUND_FIRST_NAMES` wrapped with :py:class:`SetManager`.
    :param set non_first_name_prefixes:
        :py:attr:`~prefixes.NON_FIRST_NAME_PREFIXES` wrapped with :py:class:`SetManager`.
        The subset of prefixes that are never a first name, so a *leading* one
        marks the whole name as a surname. Must stay disjoint from
        ``bound_first_names``.
    :type capitalization_exceptions: dict or iterable of (key, value) tuples
    :param capitalization_exceptions:
        :py:attr:`~capitalization.CAPITALIZATION_EXCEPTIONS` wrapped with :py:class:`TupleManager`.
    :type regexes: dict or iterable of (name, compiled pattern) tuples
    :param regexes:
        :py:attr:`~regexes.REGEXES` wrapped with :py:class:`RegexTupleManager`.

    :py:attr:`nickname_delimiters` and :py:attr:`maiden_delimiters` are not
    constructor arguments -- they're always set in ``__init__`` (see the
    comment there for the string-sentinel-vs-compiled-pattern mechanism) --
    but are documented here since they're the two `Constants` attributes a
    caller is most likely to want to look up: per-bucket
    :py:class:`TupleManager` collections that :py:meth:`~nameparser.parser.HumanName.parse_nicknames`
    consults to route delimited content into ``nickname``/``maiden``. See
    the "Adding Custom Nickname Delimiters" and "Routing to Maiden Name"
    sections of the customization docs.
    """

    prefixes = _CachedUnionMember()
    suffix_acronyms = _CachedUnionMember()
    suffix_not_acronyms = _CachedUnionMember()
    titles = _CachedUnionMember()
    first_name_titles = _SetManagerAttribute()
    conjunctions = _SetManagerAttribute()
    bound_first_names = _SetManagerAttribute()
    non_first_name_prefixes = _SetManagerAttribute()
    suffix_acronyms_ambiguous = _SetManagerAttribute()
    capitalization_exceptions: TupleManager[str]
    regexes: RegexTupleManager
    nickname_delimiters: TupleManager[re.Pattern[str] | str]
    maiden_delimiters: TupleManager[re.Pattern[str] | str]
    _pst: Set[str] | None

    string_format: str | None = "{title} {first} {middle} {last} {suffix} ({nickname})"
    """
    The default string format use for all new `HumanName` instances.
    """

    initials_format = "{first} {middle} {last}"
    """
    The default initials format used for all new `HumanName` instances.
    """

    initials_delimiter = "."
    """
    The default initials delimiter used for all new `HumanName` instances.
    Will be used to add a delimiter between each initial.
    """

    initials_separator = " "
    """
    The default separator placed between consecutive initials within a name
    group (first, middle, or last). Distinct from ``initials_delimiter``,
    which is the trailing character after each individual initial.

    With defaults ``initials_delimiter="."`` and ``initials_separator=" "``,
    ``initials()`` produces ``"J. A. D."``. Setting ``initials_separator=""``
    with ``initials_delimiter="."`` and ``initials_format="{first}{middle}{last}"``
    produces ``"J.A.D."``. With the default ``initials_format``, group-level
    spacing from the template is still applied.
    """

    suffix_delimiter: str | None = None
    """
    If set, an additional delimiter used to split suffix groups after
    comma-splitting. For example, setting ``suffix_delimiter=" - "`` allows
    ``"RN - CRNA"`` to be parsed as two separate suffixes. Default is
    ``None`` (no additional splitting beyond the standard comma split).

    Note: setting this to ``","`` or ``", "`` has no additional effect —
    the full name is already split on bare commas first, and each resulting
    part is stripped of surrounding whitespace before this step runs.

    The delimiter is only applied to parts once they've been identified as
    a suffix group, so it never leaks into a first- or middle-name part. For
    example, in inverted format (``"Last, First, suffix"``) a hyphenated
    given name like ``"Doe, Mary - Kate, RN"`` with ``suffix_delimiter=" - "``
    does not get mistaken for a suffix split.
    """

    empty_attribute_default = ''
    """
    Default return value for empty attributes.

    .. doctest::

        >>> from nameparser.config import CONSTANTS
        >>> CONSTANTS.empty_attribute_default = None
        >>> name = HumanName("John Doe")
        >>> print(name.title)
        None
        >>> name.first
        'John'
        >>> CONSTANTS.empty_attribute_default = ''

    """

    capitalize_name = False
    """
    If set, applies :py:meth:`~nameparser.parser.HumanName.capitalize` to
    :py:class:`~nameparser.parser.HumanName` instance.

    .. doctest::

        >>> from nameparser.config import CONSTANTS
        >>> CONSTANTS.capitalize_name = True
        >>> name = HumanName("bob v. de la macdole-eisenhower phd")
        >>> str(name)
        'Bob V. de la MacDole-Eisenhower Ph.D.'
        >>> CONSTANTS.capitalize_name = False

    """

    force_mixed_case_capitalization = False
    """
    If set, forces the capitalization of mixed case strings when
    :py:meth:`~nameparser.parser.HumanName.capitalize` is called.

    .. doctest::

        >>> from nameparser.config import CONSTANTS
        >>> CONSTANTS.force_mixed_case_capitalization = True
        >>> name = HumanName('Shirley Maclaine')
        >>> name.capitalize()
        >>> str(name)
        'Shirley MacLaine'
        >>> CONSTANTS.force_mixed_case_capitalization = False

    """

    patronymic_name_order = False
    """
    If set, detects names in Russian formal order (``Surname GivenName Patronymic``)
    by recognizing a trailing East-Slavic patronymic suffix on the last token, and
    rotates the three name parts so that ``first``/``middle``/``last`` map to
    given name / patronymic / surname respectively.  Detection requires exactly one
    token in each of first, middle, and last; names with multi-part given names or
    multiple middle names are left unchanged.

    Also detects reversed-order Azerbaijani/Central-Asian Turkic patronymics
    (``Surname GivenName PatronymicRoot Marker``, e.g. ``oglu``/``qizi``), a
    structurally different, standalone-marker-word patronymic family. Detection
    requires exactly one token in each of first and last, exactly two tokens in
    middle, and the last token a recognised Turkic marker.

    Opt-in because a Western person whose surname happens to end in a patronymic
    suffix (e.g. ``"David Michael Abramovich"``) will be reordered incorrectly
    when the flag is on. Enable only when your data is predominantly Russian
    formal-order names.

    For per-instance control without a shared ``Constants``, pass a dedicated
    instance: ``HumanName("...", constants=Constants(patronymic_name_order=True))``.

    .. doctest::

        >>> from nameparser import HumanName
        >>> from nameparser.config import Constants
        >>> C = Constants(patronymic_name_order=True)
        >>> hn = HumanName("Ivanov Ivan Ivanovich", constants=C)
        >>> hn.first, hn.middle, hn.last
        ('Ivan', 'Ivanovich', 'Ivanov')
        >>> hn2 = HumanName("Aliyev Vusal Said oglu", constants=C)
        >>> hn2.first, hn2.middle, hn2.last
        ('Vusal', 'Said oglu', 'Aliyev')

    """

    middle_name_as_last = False
    """
    If set, folds middle names into the last name: ``middle_list`` is prepended
    to ``last_list`` and ``middle_list`` is cleared, so ``.last`` becomes what
    ``.surnames`` already was and ``.middle`` becomes empty. Useful for naming
    systems with no middle-name concept, where everything after the given name
    is lineage/family (e.g. Arabic patronymic chaining: given + father +
    grandfather + family).

    The fold is uniform across both no-comma and comma ("Last, First Middle")
    input, so the two written forms of a name converge on the same result.

    For per-instance control without a shared ``Constants``, pass a dedicated
    instance: ``HumanName("...", constants=Constants(middle_name_as_last=True))``.

    .. doctest::

        >>> from nameparser import HumanName
        >>> from nameparser.config import Constants
        >>> C = Constants(middle_name_as_last=True)
        >>> hn = HumanName("Mohamad Ahmad Ali Hassan", constants=C)
        >>> hn.first, hn.middle, hn.last
        ('Mohamad', '', 'Ahmad Ali Hassan')

    """

    def __init__(self,
                 prefixes: Iterable[str] = PREFIXES,
                 suffix_acronyms: Iterable[str] = SUFFIX_ACRONYMS,
                 suffix_not_acronyms: Iterable[str] = SUFFIX_NOT_ACRONYMS,
                 suffix_acronyms_ambiguous: Iterable[str] = SUFFIX_ACRONYMS_AMBIGUOUS,
                 titles: Iterable[str] = TITLES,
                 first_name_titles: Iterable[str] = FIRST_NAME_TITLES,
                 conjunctions: Iterable[str] = CONJUNCTIONS,
                 bound_first_names: Iterable[str] = BOUND_FIRST_NAMES,
                 non_first_name_prefixes: Iterable[str] = NON_FIRST_NAME_PREFIXES,
                 capitalization_exceptions: Mapping[str, str] | Iterable[tuple[str, str]] = CAPITALIZATION_EXCEPTIONS,
                 regexes: Mapping[str, re.Pattern[str]] | Iterable[tuple[str, re.Pattern[str]]] = REGEXES,
                 patronymic_name_order: bool = False,
                 middle_name_as_last: bool = False,
                 ) -> None:
        # These four descriptor assignments call _CachedUnionMember.__set__, which
        # calls _invalidate_pst() and establishes self._pst. They must come before
        # any read of suffixes_prefixes_titles.
        # untouched defaults (identity check) copy the prebuilt module-level
        # managers instead of re-validating the raw constants element by
        # element; user-supplied iterables still get the full check
        self.prefixes = SetManager(_DEFAULT_PREFIXES if prefixes is PREFIXES else prefixes)
        self.suffix_acronyms = SetManager(_DEFAULT_SUFFIX_ACRONYMS if suffix_acronyms is SUFFIX_ACRONYMS else suffix_acronyms)
        self.suffix_not_acronyms = SetManager(_DEFAULT_SUFFIX_NOT_ACRONYMS if suffix_not_acronyms is SUFFIX_NOT_ACRONYMS else suffix_not_acronyms)
        self.titles = SetManager(_DEFAULT_TITLES if titles is TITLES else titles)
        self.first_name_titles = SetManager(_DEFAULT_FIRST_NAME_TITLES if first_name_titles is FIRST_NAME_TITLES else first_name_titles)
        self.conjunctions = SetManager(_DEFAULT_CONJUNCTIONS if conjunctions is CONJUNCTIONS else conjunctions)
        self.bound_first_names = SetManager(_DEFAULT_BOUND_FIRST_NAMES if bound_first_names is BOUND_FIRST_NAMES else bound_first_names)
        self.non_first_name_prefixes = SetManager(_DEFAULT_NON_FIRST_NAME_PREFIXES if non_first_name_prefixes is NON_FIRST_NAME_PREFIXES else non_first_name_prefixes)
        self.suffix_acronyms_ambiguous = SetManager(_DEFAULT_SUFFIX_ACRONYMS_AMBIGUOUS if suffix_acronyms_ambiguous is SUFFIX_ACRONYMS_AMBIGUOUS else suffix_acronyms_ambiguous)
        self.capitalization_exceptions = TupleManager(capitalization_exceptions)
        self.regexes = RegexTupleManager(regexes)
        # Per-bucket delimiter collections that parse_nicknames() consults to
        # route delimited content into nickname_list / maiden_list. Each value
        # is either a compiled re.Pattern (a custom delimiter a caller adds --
        # the old extra_nickname_delimiters use case, see issue #112) or the
        # string name of a self.regexes entry to resolve live at parse time.
        # The latter is how the three built-ins (quoted_word, double_quotes,
        # parenthesis) stay linked to self.regexes, so overriding e.g.
        # self.regexes.parenthesis keeps affecting nickname/maiden parsing
        # exactly as before. Move a key between the two dicts
        # (`maiden_delimiters['parenthesis'] =
        # nickname_delimiters.pop('parenthesis')`) to change which bucket it
        # routes to without losing that live link. maiden_delimiters starts
        # empty -- maiden is off until a caller routes a delimiter to it.
        # See issue #22.
        # Only seed a built-in name if it's actually present in self.regexes --
        # a caller who overrides regexes with a minimal custom set (dropping
        # e.g. "parenthesis" entirely) shouldn't end up with a dangling
        # string sentinel that parse_nicknames() would treat as a mistake.
        # See parse_nicknames()'s fail-loud check on an unresolvable sentinel.
        self.nickname_delimiters = TupleManager[re.Pattern[str] | str]({
            name: name for name in ('quoted_word', 'double_quotes', 'parenthesis')
            if name in self.regexes
        })
        self.maiden_delimiters = TupleManager[re.Pattern[str] | str]()
        self.patronymic_name_order = patronymic_name_order
        self.middle_name_as_last = middle_name_as_last

    def _invalidate_pst(self) -> None:
        self._pst = None

    @property
    def suffixes_prefixes_titles(self) -> Set[str]:
        if self._pst is None:
            self._pst = self.prefixes | self.suffix_acronyms | self.suffix_not_acronyms | self.titles
        return self._pst

    _repr_collection_attrs = (
        'prefixes', 'suffix_acronyms', 'suffix_not_acronyms', 'titles',
        'first_name_titles', 'conjunctions', 'bound_first_names',
        'non_first_name_prefixes', 'suffix_acronyms_ambiguous',
    )
    _repr_scalar_attrs = (
        'string_format', 'initials_format', 'initials_delimiter',
        'initials_separator', 'suffix_delimiter', 'empty_attribute_default',
        'capitalize_name', 'force_mixed_case_capitalization',
        'patronymic_name_order', 'middle_name_as_last',
    )

    def __repr__(self) -> str:
        # Collections (some with hundreds of entries, e.g. titles/prefixes)
        # are summarized as counts rather than dumped in full. Scalars are
        # only shown when they differ from the class default, so a plain
        # Constants() reads as just the collection sizes.
        lines = [f"    {name}: {len(getattr(self, name))}" for name in self._repr_collection_attrs]
        lines += [
            f"    {name}: {value!r}" for name in self._repr_scalar_attrs
            if (value := getattr(self, name)) != getattr(type(self), name)
        ]
        return "<Constants : [\n" + "\n".join(lines) + "\n]>"

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        # Restore each saved attribute directly. The previous implementation
        # passed the whole state dict to __init__ as the ``prefixes`` argument,
        # which silently reverted every collection to its module default on
        # unpickling.
        self._pst = None
        for name, value in state.items():
            # Migration shim: pickles written before this fix (1.3.0 and earlier,
            # including 1.2.1) used a dir() sweep for __getstate__, so their state
            # carries the read-only ``suffixes_prefixes_titles`` property. Skip any
            # such computed property rather than raising AttributeError on its
            # missing setter; the real config is restored from the other keys. We
            # don't promise to read pre-fix blobs forever — this only smooths
            # migration for anyone persisting them, and can be dropped a release
            # or two after 1.3.0 once they've re-pickled.
            if isinstance(getattr(type(self), name, None), property):
                continue
            setattr(self, name, value)
        # Verify each descriptor-backed attr was restored. Without this, a missing
        # key surfaces later as AttributeError: 'Constants' object has no attribute
        # '_prefixes' — the private mangled name, not the public one, making it
        # very hard to diagnose.
        for attr in (n for n, v in vars(type(self)).items() if isinstance(v, _SetManagerAttribute)):
            if not hasattr(self, '_' + attr):
                raise ValueError(
                    f"Pickle state is missing required field {attr!r}. "
                    "The state blob may be truncated or from an incompatible version."
                )

    def __getstate__(self) -> Mapping[str, Any]:
        # Pickle the instance's own configuration: the collections built in
        # __init__ plus any instance-level scalar overrides.
        # _CachedUnionMember descriptors store their values with a leading
        # underscore (e.g. `_prefixes` for `prefixes`) so that the descriptor's
        # __set__ owns assignment. We map those back to the public names so
        # __setstate__ can restore them through the descriptor, re-wiring the
        # invalidation callbacks. All other underscore-prefixed names (_pst, etc.)
        # are private/cache and are intentionally excluded.
        state: dict[str, Any] = {}
        for name, val in self.__dict__.items():
            if name.startswith('_'):
                public = name[1:]
                if isinstance(getattr(type(self), public, None), _SetManagerAttribute):
                    state[public] = val
            else:
                state[name] = val
        return state


#: A module-level instance of the :py:class:`Constants()` class.
#: Provides a common instance for the module to share
#: to easily adjust configuration for the entire module.
#: See `Customizing the Parser with Your Own Configuration <customize.html>`_.
CONSTANTS = Constants()
