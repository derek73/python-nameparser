# O2 — Turkic rotation

## Standing

- Under Turkic handling a name of exactly four name words ending in a standalone marker reads family-first, at v1 parity: `Ali Ahmad Vali oglu` under `locales.TR_AZ` → family 'Ali', given 'Ahmad', middle 'Vali oglu'; any other count keeps the positional reading, the marker standing in a name field (`Ali Ahmad oglu` → family 'oglu') — 2026-07-02 PR #288.
- The marker patterns are NFC literals with `qızı` a literal alternative, dotless ı not case-folding to i, so all-caps `QIZI` falls to the ASCII alternative and decomposed input does not match (`Ali Ahmad Vali oğlu` typed decomposed → family 'oğlu'); suffix-attached Kazakh and Uzbek patronymics (`Әбішұлы`) are out of scope — 2026-07-02.
- The rotation stands down under a declared family-first order by O1's gate on the order assign read: `oglu Ahmad Vali Ali` under FAMILY_FIRST reads family 'oglu' as plain FAMILY_FIRST does, and `Ali Ahmad Vali oglu` under FAMILY_FIRST_GIVEN_LAST reads given 'oglu', middle 'Ahmad Vali' — 2026-09-07 #384.
- Re-deriving the order from the marker under a declared family-first order, and reporting where the marker and the declared order disagree, are declined for decisions/O1's reasons — 2026-09-07 #384.

Not standing: 2026-08-15, the same open interaction question as decisions/O1's, answered by 2026-09-07 #384.

Open: none in this file.

## Log

- 2026-07-02 (Turkic design; landed in the v2 core, PR #288) — shape fixed at exactly four name words (1 given + 2 middle + 1 marker), v1 parity; other shapes keep their positional reading even when that leaves the marker in a name field (see the rule's Accepted consequence).

- 2026-07-02 (design, orthography coverage) — dotless ı does not case-fold to i, so qızı is a literal alternative in the pattern (re.I cannot bridge it; all-caps QIZI falls to the ASCII alternative); the patterns are NFC literals and NFD input does not match. Scoping decline: suffix-attached Kazakh/Uzbek patronymics (Әбішұлы) are bound-suffix morphology, not a standalone marker, and deliberately out.
- 2026-08-15 — same rotation/name_order interaction status as O1.
- 2026-09-07 #384 — OPTION 1, the same answer as decisions/O1's entry of the same date and on the same principle: the rotation restores the default reading from a family-first listing, so a declared family-first order supplies that reading instead and the rotation stands down. It stands down by the same gate on the read order, for the reason O1's entry records — the marker test reads the word in the FAMILY position, which under a family-first order is the FIRST word, so a name opening with the marker reached it. Measured 2026-09-07 before the gate, `oglu Ahmad Vali Ali` with Turkic handling and FAMILY_FIRST read family `Ahmad`; after it, family `oglu`, which is what plain FAMILY_FIRST reads and this rule's own 2026-07-02 Accepted consequence — the marker in a name field. The natural-order twin `Ali Ahmad Vali oglu` is decisions/O1's entry of the same date, which measures it under both family-first orders and pins it in tests/v2/test_locales.py. Options 2 and 3 are Declined for O1's reasons.

