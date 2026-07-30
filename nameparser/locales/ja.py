"""The Japanese locale pack (#272): activates segmentation for the
Japanese repertoire -- Han and the kana-licensed composites that
resolve to HIRAGANA -- so that an unspaced 山田太郎 can be divided at
all. Applying this pack IS the "my data is Japanese" declaration, the
same role locales.ZH plays for Chinese: a pure-Han string cannot say
which language it is written in (林 is Lin or Hayashi), so neither
activation may be a default.

Unlike zh, this pack ships NO vocabulary and NO order:

* No vocabulary, because no surname list divides Japanese names. Family
  and given names draw on the same kanji, both sides run one to four
  characters, and the reading -- not the spelling -- is what settles
  most splits. That is what the pluggable segmenter is for, and it is
  why this pack alone is inert: it activates a stage that then has
  nothing to segment with.
* No order, because a kana-bearing Japanese name already reads
  family-first by default (amendment 2026-07-29 §1: hiragana identifies
  native Japanese as certainly as hangul identifies Korean), and wholly
  Han names have read family-first since the 2026-07-27 amendment.
  Pure KATAKANA is deliberately outside both the order rule and the
  activation set above -- katakana is how Japanese writes FOREIGN names
  (マイケル・ジャクソン), in their original given-first order.

Data sources: none. The pack carries no vocabulary of its own, so
there is no list here to cite, extend or keep current -- the data that
divides a Japanese name belongs to the segmenter, and namedivider's
sources and their terms are set out under Licensing below.

The segmenter is a FACTORY, ``ja_segmenter()``, not pack data: a Locale
is pure data that dissolves into a Parser at construction, and a
third-party callable is neither pure nor data. Combining the two is
explicit -- ``parser_for(locales.JA, segmenter=locales.ja_segmenter())``
-- which also keeps the optional dependency out of every import path
that merely touches this module.

Licensing (the optional dependency is never bundled; nameparser's own
LGPL is untouched): namedivider-python's source and its GBDT model are
MIT. Its surname data -- ``family_name_repository.pickle``, sourced
from Myoji-Yurai.net -- carries custom terms permitting commercial and
non-commercial use *for dividing names*, which is the only use any
caller of this module can put it to. Those terms bind only the opt-in
``ja_segmenter(gbdt=True)`` path, which is what loads that file; the
default BasicNameDivider reads namedivider's own bundled kanji.csv and
never touches it. Its BERT model for katakana division is CC-BY-SA and
is NOT used (katakana division is out of scope, amendment §6).

Declared deviations (spec §2 authoring requirement 3): the pack sets
one union policy field, self-selecting by script, so it can only change
names containing characters of the Japanese repertoire -- DEVIATES
below declares exactly that, over-declaring within the repertoire (a
name also needs an unspaced token and a segmenter to actually change,
but declaring every repertoire-bearing name is the safe direction,
zh's precedent).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import PolicyPatch, Script, _script_matcher
from nameparser._types import Segmentation

if TYPE_CHECKING:
    from nameparser._types import Segmenter

JA = Locale(
    code="ja",
    lexicon=Lexicon.empty(),
    policy=PolicyPatch(
        segment_scripts=frozenset({Script.HAN, Script.HIRAGANA})),
)

#: The scripts DEVIATES and the adapter quantify over. KATAKANA is
#: here even though the pack never ACTIVATES it: a katakana-bearing
#: token can still be a kana-licensed composite the pack acts on
#: (山田エミ) -- DEVIATES must declare it, and the adapter must not
#: decline it. A
#: pure-katakana token never reaches THE ADAPTER: KATAKANA is in no
#: activation set, so the stage's own gate stops it before the
#: segmenter is consulted. DEVIATES still declares one, and must: it
#: is a predicate over any name at all, called before any gate runs,
#: and over-declaring is its safe direction by design.
_JA_SCRIPTS = (Script.HAN, Script.HIRAGANA, Script.KATAKANA)

# Both compiled by _policy's factory from the shared codepoint table,
# so the pack carries no spans of its own to drift out of sync: the
# contains-any form backs DEVIATES, the whole-token form is the
# adapter's repertoire guard.
_has_japanese = _script_matcher(*_JA_SCRIPTS)
_wholly_japanese = _script_matcher(*_JA_SCRIPTS, whole=True)


#: How far outside [0, 1] a namedivider score may stray and still count
#: as float noise around a real answer rather than a broken divider --
#: see the adapter's own comment for why it is float32-sized.
_SCORE_EPSILON = 1e-6


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes): any name bearing a repertoire
    character -- see the repertoire note above for why katakana is
    declared and why over-declaring is safe."""
    return _has_japanese(name)


def ja_segmenter(*, gbdt: bool = False) -> Segmenter:
    """A :data:`~nameparser.Segmenter` wrapping namedivider-python,
    installed with ``pip install nameparser[ja]``:

        parser = parser_for(locales.JA, segmenter=locales.ja_segmenter())

    Wraps ``BasicNameDivider`` (99.3% accurate, ~4k names/sec, pure
    Python) by default, which needs only data bundled in the installed
    package; ``gbdt=True`` selects ``GBDTNameDivider`` (99.9%), which
    asks more of the environment on two counts. It runs namedivider's
    gradient-boosted model through lightgbm -- a hard dependency of
    namedivider-python, so the extra installs it, but its wheel does
    not bundle the native OpenMP runtime it loads at import (a missing
    ``libomp`` surfaces as lightgbm's own OSError naming the library it
    could not find). And the first such call DOWNLOADS its model and
    surname files from the network into ``~/.cache/namedivider-python``
    (namedivider prints its own progress to stdout doing so), which
    matters for offline, sandboxed or air-gapped deployments.

    The adapter declines -- returns None, leaving the token whole --
    for text outside the Japanese repertoire, for text bearing the
    shime mark 〆 (namedivider 0.4.x's rule path cuts it in the wrong
    place), for text too short to divide, for any answer that fails to
    reconstruct its input, and for
    any score outside [0, 1] by more than float noise (a divider
    scoring 87.0 is broken, and its division is worth no more than its
    score). An
    answer that puts the whole token on one side comes back as
    "confidently one token" rather than a decline: the divider read it
    and found nothing to cut, which is not the same as having no
    opinion.
    Answers arrive with namedivider's own confidence, which the parsing
    stage compares against its floor to decide whether to report a
    SEGMENTATION ambiguity: namedivider scores a rule-based division
    (the kana boundary in 高橋みなみ, or a two-character name) 1.0 and
    a kanji-statistics division well below that, so every
    statistically divided name carries the report and every
    rule-divided one carries none. The two-character rule is the case
    to know about: dividing 原恵 one character each way is a
    presumption Japanese practice makes, not a measurement (usage.rst
    says so), yet the 1.0 keeps it silent. That is namedivider's own
    stated certainty, taken as given here; ``DividedName.algorithm``
    names which rule answered and is the hook if presumption-reporting
    is ever wanted.
    """
    try:
        import namedivider
    except ImportError as exc:
        raise ImportError(
            "the Japanese segmenter needs namedivider-python -- "
            "install it with: pip install nameparser[ja]"
        ) from exc
    divider = (namedivider.GBDTNameDivider() if gbdt
               else namedivider.BasicNameDivider())

    def segment(text: str) -> Segmentation | None:
        # segment_scripts UNIONS under pack composition, so this can
        # receive tokens of any other activated script (hangul, under
        # the default policy). Decline anything outside the Japanese
        # repertoire rather than hand it to namedivider, which would
        # answer for it regardless -- the same union DEVIATES declares.
        if not _wholly_japanese(text):
            return None
        # namedivider 0.4.x has no knowledge of the shime mark: its
        # rule path cuts 〆木太郎 to 〆 | 木太郎 at confidence 1.0
        # (measured -- wrong for every attested 〆 surname: 〆木, 〆谷,
        # 〆野), so a wrong family would arrive with no SEGMENTATION
        # report. Decline instead: the family-first ORDER fix for 〆
        # stands regardless, and division can return when a divider
        # knows the mark.
        if "〆" in text:
            return None
        # namedivider RAISES below two characters ("Name length needs
        # at least 2 chars"), and a segmenter's exceptions propagate by
        # contract, so a one-character token -- routine in spaced input
        # like "林 太郎" -- must be declined here, not passed on.
        if len(text) < 2:
            return None
        result = divider.divide_name(text)
        if result.family + result.given != text:
            return None          # defensive: never trust reconstruction
        # float(): the score is a numpy scalar on the statistical path.
        # Two different failures wear the same shape here, and they get
        # different answers. Float error at the edge of namedivider's
        # softmax is arithmetic noise around a real answer, so an
        # epsilon either side of [0, 1] is tolerated and clamped --
        # Segmentation enforces the range and would otherwise raise
        # mid-parse. A score OUTSIDE that epsilon is not noise: a
        # divider reporting 87.0 confidence is broken, and its division
        # is worth nothing either. Declining keeps the parse safe AND
        # observable by absence -- an unconditional clamp mapped 87.0
        # to 1.0, i.e. "certain", silencing the SEGMENTATION report at
        # exactly the point of maximum brokenness. NaN takes the same
        # exit for free: every comparison against it is False, so it
        # fails both bounds below and declines.
        #
        # _SCORE_EPSILON is sized for FLOAT32, not float64: numpy
        # softmax output is commonly float32, whose eps is ~1.2e-7, and
        # namedivider's rule-based answers score exactly 1.0 -- so a
        # float64-sized 1e-9 band would decline a correct rule-based
        # division that came back a single ulp high (1.0000001 is
        # exactly that). A few float32 ulps is still five orders of
        # magnitude below any score a broken divider would produce, so
        # nothing is bought by tightening it.
        score = float(result.score)
        if not -_SCORE_EPSILON <= score <= 1.0 + _SCORE_EPSILON:
            return None
        confidence = min(1.0, max(0.0, score))
        # Defensive, the reconstruction check's twin: no namedivider
        # 0.4.x path can return an empty side (every answer, rule or
        # statistical, is built by slicing the input at an interior
        # offset). If one ever did, it would mean "I read this as
        # undivided" -- an empty Segmentation, which is a stated
        # opinion, and not the None that declines to have one.
        if not result.family or not result.given:
            return Segmentation((), confidence=confidence)
        return Segmentation((len(result.family),), confidence=confidence)

    return segment
