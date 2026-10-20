# P7 — a one-letter particle against the initial it spells

**When:** a one-letter word the particle vocabulary holds stands in a name, as in "Juan Ó. Pérez".

**Then:** a one-letter word written with its period is an initial and not a particle, whatever particle the same letter spells, the period being the shape T5 reads as an initial; written bare, it is the particle.

- **It is an initial in every position**, so it neither opens a surname (P1), nor joins a chain (P2), nor attaches to the family behind a comma (P6).
  ```
  "J. Ó. Pérez"               →  middle="Ó."
  "Ó. Pérez"                  →  given="Ó."
  "Pérez, Juan Ó."            →  middle="Ó."
  ```

**Because:** a one-letter particle is spelled with the same letter as an initial, and the period is what tells them apart. An initial is an abbreviation and is written with one; a particle is a whole word and is not. The Irish Ó is never written with a period, while Ó. is the initial of Óscar, Ólafur or Ólöf.

```
"Juan Ó. Pérez"             →  middle="Ó."
"Juan Ó Pérez"              →  family="Ó Pérez"  · boundary
```

**Accepted:**

- An accented initial written WITHOUT its period reads as the particle. Such initials normally carry the period, and the bare letter is exactly how the particle is written.
  ```
  "Juan Ó Pérez"              →  middle=""
  ```

---
**Signal:** shape: a one-letter word the particle vocabulary holds, read by whether T5 makes it an initial
**history:** decisions/P7 · **implemented:** nameparser/_lexicon.py, nameparser/_pipeline/_classify.py
