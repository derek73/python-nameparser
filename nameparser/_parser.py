"""Parser and the module-level parse() for the 2.0 API.

Layering: sits on _types/_lexicon/_policy/_locale/_pipeline; never
imports _render (enforced by tests/v2/test_layering.py).

_default_parser is THE one sanctioned module-level global: a
functools.cache'd frozen Parser over default config.
"""
from __future__ import annotations

import dataclasses
import functools
import warnings
from dataclasses import dataclass, field

from nameparser._lexicon import _rechosen_masks
from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._pipeline import run
from nameparser._pipeline._assemble import assemble
from nameparser._pipeline._post_rules import suffix_entries
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._vocab import _SCRIPT_MATCHERS
from nameparser._policy import UNSET, Policy, PolicyPatch, _Unset, apply_patch
from nameparser._types import (
    FOLDED_TAG, ParsedName, Role, Segmenter, Token, _guarded_getstate,
    _guarded_setstate, _validated_field_strings,
)


@dataclass(frozen=True, slots=True)
class Parser:
    """A configured name parser: a :class:`Lexicon` (vocabulary) plus
    a :class:`Policy` (behavior), both defaulted when omitted. Build
    one when you need non-default configuration, build it once, and
    call :meth:`parse` many times -- it is immutable and thread-safe.

    An optional keyword-only ``segmenter`` (a :data:`~nameparser.Segmenter`)
    plugs in outside knowledge of where an unspaced CJK token divides --
    Japanese kanji names, which no bundled list can settle. It is
    consulted only for a token the segmentation stage gates in and the
    vocabulary DECLINES, so a locale pack's surnames always win where
    they match; returning None declines in turn and the token stays
    whole. Two promises narrow when one is supplied (the first is
    rules/A1's Accepted bullet "The one exception to totality"):
    parse-totality gains its one exception -- an exception raised by
    the segmenter propagates, because a user-supplied callable's own
    error is a user-code error, not a content error -- and this Parser
    pickles only if its segmenter does (a module-level function
    pickles; a lambda or closure does not). With no segmenter, both
    promises hold unconditionally: all validity checking happens at
    construction, so a Parser that constructs successfully cannot fail
    at parse time on any str content.

    (The None field defaults resolve in __post_init__; after
    construction lexicon and policy are always non-None -- the
    annotations state the steady-state truth, hence the assignment
    ignores on the defaults.)"""

    lexicon: Lexicon = None  # type: ignore[assignment]  # None -> default()
    policy: Policy = None  # type: ignore[assignment]    # None -> Policy()
    #: An optional hook supplying outside knowledge of where an unspaced
    #: token divides -- see the class docstring; None leaves such tokens
    #: whole. Keyword-only, so the reserved growth stays additive:
    #: positional construction keeps its two-argument shape.
    segmenter: Segmenter | None = field(default=None, kw_only=True)

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if self.lexicon is None:
            object.__setattr__(self, "lexicon", Lexicon.default())
        elif not isinstance(self.lexicon, Lexicon):
            raise TypeError(
                f"lexicon must be a Lexicon or None, got {self.lexicon!r}")
        if self.policy is None:
            object.__setattr__(self, "policy", Policy())
        elif not isinstance(self.policy, Policy):
            raise TypeError(
                f"policy must be a Policy or None, got {self.policy!r}")
        if self.segmenter is not None and not callable(self.segmenter):
            raise TypeError(
                f"segmenter must be callable or None, got {self.segmenter!r}")
        # A configuration gap that used to be silent (#272's API, made
        # loud before 2.1.0): segment_scripts can activate a script
        # that neither the vocabulary nor a segmenter can ever divide
        # -- the JA pack's whole shape, when its segmenter is
        # forgotten. The parser then behaves identically to a working
        # one minus the feature, which reads as "not working" with no
        # signal why. Statically decidable here, so say it here; a
        # warning rather than an error because the inert pack is a
        # pinned, deliberate property (a JA registration must be safe
        # without the extra), and warnings are filterable by the rare
        # caller who wants exactly that.
        if self.segmenter is None:
            uncovered = sorted(
                script.value
                for script in self.policy.segment_scripts
                if not any(_SCRIPT_MATCHERS[script](entry)
                           for entry in self.lexicon._sets.surnames))
            if uncovered:
                names = ", ".join(uncovered)
                one = len(uncovered) == 1
                # the ja hint only where a Japanese script is among the
                # dead ones -- a hangul-only gap (a from-scratch
                # lexicon under the default policy) has different
                # remedies, and pointing it at ja_segmenter would be a
                # non sequitur
                ja_hint = (
                    " For Japanese, pass "
                    "segmenter=locales.ja_segmenter() (install with: "
                    "pip install 'nameparser[ja]')."
                    if {"han", "hiragana", "katakana"} & set(uncovered)
                    else "")
                warnings.warn(
                    f"Policy.segment_scripts activates {names} but the "
                    f"vocabulary has no surnames in "
                    f"{'that script' if one else 'those scripts'} "
                    f"and no segmenter is configured: unspaced names "
                    f"written in {'it' if one else 'them'} will never "
                    f"divide. Supply covering surnames, pass a "
                    f"segmenter, or deactivate with "
                    f"Policy(segment_scripts=frozenset()).{ja_hint}",
                    UserWarning, stacklevel=3)

    def __repr__(self) -> str:
        # composes the two bounded component reprs; the
        # segmenter shows by name, and only when one is set, so the
        # default Parser's repr is unchanged
        seg = ""
        if self.segmenter is not None:
            # never repr() the callable itself: a partial reprs its
            # bound arguments and a callable instance its address, both
            # unbounded -- the class name is the bounded fallback
            name = (getattr(self.segmenter, "__qualname__", None)
                    or type(self.segmenter).__name__)
            seg = f", segmenter={name}"
        return f"Parser({self.lexicon!r}, {self.policy!r}{seg})"

    # -- properties ------------------------------------------------------

    @property
    def languages(self) -> frozenset[str]:
        """The languages this parser's vocabulary is chosen under,
        :attr:`Lexicon.languages` read through: set by
        :func:`parser_for`, empty where none was chosen. Added in
        3.0."""
        return self.lexicon.languages

    @property
    def strict(self) -> bool:
        """Whether the choice is strict, :attr:`Lexicon.strict` read
        through. Added in 3.0."""
        return self.lexicon.strict

    def parse(self, text: str) -> ParsedName:
        """Parse one name string into a :class:`ParsedName`. Never
        raises on string content (unparseable input yields empty
        fields plus ambiguities); non-str raises TypeError eagerly,
        with a decode hint for bytes (bytes support ended with 1.x).
        The one exception to that totality is a configured
        ``segmenter``, whose own exceptions propagate (see the class
        docstring)."""
        if isinstance(text, bytes):
            raise TypeError(
                "parse() takes str, not bytes -- decode first, e.g. "
                "raw.decode('utf-8')")
        if not isinstance(text, str):
            raise TypeError(f"parse() takes str, got {text!r}")
        state = ParseState(original=text, lexicon=self.lexicon,
                           policy=self.policy, segmenter=self.segmenter)
        return assemble(run(state))

    # -- editing ----------------------------------------------------------

    def revise(self, name: ParsedName, **fields: str) -> ParsedName:
        """:meth:`ParsedName.replace` with this parser's vocabulary:
        each value is tokenized and classified by a full sub-parse, so
        the stable tags survive and the tag-driven views
        (family_particles, initials(), the suffix join, and since #407
        capitalized()) behave as if the text had been parsed. The
        value is classified ON ITS OWN, though -- a word whose reading
        depends on surrounding context may classify differently than
        it would in place, and a glued CJK honorific the whole name
        kept on an initial may peel in the value. The sub-parse's role
        choices and ambiguities are discarded -- every harvested token
        takes the named field's role -- and its structural behavior
        applies: delimiter characters do not become tokens, and a
        maiden marker is consumed as in parsing -- mid-value always,
        and leading a DELIMITED value under a policy routing that pair
        to maiden, where "(née Jones)" revises to "Jones" while the
        bare "née Jones" keeps its marker, a leading marker in an
        undelimited value being no marker at all (#329).
        A suffix value's ENTRY structure is derived from the value's
        own commas after the role is forced, by the rule a whole name
        uses: a comma parts two credentials and a space joins them, so
        ``revise(n, suffix="MD PhD")`` is one entry and a name's
        rendered suffix revises back to itself wherever the value's
        words read as the whole name read them -- the honorific peel
        above was the one corpus exception of 368 suffix-bearing names,
        2026-09-06 (#511). A second came with #601/#602: a suffix
        holding a maiden marker the whole name left a word, whose
        value read on its own takes the clause and drops the marker
        ('Jane Doe PhD nee Smith' renders 'PhD nee Smith', which
        revises to 'PhD Smith'), three corpus names on 2026-10-04. A delimiter the policy names through
        ``extra_suffix_delimiters`` parts a value only where the
        value's own words, read as a name, give it a tail segment for
        the core to be dropped on; a run of post-nominals has none,
        with or without a comma of its own (``"MD PhD - FACS"`` and
        ``"MD, PhD - FACS"`` both keep the dash as a word), so write a
        comma at the boundary you want rather than the delimiter.
        Tokens are synthetic (span=None); original is unchanged; a
        value with no name content (empty, whitespace, or punctuation
        only) clears the field; ambiguities referencing replaced
        tokens are dropped."""
        if not isinstance(name, ParsedName):
            raise TypeError(f"revise() takes a ParsedName, got {name!r}")
        replaced = _validated_field_strings(fields)
        harvested: dict[Role, tuple[Token, ...]] = {}
        for role, value in replaced.items():
            # the same construction parse() makes, spelled twice
            # rather than through a helper: routing parse() through
            # one cost a frame per parse on the hot path (py3.11,
            # 2026-09-06: 415 calls/name against 414 without it, in a
            # 402-418 band), the same trade _mark_suffix_entries
            # refused, one row over
            state = run(ParseState(original=value, lexicon=self.lexicon,
                                   policy=self.policy,
                                   segmenter=self.segmenter))
            dropped = set(state.dropped)
            # Force the role BEFORE the entry pass: it keys on
            # Role.SUFFIX, and a bare value's sub-parse reads its words
            # as a name ('RA PhD' is a title and a family there), so
            # inside the sub-parse it joined nothing. The sub-parse's
            # tags are KEPT, "joined" included: a within-piece mark
            # (the Ph. D. merge) is role-blind and right for every
            # role, and a clear was measured and backed out --
            # decisions/R1 (2026-09-06 #511) carries the rest: the
            # between-piece mark that rides onto a non-suffix role, and
            # which views read it. Dropped tokens keep their role: the
            # pass filters them by index and assemble omits them.
            forced = tuple(
                tok if i in dropped
                else dataclasses.replace(tok, role=role)
                for i, tok in enumerate(state.tokens))
            # rules/R1: "a run of post-nominals written with spaces
            # renders with spaces, and one written with commas keeps
            # them" -- the same pass post_rules runs last, over the
            # value's own comma offsets, so the harvest carries exactly
            # the entry structure the value's commas describe. Run for
            # every role: for a non-suffix role it is a no-op, kept
            # unconditional as the simpler contract, revise() being off
            # the call-count band.
            entried = suffix_entries(
                dataclasses.replace(state, tokens=forced))
            harvested[role] = tuple(
                Token(t.text, None, role, t.tags - {FOLDED_TAG})
                for t in assemble(entried).tokens)
        return name._with_field_tokens(harvested)

    # -- comparison -------------------------------------------------------

    def matches(self, a: str | ParsedName, b: str | ParsedName) -> bool:
        """Component-wise case-insensitive comparison of two names,
        parsing str arguments with THIS parser.
        :meth:`ParsedName.matches` parses its str argument with the
        DEFAULT parser instead -- for names parsed with a custom
        Parser, use this method."""
        if isinstance(a, str):
            a = self.parse(a)
        elif not isinstance(a, ParsedName):
            raise TypeError(f"matches() takes str or ParsedName, got {a!r}")
        if isinstance(b, str):
            b = self.parse(b)
        elif not isinstance(b, ParsedName):
            raise TypeError(f"matches() takes str or ParsedName, got {b!r}")
        return a.comparison_key() == b.comparison_key()

    # -- rendering delegates ----------------------------------------------

    def capitalized(self, name: ParsedName, *,
                    force: bool = False) -> ParsedName:
        """:meth:`ParsedName.capitalized` under THIS parser's lexicon.
        The no-argument form of that method uses the DEFAULT lexicon --
        for names parsed with a custom Parser, use this method."""
        if not isinstance(name, ParsedName):
            raise TypeError(f"capitalized() takes a ParsedName, got {name!r}")
        return name.capitalized(self.lexicon, force=force)


@functools.cache
def _default_parser() -> Parser:
    return Parser()


def parse(text: str) -> ParsedName:
    """Parse a name with the default configuration and return a
    :class:`ParsedName`. Equivalent to ``Parser().parse(text)``; build
    your own :class:`Parser` (or use :func:`parser_for`) for custom
    vocabulary or behavior. Never raises on string content."""
    return _default_parser().parse(text)


def _reading_index_selected(languages: frozenset[str],
                            strict: bool = False) -> frozenset[str]:
    # the reading index loads on first lookup, so a caller who chooses
    # no language never imports it (decisions/vocabulary-model, 3a)
    from nameparser._reading_index import selected
    return selected(languages, strict=strict)


def _rewrapped(exc: Exception, message: str) -> Exception:
    """`exc`'s message with `message` before it, as a plain TypeError or
    ValueError: a subclass may take other constructor arguments
    (_lexicon._MaskValueError takes three)."""
    return (TypeError if isinstance(exc, TypeError) else ValueError)(
        f"{message}: {exc}")


def _with_packs(lexicon: Lexicon, locales: tuple[Locale, ...],
                languages: frozenset[str], strict: bool) -> Lexicon:
    """`lexicon` with the packs' fragments joined before it, in pack
    order, so its own readings outrank every pack's and a later pack's
    an earlier one's, and the choice of `languages` recorded, where the
    compile and its refusals happen (decisions/vocabulary-model,
    2026-11-02 #754, items 3 and 4). The case masks follow the same
    order: the choice moves `lexicon`'s, the packs' are laid over them,
    and a mask `lexicon` holds as the choice leaves the shipped one is
    no statement of the caller's, so a pack's mask of the word wins it,
    as a pack's readings win over the shipped ones."""
    fragments = Lexicon.empty()
    for loc in locales:
        fragments = fragments | loc.lexicon
    joined = fragments | lexicon
    if languages:
        chosen = _reading_index_selected(languages, strict)
        mine = dict(_rechosen_masks(lexicon, chosen, strict))
        shipped = dict(_rechosen_masks(Lexicon.default(), chosen, strict))
    else:
        mine = dict(lexicon.capitalization_exceptions)
        shipped = dict(Lexicon.default().capitalization_exceptions)
    masks = dict(mine)
    for k, v in fragments.capitalization_exceptions:
        if k not in mine or mine[k] == shipped.get(k):
            masks[k] = v
    cap = tuple(sorted(masks.items()))
    if not languages and cap == joined.capitalization_exceptions:
        return joined
    return dataclasses.replace(
        joined, capitalization_exceptions=cap, _languages=languages,
        _strict=strict)


def _failed_layer(lexicon: Lexicon, locales: tuple[Locale, ...],
                  languages: frozenset[str], strict: bool) -> str:
    """The layer a failed `_with_packs` names (rules/D2): the first pack
    whose fragment fails the join, or, where base's lexicon fails under
    the choice alone, the languages and the packs that chose them.
    Taken on the error path only, by building again pack by pack."""
    def fails(packs: tuple[Locale, ...]) -> bool:
        try:
            _with_packs(lexicon, packs, languages, strict)
        except (TypeError, ValueError):
            return True
        return False

    if not fails(()):
        for n, loc in enumerate(locales, 1):
            if fails(locales[:n]):
                return f"while applying locale {loc.code!r}"
    # base's lexicon fails alone only under the choice: with no
    # languages a join fails only on a pack, found above
    choosers = [repr(loc.code) for loc in locales if loc.languages]
    if lexicon.languages:
        choosers.append("base")
    return (f"while applying the languages chosen, "
            f"{', '.join(sorted(languages))} (by {', '.join(choosers)})")


def parser_for(*locales: Locale, base: Parser | None = None,
               segmenter: Segmenter | None | _Unset = UNSET,
               strict: bool | _Unset = UNSET) -> Parser:
    """The packs' ``languages`` and base's recorded choice unioned into
    one choice, recorded on the built parser's lexicon
    (:attr:`Parser.languages`), so the order of the packs, and whether
    they were chained through ``base``, does not change it:
    ``parser_for(EN, base=parser_for(PT))`` reads as ``parser_for(PT,
    EN)``. The packs' lexicon fragments are joined left-to-right and
    base's lexicon after them, so a caller's own readings outrank every
    pack's and a later pack's an earlier one's; the choice filters the
    shipped readings and every lexicon's ``add`` and ``remove`` apply
    after it, so a choice never drops a caller's word. A caller's
    reading that cannot stand beside one the choice turns on raises
    ValueError here, naming the call (decisions/vocabulary-model,
    2026-11-02 #754, items 3 and 4). Policy patches apply left-to-right
    (later wins; set-valued fields union per the patch metadata). A
    pack that chooses no language leaves the base vocabulary exactly
    as it is.

    ``strict=True`` makes the choice strict: only the chosen languages'
    vocabulary files are compiled, each tag selecting its own and its
    ancestors' as a plain choice does, plus mul.toml, the words every
    language writes alike (``Dr``, ``Prof``, ``PhD``, ``MSc``, the
    numerals), and a native-script word's readings (one with a letter
    and no Latin letter), name readings included, as a plain choice of
    the same languages keeps them; every other
    file's readings leave, und.toml's
    among them, and with them the markers they derive. It is for single-origin data
    (``parser_for(Locale(code="ko", lexicon=Lexicon.empty(),
    languages=frozenset({"ko"})), strict=True)`` reads ``Kim Do Hyun``
    with no Portuguese particle ``do``). A caller's own readings and the
    packs' fragments apply after it, as after a plain choice, and the
    policy patches unchanged. ``strict`` has three states, as
    ``segmenter`` does: omitted (:data:`~nameparser.UNSET`) keeps base's
    recorded strictness, ``False`` on a strict base raises ValueError, a
    strict choice not being undone by a later call, and ``True`` on a
    plain one makes the whole choice strict. A strict choice accepts a
    language whose file holds no reading yet (``hu``), which a plain
    one refuses as changing nothing, and raises ValueError when the
    packs choose no language, since it would then keep no language's
    own words, only mul.toml's and native-script words' readings
    (decisions/vocabulary-model, 2026-10-30 #753, file-strict, and
    2026-10-31 #753, phase 3j).

    Validation errors raised while applying a
    pack are wrapped with that pack's identity (rule D2) --
    PolicyPatch validates lazily, so with stacked packs the raw error
    would otherwise point at nothing. Two packs setting the same SCALAR
    field to different values is a declared conflict: UserWarning, later
    wins; two setting it to the same value agree, and nothing is warned.

    A ``segmenter`` is passed straight through to the built Parser --
    ``parser_for(locales.JA, segmenter=locales.ja_segmenter())`` is how
    a pack and a segmenter combine, since packs are pure data and
    cannot supply one. The argument has THREE states, the same
    :data:`~nameparser.UNSET` spelling a PolicyPatch field uses, because
    None is a meaningful value here and not an absence: omitted (UNSET)
    carries base's segmenter through unchanged; a callable OVERRIDES
    base's (later wins, the rule scalar policy fields follow); and an
    explicit ``None`` CLEARS base's, which is how you derive an
    unsegmented parser from a segmented one without rebuilding its
    lexicon and policy by hand."""
    if base is not None and not isinstance(base, Parser):
        raise TypeError(f"base must be a Parser or None, got {base!r}")
    if strict is not UNSET and not isinstance(strict, bool):
        raise TypeError(f"strict must be True or False, got {strict!r}")
    for loc in locales:
        if not isinstance(loc, Locale):
            raise TypeError(f"parser_for() takes Locale packs, got {loc!r}")
    lexicon = base.lexicon if base is not None else Lexicon.default()
    policy = base.policy if base is not None else Policy()
    # Resolved here rather than at the return because the return builds
    # a FRESH Parser: any field not listed there silently takes its
    # default, and a dropped segmenter would be invisible. UNSET, not
    # None, is what "not given" means -- None is the CLEAR request, and
    # collapsing the two would make an explicit
    # parser_for(..., segmenter=None) silently inherit the very
    # segmenter it was asked to drop.
    if segmenter is UNSET:
        segmenter = base.segmenter if base is not None else None
    # strict's three states, as segmenter's: omitted keeps base's
    # strictness; an explicit False on a strict base is refused, a
    # strict choice not being undone by a later call, and an explicit
    # True makes a plain base's choice strict (decisions/vocabulary-model,
    # 2026-11-02 #754, sub-phase 4i-c)
    if isinstance(strict, _Unset):
        strict = lexicon.strict
    elif lexicon.strict and not strict:
        raise ValueError(
            "base's lexicon was chosen with strict=True, and a chained "
            "choice keeps it: leave strict out or pass strict=True, or "
            "choose every language in one call from the default lexicon, "
            "base's packs included, parser_for(*packs, strict=False)")
    # one choice for all the packs and the base's, so applying them is
    # order-free; each pack's tags are checked on their own first, so a
    # tag no file holds is reported with the pack that named it
    # (rules/D2)
    languages = lexicon.languages
    for loc in locales:
        if loc.languages:
            try:
                _reading_index_selected(loc.languages, strict)
            except ValueError as exc:
                raise _rewrapped(
                    exc, f"while applying locale {loc.code!r}") from exc
            languages |= loc.languages
    if strict and not languages:
        raise ValueError(_no_strict_language(locales))
    try:
        lexicon = _with_packs(lexicon, locales, languages, strict)
    except (TypeError, ValueError) as exc:
        # rules/D2: "applying a locale pack wraps any such error with
        # the locale's code, so a stacked configuration names which
        # layer broke" -- the pack whose fragment broke the join, or,
        # where base's own lexicon clashes with the choice, the
        # languages and the packs that chose them (history:
        # decisions/vocabulary-model, 2026-10-29 3b and 2026-11-02 #754,
        # sub-phase 4i-c)
        raise _rewrapped(exc, _failed_layer(
            lexicon, locales, languages, strict)) from exc
    # each scalar field's setter so far and the value it left in the
    # policy: a later pack leaving another value overrides it, which is
    # warned; one leaving the same value (cs and sk's two_family_names)
    # agrees. Compared as the applied Policy holds it, canonical, so a
    # mapping written in another key order (script_orders) is the value
    # it is, not the spelling it was given in.
    scalar_setters: dict[str, tuple[str, object]] = {}
    scalars = [f.name for f in dataclasses.fields(PolicyPatch)
               if f.metadata.get("compose") != "union"]
    for loc in locales:
        # rules/D2: "applying a locale pack wraps any such error with
        # the locale's code, so a stacked configuration names which layer
        # broke" (history: decisions/D2)
        try:
            policy = apply_patch(policy, loc.policy)
        except (TypeError, ValueError) as exc:
            raise _rewrapped(exc, f"while applying locale {loc.code!r}") from exc
        for name in scalars:
            if getattr(loc.policy, name) is UNSET:
                continue
            value = getattr(policy, name)
            if name in scalar_setters:
                code, held = scalar_setters[name]
                if code != loc.code and held != value:
                    warnings.warn(
                        f"locale {loc.code!r} overrides scalar policy field "
                        f"{name!r} already set by locale {code!r}; later wins",
                        UserWarning, stacklevel=2)
            scalar_setters[name] = (loc.code, value)
    # rules/D1: "constructing a parser that activates division for
    # scripts with no covering surnames and no segmenter warns at
    # construction, naming the dead scripts and each way out"
    # (history: decisions/D1)
    # Construction warnings (the segmenterless-activation check in
    # Parser.__post_init__) re-emit from THIS frame: its stacklevel is
    # sized for direct Parser(...) construction, and through this
    # function's extra frame the default single-line rendering would
    # point into the library instead of at the caller -- the exact
    # call the message tells them to change.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        built = Parser(lexicon=lexicon, policy=policy, segmenter=segmenter)
    for w in caught:
        warnings.warn(w.message, stacklevel=2)
    return built


def _no_strict_language(locales: tuple[Locale, ...]) -> str:
    """The refusal of a strict call that chooses no language, which
    would keep only mul.toml's and native-script words' readings, dropping
    every language's own words in silence. The fix it offers is a pack
    choosing the first pack's code where that is a language a strict
    choice accepts, else ``en``."""
    tag = "en"
    if locales:
        try:
            _reading_index_selected(frozenset({locales[0].code}), True)
        except ValueError:
            pass
        else:
            tag = locales[0].code
    codes = ", ".join(repr(loc.code) for loc in locales)
    named = ("no pack was given" if not locales
             else f"the pack {codes} chooses none" if len(locales) == 1
             else f"the packs {codes} choose none")
    return (f"strict=True keeps only the chosen languages' vocabulary, "
            f"the shared words (mul.toml) and other scripts' words, and "
            f"{named}, so it would keep the shared and other scripts' "
            f"words alone; add "
            f"a pack that chooses a language, e.g. "
            f"Locale(code={tag!r}, lexicon=Lexicon.empty(), "
            f"languages=frozenset({{{tag!r}}})), or drop strict=True")
