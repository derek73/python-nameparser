"""Not a stage: converts the final ParseState into a public ParsedName.

Consumes: tokens (all roles set), dropped, ambiguities (by index).
Produces: a validated ParsedName -- the constructor re-checks every
invariant (span order/bounds, ambiguity subset), so a pipeline bug
that would produce an invalid result dies HERE, not in a renderer
three layers away.

Structural tokens (dropped maiden markers) are omitted, like delimiter
characters. A main-stream token that somehow reaches here with no role
takes Role.GIVEN -- parse must never raise on the *content* of a name,
so the fallback is deliberately boring rather than an exception. This
should never fire in practice (assign/group must set a role on every
main-stream token); it exists as a last-resort safety net against a
pipeline bug, not as sanctioned behavior for real input -- see
test_assemble_falls_back_to_given_for_unassigned_role in
tests/v2/pipeline/test_assemble.py.
"""
from __future__ import annotations

from nameparser._pipeline._state import ParseState
from nameparser._types import Ambiguity, ParsedName, Role, Token


def assemble(state: ParseState) -> ParsedName:
    dropped = set(state.dropped)
    final: dict[int, Token] = {}
    for i, t in enumerate(state.tokens):
        if i in dropped:
            continue
        role = t.role if t.role is not None else Role.GIVEN
        final[i] = Token(t.text, t.span, role, t.tags)
    # No alphanumeric character among the SURVIVING tokens means no
    # name: a bare '.' or '- -' is not a person. v1 kept such input
    # (parse('.') -> first '.'); 2.0 empties it so bool() stays an
    # honest "did I get a name?" check. isalnum() is Unicode-aware, so
    # every real name in any script has content and only pure
    # punctuation/symbols empty out. (Embedded junk in a name with
    # content -- 'John . Smith' -- is left alone: that parse is truthy,
    # so bool() is not misled.)
    #
    # This read "anywhere" until #329, and the two said the same thing
    # for as long as nothing could take a content-bearing token away.
    # Dropping a maiden marker inside a delimited clause can, and
    # "(née —)" under Policy(maiden_delimiters=...) is the input where
    # the readings part: the marker is the clause's only alnum token,
    # so once it goes structural the em dash is all that survives and
    # the whole parse empties -- where 1.4.0 and pre-#329 both gave
    # maiden 'née —'. Deliberate, not fallout: a dropped marker is
    # structural like a delimiter character, and brackets plus a marker
    # plus a dash name no one, exactly as "(-)" already named no one.
    # A guard keyed on what ELSE is in the clause would be a different
    # rule, and would leave maiden holding marker-plus-punctuation.
    # Pinned by cases.py's maiden_marker_delimited_content_free.
    #
    # The TOKENS go, not the diagnostics: this drops the name, and
    # "was the input malformed?" is the one question still worth
    # answering about it -- most of all here, where there is no parse
    # left to infer it from. parse('(') keeps its unbalanced-delimiter
    # report, pointing at no token because no token survived.
    contentless = not any(
        c.isalnum() for t in final.values() for c in t.text)
    if contentless:
        final = {}
    ambiguities = []
    for pending in state.ambiguities:
        materialized = tuple(final[i] for i in pending.indices
                             if i in final)
        if pending.indices and not materialized and not contentless:
            # every referent was dropped: the ambiguity describes
            # nothing that survives assembly. Born-empty ambiguities
            # (unbalanced delimiters) are token-independent and kept.
            # Not so when the whole name was emptied just above -- the
            # referents did not lose a contest, they were discarded
            # wholesale, and the report still describes the input.
            continue
        ambiguities.append(
            Ambiguity(pending.kind, pending.detail, materialized))
    return ParsedName(original=state.original,
                      tokens=tuple(final.values()),
                      ambiguities=tuple(ambiguities))
