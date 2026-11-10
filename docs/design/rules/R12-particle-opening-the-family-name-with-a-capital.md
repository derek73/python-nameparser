# R12 — a particle opening the family name with a capital

**When:** case repair meets a family word whose particle reading the vocabulary writes with a capital where it opens the family name, as in "LEVON TER PETROSYAN".

**Then:** the word is written as a name word is where the word before it in the family name, in the order the family is written out, is no particle, and keeps a particle's lowercase after one.

- **A particle closing a hyphenated word counts as one**, the hyphenated word's last part being particle vocabulary, in the family name or, where the word opens the family name, as the last middle name, a surname's first half the parse read as a middle name (`Maitland-van der Zee`).
- **A particle written right before the family name counts whatever its role**, where the word opens the family name: a Dutch surname written without a given name capitalizes only its first particle, which the parse reads as the given name (`Van der Walt`, `Van ter Horst`).

**Because:** the Armenian priestly prefix (Ter, Der) opens a surname with a capital, where the Dutch and German particles it spells stand behind another particle written in lowercase (van der, von der, van ter). The particle before the word is the one thing in the written name that tells the two apart, and a spelling-based guess at the language is no signal.

```
"LEVON TER PETROSYAN"       →  capitalized="Levon Ter Petrosyan"
"ARMEN DER KIUREGHIAN"      →  capitalized="Armen Der Kiureghian"
"TER PETROSYAN, LEVON"      →  capitalized="Levon Ter Petrosyan"
"PETROSYAN, LEVON TER"      →  capitalized="Levon Ter Petrosyan"
"Levon ter Petrosyan"       →  capitalized_forced="Levon Ter Petrosyan"
"VAN DER WALT"              →  capitalized="Van der Walt"  · boundary
"VAN TER HORST"             →  capitalized="Van ter Horst"  · boundary
"Van der Walt"              →  capitalized_forced="Van der Walt"  · boundary
"JAN VAN DER BERG"          →  capitalized="Jan van der Berg"  · boundary
"JAN VAN TER HORST"         →  capitalized="Jan van ter Horst"  · boundary
"URSULA VON DER LEYEN"      →  capitalized="Ursula von der Leyen"  · boundary
"VAN DER BERG, JAN"         →  capitalized="Jan van der Berg"  · boundary
"DER BERG, JAN VAN"         →  capitalized="Jan van der Berg"  · boundary
"TER HORST, JAN VAN"        →  capitalized="Jan van ter Horst"  · boundary
"ANNA AZ- DER BERG"         →  capitalized="Anna az- der Berg"  · boundary
"ANKE MAITLAND-VAN DER ZEE"  →  capitalized="Anke Maitland-van der Zee"  · boundary
"DER ZEE, ANKE MAITLAND-VAN"  →  capitalized="Anke Maitland-van der Zee"  · boundary
"JAN TER HORST VAN DER BERG"  →  capitalized="Jan ter Horst van der Berg"  · boundary
```

**Precedence:**

- **A particle standing apart, which R4 writes in lowercase** ("LEVON TER PETROSYAN"): R12 wins where the word opens the family name, R4's particle bullet leaving such a word to it.

**Accepted:**

- The word takes its capital whatever language it is written in, since nothing in its spelling tells the Armenian prefix from the Dutch and German particle: a Dutch surname opened by `ter` is written with a capital, and a German `der` behind a word the vocabulary does not list as a particle (`aus der`) opens the family name as far as repair can tell.
  ```
  "GERARD TER BORCH"          →  capitalized="Gerard Ter Borch"  · boundary
  "KAREN AUS DER FÜNTEN"      →  capitalized="Karen Aus Der Fünten"  · boundary
  ```
- A German epithet the parse places in the family name takes the capital too, its article opening the family name there.
  ```
  "ALEXANDRE DUMAS DER ÄLTERE"  →  capitalized="Alexandre Dumas Der Ältere"  · boundary
  "JOHANN DER JÜNGERE"        →  capitalized="Johann Der Jüngere"  · boundary
  ```
- A Taiwanese given-name syllable `Der`, which the parse places in the family name, takes the capital its writers give it, the parse itself being unchanged.
  ```
  "JA DER LIANG"              →  capitalized="Ja Der Liang"  · boundary
  ```

---
**Signal:** neighbor: the word before it in the family name, or the word written right before the family name in any role where it opens the family, a particle or not
**history:** decisions/R12 · **implemented:** nameparser/_render.py
