# family-without-an-inherited-name — what `family` and the patronymic view hold where a convention has no family name

## Standing

- `family` is the name a convention files a person under, not necessarily an inherited one: where a convention has no inherited name, the word in the surname slot of that convention's own records is the family (the Mongolian father's name, a Kyrgyz `Father uulu`, the last word of an Ethiopian or a Burmese name); no default reading changes and no field is added — 2026-11-12 #1253.
- The patronymic view keeps rules/R9's basis, filled only by a word or a rule that says patronymic, never by a position; it may overlap the family or be a part of it, and a father's name nothing in the text marks (Ethiopia) fills no view — 2026-11-12 #1253.
- An Ethiopian or Eritrean name stays positional, its family the grandfather's name where it is written and the father's where it is not; a caller matching such a list builds the matcher from a parser with `middle_as_family`, keeping the default parser for the fields (docs/matching.rst) — 2026-11-12 #1253.

Open: #1188 (Kazakh), #1155 (`بن` chain), #1231 (Burma), each a value question under the two statements; #1165 (`S/O`, `W/O`), a decision of its own.

## Log

- 2026-11-12 #1253 — `family` IS THE NAME A CONVENTION FILES A PERSON UNDER, AND THE PATRONYMIC VIEW IS FILLED ONLY BY A WORD OR A RULE THAT SAYS PATRONYMIC. Decided on the issue (its last comment), which settles the shape of #1203, #1237, #1187, #1188, #1155, #1210, #1231 and #1165: each becomes a pack, a rule value or a vocabulary entry under two statements, and no default reading changes and no field is added.
  1. `family` is the name a convention files a person under, not necessarily an inherited one. Where a convention has no inherited name, the word in the surname slot of that convention's own records is the family: the Mongolian father's name (the passport's surname field), a Kyrgyz `Father uulu`, the last word of an Ethiopian or a Burmese name. The decision adds that this is what the parse does by position today, and what a caller sorting or matching reads the field for. Measured on master 2b39f23d, 2026-11-12, position gives it for the Ethiopian name (below); the Mongolian and Kyrgyz names need the order and the marker reading each leaf adds (`Ухнаагийн Хүрэлсүх` reads family 'Хүрэлсүх' by default, `Бекмырза Чолпонбай уулу` family 'уулу'); and a Burmese name opening with `San` loses it to the particle fold, rules/P1 (`Aung San Suu Kyi` → given 'Aung', family 'San Suu Kyi'), a case for #1231's pack. The name-order section's Background (rules/O-name-order.md) states it.
  2. The patronymic view keeps rules/R9's basis: it is filled only by a word or a rule that says patronymic, never by a position. It may overlap `family` or be a part of it. A father's name nothing in the text marks fills no view. rules/R9's Because states it.
  - **Per sub-issue**, as the decision lays them out:
    - #1203 Ethiopia: stays positional, and the father's name fills no view. Accepted: the same person written with two words and with three has a different `family` (rules/O4's Accepted clause).
    - #1237 Mongolia: a Mongolian pack with a family-first order, the father's name the `family`; a rule reading the genitive may fill the view (the pack lands with #1237).
    - #1187 Kyrgyz: with no surname, the father's name and its marker are the `family` and the patronymic view alike (the reading lands with #1187, in rules/O2).
    - #1188 Kazakh: an ending rule fills the view, as the East Slavic one does; which choice turns it on is a value question.
    - #1155 a family name after a `بن` chain: the view may be a part of the family, stopping before a family name a closed signal marks; which signal is a value question.
    - #1210 Hebrew `בן`: decided with #1257.
    - #1231 Burma: a pack, the last word the `family` by position, the honorifics titles.
    - #1165 `S/O`, `W/O`: out of this decision; the words after the marker are another person's name, which the model has no place for. Malaysian `a/l` and `a/p`, where the father's name is part of the legal name, read as `bin` does and are a vocabulary question.
  - **Measured for #1203** (dated snapshots):
    - House of Peoples' Representatives (OpenSanctions `et_hopr`, as `opensanctions-parliaments` fetched it on 2026-11-12, the dataset's version of that day): 2,191 distinct names, 211 of two words, 1,940 of three, 35 of four and 5 longer; the default reads 1,938 of the 1,940 three-word names as own name, father (`middle`) and grandfather (`family`), the two others being `Abu Tuke Birki` (given 'Abu Tuke', `abu` joining the word after it as a bound given name, rules/P5) and `MOHAMMED ABU HESEN` (family 'ABU HESEN'); no name fills the patronymic view. The list has no fields, so the reading expected is the convention's. #1203 counted 2,291 names, 2,039 of three words, on the 2026-11-08 fetch. Recompute: the `et_hopr` rows of `local/opensanctions-parliaments/raw.jsonl` whose `form` is `name`, distinct, each parsed with `parse()` and compared word by word with its own words.
    - ORCID's Ethiopian and Eritrean records, scored against the boxes their holders filed (`config_diff.py score default 'default@middle_as_family=1' --group ET --group ER`, run in a master 2b39f23d checkout on 2026-11-12): ET 91.95% by default against 70.43% under `middle_as_family` (18,794 records), ER 92.24% against 72.41% (232). #1203 measured 91.99% and 70.46% for ET on 2026-11-08; ER is unchanged.
    - #1203's other figures were not re-taken: ORCID's 11,913 Ethiopian records filing one given and one family word, the three-word filings splitting 5,477 with the father's name in the given box against 1,384 with it beside the grandfather's in the family box, and Wikidata's family name (P734) filled for 56 of 445 Ethiopians (2026-11-08, the issue).
  - **Matching across the two spellings** needs nothing new. `Parser.matching().check` on master 2b39f23d, 2026-11-12:

    | Pair | default parser | `Parser(policy=Policy(middle_as_family=True))` |
    |---|---|---|
    | `Abiy Ahmed Ali` / `Abiy Ahmed` | family `conflict`, no shared key | family `part-of-other`, consistent, shared key `ahmed;a` |
    | `Abiy Ahmed Ali` / `Abiy Ali` | consistent (`same`), though the second's father is the first's grandfather | consistent (`part-of-other`) |
    | `Abiy Ahmed` / `Abiy Ali` | conflict | conflict |
    | `Abiy Ahmed Ali` / `Abiy Bekele` | conflict | conflict |
    | `Abiy Ahmed Ali` / `Abiy Ahmed Bekele` | conflict | conflict, though the two share the key `ahmed;a` (a key groups, the check decides) |

    So a caller matching a list written under this convention builds the matcher from a parser that folds the middle names into the family and keeps the default parser for the fields, since rules/O3's switch costs about 21.5 points of field agreement on ORCID's Ethiopian records. `across-roles` and `other_readings` do not reach the pair. The fold is right only for a list known to follow the convention: under it `John Paul Smith` and `John Paul` are consistent too, and it compares the family's words regardless of order, so a father and grandfather written the other way round are consistent (`Abiy Ahmed Ali` / `Abiy Ali Ahmed`, which the default matcher keeps apart). docs/matching.rst carries the recipe, with invented names.
