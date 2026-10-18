# T1 — separators, not joiners

- 2026-07 (v2 core, PR #288) — v1's squash_emoji/squash_bidi REMOVED the character and joined its neighbors. (v1.3.0 had no bidi handling at all: squash_bidi entered late v1 via #266, 2026-07-07, on the emoji precedent's shape.) ('A😀B' → 'AB'); v2 makes an ignorable character a separator ('A😀B' → 'A', 'B'). The unavoidable consequence of every part being an exact positioned piece of the input: with no rewriting stage, nothing can splice two half-words together.

