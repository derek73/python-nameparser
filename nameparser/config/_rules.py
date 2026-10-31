"""The compiled [rules] tables. GENERATED from nameparser/vocab/*.toml by
tools/vocab/build.py -- do not edit; edit the TOML and run

    uv run python tools/vocab/build.py

One line per vocabulary file holding a [rules] table: its BCP 47 tag
and its keys as sorted (Policy field, value) pairs, a set-valued field's
value a sorted tuple. nameparser._locale.rules_patch turns a file's
pairs into the PolicyPatch its shipped pack carries (#754, 4f).
"""


RULES: tuple[tuple[str, tuple[tuple[str, object], ...]], ...] = (
    ('es', (('two_family_names', True),)),
    ('ru', (('patronymic_rules', ('east-slavic',)),)),
    ('tr', (('patronymic_rules', ('turkic',)),)),
)
