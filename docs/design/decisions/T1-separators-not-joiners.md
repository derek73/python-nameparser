# T1 — separators, not joiners

## Standing

- An ignorable character is a separator, never removed with its neighbors joined as v1's squash_emoji and squash_bidi did: `A😀B` reads given 'A', family 'B' — 2026-07 PR #288.
- The `strip_bidi=False` half of the opt-out carries no example, by decision; with it `John‏Smith` (a right-to-left mark between the words) reads given 'John‏Smith', the mark kept — 2026-10-20 #761.

Open: none in this file.

## Log

- 2026-07 (v2 core, PR #288) — v1's squash_emoji/squash_bidi REMOVED the character and joined its neighbors. (v1.3.0 had no bidi handling at all: squash_bidi entered late v1 via #266, 2026-07-07, on the emoji precedent's shape.) ('A😀B' → 'AB'); v2 makes an ignorable character a separator ('A😀B' → 'A', 'B'). The unavoidable consequence of every part being an exact positioned piece of the input: with no rewriting stage, nothing can splice two half-words together.
- 2026-10-20 (Derek), #761 — the `strip_bidi=False` half of the opt-out carries no example, by decision: the example would be a name holding an invisible direction mark (`John‏Smith`, which reads given `John‏Smith` with the marks kept), and that is not worth a new policy annotation in `tests/v2/rules_doc.py`'s registry.
