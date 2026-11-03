# R8 — the generation, credentials and honorifics views

**When:** the suffix of a parsed name is read by what each of its words is, as in "Smith, John, Jr., MD, Esq.".

**Then:** the suffix splits into three views that partition it, the generation holding its words read as a generation or an agnomen, the honorifics its words read as a form of address written after the name, and the credentials every other word, each joining its words in written order and separating two of them by a comma where the suffix holds one anywhere between them, R1's separator, and by a space where it holds none.

**Because:** a generation numbers the bearer among relatives of the same name while a credential is earned, and CLDR's person-name fields keep the two apart and format them differently. A form of address after the name (`さん`, `씨`, `先生`) is neither: it is no part of the name on either side (W3), and CLDR files it as a title, while an office written there (`議員`) is a credential in CLDR as in this view. A caller wanting one had to re-read the suffix against vocabulary they would have had to rebuild (#326), and all three are views, so the suffix field itself does not change.

```
"Smith, John, Jr., MD, Esq."  →  generation="Jr."
"Smith, John, Jr., MD, Esq."  →  credentials="MD, Esq."
"Smith, John, Jr., MD, Esq."  →  suffix="Jr., MD, Esq."
"Dr. Juan Q. Xavier de la Vega III"  →  generation="III"
"Pedro Alves Filho"         →  generation="Filho"
"John Smith Esq."           →  credentials="Esq."
"王小明先生"                  →  honorifics="先生"
"王小明先生"                  →  credentials=""
"김민준 씨"                   →  honorifics="씨"
"田中さん, PhD"               →  credentials="PhD"
"田中さん, PhD"               →  honorifics="さん"
"王小明 議員"                 →  credentials="議員"
"John Smith Jr. III PhD"    →  generation="Jr. III"
"John Smith Jr. III PhD"    →  credentials="PhD"
"John Smith Ph. D. Jr."     →  credentials="Ph. D."
"John Smith, MD Jr. PhD"    →  credentials="MD PhD"
"John Smith, MD, Jr. PhD"   →  credentials="MD, PhD"
"John Smith, MD / Jr. / PhD"  →  credentials="MD, PhD"
"John Smith, PhD and MD Jr."  →  credentials="PhD and MD"
"John Smith PhD"            →  generation=""
"John Smith"                →  generation=""  · boundary
"John Smith"                →  credentials=""
"John Smith"                →  honorifics=""
```

**Except:**

- **A connective in the suffix** is in the view of the word before it, being read as none of the three.
  ```
  "John Smith, Jr. and III"   →  generation="Jr. and III"
  ```

**Accepted:**

- A word of the suffix vocabulary that is neither a generation, a credential nor a form of address (a courtesy such as `Esq.`, a status such as `ret.`) is in the credentials, CLDR's catch-all, which CLDR's own examples of the field include `Esq.` in; its reading's kind, a post-nominal word, tells it apart for a caller who needs it. A courtesy that is itself said to the bearer (`Rinpoche`, `महाराज`) is there too, by its kind, beside the honorifics a word like `साहब` reads as.
  ```
  "John Smith, Jr., Esq."     →  credentials="Esq."
  "Ram Das महाराज"            →  credentials="महाराज"
  ```
- A connective joining a generation to a credential is left at the end of the generation, the view of the word before it.
  ```
  "John Smith, Jr. and MD"    →  generation="Jr. and"
  ```
- A suffix word with no reading, one that `replace()` or `Parser.revise()` wrote or in a name unpickled from 2.x, is in the credentials whatever it is, since nothing records what it was read as.
- A word with a delimiter glued on keeps it in the view, as the suffix keeps it (C10), so the view can end in the delimiter.
  ```
  "John Smith, Jr.; MD"       →  generation="Jr.;"
  ```
- A suffix word read by its period-joined chunks, as a title written `Lt.Gov.` is, is listed whole by no suffix word, so it has no kind of its own and is in the credentials, a word made only of generation words included; before the first comma a period-written generation word with a delimiter glued on reaches the suffix only this way, while one written without the period stays a name word.
  ```
  "John Smith Jr.III"         →  credentials="Jr.III"
  "John Smith, Jr.III"        →  credentials="Jr.III"
  "John Smith Jr.; MD"        →  credentials="Jr.; MD"
  "John Smith Jr; MD"         →  family="Jr;"
  ```
- A name word in the suffix, one a run took in by where it stands, is in the credentials, the catch-all.
  ```
  "Smith, Jr., John"          →  credentials="John"
  ```
- The kind of a word listed as a suffix word is the lexicon's, the kind of the suffix reading its `Lexicon` holds, so a word a caller adds as a generation (`add("secundus", kind="generation")`) reads as one, a word added as an honorific or a professional honorific is in the honorifics, and a word added as a credential, as a plain `suffix`, or as a status or courtesy word is in the credentials, a credential written as a word (`acronym=False`) as the gated `KC` is (S11); an agnomen reads as an agnomen. On the default lexicon the kind is the shipped vocabulary's, which compiles it, and a lexicon whose readings a caller removed reads the kind it holds, not the files'.
  ```
  "John Smith KC"             →  credentials="KC"
  ```

---
**Signal:** none in the name: the reading each suffix word took
**history:** decisions/R8 · **implemented:** nameparser/_types.py, nameparser/_pipeline/_classify.py
