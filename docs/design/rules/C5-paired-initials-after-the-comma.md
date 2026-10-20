# C5 — paired initials after the comma

**When:** paired initials — two single letters joined by a period, with or without a period after the second ('M.J.', 'M.J') — stand in the part after the comma, as in "García Márquez, G.J.".

**Then:** paired initials are the exception to the ambiguous credential class's count (C4): the one dotted shape a person's own initials are written in, they are read as the given name after the comma.

- **Undotted, where the name carries the case contrast C6 asks for**, an unlisted word of two capitals after the comma is the paired initials' shape and is decided at this comma exactly as they are ('García Márquez, MJ' and 'García Márquez, MJ PhD' keep given 'MJ').
  ```
  "García Márquez, MJ"        →  given="MJ"  · boundary
  "García Márquez, MJ PhD"    →  given="MJ"  · boundary
  ```

**Because:** two words before the comma may be one surname written in two ('García Márquez'), and the count cannot tell them from a given name and a family name.

```
"Smith, A.B."               →  given="A.B."  · boundary
"García Márquez, G.J."      →  given="G.J."
"García Márquez, G.J."      →  family="García Márquez"
"John Smith, A.B."          →  given="A.B."
"García Márquez, G.J"       →  given="G.J"
```

**Except:**

- **Only an unambiguous suffix word in front of them that is not also title vocabulary, or another word the class admits by its dotted shape standing in the same part, makes them the credential run.** A word of this class in front of them speaks for nothing, as S7's company has it, and where nothing but words of both the suffix and the title vocabulary stands in front of them, those are the titles of the given part the initials open, as S7 reads them there.
  ```
  "John Smith, PhD X.Y."      →  suffix="PhD X.Y."
  "De La Cruz, M.J. PhD"      →  given="M.J."  · boundary
  "García Márquez, Ms G.J."   →  given="G.J."  · boundary
  "García Márquez, Ed G.J."   →  given="Ed"  · boundary
  "John Smith, A.B. Ph.D."    →  given="A.B."  · boundary
  ```
- **Behind two or more name words, paired initials that are not the only shape word in the part are a credential** however little else speaks for them, since no one writes a person's initials as two dotted groups.
  ```
  "García Márquez, MJ JK"     →  suffix="MJ JK"
  "John Smith, X.Y. P.Q."     →  suffix="X.Y. P.Q."
  ```

**Precedence:**

- **A generation ending the name before the comma** ("John Smith Jr., M.J."): dotted, the paired initials keep this rule's reading and are the given name, the generation staying the suffix; undotted as two capitals, they are the credential C12 reads (C1).

**Accepted:**

- Three or more initials run together with periods behind a surname of two words read as a credential. Initials are conventionally written apart ('J. R. R.'), and a token of three or more single letters run together is far likelier a credential than a given name and a middle name written as one word.
  ```
  "García Márquez, G.J.R."    →  suffix="G.J.R."
  ```

---
**Signal:** shape: paired initials after the comma, dotted or as two undotted capitals
**history:** decisions/C5 · **implemented:** nameparser/_pipeline/_comma.py
