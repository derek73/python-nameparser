# D2 — construction raises, parse never does

D2. Rationale: whatever a name contains, parsing answers; only a
    broken configuration may raise, and it must name the field.
    Configuration validation raises at construction with the
    offending field and value named; applying a locale pack wraps
    any such error with the locale's code, so a stacked
    configuration names which layer broke.
      [bad-name-order]  →  raises="name_order elements must be Role members"
      [bad-order-none]  →  raises="name_order must be an iterable"
    no-boundary: the non-raising side is every other rule's
    examples; parse() itself is total (A1).
    history: decisions/D2 · implemented: nameparser/_policy.py, nameparser/_parser.py
