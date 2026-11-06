# P10 — a given name a particle completes

**When:** a given name of one word begins the name words of a name read given-first, and the particle chain behind it opens with a particle run and a word the vocabulary names a given name written behind a particle, as in "María del Carmen García".

**Then:** the particle run and that word are a middle name, so the chain's other words are the family.

- **The word is one a reading marks** (`after_particle`), the second of a compound given name written behind a particle: the Marian and devotional names (del Carmen, de los Ángeles, del Pilar, de Lourdes), marked on Spanish counts and written in Portuguese names too (do Socorro, de Fátima), and the Portuguese ones marked on Portuguese counts (de Lurdes, do Céu, da Glória, de Tarso).
  ```
  "María del Carmen García"   →  middle="del Carmen"
  "María del Carmen García"   →  family="García"
  "María de los Ángeles López Pérez"  →  family="López Pérez"
  "Ana de María Pérez"        →  middle="de María"
  "Maria do Socorro Silva"    →  middle="do Socorro"
  "Maria de Lurdes Costa"     →  middle="de Lurdes"
  "Paulo de Tarso Ribeiro"    →  family="Ribeiro"
  "Maria do Carmo Silva"      →  family="do Carmo Silva"  · boundary
  "João da Silva Santos"      →  family="da Silva Santos"  · boundary
  ```
- **A word filers write as a given name less surely is marked for its language alone**, read where the caller chooses that language and left to the surname otherwise: Portuguese das Graças, de Cássia and da Piedade.
  ```
  "Maria das Graças Silva"  [pt]  →  middle="das Graças"
  "RITA DE CASSIA SOUZA"  [pt_br]  →  family="SOUZA"
  "Maria das Graças Silva"    →  family="das Graças Silva"  · boundary
  "Maria das Graças Silva"  [es]  →  family="das Graças Silva"  · boundary
  ```
- **A title, a suffix and a nickname are no name words**, so they stand outside the reading.
  ```
  "Dr. María del Mar García Jr."  →  middle="del Mar"
  "María del Carmen García, PhD"  →  family="García"
  ```

**Because:** across Spain, Portugal and Latin America a compound given name is often a Marian or devotional title written with a particle, María del Carmen, María de los Ángeles, so given-first the given name's second half stands where a particle surname would begin. The word behind the particle says which it is: written there, `Carmen` and `Ángeles` are given names, where `Silva` and `Cruz` begin surnames. Filers who split such a name into boxes put the phrase with the given names, not with the surname.

```
"María del Carmen"          →  family="del Carmen"  · boundary
"García, María del Carmen"  →  middle="del Carmen"  · boundary
```

**Except:**

- **A name word must be left for the family**, one with a letter that is no connective standing alone, the phrase being one unit (a connective joining the word behind it, P3, makes the unit longer); and under the Turkic patronymic rule (R9), no marker may stand behind the phrase, whose father's name it would be.
  ```
  "María del Carmen y"        →  family="del Carmen y"
  "María del Carmen 3"        →  family="del Carmen 3"
  "María del Carmen y García"  →  family="del Carmen y García"
  ```
- **A run holding a saint particle opens a surname**: a phrase written with San, Santa or St, or with Sta. or Sto., names a place or a family, never a given name's second half.
  ```
  "Domingo Santa María González"  →  family="Santa María González"
  "Juan Sta. Maria Reyes"         →  family="Sta. Maria Reyes"
  ```
- **The given name must be one name word, and a name word itself**: a given name of two words (a hyphen, a bound given-name pair, P5) keeps what it has, and a patronymic (R9), a name a community gives every member, or a mark with no letter completes nothing.
  ```
  "María-José del Carmen García"  →  family="del Carmen García"
  "Abu Bakr del Carmen García"    →  family="del Carmen García"
  "Kaur del Carmen García"        →  family="del Carmen García"
  "bin del Carmen García"         →  family="del Carmen García"
  "3 del Carmen García"           →  family="del Carmen García"
  ```
- **A middle name between them leaves the chain to the family**, the phrase no longer standing beside the given name.
  ```
  "Ana María del Carmen García"   →  family="del Carmen García"
  ```
- **A family-first order puts no family behind the given name**, and lays its own name out (O4).
  ```
  "María del Carmen García"  family-first  →  given="del Carmen García"
  ```

**Precedence:**

- **Against two-given-name handling** (O7): this rule reads first, so the phrase is the middle unit beside the given name that O7 takes.
  ```
  "María del Carmen García"  two_given_names  →  given="María del Carmen"
  ```
- **Against two-family-name handling** (O6): this rule reads first, and O6 leaves the phrase where it stands.
  ```
  "María del Carmen de la Vega"  two_family_names  →  middle="del Carmen"
  ```

**Accepted:**

- A surname written with a marked word behind its particle reads as a middle name and the rest of the family, where the vocabulary cannot tell the two apart: `del Valle`, `del Rosario` and `de Jesús` open a family box in about one ORCID record in ten of those holding them.
  ```
  "Pedro del Valle Llufrio"   →  middle="del Valle"
  ```
- The family a phrase leaves behind keeps the words P2 chained into one unit, so two-family-name handling reads no second surname in it.
  ```
  "María del Carmen García López"  two_family_names  →  surname2=""
  ```
- The rule reports nothing: the vocabulary says which reading the word takes, and a report on every such name would teach the caller to ignore the field.

---
**Signal:** position: the word behind a particle run opening the family, looked up as a given name written there; the run's particles, looked up for a saint; and the given name, looked up as a name a community gives every member: vocabulary signals tagged by where the word stands, as P1's is
**history:** decisions/P10 · **implemented:** nameparser/_pipeline/_post_rules.py
