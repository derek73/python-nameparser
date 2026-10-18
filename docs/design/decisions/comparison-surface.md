# comparison-surface — why value equality died, and what replaced it

- 2026-07 (1.3.0 arc, #223/#224; executed in the v2 core — measured: HumanName == HumanName is False, matches() and comparison_key() live, the facade cites #223) — the trilemma: case-insensitive equality, equality-with-plain-strings, and hashability are mutually inconsistent (a hash cannot equal both hash("John Smith") and hash("john smith")), so 1.2.0's design was unfixable in place, not merely disliked. Additional costs of the old surface: equality ran through str(self) and so depended on mutable string_format, and maiden was invisible to == (absent from the default format).
- 2026-07-06 — the cross-constants asymmetry, pinned: a str operand is reparsed with self.C; a HumanName operand is compared as already parsed.

Declined:

- Component-based __eq__/__hash__ — workable, considered, rejected: it still privileged one equality semantic for a domain that has none, and kept the mutate-while-hashed hazard.
- Lenient matching (initials-compatible, Bob/Robert) — declined WITHOUT an issue, deliberately: matches() is exact-components by design. Someone will propose could_match() within a year; this entry is the resolved-as-no they should find.

