"""The Slovenian locale pack: a choice of languages, ``sl``, and a policy
patch, no lexicon fragment (3.0, phase 3f, #753; the patch since #1190;
mechanisms.md#LOCALE-PACKS-PURE-DATA). Choosing it turns on
nameparser/vocab/sl.toml's readings written ``default = false``: the
generations ``ml.`` (mlajši) and ``st.`` (starejši); on a word sl.toml
holds a vocabulary reading of, other languages' vocabulary readings
leave (`st`'s Saint title and particle, so ``St Clair`` is a given name
under this pack; a caller whose names also hold the English Saint
chooses ``fr`` too, a choice that changes no other
word (decisions/vocabulary-model's 2026-10-30 phase 3f entry; ``père``,
the one other word it named, is read by default since 2026-11-03).

It reads two family names (``Policy.two_family_names``, rules/O6), its
policy patch compiled from sl.toml's [rules] table by
tools/vocab/build.py, so the married double surname written without a
hyphen stays whole: ``Elena Zavadlav Ušaj`` gives family ``Zavadlav Ušaj``,
where the default gives the first of them as a middle name. Two given
names pay for it, with no given-name list to keep them out of the
family, as under CS and SK: ``Janez Jože Novak`` gives family ``Jože Novak``
(decisions/O6's 2026-11-21 #1190 entry, which records the cost).

Data sources: the readings' own entries in nameparser/vocab/sl.toml,
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

SL = Locale(
    code="sl",
    lexicon=Lexicon.empty(),
    # nameparser/vocab/sl.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("sl"),
    languages=frozenset({"sl"}),
)


# rules/O6's declaration, which every pack turning O6 on shares
DEVIATES = deviates_by_two_family_names
