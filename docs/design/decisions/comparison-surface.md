# comparison-surface — why value equality died, and what replaced it

## Standing

- Case-insensitive equality, equality with plain strings and hashability cannot all hold, so the mutable `HumanName` carried no value equality, and went in 3.0 without it; comparison is `matches()` and `comparison_key()`, one casefolded component per field, the maiden name included — 2026-07 #223; 2026-10-28 #357.

Not standing: the cross-constants asymmetry of `HumanName.matches()`, gone with it — 2026-10-28 #357.

Open: none in this file.

## Log

- 2026-07 (1.3.0 arc, #223/#224; executed in the v2 core — measured: HumanName == HumanName is False, matches() and comparison_key() live, the facade cites #223) — the trilemma: case-insensitive equality, equality-with-plain-strings, and hashability are mutually inconsistent (a hash cannot equal both hash("John Smith") and hash("john smith")), so 1.2.0's design was unfixable in place, not merely disliked. Additional costs of the old surface: equality ran through str(self) and so depended on mutable string_format, and maiden was invisible to == (absent from the default format).
- 2026-07-06 — the cross-constants asymmetry, pinned: a str operand is reparsed with self.C; a HumanName operand is compared as already parsed.
- 2026-10-28 #357 — `HumanName` IS REMOVED, and with it the surface the 2026-07 entry took value equality off and the cross-constants asymmetry of the 2026-07-06 entry (decisions/3-0-reevaluations' 2026-10-28 #357, REMOVAL entry). Comparison stays `matches()` and `comparison_key()`. Measured 2026-10-28: the immutable `ParsedName` compares as a frozen dataclass does, exactly and case-sensitively, `parse('John Smith') == parse('John Smith')` True and `parse('John Smith') == 'John Smith'` False, with equal hashes, so no part of the trilemma is reopened; a str operand to `ParsedName.matches()` is parsed under the default configuration and to `Parser.matches()` under that parser's.

Declined:

- Component-based __eq__/__hash__ — workable, considered, rejected: it still privileged one equality semantic for a domain that has none, and kept the mutate-while-hashed hazard.
- Lenient matching (initials-compatible, Bob/Robert) — declined WITHOUT an issue, deliberately: matches() is exact-components by design. Someone will propose could_match() within a year; this entry is the resolved-as-no they should find.

