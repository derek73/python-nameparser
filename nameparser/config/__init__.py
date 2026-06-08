"""
The :py:mod:`nameparser.config` module manages the configuration of the
nameparser. 

A module-level instance of :py:class:`~nameparser.config.Constants` is created
and used by default for all HumanName instances. You can adjust the entire module's
configuration by importing this instance and changing it.

::

    >>> from nameparser.config import CONSTANTS
    >>> CONSTANTS.titles.remove('hon').add('chemistry','dean') # doctest: +ELLIPSIS
    SetManager({'msgt', ..., 'adjutant'})

You can also adjust the configuration of individual instances by passing
``None`` as the second argument upon instantiation.

::

    >>> from nameparser import HumanName
    >>> hn = HumanName("Dean Robert Johns", None)
    >>> hn.C.titles.add('dean') # doctest: +ELLIPSIS
    SetManager({'msgt', ..., 'adjutant'})
    >>> hn.parse_full_name() # need to run this again after config changes

**Potential Gotcha**: If you do not pass ``None`` as the second argument,
``hn.C`` will be a reference to the module config, possibly yielding 
unexpected results. See `Customizing the Parser <customize.html>`_.
"""
import re
import sys
from collections.abc import Iterable, Iterator, Mapping, Set
from typing import Any, TypeVar

from typing_extensions import Self

from nameparser.util import lc
from nameparser.config.prefixes import PREFIXES
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

    def __init__(self, elements: Iterable[str]) -> None:
        self.elements = set(elements)

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
        Add the lower case and no-period version of the string to the set. Pass an
        explicit `encoding` parameter to specify the encoding of binary strings that
        are not DEFAULT_ENCODING (UTF-8).
        """
        stdin_encoding = None
        if sys.stdin:
            stdin_encoding = sys.stdin.encoding
        encoding = encoding or stdin_encoding or DEFAULT_ENCODING
        if isinstance(s, bytes):
            s = s.decode(encoding)
        self.elements.add(lc(s))

    def add(self, *strings: str) -> Self:
        """
        Add the lower case and no-period version of the string arguments to the set.
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
        for s in strings:
            if (lower := lc(s)) in self.elements:
                self.elements.remove(lower)

        return self


T = TypeVar('T')


class TupleManager(dict[str, T]):
    '''
    A dictionary with dot.notation access. Subclass of ``dict``. Makes the tuple constants 
    more friendly.
    '''

    def __getattr__(self, attr: str) -> T | None:
        return self.get(attr)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __getstate__(self) -> Mapping[str, T]:
        return dict(self)

    def __setstate__(self, state: Mapping[str, T]) -> None:
        self.update(state)

    def __reduce__(self) -> tuple[type, tuple[()], Mapping[str, T]]:
        return (TupleManager, (), self.__getstate__())


class RegexTupleManager(TupleManager[re.Pattern[str]]):
    def __getattr__(self, attr: str) -> re.Pattern[str]:
        return self.get(attr, EMPTY_REGEX)


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
    :type capitalization_exceptions: tuple or dict
    :param capitalization_exceptions: 
        :py:attr:`~capitalization.CAPITALIZATION_EXCEPTIONS` wrapped with :py:class:`TupleManager`.
    :type regexes: tuple or dict
    :param regexes: 
        :py:attr:`regexes`  wrapped with :py:class:`TupleManager`.
    """

    prefixes: SetManager
    suffix_acronyms: SetManager
    suffix_not_acronyms: SetManager
    titles: SetManager
    first_name_titles: SetManager
    conjunctions: SetManager
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

    def __init__(self,
                 prefixes: Iterable[str] = PREFIXES,
                 suffix_acronyms: Iterable[str] = SUFFIX_ACRONYMS,
                 suffix_not_acronyms: Iterable[str] = SUFFIX_NOT_ACRONYMS,
                 titles: Iterable[str] = TITLES,
                 first_name_titles: Iterable[str] = FIRST_NAME_TITLES,
                 conjunctions: Iterable[str] = CONJUNCTIONS,
                 capitalization_exceptions: TupleManager[str] | Iterable[tuple[str, str]] = CAPITALIZATION_EXCEPTIONS,
                 regexes: RegexTupleManager | TupleManager[re.Pattern[str]] | Iterable[tuple[str, re.Pattern[str]]] = REGEXES
                 ) -> None:
        self.prefixes = SetManager(prefixes)
        self.suffix_acronyms = SetManager(suffix_acronyms)
        self.suffix_not_acronyms = SetManager(suffix_not_acronyms)
        self.titles = SetManager(titles)
        self.first_name_titles = SetManager(first_name_titles)
        self.conjunctions = SetManager(conjunctions)
        self.capitalization_exceptions = TupleManager(capitalization_exceptions)
        self.regexes = RegexTupleManager(regexes)
        self._pst = None

    @property
    def suffixes_prefixes_titles(self) -> Set[str]:
        if not self._pst:
            self._pst = self.prefixes | self.suffix_acronyms | self.suffix_not_acronyms | self.titles
        return self._pst

    def __repr__(self) -> str:
        return "<Constants() instance>"

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        Constants.__init__(self, state)

    def __getstate__(self) -> Mapping[str, Any]:
        attrs = [x for x in dir(self) if not x.startswith('_')]
        return dict([(a, getattr(self, a)) for a in attrs])


#: A module-level instance of the :py:class:`Constants()` class.
#: Provides a common instance for the module to share
#: to easily adjust configuration for the entire module.
#: See `Customizing the Parser with Your Own Configuration <customize.html>`_.
CONSTANTS = Constants()
