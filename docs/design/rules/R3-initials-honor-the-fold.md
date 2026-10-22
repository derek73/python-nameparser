# R3 — initials honor the fold

**When:** initials are asked of a parsed name, as in "Dr. Juan Q. Xavier de la Vega III".

**Then:** initials take the first letter of each given, middle, and base family word; titles, suffixes, particles and nicknames contribute nothing.

- **A word is a particle only where its position makes it one**, not because the vocabulary lists it: where it stands as a name word it is a name word and initials.
  ```
  "Anh Do"                    →  initials="A. D."
  "Nguyen, Van Le"            →  initials="V. L. N."
  ```

- **A connective contributes nothing where it is joining** (P3). A part holding another name word for it to join — the part's working particles set aside — is a part where the connective is doing a connective's work and is no name word of its own. This is one rule for every group: a connective written among given names is a connective there too and contributes nothing where it joins. The question is asked of the WHOLE PART, never of a word count: a part of two words where one is the connective is still a part where it joins — the base of "Jon Dough and" is "Dough and" and its initials are "J. D." — and a part of three is no different. A connective with nothing in its part to join initials. A part holding nothing else is a part where it is joining nothing, and there it initials like any other name word, agreeing with the base. The part's working particles are set aside here too, so the "y" of "Juan de y" initials.
  ```
  "John and Jane Smith"       →  initials="J. J. S."
  "Duke of Edinburgh"         →  initials="D. E."
  "Juan Velasquez y Garcia"   →  initials="J. V. G."
  "Jon Dough and"             →  initials="J. D."
  "Juan de y"                 →  initials="J. y."
  ```
- **The first letter is the one the word's composed spelling begins with**, written in the form the writer used: a letter written as a base letter followed by its combining accent initials whole, and so does a syllable written as its separate parts, wherever the two compose to one character; a mark that never composes with its letter (a nukta after ज, whose precomposed U+095B is excluded from composition) is left out of the initial, while the precomposed letter keeps it.
  ```
  "émile zola"                →  initials="e\u0301. z."
  "マイケル ジャクソン"            →  initials="マ. シ\u3099."
  ```
- **Each group initials in the order its field reads**: written order, except folded family words (O3, P6), which initial before the rest of the family exactly as they render before it (R1). Which words a group contributes is this rule's question, and the order they contribute in is the field's; the field and this view never disagree about order, and can differ about membership — the family field of "Dr. Juan Q. Xavier de la Vega III" is de la Vega, where the initials take its base — so the field settles order and nothing else.
  ```
  "Hassan, Mohamad Ahmad Ali"  middle_as_family  →  initials="M. A. A. H."
  ```

**Because:** initials abbreviate the person's name words. Titles, suffixes, particles and nicknames are not name words.

```
"Dr. Juan Q. Xavier de la Vega III"  →  initials="J. Q. X. V."
"Sean O'Connor"             →  initials="S. O."  · boundary
```

**Except:**

- **A part whose every word is a particle initials those particles**: they are not acting as particles there but are the part's base (R2), and initial like any other name word, so a family that is all particles contributes its words rather than nothing.
  ```
  "Juan van der"              →  initials="J. v. d."
  ```

**Accepted:**

- This rule reads a part the parser read. A field set as raw text after the parse carries no reading, and this view is handed no vocabulary to supply one — it takes a format spec and two separators and nothing else — so every word of such a field initials, particles and conjunctions alike: a family set that way to "de la vega" gives "j. d. l. v." where parsing the same name gives "j. v.". Case repair IS handed a vocabulary, so it falls back for the one question a word can answer on its own, and R4 says which. Revising the field through the parser classifies it and matches the parse in both of the parsed name's views. (The shape needs a field edited after the parse, so no example line.)
- The v1 facade's HumanName.initials() is a second view of this question and IS handed a vocabulary: it reads the parse's connective reading wherever a word is backed by a parsed token, and falls back to the vocabulary as case repair does wherever a word is not — a field set as raw text, or a name restored from a v1 pickle or copied through the same state hooks. The particle question is never asked of the parse on that view: every word, backed or spliced alike, is looked up in the vocabulary, so a family spliced to "de la vega" initials "j. v." on that view against "j. d. l. v." on the parsed name's own. The two views agree on WHICH WORDS initial in a parsed name; what still differs there is GROUPING, the facade initialing a joined run as one element, so "Ph. D., John" gives a run-together "J. P D." on that view against "J. P. D." on this one. (Both shapes need a field edited after the parse or a rendering the other view does not have, so no example line.)
- The given group's answer is a 1.4.0 parity break, and a second one in the other direction sits beside it. A connective among given names contributed an initial from 1.4.0 until this rule reached it, so "John and Jane Smith" gives "J. J. S." where every release through 2.3 gave "J. a. J. S." and 1.4.0 gave the run-together "J a J. S."; and a connective holding a part alone now contributes one, so "محمد و علي" gives "م. و. ع." on both views, which is 1.4.0's own answer restored.

---
**Signal:** none in the name: the parsed given, middle and base family words, and the connectives joining them
**history:** decisions/R3 · **implemented:** nameparser/_render.py, nameparser/_facade.py, nameparser/_pipeline/_post_rules.py
