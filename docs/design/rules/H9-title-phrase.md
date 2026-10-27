# H9 — the title phrase

**When:** a title word that is also borne as a given name, or a word that only qualifies a head title, stands where a title would be read, as in "Dean Smith" or "Wing Lau".

**Then:** the word is a title only inside a title phrase, and elsewhere a name word.

- **A title that may be a given name** has its phrase partner in a modifier or a style before it that is a title there, in a title before it that attaches to it, in a title after it that it attaches to, or in `of` after it. No other title before it is one, a salutation least of all, and no other title after it: a donor list writes the salutation after the given name.
  ```
  "Dean of Students Jane Smith"  →  title="Dean of Students"
  "Associate Dean Smith"      →  title="Associate Dean"
  "Major General John Smith"  →  title="Major General"
  "Chief Justice John Roberts"  →  title="Chief Justice"
  "The Hon. Justice Mary Smith"  →  title="The Hon. Justice"
  "His Grace John Smith"      →  title="His Grace"
  "Field Marshal Bernard Montgomery"  →  title="Field Marshal"
  "Sergeant Major John Smith"  →  title="Sergeant Major"
  "Mr Dean Smith"             →  given="Dean"
  "SMITH, DEAN MR."           →  given="DEAN"
  "General Major John Smith"  →  given="Major"
  "Grace Dean Smith"          →  given="Grace"
  "Sgt Marshal Smith"         →  given="Marshal"
  "Mr Mahdi Karimi"           →  given="Mahdi"
  "Buddha Bahadur Tamang"     →  given="Buddha"
  "King Curtis"               →  given="King"
  "Sultana Begum"             →  given="Sultana"
  "Mr Shaikh Ahmed"           →  given="Shaikh"
  ```
- **A modifier in the leading run of titles before the first comma** has its phrase in a head title after it in that run, in `of` after it, or in the object of `of` or `the` there. A modifier outside that run, ending the name or after a comma, is read as any title is, save one that may be a given name, which is read everywhere as it is in that run.
  ```
  "Wing Commander Lau"        →  title="Wing Commander"
  "Mr Wing Lau"               →  given="Wing"
  "Mr. and Mrs. Wing Lau"     →  given="Wing"
  "President of the United States Barack Obama"  →  title="President of the United States"
  "Mother Superior of the Convent Mary Smith"  →  title="Mother Superior of the Convent"
  "Jane Smith Vice."          →  title="Vice."
  "John Smith, Vice"          →  title="Vice"
  "Lau, Wing"                 →  given="Wing"
  "Lau, Wing Commander"       →  title="Wing Commander"
  "John Smith Wing."          →  family="Wing."
  ```
- **A title that may be a given name, read as a name word where it is the first name word after any titles and no comma has marked the given name,** is reported as `title-or-name` where a phrase the vocabulary lists holds it; inside a phrase, later in the name, or in the given part after a family comma, it is not. A word no listed phrase holds is a title only behind a style or a modifier, or before `of`, the partners every such word shares, so standing alone it is no title a reader would hesitate over.
  ```
  "Dean Smith"                →  ambiguities=("title-or-name",)
  "Marshal Yanda"             →  ambiguities=("title-or-name",)
  "Mr Dean Smith"             →  ambiguities=("title-or-name",)
  "Dean Smith, MD"            →  ambiguities=("title-or-name",)
  "Grace Smith"               →  ambiguities=()
  "Bard Larsen"               →  ambiguities=()
  "GRACE SMITH"               →  ambiguities=()
  "SMITH, DEAN MR."           →  ambiguities=()
  ", Dean"                    →  ambiguities=()
  "Major General John Smith"  →  ambiguities=()
  "John Dean Smith"           →  ambiguities=()
  ```

**Because:** a title addresses the name after it, so the front of a name has no count to read, and what tells the person "Dean Smith" from the office in "Dean of Students" is the phrase the word stands in. A word that only qualifies a head title, as wing qualifies commander, says nothing about the person on its own. After a comma the part is read as written there, as decision 10 measured: a lone title word in a part after the name is the person's role, and reading it as a name reversed the name, save a word also borne as a given name, which the name data measured so far writes there as the listing form's given name, or at the end as a surname, rather than a role.

```
"Dean Smith"                →  given="Dean"
"Major Smith"               →  given="Major"
"Wing Lau"                  →  given="Wing"
"Mr Smith"                  →  title="Mr"  · boundary
"Wing Commander Lau"        →  ambiguities=()  · boundary
```

**Precedence:**

- **A modifier that may be a given name** is read by the modifier's test in every part, its run being its phrase, not by the partners of a title that may be a given name: a style before it is no partner of itself.
  ```
  "Hon. Wing Lau"             →  given="Wing"
  ```
- **A period-marked word in the leading run of titles** (H2): the abbreviation shape makes it a title whatever the vocabulary says, save a given name written short or a word a connective joins (below), so the phrase test never reaches it and nothing is reported, at the front of the name or behind another title; a style that may be a given name, made a title by the shape alone, is no partner of the word behind it, where a modifier is (`Wing. Dean Smith` → title 'Wing. Dean').
  ```
  "Dean. Smith"               →  title="Dean."
  "Wing. Lau"                 →  title="Wing."
  "Mr Buddha. Tamang"         →  title="Mr Buddha."
  "Shaikh. Sultan Khan"       →  given="Sultan"
  ```
- **A title run** (H3, H4): a word this rule reads as a name word is no title word to the run, so the run stops before it and does not count it.
  ```
  "Mr Dean Smith"             →  title="Mr"
  "Dean"                      →  given="Dean"
  ```
- **A connective after the word** (P3): only `of` makes a phrase of the join, so a word read as a name word before `and` joins the next word as two names join, and so does one written with its period, the join taking it before H2's shape is asked.
  ```
  "Dean and Mary Smith"       →  given="Dean and Mary"
  "Dean. and Mary Smith"      →  given="Dean. and Mary"
  ```
- **A title that may be a given name which a caller lists in `titles`** is a title wherever it stands, since that is what listing it asks; a modifier is read by this rule however it is listed, and leaving its word out of the modifiers turns the rule off for it.

**Accepted:**

- A judge styled with a salutation reads the salutation as the title and the word as the given name, since a salutation is never a partner; the people who write a salutation before the word file it as their forename.
  ```
  "Mr Justice Smith"          →  given="Justice"
  ```
- A modifier whose head is not a listed title loses the title, as with duke, which the vocabulary refuses, and so does a modifier written after its head with no `of` behind it.
  ```
  "Grand Duke of Tuscany"     →  given="Grand"
  "Princess Royal Anne"       →  given="Royal"
  ```
- In the given part after a family comma a modifier that is not also a given name is read as listed, so the listing form and the written order of one name read it differently, the cost decision 10 took for the parts where a lone title word is a role.
  ```
  "Hudson, Rock"              →  title="Rock"
  ```
- A phrase that is the whole given part after a family comma leaves the given name empty, as a lone title there does.
  ```
  "Smith, Sgt Major"          →  title="Sgt Major"
  ```
- A modifier that may be a given name keeps the title wherever its run's test finds a phrase it does not form, in the object of `the` behind a style, and before a suffix whose period H2's shape reads as a head.
  ```
  "The Hon. Wing Lau"         →  title="The Hon. Wing"
  "John Smith Wing. Jr."      →  title="Wing."
  ```
- An epithet that is also a given name, written with its article before the name or after a comma, reads as a name word, the article joining it; no name data at hand writes either shape.
  ```
  "The Mahdi Muhammad Ahmad"  →  given="The Mahdi"
  "William Shakespeare, the Bard"  →  given="the Bard"
  ```
- A religious title that opens given names in another tradition, written bare, reads as a name word before a name in every tradition, behind any title but a style, a modifier or one that attaches to it; no name data at hand writes the title there.
  ```
  "Gyani Zail Singh"          →  given="Gyani"
  "Lord Buddha Tamang"        →  given="Buddha"
  ```
- A ruler written with the bare title in front reads it as the given name, a style before it or `of` after it keeping the title; the record data at hand writes the word there almost only as a given name, and rulers that way mostly in news text.
  ```
  "King Henry"                →  given="King"
  "Sultan Hassanal Bolkiah"   →  given="Sultan"
  "Shaikh Hamad bin Isa"      →  given="Shaikh"
  "His Majesty King Charles"  →  title="His Majesty King"
  ```
- Once a partner has made the word a title, a coordinating join behind it takes the next word into the title too.
  ```
  "Chief Dean and Mary Smith" →  title="Chief Dean and Mary"
  ```

---
**Signal:** neighbor: the titles and connectives beside a listed title word in its run of titles
**history:** decisions/H9 · **implemented:** nameparser/_pipeline/_classify.py, nameparser/_pipeline/_vocab.py, nameparser/_pipeline/_assign.py
