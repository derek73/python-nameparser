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
from nameparser._pipeline._state import ParseState, WorkToken
from nameparser._pipeline._vocab import is_initial, suffix_as_written


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
    if n in lex.conjunctions:
        tags.add("conjunction")
    if n in lex.bound_given_names:
        tags.add("vocab:bound-given")
    if n in lex.maiden_markers:
        tags.add("vocab:maiden-marker")
    if is_initial(token.text):
        tags.add("initial")
    return frozenset(tags)


def classify(state: ParseState) -> ParseState:
    tokens = tuple(
        dataclasses.replace(t, tags=_tags_for(t, state))
        for t in state.tokens)
    return dataclasses.replace(state, tokens=tokens)
