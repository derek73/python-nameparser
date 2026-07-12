import re
import warnings
from collections.abc import Callable, Iterable, Iterator
from operator import itemgetter
from itertools import groupby

from typing import overload

from nameparser.util import HumanNameAttributeT, lc
from nameparser.util import log
from nameparser.config import CONSTANTS
from nameparser.config import Constants
from nameparser.config import DEFAULT_ENCODING

def group_contiguous_integers(data: Iterable[int]) -> list[tuple[int, int]]:
    """
    return list of tuples containing first and last index
    position of contiguous numbers in a series
    """
    ranges: list[tuple[int, int]] = []
    for key, group_with_indices in groupby(enumerate(data), lambda i: i[0] - i[1]):
        group = list(map(itemgetter(1), group_with_indices))
        if len(group) > 1:
            ranges.append((group[0], group[-1]))
    return ranges


class HumanName:
    """
    Parse a person's name into individual components.

    Instantiation assigns to ``full_name``, and assignment to
    :py:attr:`full_name` triggers :py:func:`parse_full_name`. After parsing the
    name, these instance attributes are available. Alternatively, you can pass
    any of the instance attributes to the constructor method and skip the parsing
    process. If any of the the instance attributes are passed to the constructor
    as keywords, :py:func:`parse_full_name` will not be performed.

    **HumanName Instance Attributes**

    * :py:attr:`title`
    * :py:attr:`first`
    * :py:attr:`middle`
    * :py:attr:`last`
    * :py:attr:`suffix`
    * :py:attr:`nickname`
    * :py:attr:`maiden`
    * :py:attr:`surnames`
    * :py:attr:`given_names`

    :param str full_name: The name string to be parsed.
    :param constants:
        a :py:class:`~nameparser.config.Constants` instance (subclasses are
        honored). Pass ``None`` for `per-instance config <customize.html>`_.
        Anything else raises ``TypeError``.
    :param str encoding: string representing the encoding of your input
        (deprecated with ``bytes`` input, removal in 2.0 — decode before
        passing; see issue #245)
    :param str string_format: python string formatting
    :param str initials_format: python initials string formatting
    :param str initials_delimter: string delimiter for initials
    :param str initials_separator: string separator between consecutive initials
    :param str suffix_delimiter: additional delimiter to split post-comma parts
        before suffix detection, e.g. ``" - "`` for ``"RN - CRNA"``
    :param str first: first name
    :param str middle: middle name
    :param str last: last name
    :param str title: The title or prenominal
    :param str suffix: The suffix or postnominal
    :param str nickname: Nicknames
    :param str maiden: Maiden name
    """

    original: str | bytes = ''
    """
    The original string, untouched by the parser.
    """

    _members = ['title', 'first', 'middle', 'last', 'suffix', 'nickname', 'maiden']
    _full_name = ''

    title_list: list[str]
    first_list: list[str]
    middle_list: list[str]
    last_list: list[str]
    suffix_list: list[str]
    nickname_list: list[str]
    maiden_list: list[str]
    _had_comma: bool

    def __init__(
        self,
        full_name: str | bytes = "",
        constants: Constants | None = CONSTANTS,
        encoding: str = DEFAULT_ENCODING,
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
        self.C = constants

        # Lookup entries derived while parsing this instance (period-joined
        # titles/suffixes like "Lt.Gov.", conjunction-joined pieces like
        # "Mr. and Mrs." or "von und zu"). Kept separate from self.C so that
        # parsing never writes into the config — which is usually the shared
        # module-level CONSTANTS — keeping results independent of what was
        # parsed before and config reads safe across threads. Values are
        # lc()-normalized, mirroring how SetManager stores them. Reset at the
        # start of each parse_full_name() run.
        self._derived_titles: set[str] = set()
        self._derived_suffixes: set[str] = set()
        self._derived_conjunctions: set[str] = set()
        self._derived_prefixes: set[str] = set()

        self.encoding = encoding
        self.string_format = string_format if string_format is not None else self.C.string_format
        self.initials_format = initials_format if initials_format is not None else self.C.initials_format
        self.initials_delimiter = initials_delimiter if initials_delimiter is not None else self.C.initials_delimiter
        self.initials_separator = initials_separator if initials_separator is not None else self.C.initials_separator
        self.suffix_delimiter = suffix_delimiter if suffix_delimiter is not None else self.C.suffix_delimiter
        self._had_comma = False
        if (first or middle or last or title or suffix or nickname or maiden):
            self.first = first
            self.middle = middle
            self.last = last
            self.title = title
            self.suffix = suffix
            self.nickname = nickname
            self.maiden = maiden
        else:
            # calls _apply_full_name directly (not the setter) so the
            # deprecation warning below attributes to this constructor's
            # caller rather than to the setter
            self._apply_full_name(full_name, stacklevel=3)

    @staticmethod
    def _validate_constants(constants: 'Constants | None') -> 'Constants':
        # Shared by the constructor and the C setter so both assignment paths
        # give the same immediate TypeError instead of one bypassing the
        # other and failing far from the cause (#239).
        if constants is None:
            return Constants()
        if not isinstance(constants, Constants):
            # passing the class itself is the likeliest mistake, and
            # reporting it as "got type" would only add confusion
            hint = (" (a class was passed; did you mean Constants()?)"
                    if isinstance(constants, type) else "")
            raise TypeError(
                "constants must be a Constants instance or None, "
                f"got {type(constants).__name__}{hint}"
            )
        return constants

    @property
    def C(self) -> 'Constants':
        """
        A reference to the configuration for this instance, which may or may not be
        a reference to the shared, module-wide instance at
        :py:mod:`~nameparser.config.CONSTANTS`. See `Customizing the Parser
        <customize.html>`_.

        Assigning a non-``Constants`` value (besides ``None``, which builds a
        fresh private ``Constants()``) raises the same ``TypeError`` as passing
        an invalid ``constants`` argument to the constructor (#239).
        """
        return self._C

    @C.setter
    def C(self, constants: 'Constants | None') -> None:
        self._C = self._validate_constants(constants)

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        c = state.pop('_C')
        state['C'] = None if c is CONSTANTS else c  # sentinel: restore shared singleton on load
        return state

    def __setstate__(self, state: dict) -> None:
        state = dict(state)
        c = state.pop('C', None)
        self._C = CONSTANTS if c is None else c
        self.__dict__.update(state)
        # pickles from before the per-parse derived sets existed lack them;
        # backfill so the is_* predicates work without a re-parse
        for attr in ('_derived_titles', '_derived_suffixes',
                     '_derived_conjunctions', '_derived_prefixes'):
            self.__dict__.setdefault(attr, set())

    def __iter__(self) -> Iterator[str]:
        return (value for member in self._members
                if (value := getattr(self, member)))

    def __len__(self) -> int:
        return sum(1 for member in self._members if getattr(self, member))

    def __eq__(self, other: object) -> bool:
        """
        .. deprecated:: 1.3.0
            Removed in 2.0 (see issue #223); use :py:meth:`matches`.

        HumanName instances are equal to other objects whose
        lower case unicode representation is the same. Note the
        differences from :py:meth:`matches`: this compares formatted
        output, so it depends on ``string_format`` and cannot see
        ``maiden``, and it stringifies operands of any type.
        """
        warnings.warn(
            "HumanName == comparison is deprecated and will be removed in "
            "2.0; use matches() instead. See "
            "https://github.com/derek73/python-nameparser/issues/223",
            DeprecationWarning,
            stacklevel=2,
        )
        return str(self).lower() == str(other).lower()

    @overload
    def __getitem__(self, key: slice) -> list[str]: ...
    @overload
    def __getitem__(self, key: str) -> str: ...
    def __getitem__(self, key: slice | str) -> str | list[str]:
        if isinstance(key, slice):
            return [getattr(self, x) for x in self._members[key]]
        else:
            return getattr(self, key)

    def __setitem__(self, key: str, value: str | list[str] | None) -> None:
        if key in self._members:
            self._set_list(key, value)
        else:
            raise KeyError("Not a valid HumanName attribute", key)

    def __str__(self) -> str:
        if self.string_format is not None:
            # string_format = "{title} {first} {middle} {last} {suffix} ({nickname})"
            # Empty attributes must render as '' (not empty_attribute_default,
            # which may be None) so str.format does not interpolate the
            # literal "None" into the output, which cannot be scrubbed
            # afterward without corrupting name text containing the same
            # substring (#254).
            _s = self.string_format.format(**{k: v or '' for k, v in self.as_dict().items()})
            # remove trailing punctuation from missing nicknames
            _s = _s.replace(" ()", "").replace(" ''", "").replace(' ""', "")
            _s = self.C.regexes.space_before_comma.sub(',', _s)
            return self.collapse_whitespace(_s).strip(', ')
        return " ".join(self)

    def __hash__(self) -> int:
        """
        .. deprecated:: 1.3.0
            Removed in 2.0 (see issue #223); use :py:meth:`comparison_key`
            for sets, dicts, and dedup.
        """
        warnings.warn(
            "hash(HumanName) is deprecated and will be removed in 2.0; use "
            "comparison_key() for sets and dicts. See "
            "https://github.com/derek73/python-nameparser/issues/223",
            DeprecationWarning,
            stacklevel=2,
        )
        # __eq__ compares lowercased strings, so hash the lowercased string
        # to keep equal instances in the same hash bucket.
        return hash(str(self).lower())

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

    def as_dict(self, include_empty: bool = True) -> dict[str, str]:
        """
        Return the parsed name as a dictionary of its attributes.

        :param bool include_empty: Include keys in the dictionary for empty name attributes.
        :rtype: dict

        .. doctest::

            >>> name = HumanName("Bob Dole")
            >>> name.as_dict()
            {'title': '', 'first': 'Bob', 'middle': '', 'last': 'Dole', 'suffix': '', 'nickname': '', 'maiden': ''}
            >>> name.as_dict(False)
            {'first': 'Bob', 'last': 'Dole'}

        """
        d = {}
        for m in self._members:
            if include_empty:
                d[m] = getattr(self, m)
            else:
                val = getattr(self, m)
                if val:
                    d[m] = val
        return d

    def comparison_key(self) -> tuple[str, ...]:
        """
        The seven name components (title, first, middle, last, suffix,
        nickname, maiden) as a lowercased tuple: a canonical, hashable
        identity for the parsed name. Use it for dedup, dict keys, and
        sorting or grouping, e.g.
        ``unique = {n.comparison_key(): n for n in names}.values()``.

        Built from the ``*_list`` attributes, so it is unaffected by
        display settings like ``string_format`` and
        ``empty_attribute_default``.

        Empty or unparsable input yields the all-empty key, so such names
        all compare equal and collide in dedup; screen them out with
        ``len(name) == 0`` first.

        .. doctest::

            >>> HumanName("Dr. Juan Q. Xavier de la Vega III").comparison_key()
            ('dr.', 'juan', 'q. xavier', 'de la vega', 'iii', '', '')

        """
        return tuple(
            " ".join(getattr(self, member + "_list")).lower()
            for member in self._members
        )

    def matches(self, other: 'str | HumanName') -> bool:
        """
        Compare parsed components case-insensitively; the semantic
        replacement for the deprecated ``==``. A ``str`` argument is parsed
        first, using this instance's configuration, so any written form of
        the same name matches; a ``HumanName`` argument is compared as
        already parsed — its own configuration determined its components.
        Two empty or unparsable names match each other; check
        ``len(name) == 0`` to screen them.

        .. doctest::

            >>> name = HumanName("Dr. Juan Q. Xavier de la Vega III")
            >>> name.matches("de la vega, dr. juan Q. xavier III")
            True
            >>> name.matches("Juan de la Vega")
            False

        Unlike the deprecated ``==``, all seven components participate
        (including ``maiden``, which the default ``string_format`` omits)
        and display settings have no effect. Raises ``TypeError`` for
        anything that is not a ``str`` or ``HumanName``; guard optional
        values explicitly, e.g. ``x is not None and name.matches(x)``.

        Parses string arguments on every call. When matching one name
        against many candidates, parse the candidates once or compare
        :py:meth:`comparison_key` values instead.
        """
        if isinstance(other, HumanName):
            return self.comparison_key() == other.comparison_key()
        if isinstance(other, str):
            return self.comparison_key() == type(self)(other, self.C).comparison_key()
        raise TypeError(
            f"matches() requires a str or HumanName, got {type(other).__name__}"
        )

    def _process_initial(self, name_part: str, firstname: bool = False) -> str:
        """
            Name parts may include prefixes or conjunctions. This function filters these from the name unless it is
            a first name, since first names cannot be conjunctions or prefixes.
        """
        # split() rather than split(" "): *_list attributes assigned directly
        # bypass parse_pieces whitespace normalization, and split(" ") yields
        # empty strings for repeated spaces (#232)
        parts = name_part.split()
        initials = []
        for part in parts:
            if not (self.is_prefix(part) or self.is_conjunction(part)) or firstname:
                initials.append(part[0])
        if len(initials) > 0:
            return self.initials_separator.join(initials)
        # Return '' (never empty_attribute_default, which may be None) when a
        # part has no initialable words, e.g. a middle name consisting only of
        # prefixes ("de la"). Callers drop these parts entirely.
        return ''

    def _initials_lists(self) -> tuple[list[str], list[str], list[str]]:
        """Initials for the first, middle and last name groups. Parts that
        yield no initials (e.g. a prefix-only middle name like "de la") are
        dropped rather than kept as empty strings.
        """
        def group_initials(names: list[str], firstname: bool = False) -> list[str]:
            return [i for i in (self._process_initial(n, firstname) for n in names if n) if i]
        return (group_initials(self.first_list, True),
                group_initials(self.middle_list),
                group_initials(self.last_list))

    def initials_list(self) -> list[str]:
        """
            Returns the initials as a list

            .. doctest::

                >>> name = HumanName("Sir Bob Andrew Dole")
                >>> name.initials_list()
                ['B', 'A', 'D']
                >>> name = HumanName("J. Doe")
                >>> name.initials_list()
                ['J', 'D']
        """
        first_initials_list, middle_initials_list, last_initials_list = self._initials_lists()
        return first_initials_list + middle_initials_list + last_initials_list

    def initials(self) -> str:
        """
        Return formatted initials for the name, controlled by
        ``initials_format``, ``initials_delimiter``, and ``initials_separator``.

        ``initials_delimiter`` is appended after each individual initial.
        ``initials_separator`` is placed between consecutive initials within
        a name group (first, middle, or last). Both can be set as
        ``Constants`` attributes or as ``HumanName`` constructor kwargs.

        .. doctest::

            >>> name = HumanName("Sir Bob Andrew Dole")
            >>> name.initials()
            'B. A. D.'
            >>> name = HumanName("Sir Bob Andrew Dole", initials_format="{first} {middle}")
            >>> name.initials()
            'B. A.'
            >>> name = HumanName("Doe, John A.", initials_delimiter="", initials_separator="")
            >>> name.initials()
            'J A D'
        """

        first_initials_list, middle_initials_list, last_initials_list = self._initials_lists()

        # Empty name groups must render as '' (not empty_attribute_default,
        # which may be None) so str.format does not interpolate the literal
        # "None" into the output. A fully-empty result falls back to
        # empty_attribute_default, matching the other attribute accessors
        # (e.g. ``first``).
        initials_dict = {
            "first":  (self.initials_delimiter + self.initials_separator).join(first_initials_list) + self.initials_delimiter
            if len(first_initials_list) else "",
            "middle": (self.initials_delimiter + self.initials_separator).join(middle_initials_list) + self.initials_delimiter
            if len(middle_initials_list) else "",
            "last": (self.initials_delimiter + self.initials_separator).join(last_initials_list) + self.initials_delimiter
            if len(last_initials_list) else ""
        }

        _s = self.initials_format.format(**initials_dict)  # noqa: UP032
        return self.collapse_whitespace(_s) or self.C.empty_attribute_default

    @property
    def has_own_config(self) -> bool:
        """
        True if this instance is not using the shared module-level
        configuration.
        """
        return self.C is not CONSTANTS

    # attributes

    @property
    def title(self) -> str:
        """
        The person's titles. Any string of consecutive pieces in
        :py:mod:`~nameparser.config.titles` or
        :py:mod:`~nameparser.config.conjunctions`
        at the beginning of :py:attr:`full_name`.
        """
        return " ".join(self.title_list) or self.C.empty_attribute_default

    @title.setter
    def title(self, value: str | list[str] | None) -> None:
        self._set_list('title', value)

    @property
    def first(self) -> str:
        """
        The person's first name. The first name piece after any known
        :py:attr:`title` pieces parsed from :py:attr:`full_name`.
        """
        return " ".join(self.first_list) or self.C.empty_attribute_default

    @first.setter
    def first(self, value: str | list[str] | None) -> None:
        self._set_list('first', value)

    @property
    def middle(self) -> str:
        """
        The person's middle names. All name pieces after the first name and
        before the last name parsed from :py:attr:`full_name`.
        """
        return " ".join(self.middle_list) or self.C.empty_attribute_default

    @middle.setter
    def middle(self, value: str | list[str] | None) -> None:
        self._set_list('middle', value)

    @property
    def last(self) -> str:
        """
        The person's last name. The last name piece parsed from
        :py:attr:`full_name`.
        """
        return " ".join(self.last_list) or self.C.empty_attribute_default

    @last.setter
    def last(self, value: str | list[str] | None) -> None:
        self._set_list('last', value)

    @property
    def suffix(self) -> str:
        """
        The persons's suffixes. Pieces at the end of the name that are found in
        :py:mod:`~nameparser.config.suffixes`, or pieces that are at the end
        of comma separated formats, e.g.
        "Lastname, Title Firstname Middle[,] Suffix [, Suffix]" parsed
        from :py:attr:`full_name`.
        """
        return ", ".join(self.suffix_list) or self.C.empty_attribute_default

    @suffix.setter
    def suffix(self, value: str | list[str] | None) -> None:
        self._set_list('suffix', value)

    @property
    def nickname(self) -> str:
        """
        The person's nicknames. Any text found inside of quotes (``""``) or
        parenthesis (``()``)
        """
        return " ".join(self.nickname_list) or self.C.empty_attribute_default

    @nickname.setter
    def nickname(self, value: str | list[str] | None) -> None:
        self._set_list('nickname', value)

    @property
    def maiden(self) -> str:
        """
        The person's maiden (alternate/prior) last name. Empty unless a
        delimiter has been routed to it via
        :py:attr:`~nameparser.config.Constants.maiden_delimiters` -- see the
        "Routing to Maiden Name" section of the customization docs.
        """
        return " ".join(self.maiden_list) or self.C.empty_attribute_default

    @maiden.setter
    def maiden(self, value: str | list[str] | None) -> None:
        self._set_list('maiden', value)

    @property
    def surnames_list(self) -> list[str]:
        """
        List of middle names followed by last name.
        """
        return self.middle_list + self.last_list

    @property
    def surnames(self) -> str:
        """
        A string of all middle names followed by the last name.
        """
        return " ".join(self.surnames_list) or self.C.empty_attribute_default

    @property
    def given_names_list(self) -> list[str]:
        """
        List of first name followed by middle names.
        """
        return self.first_list + self.middle_list

    @property
    def given_names(self) -> str:
        """
        A string of the first name followed by all middle names.
        """
        return " ".join(self.given_names_list) or self.C.empty_attribute_default

    def _split_last(self) -> tuple[list[str], list[str]]:
        """Return (prefix_particles, base_words) split from the last name.

        The base_words list is never empty: if every word in the last name
        matches a prefix particle, the guard fires and all words are returned
        as the base with an empty prefix list (heuristic: a family name is
        assumed not to consist entirely of particles).

        >>> HumanName("Vincent van Gogh")._split_last()
        (['van'], ['Gogh'])
        >>> HumanName("Anh Do")._split_last()
        ([], ['Do'])
        """
        words = " ".join(self.last_list).split()
        i = 0
        while i < len(words) and self.is_prefix(words[i]):
            i += 1
        if i == len(words):
            # Heuristic: assume a family name isn't entirely composed of
            # particles (e.g. surname "Do" which also appears in PREFIXES).
            # Don't strip — treat the whole last name as the base.
            return [], words
        return words[:i], words[i:]

    @property
    def last_prefixes_list(self) -> list[str]:
        """
        List of leading prefix particles in the last name (the *tussenvoegsel*).
        Returns ``[]`` when there are none, including the case where every word
        in the last name matches a prefix — see :py:meth:`_split_last`.

        >>> HumanName("Juan de la Vega").last_prefixes_list
        ['de', 'la']
        """
        return self._split_last()[0]

    @property
    def last_base_list(self) -> list[str]:
        """
        List of last-name words after stripping leading prefix particles.
        Never empty: when every word matches a prefix, no stripping occurs and
        the full last name is returned — see :py:meth:`_split_last`.

        >>> HumanName("Vincent van Gogh").last_base_list
        ['Gogh']
        """
        return self._split_last()[1]

    @property
    def last_base(self) -> str:
        """
        The last name with leading prefix particles removed (the core surname).
        For ``"van Gogh"`` this is ``"Gogh"``; for ``"Smith"`` it is ``"Smith"``.
        ``last`` is always unchanged. When every word in the last name matches a
        prefix particle, no stripping occurs and the full last name is returned.

        >>> HumanName("Vincent van Gogh").last_base
        'Gogh'
        >>> HumanName("John Smith").last_base
        'Smith'
        """
        return " ".join(self.last_base_list) or self.C.empty_attribute_default

    @property
    def last_prefixes(self) -> str:
        """
        The leading prefix particle(s) of the last name (the *tussenvoegsel*).
        Returns ``""`` (or ``empty_attribute_default``) when there are none,
        including when every word in the last name matches a prefix particle
        (the all-particles guard; see :py:meth:`_split_last`).

        >>> HumanName("Vincent van Gogh").last_prefixes
        'van'
        >>> HumanName("Juan de la Vega").last_prefixes
        'de la'
        """
        return " ".join(self.last_prefixes_list) or self.C.empty_attribute_default

    # setter methods

    def _set_list(self, attr: str, value: str | list[str] | None) -> None:
        if isinstance(value, list):
            val = value
        elif isinstance(value, (str, bytes)):
            val = [value]
        elif value is None:
            val = []
        else:
            raise TypeError(
                "Can only assign strings, lists or None to name attributes."
                f" Got {type(value)}")
        setattr(self, attr+"_list", self.parse_pieces(val))

    # Parse helpers
    def is_title(self, value: str) -> bool:
        """Is in the :py:data:`~nameparser.config.titles.TITLES` set or was
        derived as a title earlier in this parse (e.g. ``"Lt.Gov."``,
        ``"Mr. and Mrs."``)."""
        word = lc(value)
        return word in self.C.titles or word in self._derived_titles

    def is_leading_title(self, piece: str) -> bool:
        """
        True if ``piece`` is a known title, or an unrecognized multi-letter
        word ending in a single trailing period (e.g. ``"Major."``). The
        ``{2,}`` in the ``period_abbreviation`` regex, not a separate
        ``is_an_initial()`` check, is what excludes single-letter initials
        like ``"J."``. Only meaningful for pieces in the title position
        (before the first name is set) — a period-abbreviation appearing
        later in the name is left as a middle name. The match is not
        registered in ``C.titles`` or the per-parse derived titles, so
        matching ``"Major."`` here never makes ``"Major"`` (or ``"Major."``)
        a recognized title elsewhere, even within the same parse.
        """
        return self.is_title(piece) or bool(self.C.regexes.period_abbreviation.match(piece))

    def is_conjunction(self, piece: str | list[str]) -> bool:
        """Is in the conjunctions set — config or derived earlier in this
        parse (e.g. ``"of the"``) — and not :py:func:`is_an_initial()`."""
        if isinstance(piece, list):
            for item in piece:
                if self.is_conjunction(item):
                    return True
            return False
        return (piece.lower() in self.C.conjunctions
                or piece.lower() in self._derived_conjunctions) \
            and not self.is_an_initial(piece)

    def is_prefix(self, piece: str | list[str]) -> bool:
        """
        Lowercased, leading/trailing-periods-stripped version of piece is in the
        :py:data:`~nameparser.config.prefixes.PREFIXES` set, or was derived as
        a prefix earlier in this parse (e.g. ``"von und"``).
        """
        if isinstance(piece, list):
            for item in piece:
                if self.is_prefix(item):
                    return True
            return False
        word = lc(piece)
        return word in self.C.prefixes or word in self._derived_prefixes

    def is_bound_first_name(self, piece: str) -> bool:
        """Lowercased, leading/trailing-periods-stripped version of piece is in :py:attr:`~nameparser.config.Constants.bound_first_names`."""
        return lc(piece) in self.C.bound_first_names

    def is_non_first_name_prefix(self, piece: str) -> bool:
        """Lowercased, leading/trailing-periods-stripped version of piece is in
        :py:attr:`~nameparser.config.Constants.non_first_name_prefixes`."""
        return lc(piece) in self.C.non_first_name_prefixes

    def _join_bound_first_name(self, pieces: list[str], reserve_last: bool) -> list[str]:
        """Join a first-name prefix to its following piece.

        Finds the first non-title piece; if it is in ``bound_first_names``,
        merges it with the next piece — unless ``reserve_last`` is True and no
        further piece would remain for the last name.
        """
        fi = next((i for i, p in enumerate(pieces) if not self.is_title(p)), None)
        if fi is None:
            return pieces
        if not self.is_bound_first_name(pieces[fi]):
            return pieces
        next_i = fi + 1
        if next_i >= len(pieces):
            return pieces
        if reserve_last:
            # Count non-suffix pieces from next_i onward; need ≥2 so the join
            # target and at least one last-name piece both exist.
            non_suffix_remaining = sum(
                1 for p in pieces[next_i:] if not self.is_suffix(p)
            )
            if non_suffix_remaining <= 1:
                return pieces
        pieces[fi] = pieces[fi] + " " + pieces[next_i]
        del pieces[next_i]
        return pieces

    def is_roman_numeral(self, value: str) -> bool:
        """
        Matches the ``roman_numeral`` regular expression in
        :py:data:`~nameparser.config.regexes.REGEXES`.
        """
        return bool(self.C.regexes.roman_numeral.match(value))

    def is_suffix(self, piece: str | list[str]) -> bool:
        """
        Is in the suffixes set — or was derived as a period-joined suffix
        earlier in this parse (e.g. ``"JD.CPA"``) — and not
        :py:func:`is_an_initial()`.

        Some suffixes may be acronyms (M.B.A) while some are not (Jr.),
        so we remove the periods from `piece` when testing against
        `C.suffix_acronyms`.
        """
        # suffixes may have periods inside them like "M.D."
        if isinstance(piece, list):
            for item in piece:
                if self.is_suffix(item):
                    return True
            return False
        else:
            word = lc(piece)
            return ((word.replace('.', '') in self.C.suffix_acronyms)
                    or (word in self.C.suffix_not_acronyms)
                    or (word in self._derived_suffixes)) \
                and not self.is_an_initial(piece)

    def are_suffixes(self, pieces: Iterable[str]) -> bool:
        """Return True if all pieces are suffixes.

        Vacuously True for an empty iterable — the piece loops in
        :py:func:`parse_full_name` rely on this to route the final piece
        to the last-name branch.
        """
        for piece in pieces:
            if not self.is_suffix(piece):
                return False
        return True

    def is_suffix_lenient(self, piece: str) -> bool:
        """Like is_suffix(), but suffix_not_acronyms members are accepted
        unconditionally, bypassing is_suffix()'s is_an_initial() veto.

        This covers all suffix_not_acronyms members (i, ii, iii, iv, v, jr,
        sr, etc.), case-insensitively, including single-letter entries that
        is_suffix() would otherwise reject. Only safe for pieces in
        unambiguous positions, e.g. after a comma ("John Ingram, V").
        """
        return lc(piece) in self.C.suffix_not_acronyms or self.is_suffix(piece)

    def expand_suffix_delimiter(self, part: str) -> list[str]:
        """Split a single post-comma part on :py:attr:`suffix_delimiter`,
        if configured. Used only at suffix-consumption sites, where a part
        has already been identified as a suffix group, so splitting it
        further can't misparse an unrelated name segment. Returns ``[part]``
        unchanged if no delimiter is configured.
        """
        if not self.suffix_delimiter:
            return [part]
        return [p for p in (p.strip() for p in part.split(self.suffix_delimiter)) if p]

    def are_suffixes_after_comma(self, pieces: Iterable[str]) -> bool:
        """Return True if all pieces are suffixes by the lenient
        :py:func:`is_suffix_lenient` test. Used when detecting suffix-comma
        format (e.g. "John Ingram, V") where the post-comma position is
        unambiguous.
        """
        return all(self.is_suffix_lenient(piece) for piece in pieces)

    def is_rootname(self, piece: str) -> bool:
        """
        Is not a known title, suffix or prefix. Just first, middle, last names.
        """
        word = lc(piece)
        return word not in self.C.suffixes_prefixes_titles \
            and word not in self._derived_titles \
            and word not in self._derived_suffixes \
            and word not in self._derived_prefixes \
            and not self.is_an_initial(piece)

    def is_an_initial(self, value: str) -> bool:
        """
        Words with a single period at the end, or a single uppercase letter.

        Matches the ``initial`` regular expression in
        :py:data:`~nameparser.config.regexes.REGEXES`.
        """
        return bool(self.C.regexes.initial.match(value))

    def is_east_slavic_patronymic(self, piece: str) -> bool:
        """
        Return True if ``piece`` ends with a recognised East-Slavic patronymic
        suffix, checked against both Latin-script and Cyrillic patterns in
        ``self.C.regexes``.  Latin suffixes: ``-ovich``, ``-ovna``, ``-evich``,
        ``-evna``, ``-ichna``, and the irregular forms ``-ilyich``, ``-kuzmich``,
        ``-lukich``, ``-fomich``, ``-fokich``.  Cyrillic equivalents are matched
        by a separate pattern.
        """
        return bool(
            self.C.regexes.east_slavic_patronymic.search(piece)
            or self.C.regexes.east_slavic_patronymic_cyrillic.search(piece)
        )

    def is_turkic_patronymic_marker(self, piece: str) -> bool:
        """
        Return True if ``piece`` is exactly a recognised Turkic patronymic
        marker word (e.g. ``oglu``, ``qizi``, ``uly``), checked against both
        Latin-script and Cyrillic patterns in ``self.C.regexes``. Unlike
        East-Slavic patronymics, these are standalone marker words, not
        suffixes, so the match is whole-word rather than a suffix search.
        """
        return bool(
            self.C.regexes.turkic_patronymic_marker.match(piece)
            or self.C.regexes.turkic_patronymic_marker_cyrillic.match(piece)
        )

    # full_name parser

    @property
    def full_name(self) -> str:
        """The string output of the HumanName instance."""
        return str(self)

    @full_name.setter
    def full_name(self, value: str | bytes) -> None:
        self._apply_full_name(value, stacklevel=3)

    def _apply_full_name(self, value: str | bytes, *, stacklevel: int) -> None:
        # Shared by the setter and the constructor so each can call it
        # directly with a stacklevel that attributes the warning to *its own*
        # caller -- the constructor going through the setter would otherwise
        # add a frame and misattribute the warning to this module.
        self.original = value

        if isinstance(value, bytes):
            # deprecated 1.3.0, raises TypeError in 2.0 (#245)
            warnings.warn(
                "Passing bytes to HumanName is deprecated and will raise "
                "TypeError in 2.0; decode it first, e.g. "
                "value.decode('utf-8'). See "
                "https://github.com/derek73/python-nameparser/issues/245",
                DeprecationWarning,
                stacklevel=stacklevel,
            )
            self._full_name = value.decode(self.encoding)
        else:
            self._full_name = value

        self.parse_full_name()

    def collapse_whitespace(self, string: str) -> str:
        # collapse multiple spaces into single space
        string = self.C.regexes.spaces.sub(" ", string.strip())
        if string and self.C.regexes.commas.fullmatch(string[-1]):
            string = string[:-1]
        return string

    def pre_process(self) -> None:
        """

        This method happens at the beginning of the :py:func:`parse_full_name`
        before any other processing of the string aside from unicode
        normalization, so it's a good place to do any custom handling in a
        subclass. Runs :py:func:`squash_bidi`, :py:func:`parse_nicknames` and
        :py:func:`squash_emoji`.

        """
        self.squash_bidi()
        self.fix_phd()
        self.parse_nicknames()
        self.squash_emoji()

    def handle_east_slavic_patronymic_name_order(self) -> None:
        """
        When patronymic_name_order is enabled, detect Russian formal order
        (Surname GivenName Patronymic) and rotate to Western order.
        Fires only for no-comma, single-token first/middle/last where the last
        token is a patronymic and the middle token is not.  Title, suffix, and
        nickname parts do not affect this guard — reordering proceeds regardless
        of whether they are present.
        """
        if (
            not self._had_comma
            and len(self.first_list) == 1
            and len(self.middle_list) == 1
            and len(self.last_list) == 1
            and self.is_east_slavic_patronymic(self.last_list[0])
            and not self.is_east_slavic_patronymic(self.middle_list[0])
        ):
            self.first_list, self.middle_list, self.last_list = (
                self.middle_list,
                self.last_list,
                self.first_list,
            )

    def handle_turkic_patronymic_name_order(self) -> None:
        """
        When patronymic_name_order is enabled, detect the reversed Turkic
        formal order (Surname GivenName PatronymicRoot Marker) and rotate to
        Western order. Fires only for the strict 4-token, no-comma shape:
        single-token first/last and exactly two middle tokens, where the last
        token is a recognised Turkic patronymic marker.
        """
        if (
            not self._had_comma
            and len(self.first_list) == 1
            and len(self.middle_list) == 2
            and len(self.last_list) == 1
            and self.is_turkic_patronymic_marker(self.last_list[0])
        ):
            self.first_list, self.middle_list, self.last_list = (
                [self.middle_list[0]],
                [self.middle_list[1], self.last_list[0]],
                self.first_list,
            )

    def handle_non_first_name_prefix(self) -> None:
        """
        A leading prefix that is never a first name means the whole name is a
        surname -- fold first (and any middle) into last. Keys on the parsed
        first name, so a non-leading particle ("Jean de Mesnil") is untouched
        and title/suffix are preserved. The middle_list/last_list guard leaves a
        degenerate bare "de" as first="de" rather than inventing a surname.
        """
        if (len(self.first_list) == 1
                and self.is_non_first_name_prefix(self.first_list[0])
                and (self.middle_list or self.last_list)):
            self.last_list = self.first_list + self.middle_list + self.last_list
            self.first_list = []
            self.middle_list = []

    def handle_middle_name_as_last(self) -> None:
        """
        When middle_name_as_last is enabled, fold middle_list into last_list
        (prepended, preserving order) and clear middle_list. No-op when
        middle_list is already empty.
        """
        self.last_list = self.middle_list + self.last_list
        self.middle_list = []

    def post_process(self) -> None:
        """
        This happens at the end of the :py:func:`parse_full_name` after
        all other processing has taken place. Runs :py:func:`handle_firstnames`
        and :py:func:`handle_capitalization`.
        """
        self.handle_firstnames()
        self.handle_non_first_name_prefix()
        if self.C.patronymic_name_order:
            self.handle_east_slavic_patronymic_name_order()
            self.handle_turkic_patronymic_name_order()
        if self.C.middle_name_as_last:
            self.handle_middle_name_as_last()
        self.handle_capitalization()

    def fix_phd(self) -> None:
        _re = self.C.regexes.phd

        if match := _re.search(self._full_name):
            self.suffix_list.extend(match.groups())
            self._full_name = _re.sub("", self._full_name)

    def parse_nicknames(self) -> None:
        """
        Delimited content in the name is routed to either the nickname or
        maiden bucket, based on which of
        :py:attr:`~nameparser.config.Constants.nickname_delimiters` /
        :py:attr:`~nameparser.config.Constants.maiden_delimiters` the matching
        delimiter belongs to -- unless that content is suffix-shaped -- an
        unambiguous suffix_not_acronyms/suffix_acronyms member, or content
        ending in a period -- in which case it's left in place (undelimited)
        for normal downstream suffix/title/word parsing instead. This happens
        before any other processing of the name.

        Single quotes cannot span white space characters and must border
        white space to allow for quotes in names like O'Connor and Kawai'ae'a.
        Double quotes and parenthesis can span white space.

        By default, ``nickname_delimiters`` holds the three built-in
        delimiters (``quoted_word``, ``double_quotes`` and ``parenthesis``,
        resolved live from :py:attr:`~nameparser.config.Constants.regexes` so
        overriding e.g. ``CONSTANTS.regexes.parenthesis`` keeps affecting
        nickname parsing) and ``maiden_delimiters`` is empty. Move a key
        between the two dicts, e.g.
        ``maiden_delimiters['parenthesis'] = nickname_delimiters.pop('parenthesis')``,
        to route it to ``maiden`` instead, or add a new compiled pattern under
        any key to recognize an additional delimiter -- see the "Adding
        Custom Nickname Delimiters" and "Routing to Maiden Name" sections of
        the customization docs.
        """

        def handle_match(target_list: list[str]) -> Callable[['re.Match[str]'], str]:
            def _handle(m: 're.Match[str]') -> str:
                # Fall back to the whole match when the regex has no capturing
                # group (e.g. a custom override regex without one, like
                # EMPTY_REGEX) -- mirrors the old code's use of findall(), which
                # returns the whole match for group-less patterns.
                content = m.group(1) if m.lastindex else m.group(0)
                stripped = lc(content)
                # Inlined rather than calling self.is_suffix(content): is_suffix()
                # also rejects single-letter initials via is_an_initial(), which
                # isn't relevant here, and the suffix_acronyms_ambiguous exclusion
                # needs to be interleaved into the acronym branch specifically.
                # Acronym suffixes may have periods between every letter (e.g.
                # "M.D", "Ph.D") that aren't necessarily trailing, so -- exactly
                # like is_suffix() -- strip all periods before checking
                # suffix_acronyms/suffix_acronyms_ambiguous membership. Bare
                # `stripped` (lc() only strips leading/trailing periods) is still
                # used for suffix_not_acronyms, matching is_suffix()'s asymmetry.
                acronym_stripped = stripped.replace('.', '')
                is_unambiguous_suffix = (
                    stripped in self.C.suffix_not_acronyms
                    or (acronym_stripped in self.C.suffix_acronyms
                        and acronym_stripped not in self.C.suffix_acronyms_ambiguous)
                )
                if is_unambiguous_suffix or content.endswith('.'):
                    # Leave the bare content -- no delimiters -- so downstream
                    # word-splitting/suffix-matching sees it exactly as if it had
                    # never been wrapped in parens/quotes. is_suffix()/lc() only
                    # strip periods, never parens/quotes, so returning m.group(0)
                    # here (e.g. literal "(Ret)") would never match
                    # suffix_not_acronyms ("ret").
                    return content
                target_list.append(content)
                return ''
            return _handle

        # Same handle_match for every delimiter: suffix-shaped content is rare
        # in quotes but not impossible, and the logic is delimiter-agnostic,
        # so there's no reason to special-case parenthesis here. A string
        # delimiter value names a Constants.regexes entry, resolved via
        # getattr() so overriding e.g. self.C.regexes.parenthesis keeps
        # working; anything else is already a compiled pattern, added
        # directly by a caller. Unlike a caller directly querying
        # self.C.regexes (where RegexTupleManager's EMPTY_REGEX default for
        # an unknown attribute is harmless -- the caller sees the pattern and
        # can react to it), a bad string here is an internal cross-reference
        # the delimiter dict itself is responsible for keeping valid.
        # EMPTY_REGEX matches the empty string at every position, so
        # silently falling back to it would not just skip the delimiter --
        # handle_match() would fire on every zero-width match and append ''
        # into the bucket's list repeatedly, producing a truthy
        # whitespace-only nickname/maiden while leaving the real delimited
        # content (e.g. literal parentheses) unstripped. Fail loudly instead.
        for bucket, delimiters in (
            ('nickname', self.C.nickname_delimiters),
            ('maiden', self.C.maiden_delimiters),
        ):
            target_list = getattr(self, bucket + '_list')
            _handle_match = handle_match(target_list)
            for raw_pattern in delimiters.values():
                if isinstance(raw_pattern, re.Pattern):
                    _re = raw_pattern
                elif raw_pattern in self.C.regexes:
                    _re = getattr(self.C.regexes, raw_pattern)
                else:
                    raise ValueError(
                        f"{bucket}_delimiters references unknown regexes key {raw_pattern!r}. "
                        f"Known regexes keys: {sorted(self.C.regexes)}"
                    )
                self._full_name = _re.sub(_handle_match, self._full_name)

    def squash_emoji(self) -> None:
        """
        Remove emoji from the input string.
        """
        re_emoji = self.C.regexes.emoji
        if re_emoji and re_emoji.search(self._full_name):
            self._full_name = re_emoji.sub('', self._full_name)

    def squash_bidi(self) -> None:
        """
        Remove invisible bidirectional control characters from the input
        string. They carry no name content but stick to the parts they
        surround, so parsed attributes stop comparing equal to the clean name.
        """
        re_bidi = self.C.regexes.bidi
        if re_bidi and re_bidi.search(self._full_name):
            self._full_name = re_bidi.sub('', self._full_name)

    def handle_firstnames(self) -> None:
        """
        If there are only two parts and one is a title, assume it's a last name
        instead of a first name. e.g. Mr. Johnson. Unless it's a special title
        like "Sir", then when it's followed by a single name that name is always
        a first name.
        """
        if self.title \
                and len(self) == 2 \
                and lc(self.title) not in self.C.first_name_titles:
            self.last, self.first = self.first, self.last

    def parse_full_name(self) -> None:
        """

        The main parse method for the parser. This method is run upon
        assignment to the :py:attr:`full_name` attribute or instantiation.

        Basic flow is to hand off to :py:func:`pre_process` to handle
        nicknames. It then splits on commas and chooses a code path depending
        on the number of commas.

        :py:func:`parse_pieces` then splits those parts on spaces and
        :py:func:`join_on_conjunctions` joins any pieces next to conjunctions.
        """

        self.title_list = []
        self.first_list = []
        self.middle_list = []
        self.last_list = []
        self.suffix_list = []
        self.nickname_list = []
        self.maiden_list = []

        # each parse derives these from scratch; entries from a previous
        # full_name must not influence this one
        self._derived_titles = set()
        self._derived_suffixes = set()
        self._derived_conjunctions = set()
        self._derived_prefixes = set()

        self.pre_process()

        self._full_name = self.collapse_whitespace(self._full_name)

        # break up full_name by commas
        parts = [x.strip() for x in self.C.regexes.commas.split(self._full_name)]
        self._had_comma = len(parts) > 1

        log.debug("full_name: %s", self._full_name)
        log.debug("parts: %s", parts)

        if len(parts) == 1:

            # no commas, title first middle middle middle last suffix
            #            part[0]

            pieces = self.parse_pieces(parts)
            pieces = self._join_bound_first_name(pieces, reserve_last=True)
            p_len = len(pieces)
            for i, piece in enumerate(pieces):
                try:
                    nxt = pieces[i + 1]
                except IndexError:
                    nxt = None

                # title must have a next piece, unless it's just a title
                if not self.first \
                        and (nxt or p_len == 1) \
                        and self.is_leading_title(piece):
                    self.title_list.append(piece)
                    continue
                if not self.first:
                    if p_len == 1 and self.nickname:
                        self.last_list.append(piece)
                        continue
                    self.first_list.append(piece)
                    continue
                if self.are_suffixes(pieces[i+1:]) or \
                        (
                            # if the next piece is the last piece and a roman
                            # numeral but this piece is not an initial
                            nxt is not None and \
                            self.is_roman_numeral(nxt) and i == p_len - 2
                            and not self.is_an_initial(piece)
                ):
                    # any piece reaching this check as the final piece lands
                    # here: are_suffixes() is vacuously True for the empty
                    # tail, making this the last-name branch as well as the
                    # suffix branch
                    self.last_list.append(piece)
                    self.suffix_list += pieces[i+1:]
                    break

                self.middle_list.append(piece)
        else:
            # if all the end parts are suffixes and there is more than one piece
            # in the first part. (Suffixes will never appear after last names
            # only, and allows potential first names to be in suffixes, e.g.
            # "Johnson, Bart"

            post_comma_pieces = self.parse_pieces(parts[1].split(' '), 1)

            # Detection must see the delimiter-expanded words too, or a
            # delimiter-joined suffix group like "RN - CRNA" would never be
            # recognized as suffix-comma format in the first place.
            suffix_delimiter_pieces = [word for part in self.expand_suffix_delimiter(parts[1])
                                        for word in part.split(' ')]

            if self.are_suffixes_after_comma(suffix_delimiter_pieces) \
                    and len(parts[0].split(' ')) > 1:

                # suffix comma:
                # title first middle last [suffix], suffix [suffix] [, suffix]
                #               parts[0],          parts[1:...]

                for part in parts[1:]:
                    # skip empty segments from doubled commas, mirroring the
                    # parts[2:] guard in the lastname-comma path below
                    if part:
                        self.suffix_list += self.expand_suffix_delimiter(part)
                pieces = self.parse_pieces(parts[0].split(' '))
                pieces = self._join_bound_first_name(pieces, reserve_last=True)
                log.debug("pieces: %s", str(pieces))
                for i, piece in enumerate(pieces):
                    try:
                        nxt = pieces[i + 1]
                    except IndexError:
                        nxt = None

                    if not self.first \
                            and (nxt or len(pieces) == 1) \
                            and self.is_leading_title(piece):
                        self.title_list.append(piece)
                        continue
                    if not self.first:
                        self.first_list.append(piece)
                        continue
                    if self.are_suffixes(pieces[i+1:]):
                        # any piece reaching this check as the final piece
                        # lands here: are_suffixes() is vacuously True for the
                        # empty tail, making this the last-name branch as well
                        # as the suffix branch
                        self.last_list.append(piece)
                        self.suffix_list = pieces[i+1:] + self.suffix_list
                        break
                    self.middle_list.append(piece)
            else:

                # lastname comma:
                # last [suffix], title first middles[,] suffix [,suffix]
                #      parts[0],      parts[1],              parts[2:...]

                log.debug("post-comma pieces: %s", str(post_comma_pieces))
                post_comma_pieces = self._join_bound_first_name(post_comma_pieces, reserve_last=False)

                # lastname part may have suffixes in it
                lastname_pieces = self.parse_pieces(parts[0].split(' '), 1)
                for piece in lastname_pieces:
                    # the first one is always a last name, even if it looks like
                    # a suffix
                    if self.is_suffix(piece) and len(self.last_list) > 0:
                        self.suffix_list.append(piece)
                    else:
                        self.last_list.append(piece)

                for i, piece in enumerate(post_comma_pieces):
                    try:
                        nxt = post_comma_pieces[i + 1]
                    except IndexError:
                        nxt = None

                    if not self.first \
                            and (nxt or len(post_comma_pieces) == 1) \
                            and self.is_leading_title(piece):
                        self.title_list.append(piece)
                        continue
                    if not self.first:
                        self.first_list.append(piece)
                        continue
                    # A trailing token in a two-part lastname-comma name is
                    # unambiguously positioned, so use the lenient test that
                    # accepts suffix_not_acronyms members is_suffix() would
                    # veto as initials. When parts[2] exists the caller
                    # already declared an explicit suffix via comma (e.g.
                    # 'Doe, Rev. John V, Jr.'), making the trailing token
                    # more likely a middle initial.
                    if self.is_suffix(piece) or \
                            (nxt is None and len(parts) == 2
                             and self.is_suffix_lenient(piece)):
                        self.suffix_list.append(piece)
                        continue
                    self.middle_list.append(piece)
                for part in parts[2:]:
                    # skip empty segments from doubled commas ("Doe, John,, Jr.")
                    # without dropping the segments that follow them
                    if part:
                        self.suffix_list += self.expand_suffix_delimiter(part)

        self.post_process()

    def parse_pieces(self, parts: Iterable[str], additional_parts_count: int = 0) -> list[str]:
        """
        Split parts on spaces and remove commas, join on conjunctions and
        lastname prefixes. Tokens that are empty after stripping spaces and
        commas are dropped, so the returned pieces never contain empty
        strings. If parts have periods in the middle, try splitting
        on periods and check if the parts are titles or suffixes. If they are,
        register the periods-joined part as a derived title/suffix for this
        parse so it will be recognized; the constants are not modified.

        :param list parts: name part strings from the comma split
        :param int additional_parts_count:

            if the comma format contains other parts, we need to know
            how many there are to decide if things should be considered a
            conjunction.
        :return: pieces split on spaces and joined on conjunctions
        :rtype: list
        """

        output: list[str] = []
        for part in parts:
            if not isinstance(part, (str, bytes)):
                raise TypeError("Name parts must be strings. "
                                f" Got {type(part)}")
            # drop tokens that strip to nothing (e.g. from a bare "," input or
            # an empty comma segment) so no empty piece reaches the parse
            # loops and the public *_list attributes
            output += [s for s in (x.strip(' ,') for x in part.split(' ')) if s]

        # If part contains periods, check if it's multiple titles or suffixes
        # together without spaces. If so, register the periods-joined part as
        # a derived title/suffix for this parse so it gets recognized later
        for part in output:
            # if this part has a period not at the beginning or end
            if self.C.regexes.period_not_at_end and self.C.regexes.period_not_at_end.match(part):
                # split on periods, any of the split pieces titles or suffixes?
                # ("Lt.Gov.")
                period_chunks = part.split(".")
                titles = list(filter(self.is_title,  period_chunks))
                suffixes = list(filter(self.is_suffix, period_chunks))

                # register the part so it will be found by the is_* checks
                if titles:
                    self._derived_titles.add(lc(part))
                    continue
                if suffixes:
                    self._derived_suffixes.add(lc(part))
                    continue

        return self.join_on_conjunctions(output, additional_parts_count)

    def join_on_conjunctions(self, pieces: list[str], additional_parts_count: int = 0) -> list[str]:
        """
        Join conjunctions to surrounding pieces. Title- and prefix-aware. e.g.:

            ['Mr.', 'and', 'Mrs.', 'John', 'Doe'] ==>
                            ['Mr. and Mrs.', 'John', 'Doe']

            ['The', 'Secretary', 'of', 'State', 'Hillary', 'Clinton'] ==>
                            ['The Secretary of State', 'Hillary', 'Clinton']

        When joining titles, registers the newly formed piece as a derived
        title for the current parse so it will be recognized correctly later
        in the same parse. E.g. while parsing the example names above,
        'The Secretary of State' and 'Mr. and Mrs.' are treated as titles.
        The configuration in ``self.C`` is never modified.

        :param list pieces: name pieces strings after split on spaces
        :param int additional_parts_count:
        :return: new list with piece next to conjunctions merged into one piece
            with spaces in it.
        :rtype: list

        """
        length = len(pieces) + additional_parts_count
        # don't join on conjunctions if there's only 2 parts
        if length < 3:
            return pieces

        rootname_pieces = [p for p in pieces if self.is_rootname(p)]
        total_length = len(rootname_pieces) + additional_parts_count

        # find all the conjunctions, join any conjunctions that are next to each
        # other, then join those newly joined conjunctions and any single
        # conjunctions to the piece before and after it
        conj_index = [i for i, piece in enumerate(pieces)
                      if self.is_conjunction(piece)]

        contiguous_conj_i = group_contiguous_integers(conj_index)

        # process ranges in reverse so deleting one range doesn't shift the
        # indices of ranges still to be processed
        for cont_i in reversed(contiguous_conj_i):
            new_piece = " ".join(pieces[cont_i[0]: cont_i[1]+1])
            pieces[cont_i[0]:cont_i[1]+1] = [new_piece]
            # register newly joined conjunctions to be found later this parse
            self._derived_conjunctions.add(lc(new_piece))

        if len(pieces) == 1:
            # if there's only one piece left, nothing left to do
            return pieces

        # refresh conjunction index locations
        conj_index = [i for i, piece in enumerate(pieces) if self.is_conjunction(piece)]

        def register_joined_piece(new_piece: str, neighbor: str) -> None:
            if self.is_title(neighbor):
                # when joining to a title, make new_piece a title too
                self._derived_titles.add(lc(new_piece))
            if self.is_prefix(neighbor):
                # when joining to a prefix, make new_piece a prefix too, so
                # e.g. "von" + "und" bridges into "von und" and can still
                # chain onto a following prefix/lastname (see "von und zu")
                self._derived_prefixes.add(lc(new_piece))

        def shift_conj_index(past: int, by: int) -> None:
            # after removing pieces at/after `past`, indices of the
            # remaining conjunctions need to shift down by `by`
            for j, val in enumerate(conj_index):
                if val > past:
                    conj_index[j] = val - by

        for i in conj_index:
            if len(pieces[i]) == 1 and total_length < 4 and pieces[i].isalpha():
                # if there are only 3 total parts (minus known titles, suffixes
                # and prefixes) and this conjunction is a single letter, prefer
                # treating it as an initial rather than a conjunction.
                # http://code.google.com/p/python-nameparser/issues/detail?id=11
                continue

            start = max(0, i - 1)
            end = min(len(pieces), i + 2)
            new_piece = " ".join(pieces[start:end])
            neighbor = pieces[start] if start < i else pieces[end - 1]
            register_joined_piece(new_piece, neighbor)
            pieces[start:end] = [new_piece]
            shift_conj_index(past=i, by=end - start - 1)

        # join prefixes to following lastnames: ['de la Vega'], ['van Buren']
        i = 0
        while i < len(pieces):
            # total_length >= 1 covers essentially all real input, so this
            # treats any leading piece as a first name rather than a prefix.
            leading_first_name = i == 0 and total_length >= 1
            if not self.is_prefix(pieces[i]) or leading_first_name:
                i += 1
                continue

            # absorb any immediately-adjacent prefixes into one contiguous run
            # e.g. "von und zu der" ==> chain them all before looking further
            j = i + 1
            while j < len(pieces) and self.is_prefix(pieces[j]):
                j += 1

            # then join everything after the run until the next prefix or suffix
            while j < len(pieces) and not self.is_prefix(pieces[j]) and not self.is_suffix(pieces[j]):
                j += 1

            pieces[i:j] = [' '.join(pieces[i:j])]
            i += 1

        log.debug("pieces: %s", pieces)
        return pieces

    # Capitalization Support

    def cap_word(self, word: str, attribute: HumanNameAttributeT) -> str:
        if (self.is_prefix(word) and attribute in ('last', 'middle')) \
                or self.is_conjunction(word):
            return word.lower()
        exceptions = self.C.capitalization_exceptions
        key = lc(word)
        for k in (key, key.replace('.', '')):
            if k in exceptions:
                return exceptions[k]
        mac_match = self.C.regexes.mac.match(word)
        if mac_match:
            def cap_after_mac(m: re.Match) -> str:
                return m.group(1).capitalize() + m.group(2).capitalize()
            return self.C.regexes.mac.sub(cap_after_mac, word)
        else:
            return word.capitalize()

    def cap_piece(self, piece: str, attribute: HumanNameAttributeT) -> str:
        if not piece:
            return ""

        def replacement(m: re.Match) -> str:
            return self.cap_word(m.group(0), attribute)

        return self.C.regexes.word.sub(replacement, piece)

    def capitalize(self, force: bool | None = None) -> None:
        """
        The HumanName class can try to guess the correct capitalization of name
        entered in all upper or lower case. By default, it will not adjust the
        case of names entered in mixed case. To run capitalization on all names
        pass the parameter `force=True`.

        :param bool force: Forces capitalization of mixed case strings. This
            parameter overrides rules set within
            :py:class:`~nameparser.config.CONSTANTS`.

        **Usage**

        .. doctest:: capitalize

            >>> name = HumanName('bob v. de la macdole-eisenhower phd')
            >>> name.capitalize()
            >>> str(name)
            'Bob V. de la MacDole-Eisenhower Ph.D.'
            >>> # Don't touch good names
            >>> name = HumanName('Shirley Maclaine')
            >>> name.capitalize()
            >>> str(name)
            'Shirley Maclaine'
            >>> name.capitalize(force=True)
            >>> str(name)
            'Shirley MacLaine'

        """
        name = str(self)
        force = self.C.force_mixed_case_capitalization \
            if force is None else force

        if not force and not (name == name.upper() or name == name.lower()):
            return
        self.title_list = self.cap_piece(self.title, 'title').split()
        self.first_list = self.cap_piece(self.first, 'first').split()
        self.middle_list = self.cap_piece(self.middle, 'middle').split()
        self.last_list = self.cap_piece(self.last, 'last').split()
        # suffix is stored comma-separated ("Ph.D., J.D."), not space-separated
        self.suffix_list = [s for s in self.cap_piece(self.suffix, 'suffix').split(', ') if s]

    def handle_capitalization(self) -> None:
        """
        Handles capitalization configurations set within
        :py:class:`~nameparser.config.CONSTANTS`.
        """
        if self.C.capitalize_name:
            self.capitalize()
