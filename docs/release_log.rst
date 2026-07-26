Release Log
===========
* 2.0.0 - unreleased

    **2.0.0rc2 released 2026-07-26** (rc1 on 2026-07-23) for testing
    ahead of the final
    2.0.0. Install it with ``pip install --pre nameparser`` (a
    pre-release is not selected by a plain ``pip install``); please
    report anything the migration missed on `issue #284
    <https://github.com/derek73/python-nameparser/issues/284>`_. The
    notes below describe 2.0.0 as a whole.

    nameparser 2.0 adds a new parsing API alongside ``HumanName``.
    ``parse()`` returns an immutable ``ParsedName`` whose seven fields
    are named for what they are (``given``, ``family``) rather than
    where they sit in a Western name, configured by two frozen value
    objects -- a ``Lexicon`` of vocabulary and a ``Policy`` of behavior
    -- instead of a mutable global. ``HumanName`` keeps working: it is
    now a compatibility facade over the same pipeline, and it stays
    through 2.x. The removals below are the deprecations announced in
    1.3.0 and 1.4.0 coming due; if your code runs warning-free on
    1.4.0, most of them will not affect you. See :doc:`migrate` for the
    field-by-field map.

    **The 2.0 API**

    - Add ``parse(text)``, returning an immutable ``ParsedName`` with seven fields -- ``title``, ``given``, ``middle``, ``family``, ``suffix``, ``nickname``, ``maiden`` -- plus the derived views ``given_names``, ``surnames``, ``family_base`` and ``family_particles``. Parsing is a pure function of the text, a ``Lexicon`` and a ``Policy``: nothing global is consulted and nothing is mutated
    - Add ``Lexicon``, the frozen vocabulary object. ``Lexicon.default()`` is the shipped vocabulary and ``Lexicon.empty()`` is a blank one; ``add(**entries)``, ``remove(**entries)`` and field-wise ``|`` all return new instances. Its fields are ``titles``, ``given_name_titles``, ``suffix_acronyms``, ``suffix_words``, ``suffix_acronyms_ambiguous``, ``particles``, ``particles_ambiguous``, ``conjunctions``, ``bound_given_names``, ``maiden_markers`` and ``capitalization_exceptions``
    - Add ``Policy``, the frozen behavior object: ``name_order``, ``patronymic_rules``, ``middle_as_family``, ``nickname_delimiters``, ``maiden_delimiters``, ``extra_suffix_delimiters``, ``lenient_comma_suffixes``, ``strip_emoji`` and ``strip_bidi``
    - Add ``Parser``, a reusable parser bound to a lexicon and policy (``Parser(lexicon=..., policy=...).parse(text)``), and ``parser_for(*locales, base=None)``, which folds locale packs onto a base parser
    - Add ``name_order`` and the constants ``GIVEN_FIRST``, ``FAMILY_FIRST`` and ``FAMILY_FIRST_GIVEN_LAST``, so a family-first name can be parsed as written rather than reordered by hand (closes the configuration half of #270)
    - Add ``PatronymicRule`` with the members ``EAST_SLAVIC`` and ``TURKIC``. v1's single ``patronymic_name_order`` flag enabled both detectors at once; ``Policy(patronymic_rules=...)`` lets you enable either one alone
    - Add ``PolicyPatch`` and the ``UNSET`` sentinel for partial policy deltas that compose -- set-valued fields union, scalar fields override with later winning. This is the mechanism locale packs are built from, and ``UNSET`` is only needed when you must distinguish "not set" from a real ``False`` or ``None``
    - Add ``Token``, ``Span`` and ``Role``: every field is backed by tokens carrying exact ``(start, end)`` offsets into the original string, reachable with ``tokens_for(Role.GIVEN)``. This replaces v1's ``*_list`` attributes and makes it possible to highlight or re-slice the input the parse came from. ``Role`` is a ``StrEnum``, so members compare and stringify as their field names (``Role.GIVEN == "given"``), matching ``AmbiguityKind``; ``tokens_for()`` accepts a role's string name too, and raises ``ValueError`` for an unknown role
    - Add ``STABLE_TAGS`` to the public API: the four documented ``Token.tags`` values (``particle``, ``conjunction``, ``initial``, ``joined``)
    - Add ``Policy.patched(patch)``, applying a ``PolicyPatch`` directly without wrapping it in a locale pack
    - Add ``Parser.matches(a, b)`` and ``Parser.capitalized(name)``: the ``ParsedName`` methods of the same names fall back to the default configuration for str/omitted arguments, which is silently wrong for names parsed with a custom ``Parser``
    - Add ``Parser.revise(name, **fields)``: ``ParsedName.replace()`` with the replacement text classified by the parser's vocabulary, so particle/initial/suffix-join behavior survives the edit
    - Add ``Ambiguity`` and the ``AmbiguityKind`` enum, so a parse reports what it had to guess at instead of guessing silently. The kinds emitted today are ``particle-or-given``, ``suffix-or-name``, ``suffix-or-nickname``, ``unbalanced-delimiter`` and ``comma-structure``; ``order`` is reserved and not yet emitted. The two suffix kinds cover the post-nominals that are also ordinary words: ``"John Smith MA"`` reports that ``MA`` was read as a credential rather than a surname, and ``"JEFFREY (JD) BRICKEN"`` that the delimited ``JD`` was read as a nickname rather than a suffix. A reading the vocabulary settles on its own — ``"John Smith M.A."``, ``"Andrew Perkins (MBA)"`` — is not a guess and reports nothing
    - Add ``ParsedName`` output and comparison methods: ``render(spec)``, ``initials()``, ``capitalized()`` (which returns a new value rather than mutating in place), ``as_dict()`` (whose ``include_empty`` flag is keyword-only, unlike ``HumanName.as_dict()``'s), ``replace(**fields)``, ``matches()`` and ``comparison_key()``
    - Add ``Locale``, the public pack type. Writing your own needs no registration -- construct a ``Locale`` and pass it to ``parser_for()``
    - Ship a fully typed public API (PEP 561): the core modules are checked under strict mypy settings, and nameparser 2.0 has no runtime dependencies

    **Breaking Changes**

    - Raise the minimum Python to 3.11 and drop the last runtime dependency, ``typing_extensions`` (#257). Python 3.10 is no longer supported
    - Remove ``HumanName.__eq__`` and ``__hash__`` (deprecated in 1.3.0, #223): instances now compare and hash by identity, so ``HumanName("John Smith") == "John Smith"`` is ``False`` where 1.x returned ``True``. **This changes result silently rather than raising** -- it is the one removal that can pass unnoticed into production. Use ``matches()`` to ask whether two names are the same, and ``comparison_key()`` as a dict key or sort key
    - Remove every v1 parsing hook and subclass extension point: ``pre_process``, ``post_process``, ``parse_pieces``, ``parse_nicknames``, ``join_on_conjunctions``, the ``is_*`` predicates, ``cap_word``/``cap_piece``, ``handle_firstnames``, ``fix_phd`` and the rest. A subclass that overrides one gets a ``DeprecationWarning`` at construction naming the hooks, because the facade delegates to the core ``Parser`` and never calls them (closes #280). Customize through ``Lexicon``/``Policy`` instead
    - Remove regex configuration: ``CONSTANTS.regexes`` is now a read-only proxy. Reads still work, but ``CONSTANTS.regexes.bidi = False``, item assignment and ``Constants(regexes=...)`` all raise ``TypeError``. **If you followed 1.3.1's advice to keep bidi marks with** ``CONSTANTS.regexes.bidi = False``, that opt-out is now ``Policy(strip_bidi=False)`` on the 2.0 API; the same applies to ``regexes.emoji`` and ``Policy(strip_emoji=False)``
    - Remove ``bytes`` input and the ``encoding`` argument (#245): passing ``bytes`` to ``HumanName`` or to a set manager raises ``TypeError`` with a decode hint, and ``SetManager.add_with_encoding()`` and ``DEFAULT_ENCODING`` are gone. Decode first, then use ``add()``
    - Remove ``SetManager.__call__`` (#243); iterate the manager or call ``set(manager)``. ``remove()`` of a missing member now raises ``KeyError`` like ``set.remove`` -- ``discard()`` is the ignore-missing form -- and the set operators ``|``, ``&``, ``-`` and ``^`` return a plain ``set``
    - Remove ``HumanName`` slice access and item assignment (#258): ``name[1:-3]`` and ``name['first'] = value`` raise ``TypeError``. String-key reads (``name['first']``) and iteration are unchanged; assign fields as plain attributes
    - Remove ``Constants.empty_attribute_default`` (#255): empty fields are always ``''``. Assigning it raises ``AttributeError``; a pickle carrying the key still loads, with the value ignored
    - Remove ``constants=None`` (#261): both ``HumanName(..., constants=None)`` and ``hn.C = None`` raise ``TypeError``. Use ``Constants()`` for library defaults or ``CONSTANTS.copy()`` for a private snapshot
    - Remove silent unknown-key access on the mapping managers (#256): ``CONSTANTS.capitalization_exceptions.typo`` and ``CONSTANTS.regexes.typo`` raise ``AttributeError`` naming the miss, instead of returning ``None``/``EMPTY_REGEX`` (the mapping manager also lists the known keys). ``.get()`` remains available on both for intentional soft access
    - Remove support for ``Constants`` pickles written by nameparser 1.2.x or earlier (#279): loading one raises ``ValueError`` telling you to re-pickle under 1.3/1.4 first
    - Remove the dead ``regexes.no_vowels`` pattern (#268) and the ``Constants.suffixes_prefixes_titles`` cached union; neither was read by the parser
    - Change ``HumanName``'s ``*_list`` attributes to read-only properties: they remain readable snapshots, but ``name.first_list = [...]`` now raises ``AttributeError``
    - Change the ``Constants`` constructor to keyword-only; positional construction no longer works

    **Behavior Changes**

    - Recognize maiden-name markers -- ``née``, ``nee``, ``born``, ``geb.``, ``roz.`` and the Scandinavian participle forms -- and route the following name to the new ``maiden`` field. 1.x folded them into ``middle``/``last``, so ``"Jane Smith née Jones"`` parsed as ``middle="Smith née"`` (closes #274)
    - Recognize typographic nickname delimiters by default in both APIs (closes #273): smart quotes (``“Jack”``), German and Polish low-high quotes (``„Hansi“``), Swedish right-right quotes (``”Ann”``), guillemets in either direction (``«Petit»``, ``»Hansi«``), CJK corner brackets (``「タロ」``, ``『ハナ』``) and fullwidth parentheses. In 1.x these leaked into ``middle`` as literal text. Curly *single* quotes stay excluded, because U+2019 is the apostrophe in "O’Connor"
    - Fix the pre-comma piece being routed to ``first`` when everything after the comma is a suffix or title: ``"Andrews, M.D."`` now reads family ``Andrews`` / suffix ``M.D.`` where 1.x read given ``M.D.`` / family ``Andrews``, and ``"Smith, Dr."`` moves ``Smith`` from ``first`` to ``family`` (the title was already correct in 1.x). The piece before a comma is definitionally the family name
    - Fix a lone recognized trailing suffix with no comma being routed to ``first``/``last``: ``"Johnson PhD"`` and ``"Mr. Johnson PhD"`` now keep the suffix in ``suffix``
    - Fix a split ``"Ph. D."`` credential being read as two tokens; it now classifies as one suffix, replacing v1's ``fix_phd`` hook. This now holds wherever the credential sits: 1.x healed the pair only when it trailed, so ``"Ph. D. John Smith"`` parsed as title ``Ph.`` / given ``D.`` with the real given name pushed to ``middle``; it now reads given ``John``, family ``Smith``, suffix ``Ph. D.``
    - Fix ``chargé d'affaires``: shipped as one unmatchable ``TITLES`` entry since it was added, it is now two chainable entries (``chargé``, ``d'affaires``), so the title is recognized; the unaccented spelling ``charge`` ships too, like ``attaché``/``attache``
    - Remove seven multi-word ``SUFFIX_ACRONYMS`` entries (``leed ap``, ``nicet i``–``nicet iv``, ``psm i``, ``psm ii``) that could never match in any release; splitting them would swallow real names ("John Leed", "Smith, A.P."), so they are dropped instead
    - Add a ``UserWarning`` when a multi-word entry is stored in a per-word ``Lexicon`` field or as a ``capitalization_exceptions`` key -- such entries can never match
    - Parse an input with no alphanumeric character to an empty name in both APIs. 1.x kept pure punctuation as a name part, so ``"."`` gave ``first="."`` and ``bool()`` was ``True``; 2.0 empties it, keeping ``bool(parse(x))`` an honest "did I get a name?" test. The check is Unicode-aware, so names in any script are unaffected; only inputs that are entirely punctuation or symbols (``"."``, ``"- -"``) change. Junk embedded in a name with real content -- the stray dot in ``"John . Smith"`` -- is still kept, since that parse is already truthy
    - Fold a leading never-given particle into the family name. Note that ``Lexicon.particles_ambiguous`` is the **complement** of v1's ``non_first_name_prefixes``, not a rename -- it lists the particles that *may* double as a given name, where v1 listed the ones that may not. Copying a v1 customization across without inverting it silently reverses the behavior; see :doc:`migrate`
    - Add ``ma`` and ``do`` to ``suffix_acronyms_ambiguous``, the set of post-nominals that are also ordinary surnames. An entry there is read as a credential when the name can spare it — written with periods (``"John Smith M.A."``), or when removing it still leaves a given *and* a family name (``"John Smith MA"`` → suffix ``MA``). With only two pieces to go around, the surname reading wins instead: ``"Jack Ma"`` and ``"Anh Do"`` keep their family names. As a side effect, a parenthesized or quoted ``"(MA)"``/``"(DO)"`` now falls through to nickname parsing rather than escaping to ``suffix``, since inside delimiters the nickname reading is the plausible one
    - Change ``comparison_key()`` and ``matches()`` in both APIs to fold with ``str.casefold()`` where 1.4 used ``str.lower()``, so Unicode case pairs compare equal -- ``"STRASSE"`` matches ``"Straße"``, and a Greek final sigma matches its regular form. This is strictly more permissive: anything 1.4 matched still matches. Vocabulary normalization deliberately still uses ``lower()``, for v1 parity
    - Change the 2.0 API's default ``render()``/``str()`` spec to show every non-empty field: ``'{title} {given} "{nickname}" {middle} {family} ({maiden}) {suffix}'``. The quoted nickname round-trips exactly; the parenthesized maiden re-parses as a nickname, a deliberate choice of presentation over lossless round-trip -- use ``née {maiden}`` in a custom spec if you need it to survive a reparse. ``HumanName`` keeps v1's own ``string_format`` default, unchanged
    - Change delimiter-overlap precedence in the 2.0 API: a pair listed in ``Policy.maiden_delimiters`` is dropped from the effective nickname set, so ``Policy(maiden_delimiters={("(", ")")})`` alone routes parenthesized content to ``maiden``. The default nickname set is exported as ``DEFAULT_NICKNAME_DELIMITERS``. ``HumanName`` keeps v1's nickname-wins precedence, so no existing behavior changes
    - Change suffix-delimiter rendering when a custom suffix delimiter is configured: for ``suffix_delimiter="/"`` and ``"John Smith, RN/CRNA"``, 1.x split the token and rendered ``suffix="RN, CRNA"`` where 2.0 keeps it whole as ``"RN/CRNA"``. Role assignment is unchanged; only rendering differs
    - Correct a long-standing typo in the shipped vocabulary that 1.x carried: ``actor`` and ``television`` had trailing spaces in ``TITLES``, so ``"actor" in TITLES`` was ``False``. **Parse output is unchanged** -- the parser normalizes entries on ingest, which is exactly what let the typo go unnoticed -- but code that tests membership against the exported constants directly will see corrected results. The data modules now assert their invariants at import time, alongside the ones ``prefixes.py`` already checked; entries must be stored lowercase and whitespace-free, so this class of typo now fails the build

    **International name support**

    - Add ``nameparser.locales`` with the first two packs: ``locales.RU`` (East Slavic patronymic order) and ``locales.TR_AZ`` (Turkic patronymic markers). Packs are pure data folded in at ``parser_for(locales.RU)``, they compose (``parser_for(locales.RU, locales.TR_AZ)`` unions the rules), and they are never auto-detected -- there is no reliable way to detect a name's language from the name alone. ``locales.available()`` and ``locales.get(code)`` look packs up by code; loading is lazy, so importing the package imports no pack (closes the pack half of #270; #271/#272/#146 stay staged for 2.x)
    - Add non-Latin vocabulary to the default lexicon (#269): Cyrillic, Greek, Arabic and Hebrew titles, conjunctions and name particles. Native-script entries cannot collide with Latin-script names, which is what makes them safe to enable by default. Deferred pending vetting: the Cyrillic ``мл``/``ст`` suffixes and the bare Greek ``κ`` title, which collides with the initial-plus-surname shape. Behavior note: ``محمد بن سلمان`` now chains ``بن`` onto the family name where 1.x read it as a middle name
    - Add Arabic-script bound given names (#269): ``عبد``, the kunya pair ``أبو``/``ابو``, and ``أم``/``ام`` join the following word into the given name exactly as their transliterations (``abdul``, ``abu``, ``umm``) always did, so ``عبد الرحمن محمد`` parses given ``عبد الرحمن``, family ``محمد`` where 1.x split it into given plus middle
    - Add Arabic honorific titles and the conjunction ``و`` (#269): the doctor, professor, hajj, sheikha and engineer forms (``الدكتور``/``الدكتورة``/``دكتور``/``دكتورة``, ``الأستاذ``/``الأستاذة``/``أستاذ``/``أستاذة``, ``الحاج``/``الحاجة``, ``الشيخة``, ``مهندس``) as given-name titles, since Arabic honorifics precede the given name like ``الشيخ``. Deferred under the collision rule: bare ``سيد``/``شيخ``/``أمير``/``سلطان`` (all common given names), the ``د.`` abbreviation (bare ``د`` would swallow initials), and the Ottoman post-nominals ``باشا``/``بك``/``أفندي`` (which survive as family names)
    - Add Hebrew honorifics and post-nominals, and Devanagari titles (#269): the Israeli honorifics ``גברת``, ``פרופ'``/``פרופ׳``, ``פרופסור``, ``עו"ד``/``עו״ד`` and ``הרב`` as titles; ``ז"ל``/``ז״ל`` and ``שליט"א``/``שליט״א`` as suffixes, in both gershayim spellings; and Devanagari ``श्री``, ``श्रीमती`` and ``डॉ``. Latin ``sri``/``shri`` were deliberately not added, because they collide with real given names where the native script cannot. Deferred: bare ``רב`` (an ordinary word meaning "many") and ``בר`` as a particle (Bar is a common modern given name)

    **Compatibility layer**

    - Reimplement ``HumanName`` as a facade over the 2.0 pipeline, and ``Constants`` as a shim resolving to a ``(Lexicon, Policy)`` snapshot with a shared parser cache. Fields, aggregates, mutation through ``name.C.titles.add(...)``, rendering defaults, ``capitalize()``, ``matches()``, ``comparison_key()``, iteration, ``as_dict()`` and pickling are all preserved, and ``nameparser.parser`` and ``nameparser.config`` remain importable. The compatibility layer ships through 2.x and is removed in 3.0
    - Note that ``CONSTANTS.capitalize_name`` and ``force_mixed_case_capitalization`` are still honored through the facade, but the 2.0 API never capitalizes during ``parse()`` -- call ``capitalized()`` when you want it
    - Add ``Role`` members (and their string values ``given``/``family``) as valid ``HumanName`` subscript keys: ``hn[Role.GIVEN]`` returns ``hn.first``

    **Command line**

    - Rewrite ``python -m nameparser`` over the 2.0 API with a real argument parser. It prints the parse plus its capitalized form and initials by default, takes ``--json`` to emit the fields as JSON (``python -m nameparser --json "Doe, John"``), takes ``--locale CODE`` to apply a pack, and exits with a usage message on bad arguments

    **Documentation**

    - Rewrite the documentation new-API-first: a new front page and README, ``usage.rst`` as a tour of the 2.0 API, a principle-first ``customize.rst``, a reference split into the 2.0 API and the compatibility layer, and new pages for :doc:`concepts`, :doc:`locales` and :doc:`migrate` -- the last carrying full attribute and configuration maps from v1 names to 2.0 names (#262). The 1.x documentation remains online as the readthedocs ``stable`` build

    Parsing changes were checked against a 652-name differential corpus
    -- names harvested from the v1 test banks, plus names reported in
    the issue tracker -- and everything not listed above parses
    identically between 1.4.0 and 2.0. The harness lives in
    ``tools/differential/`` in the source repository (it is development
    tooling, not part of the installed package) -- see its README to
    reproduce the comparison against your own names.

    **Changed since 2.0.0rc1** (for anyone who tested the release candidate)

    - ``Role`` became a ``StrEnum``; ``str(Role.GIVEN)`` is now ``"given"``
    - ``ParsedName.tokens_for()`` raises ``ValueError`` for unknown roles instead of returning no tokens; it also accepts role-name strings
    - ``ParsedName.as_dict()``'s ``include_empty`` is keyword-only
    - ``HumanName`` subscripting accepts ``Role`` members
    - The eight multi-word vocabulary entries that could never match were repaired (``chargé d'affaires`` split; seven credential acronyms removed), and storing a new multi-word entry now warns; those eight are dropped silently, not warned about, when a restored ``Constants`` pickle carries all eight of them (the pre-2.0 signature)
    - ``PolicyPatch``'s repr shows only the fields a patch sets, instead of all nine with UNSET sentinels
    - New since rc1: ``STABLE_TAGS``, ``Policy.patched()``, ``Parser.matches()``, ``Parser.capitalized()``, and ``Parser.revise()`` -- see the API section above

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

