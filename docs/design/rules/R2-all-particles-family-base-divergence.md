# R2 — the all-particles family_base divergence

**When:** the family name of a parsed name is read with its particles set apart, as in "Dr. Juan Q. Xavier de la Vega III".

**Then:** the family name splits into further views: the base (the family without its particles) and the particles themselves.

**Because:** callers need the family name with and without its particles, and the base is that view under every naming convention, not one culture's collation or catalogue key.

```
"Dr. Juan Q. Xavier de la Vega III"  →  family_base="Vega"
"Dr. Juan Q. Xavier de la Vega III"  →  family_particles="de la"
"Juan de la Vega"           →  family_base="Vega"  · boundary
"Juan de la Vega"           →  family_particles="de la"
"Sean O'Connor"             →  family_base="O'Connor"
"da Silva do Amaral de Souza, Miguel"  →  family_base="Silva Amaral Souza"
"da Silva do Amaral de Souza, Miguel"  →  family_particles="da do de"
"Smith, de Mesnil Jean"     →  family_base="Smith Mesnil Jean"
```

**Except:**

- **A name part whose every word is particle vocabulary** is a part where none of them is doing a particle's work — nothing joins them to a name — so they read as ordinary name words: they anchor the base and leave the particles view. "Every word", not "standing alone": a two-particle run has neither word alone and both are name words there. Position decides that, not vocabulary; whether the word is borne as a surname somewhere does not enter into it.
  ```
  "Anh Do"                    →  family_base="Do"
  "Juan van der"              →  family_base="van der"
  "Juan van der"              →  family_particles=""
  ```
- **A connective standing between two words of the part is set aside when the part is asked whether every word is particle vocabulary** (P3): it is joining them, and a word doing a connective's work is never the part's base, so particles joined by a connective are all particles and anchor the base. A connective ending the part joins nothing and is a name word (R3), so the particle before it still works as one.
  ```
  "Fritz Freiherr und von Bar"  →  family_base="Freiherr und von Bar"  deviates: #939 (today: family_base="und")
  "Juan de y"                 →  family_base="y"  · boundary
  ```

**Accepted:**

- The invariant the all-particles exception exists to hold: a non-empty family always has a non-empty base. A particle needs a base to attach to, so a family that is all particles is a family whose words are not acting as particles.
  ```
  "Del Toro"  family-first    →  family_base="Del"
  ```
- The all-particles test runs after every rule that moves a token between parts, so O3's fold decides it too — a middle folded into the family can leave the family all particles, or can give a trailing particle the name word it was missing.
  ```
  "Anh Van Do"  middle_as_family  →  family_base="Van Do"
  "Nguyen, Van Le"  middle_as_family  →  family_particles="Le"
  ```

---
**Signal:** neighbor: a family part whose every word is particle vocabulary
**history:** decisions/R2 · **implemented:** nameparser/_types.py, nameparser/_pipeline/_post_rules.py, nameparser/_facade.py
