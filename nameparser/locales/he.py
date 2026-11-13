"""The Hebrew locale pack: a choice of languages, ``he``, and nothing
else -- no lexicon fragment and no policy patch
(mechanisms.md#LOCALE-PACKS-PURE-DATA; #1257). Choosing it turns on
nameparser/vocab/he.toml's readings written ``default = false``: the
clan particle ``ben`` of Israeli family names in Latin script, so
``Yael Ben David`` gives family ``Ben David`` where the default gives
middle ``Ben``, family ``David``. The default leaves ``ben`` to
position because the given name Ben, a British middle name too, stands
where the particle claim acts; a ``Ben`` opening a name stays the given
name under the pack and reports the fork (``Ben Affleck``). The Hebrew
spelling, ``בן``, is read by default.

The pack is for family names written with ``Ben``, not for a civil
register's chain of fathers' names: ``Karim ben Ali ben Salah Haddad``
gives family ``ben Salah Haddad``, as under ``locales.AR`` (#1248).

Data sources: the readings' own entries in nameparser/vocab/he.toml,
each with its issue and the vetting on its note; nothing is listed
here.

Deviations: derived, not declared. The words a choice of ``he``
can move are ``_reading_index.changed_words``, which the
non-interference gate in tests/v2/test_locales.py reads
(decisions/deviates-registry), so this module carries no DEVIATES.
"""
from __future__ import annotations

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale

HE = Locale(code="he", lexicon=Lexicon.empty(),
            languages=frozenset({"he"}))
