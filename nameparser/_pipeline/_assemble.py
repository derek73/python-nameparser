"""Not a stage: converts the final ParseState into a public ParsedName.

Consumes: tokens (all roles set), dropped, ambiguities (by index).
Produces: a validated ParsedName -- the constructor re-checks every
invariant (span order/bounds, ambiguity subset), so a pipeline bug
that would produce an invalid result dies HERE, not in a renderer
three layers away.

Structural tokens (dropped maiden markers) are omitted, like delimiter
characters. A main-stream token that somehow reaches here with no role
takes Role.GIVEN -- parse is total over str (spec §5a) and must not
raise on content; the fallback is deliberately boring.
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
    ambiguities = tuple(
        Ambiguity(p.kind, p.detail,
                  tuple(final[i] for i in p.indices if i in final))
        for p in state.ambiguities)
    return ParsedName(original=state.original,
                      tokens=tuple(final.values()),
                      ambiguities=ambiguities)
