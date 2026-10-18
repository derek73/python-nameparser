# N2 — same-character quotes and shared-character conventions

- 2026-07-18 #273 (7ee6e3a) — the typographic delimiter pairs shipped with a per-pair full-text scan; three independent review agents broke it the same day: with two shared-character conventions genuinely present, the earlier-sorted pair stole the close and the legitimate match dropped silently, zero ambiguity.
- 2026-07-18 (05fe693, the same day) — the interleaved leftmost-match restructure replaced it (an altitude review called it the right depth); the author's own first fix — post-hoc offset filtering of unbalanced candidates alone — was superseded within the day and survives only as the bulk-recorded dangler filter rules.md#N2 now names. The word-internal carve-out covers ONLY the straight apostrophe because it is the one delimiter character that occurs mid- and end-of-word in real names; Derek's distinguishing test: with double quotes the same shape ("Mari\" Aube\"") is genuinely ambiguous, while Mari' Aube' is not. A cached delimiter-charset prescreen landed in the same commit, measured: no-delimiter names parse faster than the pre-#273 baseline.

Declined:

- The offset-filter as the whole fix — it repaired the reported symptom (spurious unbalanced flags) while leaving the stolen- close mis-extraction in place.

