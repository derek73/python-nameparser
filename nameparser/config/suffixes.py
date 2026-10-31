# The words, and the vetting notes that stood beside them here, live in
# nameparser/vocab/*.toml, classified by kind (generation, credential,
# honorific, ...) and by language. A suffix reading is an acronym or a
# word (`acronym`, true by default for a credential), so the two sets
# below are disjoint by construction; a name reading beside a suffix
# reading, `attached` on a word reading and the agnomen kind make the
# marker subsets.
# tools/vocab/build.py compiles them into _compiled.py and runs the
# checks that were import-time asserts here (decisions/vocabulary-model).
from nameparser.config import _compiled

SUFFIX_WORDS = _compiled.SUFFIX_WORDS
"""

Post-nominal suffixes matched as WORDS: the lookup uses the normalized token,
so only EDGE periods come off and interior ones survive -- "Junior." matches
here, "J.u.n.o.r." does not and stays name text ("John J.u.n.o.r." parses a
family name, on both APIs). The example is deliberately not "J.u.n.i.o.r.",
which fails this lookup too: an interior-period token that no whole-token
set claims goes to ``period_joined_vocab``, which splits it on its periods
and, no chunk being a title, calls the whole thing a suffix if ANY chunk is
suffix vocabulary -- except where every chunk it matches is a SINGLE ASCII
CHARACTER, which since 2.4 retires rather than claims (decisions/S3): the
one-character suffix vocabulary is the Roman numerals and the digit "2" --
ASCII is load-bearing there, since the seven single-character CJK
honorifics in THIS set (様, 殿, 氏, 군, 님, 씨, 양 -- three of them also
glued-honorific heads below) must KEEP their chunk claim ("J.씨" still
derives from 씨) -- and a word
built of single ASCII letters is not about generations. So "J.u.n.i.o.r."
no longer reaches this set's "i" entry as a generational claim; it is
read by POSITION instead, as an unlisted multi-chunk word
(``Policy.unlisted_dotted_suffixes``, default on), and with words to
spare it is still a suffix (rules/S3). A multi-character chunk match
is untouched -- "Msc.Ed." still derives from ``ed`` and reads as a
suffix outright, and "Lt.Gov." still derives a TITLE from its own
multi-character chunk match.
So membership here is not the last word on a dotted token; the sentence is
about this set's lookup alone. :data:`SUFFIX_ACRONYMS` is the set matched
with every period removed, so it alone covers a multi-dot spelling: both
"P.H.D." and the bare "PhD" reach its `phd` entry, the two normalizing to
the same string once the periods come off. The vocabulary build keeps
the two DISJOINT (tools/vocab/build.py): a post-nominal belongs to
one of them or the other, and which one holds it is what decides whether
its multi-dot spelling reaches a whole-token lookup at all --
``period_joined_vocab`` may still claim the token chunk by chunk, as
"Msc.Ed." and "Lt.Gov." above show -- or read it by position instead,
as "J.u.n.i.o.r." now does.

"""
GLUED_HONORIFICS = _compiled.GLUED_HONORIFICS
"""

The subset of :data:`SUFFIX_WORDS` a name token may end WITH, peeled off as
its own token before segmentation (#308). Deliberately harsher than the
spaced set, because a glued tail has no writer-drawn token boundary to lean
on -- these entries are recognized in the SPACED position only:

* 양, 군 -- 김지양 and 김지군 are given names ending in these syllables, and
  양 is a top-tier surname besides.
* 氏 -- 王氏 is a historical name form ("the Wang woman").
* 博士 -- glued 田中博士 IS Tanaka Hiroshi, an attested given name.
* 殿 -- some ninety Japanese surnames END in it, 鵜殿 (Udono) and 真殿
  (Madono) with four-figure populations, so peeling it would cut a real
  family name in two. Spaced 殿 is safe for the reason 양/군 are: a
  殿-surnamed person's name LEADS, and the suffix gate is trailing-only.
* The Indic trailing set (जी, साहब, साहिब, साहेब, महाराज, সাহেব, বাবু,
  মহারাজ) and Latin rinpoche are spaced-only for the same reason 殿 is:
  जी ends Banerjee/Mukherjee/Chatterjee (बनर्जी, मुखर्जी, चटर्जी) and a
  glued peel would strand बनर् on a bare virama. The criterion is not
  CJK-specific, which is the point (decisions/indic-honorifics).

Three more are in NEITHER set, so neither spelling is recognized. 君: 王君 is
a complete Chinese name (君 is a common given-name final), so the honorific
reading never gets the benefit of the doubt -- while its kana spelling くん
ships glued, above. Bare 선생 and 교수: they read as common nouns as readily
as address terms, and only their -님 forms ship.

"""
SUFFIX_WORDS_AMBIGUOUS = _compiled.SUFFIX_WORDS_AMBIGUOUS
"""

The subset of :data:`SUFFIX_WORDS` also borne as a name: a generation
word with a ``given`` or ``family`` reading, such as French ``fils`` and
the Brazilian agnomens (``filho``, ``neto``), or a credential written as a
word, King's Counsel's ``kc``, also the Nepali surname. Each is read as a suffix
only where the name keeps a word for its family (rules/S11): ``Alexandre
Dumas fils`` ends in a suffix and ``Marie Fils`` keeps her family name.

"""
AGNOMENS = _compiled.AGNOMENS
"""

The subset of :data:`SUFFIX_WORDS_AMBIGUOUS` whose writing says nothing
about the reading: an agnomen is written in the case of the name around
it, so only the words to spare decide (rules/S11).

"""
SUFFIX_ACRONYMS_AMBIGUOUS = _compiled.SUFFIX_ACRONYMS_AMBIGUOUS
"""

Acronym suffixes from SUFFIX_ACRONYMS that also plausibly collide with a
word borne as a name -- a given name, nickname or surname. Not a
partition of SUFFIX_ACRONYMS -- a small, standalone exception list, read
wherever the pipeline decides an acronym's bare reading (rules/S4).

"""
SUFFIX_ACRONYMS = _compiled.SUFFIX_ACRONYMS
"""

Post-nominal acronyms. Titles, degrees and other things people stick after their name
that may or may not have periods between the letters. The parser removes periods
when matching against these pieces.

"""


# In SOURCE order, not alphabetical: `automodule :members:` follows
# __all__ where a module defines one, so an alphabetical list here would
# silently reorder this module's entries in modules.html.
__all__ = [
    "SUFFIX_WORDS",
    "GLUED_HONORIFICS",
    "SUFFIX_WORDS_AMBIGUOUS",
    "AGNOMENS",
    "SUFFIX_ACRONYMS_AMBIGUOUS",
    "SUFFIX_ACRONYMS",
]
