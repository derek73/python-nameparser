# P1 — lone particle fold

**When:** a never-given particle opens the name and has another name word behind it to attach to, as in "de Mesnil".

**Then:** the name is surname-only: the particle run and the name words it attaches to are the family, under every name order.

- **The run is every particle in sequence**, never-given and ambiguous alike: "de la Vega" is one group, not "de" plus a separate "la Vega". An ambiguous particle keeps whatever reading its position gives it.
  ```
  "de la Vega"                →  family="de la Vega"
  "de los Santos"             →  family="de los Santos"
  ```
- **A title does not move the opening position** (P4).
  ```
  "Sir de Mesnil"             →  family="de Mesnil"
  ```
- **Under the default order the run takes the rest of the name.** That is a reading rather than a gap in one: a never-given particle marks where a surname BEGINS, surnames are routinely several words, and no declaration has said this one ends before the string does. So `de Mesnil Jean` reports the whole string as the family, which is 1.4.0's reach as well, by design (decisions/P1, #471).
  ```
  "de Mesnil Jean"            →  family="de Mesnil Jean"
  ```
- **Under a family-first order the run takes exactly ONE name word**: declaring that order asserts that what follows the family is not more surname. One name word means one UNIT — a particle chain (P2), a conjunction join (P3) or a bound given-name pair (P5) is taken whole or not at all. What is left over is not read by O4's rule for a whole name, which would make the first leftover a second family name; it is laid out as the positions AFTER the family in the declared order, the family slot being already filled.
  ```
  "de Mesnil Jean"  family-first  →  family="de Mesnil"
  "de Mesnil Jean"  family-first  →  given="Jean"
  "de la Vega y Santos Juan"  family-first  →  family="de la Vega y Santos"
  "ibn Awf abdul Rahman"  family-first  →  given="abdul Rahman"
  "de la Cruz Juan Carlos"  family-first-given-last  →  given="Carlos"
  ```
- **After a family comma the run takes the rest of that part, whatever order is declared**: the comma has already fixed the surname, so there is no positional read left for an order to narrow.
  ```
  "Smith, de Mesnil Jean"  family-first  →  family="Smith de Mesnil Jean"
  ```

**Because:** a particle OPENING a name has the whole rest of the name to link forward to, so it is doing a particle's work and the piece it heads is a surname written out in full. That is evidence about the writing, not about the word, which is why no declared order contradicts it.

```
"Mc Donald"                 →  family="Mc Donald"
"van Gogh"                  →  given="van"  · boundary
```

**Precedence:**

- **Against a declared order** ("de Mesnil" under a family-first order): the particle claims the FAMILY rather than a given name under every order, because this is evidence about how the name is written, and a declared order governs only what no vocabulary has claimed (O4) — the same precedence the script license takes in W4.

**Accepted:**

- The default-order reach has two faces, and the second is a real cost. A surname-only string is read right, which is what the reach is for; a family-first listing read under the default order is read wrong, all of it landing in the family. The remedy is the declaration or the comma — declare a family-first order, which gives family `de la Cruz`, given `Juan`, middle `Carlos`, or write the family comma. What NEITHER order settles is the comma's alone: `de la Family Family Given` and `de la Family Given Given` are the same string shape, and no reading of the words tells them apart.
  ```
  "de la Torre Vega"          →  family="de la Torre Vega"
  "de la Cruz Juan Carlos"    →  family="de la Cruz Juan Carlos"
  ```
- A bare "de" stays the given name — there is nothing to fold into, and inventing a surname would be worse.
  ```
  "de"                        →  given="de"
  ```
- Stopping the run leaves a MIDDLE where the fold never left one before, so O3 has something to claim that it could not reach until now. The family it then reports is discontiguous in the input — words 1-3 plus word 5 — and renders the folded word first, which is R1's order, not this rule's doing.
  ```
  "de la Cruz Juan Carlos"  family-first+middle_as_family  →  family="Carlos de la Cruz"
  ```
- Only the OPENING position is this rule's subject. A particle standing where a family-first order puts the given name is not folded: that slot holds what the caller DECLARED to be the given name, and the never-given vocabulary supplies a reading where position leaves the question open rather than vetoing one position has already given. A particle ending the name is P6's, and only where it landed in a MIDDLE. A particle chain standing inside the name is grouped normally (P2) and positioned by the declared order, so a family-first reading may report it as the given name; what the vocabulary forbids is the bare particle reading as a given name, not any name part that begins with one.
  ```
  "Mesnil de"  family-first   →  given="de"
  "Juan de la Vega"  family-first  →  family="Juan"
  ```

---
**Signal:** position
**history:** decisions/P1 · **implemented:** nameparser/_pipeline/_post_rules.py
