"""Rendering for the 2.0 API: ParsedName -> display strings.

Layering: imports nameparser._types, and nameparser._lexicon for
Lexicon.default() (capitalized() with lexicon=None), _normalize and
FULL_STOPS (enforced by tests/v2/test_layering.py). Parsing code
never imports this module; ParsedName's rendering methods delegate
here via call-time imports.

Malformed str.format specs beyond unknown keys (positional fields,
bad conversions) surface the raw str.format error; only unknown KEYS
get the enriched KeyError.
"""
from __future__ import annotations

import re

from nameparser._lexicon import FULL_STOPS, Lexicon, _normalize
from nameparser._types import (FOLDED_TAG, SHAPE_ACRONYM_TAG,
                               UNCLASSIFIED_TAG, UNJOINED_CONJUNCTION_TAG,
                               UNJOINED_TAG, Ambiguity, ParsedName, Role,
                               Token)

_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_COMMA = re.compile(r"\s+,")
_COMMA_CHAR = re.compile(r"[,،，]")  # ASCII, Arabic, fullwidth
_MAC = re.compile(r"^(ma?c)(\w{2,})", re.IGNORECASE)
_WORD = re.compile(r"(\w|\.)+")

#: str.format keys render() accepts: the seven role fields in canonical
#: order (derived from Role -- never restated) plus the derived views.
_DERIVED_VIEWS = ("family_base", "family_particles", "surnames", "given_names")
_RENDER_KEYS = tuple(r.value for r in Role) + _DERIVED_VIEWS

#: str.format keys initials() accepts: the three name-bearing roles.
_INITIALS_KEYS = (Role.GIVEN.value, Role.MIDDLE.value, Role.FAMILY.value)

#: Tags whose tokens contribute no initial outside the given group --
#: unless the token also carries UNJOINED_TAG, i.e. the whole part is
#: particles, in which case they are the part's only words and do
#: contribute (rules.md#R3, #404). The mark readmits a token carrying
#: EITHER tag: a conjunction with nothing to join is not acting as a
#: conjunction any more than a particle with nothing to join is acting
#: as a particle, so it is a name word of the part like the rest.
#: Not STABLE_TAGS -- that also contains "initial", which must contribute.
_SKIP_TAGS = frozenset({"particle", "conjunction"})
#: The given group's own skip set (rules.md#R3, #461): a connective
#: contributes no initial in ANY group where it is joining words, so
#: the given group no longer exempts it -- "one rule for every group".
#: The particle exemption stays: a given-group particle is a name word
#: there, which is what the whole-group exemption was for.
_SKIP_TAGS_GIVEN = frozenset({"conjunction"})
#: Either unjoined mark readmits the word it sits on.
_UNJOINED_MARKS = frozenset({UNJOINED_TAG, UNJOINED_CONJUNCTION_TAG})

# Ported verbatim from v1 (nameparser/config/regexes.py "initial", minus
# the empty alternative) -- layering forbids importing the pipeline here;
# keep in sync with _pipeline/_vocab.py by hand.
# Its one reader is _reads_as_conjunction below, and that reader only
# ever sees a bare string with no token attached to it -- a spliced
# field (replace()), restored state (__setstate__: a pickle load,
# copy.copy, or copy.deepcopy), a direct string call, or -- since
# 84d9000 -- a widen-only _process_initial override that drops the
# token it was handed on its way to the string path. The first two
# never had a token to begin with: for anything the parser classified
# AND the caller passed the token along, the tag is the answer and
# this pattern is not asked. The last two might have been classified
# and the reader cannot tell -- it only knows no token was passed.
# So the two copies no longer decide the same question about the same
# token -- _vocab's says what the parse decided, this one says what it
# WOULD have decided about text handed over with no token -- which is
# why they must keep answering alike, and why test_regex_sync pins the
# patterns against each other and against config.
# Deliberately NOT composed with _vocab's repertoire test (#320):
# layering forbids the import. The divergence is reachable only for a
# caller-added CJK conjunction spliced into a field, since no shipped
# vocabulary carries one, and it costs nothing there: CJK is caseless,
# so the carve-out's lower() and the fall-through's capitalize() return
# the same string. Since #528 this pattern is read by more than case
# repair: through _reads_as_conjunction below, whose callers are case
# repair's spliced field and the v1 facade's initials view, the latter
# in three shapes -- a token carrying UNCLASSIFIED_TAG
# (_facade._token_is_conjunction), a direct _process_initial call with
# no tokens at all, and, since 84d9000, a widen-only _process_initial
# override that drops a token the parse DID classify. For initials the
# CJK divergence would decide whether such a spliced, dropped or
# never-parsed connective contributes a letter rather than which case
# it renders in -- still unreachable from any shipped vocabulary, and
# still not worth the import layering forbids.
_INITIAL = re.compile(r"^(\w\.|[A-Z])$")

#: The hyphen clause's own initial test (_cap_text, #478): _INITIAL's
#: period alternative alone. The bare-capital half is deliberately not
#: used here -- admitting it would exempt a capital connective from
#: the clause on its CASE alone, reading it as an initial and leaving
#: it uppercase. The dotted test runs before the vocabulary test, and
#: a capital DOES lower there: 'Y' in 'JOSE ORTEGA-Y-GASSET' reaches
#: the vocabulary test and lowers to 'Ortega-y-Gasset'. Exempting it
#: on case is exactly the reading #458 removed from case repair
#: generally. Registered in tests/v2/test_regex_sync.py as the period
#: alternative of _INITIAL's pattern, so the two cannot drift apart
#: unnoticed.
_DOTTED_INITIAL = re.compile(r"^\w\.$")

# v1 regexes.py "roman_numeral" -- the pipeline's _vocab._ROMAN,
# copied by hand because layering forbids this module the import
# (the reason _INITIAL above is a copy too) and pinned against config
# by tests/v2/test_regex_sync.py. Its one reader is _cap_word's
# numeral clause, which asks a RENDERING question of a word the parse
# already put in the suffix role -- how a numeral is written -- and
# not the parse's own question of whether the word is a suffix, so
# the role is honored rather than re-derived
# (mechanisms.md#RENDER-HONORS-THE-PARSE).
_ROMAN = re.compile(r'^(X|IX|IV|V?I{0,3})$', re.I)


def _reads_as_conjunction(word: str, lex: Lexicon) -> bool:
    """v1's is_conjunction, asked only where the CALLER supplies no
    token.

    A token the parse classified carries its reading in its tags, and
    the library's own token path -- _facade._token_is_conjunction --
    consults that tag first and never reaches here for a token it
    holds. This function is reached only where there is no token to
    consult: a field spliced in as raw text (replace()) or restored
    state (__setstate__: a pickle load, copy.copy, or copy.deepcopy),
    both carrying UNCLASSIFIED_TAG; a direct call with no parse behind
    it; or, since 84d9000, a widen-only _process_initial override that
    drops the token it was handed on its way to the string path --
    text the parse DID classify, whose reading the override chose not
    to forward. This function cannot tell any of those apart from one
    another; it can only give the answer the parser would have given
    from the word alone, the initial carve-out included ('E.' assigned
    to middle is an initial, not the Italian conjunction). What it
    cannot give is an answer the parse reached by looking at the whole
    NAME -- rules.md#P3's one-case fork is the live example -- which
    is why it is the fallback and the tags are the rule.
    """
    return bool(_normalize(word) in lex.conjunctions
                and not _INITIAL.fullmatch(word))


def _collapse(rendered: str) -> str:
    """The #254 collapse: empty fields substitute '' and every artifact
    of that is removed -- dangling empty-nickname wrappers, space runs,
    space-before-comma, one trailing comma character (any script),
    leading/trailing ', ' debris."""
    rendered = (rendered.replace(" ()", "")
                        .replace(" ''", "")
                        .replace(' ""', ""))
    rendered = _SPACE_BEFORE_COMMA.sub(",", rendered)
    rendered = _SPACES.sub(" ", rendered.strip())
    if rendered and _COMMA_CHAR.fullmatch(rendered[-1]):
        rendered = rendered[:-1]
    return rendered.strip(", ")


def _format_spec(spec: str, values: dict[str, str], noun: str,
                 keys: tuple[str, ...]) -> str:
    """Shared tail of render()/initials(): fill the spec, enrich
    unknown-KEY errors with the valid key list, collapse."""
    if not isinstance(spec, str):
        raise TypeError(f"spec must be a str, got {spec!r}")
    try:
        rendered = spec.format(**values)
    except KeyError as exc:
        raise KeyError(
            f"unknown {noun} field {exc.args[0]!r}; valid fields: "
            f"{', '.join(keys)}"
        ) from None
    return _collapse(rendered)


def render(name: ParsedName, spec: str) -> str:
    """Fill the str.format spec from the seven role fields and the
    derived views (empty fields substitute ''), then apply the #254
    collapse. Unknown keys raise KeyError naming the valid fields."""
    values = {key: getattr(name, key) for key in _RENDER_KEYS}
    return _format_spec(spec, values, "render", _RENDER_KEYS)


# rules.md#R3: "initials take the first letter of each given, middle,
# and base family word; titles, suffixes, particles and nicknames
# contribute nothing"
def initials(name: ParsedName, spec: str, delimiter: str, separator: str) -> str:
    """First letter of each contributing token per group, v1 semantics:
    delimiter follows each initial, separator sits between initials
    within a group. Each group is ordered the way its FIELD is
    ordered -- written order, except folded words, which initial
    before the rest of the group (#408).
    A token tagged conjunction contributes no initial in ANY group,
    and one tagged particle contributes none in middle/family
    (given-group particles always contribute); either unjoined mark
    readmits the word it sits on, so the words of an all-particle part
    and a connective with nothing in its part to join both count;
    tags come from the pipeline --
    hand-built untagged tokens all contribute, and so do the words of
    a field spliced in by replace(), which the parse never read.
    This view takes NO lexicon, so it has none to fall back to for
    that text: `replace(family='de la vega')` initials every word of
    that field where the same name parsed gives 'j. v.'
    (rules.md#R3's Accepted
    clause, and decisions.md#R4 for why the fallback was tried
    and dropped -- #464 is the crossing that would make it
    answerable). Valid spec keys: given, middle, family."""
    if not isinstance(delimiter, str):
        raise TypeError(f"delimiter must be a str, got {delimiter!r}")
    if not isinstance(separator, str):
        raise TypeError(f"separator must be a str, got {separator!r}")
    values: dict[str, str] = {}
    for key in _INITIALS_KEYS:
        role = Role(key)
        tokens = name.tokens_for(role)
        skip = _SKIP_TAGS_GIVEN if role is Role.GIVEN else _SKIP_TAGS
        tokens = tuple(t for t in tokens
                       if not (skip & t.tags)
                       or _UNJOINED_MARKS & t.tags)
        # mechanisms.md#FOLDED_TAG: "a rule that needs different
        # rendering order tags the token, and the rendering views
        # consult the tag" -- this is a rendering view, so it reads
        # the tag the same way _types._text_for does, and for the same
        # reason: the fold is an ORDER the parse recorded, not one the
        # view is free to take again
        # (mechanisms.md#RENDER-HONORS-THE-PARSE: "the parse decides
        # it; the render views honor those decisions and never
        # re-evaluate them"). Applied to every role this view renders,
        # exactly as _text_for applies it -- the pipeline puts the tag
        # on FAMILY tokens alone today, so GIVEN and MIDDLE are
        # uniformity with the mechanism rather than reachable
        # behavior; a producer that ever folds into another part would
        # otherwise reopen #408 there.
        tokens = (tuple(t for t in tokens if FOLDED_TAG in t.tags)
                  + tuple(t for t in tokens if FOLDED_TAG not in t.tags))
        values[key] = separator.join(
            t.text[0] + delimiter for t in tokens)
    return _format_spec(spec, values, "initials", _INITIALS_KEYS)


def _letter_run_ge2(text: str) -> list[bool]:
    """One flag per alphanumeric character of `text`, in the order
    _apply_mask below walks them: True where that character is a
    LETTER with a letter immediately before or after it WITHIN
    `text` -- a full stop or a digit breaks a run, exactly as either
    breaks one in the word _apply_mask is casing. A digit's own flag
    is always False; the initial-beside-a-stop exception only ever
    concerns letters."""
    n = len(text)
    flags: list[bool] = []
    for i, c in enumerate(text):
        if not c.isalnum():
            continue
        if not c.isalpha():
            flags.append(False)
            continue
        prev_letter = i > 0 and text[i - 1].isalpha()
        next_letter = i + 1 < n and text[i + 1].isalpha()
        flags.append(prev_letter or next_letter)
    return flags


# rules.md#R4: "the writer split a chunk the mask keeps together, so
# the split-off letter is an initial" -- the split-initial exception
# the docstring below states in one sentence and defers to.
def _apply_mask(word: str, mask: str) -> str | None:
    """rules.md#R4's mask: `word` with each letter or digit recased to
    the case of the mask's alphanumeric in the same position, and
    every other character kept where the writer put it -- 'ph.d.'
    under 'PhD' is 'Ph.D.'. None where the two alphanumeric counts
    differ. The lookup key makes that rare and not impossible: the
    key is the word NFC-composed, so a word written in decomposed
    hangul spells one syllable in two letters and still finds a
    one-letter key. The caller falls through to its next clause
    rather than guess.

    One exception the mask does not decide: a SINGLE LETTER split off
    alone beside a full stop is written in capitals whatever the mask
    says there, but only where the mask itself writes that letter
    inside a run of two or more letters (the rule stated above this
    function). What the code adds past that statement: a run is of
    LETTERS only, so a DIGIT ends one exactly as a full stop does; the
    full stop tested is any of FULL_STOPS, not the ASCII period alone
    (#322) -- though through capitalized() only the ASCII period is
    ever reachable, since _WORD splits a token at any other stop and
    this function never sees the rest of the word; the fullwidth row
    in test_render pins the direct call, which is reachable.

    Casing goes through the WHOLE word (word.lower()/word.upper())
    rather than per character, when both have the same length as
    `word`: a per-character str.lower()/str.upper() call is
    context-free and gets some letters wrong that the whole-word form
    gets right -- a medial sigma where Greek wants a final one, for
    one. A mask letter is read as upper when it is not lower
    (`not letter.islower()`), so a titlecase letter (Unicode category
    Lt) reads as upper rather than lower -- a known limit: no
    per-character titlecase mapping is attempted."""
    mask_chars = [c for c in mask if c.isalnum()]
    if len(mask_chars) != sum(1 for c in word if c.isalnum()):
        return None
    mask_run = _letter_run_ge2(mask)
    lowered = word.lower()
    uppered = word.upper()
    same_length = len(lowered) == len(word) and len(uppered) == len(word)
    n = len(word)
    out: list[str] = []
    at = 0
    for i, c in enumerate(word):
        if not c.isalnum():
            out.append(c)
            continue
        mask_char = mask_chars[at]
        in_mask_run = mask_run[at]
        at += 1
        if c.isalpha():
            prev_letter = i > 0 and word[i - 1].isalpha()
            next_letter = i + 1 < n and word[i + 1].isalpha()
            beside_stop = (i > 0 and word[i - 1] in FULL_STOPS) or (
                i + 1 < n and word[i + 1] in FULL_STOPS)
            if (not prev_letter and not next_letter and beside_stop
                    and in_mask_run):
                out.append(uppered[i] if same_length else c.upper())
                continue
        if mask_char.islower():
            out.append(lowered[i] if same_length else c.lower())
        else:
            out.append(uppered[i] if same_length else c.upper())
    return "".join(out)


def _cap_word(word: str, role: Role, tags: frozenset[str],
              lex: Lexicon) -> str:
    # Clause order: the particle/connective arm, then the exceptions
    # map as a mask, then the acronym clause (listed or by shape),
    # then the numeral clause, then Mac/Mc, then str.capitalize. v1's
    # cap_word had the first, second, fifth and sixth in this order;
    # the mask ahead of the acronym clause is what gives bsc 'BSc'
    # though bsc is a listed acronym too.
    normalized = _normalize(word)
    # rules.md#R4: "a part whose every word is particle vocabulary is
    # repaired as ordinary name words, since none of them is doing a
    # particle's work there" -- UNJOINED_TAG is that mark (#407).
    # Only the PARTICLE conjunct is gated on it, and that is the rule
    # rather than an omission -- rules.md#R4: "A CONNECTIVE the parse
    # placed among the name words keeps its lowercase wherever it
    # stands there, including inside a part whose other words the
    # unjoined mark has turned into ordinary name words" -- so a
    # conjunction keeps conjunction treatment even inside a part the
    # mark has turned into ordinary name words.
    # The `generation` guard below is the other half of that sentence:
    # a word this vocabulary holds can ALSO be the generation it
    # spells ('i' is the Catalan link and the roman numeral), and
    # where the parse read the generation the token still carries the
    # `conjunction` tag classify gave it -- so without the guard,
    # `parse("John Quincy Smith i").capitalized(force=True)` gave
    # 'John Quincy Smith i' where every release through 2.3 gave
    # 'John Quincy Smith I' (#397 review). Such a token is repaired
    # as the suffix it was read as, which is the rest of R4's
    # sentence: "one the parse read as the generation it also spells
    # is not a connective of this name at all".
    # BOTH HALVES, and the role alone is not enough -- the role says
    # where the word landed and the vocabulary says whether landing
    # there made it a generation. A plain connective can land in the
    # suffix field without being generational vocabulary at all (a
    # third comma part: `Smith, John, and`), and on the role test
    # alone every one of them was repaired as a name word --
    # 'John Smith And' where 1.4.0, 2.0 through 2.3 and the parent
    # commit all gave 'John Smith and', and 'John Smith De, Y' for a
    # field spliced to suffix='de y' where R4's own Accepted
    # paragraph says the vocabulary answers and the 'y' keeps its
    # lowercase (#397 second review). `vocab:suffix` is classify's
    # record of the vocabulary half, so the pair reads two decisions
    # the parse already made and re-derives neither
    # (mechanisms.md#RENDER-HONORS-THE-PARSE).
    # It guards the whole test rather than the two conjunction arms
    # alone, which reads as the wider claim and is not one: the
    # particle arm asks for role MIDDLE or FAMILY, so a SUFFIX-roled
    # token can never reach it either way.
    # No SHIPPED name witnesses the difference: `particles` and
    # `conjunctions` are disjoint in the default vocabulary and in
    # every locale pack, so no shipped conjunction can sit in an
    # all-particle part and carry the mark. That is a property of the
    # shipped DATA, not an invariant -- both sets are public,
    # configurable API, and a caller's Lexicon may put one word in
    # both, the way _pipeline/_post_rules.py's arms allow for. Measured:
    # under `Lexicon.default().add(particles={'y'})`, `anh y van` has
    # an all-particle family whose `y` carries both tags and the mark,
    # and gives 'Anh y Van'; gating this conjunct too would give
    # 'Anh Y Van'. That is pinned by test_repair_keeps_a_conjunction_
    # lowercase_in_a_particle_part -- until which gating it passed the
    # whole suite.
    # initials() does NOT match this carve-out, and since #461 that
    # is a DECIDED disagreement rather than a recorded one: a
    # connective that initials because it joins nothing is still not
    # written the way a name is written, which is the sentence quoted
    # above and this rule's own reason rather than a borrowing from
    # R3. Under that same lexicon `Anh y Van` repairs to 'Anh y Van'
    # and initials 'A. y. V.' -- the two views agreeing on this row
    # because R2's mark readmits the word for both -- while
    # `parse("Juan de y")` repairs to 'Juan de y' and initials
    # 'J. y.', where they part. Pinned by
    # test_initials_readmits_a_conjunction_in_a_particle_part and
    # test_repair_keeps_a_lone_connective_lowercase_where_it_initials.
    # That conjunct reads the TAG, not the word (#458). classify takes
    # the conjunction-versus-initial decision once, over the whole
    # token -- v1's is_conjunction excludes initials, so 'E.' in
    # 'Scott E. Werner' is an initial and is never tagged (pinned live
    # 2026-07-17) -- and a view honors that decision rather than
    # taking it again from the spelling
    # (mechanisms.md#RENDER-HONORS-THE-PARSE: "the render views honor
    # those decisions and never re-evaluate them"), the tags being
    # classify's record of it (mechanisms.md#VOCAB-TAGS: "later stages
    # test tags"). Asking again was not even the same question:
    # the copy of the initial pattern that stood here was the SHAPE
    # half alone, and it re-decided per WORD of a token's text, so
    # 'juan e-f smith' capitalized to 'Juan e-F Smith'.
    # mechanisms.md#RENDER-HONORS-THE-PARSE: "a token the parse never
    # saw carries no decision to honor, so a view falls back to the
    # vocabulary" -- _reads_as_conjunction above, which is v1's
    # predicate applied over TODAY's vocabulary rather than 1.4.0's.
    # That is the honest claim and it is narrower than parity: the two
    # vocabularies differ, so an assigned field can repair differently
    # from 1.4.0 without this predicate differing at all. Measured on
    # the released wheel: `h.last = "хосе и мария сантос"` gives
    # 'Хосе И Мария Сантос' on 1.4.0 and 'Хосе и Мария Сантос' here,
    # the Cyrillic `и` being a 2.x conjunction and not a 1.4.0 one;
    # `h.last = "de la vega"` gives 'de la Vega' there and here.
    # The mark, not the SPAN, is what says the text was never read:
    # Parser.revise() also builds span-less tokens, from a sub-parse
    # whose tags it keeps on purpose, and keying this on `span is None`
    # overrode them -- `revise(middle='e-f')` repaired to 'e-F' where
    # the same words parsed gave 'E-F' (#463 review).
    generation = role is Role.SUFFIX and "vocab:suffix" in tags
    if not generation and (
            (normalized in lex.particles
             and role in (Role.MIDDLE, Role.FAMILY)
             and UNJOINED_TAG not in tags)
            or "conjunction" in tags
            or (UNCLASSIFIED_TAG in tags
                and _reads_as_conjunction(word, lex))):
        return word.lower()
    # v1 cap_word tries the edge-stripped form, then the period-free
    # form ('Ph.D.' -> 'ph.d' -> 'phd' hits the exceptions map). The
    # value found is a MASK, not a replacement (#459): it recases the
    # word as the writer punctuated it, so 'Ph.D.' under 'PhD' stays
    # 'Ph.D.' and 'phd' becomes 'PhD'. v1 substituted the value, which
    # is how 'md' became 'M.D.' and 'iii.' lost its period;
    # rules.md#R4: "Repair changes case and nothing else". Role-free,
    # as the map always was: an entry is the caller saying how a word
    # is written wherever it stands.
    for key in (normalized, normalized.replace(".", "")):
        mask = lex.capitalization_exceptions_map.get(key)
        if mask is not None:
            masked = _apply_mask(word, mask)
            if masked is not None:
                return masked
    # A credential acronym the exceptions map doesn't carry (mba, jd,
    # qc, and md since #459 took it out of the map) is an initialism,
    # not a word to title-case: a one-case name repairs to the
    # acronym's caps instead of 'Mba' (#459). So is a word classify
    # admitted to the credential class by its dotted SHAPE alone
    # (SHAPE_ACRONYM_TAG; rules.md#S3's unlisted 'x.y.z.'), which has
    # no vocabulary entry to be listed in. The mask above is asked
    # first, which is what keeps a conventionally mixed-case acronym as
    # it is written (bsc -> BSc) though it is listed here too. Gated
    # on the SUFFIX role so a word that is a family name only happens
    # to be in the vocabulary (anh van DO) still repairs as an ordinary
    # name word -- #459's given-role half, decided: repair follows the
    # role the parse chose ('qc mp' -> 'Qc MP').
    if role is Role.SUFFIX and (
            normalized.replace(".", "") in lex.suffix_acronyms
            or SHAPE_ACRONYM_TAG in tags):
        return word.upper()
    # rules.md#R4: "A roman numeral the parse put in the suffix role is
    # written in capitals" whether or not the vocabulary lists it: 'vi'
    # through 'x' carry no vocabulary tag and title-cased to 'Vi'/'Ix'
    # until #459, while 'ii'/'iii'/'iv' rode the exceptions map, which is
    # why they left it. Suffix-gated for the acronym clause's reason
    # -- 'Vi' is a given name -- and it is also what writes a
    # generational 'i' the connective arm's `generation` guard let
    # through ('Carod i' forced -> 'Carod I').
    if role is Role.SUFFIX and _ROMAN.match(normalized):
        return word.upper()
    if _MAC.match(word):
        return _MAC.sub(
            lambda m: m.group(1).capitalize() + m.group(2).capitalize(),
            word)
    return word.capitalize()


def _cap_text(text: str, role: Role, tags: frozenset[str],
              lex: Lexicon) -> str:
    # word-by-word within the token text: hyphenated names capitalize
    # both sides ("macdole-eisenhower" -> "MacDole-Eisenhower"). The
    # per-word walk is also why an UNCLASSIFIED token gets the
    # vocabulary asked per word: the parse would have made one token
    # per word of that text, so this is the granularity its answer
    # would have had.
    def cap(match: re.Match[str]) -> str:
        return _cap_word(match.group(0), role, tags, lex)

    if "-" not in text:
        return _WORD.sub(cap, text)
    parts = text.split("-")
    named = [at for at, part in enumerate(parts) if _WORD.search(part)]
    if len(named) < 3:
        return _WORD.sub(cap, text)
    # rules.md#R4: "Inside a hyphenated word, a part that is
    # connective vocabulary with a worded part on each side of it
    # keeps its lowercase" -- the hyphens are the writer joining the
    # name around it, as the spaced connective would (#478). Position
    # and vocabulary both come from the whole token, which is why
    # this sits here and not in _cap_word, whose word has lost its
    # neighbours. It does NOT re-derive the conjunction-versus-
    # initial class from a word's CASE, the thing #458 removed: an
    # EDGE part has a part on one side only and stays ordinary name
    # text, so 'juan e-f smith' keeps 'E-F'. A 'part' is one holding
    # a word; an empty part does not count and is skipped, so a
    # trailing hyphen ('md-phd-') supplies no neighbour while a
    # doubled one changes nothing ('garcia--y-lopez' keeps its 'y'
    # lowercase), and the two-part compound ('mcnabb-smith') never
    # gets past the count above. The period is the one punctuation
    # mark classify itself reads as an initial: a single letter marked
    # with a period is read as an initial there, as the parse reads
    # it, never as the connective, so 'j.-e.-p. dupont' keeps 'E.'
    # while the multi-letter 'und.' in 'hans smith-und.-jones' still
    # lowers.
    first, last = named[0], named[-1]
    return "-".join(
        part.lower()
        if (first < at < last and not _DOTTED_INITIAL.fullmatch(part)
                and _normalize(part) in lex.conjunctions)
        else _WORD.sub(cap, part)
        for at, part in enumerate(parts))


# rules.md#R4: "case repair returns a repaired copy and never mutates
# the parse"
def capitalized(name: ParsedName, lexicon: Lexicon | None, *,
                force: bool) -> ParsedName:
    """Case-fixing transform -> new ParsedName, same spans, new token
    texts. Gate: only a name whose words outside the suffix are
    written in one case is touched unless force=True; the gate reads
    the joined texts of every token not roled SUFFIX (#492) -- not
    render() output, so it stays decoupled from spec formatting and
    the #254 collapse.
    Repair changes case and nothing else (see the rules.md#R4 citation
    in _cap_word): an exceptions-map value is a mask recasing the word
    as written (#459), never a replacement.
    The repair reads token TAGS as well as texts: a part whose every
    word is particle vocabulary is repaired as ordinary name words,
    and the mark saying so comes from the pipeline, as does the
    reading that a word is a conjunction rather than an initial. A
    token carrying UNCLASSIFIED_TAG -- replace() splices those in, and
    so does the facade's v1 pickle load -- was never read: the
    vocabulary answers the per-word conjunction question for it, and
    the per-part particle question is left to plain particle treatment,
    since re-deriving the part answer needs a tag on every word of the
    part and these have none. A family set that way to 'de la' stays
    'de la' where the same words parsed give 'De La'; one set to
    'de y' keeps the 'y' lowercase, as the parse does and as 1.4.0
    did. Parser.revise() is the edit that classifies the value, and
    gives 'De La' (rules.md#R4's Accepted boundary).
    Idempotent: every _cap_word rule, and the hyphen rule in
    _cap_text, is a fixpoint on its own output, so a repaired name
    comes back unchanged whether or not the gate admits it again
    (a name whose non-suffix words are caseless, 'Kim Minjun' in
    hangul with a 'phd', is admitted every time)."""
    if lexicon is not None and not isinstance(lexicon, Lexicon):
        # eager, before the gate: a garbage argument must not become a
        # silent no-op on mixed-case input or a deep AttributeError
        raise TypeError(f"lexicon must be a Lexicon or None, got {lexicon!r}")
    lex = Lexicon.default() if lexicon is None else lexicon
    # rules.md#R5: "case repair acts only on a name written entirely
    # in one case" -- and "the suffixes are left out of that test": a
    # credential or a generation written the way one is written
    # ('III', 'PhD', 'Jr.') says nothing about how the writer cased
    # the NAME (#492). Titles stay in because title repair is not yet
    # trusted to act on a cased title (decisions.md#R5 names the three
    # titles that showed why).
    gate = " ".join(t.text for t in name.tokens
                     if t.role is not Role.SUFFIX)
    if not force and gate not in (gate.upper(), gate.lower()):
        return name
    new_tokens = tuple(
        Token(_cap_text(t.text, t.role, t.tags, lex), t.span, t.role, t.tags)
        for t in name.tokens)
    # equal tokens (possible only for synthetic span=None duplicates)
    # collapse to one mapping entry -- benign: the rebuilt ambiguity
    # references an equal token, so the subset invariant still holds
    replacement = dict(zip(name.tokens, new_tokens))
    new_ambiguities = tuple(
        Ambiguity(a.kind, a.detail,
                  tuple(replacement[t] for t in a.tokens))
        for a in name.ambiguities)
    return ParsedName(original=name.original, tokens=new_tokens,
                      ambiguities=new_ambiguities)
