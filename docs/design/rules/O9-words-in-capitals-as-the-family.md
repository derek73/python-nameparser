# O9 — words in capitals as the family

**When:** capitals-as-family handling is active and a name in mixed case writes some of its words in capitals, as in "DUPONT Jean" or "Jeffrey LAM Kin-fung".

**Then:** the run of words in capitals is the family name wherever it stands, at the start, at the end or in the middle, and the other words keep their written order, the first that may be a given name the given name and the rest middle names.

- **A capitals word** is two or more letters written in capitals ending the word, after any letters glued in front, holding nothing but letters, apostrophes and hyphens: `O'BRIEN`, `ALLIOT-MARIE`, `McDONALD`, `d'ESTAING`, `DuPONT` and `Jean-PIERRE` count; a word holding a full stop, a slash or a digit does not (`DR.`, `N/A`), nor does a word in brackets or quotes, nor single letters joined by a hyphen (`J-P`), nor a word whose capitals are one letter (`PhD`).
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
- **The run is every capitals word in a row**, two surnames being one family, and particles and conjunctions between capitals words join it, in any case, a listed conjunction of one letter written bare included (with its full stop it is an initial); a run neither opens nor ends in a conjunction; a lowercase particle written right before the run joins it.
  ```
  "Ayla BURSALI AKSOY"  capitals_as_family  →  family="BURSALI AKSOY"
  "Lucie FABRE DE LA MOTTE"  capitals_as_family  →  family="FABRE DE LA MOTTE"
  "LE GRAND Hugo"  capitals_as_family  →  family="LE GRAND"
  "LE GRAND Hugo"  capitals_as_family  →  given="Hugo"
  "Aude BROSSARD de VILLEMONT"  capitals_as_family  →  family="BROSSARD de VILLEMONT"
  "Jean de LA FONTAINE"  capitals_as_family  →  family="de LA FONTAINE"
  "Mary Ellen van DER BERG"  capitals_as_family  →  family="van DER BERG"
  "Ana LOPEZ Y GARCIA"  capitals_as_family  →  family="LOPEZ Y GARCIA"
  "Artur MAS I GAVARRO"  capitals_as_family  →  family="MAS I GAVARRO"
  "Mary SMITH AND Jones"  capitals_as_family  →  family="SMITH"
  "Ana LOPEZ Y. GARCIA"  capitals_as_family  →  family="GARCIA"
  ```
- **The first unit holding a word that may be a given name is the given name**: a conjunction or a particle written in lowercase outside the run is a joining word, so a lowercase particle opening a unit stays with the word after it and a unit of nothing else is a middle name, while a particle written with a capital, as a name is, is read as one.
  ```
  "JEAN y Perez"  capitals_as_family  →  given="Perez"
  "JEAN y Perez"  capitals_as_family  →  middle="y"
  "de Marie DUPONT"  capitals_as_family  →  given="de Marie"
  "Van Mary DUPONT"  capitals_as_family  →  given="Van"
  "De Marie DUPONT"  capitals_as_family  →  given="De"
  "MORRISON Van"  capitals_as_family  →  given="Van"
  "Marie DUPONT y MBA"  capitals_as_family  →  middle="y"
  ```
- **A run in the middle of the name** is the family as one at either end is, the words after it middle names.
  ```
  "Jeffrey LAM Kin-fung"  capitals_as_family  →  given="Jeffrey"
  "Jeffrey LAM Kin-fung"  capitals_as_family  →  middle="Kin-fung"
  "Jeffrey LAM Kin-fung"  capitals_as_family  →  family="LAM"
  "Mrs Rita FAN HSU Lai-tai"  capitals_as_family  →  family="FAN HSU"
  ```
- **The capitals settle the field**: they outrank a credential or title reading, so a listed suffix that is the only capitals word is the family (without the switch S6 reads a credential so written as the suffix, S11's count a suffix word that is also a name, and S10's a numeral), and so is a title written in capitals (H1, H9); a report asking which field a word of the run or a word the peel took takes names no open fork, nor does one asking whether a lone name word is the given or the family name, whether a particle opens the family, or which order the name is written in, while a title or suffix fork on any other word stands, under every order.
  ```
  "Hugo LAC"  capitals_as_family  →  family="LAC"
  "Yanjun MA"  capitals_as_family  →  family="MA"
  "Efe ALA"  capitals_as_family  →  family="ALA"
  "DOYEN Hugo"  capitals_as_family  →  family="DOYEN"
  "Hugo LAC"  capitals_as_family  →  ambiguities=()
  "Dean Mary DUPONT"  capitals_as_family  →  ambiguities=("title-or-name",)
  "Van Mary DUPONT"  capitals_as_family  →  ambiguities=()
  "Ram Bahadur KC"  capitals_as_family  →  family="KC"
  "Pedro Alves NETO"  capitals_as_family  →  family="NETO"
  "Kavitha S MA"  capitals_as_family  →  ambiguities=()
  "Pedro ALVES NETO"  capitals_as_family  →  ambiguities=()
  ```
- **A listed credential or numeral ending the name peels off before a run is chosen, wherever a capitals word that is no particle is left**: the suffix slot is read from the end, past a suffix written otherwise, so a credential a name word cuts off from the family comes off too; only a word in capitals peels, a joining word or an unlisted word in capitals ending the slot; a lone roman numeral of two or more letters stays the suffix, and the switch then reads nothing; a numeral is one the generation reading knows, II to X.
  ```
  "Mary GRAJALES III"  capitals_as_family  →  family="GRAJALES"
  "Mary GRAJALES III"  capitals_as_family  →  suffix="III"
  "Jean DUPONT MBA"  capitals_as_family  →  suffix="MBA"
  "Joan MAS i MBA"  capitals_as_family  →  suffix="MBA"
  "DUPONT Marie MBA"  capitals_as_family  →  family="DUPONT"
  "DUPONT Marie MBA"  capitals_as_family  →  suffix="MBA"
  "Marie DUPONT Jr. MBA"  capitals_as_family  →  suffix="Jr. MBA"
  "Anna DE CARO"  capitals_as_family  →  family="DE CARO"
  "John Smith III"  capitals_as_family  →  family="Smith"
  "John Smith III"  capitals_as_family  →  suffix="III"
  ```
- **A word the patronymic rule in force reads as its marker is no capitals word**, neither forming a run nor joining one, so the family and the patronymic never share it: a Turkic marker under that rule (`OGLU`, `QIZI`), and a word with an East Slavic patronymic ending under that one (R9).
  ```
  "ALIYEV Ilham Heydar OGLU"  capitals_as_family+turkic  →  family="ALIYEV"
  "ALIYEV Ilham Heydar OGLU"  capitals_as_family+turkic  →  patronymic="Heydar OGLU"
  "ИВАНОВ Иван ИВАНОВИЧ"  capitals_as_family+east-slavic  →  family="ИВАНОВ"
  ```
- **Titles, suffixes, nicknames and a maiden name keep their fields**: a title written in mixed case stays the title, and the words between brackets and in a maiden clause are no words of the name for the rule to read.
  ```
  "Dr. Mary DUPONT"  capitals_as_family  →  title="Dr."
  "Mary DUPONT Jr."  capitals_as_family  →  suffix="Jr."
  "Mary (Molly) DUPONT"  capitals_as_family  →  nickname="Molly"
  "Marie DUPONT née MARTIN"  capitals_as_family  →  maiden="MARTIN"
  ```

**Because:** in a source that writes every family name in capitals, as the French register of elected officials, Hong Kong's Legislative Council, the Turkish and Azerbaijani parliaments and the Kazakh Mazhilis do, the capitals mark the family name where position cannot: the same lists write it first, last and in the middle, and two surnames as one. A name in mixed case carries the writer's capitals as evidence; the caller who knows the source writes the convention says so, because elsewhere the same capitals are a given name or a credential often enough to cost: where one of ORCID's two boxes is written wholly in capitals, it is the given box about one time in ten (decisions/O9).

```
"DUPONT Mary"    →  given="DUPONT"  · boundary
"Ayla BURSALI AKSOY"    →  middle="BURSALI"  · boundary
"Hugo LAC"    →  suffix="LAC"  · boundary
```

**Except:**

- **Only a name in mixed case is read: a word other than a title, a particle, a conjunction or a suffix holds a lowercase letter**, read over the words no run took once the peel has taken its own: a name written wholly in capitals is unaffected, and so is one whose lowercase letters are only in a title, a suffix, a particle or conjunction written in lowercase, or a word a run joined; a particle written with a capital outside a run is a name word like any other.
  ```
  "MARY DUPONT"  capitals_as_family  →  given="MARY"
  "Dr. ANITA ROY"  capitals_as_family  →  given="ANITA"
  "MARIA de SOUZA LIMA"  capitals_as_family  →  given="MARIA"
  "JOHN McCAIN"  capitals_as_family  →  given="JOHN"
  "MARIA y LOPEZ GARCIA"  capitals_as_family  →  family="GARCIA"
  "JAN Van DER BERG"  capitals_as_family  →  given="JAN"
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
- **The switch reads only the part before the first comma**: a family comma has named the family already, and the words after a comma that sets off suffixes are read by the comma rules (C4, C6, S6); a comma with nothing before it leaves no part to read, though it named no family.
  ```
  "Dupont, MARY"  capitals_as_family  →  family="Dupont"
  "Dupont, MARY"  capitals_as_family  →  given="MARY"
  "Laure MARTEL, MD"  capitals_as_family  →  family="MARTEL"
  "Laure MARTEL, MD"  capitals_as_family  →  suffix="MD"
  "Hon CHAN Kin-por, GBS, JP"  capitals_as_family  →  family="CHAN"
  "Hon CHAN Kin-por, GBS, JP"  capitals_as_family  →  suffix="GBS, JP"
  ", DUPONT Marie"  capitals_as_family  →  given="DUPONT"
  ```
- **A capital letter written alone is an initial** (T4, T5, P8), no capitals word, so it breaks a run, unless it is a listed conjunction standing between two capitals words.
  ```
  "Mary Y SMITH"  capitals_as_family  →  middle="Y"
  "Mary Y SMITH"  capitals_as_family  →  family="SMITH"
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
- **Against a declared order, the given name and the middle names**: "under every order" holds for the family; where a joining word chained into a unit by its neighbours ends up beside the given name, how the words outside the run divide between the given and the middle names can follow the unit and the order (below).
- **Against two-given-name handling and compound-family handling** (O7, O3): those rules read the words this one leaves, O7 joining the middle unit beside the given name and O3 folding the middles into the family.
  ```
  "Juan Carlos GARCÍA"  capitals_as_family+two_given_names  →  given="Juan Carlos"
  "Mary Ann DUPONT"  capitals_as_family+middle_as_family  →  family="Ann DUPONT"
  ```
- **Against a suffix word that is also a name, and a trailing numeral** (S11, S10): their counts read such a word ending the name as the suffix, reporting it; under the switch the word written in capitals is the family where it is the run's only word that is no particle, and the report goes.
  ```
  "John Paul JUNIOR"  capitals_as_family  →  family="JUNIOR"
  "Jean Pierre FILS"  capitals_as_family  →  family="FILS"
  ```
- **Against a patronymic** (R9): the patronymic view reads the words the rule leaves in the middle under the rules a policy turns on.
  ```
  "ИВАНОВ Иван Иванович"  capitals_as_family+east-slavic  →  patronymic="Иванович"
  ```

**Accepted:**

- Joined initials in the middle of a name are a capitals word, so they read as the family: the same shape as `Jeffrey LAM Kin-fung`, which no length can tell apart. 4,246 records of the 2025-10 ORCID dump put such a run in the given box (counted 2026-11-12, decisions/O9).
  ```
  "Jan GM Brouwer"  capitals_as_family  →  family="GM"
  ```
- A credential written after the surname with no comma is the run, and so the family: 757 records of the 2025-10 ORCID dump, none from a source that writes families in capitals (counted 2026-11-12, decisions/O9).
  ```
  "John Smith MD"  capitals_as_family  →  family="MD"
  ```
- A surname whose last word spells a listed credential loses it to the suffix where a capitals word is left (`MBALLA MBA`, 19 of the 46,200 records with the family box in capitals in the capped ORCID corpus, counted 2026-11-11, decisions/O9).
- A particle written in Title case right before the run stays out of it, only a lowercase one joining, so a family name that opens with one loses it to the middle name.
  ```
  "Mary Van DUPONT"  capitals_as_family  →  middle="Van"
  ```
- A given name written in capitals in a name whose family is not reads as the family; that is the convention's other writing, and why the switch is off by default.
  ```
  "ANNA Smith"  capitals_as_family  →  family="ANNA"
  ```
- An unlisted post-nominal after a listed one, with no comma, is the last run, so it reads as the family once the listed one peels off.
  ```
  "Hon CHAN Kin-por GBS JP"  capitals_as_family  →  family="GBS"
  ```
- `capitalized()` leaves a name in mixed case as written, so the family keeps its capitals; `capitalized(force=True)` recases them, the family being named by its field by then (R5).
- A bare `DR` in capitals at the head of a name is a capitals word, so it reads as the family (204 given boxes of the 2025-10 ORCID dump open with it, counted 2026-11-12); whether a title that is never a surname should stand is open (decisions/O9).
  ```
  "DR Anna BERG"  capitals_as_family  →  family="BERG"
  "DR Anna Berg"  capitals_as_family  →  family="DR"
  ```
- A numeral is one the generation reading knows, II to X, so a longer one is a word of the run, and one standing before the family name is read with it.
  ```
  "Mary DUPONT XI"  capitals_as_family  →  family="DUPONT XI"
  "Marie II DUPONT"  capitals_as_family  →  family="II DUPONT"
  ```
- A word the peel took is the suffix with no report, though the peel can take a surname's last word (`MBALLA MBA`, above).
  ```
  "Pedro ALVES NETO"  capitals_as_family  →  suffix="NETO"
  ```
- A joining word written after the family name, with nothing to join, is laid out by the declared order.
  ```
  "DUPONT Mary y"  capitals_as_family  →  given="Mary y"
  "DUPONT Mary y"  family-first+capitals_as_family  →  middle="y"
  ```
- A lowercase conjunction the name's units chained to a word can open the given name, so a joining word's place follows the units and the order, unwritten shapes all.
  ```
  "MARTIN y Ana Maria"  capitals_as_family  →  given="y Ana"
  "MARTIN y Ana"  capitals_as_family  →  given="Ana"
  ```
- With no patronymic rule in force a marker written in capitals is a capitals word like any other, and can be the family.
  ```
  "ALIYEV Ilham Heydar OGLU"  capitals_as_family  →  family="OGLU"
  ```
- A word in capitals with any letters glued in front counts, a capital among them or not, so a hyphenated given name in capitals makes a name otherwise in capitals no mixed name, which reads by position.
  ```
  "DUPONT Jean-PIERRE"  capitals_as_family  →  family="Jean-PIERRE"
  ```
- Shapes no list writes read as the run takes them: a numeral inside a run (`MARY III Smith` → family `MARY III`), conjunctions in a row (`Mary AND AND AND SMITH` → family `SMITH`), a name word after a credential (`Anna Y MD Mary` → family `MD`, suffix `Mary`), and a particle opening the given name initialled as a name word (`de Marie DUPONT` → `d. M. D.`).
  ```
  "Anna Y MD Mary"  capitals_as_family  →  suffix="Mary"
  ```
- A conjunction in capitals trimmed off the front of a run keeps the field it was read in, a title where it opened the name.
  ```
  "THE ROCK Mary"  capitals_as_family  →  title="THE"
  ```
- The rule reports nothing of its own: the caller declared the convention.

---
**Signal:** none in the name + case contrast: a caller switch, and the words written in capitals in a name written in more than one case
**history:** decisions/O9 · **implemented:** nameparser/_pipeline/_post_rules.py, nameparser/_pipeline/_vocab.py, nameparser/_policy.py
