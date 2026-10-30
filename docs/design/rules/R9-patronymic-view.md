# R9 — the patronymic view

**When:** a name holds a word saying whose child the bearer is, a patronymic particle the vocabulary lists before the parent's name, as in "Mahathir bin Mohamad", or a patronymic ending or marker an opt-in rule reads, as in "Ivan Ivanovich Ivanov" under the East Slavic rule.

**Then:** the words read as a patronymic, in whichever field the parse put them, make the patronymic view, every field keeping them, and the view joins them with spaces in written order, the family's words in the order the family writes them.

- **A patronymic particle**: a particle the shipped vocabulary holds as a patronymic, read as a particle, with the words after it in its field, the parent's name.
- **The East Slavic rule** (`PatronymicRule.EAST_SLAVIC`, which RU turns on): a middle word carrying O1's patronymic ending.
- **The Turkic rule** (`PatronymicRule.TURKIC`, which TR_AZ turns on): a standalone patronymic marker, O2's, with the name word before it in its comma part, the father's name, a marker in the maiden name taking the maiden name's word before it.

**Because:** a patronymic names the parent, which a caller addressing the bearer or matching records needs to tell from a family name, and the people filling in fielded records, like CLDR's samples, put it in the family or the given part. Naming it in a view of its own leaves every field where those sources put it. The view reads only a word or a rule that says patronymic, never a position, since nothing in a name's shape says which name word is a parent's.

```
"Mahathir bin Mohamad"      →  patronymic="bin Mohamad"
"Mahathir bin Mohamad"      →  family="bin Mohamad"
"Ahmad bin Abdul Rahman"    →  patronymic="bin Abdul Rahman"
"Abdul Rahman bin Ahmad"    →  patronymic="bin Ahmad"
"Ali bin Ahmad bin Hasan"   →  patronymic="bin Ahmad bin Hasan"
"Siti binti Abu Bakar"      →  patronymic="binti Abu Bakar"
"Moshe bar Yosef"           →  patronymic="bar Yosef"
"محمد بن سلمان"              →  patronymic="بن سلمان"
"Mahathir bin Mohamad Jr."  →  patronymic="bin Mohamad"
"bin Mohamad, Mahathir"     →  patronymic="bin Mohamad"
"Siti Hasan née binti Ali"  →  patronymic="binti Ali"
"Ivan Ivanovich Ivanov"  [ru]  →  patronymic="Ivanovich"
"Ivan Ivanovich Ivanov"  [ru]  →  middle="Ivanovich"
"Sidorov Ivan Petrovich"  [ru]  →  patronymic="Petrovich"
"Ivanov, Ivan Ivanovich"  [ru]  →  patronymic="Ivanovich"
"Aliyev, Heydar Alirza oglu"  [tr_az]  →  patronymic="Alirza oglu"
"Ali Ahmad Vali oglu"  [tr_az]  →  patronymic="Vali oglu"
"Leyla née Aliyeva qizi"  [tr_az]  →  patronymic="Aliyeva qizi"
"Ivan Ivanovich Ivanov"     →  patronymic=""  · boundary
"Anwar Ibrahim"             →  patronymic=""
```

**Except:**

- **A patronymic particle read as a name word names no parent**, so where the parse reads it as a given name it is no patronymic.
  ```
  "Mahathir, bin Mohamad"     →  patronymic=""
  "bin Mohamad"               →  patronymic=""
  ```
- **A patronymic particle ending its field names no parent**, so a family word spelled like one stays a name word.
  ```
  "Fritz Freiherr und von Bar"  →  patronymic=""
  ```
- **A trailing patronymic particle P6 attaches to the family written before it** takes that family's words as the parent's name, the view writing them in the family's order, under `middle_as_family` too.
  ```
  "Mohamad, Mahathir bin"     →  patronymic="bin Mohamad"
  "Levi, Omer Bar"            →  patronymic="Bar Levi"
  ```
- **A nickname inside the parent's name** is skipped, not a word of the view.
  ```
  "Ahmad bin “Bob” Ali"       →  patronymic="bin Ali"
  ```
- **A Turkic marker with no name word before it in its comma part** names no father and is no patronymic, and neither does one in the maiden name with no maiden word before it.
  ```
  "oglu Ali"  [tr_az]         →  patronymic=""
  "Aliyev, oglu"  [tr_az]     →  patronymic=""
  "Ali née oglu"  [tr_az]     →  patronymic=""
  ```

**Accepted:**

- A patronymic written with no particle and no rule to read it is not read, since a position says nothing about a parent: Wikidata's Malay names with a patronymic and no family name agree 4 of 9, those written without `bin` read as given and family.
- The particle's run is every word after it in its field, so where the parse joined more than the parent's name the view holds it too, as the family does: a never-given particle opening the name takes the rest of it by default (P1).
  ```
  "ibn Ali Hasan"             →  patronymic="ibn Ali Hasan"
  ```
- The East Slavic arm reads the middle only, the field the parse puts a patronymic in after a given name: one the parse put in the family (a two-word `Ivan Petrovich`) or in the given name (FAMILY_FIRST_GIVEN_LAST's last word) is not read, and under a declared FAMILY_FIRST a surname the order puts in the middle is, `Иван Петрович Абрамович` reading patronymic `Абрамович`, the declaration O1 honors.
- The East Slavic endings are O1's, so a Ukrainian `-ївна` (`Оксана Сергіївна Баюл`) is not read.
- The Turkic father's name may stand in another field than the marker, as O2 leaves a three-word name, and a two-word name with a marker is read whole, a family name spelled as a marker included.
  ```
  "Ali Ahmad oglu"  [tr_az]   →  patronymic="Ahmad oglu"
  "Ali oglu"  [tr_az]         →  patronymic="Ali oglu"
  "Mehmet Oğlu"  [tr_az]      →  patronymic="Mehmet Oğlu"
  ```
- A word inside the particle's run is in it whatever it is read as, a title included.
  ```
  "Ahmad bin Dr. Ali"         →  patronymic="bin Dr. Ali"
  ```
- A particle is read only as a word of its own, so one glued to the name by a hyphen is not, nor one written with its vowel marks, which the vocabulary does not list.
  ```
  "Ahmad ibn-Ali"             →  patronymic=""
  "مُحَمَّد بِن سَلمان"          →  patronymic=""
  ```
- Under `two_family_names` O6 takes the middle word into the family as a first family name, leaving the East Slavic arm no middle to read, so `Ivan Ivanovich Ivanov` under RU with it reads family `Ivanovich Ivanov` and no patronymic.
- A word with no reading, one that `replace()` or `Parser.revise()` wrote or in a name unpickled from 2.x, is not in the view, since nothing records what it was read as.
- A patronymic particle is the shipped vocabulary's, read whatever the reading's default, as R8 reads a suffix word's kind, so a word only a caller's `Lexicon` lists as a particle (`ben`, which the vocabulary excludes as a patronymic) is a plain particle.
- A word the particle's run or the Turkic marker takes reads `patronymic` by position, its own reading (a name word, a bound given name, a particle) not kept in `Token.reading`.

---
**Signal:** neighbor + shape: a listed patronymic particle before the parent's name or an opt-in marker after it, and an opt-in patronymic ending on a middle word
**history:** decisions/R9 · **implemented:** nameparser/_types.py, nameparser/_pipeline/_assemble.py, nameparser/_pipeline/_classify.py, nameparser/_pipeline/_vocab.py
