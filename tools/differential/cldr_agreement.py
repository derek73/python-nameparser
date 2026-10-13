"""Where nameparser and CLDR disagree about a name's fields -- a ratchet.

CLDR's person-name test data (see build_cldr_corpus.py) states every
name's fields separately. This module parses each CLDR rendering with the
working tree and compares, role by role, with what CLDR says; the
DISAGREEMENTS are recorded in cldr_agreement.json, and
tests/v2/test_cldr_agreement.py fails when the tree's disagreements stop
matching the record:

- a role that agreed now disagrees (a regression);
- a recorded disagreement now agrees (progress, which must be recorded so
  that it is guarded from then on);
- a recorded disagreement's answer changed (a different wrong answer, or
  progress in disguise -- and a record that never goes stale).

    uv run python tools/differential/cldr_agreement.py           # summary
    uv run python tools/differential/cldr_agreement.py --record  # re-record

Re-record deliberately, and say why in the commit, as with a watched diff.
The record doubles as a measured worklist: every entry is a place the
parser and CLDR read a name differently.

Nothing is special-cased. A deliberately unnatural rendering, `さん` read
as a suffix where CLDR calls it a title, a lone word under a family-first
order: each simply disagrees, and the ratchet guards what agrees.
"""
from __future__ import annotations

from collections import Counter

from nameparser import ParsedName

ROLES = ("title", "given_names", "family", "suffix",
         "family_particles", "family_base")


def _has_space(text: str) -> bool:
    return any(ch.isspace() for ch in text)


def _words(text: str) -> list[str]:
    return text.replace(",", " ").split()


def _squash(text: str) -> str:
    return "".join(text.replace(",", "").split())


def occurs(value: str, text: str) -> bool:
    """Whether a CLDR field's value appears in a rendering: word by word
    where the rendering has spaces (so `Wolf` is not found in `Wolfgang`),
    by substring where it has none (unspaced scripts)."""
    if _has_space(text):
        need = Counter(_words(value))
        return bool(need) and not need - Counter(_words(text))
    return bool(_squash(value)) and _squash(value) in _squash(text)


def expected_roles(fields: dict[str, str], text: str) -> dict[str, str]:
    """What CLDR says each role holds IN THIS RENDERING. CLDR's formats
    drop fields by locale and order, so a role is built only from the
    fields whose value occurs in the text; a role with none expects ''.
    The particle and base views are compared only where CLDR states the
    split, i.e. the name has a surname-core."""
    def present(*names: str) -> str:
        return " ".join(fields[n] for n in names
                        if n in fields and occurs(fields[n], text))

    family = (("surname", "surname2") if "surname" in fields
              else ("surname-prefix", "surname-core", "surname2"))
    roles = {"title": present("title"),
             "given_names": present("given", "given2"),
             "family": present(*family),
             "suffix": present("generation", "credentials")}
    if "surname-core" in fields:
        roles["family_particles"] = present("surname-prefix")
        roles["family_base"] = present("surname-core", "surname2")
    return roles


def same(expected: str, got: str, text: str) -> bool:
    """Agreement, decided by the rendering as occurs() is: the same
    multiset of words where it has spaces (order within a role is free),
    the same text with spaces and commas removed where it has none."""
    if _has_space(text):
        return Counter(_words(expected)) == Counter(_words(got))
    return _squash(expected) == _squash(got)


def got_roles(name: ParsedName) -> dict[str, str]:
    return {"title": name.title, "given_names": name.given_names,
            "family": name.family, "suffix": name.suffix,
            "family_particles": name.family_particles,
            "family_base": name.family_base}
