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

**Because:** two words before the comma may be one surname written in two ('García Márquez'), and the count cannot tell them from a given name and a family name.

```
"Smith, A.B."               →  given_names="A.B."  · boundary
"García Márquez, G.J."      →  given_names="G.J."
"García Márquez, G.J."      →  family="García Márquez"
"John Smith, A.B."          →  given_names="A.B."
"García Márquez, G.J"       →  given_names="G.J"
```

**Except:**

- **Only an unambiguous suffix word in front of them that is not also title vocabulary, or another word the class admits by its dotted shape standing in the same part, makes them the credential run**, save the undotted pair's company of credentials above. A word of this class in front of them speaks for nothing, as S7's company has it, and where nothing but words of both the suffix and the title vocabulary stands in front of them, those are the titles of the given part the initials open, as S7 reads them there.
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
- **A generation ending the name before the comma** ("John Smith Jr., M.J."): dotted, the paired initials keep this rule's reading and are the given name, parted by T7, the generation staying the suffix; undotted as two capitals, they are the credential C12 reads (C1, where a roman numeral S10 reads stays the suffix as a listed generation does).

**Accepted:**

- Undotted initials of a given name behind a surname of two words, written with credentials behind them, read as a credential with the rest: two capitals before credentials are a credential far more often than initials in the populations that write them, and the dotted pair, how initials are written, keeps its reading. `CapsSuffixes.OFF` keeps the given name, the caps shape admitting nothing.
  ```
  "García Márquez, MJ PhD"    →  suffix="MJ PhD"
  ```

- Three or more initials run together with periods behind a surname of two words read as a credential. Initials are conventionally written apart ('J. R. R.'), and a token of three or more single letters run together is far likelier a credential than a given name and a middle name written as one word.
  ```
  "García Márquez, G.J.R."    →  suffix="G.J.R."
  ```

---
**Signal:** shape: paired initials after the comma, dotted or as two undotted capitals + neighbor: credentials behind the undotted pair
**history:** decisions/C5 · **implemented:** nameparser/_pipeline/_comma.py
