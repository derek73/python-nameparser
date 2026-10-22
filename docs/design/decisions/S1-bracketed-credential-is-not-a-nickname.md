# S1 — a bracketed credential is not a nickname

## Standing

- The rule says what the escape does: quotes escape as brackets do, and a clause of two or more words is not suffix-shaped unless an ASCII period ends it, so `(PhD MBA)` keeps its nickname reading with nothing reported, as 1.4.0 read it — 2026-10-21 #807.

Elsewhere: an ambiguous member alone in the brackets staying a nickname, reported, is decided under decisions/suffix-acronym-collisions (its Standing line ending 2026-09-25 #540; 2026-10-21) and decisions/ma-do's 2026-07-17 entry.

## Log

- 2026-10-21 (Derek), #807 — S1 IS NARROWED TO WHAT THE ESCAPE DOES, NOT WIDENED TO WHAT ITS THEN HAD SAID. The rule's Then said suffix-shaped bracketed content reads as if written bare, and #807's review measured two places the parser had never done so: a clause of two or more words is never suffix-shaped unless it ends in a period (`John Smith (PhD MBA)` → nickname 'PhD MBA', nothing reported; `(MBA PhD.)` → suffix), the escape asking its question of the whole clause; and every default nickname pair escapes alike, quotes included (`John Smith "MBA"` → suffix, `"MA"` → nickname, reported). Derek: narrow the rule for both rather than change the parser. 1.4.0 reads `(PhD MBA)` as nickname 'PhD MBA' and the ASCII-quoted `"MBA"` and `'MBA'` as suffix 'MBA' (measured 2026-10-21, the wheel run from a scratch dir), so neither is a 2.x move; the typographic and CJK pairs (`«MBA»`, `“MBA”`, `「MBA」`, `（MBA）`) were no delimiters in 1.4.0, which read each as a family name, and escape alike since 2.x added them. The third gap the review found, `John Smith (M.A)` → nickname where bare `John Smith M.A` → suffix (1.4.0: suffix in both), was left to an issue rather than narrowed. Limits the review measured and the rule now states or leaves: the period is tested on the raw clause, so `(PhD MBA. )` stays a nickname, and an ideographic full stop does not count (`(PhD MBA。)`), as decisions/cjk-full-stops records for one word; under a caller-declared maiden pair the same clauses read as maiden names, the report being a nickname's alone.
