"""The Czech locale pack: a choice of languages, ``cs``, a policy
patch and a lexicon fragment (3.0, phase 3f, #753; the fragment since
#970; mechanisms.md#LOCALE-PACKS-PURE-DATA). Choosing it turns on
nameparser/vocab/cs.toml's readings written ``default = false``: the
generations ``ml.`` (mladší) and ``st.`` (starší), the salutation
``pan``, the birth marker ``roz.``, the academic titles written before
the name that the default leaves off (``MgA.``, ``BcA.``, ``Bc.``,
``Ing.``, the rank ``mjr.``; ``Mgr.`` read
as the degree, the doctorates being read by default since #1115, and
the post-nominal ``DrSc.`` since #969); on a word cs.toml holds a
vocabulary reading of, other languages' vocabulary readings leave
(`st`'s Saint title and particle, so ``St Clair`` is a given name under
this pack; a caller whose names also hold the English Saint chooses
``fr`` too, a choice that changes no other
word (decisions/vocabulary-model's 2026-10-30 phase 3f entry; ``père``,
the one other word it named, is read by default since 2026-11-03).

It reads two family names (``Policy.two_family_names``, rules/O6), its
policy patch compiled from cs.toml's [rules] table by
tools/vocab/build.py, so the married double surname written without a
hyphen stays whole: ``Alena Pešová Řehořová`` gives family ``Pešová
Řehořová``, where the default gives the first of them as a middle name.
Two given names pay for it, with no given-name list to keep them out of
the family: ``Petr Pavel Novák`` gives family ``Pavel Novák``
(decisions/vocabulary-model's 2026-10-30 phase 3f amended entry, which
records the cost and the list that could lift it).

Its fragment removes ``ing``'s given-name reading, so ``Ing Jan Novák``
gives title ``Ing``, and ``Ing. et Ing. Jan Novák`` the title ``Ing. et
Ing.``, where the default gives the given name ``Ing`` and ``Ing. et
Ing.``: a choice never
drops a name reading (decision 15 of decisions/vocabulary-model), and
this one is mul.toml's, which a strict choice keeps too, so neither a
reading cs.toml could write nor ``strict=True`` makes Ing a title
outside a title phrase (rules/H9). The family reading stays, keeping
the credential mul.toml lists gated, so ``Mr Tom Ing`` keeps family
``Ing``. The cost is Ing the given name opening a name or alone after
a family comma, Chinese, Malaysian or Swedish (``Ing Wei Lim`` and
``Lim, Ing`` give title ``Ing``), Ing the surname at the head of a
family comma (``Ing Ho, Mei`` gives family ``Ho``), and a
post-nominal glued to Ing.'s stop (``Ing.Paed.IGIP``) read as a title
(decisions/vocabulary-model, the 2026-11-21 #970 entry).

Data sources: the readings' own entries in nameparser/vocab/cs.toml,
each with its issue and the vetting on its note; nothing is listed
here.

Declared deviations (mechanisms.md#LOCALE-PACKS-PURE-DATA): the choice's
are derived, not declared -- the words whose compiled readings it
changes (``_reading_index.changed_words``), which the non-interference
gate in tests/v2/test_locales.py ors in -- so DEVIATES below declares
only what the patch and the fragment change.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale, deviates_by_two_family_names, rules_patch

CS = Locale(
    code="cs",
    # the given reading that gates cs.toml's Ing (#970): a choice never
    # drops a name reading, and this is mul.toml's, which strict keeps
    lexicon=Lexicon.empty().remove("ing", kind="given"),
    # nameparser/vocab/cs.toml's [rules], compiled by tools/vocab/build.py
    policy=rules_patch("cs"),
    languages=frozenset({"cs"}),
)


def DEVIATES(name: str) -> bool:
    """True when this pack may parse `name` differently from the
    default parser (the declared-deviation predicate the
    non-interference gate consumes): rules/O6's declaration, which
    every pack turning O6 on shares, or a name holding the word the
    fragment changes, ``Ing``, in any case and glued to a stop
    (``Ing.Paed.IGIP``), but not a word that merely holds its letters
    (``King``). The derived surface holds ``ing`` too while cs.toml
    lists it; this keeps the fragment declared if that reading goes."""
    letters = "".join(c if c.isalpha() else " " for c in name.casefold())
    return deviates_by_two_family_names(name) or "ing" in letters.split()
