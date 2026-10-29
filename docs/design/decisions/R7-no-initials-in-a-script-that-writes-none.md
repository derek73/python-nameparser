# R7 — no initials in a script that writes none

## Standing

- A word whose first letter is in Han, Hangul or kana (`_policy._NO_INITIALS`, the scripts the parse's initial veto reads, #320) contributes nothing to `initials()`, the test asked of the letter's composed spelling — 2026-10-28 #754 (Derek).

Open: none in this file.

## Log

- 2026-10-28 #754 (Derek) — DECIDED, as part of item 6 of decisions/vocabulary-model's #754 output-model entry (the render defaults): `initials()` gives nothing for a word in a script with no initials, where it gave the first character with a period (`'王.'`). Implemented 2026-10-29 (sub-phase 4e) as a rule of its own rather than a clause of rules/R3, since it reads the word's script, a signal R3 does not read. Measured over the committed corpus's distinct entries, each under its declared order, against `9210f221` (the recipe is decisions/R6's 2026-10-29 entry): every `initials()` move is a Han, Hangul or kana initial dropped, and no other initial moves.
