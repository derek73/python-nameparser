"""Internal pipeline state: WorkToken and ParseState.

WorkTokens are pipeline-internal (no validation -- the tokenizer is the
only producer) and are addressed BY INDEX in every stage: pieces and
segments are runs of token indices, never joined strings, so value-based
lookup (v1's #100 family) is structurally impossible.

Layering: imports _types, _lexicon, _policy only (enforced by
tests/v2/test_layering.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from nameparser._lexicon import Lexicon
from nameparser._policy import Policy
from nameparser._types import AmbiguityKind, Role, Segmenter, Span


# The comma characters (ASCII/Arabic/fullwidth, #265). Shared here so
# tokenize (separators/segmentation) and extract (close-quote
# boundaries) cannot drift apart.
COMMA_CHARS = frozenset({",", "\u060c", "\uff0c"})

@dataclass(frozen=True, slots=True)
class WorkToken:
    """One tokenized word. role stays None until assign; extracted
    nickname/maiden tokens arrive with their role pre-set. text is
    always the exact original slice (tokenize is the sole producer;
    the anti-#100 invariant depends on it)."""

    text: str
    span: Span
    tags: frozenset[str] = frozenset()
    role: Role | None = None


class Structure(Enum):
    """segment's comma-structure decision."""

    NO_COMMA = auto()
    FAMILY_COMMA = auto()   # "Family, Given ..." (v1 lastname-comma)
    SUFFIX_COMMA = auto()   # "Given Family, Suffix ..."


@dataclass(frozen=True, slots=True)
# rules.md#A1: "parsing never fails on any input: where the text's
# structure or a word's reading is genuinely uncertain, the parse
# completes on the best reading and carries an ambiguity report
# naming the doubt"
class PendingAmbiguity:
    """An ambiguity recorded mid-pipeline by token INDEX; assemble
    materializes real Ambiguity objects over the final tokens.

    ``origin`` is for the one stage that runs BEFORE tokens exist:
    extract_delimited knows only a character offset, so it records that
    and tokenize resolves it to the containing token's index. Stages
    after tokenize set ``indices`` directly and leave ``origin`` None.
    """

    kind: AmbiguityKind
    detail: str
    indices: tuple[int, ...] = ()
    origin: int | None = None


@dataclass(frozen=True, slots=True)
class ParseState:
    """Carried through the stage fold. Frozen; stages return copies via
    dataclasses.replace. Fields are filled progressively:
    extract_delimited -> extracted/masked; tokenize -> tokens (span-
    sorted)/comma_offsets/interpunct_offsets (the 间隔号 offsets the
    order and segmentation decisions consult, #298; the nakaguro
    separators record NOTHING); segment -> segments/structure;
    script_segment -> tokens and segments again (the one stage that
    changes the token COUNT: an unspaced CJK token splits into n+1
    pieces, still as sub-slices of the original, and every later index
    in the segment runs shifts by n); classify -> token tags; group ->
    pieces/piece_tags/dropped AND maiden token roles;
    assign -> the remaining token roles AND `order`, the effective
    order it read them under; post_rules -> roles again.
    Ambiguities are recorded by every stage that DECIDES one --
    extract (resolved to a token index by tokenize), segment,
    script_segment, classify,
    group, and assign -- since a fork whose branches are taken in
    different stages needs an emitter in each. Post-group, segments
    may retain indices of dropped tokens -- assign iterates pieces,
    never segments. This ownership map is pinned by
    tests/v2/pipeline/test_state.py.

    segmenter belongs to no stage: like original/lexicon/policy it is
    passed in at construction by Parser.parse and only ever READ (by
    script_segment, for a token the vocabulary declined)."""

    original: str
    lexicon: Lexicon
    policy: Policy
    #: The optional Parser(segmenter=...) hook; None = not configured.
    segmenter: Segmenter | None = None
    extracted: tuple[tuple[Role, Span], ...] = ()
    masked: tuple[Span, ...] = ()
    tokens: tuple[WorkToken, ...] = ()
    comma_offsets: tuple[int, ...] = ()
    interpunct_offsets: tuple[int, ...] = ()
    segments: tuple[tuple[int, ...], ...] = ()
    structure: Structure = Structure.NO_COMMA
    # pieces[s][p] = run of token indices: piece p of segment s.
    # piece_tags[s][p] = derived flags for that piece ("title", "prefix",
    # "suffix", "conjunction") set by group's joins.
    pieces: tuple[tuple[tuple[int, ...], ...], ...] = ()
    piece_tags: tuple[tuple[frozenset[str], ...], ...] = ()
    dropped: tuple[int, ...] = ()   # structural tokens (maiden markers)
    #: The order `assign` actually READ the name under -- name_order,
    #: or the script_orders entry that overrode it. None wherever no
    #: positional read happened: after a family comma (which fixes the
    #: family, so assign consults no order at all), and on every early
    #: return in `_assign_main`, where a segment holds no name piece
    #: to position. Recorded rather than recomputed downstream,
    #: because the two can differ and a post_rules rule keyed on
    #: `policy.name_order` would then disagree with the roles assign
    #: already wrote (#395). Reaching that divergence needs a custom
    #: lexicon -- every shipped particle is Latin, and Latin has no
    #: script_orders entry -- which is why the test for it builds its
    #: own (test_post_rules.py).
    order: tuple[Role, Role, Role] | None = None
    ambiguities: tuple[PendingAmbiguity, ...] = ()
