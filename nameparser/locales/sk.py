"""The Slovak locale pack: a choice of languages, ``sk``, and a policy
patch, no lexicon fragment (3.0, phase 3f, #753;
mechanisms.md#LOCALE-PACKS-PURE-DATA). Choosing it turns on
nameparser/vocab/sk.toml's readings written ``default = false``: the
generations ``ml.`` and ``st.``, the academic titles written before the
name (``MUDr.``, ``JUDr.``, ``PhDr.``, ``RNDr.``, ``Mgr.`` and the rest)
and the post-nominals ``ArtD.`` and ``DrSc.``; on a word sk.toml holds a
vocabulary reading of, other languages' vocabulary readings leave
(`st`'s Saint title and particle, so ``St Clair`` is a given name under
this pack; a caller whose names also hold the English Saint chooses
``fr`` too, whose only other word the choice changes is ``père``, as
decisions/vocabulary-model's 2026-10-30 phase 3f entry records).

It reads two family names (``Policy.two_family_names``, rules/O6), its
policy patch compiled from sk.toml's [rules] table by
tools/vocab/build.py, so the married double surname written without a
hyphen stays whole: ``Mária Nováková Kováčová`` gives family ``Nováková
Kováčová``, where the default gives the first of them as a middle name.
Two given names pay for it, with no given-name list to keep them out of
the family: ``Ján Peter Mrkva`` gives family ``Peter Mrkva``
(decisions/vocabulary-model's 2026-10-30 phase 3f amended entry, which
records the cost and the list that could lift it).

Data sources: the readings' own entries in nameparser/vocab/sk.toml,
each with its issue and the vetting on its note; nothing is listed
here.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the choice's
are derived, not declared -- the words whose compiled readings it
changes (``_reading_index.changed_words``), which the non-interference
gate in tests/v2/test_locales.py ors in -- so DEVIATES below declares
only what the patch changes.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, deviates_by_two_family_names, rules_patch

SK = Locale(
    code="sk",
    lexicon=Lexicon.empty(),
    # nameparser/vocab/sk.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("sk"),
    languages=frozenset({"sk"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack's patch may parse `name` differently from the
    default parser: rules/O6's declaration, shared with the es pack
    (_locale.deviates_by_two_family_names)."""
    return deviates_by_two_family_names(name)
