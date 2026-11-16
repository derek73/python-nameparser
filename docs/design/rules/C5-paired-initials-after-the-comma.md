# C5 — paired initials after the comma

**When:** paired initials — two single letters joined by a period, with or without a period after the second ('M.J.', 'M.J') — stand in the part after the comma, as in "García Márquez, G.J.".

**Then:** paired initials are the exception to the ambiguous credential class's count (C4): the one dotted shape a person's own initials are written in, they are read as the given name after the comma, which T7 then parts into a given and a middle initial where it reaches them.

- **Undotted, where the name carries the case contrast C6 asks for**, an unlisted word of two capitals after the comma is the paired initials' shape and is decided at this comma as they are ('García Márquez, MJ' keeps given 'MJ'), save one thing: undotted, two capitals followed by credentials and standing beside nothing else are the credential run ('Jane Doe, BM PhD'). A credential here is a word of the company C16 reads beside its run that its own writing settles: a generation, spelled out or as a numeral, an agnomen and a word gated by the count (S11) are none, nor a member of the ambiguous class in Title case (S6), nor a particle, nor a title in front of the pair even written in capitals, though a title/suffix dual in capitals behind it is one, as in C16's company; a word joined by a slash or a hyphen is asked chunk by chunk, as its words written apart would be. With nothing behind the pair, a word in front of it makes it the credential run only as the Except below has it, an unambiguous suffix word that is no title ('Jane Doe, PhD MJ'). A suffix ending the name before the comma takes nothing from this: behind a generation the pair reads as C12 reads it alone ('Jane Doe Jr., MJ M.D.'), and behind a credential, where C12 leaves the bare pair the given name, the pair before credentials is the credential run all the same ('Jane Doe MD, MJ PhD').
  ```
  "García Márquez, MJ"        →  given="MJ"  · boundary
  "Jane Doe, BM PhD"          →  suffix="BM PhD"
  "Jane Doe, MA BM FRCP"      →  suffix="MA BM FRCP"
  "Jane Doe, BM Jr."          →  given="BM"  · boundary
  "Jane Doe, MJ Junior"       →  given="MJ"  · boundary
  "Jane Doe, MJ Ed"           →  given="MJ"  · boundary
  "John Smith, RA MJ"         →  given="MJ"  · boundary
  "Jane Doe, MS BM PhD"       →  given="BM"  · boundary
  "Jane Doe, MJ MS"           →  suffix="MJ MS"
  "Jane Doe, MJ MD/Jr."       →  given="MJ"  · boundary
  "García Márquez, Ms MJ PhD" →  given="MJ"  · boundary
  "Jane Doe Jr., MJ M.D."     →  suffix="Jr., MJ M.D."
  "Jane Doe MD, MJ PhD"       →  suffix="MD, MJ PhD"
  ```
- **Alone in its part, two capitals with a listed credential in a later comma part are the credential run, dotted or not** ('Jane Mary Doe, MH, PhD', 'Jane Mary Doe, M.H., PhD'), a credential behind them speaking from a later part where none stands in their own. The pair is what the bullet above reads: an unlisted word, so undotted capitals that spell a particle or a connective stay a name, behind two or more name words (C4) in a name that carries C6's contrast, which the dotted pair has to meet here too, as two capitals, whatever its letters spell. For such a pair this narrows the reading above: dotted, it is the given name after the comma only where no later part is such a credential; the undotted pair is asked of the capitals' switch and the dotted one of the dotted shape's. A later part is that credential where every word of it is company the bullet above would take beside the pair and the vocabulary lists: a suffix word that is no generation, a title/suffix dual only in capitals, a listed member of the ambiguous class only where its capitals settle it (S6), a credential split across a space as S12 reads one, and a word joined by a slash or a hyphen, asked chunk by chunk for a generation, a word gated by the count and a member its capitals do not settle; a particle standing as a word, a word gated by the count (S11) and a word read as a credential by its shape alone (S3) each make the part none, a part with no word in it answers nothing, and a delimiter standing alone between its words is no word of it (C10). Any later part answers, not only the next and not only the last, and the parts are then read as C2 reads them. A suffix ending the name before the comma takes nothing from this, a generation included. With company in their own part the two capitals are decided by that part alone, as above, where the dotted pair keeps the given name.
  ```
  "Jane Mary Doe, MH, PhD"    →  suffix="MH, PhD"
  "Jane Mary Doe, MH, PhD"    →  given="Jane"
  "Jane Mary Doe, M.H., PhD"  →  suffix="M.H., PhD"
  "Jane Doe, M.H, PhD"        →  suffix="M.H, PhD"
  "Jane Doe, BM, BCh, PhD"    →  suffix="BM, BCh, PhD"
  "Jane Doe, MH, Jr., PhD"    →  suffix="MH, Jr., PhD"
  "Jane Doe, MH, PhD, Jr."    →  suffix="MH, PhD, Jr."
  "Jane Doe, MH, MD - PhD"    →  suffix="MH, MD, PhD"
  "Jane Doe, MH, MD/PhD"      →  suffix="MH, MD/PhD"
  "Jane Doe MD, MH, PhD"      →  suffix="MD, MH, PhD"
  "Jane Doe Jr., M.H., PhD"   →  suffix="Jr., M.H., PhD"
  "Jane Doe, M.H., PhD"  unlisted_caps_suffixes-off  →  suffix="M.H., PhD"
  "Jane Doe, MH, Jr."         →  given="MH"  · boundary
  "Jane Doe, M.H., Jr."       →  given_names="M.H."  · boundary
  "Jane Doe, MH, Ma"          →  given="MH"  · boundary
  "Jane Doe, MH, Mc"          →  given="MH"  · boundary
  "Jane Doe, MH, MD/Jr."      →  given="MH"  · boundary
  "Jane Doe, MH, XYZ"         →  given="MH"  · boundary
  "Jane Doe, MH, M. A."       →  given="MH"  · boundary
  "Jane Doe, AL, PhD"         →  given="AL"  · boundary
  "Jane Doe, MH, M. D."       →  given="MH"  · boundary
  "Jane Doe, MH Jr., PhD"     →  given="MH"  · boundary
  "Jane Doe, Ms MH, PhD"      →  given="MH"  · boundary
  "Jane Doe, M.H. PhD"        →  given_names="M.H."  · boundary
  "Jane Doe, m.h., PhD"       →  given="m.h."  · boundary
  "Jane Doe, Mh, PhD"         →  given="Mh"  · boundary
  "Doe, MH, PhD"              →  given="MH"  · boundary
  "Doe, M.H., PhD"            →  given_names="M.H."  · boundary
  "JANE DOE, MH, PHD"         →  given="MH"  · boundary
  "JANE DOE, M.H., PHD"       →  given_names="M.H."  · boundary
  "Jane Doe, MH, PhD"  unlisted_caps_suffixes-off  →  given="MH"
  "Jane Doe, M.H., PhD"  unlisted_dotted_suffixes-off  →  given_names="M.H."
  ```

**Because:** two words before the comma may be one surname written in two ('García Márquez'), and the count cannot tell them from a given name and a family name.

```
"Smith, A.B."               →  given_names="A.B."  · boundary
"García Márquez, G.J."      →  given_names="G.J."
"García Márquez, G.J."      →  family="García Márquez"
"John Smith, A.B."          →  given_names="A.B."
"García Márquez, G.J"       →  given_names="G.J"
```

**Except:**

- **Only an unambiguous suffix word in front of them that is not also title vocabulary, or another word the class admits by its dotted shape standing in the same part, makes them the credential run**, save the undotted pair's company of credentials above and a later part's listed credential behind a pair alone in its part. A word of this class in front of them speaks for nothing, as S7's company has it, and where nothing but words of both the suffix and the title vocabulary stands in front of them, those are the titles of the given part the initials open, as S7 reads them there.
  ```
  "John Smith, PhD X.Y."      →  suffix="PhD X.Y."
  "De La Cruz, M.J. PhD"      →  given_names="M.J."  · boundary
  "García Márquez, Ms G.J."   →  given_names="G.J."  · boundary
  "García Márquez, Ed G.J."   →  given="Ed"  · boundary
  "John Smith, A.B. Ph.D."    →  given_names="A.B."  · boundary
  ```
- **Behind two or more name words, paired initials that are not the only shape word in the part are a credential** however little else speaks for them, since no one writes a person's initials as two dotted groups.
  ```
  "García Márquez, MJ JK"     →  suffix="MJ JK"
  "John Smith, X.Y. P.Q."     →  suffix="X.Y. P.Q."
  ```

**Precedence:**

- **A title the run of letters spells, with a title behind it** ("García Márquez, U.S. Senator John"): the paired initials C5 keeps as the given part are H10's title where the vocabulary marks the title they spell as written that way.
  ```
  "García Márquez, U.S. Senator John"  →  title="U.S. Senator"
  ```
- **A generation ending the name before the comma** ("John Smith Jr., M.J."): dotted, the paired initials keep this rule's reading and are the given name, parted by T7, the generation staying the suffix, unless a later part's listed credential speaks for them, which is asked first and reports as the count does; undotted as two capitals, they are the credential C12 reads (C1, where a roman numeral S10 reads stays the suffix as a listed generation does).

**Accepted:**

- Undotted initials of a given name behind a surname of two words, written with credentials behind them, read as a credential with the rest: two capitals before credentials are a credential far more often than initials in the populations that write them, and the dotted pair, how initials are written, keeps its reading. `CapsSuffixes.OFF` keeps the given name, the caps shape admitting nothing.
  ```
  "García Márquez, MJ PhD"    →  suffix="MJ PhD"
  ```

- The same holds across a comma, and there for the dotted pair too: initials alone in their part behind a surname of two words, or of words a connective joins, read as a credential where a later part is a listed credential. No name of the kind was found where the rule was measured, every such pair read there being a credential.
  ```
  "García Márquez, MJ, PhD"   →  suffix="MJ, PhD"
  "Ortega y Gasset, MJ, PhD"  →  suffix="MJ, PhD"
  "García Márquez, M.J., PhD"  →  suffix="M.J., PhD"
  ```

- A given name or a surname that two capitals spell, dotted or not, is not held back there: the pair is read by its shape, and a word listed as a name in another writing is unlisted in this one. Undotted capitals that spell a particle or a connective are a listed word and stay a name; dotted, the same letters are a pair like any other. Nor is a later part's credential that a given name written short also spells, in whatever case, as in the pair's own part.
  ```
  "Ana Ruiz, JO, MD"          →  suffix="JO, MD"
  "Ram Bahadur, BK, MD"       →  suffix="BK, MD"
  "Ram Bahadur, BK, MD"  [ne]  →  suffix="BK, MD"
  "Ram Bahadur, B.K., MD"     →  suffix="B.K., MD"
  "Ram Bahadur, B.K., MD"  [ne]  →  suffix="B.K., MD"
  "Jane Doe, MH, Md"          →  suffix="MH, Md"
  "Jane Doe, A.L., PhD"       →  suffix="A.L., PhD"
  ```

- A part between the two capitals and the listed credential is taken with them whatever it holds, a name word included, and keeps C2's flag.
  ```
  "Jane Doe, MH, John, PhD"   →  suffix="MH, John, PhD"
  "Jane Doe, MH, John, PhD"   →  ambiguities=("comma-structure", "suffix-or-name")
  ```

- A full name the count reads as one name word (C3: a capitalized particle with its surname, a word that is a title and a particle with its surname) keeps the listing form, so the two capitals stay the given name there.
  ```
  "Bin Zhang, MH, PhD"        →  given="MH"
  "Freiherr von Berg, MH, PhD"  →  given="MH"
  ```

- Three or more initials run together with periods behind a surname of two words read as a credential. Initials are conventionally written apart ('J. R. R.'), and a token of three or more single letters run together is far likelier a credential than a given name and a middle name written as one word.
  ```
  "García Márquez, G.J.R."    →  suffix="G.J.R."
  ```

---
**Signal:** shape: paired initials after the comma, dotted or as two undotted capitals + neighbor: credentials behind the undotted pair in its part, or behind either pair in a later part
**history:** decisions/C5 · **implemented:** nameparser/_pipeline/_comma.py
