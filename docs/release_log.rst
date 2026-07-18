Release Log
===========
* 2.0.0 - unreleased

    **Locale packs (opt-in)**

    - Add ``nameparser.locales`` with the first two packs: ``locales.RU`` (East Slavic patronymic order) and ``locales.TR_AZ`` (Turkic patronymic markers). Packs are pure data folded in at ``parser_for(locales.RU)``; they compose (``parser_for(locales.RU, locales.TR_AZ)`` unions the rules) and are never auto-detected -- there is no reliable way to detect a name's language (closes the pack half of #270; #271/#272/#146 stay staged for 2.x)
    - The CLI gains ``--locale CODE`` (``python -m nameparser --locale ru "..."``)
    - Add non-Latin vocabulary to the default lexicon (#269): Cyrillic, Greek, Arabic and Hebrew titles, conjunctions, and name particles -- native-script entries cannot collide with Latin-script names. Deferred pending vetting: Cyrillic ``мл``/``ст`` suffixes and the bare Greek ``κ`` title (it collides with the initial+surname shape). Behavior note: ``محمد بن سلمان`` now chains ``بن`` onto the family name where 1.x read it as a middle name

    **Behavior Changes (draft)**

    .. note::
       This section is a **draft**, generated from the v1-vs-2.0
       differential harness (``tools/differential/``) run against the
       pre-M12 v1 test corpus (486 name strings). It will be replaced
       by hand-written release notes before 2.0 ships; entries below
       are grouped by the harness's classification and reference the
       ``tests/v2/cases.py`` row (if any) that pins the new behavior.

    - Fix ``"Andrews, M.D."``-shaped input: the lone strict-suffix-or-title piece after a comma (e.g. ``"Smith, Dr."``, ``"Andrews, M.D."``) was routed to ``first`` in 1.x; 2.0 routes it to ``suffix``/``title`` instead, since the pre-comma piece is definitionally the family name (``tests/v2/cases.py`` rows ``family_comma_lone_suffix_piece``, ``family_comma_lone_title``; verified live against 1.4.0 -- 1/486 corpus names diff, all others parity)
    - Fix a lone recognized trailing suffix (e.g. ``"Johnson PhD"``, ``"Mr. Johnson PhD"``) being routed to ``first``/``last`` in 1.x when no comma is present; 2.0 keeps a recognized suffix in ``suffix`` (``tests/v2/cases.py`` rows ``suffix_stays_suffix``, ``suffix_stays_suffix_title``; not present in the differential corpus -- no v1 test string exercises the bare two-token shape, so this is unverified against 1.4 live but pinned by the case table)
    - Fix maiden-name markers (``née``/``nee``/``born``/``geb.``/``roz.``) being folded into ``middle``/``last`` in 1.x (e.g. ``"Jane Smith née Jones"`` → ``middle="Smith née"``); 2.0 recognizes the marker and routes the following name to the new ``maiden`` field (closes #274; ``tests/v2/cases.py`` row ``maiden_marker``; not present in the differential corpus)
    - Data change: ``ma``/``do`` added to ``suffix_acronyms_ambiguous`` -- ambiguous acronyms count as suffixes only when written with periods, so a bare common surname (``"Jack Ma"``, ``"Anh Do"``) keeps its family name under 2.0's keep-recognized-suffixes routing, matching 1.4's output (``tests/v2/cases.py`` row ``ambiguous_surname_acronyms``). Side effect: parenthesized/quoted ``"(MA)"``/``"(DO)"`` (no periods) no longer escape to ``suffix`` the way 1.x did -- they now fall through to nickname parsing like any other ambiguous-acronym delimited content. Not present in the differential corpus
    - Change suffix-delimiter rendering: with a custom ``Policy``/``Constants`` suffix delimiter configured (e.g. ``suffix_delimiter="/"``, ``"John Smith, RN/CRNA"``), 1.x split the token and rendered ``suffix="RN, CRNA"``; 2.0 keeps the no-space delimiter-core token whole (``suffix="RN/CRNA"``) -- role assignment is unchanged, only rendering differs (anti-#100, migration plan deviation 5; ``tests/v2/cases.py`` row ``suffix_delimiter_no_space_core``). Only fires with a non-default policy, so it does not appear in the (default-policy) differential corpus
    - Change ``comparison_key()``/``matches()`` (both APIs) to fold components with ``str.casefold()`` where 1.4 used ``str.lower()``: Unicode case-pair forms now compare equal -- ``"STRASSE"`` matches ``"Straße"``, and a Greek final-sigma variant matches its regular-sigma form. Strictly more permissive (anything 1.4 matched still matches); parse output is unaffected -- vocabulary normalization itself uses ``lower()``, v1-parity (``tests/v2/test_types.py`` row ``test_matches_casefolds_unicode_case_pairs``)
    - Change delimiter-overlap precedence in the 2.0 API: a pair listed in ``Policy.maiden_delimiters`` is dropped from the effective ``nickname_delimiters`` set (maiden wins), so ``Policy(maiden_delimiters={("(", ")")})`` alone routes parenthesized content to ``maiden`` -- no need to rebuild the nickname set. The default nickname set is now the public ``DEFAULT_NICKNAME_DELIMITERS`` constant. The 1.x facade keeps v1's nickname-wins precedence on overlap via a shim-side pre-subtraction, so no ``HumanName`` behavior changes (``tests/v2/cases.py`` row ``maiden_delimiters_win_when_shared``; ``tests/v2/test_config_shim.py`` row ``test_snapshot_overlap_keeps_v1_nickname_precedence``)
    - Recognize typographic nickname delimiters by default in BOTH APIs (closes #273): smart quotes (``“Jack”``), German/Polish low-high quotes (``„Hansi“``), Swedish right-right quotes (``”Ann”``), guillemets in both directions (``«Petit»``, ``»Hansi«``, inner spacing tolerated), CJK corner brackets (``「タロ」``/``『ハナ』``), and fullwidth parentheses. In 1.x these leaked into ``middle`` as literal text. Curly *single* quotes stay excluded (U+2019 is the apostrophe in "O’Connor" -- pinned by ``curly_apostrophe_stays_literal``). The v1 keyed idioms work on the new named sentinels (``smart_double_quotes``, ``guillemets``, ...). A delimiter character consumed by another pair's extraction no longer emits a spurious ``unbalanced-delimiter`` ambiguity (``tests/v2/cases.py`` rows ``*_nickname``; ``tests/v2/pipeline/test_extract.py``). Not present in the differential corpus

    Everything else in the 486-name differential corpus (built from the
    v1 test banks as of commit ``2d5d8c2``, pre-dating the M12 test
    reconciliation) parses identically between nameparser 1.4.0 and
    this working tree; see ``tools/differential/README.md`` for how to
    reproduce the comparison.

* 1.4.0 - July 12, 2026

    - Add ``Constants.copy()``, a detached deep copy that preserves the source instance's current customizations (unlike ``Constants()``, which always starts from library defaults) -- useful as ``CONSTANTS.copy()`` for a private snapshot of the shared config (#260)
    - Deprecate passing ``constants=None`` to ``HumanName`` (or assigning ``hn.C = None``): it silently builds a fresh ``Constants()``, discarding any customizations the caller may have expected to carry over from the shared ``CONSTANTS``. Emits ``DeprecationWarning``; will raise ``TypeError`` in 2.0. Use ``constants=Constants()`` for fresh library defaults or ``constants=CONSTANTS.copy()`` for a private snapshot instead (closes #260)
    - Deprecate assigning ``Constants.empty_attribute_default`` for removal in 2.0 (#255): once ``None`` support goes, the only legal value left is the default ``''``, so a dial with one position isn't configuration. Emits ``DeprecationWarning``; reading the attribute is unaffected
    - Deprecate unknown-key attribute access on ``TupleManager``/``RegexTupleManager`` (``CONSTANTS.regexes.typo``, ``CONSTANTS.capitalization_exceptions.typo``, etc.) for removal in 2.0 (#256): a misspelled or omitted key currently degrades silently (``None``/``EMPTY_REGEX``) with no traceback pointing at the typo. Emits ``DeprecationWarning`` naming the miss and the known keys; will raise ``AttributeError`` in 2.0. ``.get()`` remains available for intentional soft access
    - Deprecate ``HumanName`` slice access (``name[1:-3]``) and item assignment (``name['first'] = value``) for removal in 2.0 (#258): field access by position has no real use case, and item assignment duplicates plain attribute assignment. Both emit ``DeprecationWarning``; string-key access (``name['first']``) is unaffected
    - Deprecate ``SetManager.add_with_encoding()`` itself for removal in 2.0 (#245), regardless of argument type: use ``add()`` instead (decoding bytes first). Previously only the ``bytes`` path warned; the ``str`` path was silent even though the whole method goes away
    - Deprecate loading a legacy-format ``Constants`` pickle (written by nameparser <= 1.2.x, before the 1.3.0 pickle fix) for removal in 2.0 (#279): ``__setstate__``'s migration shim currently skips the stale computed-property key silently. Emits ``DeprecationWarning`` once per call telling users to re-pickle; will raise ``ValueError`` in 2.0
    - Fix the ``"Lastname, Firstname"`` comma format not being recognized when the input uses the Arabic comma ``،`` (U+060C, the standard comma in Arabic/Persian/Urdu text) or the fullwidth CJK comma ``，`` (U+FF0C) instead of the ASCII comma: both variants now also split the format and no longer leak into the parsed output (closes #265)

* 1.3.1 - July 11, 2026

    - Fix invisible Unicode bidirectional control characters (LRM/RLM/ALM, the embedding/override marks, and the isolates U+2066–U+2069) surviving parsing and sticking to ``first``/``last``/etc., so a copy-pasted right-to-left name silently failed equality and dedup. They are now stripped in preprocessing like emoji; disable via ``CONSTANTS.regexes.bidi = False`` (closes #266)
    - Fix ``str()`` corrupting name text containing the substring ``"None"`` when ``empty_attribute_default`` is ``None`` (e.g. ``"Nonez Smith"`` rendered as ``"z Smith"``): empty attributes are now substituted as ``''`` before the format string is applied, instead of scrubbing the interpolated ``"None"`` from the output afterward (closes #254)

* 1.3.0 - July 5, 2026

    **Breaking Changes & Deprecations**

    - Deprecate ``HumanName.__eq__`` and ``__hash__`` for removal in 2.0 (#223): the current design's three promises — case-insensitive equality, equality with plain strings, and hashability — are mutually inconsistent (equal objects can hash differently), equality depends on ``string_format``, and ``maiden`` is invisible to it. Both now emit ``DeprecationWarning`` naming the replacement; behavior is otherwise unchanged until 2.0 (closes #224)
    - Deprecate ``bytes`` input for removal in 2.0 (#245): passing ``bytes`` to ``HumanName``/``full_name`` or to ``SetManager.add()``/``add_with_encoding()`` now emits ``DeprecationWarning`` — decode first, e.g. ``value.decode('utf-8')``. The ``encoding`` constructor argument is deprecated with it
    - Deprecate ``SetManager.__call__`` for removal in 2.0 (#243): calling a manager returns the raw underlying set, so mutating the result bypasses normalization and cache invalidation; iterate the manager or copy with ``set(manager)`` instead
    - Add ``SetManager.discard()``, and deprecate ``remove()`` of a *missing* member (#243): it currently does nothing but will raise ``KeyError`` in 2.0, matching ``set.remove``; use ``discard()`` for intentional ignore-missing removal. Removing present members is unchanged and does not warn
    - Fix ``HumanName`` acting as its own iterator with a stored cursor: breaking out of a loop, iterating in nested loops, or calling ``len(name)`` mid-loop corrupted subsequent iteration; ``iter(name)`` now returns a fresh independent iterator each time. ``next(name)`` on the instance itself (undocumented) now raises ``TypeError`` — call ``next(iter(name))`` instead (closes #225)
    - Remove the vestigial ``unparsable`` attribute: the guard that was meant to set it has been unreachable since 2013 (v0.2.9), so it has reported ``False`` for every parsed name for over a decade; check ``len(name) == 0`` to detect an empty parse
    - Remove ``__ne__``; Python 3 derives ``!=`` from ``__eq__`` automatically
    - Change internal initials helper ``__process_initial__`` to ``_process_initial``: double-underscore-both-sides names are reserved for Python special methods; subclasses overriding the old name must rename their override
    - Change ``REGEXES`` from a ``set`` of ``(name, pattern)`` tuples to a ``dict``, so a duplicate name is a visible overwrite in the source instead of a nondeterministic winner at import time; code iterating ``REGEXES`` directly now gets keys instead of pairs — use ``.items()`` (#227)
    - Change ``CAPITALIZATION_EXCEPTIONS`` from a tuple of ``(key, value)`` tuples to a ``dict``; code iterating it directly now gets keys instead of pairs — use ``.items()`` (#233)

    **Behavior Changes (affect existing parse output)**

    - Add ``bound_first_names`` set to ``Constants``; bound Arabic given-name
      prefixes (``abdul``, ``abu``, etc.) now join forward to form a single first
      name (e.g. ``"abdul salam ahmed salem"`` → ``first="abdul salam"``,
      ``middle="ahmed"``, ``last="salem"``). Disable via
      ``CONSTANTS.bound_first_names.clear()``. **Default-on: changes parsing
      output for names with these prefixes.** (#150)
    - Treat an unrecognized, multi-letter token ending in a period in the leading title run (before the first name is set), e.g. ``"Major."``, as a ``title`` instead of a ``first`` name; internal-period abbreviations (``"E.T."``) and single-letter initials (``"J."``) are unaffected. **Default-on: changes parsing of names with a leading unknown period-abbreviation** (closes #109)
    - Fix parsing writing back into the ``Constants`` it reads (usually the shared module-level ``CONSTANTS``): pieces derived while parsing a name — period-joined titles/suffixes like ``"Lt.Gov."`` and conjunction-joined pieces like ``"Mr. and Mrs."`` or ``"von und zu"`` — are now tracked per parse instead of being permanently ``add()``-ed to the config, so parse results no longer depend on which names were parsed earlier in the process and parsing no longer mutates shared state across threads
    - Fix ``__hash__`` to lowercase the name like ``__eq__`` does, so equal ``HumanName`` instances hash equal and behave correctly in sets and dicts

    **New comparison methods**

    - Add ``matches()`` and ``comparison_key()`` for explicit name comparison: ``matches()`` compares parsed components case-insensitively (parsing ``str`` arguments first, so ``name.matches("Smith, John")`` and ``name.matches("John Smith")`` both match) and ``comparison_key()`` returns a hashable tuple of the seven components for dedup, dict keys, and sorting (#224)

    **New name fields**

    - Add a first-class ``maiden`` field and ``maiden_delimiters`` to ``Constants``, so a delimiter (e.g. parenthesis) can be routed to ``maiden`` instead of ``nickname`` for alternate/maiden surnames, e.g. ``"Baker (Johnson), Jenny"`` (closes #22)
    - Add ``given_names`` (and ``given_names_list``) attribute as aggregate of first and middle names, mirroring ``surnames`` (closes #157)
    - Add ``last_base``, ``last_prefixes`` (and ``_list`` variants) for splitting last-name prefix particles (tussenvoegsels) from the core surname (#130, #132)

    **New customization options**

    - Add ``initials_separator`` to ``Constants`` and ``HumanName`` to control spacing between consecutive initials within a name group (#171)
    - Add ``suffix_delimiter`` to ``Constants`` and ``HumanName`` for parsing suffixes separated by arbitrary delimiters, e.g. ``"RN - CRNA"`` (#156)
    - Add ``nickname_delimiters`` to ``Constants`` for registering additional nickname-delimiter regex patterns at runtime, without subclassing (closes #110, #112)
    - Add ``suffix_acronyms_ambiguous`` to ``Constants`` for acronym suffixes that also read as given-name nicknames (e.g. ``"JD"``, ``"Ed"``), used when disambiguating parenthesized/quoted content (#111)

    **International name support**

    - Add ``patronymic_name_order`` flag to ``Constants`` and ``HumanName`` for opt-in detection and reordering of Russian formal-order names (Surname GivenName Patronymic) (#85)
    - Add Turkic (Azerbaijani/Central-Asian) patronymic detection to ``patronymic_name_order``, rotating the reversed 4-token formal shape (``Surname GivenName PatronymicRoot Marker``, e.g. ``oglu``/``qizi``) into Western order (#185)
    - Add ``middle_name_as_last`` flag to ``Constants`` and ``HumanName`` for opt-in folding of middle names into the last name, for naming systems with no middle-name concept (e.g. Arabic patronymic chaining) (#133)
    - Add ``non_first_name_prefixes`` to ``Constants``: a leading particle that is never a first name (e.g. ``"de Mesnil"``, ``"dos Santos"``) now parses as a surname with an empty first name, instead of treating the particle as the first name (closes #121)
    - Add international honorifics to ``TITLES`` (#187)
    - Add German/Austrian nobility and ecclesiastical titles to ``TITLES`` (closes #101)
    - Add German/Dutch last-name prefixes and title/degree suffixes; fix ``join_on_conjunctions()`` to register multi-word prefix chains (e.g. ``"von und zu"``) as prefixes, mirroring existing title handling (closes #18)

    **Parsing fixes**

    - Fix suffix boundary lookup for prefixed last names with a title before and after (e.g. ``"dr Vincent van Gogh dr"`` producing a corrupted middle name) (closes #100)
    - Fix a repeated prefix word in a prefix chain (e.g. ``"Juan de la de la Vega"``) silently dropping the earlier occurrence in ``join_on_conjunctions()``: value-based ``pieces.index(prefix)`` lookups re-found the wrong occurrence once the list had already been mutated by prior joins; prefix positions are now tracked positionally instead of re-derived by value (closes #208)
    - Fix a trailing suffix being silently dropped after an empty comma segment, e.g. ``"Doe, John,, Jr."`` losing the ``"Jr."``
    - Fix degenerate comma input (a bare ``","`` or an empty comma segment, e.g. ``"Doe,, Jr."``, ``"John Doe, Jr.,,"``) leaving an empty-string member in ``first_list``, ``last_list``, or ``suffix_list``; whitespace-only tokens assigned via the setters are dropped the same way
    - Fix suffix-shaped parenthesized/quoted content (e.g. ``"(Ret)"``, ``"(MBA)"``) being misclassified as a nickname instead of a suffix (closes #111)
    - Fix single-character symbol conjunctions (e.g. ``"&"``, ``"/"``) being ignored in short names (#173)
    - Fix recognition of single-letter roman numeral suffixes (e.g. ``"I"``, ``"V"``) in suffix-comma format (closes #136)
    - Fix recognition of trailing ``suffix_not_acronyms`` (e.g. ``"Jr."``) in lastname-comma format (closes #144)
    - Fix missing comma between ``'msc'`` and ``'mscmsm'`` in ``suffix_acronyms``, which silently concatenated them into a bogus ``'mscmscmsm'`` entry (#111)
    - Fix ``'apn aprn'`` split into separate ``suffix_acronyms`` entries so each is recognized independently (closes #155)

    **Formatting and output fixes**

    - Fix ``IndexError`` in ``initials()``/``initials_list()`` when a ``*_list`` attribute was assigned directly with an element containing unnormalized whitespace (e.g. ``name.middle_list = ['Q  R']``), bypassing the parser's whitespace normalization (closes #232)
    - Fix ``initials()`` emitting a stray empty initial (e.g. ``"J. . V."``) -- or raising ``TypeError`` when ``empty_attribute_default`` is ``None`` -- for name parts with no initialable words, e.g. a prefix-only middle name like ``"de la"``
    - Fix capitalization of suffix acronyms written with dots, e.g. ``"M.D."`` (closes #141)
    - Fix extra whitespace before punctuation in ``str()`` output when a ``string_format`` field is empty (closes #139)
    - Fix spurious leading space in surnames and empty token in suffix list after ``capitalize()`` with an empty middle or suffix (#164)

    **API correctness and cleanup**

    - Fix the five non-cached-union ``SetManager``-backed ``Constants`` attributes (``first_name_titles``, ``conjunctions``, ``bound_first_names``, ``non_first_name_prefixes``, ``suffix_acronyms_ambiguous``) accepting non-``SetManager`` assignment silently (e.g. ``constants.conjunctions = 'and'``), degrading membership checks into substring tests with no error; assignment now raises ``TypeError`` like the four cached-union attributes already did (closes #241)
    - Fix ``HumanName.C`` accepting an invalid ``constants`` value on post-construction assignment (e.g. ``hn.C = 'garbage'``), bypassing the constructor's validation and failing later with an unrelated ``AttributeError``; ``C`` is now a property that validates on assignment too (closes #239)
    - Fix ``TupleManager`` (and ``RegexTupleManager``) accepting a bare string/bytes argument (raising a cryptic ``dict``-internals ``ValueError``) or an iterable of 2-character strings (silently shredding each into a key/value pair, e.g. ``Constants(capitalization_exceptions=['ii'])`` becoming ``{'i': 'i'}``); both now raise ``TypeError`` with a clear message (closes #242)
    - Fix ``SetManager.__contains__`` being the one operation that didn't normalize (lowercase, strip leading/trailing periods) its operand, so e.g. ``'Dr.' in constants.titles`` could return ``False`` even though the title was correctly configured; membership checks now normalize like ``add()``/``remove()``/the constructor/the set operators (closes #244)
    - Fix a bare string passed to a set-backed ``Constants`` argument (e.g. ``Constants(titles='dr')``), to ``SetManager``, or as a ``SetManager`` set-operator operand (e.g. ``constants.titles |= 'esq'``) being silently split into single characters, replacing or polluting the set and producing wrong parses with no error; it now raises ``TypeError`` with the suggested fix — wrap strings in a list, decode ``bytes`` first (closes #238)
    - Fix ``SetManager`` set operators and the constructor skipping the lowercase/strip-edge-periods normalization that ``add()`` applies: ``constants.titles |= ['Esq.']`` kept a raw ``'Esq.'`` the parser's lookups could never match, ``titles & ['Dr.']`` missed ``'dr'``, and ``Constants(titles=[...])`` stored raw elements that silently never matched; elements and operands are now normalized everywhere, and non-``str`` elements (``bytes``, ``None``, numbers) raise ``TypeError`` instead of crashing cryptically or being coerced
    - Fix the ``constants`` constructor argument silently discarding ``Constants`` *subclass* instances: the exact-type check replaced them with fresh defaults, throwing away the caller's configuration. Subclass instances are now used as given; anything that is neither ``None`` nor a ``Constants`` instance now raises ``TypeError`` instead of being silently swapped for defaults (closes #226)
    - Fix ``Constants`` customizations, singleton identity, and ``TupleManager`` subclass being lost across ``pickle``/``deepcopy`` round-trips (#167, #168, #169)
    - Fix ``is_rootname()`` returning stale results after ``add()``/``remove()`` on ``titles``, ``prefixes``, ``suffix_acronyms``, or ``suffix_not_acronyms`` (#166)
    - Fix the library logger calling ``setLevel(logging.ERROR)`` on import, which silently discarded log records regardless of an application's own logging configuration; the logger now leaves its level at ``NOTSET`` and lets the application control verbosity (closes #228)
    - Minor internal cleanups: drop a dead length check in the initials helper, simplify double-wrapped ``len(list(...))`` calls, and other small parser tidy-ups with no behavior change (closes #229)
    - Change ``Constants.__repr__`` to report collection sizes and non-default scalar config, replacing the uninformative ``<Constants() instance>`` (#221)
* 1.2.1 - June 19, 2026
    - Fix ``initials()`` interpolating the literal ``None`` for empty name parts when ``empty_attribute_default = None`` (e.g. ``"J. None D."``); empty parts now render as an empty string and a fully-empty result returns ``empty_attribute_default``
    - Add ``python -m nameparser "Name String"`` command-line helper that prints a parsed name
    - Reorganize the test suite from a single ``tests.py`` into a ``tests/`` pytest package
* 1.2.0 - June 11, 2026
    - Drop Python 2 and Python < 3.10 support; Python 3.10–3.14 now required
    - Add type hints and type declarations (PEP 561 ``py.typed`` marker)
    - Migrate build tooling to ``pyproject.toml``, drop ``setup.py``
    - Remove dead Python 2 compatibility shims (``ENCODING`` constant, ``next()`` aliases)
    - Modernize CI: uv-based workflow, trusted publishing to PyPI, Dependabot
* 1.1.3 - September 20, 2023
    - Fix case when we have two same prefixes in the name ()#147)
* 1.1.2 - November 13, 2022
    - Add support for attributes in constructor (#140)
    - Make HumanName instances hashable (#138)
    - Update repr for names with single quotes (#137)
* 1.1.1 - January 28, 2022
    - Fix bug in is_suffix handling of lists (#129)
* 1.1.0 - January 3, 2022
    - Add initials support (#128)
    - Add more titles and prefixes (#120, #127, #128, #119)
* 1.0.6 - February 8, 2020
    - Fix Python 3.8 syntax error (#104)
* 1.0.5 - Dec 12, 2019
    - Fix suffix parsing bug in comma parts (#98)
    - Fix deprecation warning on Python 3.7 (#94)
    - Improved capitalization support of mixed case names (#90)
    - Remove "elder" from titles (#96)
    - Add post-nominal list from Wikipedia to suffixes (#93)
* 1.0.4 - June 26, 2019
    - Better nickname handling of multiple single quotes (#86)
    - full_name attribute now returns formatted string output instead of original string (#87)
* 1.0.3 - April 18, 2019
    - fix sys.stdin usage when stdin doesn't exist (#82)
    - support for escaping log entry arguments (#84)
* 1.0.2 - Oct 26, 2018
    - Fix handling of only nickname and last name (#78)
* 1.0.1 - August 30, 2018
    - Fix overzealous regex for "Ph. D." (#43)
    - Add `surnames` attribute as aggregate of middle and last names
* 1.0.0 - August 30, 2018
    - Fix support for nicknames in single quotes (#74)
    - Change prefix handling to support prefixes on first names (#60)
    - Fix prefix capitalization when not part of lastname (#70)
    - Handle erroneous space in "Ph. D." (#43)
* 0.5.8 - August 19, 2018
    - Add "Junior" to suffixes (#76)
    - Add "dra" and "srta" to titles (#77)
* 0.5.7 - June 16, 2018
    - Fix doc link (#73)
    - Fix handling of "do" and "dos" Portuguese prefixes (#71, #72)
* 0.5.6 - January 15, 2018
    - Fix python version check (#64)
* 0.5.5 - January 10, 2018
    - Support J.D. as suffix and Wm. as title
* 0.5.4 - December 10, 2017
    - Add Dr to suffixes (#62)
    - Add the full set of Italian derivatives from "di" (#59)
    - Add parameter to specify the encoding of strings added to constants, use 'UTF-8' as fallback (#67)
    - Fix handling of names composed entirely of conjunctions (#66)
* 0.5.3 - June 27, 2017
    - Remove emojis from initial string by default with option to include emojis (#58)
* 0.5.2 - March 19, 2017
    - Added names scrapped from VIAF data, thanks daryanypl (#57)
* 0.5.1 - August 12, 2016
    - Fix error for names that end with conjunction (#54)
* 0.5.0 - August 4, 2016
    - Refactor join_on_conjunctions(), fix #53
* 0.4.1 - July 25, 2016
    - Remove "bishop" from titles because it also could be a first name
    - Fix handling of lastname prefixes with periods, e.g. "Jane St. John" (#50)
* 0.4.0 - June 2, 2016
    - Remove "CONSTANTS.suffixes", replaced by "suffix_acronyms" and "suffix_not_acronyms" (#49)
    - Add "du" to prefixes
    - Add "sheikh" variations to titles
    - Add parameter to force capitalization of mixed case strings
* 0.3.16 - March 24, 2016
    - Clarify LGPL licence version (#47)
    - Skip pickle tests if pickle not installed (#48)
* 0.3.15 - March 21, 2016
    - Fix string format when `empty_attribute_default = None` (#45)
    - Include tests in release source tarball (#46)
* 0.3.14 - March 18, 2016
    - Add `CONSTANTS.empty_attribute_default` to customize value returned for empty attributes (#44)
* 0.3.13 - March 14, 2016
    - Improve string format handling (#41)
* 0.3.12 - March 13, 2016
    - Fix first name clash with suffixes (#42)
    - Fix encoding of constants added via the python shell
    - Add "MSC" to suffixes, fix #41
* 0.3.11 - October 17, 2015
    - Fix bug capitalization exceptions (#39)
* 0.3.10 - September 19, 2015
    - Fix encoding of byte strings on python 2.x (#37)
* 0.3.9 - September 5, 2015
    - Separate suffixes that are acronyms to handle periods differently, fixes #29, #21
    - Don't find titles after first name is filled, fixes (#27)
    - Add "chair" titles (#37)
* 0.3.8 - September 2, 2015
    - Use regex to check for roman numerals at end of name (#36)
    - Add DVM to suffixes
* 0.3.7 - August 30, 2015
    - Speed improvement, 3x faster
    - Make HumanName instances pickleable
* 0.3.6 - August 6, 2015
    - Fix strings that start with conjunctions (#20)
    - handle assigning lists of names to a name attribute
    - support dictionary-like assignment of name attributes
* 0.3.5 - August 4, 2015
    - Fix handling of string encoding in python 2.x (#34)
    - Add support for dictionary key access, e.g. name['first']
    - add 'santa' to prefixes, add 'cpa', 'csm', 'phr', 'pmp' to suffixes (#35)
    - Fix prefixes before multi-part last names (#23)
    - Fix capitalization bug (#30)
* 0.3.4 - March 1, 2015
    - Fix #24, handle first name also a prefix
    - Fix #26, last name comma format when lastname is also a title
* 0.3.3 - Aug 4, 2014
    - Allow suffixes to be chained (#8)
    - Handle trailing suffix in last name comma format (#3). Removes support for titles
      with periods but no spaces in them, e.g. "Lt.Gen.". (#21)
* 0.3.2 - July 16, 2014
    - Retain original string in "original" attribute.
    - Collapse white space when using custom string format.
    - Fix #19, single comma name format may have trailing suffix
* 0.3.1 - July 5, 2014
    - Fix Pypi package, include new config module.
* 0.3.0 - July 4, 2014
    - Refactor configuration to simplify modifications to constants (backwards incompatible)
    - use unicode_literals to simplify Python 2 & 3 support.
    - Generate documentation using sphinx and host on readthedocs.
* 0.2.10 - May 6, 2014
    - If name is only a title and one part, assume it's a last name instead of a first name, with exceptions for some titles like 'Sir'. (`#7 <https://github.com/derek73/python-nameparser/issues/7>`_).
    - Add some judicial and other common titles. (#9)
* 0.2.9 - Apr 1, 2014
    - Add a new nickname attribute containing anything in parenthesis or double quotes (`Issue 33 <https://code.google.com/p/python-nameparser/issues/detail?id=33>`_).
* 0.2.8 - Oct 25, 2013
    - Add support for Python 3.3+. Thanks to @corbinbs.
* 0.2.7 - Feb 13, 2013
    - Fix bug with multiple conjunctions in title
    - add legal and crown titles
* 0.2.6 - Feb 12, 2013
    - Fix python 2.6 import error on logging.NullHandler
* 0.2.5 - Feb 11, 2013
    - Set logging handler to NullHandler
    - Remove 'ben' from PREFIXES because it's more common as a name than a prefix.
    - Deprecate BlankHumanNameError. Do not raise exceptions if full_name is empty string.
* 0.2.4 - Feb 10, 2013
    - Adjust logging, don't set basicConfig. Fix `Issue 10 <https://code.google.com/p/python-nameparser/issues/detail?id=10>`_ and `Issue 26 <https://code.google.com/p/python-nameparser/issues/detail?id=26>`_.
    - Fix handling of single lower case initials that are also conjunctions, e.g. "john e smith". Re `Issue 11 <https://code.google.com/p/python-nameparser/issues/detail?id=11>`_.
    - Fix handling of initials with no space separation, e.g. "E.T. Jones". Fix #11.
    - Do not remove period from first name, when present.
    - Remove 'e' from PREFIXES because it is handled as a conjunction.
    - Python 2.7+ required to run the tests. Mark known failures.
    - tests/test.py can now take an optional name argument that will return repr() for that name.
* 0.2.3 - Fix overzealous "Mac" regex
* 0.2.2 - Fix parsing error
* 0.2.0
    - Significant refactor of parsing logic. Handle conjunctions and prefixes before
      parsing into attribute buckets.
    - Support attribute overriding by assignment.
    - Support multiple titles.
    - Lowercase titles constants to fix bug with comparison.
    - Move documentation to README.rst, add release log.
* 0.1.4 - Use set() in constants for improved speed. setuptools compatibility - sketerpot
* 0.1.3 - Add capitalization feature - twotwo
* 0.1.2 - Add slice support

