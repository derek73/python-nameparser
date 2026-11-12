# O4 — positional assignment and declared order

## Standing

- Romanized Chinese order is declared, not detected, pinyin carrying no signal and diaspora making locale no guide: a caller whose data is family-first passes `Policy(name_order=FAMILY_FIRST)` — 2026-08-07 #83.
- There are three order constants because Vietnamese needs the third: `Nguyễn Thị Minh Khai` reads given 'Khai', middle 'Thị Minh', family 'Nguyễn' under FAMILY_FIRST_GIVEN_LAST, where FAMILY_FIRST strands given 'Thị' — 2026-08-07 #146.
- Free-form order tuples are declined (#270's draft shape; the decline is the log's undated Declined line, which no dated entry records): a tuple of strings raises `name_order elements must be Role members` (rules/D2) and a two-role tuple `name_order must be one of the exported orders` — 2026-08-07 #146.
- `middle_as_family` is declined as the way to drop Vietnamese middles, giving family 'Thị Minh Nguyễn' for `Nguyễn Thị Minh Khai` under FAMILY_FIRST_GIVEN_LAST; `given_names` is the view that stays correct — 2026-08-07 #146.
- One name word followed by nothing but initials reports `order`, the reserved kind, under the default given-first order with no family comma and `initials_as_family` off; capitals written as one word with no full stops (`Armitage JO`) do not count as initials there — 2026-11-11 #1254.

Open: none in this file.

## Log

- **2026-11-11 #1254 — ONE NAME WORD FOLLOWED BY NOTHING BUT INITIALS REPORTS THE ORDER, IN THE RESERVED `ORDER` KIND.** The default given-first order reads `Armitage J. O.` as given `Armitage`, a bibliography writes it surname first, and a South Asian list writes `Lakshmi R S` with the letters as the family (rules/O8); #1137 measured surname first as the 2 to 1 majority of ORCID's credit names of one word and initials, and the 3.1 cycle's session notes hold the per-shape counts (decisions/O8's entry). The default stays, so the fork is reported: assign, which lays the name out by position, emits it where it does so, naming the word in front as the family as the reading not taken.
  - The kind: `order`, reserved since 2.0 for "the name's field order itself is uncertain", which this is; a new kind was the other choice, and the reserved one adds none to the public enum.
  - Its reach: one name word, then letters in rules/T5's shape (spaced, or joined by full stops), ending the name words; under the given-first order, read by declaration or by default alike, since nothing tells the two apart; not after a family comma, not under `initials_as_family`, not when the word in front is itself a run of initials (rules/T7) or in a script that writes none. Capitals written as one word with no full stops (`Armitage JO`) do not count, whatever their length, being written as a short surname is (`Zhi LI`, `Jason NG`): among ORCID's credit names of one word and two to four such capitals, the boxes put the word first in 611 and the capitals in the family box in 183 (step 0's count, session notes). Measured on the 3.1 cycle's study populations (session notes): leaving them out leaves 592 of the 2,311 ORCID credit names confirmed as bylines unreported; counting them would also report 92 of the 592 names of Turkey's parliament (`Erkan BAŞ`) and 276 of a 60,000-name ClinicalTrials.gov sample (`Antoine BEDU`), surnames in capitals.
  - What it reached, measured against a checkout of the branch before it: 61 names of the committed corpora gain the report and no reading moves, among them every one-letter numeral read as the family (`John V`, `Malcolm X`, rules/S10), now reporting both forks it stands in, and the regnal names GND writes with a dotted numeral (`Heinrich I.`), which rules/T5 reads as an initial already. In the local corpora, with `snapshot.py --local <source> --base <that checkout>` (2026-11-11), only the reports moved: orcid-researchers 4,939 names, nepal-candidates 1,580, tse-donors 1,402, patentsview-inventors 437, ctgov-officials 392, jrc-names 133, psc-individuals 13; fec-individuals (its names written with a comma), cz-candidates, dof-signatures, govuk-people, tw-donors, uit-vinames, ukec-individuals and vn-assembly none.

- 2026-08-07 #83 — romanized Chinese order is answered by DECLARATION, not detection: pinyin carries no signal and diaspora makes locale no guide (the issue's own 2019/2021 conclusions); Policy(name_order=FAMILY_FIRST) is the answer the thread wanted.
- 2026-08-07 #146 — Vietnamese needs the THIRD order constant: measured on "Nguyễn Thị Minh Khai", FAMILY_FIRST strands given="Thị" while FAMILY_FIRST_GIVEN_LAST reads given="Khai", middle="Thị Minh", family="Nguyễn". This is why three order constants exist rather than two.

- Provenance: the three-constants argument originates in #270's own body (2026-07-07): "A boolean family_name_first flag was considered and rejected: Vietnamese order is
  [family][middle][given]." The 2026-08-07 #146 measurement below
  is the verification; #270 is the origin.

Declined:

- Free-form order tuples (('last','middle','first')-style, #270's original draft shape) — the shipped design is exported order constants with tuple rejection at construction (rule D2's
  [bad-name-order] example is the pinned message).
- middle_as_family as the way to suppress the middle slot for Vietnamese (2026-08-07 #146) — measured: it merges the middles into the family, giving family="Thị Minh Nguyễn" for "Nguyễn Thị Minh Khai" under family-first-given-last — a plausible-looking wrong answer. There is no policy field that suppresses middle, and name_order rejects a two-role tuple ("name_order must be one of the exported orders"); given_names (given + middle) is the view that stays correct wherever the internal boundary falls.

