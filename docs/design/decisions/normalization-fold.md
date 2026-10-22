# normalization-fold — lower(), not casefold(); comparison folds harder

## Standing

- Vocabulary storage folds with `lower()`, not `casefold()`, keeping authored spellings at the pinned cost that `GROSSFÜRST Hans Müller` reads given 'GROSSFÜRST' where `Großfürst Hans Müller` reads title 'Großfürst'; comparison (`comparison_key()`, `matches()`) folds with `casefold()`, so `Hans Strauß` matches `Hans Strauss` — 2026-07-17/19.
- The fold reaches a fixed point, and anything built on it converges: `_title_key` drops the words that fold away rather than keeping an empty slot — 2026-07.

Elsewhere: the fold also composes a non-ASCII word to NFC and strips the CJK full stops since 2.3.0, NFKC declined, decisions/cjk-full-stops' 2026-09-10 #322/#323 line.

Open: none in this file.

## Log

- 2026-07-17/19 — vocabulary storage normalizes with lower(), NOT casefold(): casefold mutated stored spellings (κος→κοσ, großfürst→grossfürst) while lower() keeps authored forms; the accepted cost, pinned deliberately, is that ASCII-SS GROSSFÜRST no longer matches. The paired half: comparison_key()/matches() use casefold() ON PURPOSE — comparison is the one surface that wants aggressive folding; this is a release-log-classified 2.0 CHANGE from 1.4's lower() (ß and final-sigma forms compare equal only since the v2 core; v1.4 has no casefold anywhere). The 1.x line was symmetric BY DESIGN — lower() everywhere, chosen for symmetry with the parser's lc() convention — so the storage-vs-comparison split is a v2 decision moving away from a real, deliberate alternative, not a fix of an oversight. Do not
  "fix" it symmetric: symmetric is what 1.x was.
- 2026-07 (rc1 arc) — the fold must reach a FIXED POINT, and anything built on it must converge too: _title_key joined per-word folds and kept empty slots, so given_name_titles with a foldable word stored a key match-time could never rebuild — silently inert, and pickle round-trips then rejected the state. Shipped in the rc, caught in review, fixed by dropping words that fold away.

