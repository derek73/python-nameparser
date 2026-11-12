# O8 — letters ending a name as its family

**When:** initials-as-family handling is active and a name ends in two or more single letters after a name word, as in "Lakshmi R S".

**Then:** the letters ending the name are its family name: the letters standing in a row before a family name written as one letter join it, and the name words before them are the given name and the middle names.

- **A letter is read as an initial is** (T5): a bare Latin capital or a letter and its period, spaced, so dotted and mixed letters are one run; a run written joined is one word already, which the family takes by position.
  ```
  "Lakshmi R S"  initials_as_family  →  family="R S"
  "Lakshmi R S"  initials_as_family  →  given="Lakshmi"
  "Lakshmi R. S."  initials_as_family  →  family="R. S."
  "Lakshmi R. S"  initials_as_family  →  family="R. S"
  "Ram Bahadur B K"  initials_as_family  →  middle="Bahadur"
  "Ram Bahadur B K"  initials_as_family  →  family="B K"
  "Lakshmi R S T"  initials_as_family  →  family="R S T"
  "Lakshmi R.S."  initials_as_family  →  family="R.S."
  ```
- **In a name written wholly in one case** the letters are initials in both spellings (T4), so both read alike; a lower-case letter among capitals is no initial and stays where it is.
  ```
  "LAKSHMI R S"  initials_as_family  →  family="R S"
  "lakshmi r s"  initials_as_family  →  family="r s"
  "Lakshmi r s"  initials_as_family  →  family="s"
  ```
- **Titles, suffixes, nicknames and a maiden name are no name words**, so the letters before them still end the name, and a comma that sets off only suffixes leaves the name before it to this rule.
  ```
  "Dr. Lakshmi R S"  initials_as_family  →  family="R S"
  "Lakshmi R S Jr."  initials_as_family  →  family="R S"
  "Lakshmi R S, PhD"  initials_as_family  →  family="R S"
  "Lakshmi (Lax) R S"  initials_as_family  →  family="R S"
  "Lakshmi R S née Rao"  initials_as_family  →  family="R S"
  ```

**Because:** in South India, Sri Lanka, Bangladesh and Nepal the letters written after a given name often stand for the father's name, the family's place of origin or a surname written short (`B K` for Bishwakarma, `K C` for Khatri Chhetri), and the bearer treats them as the family name. Written given-first, that name is the same string as a given name followed by a middle and a family initial, or a bibliographic byline written surname first, and no rule can read which from the words; the caller who knows the data is written that way says so.

```
"Lakshmi R S"    →  family="S"  · boundary
"Ram Bahadur B K"    →  middle="Bahadur B"  · boundary
```

**Except:**

- **One letter is the family by position already**, so there is nothing for the rule to join.
  ```
  "Kavitha S"  initials_as_family  →  family="S"
  ```
- **Letters before the name or inside it end nothing**, and a name written as nothing but letters keeps its first letter as the given name.
  ```
  "R S Lakshmi"  initials_as_family  →  family="Lakshmi"
  "John A B Smith"  initials_as_family  →  middle="A B"
  "J R S"  initials_as_family  →  given="J"
  "J R S"  initials_as_family  →  family="S"
  ```
- **A word that is no initial breaks the run**: a letter outside T5's shape, a one-letter particle (P7), or a nickname between the letters.
  ```
  "Lakshmi R É"  initials_as_family  →  family="É"
  "Maria R d S"  initials_as_family  →  family="S"
  "Lakshmi R (Lax) S"  initials_as_family  →  family="S"
  ```
- **A family comma names the family**, so the letters after it are the given part, read as any given part is.
  ```
  "Lakshmi, R S"  initials_as_family  →  family="Lakshmi"
  "Lakshmi, R S"  initials_as_family  →  given="R"
  ```
- **A family-first order places the family already**: under it the letters ending a name are the given name and the middle names it declares, as a byline written surname first reads.
  ```
  "Huntley R P"  family-first+initials_as_family  →  family="Huntley"
  "Huntley R P"  family-first+initials_as_family  →  given="R"
  "Huntley R P"  family-first-given-last+initials_as_family  →  given="P"
  ```

**Precedence:**

- **Against two-family-name handling** ("Ram Bahadur B K" with both switches on): this rule reads first, and that rule then finds a family of two words, which it leaves as it is (O6).
  ```
  "Ram Bahadur B K"  initials_as_family+two_family_names  →  middle="Bahadur"
  "Ram Bahadur B K"  initials_as_family+two_family_names  →  family="B K"
  ```
- **Against two-given-name handling**: this rule reads first, and that rule takes the middle the letters leave (O7), so a letter that rule would take as a second given name (O7 takes an initial) goes to the family.
  ```
  "Ram Bahadur B K"  initials_as_family+two_given_names  →  given="Ram Bahadur"
  "Ram R S"  initials_as_family+two_given_names  →  given="Ram"
  "Ram R S"  initials_as_family+two_given_names  →  family="R S"
  ```
- **Against compound-family handling**: this rule reads first, and O3 then folds the middles it leaves into the family.
  ```
  "Ram Bahadur B K"  initials_as_family+middle_as_family  →  family="Bahadur B K"
  ```
- **Against a connective between the letters** (P3, P8): the connective joins its letters into the family already, which this rule leaves as it is, a letter before them included: the rule joins letters only to a family written as one.
  ```
  "Maria R y S"  initials_as_family  →  family="R y S"
  "Maria R A y S"  initials_as_family  →  middle="R"
  "Maria R A y S"  initials_as_family  →  family="A y S"
  ```

**Accepted:**

- A name ending in a middle and a family initial loses its middle initial to the family, which is the shape the switch cannot tell from the one it is for: an English or Brazilian name written short reads that way under it. That is why it is off by default.
  ```
  "Melanie J D"  initials_as_family  →  family="J D"
  ```
- A roman numeral written after letters is one of them where it is no listed suffix the trailing run takes first (S10), as `V` and `I` are initials by shape.
  ```
  "Henry V I"  initials_as_family  →  family="V I"
  "Lakshmi R S III"  initials_as_family  →  suffix="III"
  "Lakshmi R S V"  initials_as_family  →  family="R S V"
  ```
- A particle opening the name that position reads as the given name (P1 folds only a never-given one) is the name word before the letters, so the letters after it are the family.
  ```
  "van R S"  initials_as_family  →  given="van"
  "van R S"  initials_as_family  →  family="R S"
  ```
- Three or more letters joined with full stops are an unlisted dotted post-nominal before any rule reads them as a family (S3), so the name word before them stays the family.
  ```
  "Ram Bahadur B.K.T."  initials_as_family  →  family="Bahadur"
  "Ram Bahadur B.K.T."  initials_as_family  →  suffix="B.K.T."
  ```
- Letters written in Devanagari are no initials (T5 reads a Latin letter), so a surname written so keeps its last letter as the family: 598 of nepal-candidates' 237,408 corpus spellings end that way (`वि क` 259, `बि क` 109, `वि. क.` 59; counted 2026-11-11, decisions/O8). Whether a Devanagari letter is an initial is #1273's question.
  ```
  "राम बहादुर वि क"  initials_as_family  →  family="क"
  ```
- The rule reports nothing: the caller declared the convention, as O6's switch reports nothing.

---
**Signal:** none in the name + position + shape: a caller switch, and the letters' written shape (T5) and position at the end of the name words
**history:** decisions/O8 · **implemented:** nameparser/_pipeline/_post_rules.py
