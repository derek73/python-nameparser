# D2 — construction raises, parse never does

**When:** a configuration is built from a value it cannot accept.

**Then:** configuration validation raises at construction with the offending field and value named.

- **A locale pack names itself:** applying a locale pack wraps any such error with the locale's code, so a stacked configuration names which layer broke.

**Because:** whatever a name contains, parsing answers. Only a broken configuration may raise, and it must name the field.

```
[bad-name-order]  →  raises="name_order elements must be Role members"
[bad-order-none]  →  raises="name_order must be an iterable"
```

---
no-boundary: the non-raising side is every other rule's examples; parse() itself is total (A1).
**Signal:** none in the name: the configuration's values, at construction
**history:** decisions/D2 · **implemented:** nameparser/_policy.py, nameparser/_parser.py
