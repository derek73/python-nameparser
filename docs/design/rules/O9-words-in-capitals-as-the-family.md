# O9 — words in capitals as the family

**When:** capitals-as-family handling is active and a name in mixed case writes some of its words in capitals, as in "DUPONT Jean" or "Jeffrey LAM Kin-fung".

**Then:** the run of words in capitals is the family name wherever it stands, at the start, at the end or in the middle, and the other words keep their written order, the first the given name and the rest middle names.

- **A capitals word** is two or more letters written in capitals, after any lowercase prefix glued in front, holding nothing but letters, apostrophes and hyphens: `O'BRIEN`, `ALLIOT-MARIE`, `McDONALD` and `d'ESTAING` count; a word holding a full stop, a slash or a digit does not (`DR.`, `N/A`), nor does a word in brackets or quotes, nor single letters joined by a hyphen (`J-P`), nor a word whose capitals are one letter (`PhD`).
  ```
  "DUPONT Mary"  capitals_as_family  →  family="DUPONT"
  "DUPONT Mary"  capitals_as_family  →  given="Mary"
  "Mary DUPONT"  capitals_as_family  →  family="DUPONT"
  "Mary O'BRIEN"  capitals_as_family  →  family="O'BRIEN"
  "Mary McDONALD"  capitals_as_family  →  family="McDONALD"
  "Mary ALLIOT-MARIE"  capitals_as_family  →  family="ALLIOT-MARIE"
  "DR. Anna Berg"  capitals_as_family  →  title="DR."
  "DR. Anna Berg"  capitals_as_family  →  family="Berg"
  "Tom N/A Reed"  capitals_as_family  →  family="Reed"
  ```
- **The run is every capitals word in a row**, two surnames being one family, and particles and conjunctions between capitals words join it, in any case; a lowercase particle written right before the run joins it.
  ```
  "Ayla BURSALI AKSOY"  capitals_as_family  →  family="BURSALI AKSOY"
  "Lucie FABRE DE LA MOTTE"  capitals_as_family  →  family="FABRE DE LA MOTTE"
  "LE GRAND Hugo"  capitals_as_family  →  family="LE GRAND"
  "LE GRAND Hugo"  capitals_as_family  →  given="Hugo"
  "Aude BROSSARD de VILLEMONT"  capitals_as_family  →  family="BROSSARD de VILLEMONT"
  "Jean de LA FONTAINE"  capitals_as_family  →  family="de LA FONTAINE"
  "Mary Ellen van DER BERG"  capitals_as_family  →  family="van DER BERG"
  ```
- **A run in the middle of the name** is the family as one at either end is, the words after it middle names.
  ```
  "Jeffrey LAM Kin-fung"  capitals_as_family  →  given="Jeffrey"
  "Jeffrey LAM Kin-fung"  capitals_as_family  →  middle="Kin-fung"
  "Jeffrey LAM Kin-fung"  capitals_as_family  →  family="LAM"
  "Mrs Rita FAN HSU Lai-tai"  capitals_as_family  →  family="FAN HSU"
  ```
- **The capitals settle the field**: they outrank a credential or title reading, so a listed credential that is the only capitals word is the family (S6 reads it as the credential without the switch), and so is a title written in capitals (H1, H9), and a report asking which field a word the rule placed takes names no open fork.
  ```
  "Hugo LAC"  capitals_as_family  →  family="LAC"
  "Yanjun MA"  capitals_as_family  →  family="MA"
  "Efe ALA"  capitals_as_family  →  family="ALA"
  "DOYEN Hugo"  capitals_as_family  →  family="DOYEN"
  "Hugo LAC"  capitals_as_family  →  ambiguities=()
  ```
- **A listed credential or numeral ending the run peels off where a capitals word that is no particle is left**, at the end of the name, where the suffix slot is; a lone roman numeral of two or more letters stays the suffix, and the switch then reads nothing.
  ```
  "Mary GRAJALES III"  capitals_as_family  →  family="GRAJALES"
  "Mary GRAJALES III"  capitals_as_family  →  suffix="III"
  "Jean DUPONT MBA"  capitals_as_family  →  suffix="MBA"
  "Anna DE CARO"  capitals_as_family  →  family="DE CARO"
  "John Smith III"  capitals_as_family  →  family="Smith"
  "John Smith III"  capitals_as_family  →  suffix="III"
  ```
- **Titles, suffixes, nicknames and a maiden name keep their fields**: a title written in mixed case stays the title, and the words between brackets and in a maiden clause are no words of the name for the rule to read.
  ```
  "Dr. Mary DUPONT"  capitals_as_family  →  title="Dr."
  "Mary DUPONT Jr."  capitals_as_family  →  suffix="Jr."
  "Mary (Molly) DUPONT"  capitals_as_family  →  nickname="Molly"
  "Marie DUPONT née MARTIN"  capitals_as_family  →  maiden="MARTIN"
  ```

**Because:** in a source that writes every family name in capitals, as the French register of elected officials, Hong Kong's Legislative Council, the Turkish and Azerbaijani parliaments and the Kazakh Mazhilis do, the capitals mark the family name where position cannot: the same lists write it first, last and in the middle, and two surnames as one. A name in mixed case carries the writer's capitals as evidence; the caller who knows the source writes the convention says so, because elsewhere capitals as often write a given name or a credential.

```
"DUPONT Mary"    →  given="DUPONT"  · boundary
"Ayla BURSALI AKSOY"    →  middle="BURSALI"  · boundary
"Hugo LAC"    →  suffix="LAC"  · boundary
```

**Except:**

- **Only a name in mixed case is read: a word other than a title, a particle or a suffix holds a lowercase letter**, so a name written wholly in capitals is unaffected, and so is one whose lowercase letters are only in a title or a particle.
  ```
  "MARY DUPONT"  capitals_as_family  →  given="MARY"
  "Dr. ANITA ROY"  capitals_as_family  →  given="ANITA"
  "MARIA de SOUZA LIMA"  capitals_as_family  →  given="MARIA"
  "JOHN McCAIN"  capitals_as_family  →  given="JOHN"
  "Mary Dupont"  capitals_as_family  →  family="Dupont"
  ```
- **A run of particles alone is no run, nor is a lone roman numeral**, and the name reads by position.
  ```
  "Karim AL Haddadi"  capitals_as_family  →  family="AL Haddadi"
  "Karim AL Haddadi"  capitals_as_family  →  given="Karim"
  ```
- **Where a name word divides two runs, the last is the family**, and the earlier keeps its place among the other words.
  ```
  "PETER Okello MUWANGA"  capitals_as_family  →  given="PETER"
  "PETER Okello MUWANGA"  capitals_as_family  →  middle="Okello"
  "PETER Okello MUWANGA"  capitals_as_family  →  family="MUWANGA"
  ```
- **The switch reads only the part before the first comma**: a family comma has named the family already, and the words after a comma that sets off suffixes are read by the comma rules (C4, C6, S6).
  ```
  "Dupont, MARY"  capitals_as_family  →  family="Dupont"
  "Dupont, MARY"  capitals_as_family  →  given="MARY"
  "Laure MARTEL, MD"  capitals_as_family  →  family="MARTEL"
  "Laure MARTEL, MD"  capitals_as_family  →  suffix="MD"
  "Hon CHAN Kin-por, GBS, JP"  capitals_as_family  →  family="CHAN"
  "Hon CHAN Kin-por, GBS, JP"  capitals_as_family  →  suffix="GBS, JP"
  ```
- **A capital letter written alone is an initial or a connective** (T4, T5, P8), no capitals word, so it breaks the run.
  ```
  "Artur MAS I GAVARRO"  capitals_as_family  →  family="GAVARRO"
  ```
- **The switch cannot be set with an unlisted capitals word read as a credential everywhere** (`CapsSuffixes.EVERYWHERE`, S9): the two read the same word ending a name with no comma opposite ways, so the configuration is refused when it is built, and so is a patch that makes it (D2).
  ```
  [capitals-everywhere]  →  raises="capitals_as_family=True cannot be set with unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE"
  [capitals-patched-everywhere]  →  raises="capitals_as_family=True cannot be set with unlisted_caps_suffixes=CapsSuffixes.EVERYWHERE"
  ```

**Precedence:**

- **Against a declared order** (O4): the capitals name the family under every order, and the other words keep their written order under every order.
  ```
  "Mary DUPONT"  family-first+capitals_as_family  →  family="DUPONT"
  "DUPONT Mary Ann"  family-first-given-last+capitals_as_family  →  given="Mary"
  ```
- **Against the post rules that move words** (H1, M4, P1, P6, O1, O2): this rule reads after them and lays the name out by its capitals, so their moves never undo it.
- **Against two-family-name handling and letters ending the name** (O6, O8): the capitals named the family, so those rules stand down where this one read the name.
  ```
  "Lucie Anne MARTIN"  capitals_as_family+two_family_names  →  family="MARTIN"
  "Lakshmi R S DUPONT"  capitals_as_family+initials_as_family  →  family="DUPONT"
  ```
- **Against two-given-name handling and compound-family handling** (O7, O3): those rules read the words this one leaves, O7 joining the middle unit beside the given name and O3 folding the middles into the family.
  ```
  "Juan Carlos GARCÍA"  capitals_as_family+two_given_names  →  given="Juan Carlos"
  "Mary Ann DUPONT"  capitals_as_family+middle_as_family  →  family="Ann DUPONT"
  ```
- **Against a patronymic** (R9): the patronymic view reads the words the rule leaves in the middle under the rules a policy turns on.
  ```
  "ИВАНОВ Иван Иванович"  capitals_as_family+east-slavic  →  patronymic="Иванович"
  ```

**Accepted:**

- Joined initials in the middle of a name are a capitals word, so they read as the family: the same shape as `Jeffrey LAM Kin-fung`, which no length can tell apart. 4,246 of ORCID's 2025 records put such a run in the given box (decisions/O9).
  ```
  "Jan GM Brouwer"  capitals_as_family  →  family="GM"
  ```
- A credential written after the surname with no comma is the run, and so the family: 757 ORCID records, none from a source that writes families in capitals (decisions/O9).
  ```
  "John Smith MD"  capitals_as_family  →  family="MD"
  ```
- A surname whose last word spells a listed credential loses it to the suffix where a capitals word is left (`MBALLA MBA`, 19 of 46,200 ORCID records with the family box in capitals, decisions/O9).
- A given name written in capitals in a name whose family is not reads as the family; that is the convention's other writing, and why the switch is off by default.
  ```
  "ANNA Smith"  capitals_as_family  →  family="ANNA"
  ```
- An unlisted post-nominal after a listed one, with no comma, is the last run, so it reads as the family once the listed one peels off.
  ```
  "Hon CHAN Kin-por GBS JP"  capitals_as_family  →  family="GBS"
  ```
- `capitalized()` leaves a name in mixed case as written, so the family keeps its capitals; `capitalized(force=True)` recases them, the family being named by its field by then (R5).
- A bare `DR` in capitals at the head of a name is a capitals word, so it reads as the family (204 ORCID given boxes open with it); whether a title that is never a surname should stand is open (decisions/O9).
  ```
  "DR Anna BERG"  capitals_as_family  →  family="BERG"
  "DR Anna Berg"  capitals_as_family  →  family="DR"
  ```
- The rule reports nothing of its own: the caller declared the convention.

---
**Signal:** case contrast + position: a caller switch, and the words written in capitals in a name written in more than one case
**history:** decisions/O9 · **implemented:** nameparser/_pipeline/_post_rules.py, nameparser/_pipeline/_vocab.py, nameparser/_policy.py
