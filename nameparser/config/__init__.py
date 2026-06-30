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

**Potential Gotcha**: If you do not pass ``None`` as the second argument,
``hn.C`` will be a reference to the module config, possibly yielding 
unexpected results. See `Customizing the Parser <customize.html>`_.
"""
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Set
from typing import Any, TypeVar, overload

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from nameparser.util import lc
from nameparser.config.prefixes import PREFIXES
from nameparser.config.first_name_prefixes import FIRST_NAME_PREFIXES
from nameparser.config.capitalization import CAPITALIZATION_EXCEPTIONS
from nameparser.config.conjunctions import CONJUNCTIONS
from nameparser.config.suffixes import SUFFIX_ACRONYMS
from nameparser.config.suffixes import SUFFIX_NOT_ACRONYMS
from nameparser.config.titles import TITLES
from nameparser.config.titles import FIRST_NAME_TITLES
from nameparser.config.regexes import EMPTY_REGEX, REGEXES

DEFAULT_ENCODING = 'UTF-8'


class SetManager(Set):
    '''
    Easily add and remove config variables per module or instance. Subclass of
    ``collections.abc.Set``.

    Only special functionality beyond that provided by set() is
    to normalize constants for comparison (lower case, no periods)
    when they are add()ed and remove()d and allow passing multiple 
    string arguments to the :py:func:`add()` and :py:func:`remove()` methods.

    '''

    _on_change: Callable[[], None] | None

    def __init__(self, elements: Iterable[str]) -> None:
        self.elements = set(elements)
        # Optional invalidation hook, wired by an owning Constants so that
        # in-place add()/remove() can clear its cached suffixes_prefixes_titles
        # union. None when the manager is used standalone.
        self._on_change = None

    def __call__(self) -> Set[str]:
        return self.elements

    def __repr__(self) -> str:
        return "SetManager({})".format(self.elements)  # used for docs

    def __iter__(self) -> Iterator[str]:
        return iter(self.elements)

    def __contains__(self, value: object) -> bool:
        return value in self.elements

    def __len__(self) -> int:
        return len(self.elements)

    def add_with_encoding(self, s: str, encoding: str | None = None) -> None:
        """
        Add the lowercased, leading/trailing-periods-stripped version of the string to the set. Pass an
        explicit `encoding` parameter to specify the encoding of binary strings that
        are not DEFAULT_ENCODING (UTF-8).
        """
        stdin_encoding = None
        if sys.stdin:
            stdin_encoding = sys.stdin.encoding
        encoding = encoding or stdin_encoding or DEFAULT_ENCODING
        if isinstance(s, bytes):
            s = s.decode(encoding)
        normalized = lc(s)
        if normalized not in self.elements:
            self.elements.add(normalized)
            if self._on_change:
                self._on_change()

    def add(self, *strings: str) -> Self:
        """
        Add the lowercased, leading/trailing-periods-stripped version of the string arguments to the set.
        Can pass a list of strings. Returns ``self`` for chaining.
        """
        for s in strings:
            self.add_with_encoding(s)

        return self

    def remove(self, *strings: str) -> Self:
        """
        Remove the lower case and no-period version of the string arguments from the set.
        Returns ``self`` for chaining.
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


class TupleManager(dict[str, T]):
    '''
    A dictionary with dot.notation access. Subclass of ``dict``. Makes the tuple constants 
    more friendly.
    '''

    def __getattr__(self, attr: str) -> T | None:
        # Dunder names are Python's protocol probes (copy looks up __deepcopy__,
        # inspect.unwrap looks up __wrapped__, ...), never config keys. Report
        # them as genuinely absent so hasattr() is honest and those probes work;
        # otherwise the dict default is mistaken for a real protocol hook. See
        # RegexTupleManager.__getattr__ for the concrete failure this prevents.
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(attr)
        return self.get(attr)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

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
        # Dunder names are Python's protocol probes (copy.deepcopy looks up
        # __deepcopy__, inspect.unwrap looks up __wrapped__, ...), never regex
        # keys. Report them as genuinely absent; otherwise the EMPTY_REGEX
        # default is mistaken for a real protocol hook — e.g. copy.deepcopy
        # tries to call the returned re.Pattern and raises TypeError.
        if attr.startswith("__") and attr.endswith("__"):
            raise AttributeError(attr)
        return self.get(attr, EMPTY_REGEX)


class _CachedUnionMember:
    """Descriptor for the four ``SetManager`` attributes whose union ``Constants``
    caches in ``_pst`` (``prefixes``, ``suffix_acronyms``, ``suffix_not_acronyms``,
    ``titles``).

    Assigning a new manager — or mutating one in place via ``add()`` / ``remove()``
    — invalidates that cache. Keeping the behavior on a descriptor scopes it to
    exactly these attributes, beside their declarations, rather than spreading it
    across a catch-all ``__setattr__`` and a separate attribute-name list.
    """

    _attr: str

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr = '_' + name

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> '_CachedUnionMember': ...
    @overload
    def __get__(self, obj: 'Constants', objtype: type | None = None) -> SetManager: ...

    def __get__(self, obj: 'Constants | None', objtype: type | None = None) -> 'SetManager | _CachedUnionMember':
        if obj is None:
            return self
        return getattr(obj, self._attr)

    def __set__(self, obj: 'Constants', value: SetManager) -> None:
        if not isinstance(value, SetManager):
            raise TypeError(
                f"Expected a SetManager instance, got {type(value).__name__!r}. "
                "Wrap your iterable: SetManager(['mr', 'ms'])"
            )
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
    :param set conjunctions:
        :py:attr:`conjunctions`  wrapped with :py:class:`SetManager`.
    :param set first_name_prefixes:
        :py:attr:`~first_name_prefixes.FIRST_NAME_PREFIXES` wrapped with :py:class:`SetManager`.
    :type capitalization_exceptions: tuple or dict
    :param capitalization_exceptions: 
        :py:attr:`~capitalization.CAPITALIZATION_EXCEPTIONS` wrapped with :py:class:`TupleManager`.
    :type regexes: tuple or dict
    :param regexes: 
        :py:attr:`regexes`  wrapped with :py:class:`TupleManager`.
    """

    prefixes = _CachedUnionMember()
    suffix_acronyms = _CachedUnionMember()
    suffix_not_acronyms = _CachedUnionMember()
    titles = _CachedUnionMember()
    first_name_titles: SetManager
    conjunctions: SetManager
    first_name_prefixes: SetManager
    capitalization_exceptions: TupleManager[str]
    regexes: RegexTupleManager
    _pst: Set[str] | None

    string_format = "{title} {first} {middle} {last} {suffix} ({nickname})"
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

    suffix_delimiter = None
    """
    If set, an additional delimiter used to split suffix groups after
    comma-splitting. For example, setting ``suffix_delimiter=" - "`` allows
    ``"RN - CRNA"`` to be parsed as two separate suffixes. Default is
    ``None`` (no additional splitting beyond the standard comma split).

    Note: setting this to ``","`` or ``", "`` has no additional effect —
    the full name is already split on bare commas first, and each resulting
    part is stripped of surrounding whitespace before this step runs.

    Known limitation: the expansion is applied to all post-comma parts, not
    just suffix groups. In inverted format (``"Last, First, suffix"``), the
    first-name part is also split on the delimiter. In practice this is
    harmless since first names rarely contain the delimiter string, but a
    name like ``"Doe, Mary - Kate, RN"`` with ``suffix_delimiter=" - "``
    would misparse.
    """

    empty_attribute_default = ''
    """
    Default return value for empty attributes.

    .. doctest::

        >>> from nameparser.config import CONSTANTS
        >>> CONSTANTS.empty_attribute_default = None
        >>> name = HumanName("John Doe")
        >>> name.title
        None
        >>>name.first
        'John'

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

    """

    patronymic_name_order = False
    """
    If set, detects names in Russian formal order (``Surname GivenName Patronymic``)
    by recognizing a trailing East-Slavic patronymic suffix on the last token, and
    rotates the three name parts so that ``first``/``middle``/``last`` map to
    given name / patronymic / surname respectively.  Detection requires exactly one
    token in each of first, middle, and last; names with multi-part given names or
    multiple middle names are left unchanged.

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

    """

    def __init__(self,
                 prefixes: Iterable[str] = PREFIXES,
                 suffix_acronyms: Iterable[str] = SUFFIX_ACRONYMS,
                 suffix_not_acronyms: Iterable[str] = SUFFIX_NOT_ACRONYMS,
                 titles: Iterable[str] = TITLES,
                 first_name_titles: Iterable[str] = FIRST_NAME_TITLES,
                 conjunctions: Iterable[str] = CONJUNCTIONS,
                 first_name_prefixes: Iterable[str] = FIRST_NAME_PREFIXES,
                 capitalization_exceptions: TupleManager[str] | Iterable[tuple[str, str]] = CAPITALIZATION_EXCEPTIONS,
                 regexes: RegexTupleManager | TupleManager[re.Pattern[str]] | Iterable[tuple[str, re.Pattern[str]]] = REGEXES,
                 patronymic_name_order: bool = False,
                 ) -> None:
        # These four descriptor assignments call _CachedUnionMember.__set__, which
        # calls _invalidate_pst() and establishes self._pst. They must come before
        # any read of suffixes_prefixes_titles.
        self.prefixes = SetManager(prefixes)
        self.suffix_acronyms = SetManager(suffix_acronyms)
        self.suffix_not_acronyms = SetManager(suffix_not_acronyms)
        self.titles = SetManager(titles)
        self.first_name_titles = SetManager(first_name_titles)
        self.conjunctions = SetManager(conjunctions)
        self.first_name_prefixes = SetManager(first_name_prefixes)
        self.capitalization_exceptions = TupleManager(capitalization_exceptions)
        self.regexes = RegexTupleManager(regexes)
        self.patronymic_name_order = patronymic_name_order

    def _invalidate_pst(self) -> None:
        self._pst = None

    @property
    def suffixes_prefixes_titles(self) -> Set[str]:
        if self._pst is None:
            self._pst = self.prefixes | self.suffix_acronyms | self.suffix_not_acronyms | self.titles
        return self._pst

    def __repr__(self) -> str:
        return "<Constants() instance>"

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        # Restore each saved attribute directly. The previous implementation
        # passed the whole state dict to __init__ as the ``prefixes`` argument,
        # which silently reverted every collection to its module default on
        # unpickling.
        self._pst = None
        for name, value in state.items():
            setattr(self, name, value)
        # Verify each descriptor-backed attr was restored. Without this, a missing
        # key surfaces later as AttributeError: 'Constants' object has no attribute
        # '_prefixes' — the private mangled name, not the public one, making it
        # very hard to diagnose.
        for attr in (n for n, v in vars(type(self)).items() if isinstance(v, _CachedUnionMember)):
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
                if isinstance(getattr(type(self), public, None), _CachedUnionMember):
                    state[public] = val
            else:
                state[name] = val
        return state


#: A module-level instance of the :py:class:`Constants()` class.
#: Provides a common instance for the module to share
#: to easily adjust configuration for the entire module.
#: See `Customizing the Parser with Your Own Configuration <customize.html>`_.
CONSTANTS = Constants()
