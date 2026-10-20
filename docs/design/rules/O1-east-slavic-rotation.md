# O1 — East Slavic rotation

**When:** East Slavic patronymic handling is active, the default given-first order stands, and the last name word of a name with no comma carries a patronymic ending, as in "Сидоров Иван Петрович".

**Then:** a name of exactly three name words — titles, suffixes and nicknames aside — whose last name word carries a patronymic ending and whose middle name word does not reads as family-first: the words are restored to given, patronymic, family.

- **A middle word that also carries the ending blocks the reading**, because the surname itself may be patronymic-derived.
  ```
  "Иван Петрович Абрамович"  [ru]  →  family="Абрамович"  · boundary
  ```
- **The restoration is the default order's work**: it recovers the given-first reading a family-first listing hides, so where the caller has DECLARED a family-first order there is nothing left to restore and position decides.

**Because:** an East Slavic name written family-first still shows its patronymic — the distinctive ending identifies which word is the patronymic, and the patronymic sits next to the given name.

```
"Сидоров Иван Петрович"  [ru]  →  family="Сидоров"
"Sidorov Ivan Petrovich Jr."  [ru]  →  family="Sidorov"
```

**Accepted:**

- Under a declared family-first order the readings part on natural-order input, and the declaration wins. A family-first listing reads the same either way under FAMILY_FIRST — the first example in the fence is that same parse with FAMILY_FIRST declared, and under FAMILY_FIRST_GIVEN_LAST the listing's given and middle swap, so only the family is invariant — while with East Slavic handling active and FAMILY_FIRST declared the natural-order Иван Петрович Сидоров reads family Иван, given Петрович, middle Сидоров. That is the caller's declaration being honored on input they said was written family-first, not a defect (#384). No registered example annotation combines a pack with an order, so the parse is pinned in tests/v2/test_locales.py instead, and decisions/O1 records why options 2 and 3 were declined.

---
**Signal:** shape: a patronymic ending on the last of exactly three name words, and not on the middle one
**history:** decisions/O1 · **implemented:** nameparser/_pipeline/_post_rules.py
