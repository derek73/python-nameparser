# R7 — no initials in a script that writes none

## Standing

- A word whose first letter is in Han, Hangul or kana, and since 2026-11-12 the Myanmar and Thai scripts (the rows of `_policy._SCRIPT_PROPERTIES` that write no initials, which the parse's initial veto reads, #320, decisions/script-properties) contributes nothing to `initials()`, the test asked of the letter's composed spelling — 2026-10-28 #754 (Derek).
- A word opening with conjoining jamo that compose to no syllable gives no initial, the jamo being hangul: `ᄒᆞᆫ 김` gives '' — 2026-11-05 #1087
- A word opening with a letter of the Myanmar script gives no initial: `ကြည် ကြည် ဌေး` gives '' — 2026-11-12 #1234 (decisions/script-properties).
- A word opening with a Thai letter gives no initial: `สมชาย ใจดี` gives '' — 2026-11-12 #1256 (decisions/script-properties).

Open: none in this file.

## Log

- 2026-10-28 #754 (Derek) — DECIDED, as part of item 6 of decisions/vocabulary-model's #754 output-model entry (the render defaults): `initials()` gives nothing for a word in a script with no initials, where it gave the first character with a period (`'王.'`). Implemented 2026-10-29 (sub-phase 4e) as a rule of its own rather than a clause of rules/R3, since it reads the word's script, a signal R3 does not read. Measured over the committed corpus's distinct entries, each under its declared order, against `9210f221` (the recipe is decisions/R6's 2026-10-29 entry): every `initials()` move is a Han, Hangul or kana initial dropped, and no other initial moves.
- 2026-11-05 #1087 — A JAMO THAT COMPOSES TO NOTHING WRITES NO INITIAL. The script table's HANGUL took in the conjoining jamo (decisions/nfd-shapes, same date), so a word opening with archaic or lone jamo is hangul to this view: `ᄒᆞᆫ 김` moved from 'ᄒ.' to '', `Mary ᄀ. Smith` from 'M. ᄀ. S.' to 'M. S.' and `John Smith, ꥠᅡ` from 'ꥠ. J. S.' to 'J. S.' (measured 2026-11-05 against 4109b026). A decomposed modern syllable gave none before, the letter being composed first. The compatibility jamo still initial (`ㄱㄴ 김` gives 'ㄱ.').
- 2026-11-12 #1234 — BURMESE WRITES NO INITIALS. The script-property table's Myanmar row (decisions/script-properties, which holds the evidence and the moves) adds Burmese to the rule: `ကြည် ကြည် ဌေး` gave 'က. က. ဌ.' from 1.4.0 through 3.0.1 and gives ''. The rule's Because no longer says the parse reads no period after such a word as an abbreviation: that is H2's own column, which the Myanmar row does not set.
- 2026-11-12 #1256 — THAI WRITES NO INITIALS. The script-property table's Thai row (decisions/script-properties, which holds the count and the moves) adds Thai to the rule, as the 2026-08-02 #320 measurement (`th` 0 of 20) had said it belonged once it earned a row: `สมชาย ใจดี` gave 'ส. ใ.' and gives ''.
