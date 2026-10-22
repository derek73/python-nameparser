# O4 — positional assignment and declared order

## Standing

- Romanized Chinese order is declared, not detected, pinyin carrying no signal and diaspora making locale no guide: a caller whose data is family-first passes `Policy(name_order=FAMILY_FIRST)` — 2026-08-07 #83.
- There are three order constants because Vietnamese needs the third: `Nguyễn Thị Minh Khai` reads given 'Khai', middle 'Thị Minh', family 'Nguyễn' under FAMILY_FIRST_GIVEN_LAST, where FAMILY_FIRST strands given 'Thị' — 2026-08-07 #146.
- Free-form order tuples are declined for the exported constants (#270's draft shape, the log's Declined line): a tuple of strings raises `name_order elements must be Role members` (rules/D2) and a two-role tuple `name_order must be one of the exported orders` — 2026-08-07 #146.
- `middle_as_family` is declined as the way to drop Vietnamese middles, giving family 'Thị Minh Nguyễn' for `Nguyễn Thị Minh Khai` under FAMILY_FIRST_GIVEN_LAST; `given_names` is the view that stays correct — 2026-08-07 #146.

Open: none in this file.

## Log

- 2026-08-07 #83 — romanized Chinese order is answered by DECLARATION, not detection: pinyin carries no signal and diaspora makes locale no guide (the issue's own 2019/2021 conclusions); Policy(name_order=FAMILY_FIRST) is the answer the thread wanted.
- 2026-08-07 #146 — Vietnamese needs the THIRD order constant: measured on "Nguyễn Thị Minh Khai", FAMILY_FIRST strands given="Thị" while FAMILY_FIRST_GIVEN_LAST reads given="Khai", middle="Thị Minh", family="Nguyễn". This is why three order constants exist rather than two.

- Provenance: the three-constants argument originates in #270's own body (2026-07-07): "A boolean family_name_first flag was considered and rejected: Vietnamese order is
  [family][middle][given]." The 2026-08-07 #146 measurement below
  is the verification; #270 is the origin.

Declined:

- Free-form order tuples (('last','middle','first')-style, #270's original draft shape) — the shipped design is exported order constants with tuple rejection at construction (rule D2's
  [bad-name-order] example is the pinned message).
- middle_as_family as the way to suppress the middle slot for Vietnamese (2026-08-07 #146) — measured: it merges the middles into the family, giving family="Thị Minh Nguyễn" for "Nguyễn Thị Minh Khai" under family-first-given-last — a plausible-looking wrong answer. There is no policy field that suppresses middle, and name_order rejects a two-role tuple ("name_order must be one of the exported orders"); given_names (given + middle) is the view that stays correct wherever the internal boundary falls.

