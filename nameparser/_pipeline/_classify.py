"""Stage: classify.

Consumes: tokens.
Produces: tokens with vocabulary tags added (text/span/role unchanged).
Reads: every Lexicon vocabulary field; Policy is not consulted.

Tags emitted -- stable (API): "particle", "conjunction", "initial";
namespaced (unstable): "vocab:title", "vocab:given-title",
"vocab:suffix", "vocab:suffix-word", "vocab:suffix-ambiguous",
"vocab:particle-ambiguous", "vocab:bound-given", "vocab:maiden-marker".
"vocab:suffix" means "counts as a suffix as written": unambiguous
suffix vocabulary, or an ambiguous acronym written with periods
('M.A.' yes, 'Ma' no -- 'Ma' gets only "vocab:suffix-ambiguous").
The initial veto is assign's job, not classify's: 'V' carries both
"vocab:suffix" and "initial".
"""
from __future__ import annotations

import dataclasses

from nameparser._lexicon import _normalize
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, WorkToken,
)
from nameparser._types import AmbiguityKind, Role
from nameparser._pipeline._vocab import (
    is_initial, period_joined_vocab, suffix_as_written,
)




def _tags_for(token: WorkToken, state: ParseState) -> frozenset[str]:
    lex = state.lexicon
    n = _normalize(token.text)
    tags = set(token.tags)
    if n in lex.titles:
        tags.add("vocab:title")
    if n in lex.given_name_titles:
        tags.add("vocab:given-title")
    if suffix_as_written(n, token.text, lex):
        tags.add("vocab:suffix")
    if n in lex.suffix_words:
        tags.add("vocab:suffix-word")
    if n in lex.suffix_acronyms_ambiguous:
        tags.add("vocab:suffix-ambiguous")
    if n in lex.particles:
        tags.add("particle")
    if n in lex.particles_ambiguous:
        tags.add("vocab:particle-ambiguous")
    if n in lex.conjunctions and not is_initial(token.text):
        # v1's is_conjunction excludes initials: 'e.' in 'john e. smith'
        # is a middle initial, not the Spanish conjunction 'e'
        tags.add("conjunction")
    if n in lex.bound_given_names:
        tags.add("vocab:bound-given")
    if n in lex.maiden_markers:
        tags.add("vocab:maiden-marker")
    if is_initial(token.text):
        tags.add("initial")
    # v1's period-joined derivation (parse_pieces): a token with a
    # period not at the end, ANY of whose period chunks is a title, is
    # a title as a whole ('Lt.Gov.', and by the ANY rule 'Mr.Smith');
    # else ANY suffix chunk makes it a suffix ('JD.CPA'). Title wins
    # (v1's continue). Skipped when the whole token already matched.
    if "vocab:title" not in tags and "vocab:suffix" not in tags:
        derived = period_joined_vocab(token.text, lex)
        if derived == "title":
            tags.add("vocab:title")
        elif derived == "suffix":
            tags.add("vocab:suffix")
    return frozenset(tags)


def classify(state: ParseState) -> ParseState:
    tokens = tuple(
        dataclasses.replace(t, tags=_tags_for(t, state))
        for t in state.tokens)
    # Delimited content whose vocabulary cannot settle it: extract's
    # escape sends an UNambiguous suffix straight through ("(MBA)" ->
    # suffix) and keeps everything else as a nickname, so an AMBIGUOUS
    # acronym in there was a coin the parser had to call. Reported here
    # rather than at the escape itself, which runs before tokenize and
    # so has no token index to point at.
    ambiguities = list(state.ambiguities)
    for i, token in enumerate(tokens):
        if (token.role is Role.NICKNAME
                and "vocab:suffix-ambiguous" in token.tags):
            ambiguities.append(PendingAmbiguity(
                AmbiguityKind.SUFFIX_OR_NICKNAME,
                f"delimited {token.text!r} is also a post-nominal; read "
                f"as a nickname rather than a suffix",
                (i,)))
    return dataclasses.replace(state, tokens=tokens,
                               ambiguities=tuple(ambiguities))
