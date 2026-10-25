# C9 — a one-character suffix word inside a comma part

**When:** a one-character suffix word — the only kind a reader could take for an initial — stands inside a comma part, as in "Smith, John V".

**Then:** it is read by what stands before it: behind another suffix it is describing that suffix and continues the run, written with a period or without, an initial being no shape anyone writes there, and behind a name word it is the generation only when written bare, a period marking it the abbreviation of a name and so a middle initial (T5).

- **Both branches then ask that the generation slot still be open**: where a further comma has already named the suffix (C2), a single letter ending the GIVEN part has no generation left to be, and stays a middle initial — with a period or without, and whether a name word or another suffix word stands before it. So a lone letter ending the given part ahead of a further comma is the middle initial, whatever stands before it, a credential run in front of it stopping short of it, where the letter is written as an initial (T5).
  ```
  "Smith, John V, Jr."        →  middle="V"
  "Smith, John PhD I, Jr."    →  middle="I"
  "Smith, John PhD I., Jr."   →  middle="I."
  "Smith, John PhD I, Jr."    →  suffix="PhD, Jr."
  "Smith, John PhD É, Jr."    →  suffix="PhD É, Jr."  · boundary
  ```
- **Only the given part is touched**: a part after the comma that is nothing but suffix words is the credential run, and a letter in it continues that run up to the further comma.
- **Longer suffix words are not in question either way**, a numeral of two or more letters being read as S10 reads one in this part.

**Because:** one letter is the shape a middle initial is written in, so only what stands before it says whether it is a generation.

```
"Smith, PSM I"              →  suffix="PSM I"
"Smith, PSM I."             →  suffix="PSM I."
"Smith, John V."            →  middle="V."
"Smith, John PhD I."        →  suffix="PhD I."
"Smith, John V"             →  suffix="V"  · boundary
```

**Precedence:**

- **Under the strict comma-suffix switch** ("Smith, RA I"): C14 governs a part after the comma that is nothing but suffix words; the given part's walk does not consult the switch.

**Accepted:**

- A letter that is a level of the credential in front of it, written ahead of a further comma, is read as the middle initial, the further comma having named the suffix: the certification level is split from its credential. No corpus holds the shape (#819, measured 2026-10-25).
  ```
  "Smith, John PSM I, Jr."    →  middle="I"
  ```

---
**Signal:** neighbor: what stands before a one-character suffix word inside a comma part
**history:** decisions/C9 · **implemented:** nameparser/_pipeline/_assign.py
